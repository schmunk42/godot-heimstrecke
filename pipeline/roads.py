# file generated with AI assistance: Claude Code - 2026-10-20 20:45:15 UTC
"""Road network: drivable OSM ways as a graph with one height per node.

Graph nodes are OSM nodes shared by two or more drivable ways (or used
twice by one way) plus every way end; edges are the way pieces between
them. Every node gets one height (median of DGM1 within 3 m), every edge
a smoothed DGM1 profile that meets both node heights exactly, and every
node of degree >= 3 a flat junction surface that shares its vertices
with the cut-back strip ends. Ways are clipped to the DGM1 box; clip
points become `boundary` nodes with negative synthetic ids.

DGM1 is bare earth: walls, cuttings, portals and abutments are steps in
it, and a 3 m median next to one is a step in the road. So node heights
are smoothed (smooth_heights): portal and abutment nodes take the DGM1
profile of their ground edges, then the graph is relaxed to a grade
limit with every ground node within MAX_NODE_DEV of its median, and the
drawn profile of every ground edge is slope-limited too.
"""
import itertools
import math

import numpy as np
import shapely

from frame import xyz

ROAD_STEP = 5.0
# the terrain is conformed to the road ground (conform.py), so the lift
# only keeps the strip above it
ROAD_LIFT = 0.1
SMOOTH_WINDOW = 50.0
# an edge profile is blended onto the node heights over this distance
END_BLEND = 25.0
# and its class lift onto the node lift over this one
LIFT_BLEND = 15.0
# where the width changes at a degree-2 node (lane count), both edges
# blend from the mean half width at the node to their own over this
TAPER = 30.0
NODE_RADIUS = 3.0
# only these structure kinds get chord heights and are left out of the
# terrain conform; building passages, culverts and covered ways are ground
STRUCTURES = ("bridge", "tunnel")
# node chords are relaxed to this grade, drawn ground profiles to the
# second one (metrics.py gates the drawn surface at 25 %)
MAX_NODE_GRADE = 0.22
MAX_SURFACE_GRADE = 0.24
# a ground node may leave its DGM1 median by this much
MAX_NODE_DEV = 2.0
# ground-side DGM1 fit window next to a portal or abutment, m from node
PORTAL_FIT = (2.0, 15.0)
RELAX_ITERS = 5000
RELAX_TOL = 1e-4
# degree-2 nodes share one strip tangent if the turn is below 45 degrees
SHARED_TANGENT_COS = 0.7071
RANK_LIFT = 0.03
# key gap between edges in the global sort key (longer than any edge)
EDGE_GAP = 1.0e6

ROAD_WIDTH = {
    "motorway": 11.0, "trunk": 9.0, "primary": 8.0, "secondary": 7.0,
    "tertiary": 6.5, "unclassified": 5.5, "residential": 5.5,
    "living_street": 4.5, "service": 3.5, "track": 3.0,
}
# draw order offset so overlapping strips do not z-fight
ROAD_RANK = {k: i for i, k in enumerate(
    ["service", "living_street", "residential", "unclassified",
     "tertiary", "secondary", "primary", "trunk", "motorway"])}
# highway=track (only in worlds whose recipe lists `tracks`) takes the
# lowest rank like service, so no rank of the other classes moves
ROAD_RANK["track"] = 0
MAJOR = ("motorway", "trunk", "primary")
# a track is drawn as gravel unless its surface is one of these; without
# a surface tag grade1 counts as paved (OSM: solid, usually asphalt)
PAVED = ("asphalt", "concrete", "concrete:plates", "paved",
         "paving_stones", "sett", "chipseal")
# junction cut-back (cut_back): room for a sidewalk (sidewalks.WIDTH +
# KERB, not imported: sidewalks imports this module), the classes that
# get one by default (sidewalks.DEFAULT), the cap, arms counted as in
# line above this angle, and how far along an arm its heading is read
SIDE_RESERVE = 1.92
WALK_CLASSES = ("residential", "unclassified", "tertiary", "secondary",
                "primary")
CUT_MAX = 8.0
EXTRA_RISE = 0.3
IN_LINE = math.radians(150.0)
ARM_PROBE_M = 8.0
NO_ACCESS = ("private", "no")
EXCLUDE_KEYS = ("motor_vehicle", "vehicle", "access")


def road_width(tags):
    try:
        return float(tags["width"])
    except (KeyError, ValueError):
        pass
    cls = tags["highway"].removesuffix("_link")
    base = ROAD_WIDTH.get(cls, 5.0)
    if tags["highway"].endswith("_link"):
        return 5.0
    try:
        lanes = int(tags["lanes"])
        oneway = tags.get("oneway") == "yes" or cls == "motorway"
        return max(base if not oneway else 0, lanes * 3.4)
    except (KeyError, ValueError):
        return base


def road_class(tags):
    return tags["highway"].removesuffix("_link")


def is_gravel(tags):
    """A track drawn as gravel (see PAVED)."""
    if tags["highway"] != "track":
        return False
    default = "asphalt" if tags.get("tracktype") == "grade1" else "gravel"
    return tags.get("surface", default) not in PAVED


def structure_kind(tags):
    """bridge, tunnel, building_passage, culvert, covered or None."""
    if tags.get("bridge", "no") != "no":
        return "bridge"
    tunnel = tags.get("tunnel", "no")
    if tunnel in ("building_passage", "culvert"):
        return tunnel
    if tunnel != "no":
        return "tunnel"
    if tags.get("covered", "no") != "no":
        return "covered"
    return None


def exclusion(tags):
    """Why a way is not drivable for cars, or None.

    The most specific tag decides (motor_vehicle, then vehicle, then
    access), so access=private with motor_vehicle=destination stays.
    Tracks are kept whatever they say: a recipe lists them to be driven,
    and most forest tracks are motor_vehicle=forestry or no.
    """
    if tags["highway"] == "track":
        return None
    for key in EXCLUDE_KEYS:
        if key in tags:
            if tags[key] in NO_ACCESS:
                return f"{key}={tags[key]}"
            return None
    return None


def clip_segment(p, q, r):
    """Liang-Barsky: parameter range of segment p-q inside |x| <= rx,
    |y| <= ry (r a scalar or the pair rx, ry)."""
    rx, ry = np.broadcast_to(r, 2)
    t0, t1 = 0.0, 1.0
    d = q - p
    for pk, qk in ((-d[0], p[0] + rx), (d[0], rx - p[0]),
                   (-d[1], p[1] + ry), (d[1], ry - p[1])):
        if pk == 0:
            if qk < 0:
                return None
            continue
        t = qk / pk
        if pk < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    return t0, t1


def clip_way(coords, nodes, r, synth):
    """Pieces of a way inside the box, node ids aligned with vertices.

    Vertices created by the clip get ids from `synth` (negative).
    """
    if np.all(np.abs(coords) <= r):
        return [(coords, list(nodes))]
    pieces, pts, ids = [], [], []

    def close():
        if len(pts) >= 2:
            pieces.append((np.array(pts), list(ids)))
        pts.clear()
        ids.clear()

    for k in range(len(coords) - 1):
        p, q = coords[k], coords[k + 1]
        span = clip_segment(p, q, r)
        if span is None:
            close()
            continue
        t0, t1 = span
        if t0 > 0:
            close()
            pts.append(p + (q - p) * t0)
            ids.append(next(synth))
        elif not pts:
            pts.append(p)
            ids.append(nodes[k])
        if t1 < 1:
            pts.append(p + (q - p) * t1)
            ids.append(next(synth))
            close()
        else:
            pts.append(q)
            ids.append(nodes[k + 1])
    close()
    return [(c, i) for c, i in pieces if polyline_length(c) > 1e-3]


def polyline_length(c):
    return float(np.sum(np.hypot(*np.diff(c, axis=0).T)))


def drivable_pieces(ex, frame, r):
    """Clipped drivable way pieces and the excluded-way counters."""
    excluded = {}
    pieces = []
    synth = itertools.count(-1, -1)
    for road in ex["roads"]:
        tags = road["tags"]
        reason = exclusion(tags)
        if reason is not None:
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        line = frame.geom_to_local(shapely.from_wkb(road["geom"]))
        coords = shapely.get_coordinates(line)
        for c, ids in clip_way(coords, road["nodes"], r, synth):
            pieces.append((road["id"], tags, c, ids))
    return pieces, excluded


def split_edges(pieces):
    """Graph nodes and the edges between consecutive graph nodes."""
    all_ids = np.concatenate([np.asarray(p[3], dtype=np.int64)
                              for p in pieces])
    uniq, counts = np.unique(all_ids, return_counts=True)
    shared = set(uniq[counts >= 2].tolist())
    node_index, node_xy, boundary = {}, [], []

    def node(nid, xy):
        k = node_index.get(nid)
        if k is None:
            k = node_index[nid] = len(node_xy)
            node_xy.append(xy)
            boundary.append(nid < 0)
        return k

    edges = []
    for way, tags, coords, ids in pieces:
        cut = [k for k, nid in enumerate(ids)
               if k == 0 or k == len(ids) - 1 or nid in shared]
        for a, b in zip(cut, cut[1:]):
            edges.append({
                "way": way, "tags": tags, "coords": coords[a:b + 1],
                "u": node(ids[a], coords[a]), "v": node(ids[b], coords[b])})
    ids = np.array(sorted(node_index, key=node_index.get), dtype=np.int64)
    return ids, np.array(node_xy), np.array(boundary), edges


def clamped_height(dem, x, y, r):
    """DGM1 height with coordinates clamped into the DGM1 box (r a scalar
    or the pair rx, ry)."""
    rx, ry = np.broadcast_to(r, 2)
    return dem.height(np.clip(x, -rx, rx), np.clip(y, -ry, ry))


def node_heights(dem, base, xy, r):
    """Median of DGM1 on a 1 m grid within NODE_RADIUS of every node."""
    k = int(NODE_RADIUS)
    dx, dy = np.meshgrid(np.arange(-k, k + 1), np.arange(-k, k + 1))
    keep = dx ** 2 + dy ** 2 <= NODE_RADIUS ** 2
    dx, dy = dx[keep].astype(float), dy[keep].astype(float)
    xs = (xy[:, 0:1] + dx).ravel()
    ys = (xy[:, 1:2] + dy).ravel()
    h = clamped_height(dem, xs, ys, r).reshape(len(xy), -1)
    return np.median(h, axis=1) - base


def interpolate_structures(height, u, v, length, struct, iters=5000,
                           lower=None):
    """Nodes inside bridge/tunnel chains: interpolate along the chain.

    A node whose incident edges are all bridges or tunnels would
    otherwise take the DGM1 height of the valley or hill under it. Its
    height becomes the length-weighted mean of its neighbours (harmonic,
    which is linear by distance along a chain), fixed nodes keep theirs.
    lower: optional per-node lower bound for the interpolated nodes
    (bridges.py lifts decks over crossing roads with it).
    """
    n = len(height)
    plain = np.zeros(n, dtype=bool)
    plain[u[~struct]] = True
    plain[v[~struct]] = True
    free = ~plain
    sel = struct & (free[u] | free[v])
    if not sel.any():
        return height, 0
    su, sv = u[sel], v[sel]
    w = 1.0 / np.maximum(length[sel], 1.0)
    den = np.bincount(su, w, n) + np.bincount(sv, w, n)
    free &= den > 0
    h = height.copy()
    for _ in range(iters):
        num = np.bincount(su, w * h[sv], n) + np.bincount(sv, w * h[su], n)
        new = np.where(free, num / np.maximum(den, 1e-12), h)
        if lower is not None:
            new = np.where(free, np.maximum(new, lower), new)
        done = np.max(np.abs(new - h)) < 1e-5
        h = new
        if done:
            break
    return h, int(np.count_nonzero(free))


def touches(n, u, v, sel):
    """Per node: is it an end of at least one selected edge."""
    out = np.zeros(n, dtype=bool)
    out[u[sel]] = True
    out[v[sel]] = True
    return out


def edge_offsets(coords):
    return np.concatenate([[0.0], np.cumsum(
        np.hypot(*np.diff(coords, axis=0).T))])


def portal_heights(net, dem, base, r, height, mixed):
    """Heights of portal/abutment nodes from their ground edges' DGM1.

    The 3 m median at such a node mixes the road with the embankment,
    the valley or the hill over the portal. A line fitted to DGM1 along
    each ground edge (PORTAL_FIT metres from the node, grade clipped to
    MAX_NODE_GRADE) is extrapolated to the node; the node takes the
    median over its ground edges, so the step lands on the structure.
    """
    est = {int(k): [] for k in np.flatnonzero(mixed)}
    plain = ~net.struct
    lo, hi = PORTAL_FIT
    for i in np.flatnonzero(plain & (mixed[net.u] | mixed[net.v])):
        c = net.edges[i]["coords"]
        cum = edge_offsets(c)
        length = cum[-1]
        if length >= lo + 2.0:
            s = np.arange(lo, min(hi, length) + 1e-9, 1.0)
        else:
            s = np.array([length / 2, length])
        for node, back in ((net.u[i], False), (net.v[i], True)):
            if not mixed[node]:
                continue
            pos = length - s if back else s
            h = clamped_height(dem, np.interp(pos, cum, c[:, 0]),
                               np.interp(pos, cum, c[:, 1]), r) - base
            sm, hm = s.mean(), h.mean()
            b = np.sum((s - sm) * (h - hm)) / np.sum((s - sm) ** 2)
            b = np.clip(b, -MAX_NODE_GRADE, MAX_NODE_GRADE)
            est[int(node)].append(hm - b * sm)
    out = height.copy()
    for k, v in est.items():
        out[k] = np.median(v)
    return out


def relax_heights(h, lo, hi, u, v, span, grade):
    """Project heights onto |h[u] - h[v]| <= grade * span within [lo, hi].

    Jacobi steps: every violating edge pulls both ends together by half
    its excess, a node moves by the mean of its pulls and is clamped to
    its bounds. Edges within the limit are left alone, so real hills
    below it keep their shape. Returns the heights, the iterations and
    the excess left on edges the bounds do not allow to fix.
    """
    n = len(h)
    lim = grade * span
    for it in range(1, RELAX_ITERS + 1):
        d = h[v] - h[u]
        excess = np.abs(d) - lim
        bad = excess > RELAX_TOL
        if not bad.any():
            break
        pull = np.where(bad, np.sign(d) * excess / 2, 0.0)
        count = np.bincount(u, bad, n) + np.bincount(v, bad, n)
        move = np.bincount(u, pull, n) - np.bincount(v, pull, n)
        h = np.clip(h + move / np.maximum(count, 1), lo, hi)
    excess = np.maximum(np.abs(h[v] - h[u]) - lim, 0.0)
    return h, it, excess


def smooth_heights(net, dem, base, r, height):
    """Slope-limited node heights; records the node classes on net.

    `structure` nodes touch a bridge/tunnel edge: chain nodes are free
    (interpolated again afterwards), portal/abutment nodes start from
    portal_heights and may move MAX_NODE_DEV from there. `ground` nodes
    may move MAX_NODE_DEV from their 3 m median. The limit is on node
    surface heights (ground + lift) over the drawn edge length, which is
    what the strips show.
    """
    n = len(height)
    net.node_struct = touches(n, net.u, net.v, net.struct)
    mixed = net.node_struct & touches(n, net.u, net.v, ~net.struct)
    net.node_portal = mixed
    centre = portal_heights(net, dem, base, r, height, mixed)
    chain = net.node_struct & ~mixed
    lo = np.where(chain, -np.inf, centre - MAX_NODE_DEV)
    hi = np.where(chain, np.inf, centre + MAX_NODE_DEV)
    span = np.maximum(net.length - net.cut_u - net.cut_v, 1.0)
    h, iters, excess = relax_heights(centre + net.lift, lo + net.lift,
                                     hi + net.lift, net.u, net.v, span,
                                     MAX_NODE_GRADE)
    net.relax = {"iterations": int(iters),
                 "edges_over_limit": int(np.count_nonzero(
                     excess > RELAX_TOL)),
                 "max_excess_m": float(excess.max()) if len(excess)
                 else 0.0,
                 "portal_nodes": int(np.count_nonzero(mixed))}
    return h - net.lift


def slope_limit(values, start, dist, grade):
    """Per-edge profiles clamped to |dv/ds| <= grade, symmetric in s.

    Mean of the largest grade-limited function below the profile and the
    smallest one above it (1-D distance transforms: one forward and one
    backward pass each, vectorised over edges by sample position).
    Profiles already within the limit come back unchanged.
    """
    low, up = values.copy(), values.copy()
    first = start[:-1]
    count = np.diff(start)
    top = int(count.max()) if len(count) else 0
    for k in range(1, top):
        i = first[count > k] + k
        step = grade * (dist[i] - dist[i - 1])
        low[i] = np.minimum(low[i], low[i - 1] + step)
        up[i] = np.maximum(up[i], up[i - 1] - step)
    for k in range(top - 2, -1, -1):
        i = first[count > k + 1] + k
        step = grade * (dist[i + 1] - dist[i])
        low[i] = np.minimum(low[i], low[i + 1] + step)
        up[i] = np.maximum(up[i], up[i + 1] - step)
    return (low + up) / 2


def running_mean(values, key, window):
    """Mean of values within +-window/2 of each key (sorted keys)."""
    lo = np.searchsorted(key, key - window / 2, side="left")
    hi = np.searchsorted(key, key + window / 2, side="right")
    cs = np.concatenate([[0.0], np.cumsum(values)])
    return (cs[hi] - cs[lo]) / (hi - lo)


def end_weights(s, e, span):
    """Linear blend weights from the start and end over span metres."""
    span = np.maximum(span, 1e-9)
    return np.maximum(0.0, 1 - s / span), np.maximum(0.0, 1 - e / span)


class RoadNetwork:
    """Drivable road graph with sampled profiles; see build_road_network.

    Nodes: ids, xy, boundary, degree, height (smoothed ground above
    base), height_raw (DGM1 3 m median), node_struct (touches a bridge or
    tunnel edge, else a ground node), node_portal (touches both kinds),
    lift, node_rank, junction. Edges (arrays of length m plus the `edges`
    list with way, tags, coords): u, v, length, width, kind
    (structure_kind), struct (bridge/tunnel), rank, cut_u, cut_v. relax:
    smoothing statistics. Samples, concatenated over edges as
    start[i]:start[i + 1]: edge_of, sx, sy, dist, raw (DGM1), ground,
    slift, surface, tangent, half (half width in m), left, right.
    emit_network adds junctions and the expected_* record.
    """


def build_road_network(ex, frame, dem, base, r):
    """Graph, node heights and edge profiles for roads inside |x|,|y|<=r
    (a scalar or the pair rx, ry)."""
    net = RoadNetwork()
    pieces, net.excluded = drivable_pieces(ex, frame, r)
    net.ids, net.xy, net.boundary, net.edges = split_edges(pieces)
    del pieces
    edges = net.edges
    net.u = np.array([e["u"] for e in edges])
    net.v = np.array([e["v"] for e in edges])
    net.length = np.array([polyline_length(e["coords"]) for e in edges])
    net.width = np.array([road_width(e["tags"]) for e in edges])
    net.kind = np.array([structure_kind(e["tags"]) for e in edges],
                        dtype=object)
    net.struct = np.isin(net.kind, STRUCTURES)
    net.rank = np.array([ROAD_RANK.get(road_class(e["tags"]), 0)
                         for e in edges])
    net.track = np.array([e["tags"]["highway"] == "track" for e in edges],
                         dtype=bool)
    net.gravel = np.array([is_gravel(e["tags"]) for e in edges], dtype=bool)
    n = len(net.ids)
    net.degree = (np.bincount(net.u, minlength=n)
                  + np.bincount(net.v, minlength=n))
    net.height_raw = node_heights(dem, base, net.xy, r)
    height, _ = interpolate_structures(
        net.height_raw, net.u, net.v, net.length, net.struct)
    net.node_rank = np.zeros(n, dtype=int)
    np.maximum.at(net.node_rank, net.u, net.rank)
    np.maximum.at(net.node_rank, net.v, net.rank)
    # a junction is gravel only where every arm is
    net.node_gravel = np.ones(n, dtype=bool)
    np.logical_and.at(net.node_gravel, net.u, net.gravel)
    np.logical_and.at(net.node_gravel, net.v, net.gravel)
    net.lift = ROAD_LIFT + RANK_LIFT * net.node_rank
    # the smoothing limits grades over the drawn length, so cut back first
    cut_back(net)
    height = smooth_heights(net, dem, base, r, height)
    net.height, net.structure_nodes = interpolate_structures(
        height, net.u, net.v, net.length, net.struct)
    sample_edges(net, dem, base, r)
    taper_half(net)
    tangents(net)
    nrm = np.column_stack([-net.tangent[:, 1], net.tangent[:, 0]])
    half = net.half[:, None]
    p = np.column_stack([net.sx, net.sy])
    net.left, net.right = p + nrm * half, p - nrm * half
    return net


def may_walk(tags):
    """The way may get a sidewalk (a tag, or a class with the default
    of sidewalks.DEFAULT): its junction ends keep room for one."""
    return any(k.startswith("sidewalk") for k in tags) \
        or (road_class(tags) in WALK_CLASSES
            and not tags["highway"].endswith("_link"))


def arm_heading(net, e, at_u):
    """Direction (radians) of edge e away from its end node, from the
    point ARM_PROBE_M along it."""
    c = net.edges[e]["coords"]
    c = c if at_u else c[::-1]
    seg = np.hypot(*np.diff(c, axis=0).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    d = min(ARM_PROBE_M, cum[-1])
    q = np.array([np.interp(d, cum, c[:, 0]), np.interp(d, cum, c[:, 1])])
    v = q - c[0]
    return math.atan2(v[1], v[0])


def cut_back(net):
    """Distance each edge end is cut back for the junction surface.

    At least the largest half width at the node, and as far as the
    arm's carriageway and sidewalk clear the carriageway and sidewalk of
    each neighbouring arm (SIDE_RESERVE on a way that may get one): with
    the angle t between the arms, (half_b + side_b + (half_a + side_a)
    cos t) / sin t, capped at CUT_MAX and a third of the edge. Arms
    nearly in line (t above IN_LINE) do not count. On a slope the part
    beyond the half width is limited to EXTRA_RISE over the edge's mean
    grade: the junction surface is flat at the node height, so a long
    cut on a slope made the drawn end climb a kink (dip findings at
    acute junctions on hills). Then every sidewalk
    starts where the neighbour's sidewalk ends and the corner between
    them (sidewalks.junction_corners) is a clean piece; with the half
    width alone a sidewalk on the acute side of an 80 degree crossing
    started inside the other road and was left out, and two sidewalks
    overlapping at a right angle made the corner polygon cross itself."""
    radius = np.zeros(len(net.ids))
    np.maximum.at(radius, net.u, net.width / 2)
    np.maximum.at(radius, net.v, net.width / 2)
    net.junction = net.degree >= 3
    side = np.array([SIDE_RESERVE if may_walk(e["tags"]) else 0.0
                     for e in net.edges])
    half = net.width / 2
    need = [np.zeros(len(net.edges)), np.zeros(len(net.edges))]
    grade = np.abs(net.height_raw[net.u] - net.height_raw[net.v]) \
        / np.maximum(net.length, 1.0)
    extra = EXTRA_RISE / np.maximum(grade, 1e-3)
    arms = {}
    for e in range(len(net.edges)):
        for end, node in ((0, net.u[e]), (1, net.v[e])):
            if net.junction[node] and net.u[e] != net.v[e]:
                arms.setdefault(int(node), []).append(
                    (arm_heading(net, e, end == 0), e, end))
    for ring in arms.values():
        ring.sort()
        n = len(ring)
        for i, (ang, e, end) in enumerate(ring):
            want = 0.0
            for j in (i - 1, (i + 1) % n):
                b_ang, b, _ = ring[j]
                t = abs((b_ang - ang + math.pi) % (2 * math.pi) - math.pi)
                if t < 1e-3 or t > IN_LINE:
                    continue
                want = max(want, (half[b] + side[b] + (half[e] + side[e])
                                  * max(math.cos(t), 0.0)) / math.sin(t))
            node = net.u[e] if end == 0 else net.v[e]
            want = min(want, radius[node] + extra[e], CUT_MAX)
            need[end][e] = max(need[end][e], want)
    net.too_short = 0
    cuts = []
    for end, ends in enumerate((net.u, net.v)):
        want = np.where(net.junction[ends],
                        np.maximum(radius[ends], need[end]), 0.0)
        cuts.append(np.minimum(want, net.length / 3))
        net.too_short += int(np.count_nonzero(want > net.length / 3))
    net.cut_u, net.cut_v = cuts


def sample_edges(net, dem, base, r):
    """5 m samples per edge: positions, ground profile, lift, surface.

    Ground edges follow a running mean of DGM1 blended onto the node
    heights; a wall or cutting in the middle of an edge would still
    show, so their surface (ground + lift) is then slope-limited to
    MAX_SURFACE_GRADE and kept inside the cone the limit allows from both
    node heights. Bridges and tunnels are a straight chord.
    """
    a, b = net.cut_u, net.length - net.cut_v
    drawn = b - a
    count = np.maximum(2, np.ceil(drawn / ROAD_STEP).astype(int) + 1)
    start = np.concatenate([[0], np.cumsum(count)])
    edge = np.repeat(np.arange(len(count)), count)
    t = (np.arange(start[-1]) - start[edge]) / (count[edge] - 1)
    dist = a[edge] + drawn[edge] * t
    x = np.empty_like(dist)
    y = np.empty_like(dist)
    for i, e in enumerate(net.edges):
        c = e["coords"]
        cum = edge_offsets(c)
        s = slice(start[i], start[i + 1])
        x[s] = np.interp(dist[s], cum, c[:, 0])
        y[s] = np.interp(dist[s], cum, c[:, 1])
    raw = clamped_height(dem, x, y, r) - base
    smooth = running_mean(raw, edge * EDGE_GAP + dist, SMOOTH_WINDOW)
    first, last = start[:-1], start[1:] - 1
    s_from, s_to = dist - a[edge], b[edge] - dist
    hu, hv = net.height[net.u], net.height[net.v]
    w0, w1 = end_weights(s_from, s_to,
                         np.minimum(END_BLEND, drawn[edge] / 2))
    ground = (smooth + (hu - smooth[first])[edge] * w0
              + (hv - smooth[last])[edge] * w1)
    own = ROAD_LIFT + RANK_LIFT * net.rank
    lu, lv = net.lift[net.u], net.lift[net.v]
    w0, w1 = end_weights(s_from, s_to,
                         np.minimum(LIFT_BLEND, drawn[edge] / 2))
    lift = own[edge] + (lu - own)[edge] * w0 + (lv - own)[edge] * w1
    lift[first], lift[last] = lu, lv
    su, sv = hu + lu, hv + lv
    surf = slope_limit(ground + lift, start, dist, MAX_SURFACE_GRADE)
    g = MAX_SURFACE_GRADE
    cone_lo = np.maximum(su[edge] - g * s_from, sv[edge] - g * s_to)
    cone_hi = np.minimum(su[edge] + g * s_from, sv[edge] + g * s_to)
    ground = np.minimum(np.maximum(surf, cone_lo), cone_hi) - lift
    linear = hu[edge] + (hv - hu)[edge] * t
    ground = np.where(net.struct[edge], linear, ground)
    ground[first], ground[last] = hu, hv
    surface = ground + lift
    surface[first], surface[last] = hu + lu, hv + lv
    net.start, net.edge_of, net.dist = start, edge, dist
    net.sx, net.sy = x, y
    net.raw, net.ground, net.slift, net.surface = raw, ground, lift, surface


def taper_half(net):
    """net.half: the edge half width, blended at degree-2 nodes whose two
    edges differ in width from the mean of both over TAPER (at most half
    the drawn length) onto each edge's own."""
    own = net.width / 2
    uv = np.stack([net.u, net.v])
    both = np.bincount(uv.ravel(), weights=np.tile(own, 2),
                       minlength=len(net.ids))[uv]
    # half-width difference to the other edge at each end (u, v)
    step = np.abs(2 * own - both)
    taper = (net.degree[uv] == 2) & (step > 1e-6)
    delta = np.where(taper, both / 2 - own, 0.0)
    edge, a = net.edge_of, net.cut_u
    drawn = net.length - net.cut_v - a
    s_from = net.dist - a[edge]
    w0, w1 = end_weights(s_from, drawn[edge] - s_from,
                         np.minimum(TAPER, drawn[edge] / 2))
    half = own[edge] + delta[0][edge] * w0 + delta[1][edge] * w1
    first, last = net.start[:-1], net.start[1:] - 1
    half[first], half[last] = own + delta[0], own + delta[1]
    net.half = half
    net.taper_nodes = len(np.unique(uv[taper]))
    net.taper_max_step_m = round(float(step[taper].max(initial=0.0)), 2)
    net.relax["taper_nodes"] = net.taper_nodes
    net.relax["taper_max_step_m"] = net.taper_max_step_m


def unit(v):
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12)


def tangents(net):
    """Sample tangents; gentle degree-2 nodes share one end tangent."""
    p = np.column_stack([net.sx, net.sy])
    first, last = net.start[:-1], net.start[1:] - 1
    idx = np.arange(len(p))
    nxt, prv = np.minimum(idx + 1, len(p) - 1), np.maximum(idx - 1, 0)
    nxt[last], prv[first] = last, first
    tangent = unit(p[nxt] - p[prv])
    # the away-from-node direction of every edge end, and its sample
    ends = np.concatenate([net.u, net.v])
    sample = np.concatenate([first, last])
    away = np.concatenate([tangent[first], -tangent[last]])
    order = np.argsort(ends, kind="stable")
    pair = order[net.degree[ends[order]] == 2].reshape(-1, 2)
    through = away[pair[:, 1]] - away[pair[:, 0]]
    # only gentle turns: a shared tangent at a sharp corner folds strips
    turn = -np.sum(away[pair[:, 0]] * away[pair[:, 1]], axis=1)
    ok = turn > SHARED_TANGENT_COS
    pair, through = pair[ok], unit(through[ok])
    for col in (0, 1):
        s = sample[pair[:, col]]
        sign = np.where(np.sum(tangent[s] * through, axis=1) < 0, -1, 1)
        tangent[s] = through * sign[:, None]
    net.tangent = tangent


def convex_hull(pts):
    """Monotone chain hull, counter-clockwise, as indices into pts."""
    order = sorted(range(len(pts)), key=lambda i: (pts[i][0], pts[i][1]))

    def cross(o, a, b):
        return ((pts[a][0] - pts[o][0]) * (pts[b][1] - pts[o][1])
                - (pts[a][1] - pts[o][1]) * (pts[b][0] - pts[o][0]))

    hull = []
    for seq in (order, order[::-1]):
        part = []
        for i in seq:
            while len(part) >= 2 and cross(part[-2], part[-1], i) <= 0:
                part.pop()
            part.append(i)
        hull += part[:-1]
    return hull


def junction_surface(centre, rim, height):
    """Flat fan from the node centre over the hull of the rim points.

    The centre takes part in the hull, so a fork whose strips all leave
    to one side still gets a valid convex fan. Returns glTF vertices,
    counter-clockwise faces (normal up) and the hull ring in map
    coordinates (counter-clockwise, for skirts.py), or None if nothing
    is left.
    """
    pts = np.vstack([centre[None, :], rim])
    hull = convex_hull(pts.tolist())
    if 0 in hull:
        k = hull.index(0)
        ring = hull[k + 1:] + hull[:k]
        tris = [(0, ring[i], ring[i + 1]) for i in range(len(ring) - 1)]
    else:
        ring = hull
        tris = [(0, ring[i], ring[(i + 1) % len(ring)])
                for i in range(len(ring))]
    faces = []
    for a, b, c in tris:
        ab, ac = pts[b] - pts[a], pts[c] - pts[a]
        if ab[0] * ac[1] - ab[1] * ac[0] > 1e-6:
            faces.append((a, b, c))
    if not faces:
        return None
    used = sorted({i for f in faces for i in f})
    remap = {k: i for i, k in enumerate(used)}
    sel = pts[used]
    verts = xyz(sel[:, 0], np.full(len(sel), height), sel[:, 1])
    return (verts, np.array([[remap[i] for i in f] for f in faces]),
            pts[hull])


def tile_keys(tiles, x, y):
    """Tiles.keys per point, -1 outside."""
    return tiles.keys(x, y)


def add_ribbon(tiles, verts, faces, owner, color, layer="roads"):
    """Split a strip into tiles by segment owner (shared seam vertices).

    Faces 2k and 2k + 1 belong to segment k.
    """
    for key in np.unique(owner):
        if key < 0:
            continue
        seg = np.flatnonzero(owner == key)
        sub_faces = faces[np.concatenate([2 * seg, 2 * seg + 1])]
        used = np.unique(sub_faces)
        remap = -np.ones(len(verts), dtype=int)
        remap[used] = np.arange(len(used))
        bucket = tiles.bucket(key)[layer]
        bucket.add(verts[used], remap[sub_faces], color)


def rank_color(rank, colors, gravel=False):
    """colors = (minor, major, gravel)."""
    if gravel:
        return colors[2]
    major = min(ROAD_RANK[c] for c in MAJOR)
    return colors[1] if rank >= major else colors[0]


def ribbon(a, b, h_a, h_b):
    """Vertices (line a then line b) and faces of one ribbon between two
    lines of map points; faces 2k and 2k + 1 belong to segment k
    (add_ribbon). Counter-clockwise from above when b lies right of a."""
    cnt = len(a)
    verts = np.vstack([xyz(a[:, 0], h_a, a[:, 1]),
                       xyz(b[:, 0], h_b, b[:, 1])])
    k = np.arange(cnt - 1)
    faces = np.empty((2 * (cnt - 1), 3), dtype=int)
    faces[0::2] = np.column_stack([k, cnt + k, k + 1])
    faces[1::2] = np.column_stack([k + 1, cnt + k, cnt + k + 1])
    return verts, faces


def orient(verts, faces, want):
    """Flip faces whose normal points away from want (one glTF vector,
    or one per face)."""
    a, b, c = (verts[faces[:, i]] for i in range(3))
    away = np.sum(np.cross(b - a, c - a) * np.asarray(want), axis=1) < 0
    faces = faces.copy()
    faces[away] = faces[away][:, ::-1]
    return faces


def strip_mesh(left, right, height):
    """Vertices (left then right) and faces of one flat strip."""
    return ribbon(left, right, height, height)


def emit_network(tiles, net, colors):
    """Strips and junction surfaces into the tiles' `roads` buckets.

    colors = (minor, major, gravel). Records on `net` what metrics.py checks in
    the export: per node of degree >= 2 inside the tiles, the XZ of every
    emitted strip end vertex and junction vertex (expected_node,
    expected_xz) and the expected height per node (expected_height).
    """
    seg_owner = tile_keys(tiles, (net.sx[:-1] + net.sx[1:]) / 2,
                          (net.sy[:-1] + net.sy[1:]) / 2)
    exp_node, exp_xy = [], []
    for i in range(len(net.edges)):
        s0, s1 = net.start[i], net.start[i + 1]
        verts, faces = strip_mesh(net.left[s0:s1], net.right[s0:s1],
                                  net.surface[s0:s1])
        owner = seg_owner[s0:s1 - 1]
        add_ribbon(tiles, verts, faces, owner,
                   rank_color(net.rank[i], colors, net.gravel[i]))
        for node, smp, seg in ((net.u[i], s0, owner[0]),
                               (net.v[i], s1 - 1, owner[-1])):
            if net.degree[node] >= 2 and seg >= 0:
                exp_node += [node, node]
                exp_xy += [net.left[smp], net.right[smp]]
    net.junctions = emit_junctions(tiles, net, colors, exp_node, exp_xy)
    exp_node = np.array(exp_node, dtype=int)
    exp_xy = np.array(exp_xy).reshape(-1, 2)
    inside = tile_keys(tiles, net.xy[:, 0], net.xy[:, 1]) >= 0
    keep = inside[exp_node]
    net.expected_node = exp_node[keep]
    net.expected_xz = np.column_stack([exp_xy[keep, 0], -exp_xy[keep, 1]])
    net.expected_height = net.height + net.lift
    net.inside = inside


def emit_junctions(tiles, net, colors, exp_node, exp_xy):
    """Junction surfaces at every node of degree >= 3 inside the tiles.

    Keeps (node, hull ring, height) of every surface in net.junction_rings.
    """
    rims = {int(k): [] for k in np.flatnonzero(net.junction)}
    first, last = net.start[:-1], net.start[1:] - 1
    for ends, smp in ((net.u, first), (net.v, last)):
        for node, s in zip(ends.tolist(), smp.tolist()):
            if node in rims:
                rims[node] += [net.left[s], net.right[s]]
    keys = tile_keys(tiles, net.xy[:, 0], net.xy[:, 1])
    net.junction_rings = []
    for node, rim in rims.items():
        if keys[node] < 0:
            continue
        surf = junction_surface(net.xy[node], np.array(rim),
                                net.height[node] + net.lift[node])
        if surf is None:
            continue
        verts, faces, ring = surf
        net.junction_rings.append(
            (node, ring, net.height[node] + net.lift[node]))
        bucket = tiles.bucket(keys[node])["roads"]
        bucket.add(verts, faces, rank_color(net.node_rank[node], colors,
                                            net.node_gravel[node]))
        exp_node += [node] * len(verts)
        exp_xy += list(np.column_stack([verts[:, 0], -verts[:, 2]]))
    return len(net.junction_rings)
# - revised 2026-10-22 (tiles own their key lookup)
# - revised 2026-10-23 (rectangular clip box)
# - revised 2026-10-25 (cut-back clears the neighbouring arms at skew junctions)
# - revised 2026-10-25 (highway=track as gravel roads, recipe `tracks`)
