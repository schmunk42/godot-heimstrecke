# file generated with AI assistance: Claude Code - 2026-10-21 22:40:00 UTC
"""Bridge decks (stage A2.2b).

roads.py draws a bridge as a straight chord between its abutment nodes.
Over a road the chord can sag far below a real deck, so raise_decks
first lifts the deck where it crosses another drivable road: wherever a
bridge segment crosses (plan view) a segment of an edge that shares no
node with it and the bridge is at least GRADE_SEP above it, the surface
must clear the other road by CLEAR_MIN plus DECK_DEPTH. The requirement
holds over the other road's width and falls off at RAMP_GRADE; nodes
inside a bridge chain may rise (interpolate_structures with a lower
bound) as far as MAX_NODE_GRADE from the abutment nodes allows, which
stay, and the lifted profile is smoothed over RAMP_SMOOTH and kept
inside the MAX_SURFACE_GRADE cones of its node heights. Where that is
not enough (a short bridge between two abutments), the ground road
below gets a dip of the same shape; DGM1 under a bridge is interpolated
anyway, the laser does not see under the deck. OSM layer tags are not
used.

Then every 5 m segment of a bridge edge is classified by DGM1 on the
centre line and both deck edge lines:

- deck: the underside (surface - DECK_DEPTH) is at least GAP_MIN above
  DGM1 at both ends on all three lines. The segment gets a deck body:
  a walkway beside the strip, a parapet, the outer faces and the
  underside. conform.py keeps DGM1 under it.
- low: everything else (a short bridge over a brook or a path, a chord
  running into a slope). No deck body, so nothing sinks into the
  terrain or stands on it as a bulge; conform.py treats the segment
  like a ground road.

Deck runs shorter than MIN_DECK_RUN between two abutments become low.
Where a deck run ends (an abutment: the next segment is low, a ground
road or nothing) an end face closes the body down to WALL_FOOT below
the terrain, and conform.py pins the terrain triangles crossing the
abutment line to the deck's ground plane, so the terrain meets the deck
without a step unless another road in the same terrain cells is lower.
Parapet pieces standing on another strip are left out. All faces have
both windings; everything goes into the `bridges` layer, which world.gd
loads with collision like every other layer.
"""
import numpy as np
import shapely

from frame import xyz
from roads import (EDGE_GAP, MAX_NODE_GRADE, MAX_SURFACE_GRADE,
                   clamped_height,
                   interpolate_structures, junction_surface, running_mean,
                   tile_keys, touches)
from structures import Strips, StructureGeometry

# lichte Hoehe: deck underside over the surface of a road below
CLEAR_MIN = 4.5
DECK_DEPTH = 1.2
# surface difference at a crossing above which it is grade-separated
GRADE_SEP = 1.0
# the clearance holds this far beyond the lower road's strip edge
CLEAR_MARGIN = 1.0
# shallow crossings stretch the plateau, but not beyond 1 / MIN_SIN
MIN_SIN = 0.25
RAMP_GRADE = 0.08
RAMP_SMOOTH = 20.0
RAISE_ROUNDS = 3
GAP_MIN = 0.5
MIN_DECK_RUN = 15.0
# cross section beside the strip: walkway, parapet
WALKWAY = 0.75
PARAPET_W = 0.3
PARAPET_H = 1.0
# the abutment line reaches this far beyond the deck edge
ABUT_MARGIN = 2.0
# the end face (abutment wall) reaches this far below the terrain
WALL_FOOT = 0.5
# steps at the abutment above this count as steps in the report
STEP_TOL = 0.05
LISTED = 10
COLORS = {"walkway": (0.56, 0.56, 0.55), "parapet": (0.74, 0.73, 0.70),
          "side": (0.64, 0.63, 0.60), "underside": (0.44, 0.44, 0.45)}


def segment_index(net):
    """First sample index of every drawn segment."""
    k = np.arange(len(net.sx) - 1)
    return k[net.edge_of[k] == net.edge_of[k + 1]]


def cross2(a, b):
    return a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]


def crossings(net):
    """Plan-view crossings of bridge segments with other edges' segments.

    Pairs whose edges share a node meet at that node and are left out.
    Returns a dict of arrays: kb, ko (segment starts of the bridge and
    the other segment), tb, to (fractions along them), xy, sin (of the
    crossing angle), hb, ho (surface heights at the crossing), sb
    (distance along the bridge edge), so (along the other edge).
    """
    k = segment_index(net)
    a = np.column_stack([net.sx[k], net.sy[k]])
    b = np.column_stack([net.sx[k + 1], net.sy[k + 1]])
    lines = shapely.linestrings(np.stack([a, b], axis=1))
    br = np.flatnonzero(net.kind[net.edge_of[k]] == "bridge")
    qi, oi = shapely.STRtree(lines).query(lines[br], predicate="intersects")
    pb, po = br[qi], oi
    eb, eo = net.edge_of[k[pb]], net.edge_of[k[po]]
    keep = (eb != eo) & (net.u[eb] != net.u[eo]) & (net.u[eb] != net.v[eo]) \
        & (net.v[eb] != net.u[eo]) & (net.v[eb] != net.v[eo])
    pb, po = pb[keep], po[keep]
    r, s = b[pb] - a[pb], b[po] - a[po]
    den = cross2(r, s)
    ok = np.abs(den) > 1e-9
    pb, po, r, s, den = pb[ok], po[ok], r[ok], s[ok], den[ok]
    qp = a[po] - a[pb]
    tb = np.clip(cross2(qp, s) / den, 0.0, 1.0)
    to = np.clip(cross2(qp, r) / den, 0.0, 1.0)
    kb, ko = k[pb], k[po]

    def along(arr, kk, t):
        return arr[kk] + (arr[kk + 1] - arr[kk]) * t

    return {"kb": kb, "ko": ko, "tb": tb, "to": to,
            "xy": a[pb] + r * tb[:, None],
            "sin": np.abs(den) / np.maximum(
                np.hypot(*r.T) * np.hypot(*s.T), 1e-12),
            "hb": along(net.surface, kb, tb), "ho": along(net.surface, ko, to),
            "sb": along(net.dist, kb, tb), "so": along(net.dist, ko, to)}


def needs(net, c):
    """Grade-separated crossings with the bridge on top: the surface the
    bridge needs there and the half length of the plateau."""
    upper = c["hb"] - c["ho"] >= GRADE_SEP
    need = c["ho"] + CLEAR_MIN + DECK_DEPTH
    half = (net.half[c["ko"]] + CLEAR_MARGIN) \
        / np.maximum(c["sin"], MIN_SIN)
    return upper, need, half


def chain_bound(bound, u, v, span, grade, op):
    """Propagate node bounds along edges u-v: bound[v] = op(bound[v],
    bound[u] -/+ grade * span) and back, until nothing changes."""
    step = grade * span if op is np.minimum.at else -grade * span
    for _ in range(len(u) + 1):
        old = bound.copy()
        op(bound, v, bound[u] + step)
        op(bound, u, bound[v] + step)
        if np.array_equal(old, bound):
            break
    return bound


def raise_decks(net):
    """Lift bridge decks over the roads they cross, dip the roads below
    where the deck cannot go high enough; returns stats.

    Nodes inside a bridge chain may rise, but not above what
    MAX_NODE_GRADE allows from the fixed (abutment) nodes, the same limit
    roads.smooth_heights uses.
    """
    bridge = net.kind == "bridge"
    first, last = net.start[:-1], net.start[1:] - 1
    n = len(net.ids)
    free = touches(n, net.u, net.v, bridge) \
        & ~touches(n, net.u, net.v, ~bridge)
    drawn = net.dist[last] - net.dist[first]
    span = np.maximum(net.length - net.cut_u - net.cut_v, 1.0)
    # highest surface a free node may take, from the fixed nodes
    chain = net.node_struct & ~net.node_portal
    ub = np.where(chain, np.inf, net.height + net.lift)
    st = net.struct
    ub = chain_bound(ub, net.u[st], net.v[st], span[st], MAX_NODE_GRADE,
                     np.minimum.at)
    before_h = net.height.copy()
    before_s = net.surface.copy()
    rounds = 0
    for rounds in range(1, RAISE_ROUNDS + 1):
        c = crossings(net)
        upper, need, half = needs(net, c)
        short = upper & (c["hb"] < need - 1e-3)
        if not np.any(short):
            rounds -= 1
            break
        e = net.edge_of[c["kb"][short]]
        sb, nd, hf = c["sb"][short], need[short], half[short]
        # node lower bounds (surface), then along bridge-only chains
        lb = np.full(n, -np.inf)
        np.maximum.at(lb, net.u[e], nd - RAMP_GRADE * np.maximum(
            0.0, sb - net.dist[first[e]] - hf))
        np.maximum.at(lb, net.v[e], nd - RAMP_GRADE * np.maximum(
            0.0, net.dist[last[e]] - sb - hf))
        lb = chain_bound(lb, net.u[bridge], net.v[bridge], drawn[bridge],
                         RAMP_GRADE, np.maximum.at)
        lower = np.where(free, np.minimum(lb, ub) - net.lift, -np.inf)
        net.height, _ = interpolate_structures(
            net.height, net.u, net.v, net.length, net.struct, lower=lower)
        delta = offsets(net, e, sb, nd, hf, 1.0, net.surface)
        resample(net, delta)
    raised_s = net.surface.copy()
    # what is still missing: dip the ground road below
    c = crossings(net)
    upper, need, _ = needs(net, c)
    eo = net.edge_of[c["ko"]]
    short = upper & (c["hb"] < need - 1e-3) & ~net.struct[eo]
    if np.any(short):
        target = c["hb"][short] - DECK_DEPTH - CLEAR_MIN
        so = c["so"][short]
        kb = c["kb"][short]
        hf = (net.half[kb] + WALKWAY + PARAPET_W + CLEAR_MARGIN) \
            / np.maximum(c["sin"][short], MIN_SIN)
        dip(net, offsets(net, eo[short], so, target, hf, -1.0,
                         net.surface))
    final = crossings(net)
    upper, need, _ = needs(net, final)
    lifted = raised_s - before_s
    dipped = raised_s - net.surface
    return {"rounds": rounds,
            "nodes_raised": int(np.count_nonzero(
                net.height > before_h + 1e-6)),
            "edges_raised": int(len(np.unique(net.edge_of[
                lifted > 1e-3]))),
            "max_raise_m": round(float(lifted.max()), 2),
            "edges_dipped": int(len(np.unique(net.edge_of[
                dipped > 1e-3]))),
            "max_dip_m": round(float(dipped.max()), 2),
            "crossings": final, "upper": upper}


def offsets(net, e, s, target, half, sign, surface):
    """Per sample: how far the profile of the edges e has to move (sign
    +1 up, -1 down) to reach the surface target at distance s, holding
    it over +-half and leaving it at RAMP_GRADE; smoothed over
    RAMP_SMOOTH. Zero on every other edge."""
    env = np.full(len(net.sx), -np.inf)
    for ei, si, h, w in zip(e, s, target, half):
        sl = slice(net.start[ei], net.start[ei + 1])
        reach = np.maximum(0.0, np.abs(net.dist[sl] - si) - w
                           - RAMP_SMOOTH / 2)
        env[sl] = np.maximum(env[sl], sign * (h - surface[sl])
                             - RAMP_GRADE * reach)
    return running_mean(np.maximum(env, 0.0),
                        net.edge_of * EDGE_GAP + net.dist, RAMP_SMOOTH)


def cones(net):
    """Per sample: surface limits MAX_SURFACE_GRADE allows from both
    node heights of its edge (low, high) and the distances to them."""
    edge = net.edge_of
    first, last = net.start[:-1], net.start[1:] - 1
    s_from = net.dist - net.dist[first][edge]
    s_to = net.dist[last][edge] - net.dist
    su = (net.height + net.lift)[net.u][edge]
    sv = (net.height + net.lift)[net.v][edge]
    g = MAX_SURFACE_GRADE
    lo = np.maximum(su - g * s_from, sv - g * s_to)
    hi = np.minimum(su + g * s_from, sv + g * s_to)
    return lo, hi, s_from, s_to


def resample(net, delta):
    """Structure profiles: chords between the node heights, bridges
    raised by delta inside the cones of their node heights."""
    edge = net.edge_of
    _, hi, s_from, s_to = cones(net)
    t = s_from / np.maximum(s_from + s_to, 1e-9)
    hu, hv = net.height[net.u][edge], net.height[net.v][edge]
    linear = hu + (hv - hu) * t
    ground = np.minimum(linear + delta,
                        np.maximum(hi - net.slift, linear))
    struct = net.struct[edge]
    net.ground = np.where(struct, ground, net.ground)
    pin_ends(net)


def dip(net, delta):
    """Ground profiles lowered by delta inside the cones of their node
    heights."""
    lo, _, _, _ = cones(net)
    ground = np.maximum(net.ground - delta,
                        np.minimum(lo - net.slift, net.ground))
    net.ground = np.where(delta > 0, ground, net.ground)
    pin_ends(net)


def pin_ends(net):
    """End samples on their node heights, surface = ground + lift."""
    first, last = net.start[:-1], net.start[1:] - 1
    net.ground[first] = net.height[net.u]
    net.ground[last] = net.height[net.v]
    net.surface = net.ground + net.slift
    net.surface[first] = net.height[net.u] + net.lift[net.u]
    net.surface[last] = net.height[net.v] + net.lift[net.v]


class BridgeLayout:
    """Classified bridge segments and abutment lines.

    k: first sample of every bridge segment, deck: its class (True =
    deck, False = low). Abutments, one row per deck run end: sample
    index i, unit direction into the deck, ground grade into the deck
    and away from it (the next segment outside, the same grade if there
    is none) and the half length of the abutment line. stats: for
    metrics.
    """

    def __init__(self):
        self.k = np.zeros(0, dtype=int)
        self.deck = np.zeros(0, dtype=bool)
        self.abut_i = np.zeros(0, dtype=int)
        self.abut_dir = np.zeros((0, 2))
        self.abut_grade = np.zeros(0)
        self.abut_grade_out = np.zeros(0)
        self.abut_half = np.zeros(0)
        self.stats = {}

    def lines(self, net, base):
        """Abutment lines for conform.pin_lines (absolute heights)."""
        i = self.abut_i
        return (np.column_stack([net.sx[i], net.sy[i]]), self.abut_dir,
                self.abut_half, net.ground[i] + base, self.abut_grade,
                self.abut_grade_out)

    @property
    def deck_k(self):
        return self.k[self.deck]

    @property
    def low_k(self):
        return self.k[~self.deck]


def deck_half(net, s):
    """Half width of the deck body at samples s (strip, walkway, parapet)."""
    return net.half[s] + WALKWAY + PARAPET_W


def normals(net, s):
    return np.column_stack([-net.tangent[s, 1], net.tangent[s, 0]])


def end_flags(net, k, deck):
    """Per edge end (u, v): its end segment is a deck segment."""
    m = len(net.edges)
    out = np.zeros((m, 2), dtype=bool)
    e = net.edge_of[k]
    first = np.r_[True, e[1:] != e[:-1]]
    last = np.r_[e[1:] != e[:-1], True]
    out[e[first], 0] = deck[first]
    out[e[last], 1] = deck[last]
    return out


def continues(net, end_deck):
    """Per edge end: the deck goes on past the node (every other edge
    end there is a deck end too, and there is at least one)."""
    n = len(net.ids)
    ends = np.concatenate([net.u, net.v])
    flag = np.concatenate([end_deck[:, 0], end_deck[:, 1]])
    count = np.bincount(ends, minlength=n)
    decks = np.bincount(ends, flag, minlength=n)
    others = decks[ends] - flag
    out = (count[ends] >= 2) & (others == count[ends] - 1)
    return out.reshape(2, -1).T


def runs(net, k, deck, cont):
    """Deck runs within an edge: (first, last) positions in k, and
    whether each end is an abutment."""
    out = []
    e = net.edge_of[k]
    i = 0
    while i < len(k):
        if not deck[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(k) and deck[j + 1] and e[j + 1] == e[i]:
            j += 1
        at_u = i == 0 or e[i - 1] != e[i]
        at_v = j == len(k) - 1 or e[j + 1] != e[j]
        out.append((i, j, not (at_u and cont[e[i], 0]),
                    not (at_v and cont[e[j], 1])))
        i = j + 1
    return out


def grade_to(net, here, there):
    """Ground grade from sample here towards sample there, and the unit
    plan direction."""
    d = np.array([net.sx[there] - net.sx[here],
                  net.sy[there] - net.sy[here]])
    ln = max(float(np.hypot(*d)), 1e-9)
    return (net.ground[there] - net.ground[here]) / ln, d / ln


def outside(net, here, inner):
    """The sample next to here on the side away from inner: the other
    neighbour on the same edge, else across a degree-2 node the first
    sample of the other edge; -1 if there is none."""
    e = net.edge_of[here]
    first, last = net.start[e], net.start[e + 1] - 1
    if first < here < last:
        return 2 * here - inner
    node = net.u[e] if here == first else net.v[e]
    if net.degree[node] != 2:
        return -1
    o = np.flatnonzero(((net.u == node) | (net.v == node))
                       & (np.arange(len(net.edges)) != e))
    if len(o) != 1:
        return -1
    o = o[0]
    return net.start[o] + 1 if net.u[o] == node else net.start[o + 1] - 2


def classify(net, dem, base, r):
    """Deck or low per bridge segment, deck runs and abutment lines."""
    lay = BridgeLayout()
    k = segment_index(net)
    k = k[net.kind[net.edge_of[k]] == "bridge"]
    if not len(k):
        lay.stats = {"edges": 0}
        return lay
    s = np.unique(np.concatenate([k, k + 1]))
    p = np.column_stack([net.sx[s], net.sy[s]])
    off = deck_half(net, s)[:, None] * normals(net, s)
    dgm = np.maximum.reduce([clamped_height(dem, q[:, 0], q[:, 1], r) - base
                             for q in (p, p + off, p - off)])
    gap = net.surface[s] - DECK_DEPTH - dgm
    pos = np.searchsorted(s, k)
    deck = (gap[pos] >= GAP_MIN) & (gap[pos + 1] >= GAP_MIN)
    seg_len = np.hypot(net.sx[k + 1] - net.sx[k], net.sy[k + 1] - net.sy[k])
    short_runs = 0
    for _ in range(2):
        cont = continues(net, end_flags(net, k, deck))
        for i, j, abut_a, abut_b in runs(net, k, deck, cont):
            if abut_a and abut_b and seg_len[i:j + 1].sum() < MIN_DECK_RUN:
                deck[i:j + 1] = False
                short_runs += 1
    cont = continues(net, end_flags(net, k, deck))
    ai, ad, ag, go = [], [], [], []
    for i, j, abut_a, abut_b in runs(net, k, deck, cont):
        for here, nxt, flag in ((k[i], k[i] + 1, abut_a),
                                (k[j] + 1, k[j], abut_b)):
            if not flag:
                continue
            g_in, d = grade_to(net, here, nxt)
            out = outside(net, here, nxt)
            ai.append(here)
            ad.append(d)
            ag.append(g_in)
            go.append(-grade_to(net, here, out)[0] if out >= 0 else g_in)
    lay.k, lay.deck = k, deck
    lay.abut_i = np.array(ai, dtype=int)
    lay.abut_dir = np.array(ad).reshape(-1, 2)
    lay.abut_grade = np.array(ag)
    lay.abut_grade_out = np.array(go)
    lay.abut_half = deck_half(net, lay.abut_i) + ABUT_MARGIN
    lay.stats = {"edges": int(np.count_nonzero(net.kind == "bridge")),
                 "short_deck_runs_to_low": short_runs}
    return lay


def build_decks(net, lay, tiles, ground, base):
    """Deck bodies over the deck segments, end faces at deck run ends
    (down to WALL_FOOT below the conformed terrain, an abutment wall),
    undersides under junctions inside a deck."""
    geo = StructureGeometry()
    if not len(lay.k) or not np.any(lay.deck):
        return geo
    k = lay.deck_k
    s = np.unique(np.concatenate([k, k + 1]))
    pos = np.searchsorted(s, k)
    a, b = pos, pos + 1
    p = np.column_stack([net.sx[s], net.sy[s]])
    nrm = normals(net, s)
    hw = net.half[s]
    surf = net.surface[s]
    under = surf - DECK_DEPTH
    top = surf + PARAPET_H
    mid = (p[a] + p[b]) / 2
    strips = Strips(net)
    own = net.edge_of[k]
    dropped = 0

    def at(d, h, idx):
        q = p[idx] + d[idx, None] * nrm[idx]
        return xyz(q[:, 0], h[idx], q[:, 1])

    for sign in (1.0, -1.0):
        edge_d = sign * hw
        inner_d = sign * (hw + WALKWAY)
        outer_d = sign * (hw + WALKWAY + PARAPET_W)
        # parapet pieces standing on another strip are left out
        foot = [p[i] + inner_d[i, None] * nrm[i] for i in (a, b)]
        hit = strips.inside(foot[0], surf[a], own) \
            | strips.inside(foot[1], surf[b], own) \
            | strips.inside((foot[0] + foot[1]) / 2,
                            (surf[a] + surf[b]) / 2, own)
        dropped += int(np.count_nonzero(hit))
        ka, kb = a[~hit], b[~hit]
        xy = mid[~hit]
        for d0, h0, d1, h1, color in (
                (edge_d, surf, inner_d, surf, "walkway"),
                (inner_d, surf, inner_d, top, "parapet"),
                (inner_d, top, outer_d, top, "parapet"),
                (outer_d, top, outer_d, under, "side")):
            geo.add(tiles, xy, (at(d0, h0, ka), at(d0, h0, kb),
                                at(d1, h1, kb), at(d1, h1, ka)),
                    COLORS[color])
    full = hw + WALKWAY + PARAPET_W
    geo.add(tiles, mid, (at(full, under, a), at(full, under, b),
                         at(-full, under, b), at(-full, under, a)),
            COLORS["underside"])
    # end faces: from below the terrain up to the road surface across
    # the deck, up to the parapet top only under the parapets
    ends = np.searchsorted(s, lay.abut_i)
    if len(ends):
        foot = under.copy()
        for side in (-1.0, 0.0, 1.0):
            q = p[ends] + (side * full[ends])[:, None] * nrm[ends]
            foot[ends] = np.minimum(foot[ends], ground.height(
                q[:, 0], q[:, 1]) - base - WALL_FOOT)
        geo.add(tiles, p[ends], (at(full, foot, ends),
                                 at(-full, foot, ends),
                                 at(-full, surf, ends),
                                 at(full, surf, ends)), COLORS["side"])
        inner = hw + WALKWAY
        for sign in (1.0, -1.0):
            mid_d = sign * (inner + full)[ends] / 2
            q = p[ends] + mid_d[:, None] * nrm[ends]
            ok = ends[~strips.inside(q, surf[ends],
                                     net.edge_of[s[ends]])]
            dropped += len(ends) - len(ok)
            geo.add(tiles, p[ok], (at(sign * inner, surf, ok),
                                   at(sign * full, surf, ok),
                                   at(sign * full, top, ok),
                                   at(sign * inner, top, ok)),
                    COLORS["parapet"])
    faces = junction_undersides(net, lay, tiles, geo)
    seg_len = np.hypot(*(p[b] - p[a]).T)
    inside = tile_keys(tiles, mid[:, 0], mid[:, 1]) >= 0
    geo.stats = {"parapet_pieces_dropped": dropped,
                 "end_faces": len(ends),
                 "junction_undersides": faces,
                 "deck_km_in_area": round(float(seg_len[inside].sum())
                                          / 1000, 3)}
    return geo


def junction_undersides(net, lay, tiles, geo):
    """The junction surface DECK_DEPTH lower at nodes where every edge
    end is a deck end (a junction on the deck)."""
    end_deck = end_flags(net, lay.k, lay.deck)
    cont = continues(net, end_deck)
    first, last = net.start[:-1], net.start[1:] - 1
    rims = {}
    for col, ends, smp in ((0, net.u, first), (1, net.v, last)):
        for e in np.flatnonzero(end_deck[:, col] & cont[:, col]):
            node = int(ends[e])
            if net.junction[node]:
                rims.setdefault(node, []).extend(
                    [net.left[smp[e]], net.right[smp[e]]])
    count = 0
    for node, rim in rims.items():
        surf = junction_surface(net.xy[node], np.array(rim),
                                net.height[node] + net.lift[node]
                                - DECK_DEPTH)
        if surf is None:
            continue
        verts, faces, _ = surf
        xy = np.array([[net.xy[node, 0], net.xy[node, 1]]])
        key = tile_keys(tiles, xy[:, 0], xy[:, 1])[0]
        if key < 0:
            continue
        for f in (faces, faces[:, ::-1]):
            geo.pieces.append((int(key), verts, f, COLORS["underside"]))
        count += 1
    return count


def bridge_report(net, lay, raised, ground, base, half):
    """The `bridges` block of metrics.json (not gated)."""
    out = {"edges": lay.stats.get("edges", 0)}
    if not len(lay.k):
        return out
    k = lay.k
    seg_len = np.hypot(net.sx[k + 1] - net.sx[k], net.sy[k + 1] - net.sy[k])
    hx, hy = np.broadcast_to(half, 2)
    inside = (np.abs(net.sx[k]) <= hx) & (np.abs(net.sy[k]) <= hy)
    out["segments"] = {
        "deck": int(np.count_nonzero(lay.deck & inside)),
        "low": int(np.count_nonzero(~lay.deck & inside))}
    out["deck_km"] = round(float(seg_len[lay.deck & inside].sum()) / 1000,
                           3)
    out["low_km"] = round(float(seg_len[~lay.deck & inside].sum()) / 1000,
                          3)
    out["short_deck_runs_to_low"] = lay.stats["short_deck_runs_to_low"]
    out["abutments"] = abutment_steps(net, lay, ground, base, half)
    out["crossings"] = clearance(net, raised)
    out["raise"] = {key: raised[key] for key in
                    ("rounds", "nodes_raised", "edges_raised",
                     "max_raise_m", "edges_dipped", "max_dip_m")}
    out["params"] = {"clear_min_m": CLEAR_MIN, "deck_depth_m": DECK_DEPTH,
                     "gap_min_m": GAP_MIN, "grade_sep_m": GRADE_SEP,
                     "ramp_grade": RAMP_GRADE,
                     "min_deck_run_m": MIN_DECK_RUN,
                     "step_tol_m": STEP_TOL}
    return out


def held(net, lay, ground, base):
    """Per abutment: the push-down pass left all its pinned corners on
    their plane (else a road strip in the same terrain cells lies lower:
    a road below, a parallel carriageway or a kink of its own road)."""
    from conform import line_corners
    rr, cc, li, _ = line_corners(ground.h.shape, ground.half, ground.step,
                                 lay.lines(net, base))
    moved = ground.h[rr, cc] < ground.pin[rr, cc] - 1e-4
    out = np.ones(len(lay.abut_i), dtype=bool)
    out[li[moved]] = False
    return out


def step_stats(a):
    return {"n": int(len(a)),
            "p50_m": round(float(np.median(a)), 3) if len(a) else None,
            "p95_m": round(float(np.percentile(a, 95)), 3)
            if len(a) else None,
            "max_m": round(float(a.max()), 3) if len(a) else None,
            "over_tol": int(np.count_nonzero(a > STEP_TOL))}


def abutment_steps(net, lay, ground, base, half):
    """Deck ground - conformed terrain along every abutment line (21
    points across the deck plus ABUT_MARGIN), inside the playable area,
    for all abutments and split by held()."""
    if not len(lay.abut_i):
        return {"n": 0}
    i = lay.abut_i
    p = np.column_stack([net.sx[i], net.sy[i]])
    nrm = normals(net, i)
    w = np.linspace(-1.0, 1.0, 21)
    q = p[:, None] + (lay.abut_half[:, None, None] * w[None, :, None]) \
        * nrm[:, None]
    q = q.reshape(-1, 2)
    step = np.repeat(net.ground[i], len(w)) \
        - (ground.height(q[:, 0], q[:, 1]) - base)
    hx, hy = np.broadcast_to(half, 2)
    ok = (np.abs(q[:, 0]) <= hx) & (np.abs(q[:, 1]) <= hy)
    step = step.reshape(len(i), -1)
    ok = ok.reshape(len(i), -1).all(axis=1)
    worst = np.abs(step).max(axis=1)
    kept = held(net, lay, ground, base)
    out = {"n": int(np.count_nonzero(ok))}
    if not np.any(ok):
        return out
    out.update({key: step_stats(worst[ok & sel]) for key, sel in (
        ("all", np.ones(len(i), dtype=bool)), ("held", kept),
        ("pushed", ~kept))})
    order = np.flatnonzero(ok)[np.argsort(-worst[ok])][:LISTED]
    out["worst"] = [{"way": int(net.edges[net.edge_of[i[j]]]["way"]),
                     "name": net.edges[net.edge_of[i[j]]]["tags"].get(
                         "name", ""),
                     "x": round(float(p[j, 0]), 1),
                     "y": round(float(p[j, 1]), 1),
                     "step_m": round(float(worst[j]), 3),
                     "held": bool(kept[j])}
                    for j in order if worst[j] > STEP_TOL]
    return out


def clearance(net, raised):
    """Deck underside - surface of the road below at every grade-
    separated crossing with the bridge on top."""
    c, upper = raised["crossings"], raised["upper"]
    clear = c["hb"][upper] - DECK_DEPTH - c["ho"][upper]
    out = {"pairs": int(len(upper)),
           "grade_separated_bridge_on_top": int(np.count_nonzero(upper)),
           "at_grade_or_below": int(np.count_nonzero(~upper))}
    if not len(clear):
        return out
    kb, ko, xy = c["kb"][upper], c["ko"][upper], c["xy"][upper]
    out.update({"min_clearance_m": round(float(clear.min()), 2),
                "p50_clearance_m": round(float(np.median(clear)), 2),
                "below_clear_min": int(np.count_nonzero(
                    clear < CLEAR_MIN - 0.01))})
    lowest = []
    for j in np.argsort(clear)[:LISTED]:
        eb, eo = net.edges[net.edge_of[kb[j]]], net.edges[net.edge_of[ko[j]]]
        lowest.append({"bridge_way": int(eb["way"]),
                       "bridge": eb["tags"].get("name", ""),
                       "below_way": int(eo["way"]),
                       "below": eo["tags"].get("name", ""),
                       "below_class": eo["tags"]["highway"],
                       "x": round(float(xy[j, 0]), 1),
                       "y": round(float(xy[j, 1]), 1),
                       "clearance_m": round(float(clear[j]), 2)})
    out["lowest"] = lowest
    return out
# - revised 2026-10-23 (rectangular playable area)
