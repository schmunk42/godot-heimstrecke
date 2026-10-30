# file generated with AI assistance: Claude Code - 2026-10-22 22:40:00 UTC
"""Road priority: what the drawn carriageway covers in plan.

Sidewalks and skirts are drawn from a strip edge outward without
looking at their neighbours, so where two roads meet at a sharp angle,
run side by side or end at a junction surface, one road's verge lies on
the other road: a kerb there is a step a car runs into, a skirt a slab
poking through the asphalt. The road has priority everywhere.
RoadArea indexes every drawn ground carriageway piece (each strip
segment quad and each junction hull, bridges and tunnels excluded: they
lie above or below the ground verges) in one shapely STRtree, so the
emitters can test their pieces in batches and leave out what lies on a
road (sidewalks.py, skirts.py) and the markings can stop at junction
surfaces (markings.py).
"""
import numpy as np
import shapely

# exclude value that matches no polygon (junctions carry edge -1,
# strips node -1)
NO_EDGE = -2


def road_area(net):
    """The RoadArea of net, built once after the junction surfaces."""
    area = getattr(net, "road_area", None)
    if area is None:
        area = net.road_area = RoadArea(net)
    return area


def valid(polys):
    """Polygons made valid where needed (bowtie quads at sharp bends)."""
    polys = np.asarray(polys, dtype=object).copy()
    bad = ~shapely.is_valid(polys)
    if bad.any():
        polys[bad] = shapely.make_valid(polys[bad])
    return polys


def mine(values, exclude, pi, count):
    """Per hit: the road polygon's edge or node (values) is one the
    hitting polygon pi excludes."""
    if exclude is None:
        return np.zeros(len(pi), dtype=bool)
    own = np.asarray(exclude)
    own = own.reshape(-1, 1) if own.ndim < 2 else own
    own = np.broadcast_to(own, (count, own.shape[1]))
    return np.any(values[:, None] == own[pi], axis=1)


class RoadArea:
    """Every ground strip segment quad and junction hull, in plan.

    edge: edge index per polygon, -1 for junction hulls.
    """

    def __init__(self, net):
        k = np.arange(len(net.sx) - 1)
        k = k[(net.edge_of[k] == net.edge_of[k + 1])
              & ~net.struct[net.edge_of[k]]]
        quads = shapely.polygons(np.stack(
            [net.left[k], net.left[k + 1], net.right[k + 1], net.right[k],
             net.left[k]], axis=1))
        rings = [(node, ring) for node, ring, _ in net.junction_rings
                 if not net.node_struct[node] and len(ring) >= 3]
        hulls = [shapely.Polygon(ring) for _, ring in rings]
        self.polys = valid(np.concatenate(
            [quads, np.array(hulls, dtype=object)]))
        self.edge = np.concatenate(
            [net.edge_of[k], np.full(len(hulls), -1)])
        self.node = np.concatenate(
            [np.full(len(k), -1), [int(n) for n, _ in rings]]).astype(int)
        self.tree = shapely.STRtree(self.polys)
        self.junctions = shapely.STRtree(self.polys[self.edge < 0])

    def overlap(self, polygon, exclude_edge=None, exclude_node=None):
        """m2 of each polygon on a road other than the strips of its
        exclude_edge and the hulls of its exclude_node (one polygon or
        an array; each exclude a scalar, one value per polygon or a
        (polygons, k) array of several).

        Where pieces of several road polygons hit one polygon (they may
        overlap each other) their union is measured.
        """
        polys = valid(np.atleast_1d(polygon))
        area = np.zeros(len(polys))
        pi, ti = self.tree.query(polys, predicate="intersects")
        hit = ~(mine(self.edge[ti], exclude_edge, pi, len(polys))
                | mine(self.node[ti], exclude_node, pi, len(polys)))
        hit = np.flatnonzero(hit)
        hit = hit[np.argsort(pi[hit], kind="stable")]
        pi, ti = pi[hit], ti[hit]
        if len(pi):
            pieces = shapely.intersection(polys[pi], self.polys[ti])
            np.add.at(area, pi, shapely.area(pieces))
            # several pieces of one polygon may overlap each other
            first = np.flatnonzero(np.diff(pi, prepend=-1))
            ends = np.append(first[1:], len(pi))
            for a, b in zip(first[ends - first > 1],
                            ends[ends - first > 1]):
                if area[pi[a]] > 0:
                    area[pi[a]] = shapely.union_all(pieces[a:b]).area
        return area if np.ndim(polygon) else float(area[0])

    def keep(self, polygon, exclude_edge, min_area, min_frac,
             exclude_node=None):
        """False where the overlap exceeds min_area m2 or min_frac of
        the polygon's own area (one polygon or an array)."""
        polys = valid(np.atleast_1d(polygon))
        over = np.atleast_1d(self.overlap(polys, exclude_edge,
                                          exclude_node))
        ok = (over <= min_area) & (over <= min_frac * shapely.area(polys))
        return ok if np.ndim(polygon) else bool(ok[0])

    def in_junction(self, x, y):
        """Per point: lies on a ground junction hull."""
        pts = shapely.points(np.asarray(x, dtype=float),
                             np.asarray(y, dtype=float))
        pts = np.atleast_1d(pts)
        out = np.zeros(len(pts), dtype=bool)
        pi, _ = self.junctions.query(pts, predicate="intersects")
        out[pi] = True
        return out

    def gap(self, start, direction, own, reach):
        """Free run from each start point along direction (unit) to the
        nearest road other than edge own, capped at reach."""
        end = start + direction * reach
        rays = shapely.linestrings(np.stack([start, end], axis=1))
        pi, ti = self.tree.query(rays, predicate="intersects")
        hit = self.edge[ti] != np.broadcast_to(own, len(start))[pi]
        pi, ti = pi[hit], ti[hit]
        out = np.full(len(start), float(reach))
        if len(pi):
            d = shapely.distance(
                shapely.points(start[pi]),
                shapely.intersection(rays[pi], self.polys[ti]))
            np.minimum.at(out, pi, np.nan_to_num(d, nan=reach))
        return out
