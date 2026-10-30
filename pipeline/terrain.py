# file generated with AI assistance: Claude Code - 2026-10-20 20:45:15 UTC
"""Height sources: the 1 m terrain raster (DGM1, LiDAR HD or GEDTM30 in
UTM, see fetch.py) for the playable
area, Copernicus GLO-30 (lon/lat surface model) for the horizon only.

Both answer height(x, y) for local-frame metres (x east, y north relative
to frame.e0/n0) with a bilinear lookup between pixel centres.
"""
import random
import time
from pathlib import Path

import numpy as np
import rasterio
import rasterio.features
import rasterio.merge
import shapely
from rasterio.crs import CRS
from rasterio.transform import from_origin

DGM1_CRS = CRS.from_epsg(25832)


class TerrainError(RuntimeError):
    """Input, coverage or no-data problem; callers exit with code 2."""


def bilinear(data, col, row):
    """Sample data at fractional pixel-centre coordinates (clamped)."""
    c0 = np.clip(np.floor(col).astype(int), 0, data.shape[1] - 2)
    r0 = np.clip(np.floor(row).astype(int), 0, data.shape[0] - 2)
    fc = np.clip(col - c0, 0, 1)
    fr = np.clip(row - r0, 0, 1)
    top = data[r0, c0] * (1 - fc) + data[r0, c0 + 1] * fc
    bottom = data[r0 + 1, c0] * (1 - fc) + data[r0 + 1, c0 + 1] * fc
    return top * (1 - fr) + bottom * fr


class LonLatDem:
    """Bilinear lookup in a lon/lat raster, queried in local metres."""

    def __init__(self, paths, frame):
        datasets = [rasterio.open(p) for p in paths]
        self.data, self.transform = rasterio.merge.merge(datasets)
        self.data = self.data[0].astype(np.float32, copy=False)
        self.frame = frame

    def height(self, x, y):
        lon, lat = self.frame.to_lonlat(x, y)
        col, row = ~self.transform * (np.asarray(lon), np.asarray(lat))
        return bilinear(self.data, np.asarray(col) - 0.5,
                        np.asarray(row) - 0.5)


class Dgm1Raster:
    """Bilinear lookup in one UTM GeoTIFF written by fetch.py, in the
    frame's EPSG (25832 unless the recipe names another zone).

    Refuses to open if the raster does not cover the local rectangle
    +- half_extent_m (a scalar or the pair hx, hy; between pixel
    centres) and refuses to answer for points without data: no clamping,
    no filling, no fallback to another source. The raster may be rotated
    (fetch.py writes a turned world's raster along its local axes); every
    lookup goes through frame.to_utm() and the inverse geotransform.
    """

    def __init__(self, path, frame, half_extent_m):
        self.path = Path(path)
        try:
            ds = rasterio.open(self.path)
        except rasterio.errors.RasterioIOError as err:
            raise TerrainError(f"cannot open DGM1 raster {path}: {err}")
        with ds:
            if ds.crs != CRS.from_epsg(frame.epsg):
                raise TerrainError(f"{path}: CRS is {ds.crs}, "
                                   f"expected EPSG:{frame.epsg}")
            self.data = ds.read(1).astype(np.float32, copy=False)
            if ds.nodata is not None and not np.isnan(ds.nodata):
                self.data[self.data == ds.nodata] = np.nan
            self.transform = ds.transform
            self.bounds = ds.bounds
        self.frame = frame
        self.inverse = ~self.transform
        self.res = float(np.hypot(self.transform.a, self.transform.d))
        hx, hy = np.broadcast_to(half_extent_m, 2)
        ce, cn = frame.corners_utm(hx, hy)
        col, row = self.inverse * (ce, cn)
        rows, cols = self.data.shape
        if not (np.all(np.asarray(col) >= 0.5)
                and np.all(np.asarray(col) <= cols - 0.5)
                and np.all(np.asarray(row) >= 0.5)
                and np.all(np.asarray(row) <= rows - 0.5)):
            b = self.bounds
            raise TerrainError(
                f"DGM1 raster {self.path.name} does not cover the area: "
                f"raster EPSG:{frame.epsg} bounds {b.left:.0f},{b.bottom:.0f},"
                f"{b.right:.0f},{b.top:.0f}, required corners "
                + " ".join(f"{e:.0f},{n:.0f}" for e, n in zip(ce, cn))
                + " (re-run pipeline/fetch.py with a larger --size)")

    def footprint(self):
        """The raster's outline in local metres (a polygon, turned with
        the frame or the raster)."""
        rows, cols = self.data.shape
        e, n = self.transform * (np.array([0, cols, cols, 0]),
                                 np.array([rows, rows, 0, 0]))
        x, y = self.frame.utm_to_local(np.asarray(e), np.asarray(n))
        return shapely.Polygon(np.column_stack([x, y]))

    def fill_sea(self, sea, shore_m):
        """Cells inside sea (local metres, sea.py) get at most 0 m, cells
        without data within shore_m of it 0 m; returns both counts."""
        def mask(geom):
            world = self.frame.geom_to_utm(geom)
            return rasterio.features.geometry_mask(
                [world], out_shape=self.data.shape,
                transform=self.transform, invert=True)
        inside = mask(sea)
        shore = np.isnan(self.data) & ~inside & mask(sea.buffer(shore_m))
        self.data[inside] = np.fmin(self.data[inside], 0.0)
        self.data[shore] = 0.0
        return int(np.count_nonzero(inside)), int(np.count_nonzero(shore))

    def height(self, x, y):
        e, n = self.frame.to_utm(np.asarray(x, dtype=np.float64),
                                 np.asarray(y, dtype=np.float64))
        col, row = self.inverse * (e, n)
        col = np.asarray(col) - 0.5
        row = np.asarray(row) - 0.5
        rows, cols = self.data.shape
        outside = (col < 0) | (col > cols - 1) | (row < 0) | (row > rows - 1)
        h = bilinear(self.data, col, row)
        bad = outside | np.isnan(h)
        if np.any(bad):
            i = np.flatnonzero(bad)[0]
            be, bn = np.ravel(e)[i], np.ravel(n)[i]
            raise TerrainError(
                f"DGM1 has no data at EPSG:{self.frame.epsg} "
                f"{be:.1f},{bn:.1f} "
                f"({int(np.count_nonzero(bad))} points) in {self.path.name}")
        return h


def xyz_corners(path):
    """First and last sample of an LGL .xyz file (NW and SE cell centre)."""
    with open(path, "rb") as fh:
        first = fh.readline().split()
        fh.seek(-200, 2)
        last = fh.read().split(b"\n")
        last = [ln for ln in last if ln.strip()][-1].split()
    return (float(first[0]), float(first[1])), (float(last[0]),
                                                float(last[1]))


def convert_xyz_to_geotiff(xyz_paths, out_path, res=1.0):
    """Merge LGL DGM1 .xyz files into one float32 GeoTIFF (EPSG:25832).

    LGL layout (checked 2026-10-20): no header, "easting northing height"
    separated by single spaces, CRLF line ends, 1 m grid, rows from north
    to south and east-increasing within a row, 1000 x 1000 samples per
    1 km file, four files per 2 km zip. The coordinates are cell CENTRES
    (all end in .50), so the pixel-is-area raster starts half a cell
    west/north of the first sample: left = min_e - 0.5, top = max_n + 0.5.
    Cells without a sample stay NaN (nodata). Files are parsed one at a
    time; np.loadtxt (numpy 2 C parser) measured 0.16 s per file, faster
    than np.fromstring (0.25 s).
    """
    xyz_paths = [Path(p) for p in xyz_paths]
    if not xyz_paths:
        raise TerrainError("no .xyz files to convert")
    corners = [xyz_corners(p) for p in xyz_paths]
    left = min(c[0][0] for c in corners) - res / 2
    top = max(c[0][1] for c in corners) + res / 2
    right = max(c[1][0] for c in corners) + res / 2
    bottom = min(c[1][1] for c in corners) - res / 2
    width = int(round((right - left) / res))
    height = int(round((top - bottom) / res))
    data = np.full((height, width), np.nan, dtype=np.float32)
    samples = []
    started = time.time()
    for p in xyz_paths:
        pts = np.loadtxt(p, dtype=np.float64)
        col = (pts[:, 0] - left) / res - 0.5
        row = (top - pts[:, 1]) / res - 0.5
        ci, ri = np.rint(col).astype(int), np.rint(row).astype(int)
        if np.abs(col - ci).max() > 1e-6 or np.abs(row - ri).max() > 1e-6:
            raise TerrainError(f"{p.name}: samples are not on the "
                               f"{res} m cell-centre grid")
        if ci.min() < 0 or ri.min() < 0 or ci.max() >= width \
                or ri.max() >= height:
            raise TerrainError(f"{p.name}: samples outside the union "
                               "bounds (file not ordered NW to SE?)")
        data[ri, ci] = pts[:, 2]
        k = random.randrange(len(pts))
        samples.append(tuple(pts[k]))
        del pts
    parse_s = time.time() - started
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp.tif")
    with rasterio.open(
            tmp, "w", driver="GTiff", width=width, height=height, count=1,
            dtype="float32", crs=DGM1_CRS, nodata=np.nan,
            transform=from_origin(left, top, res, res), tiled=True,
            blockxsize=512, blockysize=512, compress="deflate",
            predictor=3, BIGTIFF="IF_SAFER") as ds:
        ds.write(data, 1)
    nodata = int(np.count_nonzero(np.isnan(data)))
    del data
    with rasterio.open(tmp) as ds:
        for e, n, h in random.sample(samples, min(3, len(samples))):
            got = next(ds.sample([(e, n)]))[0]
            if got != np.float32(h):
                raise TerrainError(f"verification failed at {e},{n}: "
                                   f"source {h}, GeoTIFF {got}")
    tmp.replace(out_path)
    print(f"converted files={len(xyz_paths)} size={width}x{height} "
          f"nodata_cells={nodata} parse_s={parse_s:.0f} "
          f"total_s={time.time() - started:.0f}")
    return out_path
# - revised 2026-10-23 (fill_sea for the sea of sea.py)
# - revised 2026-10-23 (rectangular, turned area; rotated rasters)
