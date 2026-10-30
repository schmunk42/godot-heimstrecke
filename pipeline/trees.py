# file generated with AI assistance: Claude Code - 2026-10-23 02:30:00 UTC
"""Trees: forests filled on a jittered grid, OSM single trees and rows.

Forest trees stand on a FOREST_STEP grid, each moved up to FOREST_JITTER
in both directions, inside the `forest` land cover (natural=wood,
landuse=forest). The polygon's leaf_type sets the share of conifers.
Single trees (natural=tree nodes) stand where OSM has them, tree rows
(natural=tree_row ways) get one every ROW_STEP. The RNG is seeded, so
the same extract always gives the same trees.

Left out: forest trees within ROAD_CLEAR of a road side (the sidewalk
and the pushed-down terrain beside it) or BUILDING_CLEAR of a building,
mapped trees on the carriageway itself (OSM street trees often lie
within the default road width) or in a building, all trees in water and
in the tunnel portal cuts; along tracks (recipe `tracks`) the clearing
is TRACK_CLEAR. Footways, other tracks and railways are not in the
extract, forest trees may stand on them.

The kinds depend on the biome (biome.py). temperate: broad and conifer
as above. mediterranean and mediterranean-dry: oak (holm oak), pine,
cypress and shrub; the conifer share of a forest is the pine share,
untagged forests get more
pines with height (PINE_BY_HEIGHT, laricio above, holm oak below),
mapped Cupressus become cypresses, and natural=scrub/heath outside
forest and rock is filled with shrubs (the maquis) on a SHRUB_STEP grid,
a few holm oaks among them; shrubs get no collision trunk. The shrubs
draw from their own seeded RNG, so the other trees are the same as
without them.

Output per tile: <tile>.trees, float32, one Godot MultiMesh instance per
tree (TRANSFORM_3D rows with the origin as fourth column, then the
colour, 16 floats), kind by kind (the biome's kinds), within a kind CHUNK x CHUNK
chunk by chunk (x first, then north). The model is one unit high, the
transform scales it to the tree height. <tile>.trunks: x, y, z (glTF
frame, the foot of the trunk) of every tree that gets a collision trunk:
mapped trees and forest trees within COLLIDE_M of a road side. A tile
without trees or trunks has no such file.
"""
import numpy as np
import shapely

from biome import KINDS, MEDITERRANEAN
from frame import xyz
from roads import road_width
from sidewalks import WIDTH as SIDEWALK

FOREST_STEP = 7.0
FOREST_JITTER = 2.5
ROW_STEP = 9.0
CHUNK = 250.0
ROAD_CLEAR = SIDEWALK + 4.0
# a forest track (recipe `tracks`) runs as a narrow lane through the trees
TRACK_CLEAR = 1.5
BUILDING_CLEAR = 2.0
CARRIAGEWAY_CLEAR = 0.5
COLLIDE_M = 15.0
# the foot of the trunk lies this far below the ground, on slopes too
SINK = 0.4
# share of conifers per forest leaf_type, untagged forests last
CONIFER_SHARE = {"needleleaved": 0.9, "broadleaved": 0.05, "mixed": 0.5,
                 None: 0.25}
CONIFER_GENUS = {"Pinus", "Picea", "Abies", "Taxus", "Larix", "Thuja",
                 "Pseudotsuga", "Cedrus", "Juniperus", "Sequoiadendron"}
# height ranges (m): forest broadleaf, forest conifer, mapped trees
FOREST_H = {"broad": (14.0, 26.0), "conifer": (18.0, 30.0)}
MAPPED_H = (8.0, 16.0)
SEED = 20261023
# mediterranean: forest heights per kind index (oak, pine), cypress,
# shrub and the holm oaks in the maquis
MED_FOREST_H = ((7.0, 14.0), (14.0, 26.0))
CYPRESS_H = (10.0, 18.0)
SHRUB_H = (1.2, 3.0)
MAQUIS_OAK_H = (4.0, 9.0)
MAQUIS_OAK_SHARE = 0.06
SHRUB_STEP = 8.0
SHRUB_JITTER = 2.0
# shrubs keep this much from a road side (less than forest trees)
SHRUB_ROAD_CLEAR = SIDEWALK + 1.5
# pine share of an untagged mediterranean forest, by height above sea
PINE_BY_HEIGHT = ((500.0, 0.35), (1000.0, 0.85))
CYPRESS_GENUS = {"Cupressus"}


def _height_tag(tags):
    try:
        h = float(tags["height"].split()[0])
    except (KeyError, ValueError):
        return None
    return h if 2.0 <= h <= 50.0 else None


def _mapped_kind(tags, biome):
    if biome in MEDITERRANEAN and tags.get("genus") in CYPRESS_GENUS:
        return 2
    if tags.get("leaf_type") == "needleleaved" \
            or tags.get("genus") in CONIFER_GENUS:
        return 1
    return 0


def _near(tree, limits, x, y):
    """True where (x, y) lies within limits[g] of geometry g of tree."""
    pts = shapely.points(x, y)
    pi, gi = tree.query(pts, predicate="dwithin", distance=limits.max())
    if len(pi) == 0:
        return np.zeros(len(x), dtype=bool)
    hit = shapely.distance(pts[pi], tree.geometries[gi]) < limits[gi]
    out = np.zeros(len(x), dtype=bool)
    out[pi[hit]] = True
    return out


class Trees:
    """Per tree (local x, y): kind, height h, crown width w, ground (glTF
    height of the trunk foot), angle, tint, collide; plus stats."""


def build_trees(ex, frame, net, cover, buildings, ground, base, tiles,
                cut=None, biome="temperate"):
    rng = np.random.default_rng(SEED)
    med = biome in MEDITERRANEAN
    half = tiles.half
    hx, hy = np.broadcast_to(half, 2)
    lines = [shapely.linestrings(e["coords"]) for e in net.edges]
    road_tree = shapely.STRtree(lines)
    road_half = net.width / 2
    road_clear = road_half + np.where(net.track, TRACK_CLEAR, ROAD_CLEAR)
    footprints = [g for g, _ in buildings]
    building_tree = shapely.STRtree(footprints)
    building_clear = np.full(len(footprints), BUILDING_CLEAR)

    def blocked(x, y):
        out = ~((np.abs(x) < hx) & (np.abs(y) < hy))
        for g in (cover["water"], cut):
            if g is not None:
                out |= shapely.contains_xy(g, x, y)
        return out

    # forest: jittered grid, conifer share by the polygon's leaf_type
    gx, gy = np.meshgrid(np.arange(int(2 * hx / FOREST_STEP)),
                         np.arange(int(2 * hy / FOREST_STEP)))
    fx = -hx + (gx.ravel() + 0.5) * FOREST_STEP
    fy = -hy + (gy.ravel() + 0.5) * FOREST_STEP
    fx = fx + rng.uniform(-FOREST_JITTER, FOREST_JITTER, len(fx))
    fy = fy + rng.uniform(-FOREST_JITTER, FOREST_JITTER, len(fy))
    share = np.full(len(fx), np.nan)
    by_leaf = {}
    for a in ex["areas"]:
        if a["kind"] == "forest":
            leaf = a["tags"].get("leaf_type")
            leaf = leaf if leaf in CONIFER_SHARE else None
            by_leaf.setdefault(leaf, []).append(
                frame.geom_to_local(shapely.from_wkb(a["geom"])))
    # tagged polygons win over untagged ones where they overlap
    for leaf in sorted(by_leaf, key=lambda k: k is not None):
        g = shapely.make_valid(shapely.union_all(by_leaf[leaf]))
        inside = shapely.contains_xy(g, fx, fy)
        if med and leaf is None:
            (h0, s0), (h1, s1) = PINE_BY_HEIGHT
            share[inside] = np.interp(ground.height(fx[inside], fy[inside]),
                                      (h0, h1), (s0, s1))
        else:
            share[inside] = CONIFER_SHARE[leaf]
    inside = ~np.isnan(share)
    fx, fy, share = fx[inside], fy[inside], share[inside]
    keep = ~(blocked(fx, fy) | _near(road_tree, road_clear, fx, fy)
             | _near(building_tree, building_clear, fx, fy))
    fx, fy, share = fx[keep], fy[keep], share[keep]
    f_kind = (rng.random(len(fx)) < share).astype(int)
    heights = MED_FOREST_H if med else (FOREST_H["broad"],
                                        FOREST_H["conifer"])
    lo = np.where(f_kind == 1, heights[1][0], heights[0][0])
    hi = np.where(f_kind == 1, heights[1][1], heights[0][1])
    f_h = rng.uniform(lo, hi)
    f_collide = _near(road_tree, road_clear + COLLIDE_M, fx, fy)

    # mapped trees: single trees and rows
    mx, my, m_kind, m_h = [], [], [], []
    for t in ex["trees"]:
        x, y = frame.to_local(*t["lonlat"])
        mx.append(float(x))
        my.append(float(y))
        m_kind.append(_mapped_kind(t["tags"], biome))
        m_h.append(_height_tag(t["tags"]))
    singles = len(mx)
    for row in ex["tree_rows"]:
        line = frame.geom_to_local(shapely.from_wkb(row["geom"]))
        count = max(1, int(line.length // ROW_STEP) + 1)
        pts = shapely.line_interpolate_point(
            line, np.linspace(0.0, 1.0, count), normalized=True)
        c = shapely.get_coordinates(pts)
        mx.extend(c[:, 0])
        my.extend(c[:, 1])
        m_kind.extend([_mapped_kind(row["tags"], biome)] * count)
        m_h.extend([_height_tag(row["tags"])] * count)
    mx, my = np.array(mx), np.array(my)
    m_kind = np.array(m_kind, dtype=int)
    untagged = np.array([h is None for h in m_h], dtype=bool)
    m_h = np.array([rng.uniform(*MAPPED_H) if h is None else h
                    for h in m_h])
    if med:
        # an untagged cypress takes the same place in CYPRESS_H
        cyp = untagged & (m_kind == 2)
        m_h[cyp] = np.interp(m_h[cyp], MAPPED_H, CYPRESS_H)
    is_single = np.arange(len(mx)) < singles
    out = ~((np.abs(mx) < hx) & (np.abs(my) < hy))
    on_road = _near(road_tree, road_half + CARRIAGEWAY_CLEAR, mx, my) & ~out
    in_building = _near(building_tree, np.full(len(footprints),
                                               CARRIAGEWAY_CLEAR), mx, my)
    drop = blocked(mx, my) | on_road | in_building
    stats = {
        "forest": int(len(fx)),
        "single": int(np.count_nonzero(is_single & ~drop)),
        "row": int(np.count_nonzero(~is_single & ~drop)),
        "single_on_road": int(np.count_nonzero(is_single & on_road)),
        "row_on_road": int(np.count_nonzero(~is_single & on_road)),
        "mapped_in_building": int(np.count_nonzero(in_building & ~out)),
        "mapped_outside": int(np.count_nonzero(out))}
    mx, my, m_kind, m_h = mx[~drop], my[~drop], m_kind[~drop], m_h[~drop]

    trees = Trees()
    trees.x = np.concatenate([fx, mx])
    trees.y = np.concatenate([fy, my])
    trees.kind = np.concatenate([f_kind, m_kind])
    trees.h = np.concatenate([f_h, m_h])
    # crown width relative to the height, the models are drawn for 1.0
    trees.w = trees.h * rng.uniform(0.8, 1.2, len(trees.x))
    trees.collide = np.concatenate([f_collide, np.ones(len(mx), bool)])
    trees.angle = rng.uniform(0.0, 2 * np.pi, len(trees.x))
    tint = rng.uniform(0.82, 1.12, (len(trees.x), 3))
    tint[:, 2] *= 0.9
    trees.tint = tint
    trees.kinds = KINDS[biome]
    if med:
        _add_maquis(trees, cover, half, road_tree, road_half,
                    building_tree, building_clear, blocked, stats)
    trees.ground = ground.height(trees.x, trees.y) - base - SINK
    stats.update(total=int(len(trees.x)),
                 conifer=int(np.count_nonzero(trees.kind == 1)),
                 collide=int(np.count_nonzero(trees.collide)))
    trees.stats = stats
    return trees


def _add_maquis(trees, cover, half, road_tree, road_half, building_tree,
                building_clear, blocked, stats):
    """Shrubs and a few holm oaks on scrub outside forest and rock,
    appended to trees (own RNG, so the other trees stay the same)."""
    scrub = cover.get("scrub")
    if scrub is None:
        stats["shrub"] = 0
        return
    rng = np.random.default_rng(SEED + 1)
    hx, hy = np.broadcast_to(half, 2)
    gx, gy = np.meshgrid(np.arange(int(2 * hx / SHRUB_STEP)),
                         np.arange(int(2 * hy / SHRUB_STEP)))
    sx = -hx + (gx.ravel() + 0.5) * SHRUB_STEP
    sy = -hy + (gy.ravel() + 0.5) * SHRUB_STEP
    sx = sx + rng.uniform(-SHRUB_JITTER, SHRUB_JITTER, len(sx))
    sy = sy + rng.uniform(-SHRUB_JITTER, SHRUB_JITTER, len(sy))
    keep = shapely.contains_xy(scrub, sx, sy)
    sx, sy = sx[keep], sy[keep]
    keep = ~blocked(sx, sy)
    for kind in ("forest", "rock"):
        if cover.get(kind) is not None:
            keep &= ~shapely.contains_xy(cover[kind], sx, sy)
    sx, sy = sx[keep], sy[keep]
    keep = ~(_near(road_tree, road_half + SHRUB_ROAD_CLEAR, sx, sy)
             | _near(building_tree, building_clear, sx, sy))
    sx, sy = sx[keep], sy[keep]
    oak = rng.random(len(sx)) < MAQUIS_OAK_SHARE
    kind = np.where(oak, 0, 3)
    h = np.where(oak, rng.uniform(*MAQUIS_OAK_H, len(sx)),
                 rng.uniform(*SHRUB_H, len(sx)))
    w = h * np.where(oak, rng.uniform(0.8, 1.2, len(sx)),
                     rng.uniform(1.3, 1.9, len(sx)))
    tint = rng.uniform(0.82, 1.12, (len(sx), 3))
    tint[:, 2] *= 0.9
    trees.x = np.concatenate([trees.x, sx])
    trees.y = np.concatenate([trees.y, sy])
    trees.kind = np.concatenate([trees.kind, kind])
    trees.h = np.concatenate([trees.h, h])
    trees.w = np.concatenate([trees.w, w])
    trees.collide = np.concatenate([trees.collide,
                                    np.zeros(len(sx), bool)])
    trees.angle = np.concatenate([trees.angle,
                                  rng.uniform(0.0, 2 * np.pi, len(sx))])
    trees.tint = np.concatenate([trees.tint, tint])
    stats["shrub"] = int(np.count_nonzero(~oak))
    stats["maquis_oak"] = int(np.count_nonzero(oak))


def emit_trees(trees, tiles, tile_m, out):
    """Write <tile>.trees and <tile>.trunks; returns the meta entry."""
    hx, hy = np.broadcast_to(tiles.half, 2)
    ti = np.floor((trees.x + hx) / tile_m).astype(int)
    tj = np.floor((trees.y + hy) / tile_m).astype(int)
    per = int(round(tile_m / CHUNK))
    ci = np.clip(np.floor((trees.x + hx - ti * tile_m) / CHUNK), 0,
                 per - 1).astype(int)
    cj = np.clip(np.floor((trees.y + hy - tj * tile_m) / CHUNK), 0,
                 per - 1).astype(int)
    chunk = ci + per * cj
    c, s = np.cos(trees.angle), np.sin(trees.angle)
    w, h = trees.w, trees.h
    o = xyz(trees.x, trees.ground, trees.y)
    zero = np.zeros(len(w))
    one = np.ones(len(w))
    # rows of the basis (rotation about Y, scaled) with the origin last
    buf = np.column_stack([
        w * c, zero, w * s, o[:, 0],
        zero, h, zero, o[:, 1],
        -w * s, zero, w * c, o[:, 2],
        trees.tint, one]).astype(np.float32)
    entries = []
    for (i, j) in sorted(tiles.buckets):
        name = f"tile_{i:02d}_{j:02d}"
        sel = np.flatnonzero((ti == i) & (tj == j))
        order = sel[np.lexsort((chunk[sel], trees.kind[sel]))]
        counts = [np.bincount(chunk[sel][trees.kind[sel] == k],
                              minlength=per * per).tolist()
                  for k in range(len(trees.kinds))]
        trunk = sel[trees.collide[sel]]
        # empty files are left out (a ZIP reader refuses empty entries)
        for path, data in ((out / f"{name}.trees", buf[order]),
                           (out / f"{name}.trunks",
                            o[trunk].astype(np.float32))):
            path.unlink(missing_ok=True)
            if len(data):
                data.tofile(path)
        entries.append({"name": name, "counts": counts,
                        "trunks": int(len(trunk))})
    return {"kinds": list(trees.kinds), "chunk_m": CHUNK, "tiles": entries}
# - revised 2026-10-23 (biomes: mediterranean kinds and the maquis)
# - revised 2026-10-23 (rectangular playable area)
# - revised 2026-10-25 (narrow clearing along tracks)
# - revised 2026-10-27 (mediterranean-dry takes the mediterranean kinds)
