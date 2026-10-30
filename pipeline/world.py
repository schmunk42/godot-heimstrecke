# file generated with AI assistance: Claude Code - 2026-10-22 21:57:24 UTC
"""World recipe: the area, route and start points of a world.

A recipe (worlds/<id>/world.json, schema 1) describes a world in git;
build.py reads the center, size, horizon radius, route and starts from
it instead of from command-line flags. `route` and `starts` are file
names relative to the recipe's directory and may be omitted. `terrain`
names the source of the 1 m terrain model, "dgm1" (LGL
Baden-Wuerttemberg, the default), "lidarhd" (IGN, France) or "gedtm30"
(global, about 30 m, a substitute where no open 1 m model exists), see
fetch.py. `biome` sets the look of the landscape, "temperate" (the
default), "mediterranean" or "mediterranean-dry", see biome.py. `width_km` (default
`size_km`) and `heading_deg` (default 0, counter-clockwise from east)
make a rectangular world turned along a road: size_km is then the long
side along the heading, see frame.py. `tracks` (default none) lists the
OSM `tracktype` values of `highway=track` ways that are drivable roads in
this world, e.g. ["grade1", "grade2"] for the big forest and field
tracks, see extract.py and roads.py. `epsg` (default 25832, ETRS89 /
UTM 32N) names the UTM zone of the local frame and the terrain raster
for a world outside zone 32, see frame.py. Numbers
are returned as floats, so the build output does not depend on whether
the recipe writes 10 or 10.0.

manifest_fields() gives the recipe keys of the world.json manifest that
build.py writes and pack.py packages, so their order is defined here,
plus `data_licence` and `notice`: the tiles and tree files are licensed
under the ODbL as a whole (docs/licences.md), and the notice says so,
offers the pipeline to regenerate them (ODbL 4.6) and carries the
Copernicus liability sentence when Copernicus is a source.

`python pipeline/world.py vars [--raw DIR] <recipe>` prints the Make
variables of a world as KEY=value lines (area, raw input files and
download URL, route and starts), so the Makefile holds no area of its
own: CENTER, SIZE, WIDTH, HEADING, EPSG, BBOX, COP (the Copernicus tiles the horizon square
touches, centre tile first), TERRAIN_SOURCE and TERRAIN (the GeoTIFF
fetch.py writes), PBF,
PBF_GLOB, PBF_URL, ROUTE and STARTS (empty when the recipe has none) and
TRACKS (the tracktypes comma-separated, empty without tracks).
"""
import argparse
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from biome import BIOMES
from fetch import DEFAULT_EPSG, MARGIN_M, SOURCES, tif_name

SCHEMA = 1
# schema version of the world.json manifest (build.py, pack.py)
MANIFEST_SCHEMA = 1
REQUIRED = ("id", "name", "version", "min_game", "center", "size_km",
            "horizon_km", "bbox", "osm_region", "sources", "attribution")
ID_RE = re.compile(r"[a-z0-9-]+")
# version and min_game, as in worlds/world.schema.json
VERSION_RE = re.compile(r"[0-9]+(\.[0-9]+){0,2}")
SOURCE_KEYS = ("name", "licence", "url", "credit")
GEOFABRIK = "https://download.geofabrik.de/{}-latest.osm.pbf"
# the public repository with the pipeline and the recipes (ODbL 4.6 offer)
REPOSITORY = "https://github.com/schmunk42/godot-heimstrecke"
DATA_LICENCE = {
    "name": "ODbL 1.0",
    "url": "https://opendatacommons.org/licenses/odbl/1-0/",
    "covers": "the tiles and tree files of this world"}
NOTICE = ("This world contains data from OpenStreetMap "
          "(openstreetmap.org/copyright), available under the Open Database "
          "License; its tiles and tree files are licensed under the ODbL 1.0 "
          "as well (opendatacommons.org/licenses/odbl/1-0/). Terrain and "
          "horizon keep the licences of their sources. The pipeline, the "
          "recipe and the source extracts to regenerate this world are at "
          f"{REPOSITORY}.")
COPERNICUS_LIABILITY = (
    "The organisations in charge of the Copernicus programme by law or by "
    "delegation do not incur any liability for any use of the Copernicus "
    "WorldDEM-30.")
# OSM tracktype values a recipe may list under `tracks`
TRACKTYPES = ("grade1", "grade2", "grade3", "grade4", "grade5")
# UTM north zones a recipe may name under `epsg`: ETRS89 and WGS 84
UTM_EPSG = (range(25828, 25839), range(32601, 32661))
# rough degrees per km, enough to pick the 1-degree Copernicus tiles
KM_PER_DEG = 111.0


class RecipeError(RuntimeError):
    pass


@dataclass(frozen=True)
class Recipe:
    path: Path
    id: str
    name: str
    version: str
    min_game: str
    center: tuple  # (lat, lon)
    size_km: float
    horizon_km: float
    bbox: tuple  # (west, south, east, north)
    osm_region: str  # Geofabrik path, e.g. europe/germany/...
    route: Path | None
    starts: Path | None
    width_km: float  # across the heading, size_km for a square
    heading_deg: float
    terrain: str  # one of fetch.SOURCES
    biome: str  # one of biome.BIOMES
    tracks: tuple  # tracktypes of drivable highway=track ways, see TRACKTYPES
    epsg: int  # UTM zone of frame and terrain raster, see UTM_EPSG
    sources: tuple  # dicts with SOURCE_KEYS
    attribution: str


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _floats(path, data, key, n):
    value = data[key]
    if (not isinstance(value, list) or len(value) != n
            or not all(_number(v) for v in value)):
        raise RecipeError(f"{path}: {key} must be a list of {n} numbers")
    return tuple(float(v) for v in value)


def _positive(path, data, key):
    value = data[key]
    if not _number(value) or value <= 0:
        raise RecipeError(f"{path}: {key} must be a number > 0")
    return float(value)


def _version(path, data, key):
    value = data[key]
    if not isinstance(value, str) or not VERSION_RE.fullmatch(value):
        raise RecipeError(f"{path}: {key} must be a version string like "
                          f"\"1\" or \"0.1.0\", got {value!r}")
    return value


def _sources(path, data):
    value = data["sources"]
    if not isinstance(value, list) or not value or not all(
            isinstance(s, dict)
            and all(isinstance(s.get(k), str) for k in SOURCE_KEYS)
            for s in value):
        raise RecipeError(f"{path}: sources must be a non-empty list of "
                          f"objects with {', '.join(SOURCE_KEYS)}")
    return tuple(value)


def _file(path, data, key):
    name = data.get(key)
    if name is None:
        return None
    if not isinstance(name, str) or not name:
        raise RecipeError(f"{path}: {key} must be a file name")
    return (path.parent / name).resolve()


def load_recipe(path):
    """Reads and checks the recipe at `path`; raises RecipeError."""
    if not Path(path).is_file():
        raise RecipeError(f"recipe {path} not found")
    path = Path(path).resolve()
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as err:
        raise RecipeError(f"{path}: invalid JSON ({err})") from None
    if not isinstance(data, dict):
        raise RecipeError(f"{path}: recipe must be a JSON object")
    if data.get("schema") != SCHEMA:
        raise RecipeError(f"{path}: schema must be {SCHEMA}, "
                          f"got {data.get('schema')!r}")
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise RecipeError(f"{path}: missing keys {', '.join(missing)}")
    if not isinstance(data["id"], str) or not ID_RE.fullmatch(data["id"]):
        raise RecipeError(f"{path}: id must match [a-z0-9-]+, "
                          f"got {data['id']!r}")
    region = data["osm_region"]
    if (not isinstance(region, str) or not region
            or region.startswith("/") or region.endswith("/")):
        raise RecipeError(f"{path}: osm_region must be a Geofabrik path "
                          "like europe/germany/bremen")
    terrain = data.get("terrain", "dgm1")
    if terrain not in SOURCES:
        raise RecipeError(f"{path}: terrain must be one of "
                          f"{', '.join(SOURCES)}, got {terrain!r}")
    biome = data.get("biome", "temperate")
    if biome not in BIOMES:
        raise RecipeError(f"{path}: biome must be one of "
                          f"{', '.join(BIOMES)}, got {biome!r}")
    tracks = data.get("tracks", [])
    if (not isinstance(tracks, list)
            or any(t not in TRACKTYPES for t in tracks)
            or len(set(tracks)) != len(tracks)):
        raise RecipeError(f"{path}: tracks must be a list of distinct "
                          f"values of {', '.join(TRACKTYPES)}, "
                          f"got {tracks!r}")
    width_km = _positive(path, data, "width_km") if "width_km" in data \
        else _positive(path, data, "size_km")
    heading = data.get("heading_deg", 0.0)
    if not _number(heading) or not -90.0 <= heading <= 90.0:
        raise RecipeError(f"{path}: heading_deg must be a number in "
                          f"[-90, 90], got {heading!r}")
    epsg = data.get("epsg", DEFAULT_EPSG)
    if (not isinstance(epsg, int) or isinstance(epsg, bool)
            or not any(epsg in r for r in UTM_EPSG)):
        raise RecipeError(f"{path}: epsg must be a UTM north zone "
                          "(25828-25838 or 32601-32660), "
                          f"got {epsg!r}")
    attribution = data["attribution"]
    if not isinstance(attribution, str) or not attribution:
        raise RecipeError(f"{path}: attribution must be a non-empty string")
    return Recipe(path=path, id=data["id"], name=data["name"],
                  version=_version(path, data, "version"),
                  min_game=_version(path, data, "min_game"),
                  center=_floats(path, data, "center", 2),
                  size_km=_positive(path, data, "size_km"),
                  horizon_km=_positive(path, data, "horizon_km"),
                  bbox=_floats(path, data, "bbox", 4),
                  osm_region=region,
                  route=_file(path, data, "route"),
                  starts=_file(path, data, "starts"),
                  width_km=width_km, heading_deg=float(heading),
                  terrain=terrain, biome=biome,
                  tracks=tuple(sorted(tracks)), epsg=epsg,
                  sources=_sources(path, data),
                  attribution=attribution)


def manifest_fields(recipe):
    """The recipe's keys of the world.json manifest: (head, tail).

    head goes first (schema, id, name, version, min_game), the build keys
    follow, tail (sources, attribution, data_licence, notice) goes
    last."""
    head = {"schema": MANIFEST_SCHEMA, "id": recipe.id,
            "name": recipe.name, "version": recipe.version,
            "min_game": recipe.min_game}
    notice = NOTICE
    if any(s["name"].startswith("Copernicus") for s in recipe.sources):
        notice += " " + COPERNICUS_LIABILITY
    tail = {"sources": [dict(s) for s in recipe.sources],
            "attribution": recipe.attribution,
            "data_licence": dict(DATA_LICENCE), "notice": notice}
    return head, tail


def _num(value):
    """Shortest form of a number for Make: 10.0 -> 10, 48.79 -> 48.79."""
    return repr(float(value)).removesuffix(".0")


def _cell(lat, lon):
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"cop30_{ns}{abs(lat):02d}_{ew}{abs(lon):03d}.tif"


def cop_tiles(recipe):
    """Copernicus tiles the horizon square (plus the DGM1 margin) touches,
    the centre tile first (the build merges them in this order)."""
    lat, lon = recipe.center
    r_km = recipe.horizon_km / 2 + MARGIN_M / 1000
    if recipe.heading_deg:
        # the turned horizon square reaches farther along the diagonal
        r_km *= math.sqrt(2)
    d_lat = r_km / KM_PER_DEG
    d_lon = r_km / (KM_PER_DEG * math.cos(math.radians(lat)))
    centre = (math.floor(lat), math.floor(lon))
    cells = [(a, o)
             for a in range(math.floor(lat - d_lat),
                            math.floor(lat + d_lat) + 1)
             for o in range(math.floor(lon - d_lon),
                            math.floor(lon + d_lon) + 1)]
    cells.sort(key=lambda c: (c != centre, abs(c[0] - centre[0])
                              + abs(c[1] - centre[1]), c))
    return [_cell(a, o) for a, o in cells]


def make_vars(recipe, raw):
    """The Make variables of a world, in output order."""
    lat, lon = recipe.center
    region = recipe.osm_region.rsplit("/", 1)[-1]
    raw = raw.rstrip("/")

    def rel(p):
        return os.path.relpath(p) if p else ""

    return {
        "CENTER": f"{_num(lat)},{_num(lon)}",
        "SIZE": _num(recipe.size_km),
        "WIDTH": _num(recipe.width_km),
        "HEADING": _num(recipe.heading_deg),
        "EPSG": str(recipe.epsg),
        "BBOX": ",".join(_num(v) for v in recipe.bbox),
        "COP": " ".join(f"{raw}/{t}" for t in cop_tiles(recipe)),
        "TERRAIN_SOURCE": recipe.terrain,
        "TERRAIN": f"{raw}/{recipe.terrain}/"
                   f"{tif_name(lat, lon, recipe.size_km, recipe.terrain,
                               recipe.width_km, recipe.heading_deg,
                               recipe.epsg)}",
        "PBF": f"{raw}/{region}-latest.osm.pbf",
        "PBF_GLOB": f"{raw}/{region}*.osm.pbf",
        "PBF_URL": GEOFABRIK.format(recipe.osm_region),
        "ROUTE": rel(recipe.route),
        "STARTS": rel(recipe.starts),
        "TRACKS": ",".join(recipe.tracks)}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    v = sub.add_parser("vars", help="print the Make variables of a world")
    v.add_argument("recipe", type=Path)
    v.add_argument("--raw", default="data/raw",
                   help="directory of the downloaded inputs")
    args = ap.parse_args()
    for key, value in make_vars(load_recipe(args.recipe), args.raw).items():
        print(f"{key}={value}")


if __name__ == "__main__":
    try:
        main()
    except RecipeError as err:
        print(f"error: {err}", file=sys.stderr)
        sys.exit(2)
# - revised 2026-10-22 (vars command for the Makefile)
# - revised 2026-10-22 (manifest fields for build.py and pack.py)
# - revised 2026-10-23 (terrain source per recipe)
# - revised 2026-10-23 (biome per recipe)
# - revised 2026-10-23 (width_km and heading_deg)
# - revised 2026-10-25 (data_licence and notice in the manifest)
# - revised 2026-10-27 (epsg)
# - revised 2026-10-27 (terrain gedtm30)
# - revised 2026-10-27 (biome mediterranean-dry)
