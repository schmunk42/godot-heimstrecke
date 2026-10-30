# file generated with AI assistance: Claude Code - 2026-10-22 14:10:00 UTC
"""Sidewalks beside the ground roads, so the road lies pressed in.

Every side of a ground edge with a sidewalk gets a WIDTH m strip at the
road surface plus KERB, from the strip edge outward, and a vertical kerb
face facing the road, in the `verges` layer with the skirts (with
collision; apart from `roads`, whose vertices at a node must share one
height). The road then lies kerb-deep between its sidewalks. The terrain
cannot follow: it is a 10 m grid, every triangle reaching under the road
is pushed below the road ground and also covers the sidewalk, so beyond
the sidewalk it lies about 0.3 m below the sidewalk top (raising its
target there made that worse, measured 2026-10-22). The skirt
(skirts.py) runs from the sidewalk's outer edge down into it; conform.py
only keeps the terrain under the sidewalks.

The sides come from OSM: `sidewalk`, refined by `sidewalk:both`,
`sidewalk:left` and `sidewalk:right` (yes, both, left, right and
separate count as present, no and none as absent; left and right are
seen in the way's direction). A `separate` sidewalk is mapped as its own
way a few metres off; it is drawn next to the road all the same, on a
oneway carriageway only on its outer side (the driver's right), where
untagged oneways get their default sidewalk too. Untagged ways take
DEFAULT by class, but only in town: an edge counts as in town when at
least TOWN_SHARE of its samples lie in urban land cover or have
TOWN_BUILDINGS buildings within TOWN_BUILDING_M. Outside towns an
untagged road has no sidewalk (the D 268 at Bavella or the T 50 had
sidewalks in the mountains); OSM's sidewalk tags count everywhere. Bridges and tunnels get none (a bridge deck has its
own walkway, bridges.py, a tunnel its walls), nor do the ground edges
ending at a tunnel portal.

The road has priority (priority.py): a sidewalk segment or corner lying
more than YIELD_AREA m2 or YIELD_FRAC of its area on another road is
left out, so no kerb stands on a road beside a sharp fork or a narrow
median. A segment's own strip and the junction surfaces at its ends do
not count, nor a corner's two arms and its junction surface: corners
overlap those a little by their shape, which is the accepted look.
net.walk_keep and the filtered net.corners tell the skirts what was
drawn.
"""
import math

import mapbox_earcut
import numpy as np
import shapely

from frame import xyz
from priority import road_area
from roads import add_ribbon, orient, ribbon, road_class, tile_keys

# an edge is in town (default sidewalks) when this share of its samples
# lies in urban land cover or near this many buildings
TOWN_SHARE = 0.5
TOWN_BUILDINGS = 2
TOWN_BUILDING_M = 40.0
# mesh layer of sidewalks, kerbs and skirts
LAYER = "verges"
WIDTH = 1.8
KERB = 0.12
# the raised terrain ends this far below the sidewalk top
MARGIN = 0.03
# a corner reaches out to where the outer lines of its two sidewalks
# meet if that lies within this many widths of their ends, else it is cut
# off straight (sharp angles)
CORNER_REACH = 3.0
# corners smaller than this (m2) are left out, and so are corners over a
# gap between two arms wider than CORNER_MAX_GAP (the back of a fork) or
# lying more than CORNER_MAX_OVERLAP on the junction surface
CORNER_MIN_AREA = 0.2
CORNER_MAX_GAP = math.radians(200.0)
CORNER_MAX_OVERLAP = 0.25
# a segment or corner lying more than this (m2, or this fraction of its
# area) on another road yields to it
YIELD_AREA = 0.3
YIELD_FRAC = 0.1
# untagged ways: sidewalks on both sides for these classes, none else
DEFAULT = ("residential", "unclassified", "tertiary", "secondary",
           "primary")
PRESENT = ("yes", "both", "separate")
ABSENT = ("no", "none")


def sides(tags, town=True):
    """(left, right) sidewalk presence of one way; town: the default
    applies (see the module doc)."""
    # on a oneway carriageway (often one half of a dual road) a separate
    # or default sidewalk lies on the outer side only, the driver's right
    outer = {"yes": "right", "1": "right", "-1": "left"}.get(
        tags.get("oneway"))

    def outside(side):
        return outer is None or side == outer

    def present(value, side):
        return value in ("yes", "both", side) \
            or (value == "separate" and outside(side))

    default = town and road_class(tags) in DEFAULT \
        and not tags["highway"].endswith("_link")
    left, right = default and outside("left"), default and outside("right")
    value = tags.get("sidewalk")
    if value is not None:
        left, right = present(value, "left"), present(value, "right")
    both = tags.get("sidewalk:both")
    if both in PRESENT or both in ABSENT:
        left, right = present(both, "left"), present(both, "right")
    value = tags.get("sidewalk:left")
    if value in PRESENT or value in ABSENT:
        left = present(value, "left")
    value = tags.get("sidewalk:right")
    if value in PRESENT or value in ABSENT:
        right = present(value, "right")
    return left, right


def in_town(net, urban, buildings):
    """Per edge: at least TOWN_SHARE of its samples in urban land cover
    or with TOWN_BUILDINGS buildings within TOWN_BUILDING_M."""
    n = len(net.edges)
    if not len(net.sx):
        return np.zeros(n, dtype=bool)
    town = np.zeros(len(net.sx), dtype=bool)
    if urban is not None:
        town |= shapely.contains_xy(urban, net.sx, net.sy)
    if buildings:
        tree = shapely.STRtree([g for g, _ in buildings])
        pi, _ = tree.query(shapely.points(net.sx, net.sy),
                           predicate="dwithin", distance=TOWN_BUILDING_M)
        town |= np.bincount(pi, minlength=len(net.sx)) >= TOWN_BUILDINGS
    share = np.bincount(net.edge_of, weights=town, minlength=n) \
        / np.maximum(np.bincount(net.edge_of, minlength=n), 1)
    return share >= TOWN_SHARE


def assign(net, urban=None, buildings=None):
    """net.walk: (edges, 2) bool, left and right sidewalk per edge; with
    urban land cover or buildings the default holds in town only."""
    town = in_town(net, urban, buildings) \
        if urban is not None or buildings else np.ones(len(net.edges), bool)
    net.town = town
    walk = np.array([sides(e["tags"], bool(t))
                     for e, t in zip(net.edges, town)], dtype=bool)
    walk = walk.reshape(-1, 2)
    walk[net.struct] = False
    # the ramp in front of a portal runs between retaining walls; a
    # sidewalk there would make the conform pass dig into the hill
    tunnel = net.kind == "tunnel"
    portal = np.zeros(len(net.ids), dtype=bool)
    portal[net.u[tunnel]] = portal[net.v[tunnel]] = True
    walk[portal[net.u] | portal[net.v]] = False
    net.walk = walk
    net.corners = junction_corners(net)


def junction_corners(net):
    """Corner pieces between neighbouring arms of every ground junction.

    Arms are the strip ends at the node, sorted counter-clockwise by
    their direction away from it. Between an arm and the next one, if
    both have a sidewalk on the sides facing each other, the corner runs
    from the junction surface edge p-q (the facing strip end corners)
    out to the outer sidewalk ends po and qo and, where the two outer
    lines meet near them, to that point. Returns dicts with node, the
    two arm edges, the polygon (p, q, qo, [meet], po) and the outer line
    (qo, [meet], po).
    """
    first, last = net.start[:-1], net.start[1:] - 1
    arms = {}
    for e in range(len(net.edges)):
        for node, s, sign in ((net.u[e], first[e], 1.0),
                              (net.v[e], last[e], -1.0)):
            if not net.junction[node] or net.node_struct[node]:
                continue
            away = net.tangent[s] * sign
            ccw = np.array([-away[1], away[0]])
            # left of the way away from the node: the strip's left at
            # its start, its right at its end
            if sign > 0:
                left, right = net.left[s], net.right[s]
                walk_l, walk_r = net.walk[e]
            else:
                left, right = net.right[s], net.left[s]
                walk_r, walk_l = net.walk[e]
            arms.setdefault(int(node), []).append(
                (math.atan2(away[1], away[0]), away, ccw, left, walk_l,
                 right, walk_r, e))
    corners = []
    for node, ring in arms.items():
        if len(ring) < 2:
            continue
        ring.sort(key=lambda arm: arm[0])
        fan = shapely.MultiPoint(
            [net.xy[node]] + [arm[3] for arm in ring]
            + [arm[5] for arm in ring]).convex_hull
        for i, a in enumerate(ring):
            b = ring[(i + 1) % len(ring)]
            gap = (b[0] - a[0]) % (2 * math.pi)
            if not (a[4] and b[6]) or gap > CORNER_MAX_GAP:
                continue
            p, q = a[3], b[5]
            po, qo = p + a[2] * WIDTH, q - b[2] * WIDTH
            outer = [qo]
            meet = line_meet(po, a[1], qo, b[1])
            if meet is not None:
                outer.append(meet)
            outer.append(po)
            poly = shapely.Polygon([p, q] + outer)
            if not poly.is_valid or poly.area < CORNER_MIN_AREA \
                    or poly.intersection(fan).area \
                    > CORNER_MAX_OVERLAP * poly.area:
                continue
            corners.append({"node": node, "edges": (a[7], b[7]),
                            "polygon": np.array([p, q] + outer),
                            "outer": np.array(outer)})
    return corners


def line_meet(pa, da, pb, db):
    """Where the lines pa + s da and pb + t db meet, if s and t lie
    within CORNER_REACH widths; else None."""
    den = da[0] * db[1] - da[1] * db[0]
    if abs(den) < 1e-6:
        return None
    w = pb - pa
    s = (w[0] * db[1] - w[1] * db[0]) / den
    t = (w[0] * da[1] - w[1] * da[0]) / den
    reach = CORNER_REACH * WIDTH
    if abs(s) > reach or abs(t) > reach:
        return None
    return pa + da * s


def side_lines(net, s0, s1):
    """Road edge and outward normal of both sides of samples s0:s1."""
    nrm = np.column_stack([-net.tangent[s0:s1, 1], net.tangent[s0:s1, 0]])
    return ((net.left[s0:s1], nrm), (net.right[s0:s1], -nrm))


def walk_keep(net, area):
    """(samples, 2) bool: the sidewalk segment starting at each sample
    (left, right) is drawn; the last sample of an edge mirrors the one
    before it."""
    k = np.arange(len(net.sx) - 1)
    k = k[net.edge_of[k] == net.edge_of[k + 1]]
    nrm = np.column_stack([-net.tangent[:, 1], net.tangent[:, 0]])
    keep = np.zeros((len(net.sx), 2), dtype=bool)
    for side, (edge, out) in enumerate(((net.left, nrm),
                                        (net.right, -nrm))):
        sel = k[net.walk[net.edge_of[k], side]]
        outer = edge + out * WIDTH
        quads = shapely.polygons(np.stack(
            [edge[sel], edge[sel + 1], outer[sel + 1], outer[sel],
             edge[sel]], axis=1))
        e = net.edge_of[sel]
        keep[sel, side] = area.keep(quads, e, YIELD_AREA, YIELD_FRAC,
                                    np.column_stack([net.u[e], net.v[e]]))
    last = net.start[1:] - 1
    keep[last] = keep[last - 1]
    return keep


def emit_sidewalks(tiles, net, color, kerb_color):
    """Sidewalk tops and kerb faces into the `verges` layer; stats.

    Segments and corners on another road yield; sets net.walk_keep and
    replaces net.corners by the corners kept.
    """
    area = road_area(net)
    net.walk_keep = walk_keep(net, area)
    seg_owner = tile_keys(tiles, (net.sx[:-1] + net.sx[1:]) / 2,
                          (net.sy[:-1] + net.sy[1:]) / 2)
    length, clipped = 0.0, 0
    for i in np.flatnonzero(net.walk.any(axis=1)):
        s0, s1 = net.start[i], net.start[i + 1]
        owner = seg_owner[s0:s1 - 1]
        if np.all(owner < 0):
            continue
        surface = net.surface[s0:s1]
        top = surface + KERB
        for side, (edge, out) in enumerate(side_lines(net, s0, s1)):
            if not net.walk[i, side]:
                continue
            drawn = net.walk_keep[s0:s1 - 1, side]
            own = np.where(drawn, owner, -1)
            outer = edge + out * WIDTH
            verts, faces = ribbon(edge, outer, top, top)
            add_ribbon(tiles, verts, orient(verts, faces, [0, 1, 0]),
                       own, color, LAYER)
            verts, faces = ribbon(edge, edge, surface, top)
            # the kerb faces the road, against the outward normal
            want = xyz(-out[:, 0], np.zeros(len(out)), -out[:, 1])
            want = np.repeat(want[:-1], 2, axis=0)
            add_ribbon(tiles, verts, orient(verts, faces, want), own,
                       kerb_color, LAYER)
            length += float(np.diff(net.dist[s0:s1])[drawn].sum())
            clipped += int(np.count_nonzero(~drawn))
    corners = net.corners
    if corners:
        ok = area.keep(np.array([shapely.Polygon(c["polygon"])
                                 for c in corners], dtype=object),
                       np.array([c["edges"] for c in corners]),
                       YIELD_AREA, YIELD_FRAC,
                       np.array([c["node"] for c in corners]))
        net.corners = [c for c, k in zip(corners, ok) if k]
    for corner in net.corners:
        emit_corner(tiles, net, corner, color, kerb_color)
    return {"width_m": WIDTH, "kerb_m": KERB,
            "km": round(length / 1000, 1),
            "junction_corners": len(net.corners),
            "corners_kept": len(net.corners),
            "corners_clipped": len(corners) - len(net.corners),
            "walk_clipped": clipped,
            "edges_left_right_both": [
                int(np.count_nonzero(net.walk[:, 0] & ~net.walk[:, 1])),
                int(np.count_nonzero(~net.walk[:, 0] & net.walk[:, 1])),
                int(np.count_nonzero(net.walk.all(axis=1)))]}


def corner_height(net, node):
    """Road surface of the junction at node."""
    return net.height[node] + net.lift[node]


def emit_corner(tiles, net, corner, color, kerb_color):
    """Top of one junction corner and the kerb along the junction edge."""
    node = corner["node"]
    key = tile_keys(tiles, net.xy[node, 0], net.xy[node, 1])
    if key < 0:
        return
    bucket = tiles.bucket(key)[LAYER]
    poly = corner["polygon"]
    surface = corner_height(net, node)
    tri = mapbox_earcut.triangulate_float64(
        poly, np.array([len(poly)], dtype=np.uint32)).reshape(-1, 3)
    verts = xyz(poly[:, 0], np.full(len(poly), surface + KERB), poly[:, 1])
    bucket.add(verts, orient(verts, tri, [0, 1, 0]), color)
    edge = poly[:2]
    verts, faces = ribbon(edge, edge, np.full(2, surface),
                          np.full(2, surface + KERB))
    toward = net.xy[node] - edge.mean(axis=0)
    bucket.add(verts, orient(verts, faces, [toward[0], 0.0, -toward[1]]),
               kerb_color)
# - revised 2026-10-22 (road priority: segments and corners yield)
# - revised 2026-10-22 (tiles own their key lookup)
# - revised 2026-10-25 (default sidewalks in town only)
