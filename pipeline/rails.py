# file generated with AI assistance: Claude Code - 2026-11-04 18:20:00 UTC
"""Railway tracks: a ballast bed with two rails, and on a road only the
rails.

KINDS of `railway` ways are drawn (extract.py keeps them as `rails`);
tunnels, covered and underground ways are left out, bridges get a
straight grade between the ground at their ends (DGM1 has no bridges;
no deck or pier is drawn). Each way keeps its OSM vertices (simplified
by SIMPLIFY m) with samples at most STEP m apart: a 2 m step on every
straight made the Stuttgart tiles half as large again. Where a
sample lies on a drawn ground road (priority.RoadArea.surface_height)
the road wins: no bed, the rails are flat strips RAIL_LIFT above the
road surface, so a tram line or a level crossing reads as rails let
into the asphalt. Elsewhere the bed stands BED_TOP above the conformed
ground with slopes down to BED_SINK below it, BED_HALF + BED_SLOPE
wide each side; a bed segment that overlaps a road is dropped (the
road wins there too) and its rails lie RAIL_LIFT above the ground. The
rails are flat strips RAIL_W wide everywhere, gauge from the `gauge`
tag (mm, default 1435); no sides and no sleepers: sides doubled the
vertex count, and a fine stripe pattern shimmers on the GPU.
Everything goes into the `rails` layer, which the drive scene loads
without collision (world.gd), so neither bed nor rails move the car.
"""
import numpy as np
import shapely

from extract import RAIL_KINDS as KINDS
from priority import NO_EDGE, road_area
from roads import add_ribbon, orient, ribbon, tile_keys

STEP = 5.0
SIMPLIFY = 0.1
GAUGE_MM = 1435.0
RAIL_W = 0.08
RAIL_LIFT = 0.03
BED_TOP = 0.30
BED_SINK = 0.20
BED_HALF = 1.5
BED_SLOPE = 0.9
# a bed segment overlapping a road more than this (m2) is dropped
BED_ROAD_M2 = 0.5
# trees keep this distance from a track centre line (trees.py)
RAIL_CLEAR = 3.0


def drawn(tags):
    """A railway way that lies on the surface."""
    if tags.get("railway") not in KINDS:
        return False
    if tags.get("tunnel", "no") != "no" or tags.get("covered") == "yes":
        return False
    try:
        return float(tags.get("layer", "0")) >= 0 \
            or tags.get("bridge", "no") != "no"
    except ValueError:
        return True


def gauge(tags):
    """Track gauge in m from the first number of `gauge`."""
    try:
        return float(str(tags.get("gauge", "")).split(";")[0]) / 1000
    except ValueError:
        return GAUGE_MM / 1000


def rail_lines(ex, frame, half):
    """(line, tags) in the local frame, clipped to the playable box."""
    hx, hy = np.broadcast_to(half, 2)
    box = shapely.box(-hx, -hy, hx, hy)
    out = []
    for r in ex.get("rails", []):
        if not drawn(r["tags"]):
            continue
        g = shapely.intersection(
            frame.geom_to_local(shapely.from_wkb(r["geom"])), box)
        for part in getattr(g, "geoms", [g]):
            if part.geom_type == "LineString" and part.length >= STEP:
                out.append((part, r["tags"]))
    return out


def samples(line):
    """Positions at most STEP m apart (ends and bends included),
    distance along, unit normal (left of the direction of travel)."""
    p = shapely.get_coordinates(shapely.segmentize(
        shapely.simplify(line, SIMPLIFY), STEP))
    d = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))])
    t = np.gradient(p, axis=0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    return p, d, np.column_stack([-t[:, 1], t[:, 0]])


def emit_rails(tiles, ex, frame, net, ground, base, colors):
    """Beds and rails of every drawn railway; colors = (bed, rail).
    Returns (stats, lines): lines are the drawn centre lines for the
    tree clearing."""
    bed_color, rail_color = colors
    area = road_area(net)
    stats = {"ways": 0, "km": 0.0, "km_on_road": 0.0, "km_bed": 0.0,
             "km_bridge": 0.0}
    lines = []
    for line, tags in rail_lines(ex, frame, tiles.half):
        p, d, nrm = samples(line)
        g = ground.height(p[:, 0], p[:, 1]) - base
        bridge = tags.get("bridge", "no") != "no"
        if bridge:
            g = np.interp(d, d[[0, -1]], g[[0, -1]])
        road = area.surface_height(p[:, 0], p[:, 1])
        on = np.isfinite(road) & (not bridge)
        mid = (p[:-1] + p[1:]) / 2
        owner = tile_keys(tiles, mid[:, 0], mid[:, 1])
        seg = np.diff(d)
        bed = ~on[:-1] & ~on[1:] & (owner >= 0)
        if bed.any():
            quads = shapely.polygons(np.stack(
                [p[:-1] + nrm[:-1] * BED_HALF, p[1:] + nrm[1:] * BED_HALF,
                 p[1:] - nrm[1:] * BED_HALF, p[:-1] - nrm[:-1] * BED_HALF,
                 p[:-1] + nrm[:-1] * BED_HALF], axis=1)[bed])
            bed[bed] = area.keep(quads, NO_EDGE, BED_ROAD_M2, 1.0)
        if bed.any():
            emit_bed(tiles, p, nrm, g, np.where(bed, owner, -1), ground,
                     base, bed_color)
        on_bed = np.zeros(len(p), dtype=bool)
        on_bed[:-1] |= bed
        on_bed[1:] |= bed
        top = np.where(on, road, g + np.where(on_bed, BED_TOP, 0.0)) \
            + RAIL_LIFT
        off = gauge(tags) / 2 + RAIL_W / 2
        half = nrm * (RAIL_W / 2)
        for side in (1.0, -1.0):
            c = p + nrm * (side * off)
            verts, faces = ribbon(c + half, c - half, top, top)
            add_ribbon(tiles, verts, orient(verts, faces, [0, 1, 0]), owner,
                       rail_color, "rails")
        stats["ways"] += 1
        stats["km"] += float(seg[owner >= 0].sum())
        stats["km_on_road"] += float(seg[(on[:-1] | on[1:])
                                         & (owner >= 0)].sum())
        stats["km_bed"] += float(seg[bed].sum())
        if bridge:
            stats["km_bridge"] += float(seg[owner >= 0].sum())
        lines.append(line)
    stats = {k: round(v / 1000, 2) if k.startswith("km") else v
             for k, v in stats.items()}
    return stats, lines


def emit_bed(tiles, p, nrm, g, owner, ground, base, color):
    """Ballast bed: flat top BED_TOP above the centre ground, slopes to
    BED_SINK below the ground at the feet."""
    top = g + BED_TOP
    for side in (1.0, -1.0):
        edge = p + nrm * (side * BED_HALF)
        foot = p + nrm * (side * (BED_HALF + BED_SLOPE))
        hf = ground.height(foot[:, 0], foot[:, 1]) - base - BED_SINK
        verts, faces = ribbon(edge, foot, top, hf)
        add_ribbon(tiles, verts, orient(verts, faces, [0, 1, 0]), owner,
                   color, "rails")
    verts, faces = ribbon(p + nrm * BED_HALF, p - nrm * BED_HALF, top, top)
    add_ribbon(tiles, verts, orient(verts, faces, [0, 1, 0]), owner,
               color, "rails")

