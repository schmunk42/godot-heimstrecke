# file generated with AI assistance: Claude Code - 2026-10-23 00:30:00 UTC
"""Camera scout: finds places in the road network by street name and
writes a viewpoint file for godot/tools/render_views.gd.

The curated views (godot/tools/viewpoints.json) look down from 50-60 m;
a 0.25 m bank or a lane taper is invisible from there. A scene fixture
(worlds/<id>/scenes.json, next to the world recipe) names a street, a
mode and a camera recipe; this script builds the road network the way
build.py does (same extract, DGM1 and the recipe's centre and size, so
the heights are the drawn road surface) and turns every scene into a
low or oblique camera:

    uv run python pipeline/scout.py data/out/worlds/stuttgart/extract.pkl \\
        --recipe worlds/stuttgart/world.json \\
        --out godot/tools/viewpoints_polish.json

--scenes defaults to scenes.json beside the recipe, --world (the built
world, for its route and DGM1 file name) to data/out/worlds/<id>.

A scene has `name`, `streets` (1 or 2 names, exact or else substring
match), `mode`, `height_m` (camera above the road), `back_m` (camera
behind the look-at point along the road; negative for the other
direction) and `hint` (one sentence, the snippet description). Modes:

- edge: the middle of the longest matching edge, looking along it;
  optional `kind` (ground, bridge, tunnel; default ground), `sidewalk`
  (both, one, none) and `near` [x, y] (local metres: the matching sample
  nearest to it instead of the middle); with a second street the sample
  nearest to it but EDGE_CLEAR_M clear of the junction
- junction: the node where both streets meet (most arms); with one street
  the centre of its roundabout, or its node with the most arms
- median: the sample of the street whose gap to an opposite carriageway
  of the same name is closest to `gap_m` (default and minimum
  MEDIAN_MIN_GAP: the narrowest median)
- portal: the tunnel portal node of the street (or the portal nearest to
  `near`), the camera outside on the ground edge
- taper: the degree-2 node of the street with the largest width step
- route: the middle of the longest run of route points (world.json) whose
  nearest edge has `kind`
- waypoint: copies `waypoint` and `offset` (render_views.gd waypoint view)

Without `streets`, edge and portal pick from all edges (give `near`).
A scene whose street is not found prints a warning and is skipped.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import shapely
from bridges import raise_decks
from build import DGM1_MARGIN, Tiles, add_sea, load_extract, split_areas
from frame import Frame
from roads import build_road_network
from sidewalks import assign as assign_sidewalks
from terrain import Dgm1Raster
from world import RecipeError, load_recipe

HEADER = "file generated with AI assistance: Claude Code - " \
         "2026-10-23 00:30:00 UTC"
# a sample closer than this to an edge end is a junction, not a median
MEDIAN_END_M = 20.0
MEDIAN_MIN_GAP = 1.0
# opposite carriageway: tangents at least this much apart (cos)
OPPOSITE_COS = -0.7
# edge mode with a second street: this far from it (past the junction)
EDGE_CLEAR_M = 30.0
# the camera takes the road height of the nearest street sample within
# this distance, else the terrain
CAM_SNAP_M = 10.0


class Scout:
    """The road network with per-sample helpers for the scene modes."""

    def __init__(self, net, dem, base, route):
        self.net, self.dem, self.base = net, dem, base
        self.route = route
        self.p = np.column_stack([net.sx, net.sy])
        self.names = [e["tags"].get("name", "") for e in net.edges]

    def edges_named(self, name):
        exact = [i for i, n in enumerate(self.names) if n == name]
        return np.array(exact or [i for i, n in enumerate(self.names)
                                  if name and name in n], dtype=int)

    def samples(self, edges):
        net = self.net
        return np.concatenate([np.arange(net.start[e], net.start[e + 1])
                               for e in edges]) if len(edges) else \
            np.zeros(0, dtype=int)

    def node_height(self, k):
        """Mean surface of the edge ends at node k."""
        net = self.net
        first, last = net.start[:-1], net.start[1:] - 1
        s = np.concatenate([first[net.u == k], last[net.v == k]])
        return float(net.surface[s].mean())

    def node_dir(self, k, edges):
        """Unit direction away from node k along the first of `edges`
        that touches it."""
        net = self.net
        for e in edges:
            if net.u[e] == k:
                s = net.start[e]
                return unit(self.p[min(s + 3, net.start[e + 1] - 1)]
                            - self.p[s])
            if net.v[e] == k:
                s = net.start[e + 1] - 1
                return unit(self.p[max(s - 3, net.start[e])] - self.p[s])
        return np.array([1.0, 0.0])

    def ground_height(self, xy, pool):
        """Road height under the camera: the nearest sample of `pool`
        within CAM_SNAP_M, else the DGM1 terrain."""
        if len(pool):
            d = np.hypot(*(self.p[pool] - xy).T)
            i = int(np.argmin(d))
            if d[i] <= CAM_SNAP_M:
                return float(self.net.surface[pool[i]])
        return float(self.dem.height(xy[0], xy[1])) - self.base

    def view(self, sc, at, h, direction, pool):
        """Camera back_m behind `at` against `direction`, height_m above
        the higher of the road at both ends."""
        cam = at - direction * sc["back_m"]
        ch = max(h, self.ground_height(cam, pool)) + sc["height_m"]
        return {"name": sc["name"],
                "position": [r1(cam[0]), r1(ch), r1(-cam[1])],
                "look_at": [r1(at[0]), r1(h), r1(-at[1])]}

    def filter_edges(self, edges, sc):
        net = self.net
        kind = sc.get("kind", "ground")
        keep = (net.kind[edges] == kind) if kind != "ground" \
            else ~net.struct[edges]
        side = sc.get("sidewalk")
        if side is not None:
            n = net.walk[edges].sum(axis=1)
            keep &= {"both": n == 2, "one": n == 1, "none": n == 0}[side]
        return edges[keep]

    def edge(self, sc, edges, other):
        net = self.net
        edges = self.filter_edges(edges, sc)
        if not len(edges):
            return None, "no edge with kind/sidewalk filter"
        pool = self.samples(edges)
        if "near" in sc:
            s = pool[int(np.argmin(np.hypot(
                *(self.p[pool] - np.array(sc["near"])).T)))]
            how = f"sample nearest to {sc['near']}"
        elif other is not None:
            far = shapely.STRtree(shapely.points(
                self.p[self.samples(other)]))
            _, d = far.query_nearest(shapely.points(self.p[pool]),
                                     return_distance=True,
                                     all_matches=False)
            d = np.where(d >= EDGE_CLEAR_M, d, np.inf)
            if not np.isfinite(d).any():
                return None, "no sample clear of the second street"
            s = pool[int(np.argmin(d))]
            how = f"nearest sample {EDGE_CLEAR_M:.0f} m clear of the " \
                  "second street"
        else:
            e = edges[int(np.argmax(net.length[edges]))]
            s = (net.start[e] + net.start[e + 1]) // 2
            how = f"middle of longest edge (way {net.edges[e]['way']})"
        return self.view(sc, self.p[s], float(net.surface[s]),
                         net.tangent[s], pool), how

    def junction(self, sc, edges, other):
        net = self.net
        if other is not None:
            a = np.concatenate([net.u[edges], net.v[edges]])
            b = np.concatenate([net.u[other], net.v[other]])
            common = np.intersect1d(a, b)
            if not len(common):
                return None, "streets do not meet"
            k = common[int(np.argmax(net.degree[common]))]
            at, how = net.xy[k], f"node of both streets, {net.degree[k]} arms"
            d = self.node_dir(k, edges)
        else:
            ring = [e for e in edges
                    if net.edges[e]["tags"].get("junction") == "roundabout"]
            nodes = np.unique(np.concatenate([net.u[edges], net.v[edges]]))
            if ring:
                at = np.vstack([net.edges[e]["coords"] for e in ring]) \
                    .mean(axis=0)
                k = nodes[int(np.argmax(net.degree[nodes]))]
                d = unit(net.xy[k] - at)
                how = f"roundabout centre of {len(ring)} edges"
            else:
                k = nodes[int(np.argmax(net.degree[nodes]))]
                at, d = net.xy[k], self.node_dir(k, edges)
                how = f"street node with {net.degree[k]} arms"
        h = self.node_height(k)
        pool = self.samples(np.concatenate([edges] + (
            [other] if other is not None else [])))
        # node_dir points away from the node: the camera stands on it
        return self.view(sc, at, h, -d, pool), how

    def median(self, sc, edges):
        net = self.net
        edges = edges[~net.struct[edges]]
        pool = self.samples(edges)
        if len(edges) < 2:
            return None, "fewer than two carriageway edges"
        e = net.edge_of[pool]
        end = np.minimum(net.dist[pool] - net.cut_u[e],
                         net.length[e] - net.cut_v[e] - net.dist[pool])
        pool = pool[end > MEDIAN_END_M]
        target = sc.get("gap_m", MEDIAN_MIN_GAP)
        best = None
        for s in pool:
            other = pool[(net.edge_of[pool] != net.edge_of[s])
                         & (net.tangent[pool] @ net.tangent[s]
                            < OPPOSITE_COS)]
            if not len(other):
                continue
            d = np.hypot(*(self.p[other] - self.p[s]).T)
            i = int(np.argmin(d))
            gap = d[i] - net.half[s] - net.half[other[i]]
            miss = abs(gap - target)
            if gap >= MEDIAN_MIN_GAP and (best is None or miss < best[0]):
                best = (miss, gap, s, other[i])
        if best is None:
            return None, "no opposite carriageway"
        _, gap, s, o = best
        at = (self.p[s] + self.p[o]) / 2
        h = float(net.surface[s] + net.surface[o]) / 2
        return self.view(sc, at, h, net.tangent[s], self.samples(edges)), \
            f"median gap {gap:.1f} m"

    def portal(self, sc, edges):
        net = self.net
        tunnel = net.kind == "tunnel"
        ground = ~net.struct
        n = len(net.ids)
        on = np.zeros(n, dtype=bool)
        for sel in (tunnel, ground):
            t = np.zeros(n, dtype=bool)
            t[net.u[sel]] = t[net.v[sel]] = True
            on = t if sel is tunnel else on & t
        cand = np.flatnonzero(on)
        if len(edges):
            mine = np.concatenate([net.u[edges], net.v[edges]])
            named = np.intersect1d(cand, mine)
            # the portal of a named tunnel edge, else any of the street
            tn = edges[tunnel[edges]]
            tn_nodes = np.intersect1d(
                cand, np.concatenate([net.u[tn], net.v[tn]]))
            cand = tn_nodes if len(tn_nodes) else named
        if "near" in sc and len(cand):
            k = cand[int(np.argmin(np.hypot(
                *(net.xy[cand] - np.array(sc["near"])).T)))]
        elif len(cand):
            k = cand[0]
        else:
            return None, "no tunnel portal"
        out = np.flatnonzero(ground & ((net.u == k) | (net.v == k)))
        d = self.node_dir(k, out)
        # the camera stands outside on the ramp, looking into the portal
        return self.view(sc, net.xy[k], self.node_height(k), -d,
                         self.samples(out)), f"portal node {net.ids[k]}"

    def taper(self, sc, edges):
        net = self.net
        nodes = np.unique(np.concatenate([net.u[edges], net.v[edges]]))
        best = None
        for k in nodes[net.degree[nodes] == 2]:
            at = np.flatnonzero((net.u == k) | (net.v == k))
            step = abs(net.width[at[0]] - net.width[at[-1]])
            if step > 1e-6 and (best is None or step > best[0]):
                best = (step, k)
        if best is None:
            return None, "no tapered node"
        step, k = best
        return self.view(sc, net.xy[k], self.node_height(k),
                         -self.node_dir(k, edges), self.samples(edges)), \
            f"taper node, width step {step:.1f} m"

    def route_run(self, sc):
        net = self.net
        if not self.route:
            return None, "world has no route"
        r = np.array(self.route)
        x, h, y = r[:, 0], r[:, 1], -r[:, 2]
        k = np.flatnonzero(net.edge_of[:-1] == net.edge_of[1:])
        tree = shapely.STRtree(shapely.linestrings(np.stack(
            [self.p[k], self.p[k + 1]], axis=1)))
        (_, i) = tree.query_nearest(shapely.points(x, y),
                                    all_matches=False)
        hit = net.kind[net.edge_of[k[i]]] == sc.get("kind", "tunnel")
        if not hit.any():
            return None, "route has no point on such an edge"
        # longest run of consecutive hits
        edges = np.flatnonzero(np.diff(np.concatenate([[0], hit, [0]])))
        starts, ends = edges[::2], edges[1::2]
        j = int(np.argmax(ends - starts))
        m = (starts[j] + ends[j]) // 2
        at = np.array([x[m], y[m]])
        d = unit(np.array([x[m + 1] - x[m - 1], y[m + 1] - y[m - 1]]))
        pool = np.unique(k[i[starts[j]:ends[j]]])
        name = self.names[net.edge_of[pool[0]]] or "unnamed"
        return self.view(sc, at, float(h[m]), d, pool), \
            f"route points {starts[j]}-{ends[j] - 1} on {name}"

    def scene(self, sc):
        mode = sc["mode"]
        if mode == "waypoint":
            v = {"name": sc["name"], "waypoint": sc["waypoint"]}
            if "offset" in sc:
                v["offset"] = sc["offset"]
            return v, f"waypoint {sc['waypoint']}"
        if mode == "route":
            return self.route_run(sc)
        streets = sc.get("streets", [])
        # no street: every edge, the scene picks by `near` or `kind`
        edges = self.edges_named(streets[0]) if streets else \
            np.arange(len(self.names))
        if streets and not len(edges):
            return None, f"street {streets[0]!r} not found"
        other = None
        if len(streets) > 1:
            other = self.edges_named(streets[1])
            if not len(other):
                return None, f"street {streets[1]!r} not found"
        if mode == "edge":
            return self.edge(sc, edges, other)
        if mode == "junction":
            return self.junction(sc, edges, other)
        if mode == "median":
            return self.median(sc, edges)
        if mode == "portal":
            return self.portal(sc, edges)
        if mode == "taper":
            return self.taper(sc, edges)
        return None, f"unknown mode {mode!r}"


def unit(v):
    return v / (np.linalg.norm(v) + 1e-12)


def r1(v):
    return round(float(v), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("extract", type=Path)
    ap.add_argument("--recipe", type=Path, required=True,
                    help="world recipe (worlds/<id>/world.json): centre, "
                    "size and world id")
    ap.add_argument("--scenes", type=Path,
                    help="scene fixture (default scenes.json beside the "
                    "recipe)")
    ap.add_argument("--world", type=Path,
                    help="built world: world.json (route, DGM1 file name); "
                    "default data/out/worlds/<id>")
    ap.add_argument("--terrain", type=Path,
                    help="terrain GeoTIFF (default data/raw/ + the "
                         "world's terrain_source and terrain_file)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    try:
        recipe = load_recipe(args.recipe)
    except RecipeError as err:
        sys.exit(f"error: {err}")
    scenes_path = args.scenes or recipe.path.parent / "scenes.json"
    world = args.world or Path("data/out/worlds") / recipe.id
    meta = json.loads((world / "world.json").read_text())
    terrain = args.terrain or (Path("data/raw") / meta["terrain_source"]
                               / meta["terrain_file"])
    lat, lon = recipe.center
    frame = Frame(lon, lat, recipe.heading_deg, recipe.epsg)
    tiles = Tiles(recipe.size_km, recipe.width_km)
    dem = Dgm1Raster(terrain, frame, tiles.half + DGM1_MARGIN)
    ex = load_extract(args.extract)
    add_sea(ex, frame, dem)
    base = float(dem.height(0.0, 0.0))
    net = build_road_network(ex, frame, dem, base, tiles.half + DGM1_MARGIN)
    cover, buildings = split_areas(ex, frame)
    assign_sidewalks(net, cover["urban"], buildings)
    raise_decks(net)
    scout = Scout(net, dem, base, meta.get("route"))

    scenes = json.loads(scenes_path.read_text())["scenes"]
    views = []
    for sc in scenes:
        view, how = scout.scene(sc)
        if view is None:
            print(f"warning: scene {sc['name']}: {how}, skipped",
                  file=sys.stderr)
            continue
        if sc.get("hint"):
            view["hint"] = sc["hint"]
        views.append(view)
        at = view.get("look_at")
        where = f"x={at[0]:.1f} y={-at[2]:.1f} h={at[1]:.1f}" if at \
            else "-"
        print(f"{sc['name']}: {where} ({how})")
    args.out.write_text(json.dumps({
        "_comment": HEADER + "; low and oblique views written by "
                    f"pipeline/scout.py from {scenes_path.name}",
        "views": views}, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(views)} of {len(scenes)} scenes -> {args.out}")


if __name__ == "__main__":
    main()
# - revised 2026-10-23 (world recipe instead of --center/--size)
# - revised 2026-10-23 (terrain path from terrain_source, sea filled like build.py)
# - revised 2026-10-23 (rectangular, turned worlds)
# - revised 2026-10-25 (default sidewalks in town only, as in build.py)
