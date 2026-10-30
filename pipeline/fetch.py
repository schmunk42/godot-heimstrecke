# file generated with AI assistance: Claude Code - 2026-10-20 20:45:15 UTC
"""Stage 0: download the 1 m terrain model of an area and turn it into
one GeoTIFF in UTM (EPSG:25832 or the recipe's `epsg`, the contract of
terrain.Dgm1Raster).

--source dgm1 (default): DGM1 of the LGL Baden-Wuerttemberg. The 2 km
zips sit on a grid with odd easting and even northing km of the
south-west corner (EPSG:25832). The result is
<out>/dgm1/dgm1_<E0>_<N0>_<km>.tif. Licence: dl-de/by-2-0,
"Datenquelle: LGL, www.lgl-bw.de".

--source lidarhd: MNT LiDAR HD of the IGN (France, 1 m, heights
NGF-IGN), fetched as raw float32 GeoTIFF blocks from the Geoplateforme
WMS in Lambert-93 (EPSG:2154) and warped bilinearly onto a 1 m
UTM grid. The result is <out>/lidarhd/lidarhd_<E0>_<N0>_<km>.tif.
Over the sea the service has no data; those cells stay NaN, build.py
fills them from the OSM coastline (sea.py). Licence: Licence Ouverte
2.0 (Etalab), "IGN - LiDAR HD". A turned or rectangular world (--width,
--heading, see frame.py) gets its raster along its own local axes
(a rotated geotransform, the rectangle + MARGIN_M at 1 m),
<out>/lidarhd/lidarhd_<E>_<N>_<L>x<W>_h<heading>.tif with the centre in
UTM metres, and only the WMS blocks that touch it are fetched.

--source gedtm30: GEDTM30 v1.2 of OpenGeoHub (global terrain model,
1 arc second, about 30 m, heights on EGM2008) for worlds without an
open 1 m model, read as a window from the global cloud-optimised
GeoTIFF (GEDTM30_URL, no key), cached under <out>/gedtm30/src/ and
warped bilinearly onto the same 1 m UTM grid as LiDAR HD. The file
carries scale 0.1, but the values are metres (checked against
Copernicus 2026-10-27), so the scale is not applied. The sea has no
data. A substitute raster: 30 m between samples. Licence: CC BY 4.0,
"GEDTM30, OpenGeoHub". The result is <out>/gedtm30/gedtm30_<E0>_<N0>_<km>
[_<epsg>].tif.

The last stdout line is the path of the GeoTIFF.
"""
import argparse
import math
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import rasterio
import rasterio.warp
import rasterio.windows
import requests
import shapely
from affine import Affine
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.transform import from_origin

from frame import Frame
from terrain import TerrainError, convert_xyz_to_geotiff

SOURCES = ("dgm1", "lidarhd", "gedtm30")
# sources warped onto a 1 m UTM grid (target_grid), named by km_grid
WARPED = ("lidarhd", "gedtm30")
# the UTM zone of a recipe without `epsg` (ETRS89 / UTM 32N)
DEFAULT_EPSG = 25832
URL = "https://opengeodata.lgl-bw.de/data/dgm/{}"
WMS_URL = "https://data.geopf.fr/wms-r/wms"
WMS_LAYER = "IGNF_LIDAR-HD_MNT_ELEVATION.ELEVATIONGRIDCOVERAGE.LAMB93"
LAMB93 = CRS.from_epsg(2154)
GEDTM30_URL = ("https://s3.opengeohub.org/global/dtm/v1.2/"
               "gedtm_rf_m_30m_s_20060101_20151231_go_epsg.4326.3855_v1.2.tif")
# lon/lat slack around the area's outline for the bilinear kernel
# (3 cells of 1 arc second)
GEDTM30_SLACK_DEG = 3 / 3600
# one WMS request: BLOCK_M x BLOCK_M at 1 m (4000 px took 7 s, 64 MB)
BLOCK_M = 4000
# Lambert-93 bbox beyond the warped square, for the rotation between the
# two grids and the bilinear kernel
WMS_SLACK_M = 50
# the service marks no data with -9999 but resamples it into the
# neighbouring cells (-9420 seen at the coast); nothing in France lies
# this low
NODATA_BELOW_M = -5.0
# a turned area's raster reaches this far beyond the margin: the
# coverage check wants the area between pixel centres, and the clipping
# report asks for terrain under road edges up to half a road width past
# the clip (the square grids get that from their km rounding)
TURNED_PAD_M = 50
# DGM1 covers the playable square plus this margin (build.py imports it)
MARGIN_M = 100.0
ZIP_KM = 2


class FetchError(RuntimeError):
    pass


def zip_grid(frame, size_km):
    """South-west km corners (E odd, N even) covering the area + margin."""
    r = size_km * 500.0 + MARGIN_M
    e_lo = math.floor((frame.e0 - r) / 1000)
    n_lo = math.floor((frame.n0 - r) / 1000)
    e_lo -= 1 - e_lo % 2
    n_lo -= n_lo % 2
    es = list(range(e_lo, math.ceil((frame.e0 + r) / 1000), ZIP_KM))
    ns = list(range(n_lo, math.ceil((frame.n0 + r) / 1000), ZIP_KM))
    return es, ns


def area_km(es, ns):
    """Size of the zip grid in km: "12", or "12x14" if not square."""
    km_e, km_n = len(es) * ZIP_KM, len(ns) * ZIP_KM
    return str(km_e) if km_e == km_n else f"{km_e}x{km_n}"


def km_grid(frame, size_km):
    """South-west and north-east km corners covering the area + margin
    (LiDAR HD, no zip grid)."""
    r = size_km * 500.0 + MARGIN_M
    return (math.floor((frame.e0 - r) / 1000),
            math.floor((frame.n0 - r) / 1000),
            math.ceil((frame.e0 + r) / 1000),
            math.ceil((frame.n0 + r) / 1000))


def turned(size_km, width_km, heading_deg):
    """True for a rectangular or turned area (the rotated LiDAR grid)."""
    return (width_km is not None and width_km != size_km) \
        or bool(heading_deg)


def tif_name(lat, lon, size_km, source="dgm1", width_km=None,
             heading_deg=0.0, epsg=DEFAULT_EPSG):
    """File name of the GeoTIFF for the area (world.py derives it too);
    a UTM zone other than the default adds _<epsg> before .tif."""
    name = _tif_name(lat, lon, size_km, source, width_km, heading_deg,
                     epsg)
    if epsg != DEFAULT_EPSG:
        name = name.removesuffix(".tif") + f"_{epsg}.tif"
    return name


def _tif_name(lat, lon, size_km, source, width_km, heading_deg, epsg):
    frame = Frame(lon, lat, epsg=epsg)
    if turned(size_km, width_km, heading_deg):
        if source not in WARPED:
            raise FetchError("a rectangular or turned world needs "
                             f"--source {' or '.join(WARPED)}")
        return (f"{source}_{frame.e0:.0f}_{frame.n0:.0f}_{size_km:g}x"
                f"{width_km:g}_h{heading_deg:g}.tif")
    if source in WARPED:
        e0, n0, e1, n1 = km_grid(frame, size_km)
        km = str(e1 - e0) if e1 - e0 == n1 - n0 else f"{e1 - e0}x{n1 - n0}"
        return f"{source}_{e0}_{n0}_{km}.tif"
    es, ns = zip_grid(frame, size_km)
    return f"dgm1_{es[0]}_{ns[0]}_{area_km(es, ns)}.tif"


def download(url, dest):
    tmp = dest.with_suffix(".part")
    for attempt in (1, 2):
        try:
            with requests.get(url, stream=True, timeout=60) as resp:
                if resp.status_code == 404:
                    raise FetchError(f"{url} is 404: DGM1 has no tile "
                                     "there (area outside "
                                     "Baden-Wuerttemberg?)")
                resp.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in resp.iter_content(1 << 20):
                        fh.write(chunk)
            tmp.replace(dest)
            return
        except requests.RequestException as err:
            if attempt == 2:
                raise FetchError(f"download of {url} failed: {err}")
            print(f"  retry {dest.name}: {err}", flush=True)


def extract_xyz(zip_path, target):
    """Unpack only the .xyz members, flat, into target."""
    out = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = Path(info.filename).name
            if info.is_dir() or not name.endswith(".xyz"):
                continue
            dest = target / name
            with zf.open(info) as src, dest.open("wb") as fh:
                while chunk := src.read(1 << 20):
                    fh.write(chunk)
            out.append(dest)
    if not out:
        raise FetchError(f"{zip_path.name} contains no .xyz files")
    return out


def fetch_block(e, n, dest):
    """One BLOCK_M square of the WMS with its south-west corner at e, n
    (Lambert-93), as a GeoTIFF on disk (cached like the zips)."""
    if dest.exists() and dest.stat().st_size > 0:
        return False
    params = {"SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
              "LAYERS": WMS_LAYER, "STYLES": "", "CRS": "EPSG:2154",
              "BBOX": f"{e},{n},{e + BLOCK_M},{n + BLOCK_M}",
              "WIDTH": BLOCK_M, "HEIGHT": BLOCK_M,
              "FORMAT": "image/geotiff"}
    tmp = dest.with_suffix(".part")
    for attempt in (1, 2):
        try:
            resp = requests.get(WMS_URL, params=params, timeout=180)
            resp.raise_for_status()
            if "tiff" not in resp.headers.get("content-type", ""):
                raise FetchError(f"WMS block {e},{n} is not a GeoTIFF: "
                                 f"{resp.text[:200]}")
            tmp.write_bytes(resp.content)
            tmp.replace(dest)
            return True
        except requests.RequestException as err:
            if attempt == 2:
                raise FetchError(f"WMS block {e},{n} failed: {err}")
            print(f"  retry {dest.name}: {err}", flush=True)


def read_block(path):
    """Heights of a WMS block, no data as NaN. The service writes a CRS
    without datum, so the grid is checked and Lambert-93 assumed."""
    with rasterio.open(path) as ds:
        if ds.shape != (BLOCK_M, BLOCK_M) or abs(ds.transform.a - 1) > 1e-9:
            raise FetchError(f"{path.name}: expected {BLOCK_M} px at 1 m, "
                             f"got {ds.shape} at {ds.transform.a}")
        data = ds.read(1).astype(np.float32, copy=False)
    data[data < NODATA_BELOW_M] = np.nan
    return data


def target_grid(lat, lon, size_km, width_km=None, heading_deg=0.0,
                epsg=DEFAULT_EPSG):
    """Width, height (px at 1 m) and geotransform of the warped raster.

    A square unturned area keeps the km-aligned UTM grid; a
    rectangular or turned one gets a grid along its local axes."""
    frame = Frame(lon, lat, heading_deg, epsg)
    if not turned(size_km, width_km, heading_deg):
        e0, n0, e1, n1 = km_grid(frame, size_km)
        return ((e1 - e0) * 1000, (n1 - n0) * 1000,
                from_origin(e0 * 1000, n1 * 1000, 1.0, 1.0))
    hx = math.ceil(size_km * 500.0 + MARGIN_M) + TURNED_PAD_M
    hy = math.ceil(width_km * 500.0 + MARGIN_M) + TURNED_PAD_M
    c, s = frame.cos, frame.sin
    # (col, row) -> local (-hx + col, hy - row) -> UTM
    transform = Affine(c, s, frame.e0 - c * hx - s * hy,
                       s, -c, frame.n0 - s * hx + c * hy)
    return 2 * hx, 2 * hy, transform


def fetch_lidarhd(lat, lon, size_km, folder, tif, width_km=None,
                  heading_deg=0.0, epsg=DEFAULT_EPSG):
    """WMS blocks covering the area in Lambert-93, one mosaic, warped
    onto the 1 m UTM grid of the area + margin (target_grid)."""
    width, height, transform = target_grid(lat, lon, size_km, width_km,
                                           heading_deg, epsg)
    utm = CRS.from_epsg(epsg)
    # the raster's outline in Lambert-93 (the grids are rotated)
    le, ln = outline(width, height, transform, utm, LAMB93)
    need = shapely.Polygon(np.column_stack([le, ln])).buffer(WMS_SLACK_M)
    x0 = math.floor(le.min()) - WMS_SLACK_M
    y0 = math.floor(ln.min()) - WMS_SLACK_M
    nx = math.ceil((le.max() + WMS_SLACK_M - x0) / BLOCK_M)
    ny = math.ceil((ln.max() + WMS_SLACK_M - y0) / BLOCK_M)
    blocks = folder / "blocks"
    blocks.mkdir(parents=True, exist_ok=True)
    print(f"blocks={nx * ny} ({nx}x{ny} of {BLOCK_M} m) "
          f"sw={x0},{y0} EPSG:2154, blocks away from the area skipped",
          flush=True)
    started = time.time()
    mosaic = np.full((ny * BLOCK_M, nx * BLOCK_M), np.nan, dtype=np.float32)
    k = 0
    for j in range(ny):
        for i in range(nx):
            k += 1
            e, n = x0 + i * BLOCK_M, y0 + j * BLOCK_M
            if not need.intersects(shapely.box(e, n, e + BLOCK_M,
                                               n + BLOCK_M)):
                print(f"[{k}/{nx * ny}] {e},{n} skipped", flush=True)
                continue
            dest = blocks / f"lidarhd_{e}_{n}_{BLOCK_M}.tif"
            fresh = fetch_block(e, n, dest)
            print(f"[{k}/{nx * ny}] {dest.name} "
                  f"{'fetched' if fresh else 'cached'}", flush=True)
            r0 = (ny - 1 - j) * BLOCK_M
            mosaic[r0:r0 + BLOCK_M, i * BLOCK_M:(i + 1) * BLOCK_M] = \
                read_block(dest)
    print(f"download_s={time.time() - started:.0f}", flush=True)

    out = np.full((height, width), np.nan, dtype=np.float32)
    rasterio.warp.reproject(
        mosaic, out, src_transform=from_origin(x0, y0 + ny * BLOCK_M, 1, 1),
        src_crs=LAMB93, src_nodata=np.nan, dst_transform=transform,
        dst_crs=utm, dst_nodata=np.nan,
        resampling=rasterio.warp.Resampling.bilinear)
    del mosaic
    write_warped(out, tif, transform, utm, started)


def outline(width, height, transform, src_crs, dst_crs):
    """The outline of a width x height raster, densified (41 points per
    side, the grids may be rotated), transformed to dst_crs."""
    t = np.linspace(0, 1, 41)
    cols = np.concatenate([width * t, np.full(41, width), width * (1 - t),
                           np.zeros(41)])
    rows = np.concatenate([np.full(41, height), height * (1 - t),
                           np.zeros(41), height * t])
    ring_e, ring_n = transform * (cols, rows)
    return Transformer.from_crs(src_crs, dst_crs, always_xy=True) \
        .transform(np.asarray(ring_e), np.asarray(ring_n))


def write_warped(out, tif, transform, utm, started):
    """The warped raster as tiled float32 GeoTIFF, NaN as no data."""
    height, width = out.shape
    tmp = tif.with_suffix(".tmp.tif")
    with rasterio.open(
            tmp, "w", driver="GTiff", width=width, height=height, count=1,
            dtype="float32", crs=utm, nodata=np.nan,
            transform=transform, tiled=True, blockxsize=512,
            blockysize=512, compress="deflate", predictor=3,
            BIGTIFF="IF_SAFER") as ds:
        ds.write(out, 1)
    tmp.replace(tif)
    nodata = int(np.count_nonzero(np.isnan(out)))
    print(f"warped size={width}x{height} nodata_cells={nodata} "
          f"min_m={np.nanmin(out):.1f} max_m={np.nanmax(out):.1f} "
          f"total_s={time.time() - started:.0f}", flush=True)


def fetch_gedtm30(lat, lon, size_km, folder, tif, width_km=None,
                  heading_deg=0.0, epsg=DEFAULT_EPSG):
    """The GEDTM30 window around the area (cached in lon/lat), warped
    onto the 1 m UTM grid of the area + margin (target_grid)."""
    width, height, transform = target_grid(lat, lon, size_km, width_km,
                                           heading_deg, epsg)
    utm = CRS.from_epsg(epsg)
    lo, la = outline(width, height, transform, utm, CRS.from_epsg(4326))
    w = math.floor((lo.min() - GEDTM30_SLACK_DEG) * 1e4) / 1e4
    s = math.floor((la.min() - GEDTM30_SLACK_DEG) * 1e4) / 1e4
    e = math.ceil((lo.max() + GEDTM30_SLACK_DEG) * 1e4) / 1e4
    n = math.ceil((la.max() + GEDTM30_SLACK_DEG) * 1e4) / 1e4
    src = folder / "src" / f"gedtm30_{w:.4f}_{s:.4f}_{e:.4f}_{n:.4f}.tif"
    started = time.time()
    if src.exists():
        print(f"{src.name} cached", flush=True)
    else:
        src.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(f"/vsicurl/{GEDTM30_URL}") as ds:
            window = rasterio.windows.from_bounds(w, s, e, n, ds.transform) \
                .round_offsets().round_lengths()
            data = ds.read(1, window=window).astype(np.float32, copy=False)
            data[~(np.abs(data) < 1e30)] = np.nan
            if ds.nodata is not None and abs(ds.nodata) < 1e30:
                data[data == ds.nodata] = np.nan
            profile = dict(driver="GTiff", width=data.shape[1],
                           height=data.shape[0], count=1, dtype="float32",
                           crs=ds.crs, nodata=np.nan,
                           transform=ds.window_transform(window),
                           compress="deflate", predictor=3)
        tmp = src.with_suffix(".tmp.tif")
        with rasterio.open(tmp, "w", **profile) as ds:
            ds.write(data, 1)
        tmp.replace(src)
        print(f"{src.name} fetched {data.shape[1]}x{data.shape[0]} cells "
              f"in {time.time() - started:.0f} s", flush=True)
    with rasterio.open(src) as ds:
        data = ds.read(1)
        src_transform, src_crs = ds.transform, ds.crs
    out = np.full((height, width), np.nan, dtype=np.float32)
    rasterio.warp.reproject(
        data, out, src_transform=src_transform, src_crs=src_crs,
        src_nodata=np.nan, dst_transform=transform, dst_crs=utm,
        dst_nodata=np.nan, resampling=rasterio.warp.Resampling.bilinear)
    write_warped(out, tif, transform, utm, started)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--center", required=True, help="lat,lon")
    ap.add_argument("--size", type=float, default=10.0,
                    help="km, the long side along the heading")
    ap.add_argument("--width", type=float,
                    help="km across the heading (default: --size)")
    ap.add_argument("--heading", type=float, default=0.0,
                    help="degrees counter-clockwise from east")
    ap.add_argument("--source", choices=SOURCES, default="dgm1")
    ap.add_argument("--epsg", type=int, default=DEFAULT_EPSG,
                    help="UTM zone of the raster (default ETRS89 / UTM 32N)")
    ap.add_argument("--out", type=Path, default=Path("data/raw"))
    ap.add_argument("--keep-zips", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="rebuild the GeoTIFF even if it exists")
    args = ap.parse_args()

    lat, lon = map(float, args.center.split(","))
    if args.source in WARPED:
        folder = args.out / args.source
        tif = folder / tif_name(lat, lon, args.size, args.source,
                                args.width, args.heading, args.epsg)
        if not tif.exists() or args.force:
            fetch = fetch_lidarhd if args.source == "lidarhd" \
                else fetch_gedtm30
            fetch(lat, lon, args.size, folder, tif, args.width,
                  args.heading, args.epsg)
        print(tif)
        return
    if args.epsg != DEFAULT_EPSG:
        raise FetchError("DGM1 is delivered in EPSG:25832 only")
    es, ns = zip_grid(Frame(lon, lat), args.size)
    km = area_km(es, ns)
    folder = args.out / "dgm1"
    tif = folder / tif_name(lat, lon, args.size)
    if tif.exists() and not args.force:
        print(tif)
        return
    folder.mkdir(parents=True, exist_ok=True)
    names = [f"dgm1_32_{e}_{n}_2_bw.zip" for e in es for n in ns]
    print(f"zips={len(names)} area={km} km "
          f"sw={es[0]},{ns[0]} km EPSG:25832", flush=True)
    started = time.time()
    for k, name in enumerate(names, 1):
        dest = folder / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"[{k}/{len(names)}] {name} cached", flush=True)
            continue
        download(URL.format(name), dest)
        print(f"[{k}/{len(names)}] {name} "
              f"{dest.stat().st_size / 1e6:.1f} MB", flush=True)
    print(f"download_s={time.time() - started:.0f}", flush=True)

    # downloaded archives are untrusted: unpack into their own folder
    work = folder / "xyz"
    work.mkdir(exist_ok=True)
    try:
        xyz = []
        for name in names:
            xyz += extract_xyz(folder / name, work)
        convert_xyz_to_geotiff(sorted(xyz), tif)
    finally:
        for p in work.glob("*.xyz"):
            p.unlink()
        work.rmdir()
    if not args.keep_zips:
        for name in names:
            (folder / name).unlink()
    print(tif)


if __name__ == "__main__":
    try:
        main()
    except (FetchError, TerrainError) as err:
        print(f"error: {err}", file=sys.stderr)
        sys.exit(2)
# - revised 2026-10-22 (tif_name() shared with world.py)
# - revised 2026-10-23 (LiDAR HD of the IGN as second source)
# - revised 2026-10-23 (rectangular, turned areas on a rotated grid)
# - revised 2026-10-27 (--epsg: UTM zone per recipe)
# - revised 2026-10-27 (GEDTM30 as third source)
