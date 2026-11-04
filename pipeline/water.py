# file generated with AI assistance: Claude Code - 2026-11-04 16:00:00 UTC
"""Inland water (OSM lakes, ponds, riverbanks) as a surface of its own:
the `water` tile layer above a bed carved into the terrain mesh.

The surface takes its height from the banks, never from the interior
(the raster inside a river polygon is whatever the survey saw there):
the polygon boundary is sampled every SAMPLE_M on the conformed ground,
and a point of the surface lies DROP below the lowest bank sample within
its distance to the boundary plus LEVEL_R, which reaches the opposite
bank of a torrent. A compact polygon (4 pi A / P^2 above COMPACT, a lake
or pond) is level at the lowest point of its whole boundary. On a polygon
over a slope this gives a stepped cascade, which is what a Corsican
torrent looks like.

Every terrain grid vertex inside the water goes below the surface by at
least DEPTH_MIN, DEPTH from BANK_M off the bank, with no limit on the
cut: terrain left near the surface would flicker against it. Those
vertices take the bed colour, so no blue terrain shows at the shore.
The carve and the surface work on the terrain mesh only; the raster
(`ground`) that roads, skirts, trees and buildings read stays as it is,
so the gates and the clipping report do not move.

Roads crossing the water low (a ford, a culvert, a creek bridge drawn as
plain road: surface less than ROAD_CLEAR above the water) cut the
surface and the carve, buffered by ROAD_BUFFER so that no water vertex
lands on a road vertex (metrics.shared_heights indexes those). High
decks keep the water beneath them. The sea keeps its own path (sea.py).
"""
import mapbox_earcut
import numpy as np
import shapely

SAMPLE_M = 5.0
LEVEL_R = 18.0
COMPACT = 0.25
DROP = 0.25
DEPTH_MIN = 0.3
DEPTH = 1.0
BANK_M = 6.0
ROAD_CLEAR = 1.5
ROAD_BUFFER = 1.0


class Water:
    """Inland water of a world: its surface heights, the road cut, and
    per tile the carve of the terrain and the surface mesh."""

    def __init__(self, polygon, ground, base, roads_over):
        self.polygon = polygon
        self.stats = {"water_polygons": 0, "water_m2": 0.0,
                      "water_road_cuts": 0}
        if polygon is None or polygon.is_empty:
            self.polygon = None
            return
        parts = [p for p in getattr(polygon, "geoms", [polygon])
                 if p.geom_type == "Polygon" and p.area > 0.0]
        xs, ys, hs = [], [], []
        for part in parts:
            ring = shapely.segmentize(part.boundary, SAMPLE_M)
            pts = shapely.get_coordinates(ring)
            h = np.asarray(ground.height(pts[:, 0], pts[:, 1])) - base
            compact = 4.0 * np.pi * part.area / part.length ** 2 > COMPACT
            xs.append(pts[:, 0])
            ys.append(pts[:, 1])
            hs.append(np.full(len(h), h.min()) if compact else h)
        self.bx, self.by = np.concatenate(xs), np.concatenate(ys)
        self.bh = np.concatenate(hs)
        self.samples = shapely.STRtree(shapely.points(self.bx, self.by))
        self.boundary = polygon.boundary
        shapely.prepare(self.boundary)
        self.cut = self._road_cut(roads_over)
        self.area = polygon if self.cut is None \
            else shapely.difference(polygon, self.cut)
        shapely.prepare(self.polygon)
        shapely.prepare(self.area)
        self.stats.update(water_polygons=len(parts),
                          water_m2=round(float(polygon.area)))

    def _road_cut(self, roads_over):
        i = roads_over.tree.query(self.polygon, predicate="intersects")
        if not len(i):
            return None
        c = shapely.get_coordinates(shapely.centroid(roads_over.quads[i]))
        low = roads_over.surface[i] < self.level(c[:, 0], c[:, 1]) \
            + ROAD_CLEAR
        i = i[low]
        self.stats["water_road_cuts"] = int(len(i))
        if not len(i):
            return None
        return shapely.union_all(shapely.buffer(roads_over.quads[i],
                                                ROAD_BUFFER))

    def level(self, x, y):
        """Water level (relative to base, before DROP) at points x, y:
        the lowest bank sample within the distance to the boundary plus
        LEVEL_R."""
        x, y = np.asarray(x, float), np.asarray(y, float)
        pts = shapely.points(x, y)
        reach = shapely.distance(self.boundary, pts) + LEVEL_R
        q, s = self.samples.query(pts, predicate="dwithin", distance=reach)
        out = np.full(len(x), np.inf)
        np.minimum.at(out, q, self.bh[s])
        # every point has its nearest bank sample within reach
        return out

    def carve(self, xs, ys, hs, colors, bed_color):
        """Terrain grid vertices inside the water (outside the road cut)
        go below the surface; they take bed_color. In place."""
        if self.polygon is None:
            return
        inside = shapely.contains_xy(self.polygon, xs, ys)
        if self.cut is not None:
            inside &= ~shapely.contains_xy(self.cut, xs, ys)
        k = np.flatnonzero(inside)
        if not len(k):
            return
        d = shapely.distance(self.boundary, shapely.points(xs[k], ys[k]))
        depth = DEPTH_MIN + (DEPTH - DEPTH_MIN) * np.clip(d / BANK_M, 0, 1)
        bed = self.level(xs[k], ys[k]) - DROP - depth
        hs[k] = np.minimum(hs[k], bed)
        colors[k] = bed_color

    def surface(self, xs, ys, faces):
        """The surface over the terrain grid triangles (xs, ys, faces):
        each triangle cut to the water area, heights from level. Returns
        x, y, h, faces (map coordinates, counter-clockwise), or None."""
        if self.polygon is None:
            return None
        tri = np.stack([xs[faces], ys[faces]], axis=-1)
        polys = shapely.polygons(np.concatenate([tri, tri[:, :1]], axis=1))
        near = np.flatnonzero(shapely.intersects(self.area, polys))
        if not len(near):
            return None
        nx, ny, nf = [], [], []
        n = 0
        for geom in shapely.intersection(polys[near], self.area):
            for poly in getattr(geom, "geoms", [geom]):
                if poly.geom_type != "Polygon" or poly.area < 1e-4:
                    continue
                rings = [np.asarray(poly.exterior.coords)[:-1]]
                rings += [np.asarray(r.coords)[:-1] for r in poly.interiors]
                flat = np.vstack(rings)
                ends = np.cumsum([len(r) for r in rings]).astype(np.uint32)
                t = mapbox_earcut.triangulate_float64(flat, ends) \
                    .reshape(-1, 3)
                if not len(t):
                    continue
                ab = flat[t[:, 1]] - flat[t[:, 0]]
                ac = flat[t[:, 2]] - flat[t[:, 0]]
                flip = ab[:, 0] * ac[:, 1] - ab[:, 1] * ac[:, 0] < 0
                t[flip] = t[flip][:, [0, 2, 1]]
                nx.append(flat[:, 0])
                ny.append(flat[:, 1])
                nf.append(t + n)
                n += len(flat)
        if not nf:
            return None
        x, y = np.concatenate(nx), np.concatenate(ny)
        return x, y, self.level(x, y) - DROP, np.vstack(nf)
