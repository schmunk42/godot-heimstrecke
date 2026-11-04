# file generated with AI assistance: Claude Code - 2026-11-04 17:40:00 UTC
"""Traffic islands at junctions, filled flat at road height.

OSM maps a large junction as many one-way carriageways and links, so
the drawn road area has small holes between them: the triangles and
slivers between a slip road and the main carriageway, the gaps between
the turning lanes. The terrain shows there, a 10 m grid that cannot
follow a hole a few metres wide: it reads as grass patches with dark
slopes and skirt pieces poking up between the lanes (Österreichischer
Platz, B 27, 2026-11-04). Real islands there are low kerbed plates.

Every hole of the ground road area (strip segments and junction hulls,
bridges and tunnels excluded, as in priority.py) up to MAX_AREA m2 gets
a plate: the hole's polygon triangulated on its own rim, every rim
vertex at the road surface of the nearest strip edge or junction hull,
DROP below it so the road wins where both overlap in plan. A hole is
left as it is when a building or inland water lies in it (a city block,
not an island) or its rim rises more than MAX_RISE (a ramp beside a
lower road: the plate would be a wall). Plates go into their own
`islands` layer (the `roads` vertices at a node must share one height,
metrics.shared_heights) in their own colour, and collide. conform.py
keeps the terrain under each plate with points every POINT_STEP m.
"""
import numpy as np
import shapely

from frame import xyz
from roads import convex_hull, tile_keys

LAYER = "islands"
# holes up to this many m2 are filled (the triangle in the middle of
# the Österreichischer Platz has 841); larger ones are parks, squares
# or blocks
MAX_AREA = 1000.0
# a hole whose rim heights differ by more than this is not filled (the
# triangle at the Österreichischer Platz rises 2.0 m over 50 m, a hole
# beside a ramp over a lower road 10 m)
MAX_RISE = 2.5
# the plate lies this far below the road surface at its rim
DROP = 0.02
# holes smaller than this are noise between overlapping strips
MIN_AREA = 0.5
# conform.py keeps the terrain this far below the plate, at points this
# far apart inside it
MARGIN = 0.05
POINT_STEP = 2.5


def ground_area(net):
    """The ground road area in plan before the junction surfaces are
    emitted: strip segment quads and the hull of every junction's rim
    (roads.junction_surface draws the same hull)."""
    k = np.arange(len(net.sx) - 1)
    k = k[(net.edge_of[k] == net.edge_of[k + 1])
          & ~net.struct[net.edge_of[k]]]
    polys = list(shapely.make_valid(shapely.polygons(np.stack(
        [net.left[k], net.left[k + 1], net.right[k + 1], net.right[k],
         net.left[k]], axis=1))))
    rims = junction_rims(net)
    for node, rim in rims.items():
        pts = np.vstack([net.xy[node][None, :], rim])
        hull = convex_hull(pts.tolist())
        if len(hull) >= 3:
            polys.append(shapely.Polygon(pts[hull]))
    return k, rims, shapely.union_all(np.array(polys, dtype=object))


def junction_rims(net):
    """Strip end points per ground junction node (as emit_junctions)."""
    rims = {int(n): []
            for n in np.flatnonzero(net.junction & ~net.node_struct)}
    first, last = net.start[:-1], net.start[1:] - 1
    for ends, smp in ((net.u, first), (net.v, last)):
        for node, s in zip(ends.tolist(), smp.tolist()):
            if node in rims:
                rims[node] += [net.left[s], net.right[s]]
    return {n: np.array(r) for n, r in rims.items() if len(r)}


class RimHeights:
    """Road surface height at a point on the rim of the road area: on
    the nearest strip edge line (interpolated along it) or junction
    hull (flat)."""

    def __init__(self, net, k, rims):
        a = np.vstack([net.left[k], net.right[k]])
        b = np.vstack([net.left[k + 1], net.right[k + 1]])
        ha = np.concatenate([net.surface[k], net.surface[k]])
        hb = np.concatenate([net.surface[k + 1], net.surface[k + 1]])
        for node, rim in rims.items():
            ring = np.vstack([net.xy[node][None, :], rim])
            hull = convex_hull(ring.tolist())
            if len(hull) < 3:
                continue
            p = ring[hull]
            h = net.height[node] + net.lift[node]
            a = np.vstack([a, p])
            b = np.vstack([b, np.roll(p, -1, axis=0)])
            ha = np.concatenate([ha, np.full(len(p), h)])
            hb = np.concatenate([hb, np.full(len(p), h)])
        self.a, self.b, self.ha, self.hb = a, b, ha, hb
        self.tree = shapely.STRtree(shapely.linestrings(
            np.stack([a, b], axis=1)))

    def __call__(self, xy):
        i = self.tree.query_nearest(shapely.points(xy), all_matches=False)
        pi, li = i
        out = np.zeros(len(xy))
        ab = self.b[li] - self.a[li]
        t = np.einsum("ij,ij->i", xy[pi] - self.a[li], ab)
        t = np.clip(t / np.maximum(np.einsum("ij,ij->i", ab, ab), 1e-9),
                    0.0, 1.0)
        out[pi] = self.ha[li] * (1 - t) + self.hb[li] * t
        return out


def find_islands(net, blocked, half):
    """Plates for the holes of the ground road area inside the playable
    rectangle of half sides half (the conformed terrain ends there);
    blocked: polygons (buildings, inland water) that keep a hole open.
    Returns a list of (vertices xy, heights, triangles) and stats."""
    k, rims, area = ground_area(net)
    hx, hy = np.broadcast_to(half, 2)
    holes = shapely.polygons([
        ring for g in shapely.get_parts(area) for ring in g.interiors])
    holes = holes[shapely.within(holes, shapely.box(-hx, -hy, hx, hy))]
    sizes = shapely.area(holes)
    stats = {"holes": int(len(holes)),
             "too_large": int(np.count_nonzero(sizes > MAX_AREA))}
    holes = holes[(sizes >= MIN_AREA) & (sizes <= MAX_AREA)]
    if len(blocked):
        tree = shapely.STRtree(np.asarray(blocked, dtype=object))
        hi, _ = tree.query(holes, predicate="intersects")
        free = np.ones(len(holes), dtype=bool)
        free[hi] = False
        stats["blocked"] = int(np.count_nonzero(~free))
        holes = holes[free]
    heights = RimHeights(net, k, rims)
    plates, steep = [], 0
    for hole in holes:
        hole = shapely.orient_polygons(hole)
        xy = np.array(hole.exterior.coords)[:-1]
        h = heights(xy) - DROP
        if h.max() - h.min() > MAX_RISE:
            steep += 1
            continue
        tris = shapely.get_parts(
            shapely.constrained_delaunay_triangles(hole))
        corners = shapely.get_coordinates(tris).reshape(-1, 4, 2)[:, :3]
        index = {tuple(p): i for i, p in enumerate(xy.tolist())}
        faces = np.array([[index[tuple(p)] for p in c.tolist()]
                          for c in corners])
        plates.append((xy, h, faces))
    stats.update(steep=steep, filled=len(plates),
                 area_m2=round(float(sum(
                     shapely.area(shapely.polygons(p[0]))
                     for p in plates)), 1))
    return plates, stats


def plate_points(plates, shift=0.0):
    """Points inside every plate every POINT_STEP m (the grid moved by
    shift m) plus its vertices, with the plate height there minus
    MARGIN (conform.py)."""
    pts, gh = [], []
    for xy, h, faces in plates:
        tri = xy[faces]
        lo, hi = tri.min(axis=(0, 1)) + shift, tri.max(axis=(0, 1))
        gx, gy = np.meshgrid(np.arange(lo[0], hi[0], POINT_STEP),
                             np.arange(lo[1], hi[1], POINT_STEP))
        g = np.column_stack([gx.ravel(), gy.ravel()])
        p, w, f = barycentric(g, tri)
        pts += [xy, p]
        gh += [h, np.einsum("ij,ij->i", w, h[faces[f]])]
    if not pts:
        return np.zeros((0, 2)), np.zeros(0)
    return np.vstack(pts), np.concatenate(gh) - MARGIN


def terrain_above(plates, ground, base):
    """Points where the conformed terrain rises above a plate, so it
    shows through: count and largest excess m. Checked between the
    points conform.py pushed down (the grid moved by half a step),
    because at those the terrain is below by construction."""
    pts, gh = plate_points(plates, POINT_STEP / 2)
    if not len(pts):
        return {"terrain_above": 0, "terrain_above_max_m": 0.0}
    excess = ground.height(pts[:, 0], pts[:, 1]) - base - gh - MARGIN
    over = excess > 0
    if over.any():
        worst = pts[np.argmax(excess)]
        print(f"islands: terrain {excess.max():.2f} m above a plate at "
              f"x={worst[0]:.1f} y={worst[1]:.1f}")
    return {"terrain_above": int(np.count_nonzero(over)),
            "terrain_above_max_m": round(float(max(excess.max(), 0.0)),
                                         2)}


def barycentric(p, tri):
    """Points of p inside one of the triangles tri, their weights and
    triangle index."""
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    v0, v1 = b - a, c - a
    d = v0[:, 0] * v1[:, 1] - v0[:, 1] * v1[:, 0]
    d = np.where(np.abs(d) < 1e-12, 1e-12, d)
    q = p[:, None, :] - a[None]
    u = (q[..., 0] * v1[:, 1] - q[..., 1] * v1[:, 0]) / d
    v = (v0[:, 0] * q[..., 1] - v0[:, 1] * q[..., 0]) / d
    inside = (u >= 0) & (v >= 0) & (u + v <= 1)
    pi, f = np.nonzero(inside)
    pi, first = np.unique(pi, return_index=True)
    f = f[first]
    w = np.column_stack([1 - u[pi, f] - v[pi, f], u[pi, f], v[pi, f]])
    return p[pi], w, f


def emit_islands(tiles, plates, color):
    """Each plate into the `islands` layer of the tile of its first
    vertex, counter-clockwise in plan (normal up, as
    roads.junction_surface)."""
    for xy, h, faces in plates:
        key = tile_keys(tiles, xy[:1, 0], xy[:1, 1])[0]
        if key < 0:
            continue
        a, b, c = (xy[faces[:, i]] for i in range(3))
        up = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) \
            - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0]) > 0
        faces = np.where(up[:, None], faces, faces[:, ::-1])
        tiles.bucket(key)[LAYER].add(xyz(xy[:, 0], h, xy[:, 1]), faces,
                                     color)
