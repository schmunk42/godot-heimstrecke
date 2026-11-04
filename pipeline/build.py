# file generated with AI assistance: Claude Code - 2026-10-20 18:35:00 UTC
"""Stage 2: turn the cached extract plus DGM1 into 1 km glTF tiles.

Local frame: see frame.py. Roads take their heights from DGM1
(terrain.Dgm1Raster), the route from the drawn road surface; terrain
and buildings from DGM1 conformed to the roads (conform.py), trees on
it (trees.py, own files beside the tiles); bridges get
decks lifted over the roads below them (bridges.py), tunnels tubes and
portal cuts (tunnels.py), each in their own layer; Copernicus
(LonLatDem) only draws the horizon ring, offset by the same base height
so the two meet. A world on the coast gets its sea from the OSM
coastline (sea.py): the terrain there lies at 0 m and is coloured as
water, like the horizon vertices at 0 m. The recipe's biome (biome.py)
overrides the land cover and horizon colours, paints rock and picks the
tree kinds.
"""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import mapbox_earcut
import numpy as np
import shapely
import trimesh

from biome import (FACADES, FLAT_ROOFED, GROUND_FLOOR_M, HOUSE_KINDS,
                   ISOLATED_M, ISOLATED_NEIGHBOURS, PITCHED, PLINTH_M, ROOF,
                   STOREY_M, STOREYS, ground_shade, palette, rock_share)
from bridges import (DECK_DEPTH, build_decks, bridge_report, classify,
                     deck_half, normals, raise_decks, segment_index)
from clipping import check_clipping, write_viewpoints
from conform import conform
from extract import ROAD_TAGS
from fetch import MARGIN_M
from frame import Frame, xyz
from metrics import CLIPPING_BASELINE, HARD_GATES, write_metrics
from roads import ROAD_STEP, build_road_network, emit_network
from sea import SHORE_M, coastlines, horizon_water, sea_polygon
from water import Water
from signs import country_of, write_signs
from markings import emit_markings
from sidewalks import assign as assign_sidewalks, emit_sidewalks
from skirts import emit_skirts
from starts import StartError, build_starts
from terrain import Dgm1Raster, LonLatDem, TerrainError
from trees import build_trees, emit_trees
from tunnels import build_tunnels, cut_mesh
from world import RecipeError, load_recipe, manifest_fields

TILE = 1000.0
TERRAIN_STEP = 10.0
# DGM1 must cover the playable square plus this margin; roads are clipped
# to it (more than half the smoothing window, so tiles are unaffected)
DGM1_MARGIN = MARGIN_M
HORIZON_STEP = 200.0
# a building part under a road (a deck or a raised strip) ends this far
# below the road surface, a deck's underside included; a road counts as
# over a building when its surface is UNDER_ROAD_M above the building's
# floor, so footprints that only touch a street at their own level stay
BUILDING_CLEAR_M = 1.0
UNDER_ROAD_M = 2.0
# a capped part lower than this is left out
MIN_PART_M = 2.5
# a footprint with at least this share under roads is capped as a whole
UNDER_SHARE = 0.5
# the horizon sinks this far under the playable area, which the tiles
# cover: Copernicus is a surface model (forest canopy included) on a
# 200 m grid, and in steep wooded valleys (Bavella) a triangle from ridge
# to ridge lay more than the former 30 m above the road in between
HORIZON_SINK_M = 400.0
# the sea reaches this far beyond the horizon square (camera far 40 km)
HORIZON_SEA_M = 25000.0

COLORS = {
    "default": (0.55, 0.66, 0.38),
    "urban": (0.62, 0.60, 0.56),
    "green": (0.45, 0.68, 0.33),
    "farmland": (0.70, 0.68, 0.40),
    "forest": (0.18, 0.38, 0.17),
    "water": (0.25, 0.45, 0.70),
    "road": (0.24, 0.24, 0.26),
    "road_major": (0.30, 0.30, 0.33),
    "gravel": (0.50, 0.46, 0.39),
    "bank": (0.68, 0.66, 0.60),
    "sidewalk": (0.58, 0.58, 0.56),
    "kerb": (0.66, 0.66, 0.64),
    "marking": (0.86, 0.86, 0.82),
    "route": (0.85, 0.15, 0.12),
    "horizon": (0.42, 0.52, 0.36),
}
# later entries win when land cover polygons overlap; a kind without a
# colour in the biome's palette is not painted (biome.py)
COVER_ORDER = ("urban", "farmland", "green", "scrub", "forest", "sand",
               "rock", "water")
# mesh layers of a tile (glTF node names)
LAYERS = ("terrain", "roads", "buildings", "tunnels", "bridges",
          "markings", "verges", "water")


class InputError(RuntimeError):
    pass


def grid_mesh(x0, y0, size, step, dem, base):
    n = int(round(size / step)) + 1
    xs, ys = np.meshgrid(np.linspace(x0, x0 + size, n),
                         np.linspace(y0, y0 + size, n))
    xs, ys = xs.ravel(), ys.ravel()
    hs = dem.height(xs, ys) - base
    faces = []
    for r in range(n - 1):
        for c in range(n - 1):
            a = r * n + c
            # counter-clockwise in map coordinates = normal points up
            faces.append((a, a + 1, a + n))
            faces.append((a + 1, a + n + 1, a + n))
    return xs, ys, hs, np.array(faces)


def extrude(poly, bottom, top):
    """Flat-shaded prism: unshared vertices so walls stay crisp."""
    # exterior CCW, holes CW: walls then face outward walking p -> q
    poly = shapely.orient_polygons(poly)
    rings = [np.asarray(poly.exterior.coords)[:-1]]
    rings += [np.asarray(r.coords)[:-1] for r in poly.interiors]
    verts, faces = [], []
    flat = np.vstack(rings)
    ends = np.cumsum([len(r) for r in rings])
    tri = mapbox_earcut.triangulate_float64(flat, ends.astype(np.uint32))
    roof = xyz(flat[:, 0], np.full(len(flat), top), flat[:, 1])
    verts.append(roof)
    for a, b, c in tri.reshape(-1, 3):
        ab, ac = flat[b] - flat[a], flat[c] - flat[a]
        if ab[0] * ac[1] - ab[1] * ac[0] < 0:
            b, c = c, b
        faces.append((a, b, c))
    offset = len(flat)
    for ring in rings:
        nxt = np.roll(ring, -1, axis=0)
        for p, q in zip(ring, nxt):
            quad = np.array([[p[0], bottom, -p[1]], [q[0], bottom, -q[1]],
                             [q[0], top, -q[1]], [p[0], top, -p[1]]])
            verts.append(quad)
            o = offset
            faces.append((o, o + 1, o + 2))
            faces.append((o, o + 2, o + 3))
            offset += 4
    return np.vstack(verts), faces


def hip_roof(poly, top, pitch, eave):
    """Hipped roof over the oriented envelope of poly, grown by eave: the
    four planes pass through the envelope's edges at top, rise at pitch
    (rise over run) to a ridge along the long side and end eave beyond
    the walls, lower by eave * pitch (a pyramid on a square). Each plane
    has its own vertices and both windings, since the overhang is seen
    from below. Vertices and faces like extrude()."""
    env = np.asarray(shapely.oriented_envelope(poly).exterior.coords)[:4]
    if np.hypot(*(env[1] - env[0])) < np.hypot(*(env[2] - env[1])):
        env = np.roll(env, -1, axis=0)
    long, wide = env[1] - env[0], env[2] - env[1]
    length, width = np.hypot(*long), np.hypot(*wide)
    u, v = long / length, wide / width
    corners = np.array([env[0] - (u + v) * eave, env[1] + (u - v) * eave,
                        env[2] + (u + v) * eave, env[3] - (u - v) * eave])
    inset = u * min(width / 2, length / 2)
    ridge = np.array([(env[0] + env[3]) / 2 + inset,
                      (env[1] + env[2]) / 2 - inset])
    low, high = top - eave * pitch, top + width / 2 * pitch
    c0, c1, c2, c3 = ((*c, low) for c in corners)
    r0, r1 = ((*r, high) for r in ridge)
    planes = [(c0, c1, r1, r0), (c2, c3, r0, r1), (c3, c0, r0), (c1, c2, r1)]
    verts, faces, offset = [], [], 0
    for plane in planes:
        pts = np.array(plane)
        if len(pts) == 4 and np.allclose(pts[2], pts[3]):
            pts = pts[:3]
        tris = [(0, k, k + 1) for k in range(1, len(pts) - 1)]
        ab, ac = pts[1, :2] - pts[0, :2], pts[2, :2] - pts[0, :2]
        if ab[0] * ac[1] - ab[1] * ac[0] < 0:
            tris = [(a, c, b) for a, b, c in tris]
        for side in (tris, [(a, c, b) for a, b, c in tris]):
            verts.append(xyz(pts[:, 0], pts[:, 2], pts[:, 1]))
            faces += [(a + offset, b + offset, c + offset)
                      for a, b, c in side]
            offset += len(pts)
    return np.vstack(verts), faces


def building_height(tags):
    for key in ("height",):
        try:
            return float(tags[key].split()[0])
        except (KeyError, ValueError):
            pass
    try:
        return float(tags["building:levels"]) * 3.0 + 1.0
    except (KeyError, ValueError):
        pass
    return {"house": 7.0, "garage": 3.0, "garages": 3.0, "shed": 3.0,
            "apartments": 14.0, "commercial": 15.0, "office": 18.0,
            "industrial": 10.0, "church": 20.0}.get(tags.get("building"),
                                                     9.0)


class Bucket:
    """Collects vertices/faces/colors for one mesh layer."""

    def __init__(self):
        self.v, self.f, self.c, self.n = [], [], [], 0

    def add(self, verts, faces, color):
        self.v.append(verts)
        self.f.append(np.asarray(faces) + self.n)
        col = np.broadcast_to(np.asarray(color), (len(verts), 3))
        self.c.append(col)
        self.n += len(verts)

    def mesh(self):
        if not self.v:
            return None
        colors = (np.vstack(self.c) * 255).astype(np.uint8)
        return trimesh.Trimesh(
            vertices=np.vstack(self.v), faces=np.vstack(self.f),
            vertex_colors=np.column_stack([colors,
                                           np.full(len(colors), 255)]),
            process=False)


class Tiles:
    """The playable rectangle (size_km along local X, width_km along Y,
    a square without width_km) cut into TILE x TILE buckets. half is
    the pair of half sides [hx, hy]; every consumer unpacks it with
    np.broadcast_to(half, 2), so a scalar still works."""

    def __init__(self, size_km, width_km=None):
        width_km = size_km if width_km is None else width_km
        self.half = np.array([size_km * 500.0, width_km * 500.0])
        self.nx = int(round(size_km * 1000 / TILE))
        self.ny = int(round(width_km * 1000 / TILE))
        self.buckets = {(i, j): {layer: Bucket() for layer in LAYERS}
                        for i in range(self.nx) for j in range(self.ny)}

    def of(self, x, y):
        i = int((x + self.half[0]) // TILE)
        j = int((y + self.half[1]) // TILE)
        if 0 <= i < self.nx and 0 <= j < self.ny:
            return i, j
        return None

    def keys(self, x, y):
        """Vectorised of() as one integer key per point, -1 outside."""
        i = np.floor((np.asarray(x) + self.half[0]) / TILE).astype(int)
        j = np.floor((np.asarray(y) + self.half[1]) / TILE).astype(int)
        ok = (i >= 0) & (i < self.nx) & (j >= 0) & (j < self.ny)
        return np.where(ok, i * self.ny + j, -1)

    def bucket(self, key):
        """The layer buckets of the tile with key (from keys())."""
        return self.buckets[divmod(int(key), self.ny)]


def load_extract(path):
    with path.open("rb") as fh:
        ex = pickle.load(fh)
    if not all("nodes" in r for r in ex["roads"]):
        raise InputError(f"{path}: extract is in the old format, "
                         "re-run pipeline/extract.py")
    if tuple(ex.get("road_tags", ())) != ROAD_TAGS:
        raise InputError(f"{path}: extract was made with different road "
                         "tags, re-run pipeline/extract.py")
    if "trees" not in ex or "tree_rows" not in ex:
        raise InputError(f"{path}: extract has no trees, "
                         "re-run pipeline/extract.py")
    if "coastlines" not in ex:
        raise InputError(f"{path}: extract has no coastlines, "
                         "re-run pipeline/extract.py")
    if "places" not in ex or "town_signs" not in ex:
        raise InputError(f"{path}: extract has no places or town signs, "
                         "re-run pipeline/extract.py")
    return ex


def add_sea(ex, frame, dem):
    """Sea polygon over the raster (sea.py), filled into dem; None if
    the area has no coastline."""
    sea = sea_polygon(coastlines(ex, frame), dem.footprint())
    if sea is None:
        return None, {"coastlines": len(ex["coastlines"])}
    inside, shore = dem.fill_sea(sea, SHORE_M)
    return sea, {"coastlines": len(ex["coastlines"]),
                 "sea_km2": round(sea.area / 1e6, 2),
                 "sea_cells": inside, "shore_cells_filled": shore}


def split_areas(ex, frame, sea=None):
    """Land cover unions per kind (prepared) and building footprints;
    the sea counts as water."""
    cover = {k: [] for k in COVER_ORDER}
    buildings = []
    for a in ex["areas"]:
        geom = frame.geom_to_local(shapely.from_wkb(a["geom"]))
        if a["kind"] == "building":
            buildings.append((geom, a["tags"]))
        else:
            cover[a["kind"]].append(geom)
    if sea is not None:
        cover["water"].append(sea)
    cover = {k: shapely.make_valid(shapely.union_all(v)) if v else None
             for k, v in cover.items()}
    for g in cover.values():
        if g is not None:
            shapely.prepare(g)
    return cover, buildings


def inland_water(ex, frame, half):
    """Union of the OSM water areas (not the sea) within the playable
    rectangle of half sides `half` (the raster ends DGM1_MARGIN beyond
    it), local metres, or None."""
    parts = [frame.geom_to_local(shapely.from_wkb(a["geom"]))
             for a in ex["areas"] if a["kind"] == "water"]
    if not parts:
        return None
    hx, hy = np.broadcast_to(half, 2)
    water = shapely.intersection(shapely.make_valid(shapely.union_all(
        parts)), shapely.box(-hx, -hy, hx, hy))
    return None if water.is_empty else water


def build_terrain(tiles, cover, dem, base, cut=None, colors_of=COLORS,
                  biome="temperate", inland=None):
    """One grid per tile, coloured by land cover (colors_of, the biome's
    palette) and rock (biome.rock_share, not on water), minus the cut.
    With `inland` (water.Water) the inland water gets its bed carved into
    the grid and its surface into the tile's water layer.

    Returns the numbers of terrain triangles clipped and removed by the
    cut (the portal slots of tunnels.py).
    """
    clipped = removed = 0
    for (i, j), b in tiles.buckets.items():
        x0, y0 = -tiles.half[0] + i * TILE, -tiles.half[1] + j * TILE
        xs, ys, hs, faces = grid_mesh(x0, y0, TILE, TERRAIN_STEP, dem, base)
        colors = np.tile(colors_of["default"], (len(xs), 1))
        water = np.zeros(len(xs), dtype=bool)
        for kind in COVER_ORDER:
            g = cover[kind]
            if g is not None and kind in colors_of:
                mask = shapely.contains_xy(g, xs, ys)
                colors[mask] = colors_of[kind]
                if kind == "water":
                    water = mask
        if "rock" in colors_of:
            n = int(round(TILE / TERRAIN_STEP)) + 1
            gy, gx = np.gradient(hs.reshape(n, n), TERRAIN_STEP)
            slope = np.hypot(gx, gy).ravel()
            shade = ground_shade(biome, xs, ys, slope)
            shade[water] = 1.0
            colors = colors * shade[:, None]
            share = rock_share(biome, hs + base, slope)[:, None]
            share[water] = 0.0
            colors = colors * (1 - share) \
                + np.asarray(colors_of["rock"]) * share
        if inland is not None:
            inland.carve(xs, ys, hs, colors, COLORS["gravel"])
            top = inland.surface(xs, ys, faces)
            if top is not None:
                wx, wy, wh, wf = top
                b["water"].add(xyz(wx, wh, wy), wf, COLORS["water"])
        if cut is not None and shapely.intersects(
                cut, shapely.box(x0, y0, x0 + TILE, y0 + TILE)):
            xs, ys, hs, faces, colors, c, r = cut_mesh(xs, ys, hs, faces,
                                                       colors, cut)
            clipped, removed = clipped + c, removed + r
        b["terrain"].v.append(xyz(xs, hs, ys))
        b["terrain"].f.append(faces)
        b["terrain"].c.append(colors)
        b["terrain"].n = len(xs)
    return clipped, removed


def build_roads(tiles, ex, frame, dem, base):
    """Road graph clipped to the DGM1 square."""
    return build_road_network(ex, frame, dem, base,
                              tiles.half + DGM1_MARGIN)


def facade_color(x, y, biome="temperate"):
    """Facade colour of the building with centroid x, y: 60 % warm
    plaster, 20 % white, 20 % grey, from an explicit integer mix of the
    centroid (deterministic, no global random state); a biome with
    FACADES (biome.py) picks from those by the same mix."""
    m = (int(x * 10) * 73856093 ^ int(y * 10) * 19349663) % 1000
    if biome in FACADES:
        lo = 0.0
        last = len(FACADES[biome]) - 1
        for k, (share, a, b) in enumerate(FACADES[biome]):
            if m < (lo + share) * 1000 or k == last:
                t = (m - lo * 1000) / (share * 1000)
                a, b = np.array(a), np.array(b)
                return tuple(a + (b - a) * min(max(t, 0.0), 1.0))
            lo += share
    if m < 600:
        warm = np.array([0.88, 0.82, 0.66]), np.array([0.80, 0.70, 0.54])
        t = m / 600
        return tuple(warm[0] + (warm[1] - warm[0]) * t)
    if m < 800:
        return (0.92, 0.91, 0.88)
    grey = np.array([0.66, 0.66, 0.65]), np.array([0.78, 0.77, 0.75])
    t = (m - 800) / 200
    return tuple(grey[0] + (grey[1] - grey[0]) * t)


def roof_color(x, y, biome):
    """Roof colour of the building with centroid x, y, between the
    biome's two ROOF colours by an integer mix of the centroid other than
    facade_color()'s, so roof and facade vary apart."""
    m = (int(x * 10) * 83492791 ^ int(y * 10) * 2654435761) % 1000
    a, b = np.array(ROOF[biome][0]), np.array(ROOF[biome][1])
    return tuple(a + (b - a) * m / 1000)


def storeys(x, y, biome):
    """Wall height of an untagged house with centroid x, y: STOREYS of
    the biome picked by a third integer mix of the centroid."""
    m = (int(x * 10) * 2246822519 ^ int(y * 10) * 3266489917) % 1000
    lo = 0.0
    for share, count in STOREYS[biome]:
        lo += share
        if m < lo * 1000:
            break
    return count * STOREY_M + PLINTH_M


def pitched(geom, tags, biome):
    """Whether the footprint piece geom gets a hipped roof (PITCHED)."""
    if biome not in PITCHED or tags.get("building") in FLAT_ROOFED:
        return False
    env = shapely.oriented_envelope(geom)
    if env.geom_type != "Polygon" or env.area <= 0.0:
        return False
    coords = np.asarray(env.exterior.coords)
    short = min(np.hypot(*(coords[1] - coords[0])),
                np.hypot(*(coords[2] - coords[1])))
    return short <= PITCHED[biome]["span"] \
        and geom.area >= PITCHED[biome]["rect"] * env.area


def isolated(buildings, urban):
    """Per building: outside the urban land cover and fewer than
    ISOLATED_NEIGHBOURS other buildings within ISOLATED_M."""
    cents = shapely.centroid([g for g, _ in buildings])
    if len(cents) == 0:
        return np.zeros(0, dtype=bool)
    tree = shapely.STRtree(cents)
    pi, _ = tree.query(cents, predicate="dwithin", distance=ISOLATED_M)
    near = np.bincount(pi, minlength=len(cents)) - 1
    out = near < ISOLATED_NEIGHBOURS
    if urban is not None:
        out &= ~shapely.contains_xy(urban, shapely.get_x(cents),
                                    shapely.get_y(cents))
    return out


class RoadsOver:
    """Plan quads of every drawn segment outside tunnels (deck segments
    with walkway and parapet), their lowest surface and the ceiling a
    building part under them may reach."""

    def __init__(self, net, lay):
        k = segment_index(net)
        k = k[net.kind[net.edge_of[k]] != "tunnel"]
        deck = np.isin(k, lay.deck_k)
        a, b = (np.column_stack([net.sx[i], net.sy[i]]) for i in (k, k + 1))
        ha, hb = (np.where(deck, deck_half(net, i), net.half[i])[:, None]
                  * normals(net, i) for i in (k, k + 1))
        self.quads = shapely.polygons(np.stack(
            [a + ha, b + hb, b - hb, a - ha], axis=1))
        self.surface = np.minimum(net.surface[k], net.surface[k + 1])
        self.ceiling = self.surface - np.where(deck, DECK_DEPTH, 0.0) \
            - BUILDING_CLEAR_M
        self.tree = shapely.STRtree(self.quads)

    def split(self, geom, bottom, top):
        """(geometry, top) parts of a footprint: the part under roads
        more than UNDER_ROAD_M above bottom ends at their lowest ceiling
        (left out below MIN_PART_M), the rest at top. None when no such
        road has its ceiling below top."""
        i = self.tree.query(geom, predicate="intersects")
        i = i[self.surface[i] > bottom + UNDER_ROAD_M]
        if not len(i) or self.ceiling[i].min() >= top:
            return None
        over = shapely.union_all(self.quads[i])
        cap = float(self.ceiling[i].min())
        if over.intersection(geom).area >= UNDER_SHARE * geom.area:
            # a structure mostly under the roads (a viaduct above a long,
            # low building): its rest would stick out above the deck
            return [(geom, cap)] if cap - bottom >= MIN_PART_M else []
        parts = [(geom.difference(over), top)]
        if cap - bottom >= MIN_PART_M:
            parts.append((geom.intersection(over), cap))
        return parts


def polygons(geom):
    """The polygons of a shapely result, slivers below 1 m2 left out."""
    out = [g for g in getattr(geom, "geoms", [geom])
           if g.geom_type in ("Polygon", "MultiPolygon")]
    out = [p for g in out for p in getattr(g, "geoms", [g])]
    return [p for p in out if p.area >= 1.0]


def build_buildings(tiles, buildings, dem, base, biome="temperate",
                    urban=None, roads_over=None):
    """Extruded footprints; with the biome's ROOF a tile-red roof, hipped
    where pitched() allows it (on pieces at full height, not under a
    road), with GROUND_FLOOR_M lone houses (isolated()) without a height
    or levels tag on the ground floor only. Returns the count, the number
    of those single-storey houses, of capped and of hipped buildings.
    With roads_over (RoadsOver) the part of a footprint under a deck or a
    raised road ends BUILDING_CLEAR_M below it; capped counts those
    buildings."""
    count = low = capped = hipped = 0
    lone = isolated(buildings, urban) if biome in GROUND_FLOOR_M \
        else np.zeros(len(buildings), dtype=bool)
    for (geom, tags), alone in zip(buildings, lone):
        c = geom.centroid
        key = tiles.of(c.x, c.y)
        if key is None:
            continue
        coords = shapely.get_coordinates(geom.exterior if
                                         geom.geom_type == "Polygon"
                                         else geom.geoms[0].exterior)
        bottom = float(np.min(dem.height(coords[:, 0], coords[:, 1]))) - base
        tagged = "height" in tags or "building:levels" in tags
        if alone and not tagged:
            top = bottom + GROUND_FLOOR_M[biome]
            low += 1
        elif biome in STOREYS and not tagged \
                and tags.get("building") in HOUSE_KINDS:
            top = bottom + storeys(c.x, c.y, biome)
        else:
            top = bottom + building_height(tags)
        color = facade_color(c.x, c.y, biome)
        roof = roof_color(c.x, c.y, biome) if biome in ROOF else None
        parts = roads_over.split(geom, bottom, top) \
            if roads_over is not None else None
        if parts is None:
            pieces = [(p, top) for p in getattr(geom, "geoms", [geom])]
            hips = [pitched(p, tags, biome) for p, _ in pieces]
        else:
            pieces = [(p, h) for g, h in parts for p in polygons(g)]
            hips = [False] * len(pieces)
            capped += 1
        hipped += any(hips)
        for (p, h), hip in zip(pieces, hips):
            try:
                verts, faces = extrude(p, bottom - 1.0, h)
            except Exception:
                continue
            if roof is not None:
                # extrude() puts the roof vertices first, one per ring
                # vertex
                n_roof = len(p.exterior.coords) - 1 + sum(
                    len(i.coords) - 1 for i in p.interiors)
                colors = np.tile(color, (len(verts), 1))
                colors[:n_roof] = roof
                if hip:
                    # the flat top stays, hidden under the hipped roof
                    rv, rf = hip_roof(p, h, PITCHED[biome]["pitch"],
                                      PITCHED[biome]["eave"])
                    faces = list(faces) + [(a + len(verts), b + len(verts),
                                            c + len(verts))
                                           for a, b, c in rf]
                    verts = np.vstack([verts, rv])
                    colors = np.vstack([colors, np.tile(roof, (len(rv), 1))])
                tiles.buckets[key]["buildings"].add(verts, faces, colors)
            else:
                tiles.buckets[key]["buildings"].add(verts, faces, color)
        count += 1
    return count, low, capped, hipped


def export_tiles(tiles, out):
    out.mkdir(parents=True, exist_ok=True)
    names, total_bytes = [], 0
    for (i, j), b in tiles.buckets.items():
        scene = trimesh.Scene()
        for layer in LAYERS:
            m = b[layer].mesh()
            if m is not None:
                scene.add_geometry(m, node_name=layer, geom_name=layer)
        name = f"tile_{i:02d}_{j:02d}.glb"
        scene.export(out / name)
        total_bytes += (out / name).stat().st_size
        names.append(name)
    return names, total_bytes


def write_road_lines(net, path):
    """roads.bin: every drawn 5 m sample of every edge as float32 x, y,
    z (glTF frame, y the drawn road surface, bridges and tunnels
    included), the edge index and the road rank (roads.ROAD_RANK, for
    the minimap), so Godot finds the nearest road (road_index.gd).
    Consecutive rows of the same edge form a segment."""
    rows = np.column_stack([xyz(net.sx, net.surface, net.sy),
                            net.edge_of,
                            net.rank[net.edge_of]]).astype(np.float32)
    rows.tofile(path)
    # one label per edge, in edge order, for the position readout (#)
    names = []
    for e in net.edges:
        t = e["tags"]
        name, ref = t.get("name", ""), t.get("ref", "")
        names.append(f"{name} ({ref})" if name and ref else name or ref)
    (path.parent / "road_names.json").write_text(
        json.dumps(names, ensure_ascii=False))
    return len(rows)


def build_horizon(path, horizon_km, half, dem, base, has_sea=False,
                  colors_of=COLORS, biome="temperate"):
    """Coarse ring so hills show beyond the playable area; with a sea,
    vertices at 0 m are water; rock by height as on the terrain."""
    hz = horizon_km * 500.0
    xs, ys, hs, faces = grid_mesh(-hz, -hz, 2 * hz, HORIZON_STEP, dem, base)
    colors = np.tile(colors_of["horizon"], (len(xs), 1))
    if "rock" in colors_of:
        share = rock_share(biome, hs + base, np.zeros(len(hs)))[:, None]
        colors = colors * (1 - share) + np.asarray(colors_of["rock"]) * share
    colors[horizon_water(hs + base, has_sea)] = COLORS["water"]
    hx, hy = np.broadcast_to(half, 2)
    inside = (np.abs(xs) < hx - HORIZON_STEP) \
        & (np.abs(ys) < hy - HORIZON_STEP)
    hs = np.where(inside, hs - HORIZON_SINK_M, hs)
    horizon = Bucket()
    horizon.add(xyz(xs, hs, ys), faces, colors)
    if has_sea:
        horizon_sea(horizon, xs, ys, hs, colors, hz)
    horizon.mesh().export(path)


def horizon_sea(horizon, xs, ys, hs, colors, hz):
    """Flat sea outward from the water stretches of the horizon border, so
    the sea does not end at the horizon square (the camera sees 40 km)."""
    water = np.all(colors == COLORS["water"], axis=1)
    edge = np.isclose(np.abs(xs), hz) | np.isclose(np.abs(ys), hz)
    for axis, side in ((0, -1), (0, 1), (1, -1), (1, 1)):
        coord = xs if axis == 0 else ys
        on = np.flatnonzero(edge & np.isclose(coord, side * hz))
        along = ys[on] if axis == 0 else xs[on]
        on = on[np.argsort(along)]
        for a, b in zip(on[:-1], on[1:]):
            if not (water[a] and water[b]):
                continue
            far = np.array([[xs[a], ys[a]], [xs[b], ys[b]]])
            far[:, axis] += side * HORIZON_SEA_M
            quad = np.array([[xs[a], ys[a], hs[a]], [xs[b], ys[b], hs[b]],
                             [far[1, 0], far[1, 1], hs[b]],
                             [far[0, 0], far[0, 1], hs[a]]])
            verts = xyz(quad[:, 0], quad[:, 2], quad[:, 1])
            # both windings: the side of the border decides the normal
            horizon.add(verts, [(0, 1, 2), (0, 2, 3), (0, 2, 1),
                                (0, 3, 2)], COLORS["water"])
    # the corners between two of those strips
    for sx in (-1, 1):
        for sy in (-1, 1):
            k = np.flatnonzero(np.isclose(xs, sx * hz)
                               & np.isclose(ys, sy * hz))
            if len(k) == 0 or not water[k[0]]:
                continue
            x, y, h, f = xs[k[0]], ys[k[0]], hs[k[0]], HORIZON_SEA_M
            verts = xyz(np.array([x, x + sx * f, x + sx * f, x]),
                        np.full(4, h),
                        np.array([y, y, y + sy * f, y + sy * f]))
            horizon.add(verts, [(0, 1, 2), (0, 2, 3), (0, 2, 1),
                                (0, 3, 2)], COLORS["water"])


# route points farther than this from every drawn road segment take the
# conformed terrain instead of the road surface
ROUTE_SNAP_M = 10.0
ROUTE_FAR_LISTED = 20


def route_heights(x, y, net, ground, base, tree, seg):
    """Road surface height at the nearest drawn segment, else terrain.

    seg = (k, a, b): first sample index and end points of every segment
    of consecutive samples of one edge, bridges and tunnels included.
    Returns heights, snap distances and the segment index (-1 = far).
    """
    k, a, b = seg
    pts = shapely.points(x, y)
    (pi, si), _ = tree.query_nearest(pts, max_distance=ROUTE_SNAP_M,
                                     return_distance=True)
    pi, first = np.unique(pi, return_index=True)
    si = si[first]
    h = np.asarray(ground.height(x, y), dtype=np.float64) - base
    dist = np.full(len(x), np.inf)
    nearest = np.full(len(x), -1)
    if len(pi):
        p = np.column_stack([x[pi], y[pi]])
        ab = b[si] - a[si]
        t = np.einsum("ij,ij->i", p - a[si], ab) / np.maximum(
            np.einsum("ij,ij->i", ab, ab), 1e-12)
        t = np.clip(t, 0.0, 1.0)
        q = a[si] + ab * t[:, None]
        dist[pi] = np.hypot(*(p - q).T)
        s0, s1 = net.surface[k[si]], net.surface[k[si] + 1]
        h[pi] = s0 + (s1 - s0) * t
        nearest[pi] = si
    return h, dist, nearest


def densify(x, y, step):
    """Polyline x, y resampled to at most step between consecutive points.

    The original points are kept; each segment gets evenly spaced extra
    points, interpolated linearly over the cumulative length.
    """
    seg = np.hypot(np.diff(x), np.diff(y))
    s = np.concatenate([[0.0], np.cumsum(seg)])
    n = np.maximum(np.ceil(seg / step).astype(int), 1)
    i = np.repeat(np.arange(len(seg)), n)
    j = np.arange(len(i)) - np.repeat(np.cumsum(n) - n, n)
    t = np.append(s[i] + seg[i] * j / n[i], s[-1])
    return np.interp(t, s, x), np.interp(t, s, y)


def build_route(path, frame, net, ground, base):
    """Route polyline and waypoints from an OSRM response, as vertices.

    Heights come from the drawn road surface (net.surface, including the
    lift, bridges and tunnels) at the nearest segment within
    ROUTE_SNAP_M; farther points take the conformed terrain. The line is
    densified to ROAD_STEP first, the waypoints are not. Returns the
    line, the waypoints and stats for the report.
    """
    route = json.loads(path.read_text())
    coords = np.array(route["routes"][0]["geometry"]["coordinates"])
    wp = np.array([w["location"] for w in route["waypoints"]])
    k = np.arange(len(net.sx) - 1)
    k = k[net.edge_of[k] == net.edge_of[k + 1]]
    a = np.column_stack([net.sx[k], net.sy[k]])
    b = np.column_stack([net.sx[k + 1], net.sy[k + 1]])
    tree = shapely.STRtree(shapely.linestrings(np.stack([a, b], axis=1)))
    x, y = frame.to_local(coords[:, 0], coords[:, 1])
    source_points = len(x)
    # OSRM points lie tens of metres apart: a band between them would cut
    # through crests or float over dips
    x, y = densify(x, y, ROAD_STEP)
    h, dist, nearest = route_heights(x, y, net, ground, base, tree,
                                     (k, a, b))
    line = xyz(x, h, y).round(2).tolist()
    wx, wy = frame.to_local(wp[:, 0], wp[:, 1])
    wh, _, _ = route_heights(wx, wy, net, ground, base, tree, (k, a, b))
    points = xyz(wx, wh, wy).round(2).tolist()
    snapped = nearest >= 0
    d = dist[snapped]
    far = np.flatnonzero(~snapped)[:ROUTE_FAR_LISTED]
    (fi, _), fd = tree.query_nearest(shapely.points(x[far], y[far]),
                                     return_distance=True)
    fi, first = np.unique(fi, return_index=True)
    stats = {
        "points": len(x), "source_points": source_points,
        "snapped": int(np.count_nonzero(snapped)),
        "fallback": int(np.count_nonzero(~snapped)),
        "fallback_distance_m": ROUTE_SNAP_M,
        "max_snap_m": round(float(d.max()), 2) if len(d) else None,
        "snap_p95_m": round(float(np.percentile(d, 95)), 2)
        if len(d) else None,
        "on_structure": int(np.count_nonzero(
            net.struct[net.edge_of[k[nearest[snapped]]]])),
        "far": [{"x": round(float(x[i]), 1), "y": round(float(y[i]), 1),
                 "distance_m": round(float(v), 1)}
                for i, v in zip(far[fi], fd[first])]}
    return line, points, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("extract", type=Path)
    ap.add_argument("--terrain", type=Path, required=True,
                    help="terrain GeoTIFF from pipeline/fetch.py (DGM1 "
                    "or LiDAR HD)")
    ap.add_argument("--horizon-dem", type=Path, nargs="+", required=True,
                    help="Copernicus GeoTIFFs, horizon ring only")
    ap.add_argument("--recipe", type=Path, required=True,
                    help="world recipe (worlds/<id>/world.json): area, "
                    "route and start points")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    started = time.time()
    load_start = Path("/proc/loadavg").read_text().split()[:3]

    recipe = load_recipe(args.recipe)
    lat, lon = recipe.center
    frame = Frame(lon, lat, recipe.heading_deg, recipe.epsg)
    tiles = Tiles(recipe.size_km, recipe.width_km)
    dem = Dgm1Raster(args.terrain, frame, tiles.half + DGM1_MARGIN)
    for p in args.horizon_dem:
        if not p.is_file():
            raise InputError(f"horizon DEM {p} not found")
    horizon_dem = LonLatDem(args.horizon_dem, frame)
    ex = load_extract(args.extract)
    sea, sea_stats = add_sea(ex, frame, dem)
    base = float(dem.height(0.0, 0.0))
    offset = float(horizon_dem.height(0.0, 0.0)) - base

    cover, buildings = split_areas(ex, frame, sea)
    colors_of = palette(COLORS, recipe.biome)
    t_cover = time.time()
    net = build_roads(tiles, ex, frame, dem, base)
    assign_sidewalks(net, cover["urban"], buildings)
    road_km = float(net.length.sum()) / 1000
    raised = raise_decks(net)
    layout = classify(net, dem, base, tiles.half + DGM1_MARGIN)
    t_roads = time.time()
    ground = conform(net, dem, base, tiles.half, TERRAIN_STEP, layout)
    tunnels = build_tunnels(net, ground, base, tiles)
    water = Water(inland_water(ex, frame, tiles.half), ground, base,
                  RoadsOver(net, layout))
    clipped, removed = build_terrain(tiles, cover, ground, base,
                                     tunnels.cut, colors_of, recipe.biome,
                                     water)
    tunnels.stats.update(terrain_triangles_clipped=clipped,
                         terrain_triangles_removed=removed)
    emit_network(tiles, net, (COLORS["road"], COLORS["road_major"],
                              COLORS["gravel"]))
    sidewalk_stats = emit_sidewalks(tiles, net, COLORS["sidewalk"],
                                    COLORS["kerb"])
    skirt_stats = emit_skirts(tiles, net, ground, base, COLORS["bank"])
    marking_stats = emit_markings(tiles, net, COLORS["marking"])
    clipping = check_clipping(net, ground, base, tiles.half)
    tunnels.emit(tiles, "tunnels")
    decks = build_decks(net, layout, tiles, ground, base)
    decks.emit(tiles, "bridges")
    bridge_stats = {**bridge_report(net, layout, raised, ground, base,
                                    tiles.half),
                    **decks.stats}
    t_terrain = time.time()
    building_count, single_storey, under_roads, hipped = build_buildings(
        tiles, buildings, ground, base, recipe.biome, cover["urban"],
        RoadsOver(net, layout))
    trees = build_trees(ex, frame, net, cover, buildings, ground, base,
                        tiles, tunnels.cut, recipe.biome)
    t_buildings = time.time()
    tile_files, total_bytes = export_tiles(tiles, args.out)
    tree_meta = emit_trees(trees, tiles, TILE, args.out)
    write_road_lines(net, args.out / "roads.bin")
    sign_stats = write_signs(net, ground, base, ex["places"],
                             ex["town_signs"], frame, buildings, cover,
                             tiles.half, country_of(recipe.osm_region),
                             args.out / "signs.json")
    t_export = time.time()
    build_horizon(args.out / "horizon.glb", recipe.horizon_km, tiles.half,
                  horizon_dem, base, sea is not None, colors_of,
                  recipe.biome)

    head, tail = manifest_fields(recipe)
    meta = {**head,
            "center": [lat, lon], "size_km": recipe.size_km,
            **({"width_km": recipe.width_km,
                "heading_deg": recipe.heading_deg}
               if recipe.width_km != recipe.size_km or recipe.heading_deg
               else {}),
            "tile_m": TILE,
            "base_height": base, "tiles": tile_files,
            "horizon": "horizon.glb", "roads": "roads.bin",
            "road_names": "road_names.json", "signs": "signs.json",
            "route": None,
            "trees": tree_meta,
            "terrain_source": recipe.terrain,
            "terrain_file": args.terrain.name,
            "horizon_source": "copernicus"}
    route_stats = None
    if recipe.route:
        meta["route"], meta["waypoints"], route_stats = build_route(
            recipe.route, frame, net, ground, base)
    if recipe.starts:
        meta["starts"] = build_starts(recipe.starts, net, frame,
                                      meta["route"])
    meta.update(tail)
    (args.out / "world.json").write_text(json.dumps(meta))
    t_horizon = time.time()

    run_info = {"started": started, "load_start": load_start,
                "terrain_file": args.terrain.name, "tile_m": TILE,
                "terrain_step": TERRAIN_STEP, "half": tiles.half,
                "dem_half": tiles.half + DGM1_MARGIN,
                "stages_s": {
                    "cover": t_cover - started,
                    "roads": t_roads - t_cover,
                    "terrain": t_terrain - t_roads,
                    "buildings": t_buildings - t_terrain,
                    "export": t_export - t_buildings,
                    "horizon": t_horizon - t_export}}
    metrics = write_metrics(net, args.out, run_info, dem, base, frame,
                            meta["route"], horizon_dem=horizon_dem,
                            ground=ground, route_stats=route_stats,
                            tunnels=tunnels.stats, bridges=bridge_stats,
                            skirts=skirt_stats, markings=marking_stats,
                            sidewalks=sidewalk_stats, clipping=clipping,
                            clipping_baseline_path=recipe.path.parent
                            / CLIPPING_BASELINE)
    write_viewpoints(args.out / "viewpoints.json", metrics["clipping"], net)
    graph = metrics["graph"]
    gates = metrics["gates"]

    print(f"tiles={len(tile_files)} road_km={road_km:.0f} "
          f"buildings={building_count} single_storey={single_storey} "
          f"under_roads={under_roads} hipped={hipped} "
          f"trees={trees.stats['total']} "
          f"mb={total_bytes / 1e6:.1f} "
          f"cover_s={t_cover - started:.0f} "
          f"roads_s={t_roads - t_cover:.0f} "
          f"terrain_s={t_terrain - t_roads:.0f} "
          f"buildings_s={t_buildings - t_terrain:.0f} "
          f"total_s={time.time() - started:.0f} "
          f"base_height_m={base:.2f} "
          f"copernicus_minus_dgm1_at_center_m={offset:.2f}")
    print(f"nodes={graph['nodes']} edges={graph['edges']} "
          f"junctions={graph['junction_surfaces']} "
          f"components={graph['components']['count']} "
          f"max_grade_pct={metrics['slope']['max_grade_pct']} "
          f"ground_node_dev_max_m="
          f"{metrics['node_heights']['ground']['max']}")
    print("trees: " + " ".join(f"{k}={v}" for k, v in trees.stats.items()))
    print("sea: " + " ".join(f"{k}={v}" for k, v in sea_stats.items()))
    print("water: " + " ".join(f"{k}={v}"
                               for k, v in water.stats.items()))
    print("signs: " + " ".join(f"{k}={v}" for k, v in sign_stats.items()))
    print(" ".join(f"{k}={gates[k]}" for k in HARD_GATES))
    for st in meta.get("starts", []):
        print(f"start {st['name']!r}: {st['road']} (way {st['way']}) "
              f"snap_m={st['snap_m']}")
    failed = [k for k in HARD_GATES if gates[k] != "PASS"]
    if failed:
        print(f"error: gate {', '.join(failed)} failed, see "
              f"{args.out / 'metrics.md'}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    try:
        main()
    except (InputError, TerrainError, StartError, RecipeError,
            FileNotFoundError) as err:
        print(f"error: {err}", file=sys.stderr)
        sys.exit(2)
# - revised 2026-10-22 (stone bank colour, facade colours)
# - revised 2026-10-22 (clipping report and viewpoints)
# - revised 2026-10-22 (world recipe, world.json manifest)
# - revised 2026-10-22 (tiles own their key lookup)
# - revised 2026-10-22 (DGM1 margin from fetch.py)
# - revised 2026-10-22 (name, version, min_game, sources in world.json)
# - revised 2026-10-23 (merge: clipping baseline next to the recipe)
# - revised 2026-10-23 (terrain source from the recipe, sea from the OSM coastline)
# - revised 2026-10-23 (biome palette, rock, tree kinds)
# - revised 2026-10-23 (rectangular, turned worlds)
# - revised 2026-10-23 (roads.bin: road centre lines for Godot)
# - revised 2026-10-23 (mediterranean facades, roofs, single-storey lone houses)
# - revised 2026-10-23 (road rank in roads.bin)
# - revised 2026-10-23 (road_names.json for the position readout)
# - revised 2026-10-23 (signs.json)
# - revised 2026-10-24 (horizon sinks 400 m under the playable area)
# - revised 2026-10-25 (town and distance signs)
# - revised 2026-10-25 (default sidewalks in town only)
# - revised 2026-10-25 (buildings under decks and raised roads capped)
# - revised 2026-10-25 (gravel colour for tracks)
# - revised 2026-11-04 (ground shade of the mediterranean biomes)
# - revised 2026-11-04 (inland water as a surface, water.py)
# - revised 2026-11-04 (hipped mediterranean roofs, roof colour by hash,
#   storeys by hash)
