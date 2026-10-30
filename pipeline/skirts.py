# file generated with AI assistance: Claude Code - 2026-10-22 10:30:00 UTC
"""Skirts at the road edges, down into the conformed terrain.

Roads are drawn ROAD_LIFT (plus the class lift) above the road ground,
and the conform pass lowers single terrain triangles under bends and
grade changes, so a strip edge hangs 0.2 m above the terrain on the
median and more than 1 m at about one edge point in seventy. A skirt
closes that gap, so the road edge reads as a shoulder instead of a
floating sheet: from every edge sample of a ground strip (or the outer
edge of its sidewalk at its top, sidewalks.py) and every hull edge of a
junction surface or sidewalk corner, it runs outward and down at ANGLE
below the horizontal until it is SINK below the terrain there, so the
terrain covers its lower edge. Nothing rises above the edge: the former
bank (a band 1 m out and 0.25 m up in front of the skirt) read as a
raised kerb on open land. A skirt runs out at most MAX_RUN, so a deep
one (a ramp beside a lower road, where the terrain follows the lower
road) steepens into a retaining wall instead of reaching over the road
below.

The road has priority (priority.py): a skirt segment lying on another
carriageway or junction surface yields from SKIRT_YIELD m2 or
SKIRT_YIELD_FRAC of its area. Between two carriageways closer than
2 MAX_RUN (a narrow median) the skirt of each side reaches at most half
the free gap and steepens there, so two skirts do not cross in it.
Skirts go into the `verges` layer with the sidewalks and collide, in a
light stone colour: the former dark grey read as a shadow, stone reads
as a kerb. Bridges and tunnels get none, nor do junctions at their
ends: a bridge spans open air and a tunnel road has walls (bridges.py,
tunnels.py).
"""
import numpy as np
import shapely

from priority import NO_EDGE, road_area
from roads import add_ribbon, orient, ribbon, tile_keys
from sidewalks import KERB, LAYER, WIDTH, corner_height, side_lines

# slope of the skirt below the horizontal
ANGLE = np.radians(20.0)
# the lower edge ends this far below the terrain
SINK = 0.1
# a skirt is at least MIN_DEPTH and at most MAX_DEPTH deep and reaches
# out at most MAX_RUN from the edge
MIN_DEPTH = 0.15
MAX_DEPTH = 20.0
MAX_RUN = 3.0
# a skirt segment yields from SKIRT_YIELD m2 or SKIRT_YIELD_FRAC of its
# area lying on another road
SKIRT_YIELD = 0.1
SKIRT_YIELD_FRAC = 0.05
# a skirt with less run than this left in a median is left out
MIN_SKIRT_RUN = 0.05
# edge points listed in the report where even MAX_DEPTH is not enough
WORST_LISTED = 10


def skirt_depth(edge, out, surface, ground, base, max_run=MAX_RUN):
    """Depth below the surface, from the terrain at the edge and beyond.

    Two passes: the terrain at the edge gives a first width, the terrain
    at that width can be lower (the edge sits on a slope).
    """
    def need(p):
        return surface - (ground.height(p[:, 0], p[:, 1]) - base) + SINK

    depth = need(edge)
    run = skirt_run(np.clip(depth, MIN_DEPTH, MAX_DEPTH), max_run)
    depth = np.maximum(depth, need(edge + out * run[:, None]))
    return np.clip(depth, MIN_DEPTH, MAX_DEPTH)


def skirt_run(depth, max_run=MAX_RUN):
    """Outward reach of a skirt of this depth (max_run m or per point)."""
    return np.minimum(depth / np.tan(ANGLE), max_run)


def skirt_mesh(top, out, surface, depth, max_run=MAX_RUN):
    """One ribbon from the top line outward and down, faces normal up,
    and its bottom line.

    Faces 2k and 2k + 1 belong to segment k (add_ribbon).
    """
    bottom = top + out * skirt_run(depth, max_run)[:, None]
    verts, faces = ribbon(top, bottom, surface, surface - depth)
    return verts, orient(verts, faces, [0, 1, 0]), bottom


def seg_rings(a, b):
    """Closed plan ring (segments, 5, 2) of every segment of the ribbon
    between lines a and b (for one shapely.polygons call)."""
    return np.stack([a[:-1], a[1:], b[1:], b[:-1], a[:-1]], axis=1)


def seg_points(seg):
    """Samples touched by the segments selected in seg."""
    used = np.zeros(len(seg) + 1, dtype=bool)
    used[:-1] |= seg
    used[1:] |= seg
    return used


def run_limit(gap):
    """Skirt run limit per sample from the free gap to the next road on
    that side (inf: no limit)."""
    return np.clip(gap / 2, 0.0, MAX_RUN)


def edge_key(a, b):
    """Order-free key of a line between two map points, to the mm."""
    return tuple(sorted((tuple(np.round(a, 3)), tuple(np.round(b, 3)))))


def corner_edges(net):
    """Keys of the junction hull edges a sidewalk corner covers."""
    return {edge_key(*c["polygon"][:2]) for c in net.corners}


def strip_lines(tiles, net):
    """One record per side of every ground strip inside the tiles.

    edge: the edge (its own strip does not count as another road),
    owner: tile per segment (-1 not drawn), out: outward normal per
    sample, walk: per segment 1 where the sidewalk is drawn, lines: the
    start line and its height without (0) and with (1) the sidewalk.
    """
    seg_owner = tile_keys(tiles, (net.sx[:-1] + net.sx[1:]) / 2,
                          (net.sy[:-1] + net.sy[1:]) / 2)
    recs = []
    for i in np.flatnonzero(~net.struct):
        s0, s1 = net.start[i], net.start[i + 1]
        owner = seg_owner[s0:s1 - 1]
        if np.all(owner < 0):
            continue
        surface = net.surface[s0:s1]
        for side, (edge, out) in enumerate(side_lines(net, s0, s1)):
            walk = net.walk_keep[s0:s1 - 1, side].astype(int)
            recs.append({"edge": int(i), "owner": owner, "out": out,
                         "walk": walk,
                         "lines": [(edge, surface),
                                   (edge + out * WIDTH, surface + KERB)]})
    return recs


def hull_lines(tiles, net):
    """Records like strip_lines for the junction hulls and sidewalk
    corners; a hull edge under a sidewalk corner is not drawn."""
    covered = corner_edges(net)
    lines = [(node, np.vstack([ring, ring[:1]]), height, True)
             for node, ring, height in net.junction_rings
             if not net.node_struct[node]]
    lines += [(c["node"], c["outer"],
               corner_height(net, c["node"]) + KERB, False)
              for c in net.corners]
    recs = []
    for node, top, height, hull in lines:
        key = tile_keys(tiles, net.xy[node, 0], net.xy[node, 1])
        if key < 0:
            continue
        out = top - net.xy[node]
        out /= np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)
        owner = np.full(len(top) - 1, int(key))
        if hull:
            owner[[edge_key(top[k], top[k + 1]) in covered
                   for k in range(len(top) - 1)]] = -1
        recs.append({"edge": NO_EDGE, "node": int(node), "owner": owner,
                     "out": out,
                     "walk": np.zeros(len(top) - 1, dtype=int),
                     "lines": [(top, np.full(len(top), height))]})
    return recs


def free_gaps(area, recs):
    """Per strip record and sample the free gap outward (2 MAX_RUN at
    most) to the nearest other road, from the start line."""
    mids, dirs, own, count = [], [], [], []
    for r in recs:
        w = r["walk"][:, None] > 0
        (e0, _), (e1, _) = r["lines"]
        a = np.where(w, e1[:-1], e0[:-1])
        b = np.where(w, e1[1:], e0[1:])
        d = r["out"][:-1] + r["out"][1:]
        mids.append((a + b) / 2)
        dirs.append(d / np.maximum(np.linalg.norm(d, axis=1,
                                                  keepdims=True), 1e-9))
        own.append(np.full(len(a), r["edge"]))
        count.append(len(a))
    if not recs:
        return
    gap = area.gap(np.vstack(mids), np.vstack(dirs), np.concatenate(own),
                   2 * MAX_RUN)
    for r, g in zip(recs, np.split(gap, np.cumsum(count)[:-1])):
        r["gap"] = np.minimum(np.r_[g[:1], g], np.r_[g, g[-1:]])


def plan_skirts(tiles, net, ground, base):
    """Where skirts go, after the road priority.

    Returns the line records (strip_lines, hull_lines) with per sample
    `limit`, the skirt variants (dicts: rec, drawn segments, verts,
    faces, depth, top and bottom line) and the number of skirt segments
    that yielded.
    """
    area = road_area(net)
    strips = strip_lines(tiles, net)
    free_gaps(area, strips)
    recs = strips + hull_lines(tiles, net)
    # skirts: per start variant (bare edge, sidewalk) from its start line
    variants = []
    for r in recs:
        r["limit"] = run_limit(r.get("gap", np.full(len(r["out"]), np.inf)))
        room = (r["limit"][:-1] >= MIN_SKIRT_RUN) \
            | (r["limit"][1:] >= MIN_SKIRT_RUN)
        for w in np.unique(r["walk"]):
            line, surface = r["lines"][w]
            sel = (r["walk"] == w) & room & (r["owner"] >= 0)
            if sel.any():
                variants.append({"rec": r, "drawn": sel,
                                 "used": seg_points(sel), "top": line,
                                 "height": surface})
    # the depth is per point: one terrain lookup for all variants
    pick = [(v["top"][v["used"]], v["rec"]["out"][v["used"]],
             v["height"][v["used"]], v["rec"]["limit"][v["used"]])
            for v in variants]
    depth = []
    if pick:
        top, out, height, limit = (np.concatenate(c) for c in zip(*pick))
        depth = np.split(skirt_depth(top, out, height, ground, base, limit),
                         np.cumsum([len(p[0]) for p in pick])[:-1])
    quads, own = [], []
    for v, d in zip(variants, depth):
        r = v["rec"]
        v["depth"] = np.zeros(len(v["top"]))
        v["depth"][v["used"]] = d
        v["verts"], v["faces"], v["bottom"] = skirt_mesh(
            v["top"], r["out"], v["height"], v["depth"], r["limit"])
        quads.append(seg_rings(v["top"], v["bottom"])[v["drawn"]])
        own.append(np.full(len(quads[-1]), r["edge"]))
    skirt_ok = area.keep(shapely.polygons(np.concatenate(quads)),
                         np.concatenate(own),
                         SKIRT_YIELD, SKIRT_YIELD_FRAC) if quads \
        else np.zeros(0, dtype=bool)
    skirt_ok = np.split(skirt_ok, np.cumsum([len(q) for q in quads])[:-1])
    skirt_clipped = 0
    for v, ok in zip(variants, skirt_ok):
        v["drawn"] = v["drawn"].copy()
        v["drawn"][v["drawn"]] = ok
        skirt_clipped += int(np.count_nonzero(~ok))
    return recs, variants, skirt_clipped


def drawn_runs(seg):
    """Sample slices of the runs of consecutive True segments."""
    d = np.diff(np.r_[0, np.asarray(seg, dtype=np.int8), 0])
    return [slice(a, b + 1) for a, b in zip(np.flatnonzero(d == 1),
                                            np.flatnonzero(d == -1))]


def publish(net, kind, line, rec, seg, height=None):
    """Record the drawn runs of one line for clipping.py: plan points
    (n, 2), or (n, 3) with the height, plus the owning edge (-1 for
    hull and corner lines) and node (-1 for strip lines)."""
    for s in drawn_runs(seg):
        pts = line[s] if height is None \
            else np.column_stack([line[s], height[s]])
        getattr(net, kind).append(pts)
        getattr(net, kind + "_edge").append(max(int(rec["edge"]), -1))
        getattr(net, kind + "_node").append(int(rec.get("node", -1)))


def emit_skirts(tiles, net, ground, base, color):
    """Skirts along every ground strip edge and junction hull; on a side
    with a drawn sidewalk from the sidewalk's outer edge and top, at a
    junction corner around the corner's outer line.

    `color` is the stone colour of the skirt. Reads net.walk_keep and
    the kept net.corners (emit_sidewalks). Publishes what it drew for
    clipping.py: net.skirt_feet (the lower edge of every drawn skirt
    run, plan) with parallel `_edge` and `_node` lists. Returns stats
    for the report.
    """
    recs, variants, skirt_clipped = plan_skirts(tiles, net, ground, base)
    faces_out = steepened = limited = 0
    for suffix in ("", "_edge", "_node"):
        setattr(net, "skirt_feet" + suffix, [])
    depths, tops = [], []
    for v in variants:
        r, drawn = v["rec"], v["drawn"]
        add_ribbon(tiles, v["verts"], v["faces"],
                   np.where(drawn, r["owner"], -1), color, LAYER)
        faces_out += 2 * int(np.count_nonzero(drawn))
        publish(net, "skirt_feet", v["bottom"], r, drawn)
        used = seg_points(drawn)
        d = v["depth"][used]
        want = np.clip(d, MIN_DEPTH, MAX_DEPTH) / np.tan(ANGLE)
        limit = r["limit"][used]
        steepened += int(np.count_nonzero(want >= MAX_RUN - 1e-9))
        limited += int(np.count_nonzero((want > limit + 1e-9)
                                        & (limit < MAX_RUN - 1e-9)))
        depths.append(d)
        tops.append(v["top"][used])
    d = np.concatenate(depths) if depths else np.zeros(1)
    p = np.vstack(tops) if tops else np.zeros((1, 2))
    deep = np.flatnonzero(d >= MAX_DEPTH - 1e-9)[:WORST_LISTED]
    return {"angle_deg": float(np.degrees(ANGLE)), "sink_m": SINK,
            "min_depth_m": MIN_DEPTH, "max_depth_m": MAX_DEPTH,
            "max_run_m": MAX_RUN, "faces": int(faces_out),
            "skirt_clipped": skirt_clipped,
            "depth_p50_m": round(float(np.percentile(d, 50)), 3),
            "depth_p95_m": round(float(np.percentile(d, 95)), 3),
            "depth_max_m": round(float(d.max()), 3),
            "steepened": steepened, "median_limited": limited,
            "at_max_depth": int(np.count_nonzero(d >= MAX_DEPTH - 1e-9)),
            "worst": [{"x": round(float(p[k, 0]), 1),
                       "z": round(float(-p[k, 1]), 1)} for k in deep]}


# - revised 2026-10-22 (bank, road priority, narrow medians)
# - revised 2026-10-22 (publish skirt feet and bank tops for clipping.py)
# - revised 2026-10-22 (tiles own their key lookup)
# - revised 2026-10-25 (no bank: the skirt starts at the edge)
