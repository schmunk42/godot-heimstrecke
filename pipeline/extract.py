# file generated with AI assistance: Claude Code - 2026-10-20 18:30:00 UTC
"""Stage 1: pull roads, land cover, buildings, trees and coastlines for a
bbox out of a PBF.

One pass over the regional extract is slow in Python, so the result is
cached as a pickle and later stages only read that.

`--tracks grade1,grade2` also keeps the `highway=track` ways of these
tracktypes as roads (the recipe key `tracks`, see world.py), and the
plain `highway=service` ways (no `service=*` subtype, so no car park
aisle or driveway) that share a node with such a track and with another
kept road: in OSM a forest track often meets the road only through a
short service way. Without --tracks no track and no service way is kept.
"""
import argparse
import pickle
import time
from pathlib import Path

import osmium
import shapely

ROAD_CLASSES = {
    "motorway", "motorway_link", "trunk", "trunk_link",
    "primary", "primary_link", "secondary", "secondary_link",
    "tertiary", "tertiary_link", "unclassified", "residential",
    "living_street",
}
ROAD_TAGS = ("highway", "tracktype", "surface", "lanes", "width", "bridge",
             "tunnel", "covered",
             "layer", "oneway", "name", "ref", "access", "motor_vehicle",
             "vehicle", "junction", "sidewalk", "sidewalk:left",
             "sidewalk:right", "sidewalk:both",
             # signposts (signs.py)
             "destination", "destination:forward", "destination:backward",
             "destination:ref", "destination:ref:forward",
             "destination:ref:backward", "destination:ref:to",
             "destination:ref:to:forward", "destination:ref:to:backward",
             "destination:lanes", "destination:ref:lanes")
AREA_KEYS = ("building", "landuse", "natural", "leisure", "water",
             "waterway", "amenity")
BUILDING_TAGS = ("building", "building:levels", "height", "roof:shape")
# coastline ways are kept if they come this close to the bbox (degrees,
# about 2 km): the build cuts the larger terrain raster along them, and a
# coastline ending inside it would leave land and sea in one piece
COAST_PAD_DEG = 0.02
# named places for the plain direction signs (signs.py), also beyond the
# bbox: a sign names the next town in a direction
PLACE_KINDS = ("city", "town", "village")
# name variants of a place, for the bilingual signs (signs.py, Cyprus)
PLACE_NAMES = ("name:el", "name:en", "name:el-Latn", "int_name",
               "alt_name", "official_name", "name:tr")
# town entry signs (Ortstafel, panneau d'entrée) on the roads, for signs.py
TOWN_SIGNS = ("city_limit", "DE:310", "FR:EB10")
PLACE_PAD_DEG = 0.5
# single trees (nodes) and tree rows (ways), for trees.py
TREE_TAGS = ("leaf_type", "leaf_cycle", "genus", "height")


def underground(tags):
    """A building below ground (station halls, garages, a mezzanine
    under a junction): location=underground, tunnel=yes, a negative
    layer, or levels that all lie below 0; drawn from the ground up they
    would stand on the road. location=surface always counts as above
    ground, and a building with level -1;0 reaches the ground floor."""
    if tags.get("location") == "surface":
        return False
    if tags.get("location") == "underground" or tags.get("tunnel") == "yes":
        return True
    try:
        if float(tags.get("layer", "0")) < 0:
            return True
        levels = [float(v) for v in str(tags.get("level", "0")).split(";")]
    except ValueError:
        return False
    return max(levels) < 0


def classify_area(tags):
    if "building" in tags:
        return None if underground(tags) else "building"
    landuse = tags.get("landuse")
    natural = tags.get("natural")
    leisure = tags.get("leisure")
    if natural == "water" or "water" in tags or landuse == "reservoir" \
            or tags.get("waterway") == "riverbank":
        return "water"
    if natural in ("bare_rock", "rock", "stone", "scree", "cliff"):
        return "rock"
    if natural in ("beach", "sand", "shingle"):
        return "sand"
    if natural == "wood" or landuse == "forest":
        return "forest"
    if landuse in ("vineyard", "orchard", "farmland", "allotments",
                   "plant_nursery"):
        return "farmland"
    if landuse in ("grass", "meadow", "recreation_ground", "cemetery",
                   "village_green") \
            or natural == "grassland" \
            or leisure in ("park", "garden", "pitch", "golf_course",
                           "stadium", "sports_centre"):
        return "green"
    if natural in ("scrub", "heath"):
        return "scrub"
    if landuse in ("residential", "commercial", "industrial", "retail",
                   "railway", "construction"):
        return "urban"
    return None


def links_only(roads):
    """Drop the service ways that do not link a track to another road."""
    track_nodes, other_nodes = set(), set()
    for r in roads:
        hw = r["tags"]["highway"]
        if hw == "track":
            track_nodes.update(r["nodes"])
        elif hw != "service":
            other_nodes.update(r["nodes"])
    return [r for r in roads if r["tags"]["highway"] != "service"
            or (track_nodes.intersection(r["nodes"])
                and other_nodes.intersection(r["nodes"]))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pbf", type=Path)
    ap.add_argument("--bbox", required=True,
                    help="min_lon,min_lat,max_lon,max_lat")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tracks", default="",
                    help="tracktypes of highway=track ways kept as roads, "
                         "comma-separated (grade1,grade2)")
    args = ap.parse_args()
    tracks = set(filter(None, args.tracks.split(",")))

    min_lon, min_lat, max_lon, max_lat = map(float, args.bbox.split(","))
    box = shapely.box(min_lon, min_lat, max_lon, max_lat)
    wkb = osmium.geom.WKBFactory()

    def in_box(nodes):
        for n in nodes:
            loc = n.location
            if loc.valid() and min_lon <= loc.lon <= max_lon \
                    and min_lat <= loc.lat <= max_lat:
                return True
        return False

    roads, areas, trees, tree_rows, coastlines = [], [], [], [], []
    places, town_signs = [], []
    near = box.buffer(PLACE_PAD_DEG)
    started = time.time()
    fp = (osmium.FileProcessor(args.pbf)
          .with_areas(osmium.filter.KeyFilter(*AREA_KEYS))
          .with_filter(osmium.filter.EntityFilter(
              osmium.osm.NODE | osmium.osm.WAY | osmium.osm.AREA))
          .with_filter(osmium.filter.KeyFilter(
              "highway", "place", "traffic_sign", *AREA_KEYS)))

    for obj in fp:
        if obj.is_node():
            loc = obj.location
            sign = obj.tags.get("traffic_sign", "")
            if any(t in sign for t in TOWN_SIGNS) and loc.valid() \
                    and min_lon <= loc.lon <= max_lon \
                    and min_lat <= loc.lat <= max_lat:
                town_signs.append({
                    "name": obj.tags.get("name", ""),
                    "city_limit": obj.tags.get("city_limit", ""),
                    "lonlat": (loc.lon, loc.lat)})
                continue
            if obj.tags.get("place") in PLACE_KINDS and "name" in obj.tags \
                    and loc.valid() and near.contains(
                        shapely.Point(loc.lon, loc.lat)):
                places.append({"name": obj.tags["name"],
                               "place": obj.tags["place"],
                               "lonlat": (loc.lon, loc.lat),
                               "names": {k: obj.tags[k] for k in PLACE_NAMES
                                         if k in obj.tags}})
                continue
            if obj.tags.get("natural") == "tree" and loc.valid() \
                    and min_lon <= loc.lon <= max_lon \
                    and min_lat <= loc.lat <= max_lat:
                tags = {k: obj.tags[k] for k in TREE_TAGS if k in obj.tags}
                trees.append({"id": obj.id, "tags": tags,
                              "lonlat": (loc.lon, loc.lat)})
            continue
        if obj.is_way() and obj.tags.get("natural") == "tree_row":
            if in_box(obj.nodes):
                try:
                    line = shapely.from_wkb(wkb.create_linestring(obj))
                except osmium.InvalidLocationError:
                    continue
                tags = {k: obj.tags[k] for k in TREE_TAGS if k in obj.tags}
                tree_rows.append({"id": obj.id, "tags": tags,
                                  "geom": line.wkb})
            continue
        if obj.is_way() and obj.tags.get("natural") == "coastline":
            # whole ways near the bbox, for sea.py; no node of a long way
            # may lie inside it
            try:
                line = shapely.from_wkb(wkb.create_linestring(obj))
            except osmium.InvalidLocationError:
                continue
            if line.intersects(box.buffer(COAST_PAD_DEG)):
                coastlines.append({"id": obj.id, "geom": line.wkb})
            continue
        if obj.is_way():
            highway = obj.tags.get("highway")
            if highway == "track":
                if obj.tags.get("tracktype") not in tracks:
                    continue
            elif highway == "service":
                if not tracks or "service" in obj.tags:
                    continue
            elif highway not in ROAD_CLASSES:
                continue
            if obj.tags.get("area") == "yes":
                continue
            if not in_box(obj.nodes):
                continue
            try:
                line = shapely.from_wkb(wkb.create_linestring(obj))
            except osmium.InvalidLocationError:
                continue
            # one OSM node id per linestring vertex, for the road graph
            nodes = [n.ref for n in obj.nodes]
            if len(nodes) != len(shapely.get_coordinates(line)):
                continue
            tags = {k: obj.tags[k] for k in ROAD_TAGS if k in obj.tags}
            roads.append({"id": obj.id, "tags": tags, "nodes": nodes,
                          "geom": line.wkb})
        elif obj.is_area():
            kind = classify_area(obj.tags)
            if kind is None:
                continue
            try:
                geom = shapely.from_wkb(wkb.create_multipolygon(obj))
            except (osmium.InvalidLocationError, RuntimeError):
                continue
            if not geom.intersects(box):
                continue
            tags = {}
            if kind == "building":
                tags = {k: obj.tags[k] for k in BUILDING_TAGS
                        if k in obj.tags}
            elif kind == "forest":
                tags = {k: obj.tags[k] for k in TREE_TAGS[:2]
                        if k in obj.tags}
            areas.append({"id": obj.id, "kind": kind, "tags": tags,
                          "from_way": obj.from_way(), "geom": geom.wkb})

    if tracks:
        roads = links_only(roads)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("wb") as fh:
        # build.py refuses an extract made with another tag list
        pickle.dump({"bbox": (min_lon, min_lat, max_lon, max_lat),
                     "road_tags": ROAD_TAGS, "roads": roads,
                     "areas": areas, "trees": trees,
                     "tree_rows": tree_rows, "coastlines": coastlines,
                     "places": places, "town_signs": town_signs},
                    fh)

    counts = {}
    for a in areas:
        counts[a["kind"]] = counts.get(a["kind"], 0) + 1
    relations = sum(1 for a in areas if not a["from_way"])
    print(f"roads={len(roads)} areas={counts} trees={len(trees)} "
          f"tree_rows={len(tree_rows)} coastlines={len(coastlines)} "
          f"places={len(places)} town_signs={len(town_signs)} "
          f"from_relations={relations} "
          f"seconds={time.time() - started:.0f}")


if __name__ == "__main__":
    main()
# - revised 2026-10-23 (coastline ways for the sea)
# - revised 2026-10-23 (rock, sand and scrub as their own cover kinds)
# - revised 2026-10-23 (no underground buildings)
# - revised 2026-10-23 (destination tags and places for signs)
# - revised 2026-10-25 (town entry sign nodes)
# - revised 2026-10-25 (tracks and the service ways linking them)
# - revised 2026-10-27 (name variants of places)
