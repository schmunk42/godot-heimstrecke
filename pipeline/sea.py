# file generated with AI assistance: Claude Code - 2026-10-23 10:45:00 UTC
"""The sea: the part of a square seaward of the OSM coastline.

OSM draws natural=coastline ways with the land on the left and the sea
on the right. The square's outline and the coastlines (extract.py keeps
every coastline way crossing the bbox, whole) are noded and polygonized;
a piece is sea when a point inside it lies right of the nearest
coastline. A world without coastline ways has no sea.

The terrain model has no data over the sea (LiDAR HD), and its edge is
not the shore line, so Dgm1Raster.fill_sea() sets sea cells to at most
0 m and fills the cells without data up to SHORE_M landward of the
coastline with 0 m too. Cells without data farther inland stay NaN, and
the raster refuses to answer there as before.
"""
import numpy as np
import shapely

# cells without data this far landward of the coastline count as sea
SHORE_M = 30.0
# the probe for the side of a coastline: half the segment length
SIDE_STEP_M = 0.5


def coastlines(ex, frame):
    """The coastline ways of the extract in local metres."""
    return [frame.geom_to_local(shapely.from_wkb(c["geom"]))
            for c in ex["coastlines"]]


def is_seaward(point, lines):
    """True if point lies right of the nearest coastline."""
    line = min(lines, key=lambda g: shapely.distance(g, point))
    d = line.project(point)
    a = line.interpolate(max(d - SIDE_STEP_M, 0.0))
    b = line.interpolate(min(d + SIDE_STEP_M, line.length))
    foot = line.interpolate(d)
    cross = ((b.x - a.x) * (point.y - foot.y)
             - (b.y - a.y) * (point.x - foot.x))
    return cross < 0


def sea_polygon(lines, box):
    """The sea inside box (a shapely polygon in local metres), or None."""
    if not lines:
        return None
    noded = shapely.union_all([box.boundary, *lines])
    pieces = shapely.get_parts(shapely.polygonize(shapely.get_parts(noded)))
    sea = [p for p in pieces
           if p.within(box.buffer(1.0))
           and is_seaward(p.point_on_surface(), lines)]
    if not sea:
        return None
    return shapely.make_valid(shapely.union_all(sea))


def horizon_water(heights, has_sea):
    """Horizon vertices drawn as water: Copernicus is 0 m over the sea."""
    if not has_sea:
        return np.zeros(len(heights), dtype=bool)
    return heights <= 0.5
