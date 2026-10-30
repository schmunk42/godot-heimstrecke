# file generated with AI assistance: Claude Code - 2026-10-22 23:40:00 UTC
"""Clipping report: the places where drawn road pieces cut into each
other or into the terrain, found systematically.

The hard gates (metrics.py) prove that the road surface is continuous
at the nodes and that the terrain stays below every strip. They do not
see a link strip lying in a carriageway at the same height (z-fighting),
a ramp cutting through a road a metre below, two skirts crossing in a
narrow median, terrain poking through a sidewalk or bank, a notch where
the width changes at a degree-2 node or a pothole in a profile.
Screenshots find those one at a time; this pass finds every instance in
the geometry the emitters drew, so a change is judged by counts and the
worst places can be rendered (write_viewpoints). Kinds, severity unit:

- zfight (m2 overlap): strip segment quads of two edges sharing no
  node, or a junction hull and a strip of an edge not ending at it,
  overlap in plan within GATE_TOLERANCE of each other's height.
- overlap (OVERLAP_DH - height difference, m): the same, the two lie
  less than OVERLAP_DH apart; farther apart is a proper crossing.
- median (MEDIAN_GAP - gap, m): the free run outward from a ground
  strip side (its drawn sidewalk's outer edge if any) to a ground strip
  of an edge sharing no node is below 2 skirts.MAX_RUN, where two
  carriageways' banks and skirts must share the median.
- width_step (m): the two edges at a degree-2 node differ in half width
  at their end samples by more than WIDTH_STEP.
- terrain_above (m): the conformed terrain lies more than
  GATE_TOLERANCE above a drawn sidewalk's outer top edge or a sidewalk
  corner's outer line.
- bank_buried (m): the same above a drawn bank's outer top edge. The
  bank disappears into rising terrain beside cuttings; the strip edge
  itself is covered by the hard gate and the skirt below the bank
  steepens into the retaining-wall look, so this is a cosmetic count,
  not a clipping defect, and kept apart so terrain_above stays
  comparable with pipelines that draw no banks.
- skirt_cross (m): a drawn skirt's lower edge runs over another road
  strip or junction hull, or crosses another skirt's lower edge at more
  than 30 degrees (its length within FOOT_NEAR of it), for more than
  SKIRT_MIN; nearly parallel feet are the ridge of a narrow median, and
  the feet of two edges sharing a node cross at every junction corner
  by design (counted apart as arm_feet_crossing).
- dip (m): a ground profile lies more than DIP_DEPTH below the chord
  over DIP_WINDOW; edges passing under a bridge are left out (bridges
  .dip lowers some on purpose and leaves no marker on net, so every
  candidate of bridges.needs is excluded), as are bridges and tunnels.

Every check indexes its pieces in one shapely STRtree and filters the
candidate pairs vectorised, O(n log n). A finding is one place: one per
pair of pieces' owners (edges, hulls, skirt runs) or per run of
consecutive segments of one edge side, so a count is not a number of
5 m segments. Only places inside the playable square count.

Older pipelines lack net.half, net.walk_keep and the skirt lines
skirts.py publishes; the getattr defaults let the same checks measure
the ratchet baseline on them (worlds/<id>/clipping_baseline.json), a
kind without its geometry is reported as not measured.

The ratchet (ratchet()) allows a kind RATCHET_SLACK above its baseline
count, rounded up, while the total over the measured kinds must not
exceed the baseline total: unrelated geometry changes such as the 30 m
width taper move strips by metres and shift a few overlaps in or out of
the thresholds (+2 zfight, +4 overlap there, both about 1 %), and a
ratchet without slack would block every such commit; the total still
has to go down.
"""
import json
import math
import time

import numpy as np
import shapely
from bridges import crossings, needs
from metrics import GATE_TOLERANCE
from priority import valid
from roads import EDGE_GAP
from sidewalks import KERB, WIDTH
from skirts import MAX_RUN

KINDS = ("zfight", "overlap", "median", "width_step", "terrain_above",
         "bank_buried", "skirt_cross", "dip")
# a kind fails the ratchet above its baseline count times 1 + this,
# rounded up (geometry noise, see above); the total has no slack
RATCHET_SLACK = 0.02
# pieces closer than this in height are a proper crossing beyond it
OVERLAP_DH = 2.5
# plan overlaps below this (m2) are pieces touching at an edge
MIN_AREA = 0.01
MEDIAN_GAP = 2 * MAX_RUN
WIDTH_STEP = 0.3
# a skirt foot crossing another one at more than FOOT_COS's angle counts
# its length within FOOT_NEAR of the other; a finding from SKIRT_MIN m
# (two feet meeting end to end at a node stay below it)
FOOT_NEAR = 0.25
FOOT_COS = np.cos(np.radians(30.0))
SKIRT_MIN = 0.3
DIP_WINDOW = 40.0
DIP_DEPTH = 0.5
WORST = 5
# viewpoints: per kind, in all, camera above and behind the finding
VIEWS_PER_KIND = 3
MAX_VIEWS = 15
VIEW_UP = 25.0
VIEW_BACK = 40.0


def segments(net):
    """First sample of every segment of consecutive samples of an edge."""
    k = np.arange(len(net.sx) - 1)
    return k[net.edge_of[k] == net.edge_of[k + 1]]


def inside(p, half):
    """p (n, 2) inside +-half (a scalar or the pair hx, hy)."""
    hx, hy = np.broadcast_to(half, 2)
    return (np.abs(p[:, 0]) <= hx) & (np.abs(p[:, 1]) <= hy)


def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)


def half_width(net):
    """Half width per sample (older pipelines: per edge)."""
    half = getattr(net, "half", None)
    return (net.width / 2)[net.edge_of] if half is None else half


def walk_drawn(net):
    """(samples, 2): the sidewalk segment from each sample is drawn
    (older pipelines draw every one assigned)."""
    keep = getattr(net, "walk_keep", None)
    return net.walk[net.edge_of] if keep is None else keep


def surface_at(net, k, p):
    """Road surface on centre segment k at the point nearest to p."""
    a = np.column_stack([net.sx[k], net.sy[k]])
    ab = np.column_stack([net.sx[k + 1], net.sy[k + 1]]) - a
    t = np.einsum("ij,ij->i", p - a, ab) / np.maximum(
        np.einsum("ij,ij->i", ab, ab), 1e-12)
    t = np.clip(t, 0.0, 1.0)
    return net.surface[k] + (net.surface[k + 1] - net.surface[k]) * t


def nearest_sample(net, edge, x, y):
    s = slice(net.start[edge], net.start[edge + 1])
    return net.start[edge] + int(np.argmin(np.hypot(net.sx[s] - x,
                                                    net.sy[s] - y)))


def shares_node(net, a, b):
    """Per pair: edges a and b have a node in common."""
    return (net.u[a] == net.u[b]) | (net.u[a] == net.v[b]) \
        | (net.v[a] == net.u[b]) | (net.v[a] == net.v[b])


def ends_at(net, e, node):
    """Per pair: edge e (>= 0) ends at node; False where e < 0."""
    e0 = np.maximum(e, 0)
    return (e >= 0) & ((net.u[e0] == node) | (net.v[e0] == node))


def best(group, severity):
    """Index of the largest severity of every group."""
    if not len(group):
        return np.zeros(0, dtype=int)
    order = np.lexsort((-severity, group))
    g = group[order]
    return order[np.r_[True, g[1:] != g[:-1]]]


def run_ids(flag, group, pos):
    """Run id per flagged element: consecutive elements of one group
    whose pos steps by one (elements sorted by group, pos)."""
    if not len(flag):
        return np.zeros(0, dtype=int)
    new = np.r_[True, (group[1:] != group[:-1])
                | (pos[1:] != pos[:-1] + 1) | ~flag[:-1]]
    return np.cumsum(new)[flag]


class Pieces:
    """Every strip segment quad and junction hull in one STRtree.

    edge: edge per piece (-1 hull), node (-1 strip), k: first sample of
    the segment (-1 hull), height: hull surface, ground: not a bridge or
    tunnel piece.
    """

    def __init__(self, net):
        k = segments(net)
        quads = shapely.polygons(np.stack(
            [net.left[k], net.left[k + 1], net.right[k + 1], net.right[k],
             net.left[k]], axis=1))
        rings = [(n, r, h) for n, r, h in net.junction_rings if len(r) >= 3]
        hulls = np.array([shapely.Polygon(r) for _, r, _ in rings],
                         dtype=object)
        nodes = np.array([n for n, _, _ in rings], dtype=int)
        self.poly = valid(np.concatenate([quads, hulls]))
        self.edge = np.r_[net.edge_of[k], np.full(len(rings), -1)]
        self.node = np.r_[np.full(len(k), -1), nodes]
        self.k = np.r_[k, np.full(len(rings), -1)]
        self.height = np.r_[np.full(len(k), np.nan),
                            [h for _, _, h in rings]]
        self.ground = np.r_[~net.struct[net.edge_of[k]],
                            ~net.node_struct[nodes]]
        self.tree = shapely.STRtree(self.poly)

    def owner(self, i, n_edges):
        """One id per edge and per hull."""
        return np.where(self.edge[i] >= 0, self.edge[i],
                        n_edges + self.node[i])


class Found:
    """Findings per kind; add() takes arrays of one kind."""

    def __init__(self, net, half):
        self.net, self.half = net, half
        self.items = {kind: [] for kind in KINDS}
        self.arm_feet = None
        self.sources = {}
        # one incident edge per node, for findings owned by a node
        self.node_edge = np.full(len(net.ids), -1)
        self.node_edge[net.v] = np.arange(len(net.v))
        self.node_edge[net.u] = np.arange(len(net.u))

    def add(self, kind, severity, edge, p, h):
        keep = inside(p, self.half)
        for s, e, (x, y), hh in zip(severity[keep], edge[keep], p[keep],
                                    h[keep]):
            tags = self.net.edges[int(e)]
            self.items[kind].append({
                "kind": kind, "severity": round(float(s), 3),
                "way": int(tags["way"]),
                "name": tags["tags"].get("name", ""),
                "x": round(float(x), 1), "y": round(float(y), 1),
                "h": round(float(hh), 2)})


def overlaps(net, pc, found):
    """zfight and overlap: strip-strip and strip-hull plan overlaps."""
    pi, ti = pc.tree.query(pc.poly, predicate="intersects")
    sel = pi < ti
    pi, ti = pi[sel], ti[sel]
    # the strip first; hull-hull pairs are left out
    swap = pc.edge[pi] < 0
    pi, ti = np.where(swap, ti, pi), np.where(swap, pi, ti)
    ea, eb, nb = pc.edge[pi], pc.edge[ti], pc.node[ti]
    keep = ea >= 0
    pi, ti, ea, eb, nb = pi[keep], ti[keep], ea[keep], eb[keep], nb[keep]
    strip = eb >= 0
    other = np.where(strip, (ea != eb) & ~shares_node(net, ea,
                                                      np.maximum(eb, 0)),
                     ~ends_at(net, ea, nb))
    pi, ti, ea, strip = pi[other], ti[other], ea[other], strip[other]
    piece = shapely.intersection(pc.poly[pi], pc.poly[ti])
    area = shapely.area(piece)
    keep = area > MIN_AREA
    pi, ti, ea, strip = pi[keep], ti[keep], ea[keep], strip[keep]
    piece, area = piece[keep], area[keep]
    p = shapely.get_coordinates(shapely.point_on_surface(piece))
    ha = surface_at(net, pc.k[pi], p)
    hb = np.where(strip, surface_at(net, np.maximum(pc.k[ti], 0), p),
                  pc.height[ti])
    dh = np.abs(ha - hb)
    pair = ea * (len(net.edges) + len(net.ids)) \
        + pc.owner(ti, len(net.edges))
    for kind, sel, sev in (
            ("zfight", dh < GATE_TOLERANCE, area),
            ("overlap", (dh >= GATE_TOLERANCE) & (dh < OVERLAP_DH),
             OVERLAP_DH - dh)):
        if not sel.any():
            continue
        g, s = pair[sel], sev[sel]
        i = best(g, s)
        total = s[i]
        if kind == "zfight":
            # m2 of all pieces of the pair, placed at the largest
            _, inv = np.unique(g, return_inverse=True)
            total = np.bincount(inv, weights=s)[inv[i]]
        found.add(kind, total, ea[sel][i], p[sel][i], ha[sel][i])


def outer_lines(net, k, side):
    """Start line of the verge on one side of segments k (the drawn
    sidewalk's outer edge, else the strip edge): both ends, outward
    normal and whether a sidewalk is drawn."""
    nrm = np.column_stack([-net.tangent[:, 1], net.tangent[:, 0]])
    line, out = (net.left, nrm) if side == 0 else (net.right, -nrm)
    walk = walk_drawn(net)[k, side][:, None]
    a = line[k] + out[k] * WIDTH * walk
    b = line[k + 1] + out[k + 1] * WIDTH * walk
    return a, b, unit(out[k] + out[k + 1]), walk[:, 0]


def medians(net, pc, found, k):
    """median: free run outward from every ground strip side."""
    mids, dirs, own, pos, group = [], [], [], [], []
    for side in (0, 1):
        a, b, d, _ = outer_lines(net, k, side)
        mids.append((a + b) / 2)
        dirs.append(d)
        own.append(net.edge_of[k])
        pos.append(k)
        group.append(net.edge_of[k] * 2 + side)
    mid, d, own, pos, group = (np.concatenate(c) for c in
                               (mids, dirs, own, pos, group))
    rays = shapely.linestrings(np.stack([mid, mid + d * MEDIAN_GAP],
                                        axis=1))
    ri, ti = pc.tree.query(rays, predicate="intersects")
    te = pc.edge[ti]
    hit = (te >= 0) & pc.ground[ti] & (te != own[ri]) \
        & ~shares_node(net, own[ri], np.maximum(te, 0))
    ri, ti = ri[hit], ti[hit]
    gap = np.full(len(mid), MEDIAN_GAP)
    if len(ri):
        dist = shapely.distance(shapely.points(mid[ri]), shapely.intersection(
            rays[ri], pc.poly[ti]))
        np.minimum.at(gap, ri, np.nan_to_num(dist, nan=MEDIAN_GAP))
    order = np.lexsort((pos, group))
    gap, own, pos, group, mid = (c[order] for c in
                                 (gap, own, pos, group, mid))
    flag = (gap < MEDIAN_GAP) & inside(mid, found.half)
    ids = run_ids(flag, group, pos)
    i = np.flatnonzero(flag)[best(ids, MEDIAN_GAP - gap[flag])]
    h = (net.surface[pos[i]] + net.surface[pos[i] + 1]) / 2
    found.add("median", MEDIAN_GAP - gap[i], own[i], mid[i], h)


def width_steps(net, found):
    """width_step: half width at the two end samples at degree-2 nodes."""
    half = half_width(net)
    first, last = net.start[:-1], net.start[1:] - 1
    ends = np.r_[net.u, net.v]
    smp = np.r_[first, last]
    edge = np.r_[np.arange(len(net.u)), np.arange(len(net.v))]
    sel = np.flatnonzero(net.degree[ends] == 2)
    sel = sel[np.argsort(ends[sel], kind="stable")].reshape(-1, 2)
    step = np.abs(half[smp[sel[:, 0]]] - half[smp[sel[:, 1]]])
    bad = step > WIDTH_STEP
    sel = sel[bad]
    node = ends[sel[:, 0]]
    found.add("width_step", step[bad], np.min(edge[sel], axis=1),
              net.xy[node], net.surface[smp[sel[:, 0]]])


def excess(ground, base, half, a, b, ha, hb):
    """Terrain above the segments a-b at heights ha-hb (the largest of
    both ends and the middle, of those inside the playable square: the
    terrain mesh ends there)."""
    return np.max([np.where(inside(q, half),
                            ground.height(q[:, 0], q[:, 1]) - base - h,
                            -np.inf)
                   for q, h in ((a, ha), ((a + b) / 2, (ha + hb) / 2),
                                (b, hb))], axis=0)


def terrain_above(net, ground, base, found, k):
    """terrain_above (sidewalk outer tops, corner outer lines) and
    bank_buried (bank tops): one finding per run of segments above
    GATE_TOLERANCE."""
    rows = []   # a, b, ha, hb, edge, group, pos, road surface
    for side in (0, 1):
        a, b, _, walk = outer_lines(net, k, side)
        w = walk > 0
        kw = k[w]
        e = net.edge_of[kw]
        rows.append((a[w], b[w], net.surface[kw] + KERB,
                     net.surface[kw + 1] + KERB, e, e * 2 + side, kw,
                     (net.surface[kw] + net.surface[kw + 1]) / 2))
    # corner outer lines and bank tops: all their segments at once
    lines = [(c["outer"], np.full(len(c["outer"]), net.height[c["node"]]
                                  + net.lift[c["node"]] + KERB),
              int(c.get("edges", [-1])[0]), int(c["node"]))
             for c in net.corners]
    tops = getattr(net, "bank_tops", [])
    lines += [(t[:, :2], t[:, 2], e, n) for t, e, n in
              zip(tops, getattr(net, "bank_tops_edge", []),
                  getattr(net, "bank_tops_node", []))]
    if lines:
        pts = np.vstack([p for p, _, _, _ in lines])
        height = np.concatenate([h for _, h, _, _ in lines])
        count = [len(p) for p, _, _, _ in lines]
        j = np.repeat(np.arange(len(lines)), count)
        pos = np.arange(len(j)) - np.repeat(np.cumsum(count) - count, count)
        e = np.array([e for _, _, e, _ in lines])
        n = np.array([n for _, _, _, n in lines])
        e = np.where(e >= 0, e, found.node_edge[np.maximum(n, 0)])
        road = np.where(n >= 0, net.height[np.maximum(n, 0)]
                        + net.lift[np.maximum(n, 0)], np.nan)
        s = np.flatnonzero(j[:-1] == j[1:])
        rows.append((pts[s], pts[s + 1], height[s], height[s + 1],
                     e[j[s]], 2 * len(net.edges) + j[s], pos[s],
                     road[j[s]]))
    a, b, ha, hb, edge, group, pos, h = (np.concatenate(c)
                                         for c in zip(*rows))
    ex = excess(ground, base, found.half, a, b, ha, hb)
    mid = (a + b) / 2
    order = np.lexsort((pos, group))
    ex, edge, group, pos, mid, h = (c[order] for c in
                                    (ex, edge, group, pos, mid, h))
    flag = (ex > GATE_TOLERANCE) & inside(mid, found.half)
    ids = run_ids(flag, group, pos)
    i = np.flatnonzero(flag)[best(ids, ex[flag])]
    # groups: sidewalk sides, then corners, then bank tops
    corners = 2 * len(net.edges) + len(net.corners)
    found.sources["terrain_above"] = {
        "sidewalk": int(np.count_nonzero(group[i] < 2 * len(net.edges))),
        "corner": int(np.count_nonzero((group[i] >= 2 * len(net.edges))
                                       & (group[i] < corners)))}
    # strip lines: the road surface beside; bank tops: the nearest sample
    h = h[i]
    for j in np.flatnonzero(np.isnan(h)):
        h[j] = net.surface[nearest_sample(net, edge[i][j], *mid[i][j])]
    bank = group[i] >= corners
    for kind, sel in (("terrain_above", ~bank), ("bank_buried", bank)):
        found.add(kind, ex[i][sel], edge[i][sel], mid[i][sel], h[sel])


def skirt_crossings(net, pc, found):
    """skirt_cross: skirt feet over other roads and other feet. Returns
    False when the pipeline publishes no skirt feet."""
    feet = getattr(net, "skirt_feet", None)
    if feet is None:
        return False
    keep = [i for i, f in enumerate(feet) if len(f) >= 2]
    if not keep:
        return True
    lines = np.array([shapely.LineString(feet[i]) for i in keep],
                     dtype=object)
    fe = np.asarray(net.skirt_feet_edge)[keep]
    fn = np.asarray(net.skirt_feet_node)[keep]
    owner_edge = np.where(fe >= 0, fe, found.node_edge[np.maximum(fn, 0)])
    n_edges = len(net.edges)
    # feet over strips and hulls: not their own edge, its end hulls, nor
    # (corner and hull skirts) their own hull and the edges ending there
    li, ti = pc.tree.query(lines, predicate="intersects")
    te, tn, e, n = pc.edge[ti], pc.node[ti], fe[li], fn[li]
    mine = np.where(e >= 0,
                    (te == e) | ends_at(net, e, tn) & (tn >= 0),
                    (tn == n) | ends_at(net, te, n))
    sel = pc.ground[ti] & ~mine
    li, ti = li[sel], ti[sel]
    piece = shapely.intersection(lines[li], pc.poly[ti])
    pair = li * (n_edges + len(net.ids) + 1) + pc.owner(ti, n_edges)
    rows = [(pair, shapely.length(piece), li, piece)]
    # feet crossing other feet at an angle (meeting nearly parallel is
    # the ridge of a narrow median, skirts.py)
    fi, gi = shapely.STRtree(lines).query(lines, predicate="intersects")
    ef, eg, nf, ng = fe[fi], fe[gi], fn[fi], fn[gi]
    same = ((ef >= 0) & (ef == eg)) | ((nf >= 0) & (nf == ng)) \
        | ends_at(net, ef, ng) & (ng >= 0) | ends_at(net, eg, nf) & (nf >= 0)
    sel = (fi < gi) & ~same
    fi, gi = fi[sel], gi[sel]
    at = shapely.point_on_surface(shapely.intersection(lines[fi],
                                                       lines[gi]))
    cos = np.abs(np.sum(direction(lines[fi], at)
                        * direction(lines[gi], at), axis=1))
    # two arms' feet fanning out round the same node cross by design at
    # every junction corner: counted apart, not as findings
    ef, eg = fe[fi], fe[gi]
    arms = (ef >= 0) & (eg >= 0) & shares_node(net, np.maximum(ef, 0),
                                               np.maximum(eg, 0))
    sel = (cos < FOOT_COS) & ~arms
    found.arm_feet = int(np.count_nonzero((cos < FOOT_COS) & arms))
    fi, gi = fi[sel], gi[sel]
    piece = shapely.intersection(lines[fi],
                                 shapely.buffer(lines[gi], FOOT_NEAR))
    rows.append((-1 - (fi * len(lines) + gi), shapely.length(piece), fi,
                 piece))
    pair, length, li, piece = (np.concatenate(c) for c in zip(*rows))
    _, inv = np.unique(pair, return_inverse=True)
    total = np.bincount(inv, weights=length)
    i = best(inv, length)
    i = i[total[inv[i]] > SKIRT_MIN]
    p = shapely.get_coordinates(shapely.point_on_surface(piece[i]))
    e = owner_edge[li[i]]
    h = np.array([net.surface[nearest_sample(net, ee, *pp)]
                  for ee, pp in zip(e, p)])
    found.add("skirt_cross", total[inv[i]], e, p, h.reshape(-1))
    return True


def direction(lines, at):
    """Unit direction of each line at its point nearest to at."""
    s = shapely.line_locate_point(lines, at)
    a = shapely.get_coordinates(shapely.line_interpolate_point(
        lines, np.maximum(s - 0.5, 0.0)))
    b = shapely.get_coordinates(shapely.line_interpolate_point(
        lines, s + 0.5))
    return unit(b - a)


def dips(net, found):
    """dip: ground profile below the chord over DIP_WINDOW."""
    key = net.edge_of * EDGE_GAP + net.dist
    lo = np.searchsorted(key, key - DIP_WINDOW / 2, side="left")
    hi = np.searchsorted(key, key + DIP_WINDOW / 2, side="right") - 1
    s, d = net.surface, net.dist
    t = (d - d[lo]) / np.maximum(d[hi] - d[lo], 1e-9)
    depth = s[lo] + (s[hi] - s[lo]) * t - s
    c = crossings(net)
    upper = needs(net, c)[0]
    under = np.zeros(len(net.edges), dtype=bool)
    under[net.edge_of[c["ko"][upper]]] = True
    p = np.column_stack([net.sx, net.sy])
    flag = (depth > DIP_DEPTH) & ~net.struct[net.edge_of] \
        & ~under[net.edge_of] & inside(p, found.half)
    idx = np.arange(len(s))
    ids = run_ids(flag, net.edge_of, idx)
    i = np.flatnonzero(flag)[best(ids, depth[flag])]
    found.add("dip", depth[i], net.edge_of[i], p[i], s[i])
    return int(under.sum())


def check_clipping(net, ground, base, half):
    """All clipping checks on the drawn geometry (after emit_markings);
    returns the report block without the baseline (metrics.py)."""
    t0 = time.time()
    found = Found(net, half)
    pc = Pieces(net)
    k = segments(net)
    kg = k[~net.struct[net.edge_of[k]]]
    overlaps(net, pc, found)
    medians(net, pc, found, kg)
    width_steps(net, found)
    terrain_above(net, ground, base, found, kg)
    measured = {kind: True for kind in KINDS}
    measured["skirt_cross"] = skirt_crossings(net, pc, found)
    measured["bank_buried"] = hasattr(net, "bank_tops")
    under = dips(net, found)
    items = found.items
    return {
        "seconds": round(time.time() - t0, 2),
        "counts": {kind: len(items[kind]) for kind in KINDS},
        "total": sum(len(v) for v in items.values()),
        "measured": measured,
        "sources": found.sources,
        "worst": {kind: sorted(items[kind], key=lambda f: -f["severity"])
                  [:WORST] for kind in KINDS},
        "params": {"tolerance_m": GATE_TOLERANCE,
                   "overlap_dh_m": OVERLAP_DH,
                   "median_gap_m": MEDIAN_GAP,
                   "width_step_m": WIDTH_STEP,
                   "skirt_min_m": SKIRT_MIN, "foot_near_m": FOOT_NEAR,
                   "arm_feet_crossing": found.arm_feet,
                   "dip_window_m": DIP_WINDOW, "dip_depth_m": DIP_DEPTH,
                   "dip_edges_excluded_under_bridges": under}}


def ratchet(clipping):
    """Gate PASS / FAIL / SKIPPED (no baseline for the area), the allowed
    maximum per kind with a measured baseline and both totals."""
    base = clipping.get("baseline")
    if base is None:
        return "SKIPPED", {}, None, None
    allowed = {k: math.ceil(n * (1 + RATCHET_SLACK))
               for k, n in base["counts"].items() if n is not None}
    count = sum(clipping["counts"].get(k, 0) for k in allowed)
    limit = sum(base["counts"][k] for k in allowed)
    worse = [k for k, n in allowed.items()
             if clipping["counts"].get(k, 0) > n]
    gate = "FAIL" if worse or count > limit else "PASS"
    return gate, allowed, count, limit


def write_viewpoints(path, clipping, net):
    """Camera views of the worst findings for render/render.sh
    (godot/tools/render_views.gd): VIEW_UP above and VIEW_BACK back along
    the road tangent, looking at the finding at road height."""
    p = np.column_stack([net.sx, net.sy])
    views = []
    for kind in KINDS:
        for n, f in enumerate(clipping["worst"][kind][:VIEWS_PER_KIND], 1):
            if len(views) >= MAX_VIEWS:
                break
            at = np.array([f["x"], f["y"]])
            t = net.tangent[int(np.argmin(np.hypot(*(p - at).T)))]
            cam = at - t * VIEW_BACK
            views.append({
                "name": f"{kind}-{n}",
                "position": [round(float(cam[0]), 1),
                             round(f["h"] + VIEW_UP, 1),
                             round(float(-cam[1]), 1)],
                "look_at": [f["x"], f["h"], round(-f["y"], 1)]})
    path.write_text(json.dumps({
        "_comment": "worst clipping findings per kind, written by "
                    "pipeline/clipping.py; render with RENDER_VIEWS",
        "views": views}, indent=1) + "\n")
    return len(views)
# - revised 2026-10-23 (rectangular playable area)
