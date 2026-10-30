# file generated with AI assistance: Claude Code - 2026-10-20 20:45:15 UTC
"""Local frame shared by every pipeline stage.

Origin at the area center, metres, X = east, Y = up, Z = -north (Godot's
forward axis points north). Every coordinate goes through to_local(),
nothing else does its own projection.

A world may be turned by heading_deg (the recipe's `heading_deg`,
counter-clockwise from east): local X then points along the heading and
-Z 90 degrees left of it, so a long, narrow world can follow a road that
runs diagonally. to_utm() gives UTM metres for local metres, for the
rasters that are kept in UTM: EPSG:25832 (ETRS89 / UTM 32N, Baden-
Wuerttemberg and Corsica) unless the recipe names another zone in
`epsg`. Heading 0 takes the unrotated path, so the numbers of the
unturned worlds stay the same.
"""
import math

import numpy as np
import shapely
from pyproj import Transformer


class Frame:
    def __init__(self, lon, lat, heading_deg=0.0, epsg=25832):
        self.epsg = int(epsg)
        self.fwd = Transformer.from_crs(4326, self.epsg, always_xy=True)
        self.inv = Transformer.from_crs(self.epsg, 4326, always_xy=True)
        self.e0, self.n0 = self.fwd.transform(lon, lat)
        self.heading = float(heading_deg)
        a = math.radians(self.heading)
        self.cos, self.sin = math.cos(a), math.sin(a)

    def utm_to_local(self, e, n):
        de, dn = np.asarray(e) - self.e0, np.asarray(n) - self.n0
        if self.heading == 0.0:
            return de, dn
        return (de * self.cos + dn * self.sin,
                -de * self.sin + dn * self.cos)

    def to_utm(self, x, y):
        if self.heading == 0.0:
            return np.asarray(x) + self.e0, np.asarray(y) + self.n0
        x, y = np.asarray(x), np.asarray(y)
        return (x * self.cos - y * self.sin + self.e0,
                x * self.sin + y * self.cos + self.n0)

    def to_local(self, lon, lat):
        return self.utm_to_local(*self.fwd.transform(lon, lat))

    def to_lonlat(self, x, y):
        return self.inv.transform(*self.to_utm(x, y))

    def geom_to_local(self, geom):
        return shapely.transform(
            geom, lambda c: np.column_stack(self.to_local(c[:, 0], c[:, 1])))

    def geom_to_utm(self, geom):
        return shapely.transform(
            geom, lambda c: np.column_stack(self.to_utm(c[:, 0], c[:, 1])))

    def corners_utm(self, hx, hy):
        """UTM corners of the local rectangle +-hx, +-hy."""
        e, n = self.to_utm(np.array([-hx, hx, hx, -hx]),
                           np.array([-hy, -hy, hy, hy]))
        return np.asarray(e), np.asarray(n)


def xyz(x, h, y):
    """Local east/north plus height -> glTF/Godot vertex."""
    return np.column_stack([x, h, -np.asarray(y)])
# - revised 2026-10-23 (heading_deg, to_utm, corners_utm)
# - revised 2026-10-27 (epsg: UTM zone per recipe)
