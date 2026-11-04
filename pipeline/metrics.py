# file generated with AI assistance: Claude Code - 2026-10-20 21:15:00 UTC
"""Per-build report: metrics.json and metrics.md next to the tiles.

Everything except the `run` section is deterministic. The hard gates
are listed in HARD_GATES (build.py exits with code 3 if one fails):
shared heights at nodes in the exported tiles (0.05 m), conformed
terrain below every road strip, the largest grade of the drawn road
surface (25 %) and the distance of smoothed ground node heights from
their DGM1 median (2 m). Everything else is reported only.
"""
import json
import socket
import time
from pathlib import Path

import numpy as np
import shapely
import trimesh

SEED = 20261020
# hard gates in report order: key in report["gates"] -> markdown label
HARD_GATES = {
    "shared_heights": "shared heights at nodes",
    "terrain_below_roads": "terrain below every road strip",
    "max_grade": "largest grade of the drawn surface <= 25 %",
    "node_heights": "ground node heights within 2 m of DGM1",
}
MAX_GRADE = 0.25
NODE_DEV_MAX = 2.0
NODE_DEV_P95 = 0.5
# DGM1 grade at a steep section this close to the road grade: terrain
TERRAIN_SHARE = 0.7
SHORT_EDGE = 10.0
STRUCTURE_KINDS = ("bridge", "tunnel", "building_passage", "culvert",
                   "covered")
GATE_TOLERANCE = 0.05
COMPONENT_SHARE = 0.99
BUDGET_S = 900.0
BUDGET_BYTES = 400e6
CAP = 50
STEEP = 0.12
# terrain closer than this below the road surface counts as showing through
MIN_CLEARANCE = 0.02
FIDELITY_POINTS = 20000
SEAM_SAMPLES = 2000
# clipping counts of a reference build (the ratchet), next to the recipe
CLIPPING_BASELINE = "clipping_baseline.json"


def num(x, digits=3):
    """JSON-safe rounded float (None for NaN/inf)."""
    x = float(x)
    return round(x, digits) if np.isfinite(x) else None


def pct(values, digits=3):
    values = np.abs(np.asarray(values, dtype=float))
    if len(values) == 0:
        return {"p50": None, "p95": None, "max": None, "n": 0}
    p50, p95 = np.percentile(values, [50, 95])
    return {"p50": num(p50, digits), "p95": num(p95, digits),
            "max": num(values.max(), digits), "n": int(len(values))}


def load_avg():
    return Path("/proc/loadavg").read_text().split()[:3]


def xz_key(x, z):
    """Integer key of glTF (x, z) rounded to the millimetre."""
    kx = np.rint(np.asarray(x, dtype=np.float64) * 1000).astype(np.int64)
    kz = np.rint(np.asarray(z, dtype=np.float64) * 1000).astype(np.int64)
    return ((kx + (1 << 30)) << 32) | (kz + (1 << 30))


def as_float32(a):
    return np.asarray(a, dtype=np.float32).astype(np.float64)


def load_roads(out_dir):
    """`roads` vertices per tile file: {name: (N, 3) float64}."""
    tiles = {}
    for path in sorted(out_dir.glob("tile_*.glb")):
        scene = trimesh.load(path, force="scene")
        geom = scene.geometry.get("roads")
        if geom is not None:
            tiles[path.name] = np.asarray(geom.vertices, dtype=np.float64)
    return tiles


class VertexIndex:
    """Sorted (x, z) keys with min/max height per key."""

    def __init__(self, verts):
        keys = xz_key(verts[:, 0], verts[:, 2])
        order = np.argsort(keys, kind="stable")
        keys, h = keys[order], verts[order, 1]
        self.keys, first = np.unique(keys, return_index=True)
        if len(keys):
            self.hmin = np.minimum.reduceat(h, first)
            self.hmax = np.maximum.reduceat(h, first)
        else:
            self.hmin = self.hmax = np.zeros(0)

    def find(self, keys):
        pos = np.searchsorted(self.keys, keys)
        pos = np.minimum(pos, max(len(self.keys) - 1, 0))
        found = (self.keys[pos] == keys) if len(self.keys) else \
            np.zeros(len(keys), dtype=bool)
        return found, pos


def shared_heights(net, index):
    node = net.expected_node
    keys = xz_key(as_float32(net.expected_xz[:, 0]),
                  as_float32(net.expected_xz[:, 1]))
    found, pos = index.find(keys)
    nodes = np.unique(node)
    n = len(net.ids)
    hi = np.full(n, -np.inf)
    lo = np.full(n, np.inf)
    np.maximum.at(hi, node[found], index.hmax[pos[found]])
    np.minimum.at(lo, node[found], index.hmin[pos[found]])
    missing = np.zeros(n, dtype=int)
    np.add.at(missing, node[~found], 1)
    dev = np.where(np.isfinite(hi) & np.isfinite(lo), hi - lo, np.inf)
    exp = as_float32(net.expected_height)
    off = np.maximum(np.abs(hi - exp), np.abs(lo - exp))
    dev_n = dev[nodes]
    complete = missing[nodes] == 0
    bad = (dev_n > GATE_TOLERANCE) | ~complete
    worst = nodes[np.lexsort((nodes, -np.where(np.isfinite(dev_n), dev_n,
                                                1e9)))][:20]
    classes = node_classes(net)
    passed = bool(len(nodes) > 0 and not bad.any())
    finite = dev_n[np.isfinite(dev_n)]
    return {
        "tolerance_m": GATE_TOLERANCE,
        "nodes_checked": int(len(nodes)),
        "nodes_all_vertices_found": int(np.count_nonzero(complete)),
        "vertices_expected": int(len(keys)),
        "vertices_missing": int(np.count_nonzero(~found)),
        "max_deviation_m": num(finite.max() if len(finite) else 0, 4),
        "nodes_above_tolerance": int(np.count_nonzero(
            dev_n > GATE_TOLERANCE)),
        "max_offset_from_expected_m": num(
            np.max(off[nodes][complete]) if complete.any() else 0, 4),
        "nodes_skipped_outside_tiles": int(np.count_nonzero(
            (net.degree >= 2) & ~net.inside)),
        "worst": [{"node": int(net.ids[k]),
                   "deviation_m": num(dev[k], 4) if np.isfinite(dev[k])
                   else None,
                   "missing_vertices": int(missing[k]),
                   "classes": classes[k]} for k in worst],
        "passed": passed,
    }


def node_classes(net):
    out = {}
    for i, e in enumerate(net.edges):
        cls = e["tags"]["highway"]
        for k in (int(net.u[i]), int(net.v[i])):
            out.setdefault(k, set()).add(cls)
    return {k: sorted(v) for k, v in out.items()}


def seams(tiles, half, tile_m):
    """Roads vertices on or beyond their tile's border vs the neighbour."""
    hx, hy = np.broadcast_to(half, 2)
    nx, ny = int(round(2 * hx / tile_m)), int(round(2 * hy / tile_m))
    index = {name: VertexIndex(v) for name, v in tiles.items()}
    cand = []
    for name, v in tiles.items():
        i, j = int(name[5:7]), int(name[8:10])
        x0, y0 = -hx + i * tile_m, -hy + j * tile_m
        x, y = v[:, 0], -v[:, 2]
        near = ((x < x0 + 0.01) | (x > x0 + tile_m - 0.01)
                | (y < y0 + 0.01) | (y > y0 + tile_m - 0.01))
        inside = (np.abs(x) < hx - 0.01) & (np.abs(y) < hy - 0.01)
        for k in np.flatnonzero(near & inside):
            cand.append((name, k))
    rng = np.random.default_rng(SEED)
    if len(cand) > SEAM_SAMPLES:
        pick = np.sort(rng.choice(len(cand), SEAM_SAMPLES, replace=False))
        cand = [cand[k] for k in pick]
    found = mismatch = 0
    worst = 0.0
    for name, k in cand:
        v = tiles[name][k]
        x, y = v[0], -v[2]
        best = None
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                i = int(np.floor((x + hx) / tile_m)) + di
                j = int(np.floor((y + hy) / tile_m)) + dj
                other = f"tile_{i:02d}_{j:02d}.glb"
                if other == name or other not in index or not (
                        0 <= i < nx and 0 <= j < ny):
                    continue
                x0, y0 = -hx + i * tile_m, -hy + j * tile_m
                if not (x0 - 0.01 <= x <= x0 + tile_m + 0.01
                        and y0 - 0.01 <= y <= y0 + tile_m + 0.01):
                    continue
                ok, pos = index[other].find(xz_key([v[0]], [v[2]]))
                if ok[0]:
                    d = max(abs(index[other].hmax[pos[0]] - v[1]),
                            abs(index[other].hmin[pos[0]] - v[1]))
                    best = d if best is None else min(best, d)
        if best is not None:
            found += 1
            worst = max(worst, best)
            mismatch += best > 0.001
    return {"vertices_checked": len(cand), "with_counterpart": found,
            "without_counterpart": len(cand) - found,
            "height_mismatches": int(mismatch),
            "max_height_difference_m": num(worst, 4)}


def node_labels(n, u, v):
    """Smallest node index of each node's component over edges u-v."""
    label = np.arange(n)
    while True:
        m = np.minimum(label[u], label[v])
        new = label.copy()
        np.minimum.at(new, u, m)
        np.minimum.at(new, v, m)
        new = new[new]
        if np.array_equal(new, label):
            return label
        label = new


def components(net):
    label = node_labels(len(net.ids), net.u, net.v)
    comp = label[net.u]
    roots, inverse = np.unique(comp, return_inverse=True)
    km = np.bincount(inverse, net.length) / 1000
    count = np.bincount(inverse)
    touches = np.zeros(len(roots), dtype=bool)
    bnode = net.boundary[net.u] | net.boundary[net.v]
    touches[inverse[bnode]] = True
    order = np.lexsort((roots, -km))
    total = km.sum()
    others = []
    for c in order[1:]:
        ways = []
        for e in np.flatnonzero(inverse == c):
            w = int(net.edges[e]["way"])
            if w not in ways:
                ways.append(w)
            if len(ways) == 3:
                break
        others.append({"km": num(km[c]), "edges": int(count[c]),
                       "reason": "boundary" if touches[c] else "osm_gap",
                       "ways": ways})
        if len(others) == CAP:
            break
    share = km[order[0]] / total if total else 0.0
    reasons = np.where(touches, "boundary", "osm_gap")[order[1:]]
    return {"count": int(len(roots)),
            "largest_km": num(km[order[0]]),
            "largest_share": num(share, 5),
            "threshold": COMPONENT_SHARE,
            "passed": bool(share >= COMPONENT_SHARE),
            "others_total": int(len(roots) - 1),
            "others_boundary": int(np.count_nonzero(reasons ==
                                                    "boundary")),
            "others_osm_gap": int(np.count_nonzero(reasons == "osm_gap")),
            "others_km": num(total - km[order[0]]),
            "others": others}


def roads_block(net):
    per = {}
    for i, e in enumerate(net.edges):
        cls = e["tags"]["highway"]
        row = per.setdefault(cls, {"edges": 0, "km": 0.0})
        row["edges"] += 1
        row["km"] += net.length[i] / 1000
    per = {k: {"edges": v["edges"], "km": num(v["km"])}
           for k, v in sorted(per.items(), key=lambda kv: -kv[1]["km"])}
    return {"per_class": per, "km_total": num(net.length.sum() / 1000),
            "excluded_ways": dict(sorted(net.excluded.items())),
            "note": "service roads are dropped at extract time and not "
                    "counted here; the most specific access tag decides "
                    "(motor_vehicle, vehicle, access)"}


def graph_block(net):
    deg = np.bincount(net.degree)
    return {"nodes": int(len(net.ids)), "edges": int(len(net.edges)),
            "boundary_nodes": int(np.count_nonzero(net.boundary)),
            "degree_histogram": {str(d): int(c) for d, c in enumerate(deg)
                                 if c},
            "junction_nodes": int(np.count_nonzero(net.junction)),
            "junction_surfaces": int(net.junctions),
            "edge_ends_too_short_to_cut": int(net.too_short),
            "structure_nodes_interpolated": int(net.structure_nodes),
            "components": components(net)}


def links_block(net):
    ways = set()
    count = 0
    for i, e in enumerate(net.edges):
        if not e["tags"]["highway"].endswith("_link"):
            continue
        count += 1
        for k in (net.u[i], net.v[i]):
            if net.degree[k] == 1 and not net.boundary[k]:
                ways.add(int(e["way"]))
    ways = sorted(ways)
    return {"link_edges": count, "dangling_link_ways": len(ways),
            "ways": ways[:CAP]}


def crossings(net):
    """Edges whose geometries cross without a shared node."""
    sel = np.flatnonzero(net.inside[net.u] | net.inside[net.v])
    lines = np.array([shapely.LineString(net.edges[i]["coords"])
                      for i in sel])
    tree = shapely.STRtree(lines)
    a, b = tree.query(lines, predicate="crosses")
    keep = a < b
    a, b = sel[a[keep]], sel[b[keep]]
    counts = {"layer_differs": 0, "bridge": 0, "tunnel": 0,
              "unexplained": 0}
    listed = []
    for i, j in sorted(zip(a.tolist(), b.tolist())):
        if {net.u[i], net.v[i]} & {net.u[j], net.v[j]}:
            continue
        ti, tj = net.edges[i]["tags"], net.edges[j]["tags"]
        kind = "unexplained"
        if ti.get("layer", "0") != tj.get("layer", "0"):
            kind = "layer_differs"
        elif "no" != ti.get("bridge", "no") or "no" != tj.get("bridge",
                                                              "no"):
            kind = "bridge"
        elif "no" != ti.get("tunnel", "no") or "no" != tj.get("tunnel",
                                                              "no"):
            kind = "tunnel"
        counts[kind] += 1
        if kind == "unexplained":
            pair = sorted([int(net.edges[i]["way"]),
                           int(net.edges[j]["way"])])
            if pair not in listed:
                listed.append(pair)
    listed.sort()
    return {"pairs": int(sum(counts.values())), **counts,
            "unexplained_way_pairs": len(listed),
            "unexplained_list": listed[:CAP]}


def in_area(x, y, half):
    hx, hy = np.broadcast_to(half, 2)
    return (np.abs(x) < hx) & (np.abs(y) < hy)


def steep_reason(net, edge, grade, terrain, at_struct):
    """Why a steep section is steep, most specific first."""
    if net.struct[edge] or at_struct[net.u[edge]] \
            or at_struct[net.v[edge]]:
        return "structure_end"
    if abs(terrain) >= TERRAIN_SHARE * abs(grade):
        return "terrain"
    if net.length[edge] < SHORT_EDGE:
        return "short_edge"
    return "osm"


def slope(net, dem, base, half, dem_half):
    """Grades of the drawn surface; steep sections with their reason.

    A section next to a bridge or tunnel is `structure_end` even where
    DGM1 is as steep as the road: there the DGM1 step is the abutment or
    portal, not a hill.
    """
    s = np.arange(len(net.sx) - 1)
    same = net.edge_of[s] == net.edge_of[s + 1]
    ds = net.dist[s + 1] - net.dist[s]
    mx = (net.sx[s] + net.sx[s + 1]) / 2
    my = (net.sy[s] + net.sy[s + 1]) / 2
    seg = s[same & (ds >= 1.0) & in_area(mx, my, half)]
    grade = (net.surface[seg + 1] - net.surface[seg]) / ds[seg]
    absg = np.abs(grade)
    steep = absg > STEEP
    # runs of consecutive steep segments on the same edge
    runs = []
    k = 0
    while k < len(seg):
        if not steep[k]:
            k += 1
            continue
        j = k
        while (j + 1 < len(seg) and steep[j + 1]
               and seg[j + 1] == seg[j] + 1
               and net.edge_of[seg[j + 1]] == net.edge_of[seg[k]]):
            j += 1
        best = k + int(np.argmax(absg[k:j + 1]))
        runs.append((k, j, best))
        k = j + 1
    sections = []
    if runs:
        best = np.array([r[2] for r in runs])
        p = seg[best]
        cx, cy = mx[p], my[p]
        t = net.tangent[p]
        dx, dy = np.broadcast_to(dem_half, 2)
        h1 = dem.height(np.clip(cx + 5 * t[:, 0], -dx, dx),
                        np.clip(cy + 5 * t[:, 1], -dy, dy))
        h0 = dem.height(np.clip(cx - 5 * t[:, 0], -dx, dx),
                        np.clip(cy - 5 * t[:, 1], -dy, dy))
        terrain = (h1 - h0) / 10
        at_struct = np.zeros(len(net.ids), dtype=bool)
        at_struct[net.u[net.struct]] = True
        at_struct[net.v[net.struct]] = True
        for n, (k, j, b) in enumerate(runs):
            i = int(net.edge_of[seg[b]])
            e = net.edges[i]
            sections.append({
                "way": int(e["way"]), "name": e["tags"].get("name", ""),
                "class": e["tags"]["highway"],
                "grade_pct": num(absg[b] * 100, 1),
                "terrain_grade_pct": num(abs(terrain[n]) * 100, 1),
                "length_m": num(np.sum(ds[seg[k:j + 1]]), 0),
                "reason": steep_reason(net, i, absg[b], terrain[n],
                                       at_struct),
                "x": num(cx[n], 0), "y": num(cy[n], 0)})
    reasons = {k: 0 for k in ("structure_end", "terrain", "short_edge",
                              "osm")}
    for sec in sections:
        reasons[sec["reason"]] += 1
    sections.sort(key=lambda r: (-r["grade_pct"], r["way"], r["x"]))
    q = np.percentile(absg * 100, [50, 90, 95, 99]) if len(absg) else \
        [np.nan] * 4
    top = float(absg.max()) if len(absg) else 0.0
    return {"segments": int(len(seg)),
            "abs_grade_pct": {"p50": num(q[0], 2), "p90": num(q[1], 2),
                              "p95": num(q[2], 2), "p99": num(q[3], 2),
                              "max": num(top * 100, 2)
                              if len(absg) else None},
            "threshold_pct": STEEP * 100,
            "steep_sections": len(sections),
            "steep_km": num(np.sum(ds[seg[steep]]) / 1000),
            "reasons": reasons,
            "max_grade_pct": num(top * 100, 2),
            "max_grade_limit_pct": num(MAX_GRADE * 100, 1),
            "passed": bool(top <= MAX_GRADE),
            "sections": sections[:30]}


def incident_ways(net):
    """Per node: sorted (way, name) pairs of its incident edges."""
    out = {}
    for i, e in enumerate(net.edges):
        pair = (int(e["way"]), e["tags"].get("name", ""))
        for k in (int(net.u[i]), int(net.v[i])):
            out.setdefault(k, set()).add(pair)
    return {k: sorted(v) for k, v in out.items()}


def node_heights_block(net, half):
    """Smoothed node height - DGM1 3 m median, inside the playable area.

    Ground nodes are gated (max), structure nodes (portals, abutments,
    nodes inside bridge/tunnel chains) take the DGM1 step and are only
    listed.
    """
    inside = in_area(net.xy[:, 0], net.xy[:, 1], half)
    dev = net.height - net.height_raw
    ground = inside & ~net.node_struct
    struct = np.flatnonzero(inside & net.node_struct)
    g = pct(dev[ground])
    portal = pct(dev[inside & net.node_portal])
    worst = struct[np.lexsort((net.ids[struct], -np.abs(dev[struct])))]
    ways = incident_ways(net)
    top = []
    for k in worst[:20]:
        pairs = ways.get(int(k), [])
        top.append({"node": int(net.ids[k]), "deviation_m": num(dev[k]),
                    "ways": [w for w, _ in pairs],
                    "names": sorted({nm for _, nm in pairs if nm})})
    return {
        "ground": {**g, "max_limit_m": NODE_DEV_MAX,
                   "p95_target_m": NODE_DEV_P95,
                   "p95_target_met": bool(g["n"] == 0
                                          or g["p95"] <= NODE_DEV_P95),
                   "passed": bool(g["n"] == 0 or g["max"] <= NODE_DEV_MAX)},
        "structure": {"count": len(struct),
                      "max_m": num(np.abs(dev[struct]).max())
                      if len(struct) else None,
                      "portal": portal,
                      "top": top},
        "relax": net.relax,
    }


def structures_block(net):
    """Edges, chains and km per structure kind inside the playable area."""
    near = net.inside[net.u] | net.inside[net.v]
    out = {}
    for kind in STRUCTURE_KINDS:
        sel = near & (net.kind == kind)
        u, v = net.u[sel], net.v[sel]
        label = node_labels(len(net.ids), u, v)
        out[kind] = {"edges": int(np.count_nonzero(sel)),
                     "chains": len(np.unique(label[u])),
                     "km": num(net.length[sel].sum() / 1000)}
    return {"kinds": out,
            "note": "only bridge and tunnel are treated as structures "
                    "(chord heights, excluded from conform and the "
                    "terrain gates); building passages, culverts and "
                    "covered ways are ground roads"}


def road_vs_terrain(net, dem, base, half, dem_half):
    keep = in_area(net.sx, net.sy, half) & ~net.struct[net.edge_of]
    centre = net.ground[keep] - net.raw[keep]
    edge_h = []
    for side in (net.left, net.right):
        p = side[keep]
        dx, dy = np.broadcast_to(dem_half, 2)
        h = dem.height(np.clip(p[:, 0], -dx, dx),
                       np.clip(p[:, 1], -dy, dy)) - base
        edge_h.append(net.surface[keep] - h)
    return ({**pct(centre),
             "samples_excluded_bridge_tunnel": int(np.count_nonzero(
                 in_area(net.sx, net.sy, half)
                 & net.struct[net.edge_of]))},
            pct(np.concatenate(edge_h)))


def terrain_below_roads(net, ground, base, half):
    """Clearance road surface - conformed terrain at strip centre and
    edges, at 1/16, 5/16, 9/16 and 13/16 between samples (the push-down
    pass in conform.py uses multiples of 1/8, so this is an independent
    check); no
    bridges/tunnels, only points inside the playable square (outside it
    there is no terrain mesh). Below MIN_CLEARANCE the terrain shows
    through."""
    k = np.arange(len(net.sx) - 1)
    k = k[(net.edge_of[k] == net.edge_of[k + 1])
          & ~net.struct[net.edge_of[k]]
          & in_area(net.sx[k], net.sy[k], half)]
    centre = np.column_stack([net.sx, net.sy])
    clear, where, at = [], [], []
    for t in (0.0625, 0.3125, 0.5625, 0.8125):
        surf = net.surface[k] + (net.surface[k + 1] - net.surface[k]) * t
        for p in (centre, net.left, net.right):
            q = p[k] + (p[k + 1] - p[k]) * t
            inside = in_area(q[:, 0], q[:, 1], half)
            clear.append((surf - (ground.height(q[:, 0], q[:, 1])
                                  - base))[inside])
            where.append(k[inside])
            at.append(q[inside])
    clear = np.concatenate(clear)
    where = np.concatenate(where)
    at = np.vstack(at) if at else np.zeros((0, 2))
    bad = clear < MIN_CLEARANCE
    worst = []
    seen = set()
    for k in np.argsort(clear)[:CAP * 200]:
        if not bad[k]:
            break
        e = net.edges[net.edge_of[where[k]]]
        if int(e["way"]) in seen:
            continue
        seen.add(int(e["way"]))
        worst.append({"way": int(e["way"]),
                      "name": e["tags"].get("name", ""),
                      "class": e["tags"]["highway"],
                      "clearance_m": num(clear[k], 2),
                      # local metres, for a viewpoint (glTF z = -y)
                      "x": num(at[k, 0], 1), "y": num(at[k, 1], 1)})
        if len(worst) >= CAP:
            break
    return {"min_clearance_m": MIN_CLEARANCE, **pct(clear),
            "min_m": num(clear.min()) if len(clear) else None,
            "points_below": int(np.count_nonzero(bad)),
            "ways_below": len({int(net.edges[net.edge_of[w]]["way"])
                               for w in where[bad]}),
            "passed": bool(not np.any(bad)), "worst": worst,
            "conform": ground.stats}


def terrain_block(run_info, dem, base, horizon_dem, half, tiles_dir):
    out = {"terrain_file": run_info.get("terrain_file"),
           "base_height_m": num(base)}
    if horizon_dem is not None:
        out["copernicus_minus_dgm1_at_center_m"] = num(
            horizon_dem.height(0.0, 0.0) - dem.height(0.0, 0.0))
        hx, hy = np.broadcast_to(half, 2)
        xs, ys = np.meshgrid(np.arange(-hx, hx + 1e-6, 50.0),
                             np.arange(-hy, hy + 1e-6, 50.0))
        xs, ys = xs.ravel(), ys.ravel()
        d = horizon_dem.height(xs, ys) - dem.height(xs, ys)
        out["copernicus_minus_dgm1_grid50"] = {
            "median_m": num(np.median(d)),
            "p95_m": num(np.percentile(d, 95)),
            "abs_p95_m": num(np.percentile(np.abs(d), 95)),
            "points": int(len(d))}
    step = run_info.get("terrain_step", 10.0)
    rng = np.random.default_rng(SEED)
    hx, hy = np.broadcast_to(half, 2)
    x = rng.uniform(-hx, hx, FIDELITY_POINTS)
    y = rng.uniform(-hy, hy, FIDELITY_POINTS)
    cx = np.clip(np.floor((x + hx) / step), 0, int(round(2 * hx / step)) - 1)
    cy = np.clip(np.floor((y + hy) / step), 0, int(round(2 * hy / step)) - 1)
    x0, y0 = -hx + cx * step, -hy + cy * step
    fx, fy = (x - x0) / step, (y - y0) / step
    h00, h10 = dem.height(x0, y0), dem.height(x0 + step, y0)
    h01, h11 = dem.height(x0, y0 + step), dem.height(x0 + step, y0 + step)
    mesh = (h00 * (1 - fx) * (1 - fy) + h10 * fx * (1 - fy)
            + h01 * (1 - fx) * fy + h11 * fx * fy)
    # raw DGM1 against its own 10 m grid: what the mesh step loses, not
    # what the conformed terrain shows
    out["fidelity"] = {"measures": "raw DGM1 sampling error of the "
                                   f"{step:.0f} m mesh",
                       "mesh_step_m": step, "seed": SEED,
                       **pct(mesh - dem.height(x, y))}
    return out


def route_start(net, route_points):
    if not route_points:
        return None
    x, y = route_points[0][0], -route_points[0][2]
    lines = np.array([shapely.LineString(e["coords"])
                      for e in net.edges])
    d = shapely.distance(lines, shapely.Point(x, y))
    k = int(np.argmin(d))
    e = net.edges[k]
    return {"x": num(x, 1), "y": num(y, 1), "way": int(e["way"]),
            "class": e["tags"]["highway"], "name": e["tags"].get("name", ""),
            "distance_m": num(d[k], 2),
            "on_drivable_road": bool(d[k] <= 3.0)}


def run_block(run_info, out_dir):
    files = sorted(out_dir.glob("tile_*.glb"))
    sizes = [f.stat().st_size for f in files]
    stages = {k: num(v, 1) for k, v in run_info["stages_s"].items()}
    total = sum(sizes)
    return {"hostname": socket.gethostname(),
            "loadavg_start": run_info.get("load_start"),
            "stages_s": stages, "tiles": len(files),
            "tile_bytes": int(total),
            "largest_tile_bytes": int(max(sizes) if sizes else 0),
            "budget": {"build_s_max": BUDGET_S,
                       "tile_bytes_max": int(BUDGET_BYTES),
                       "tile_bytes_ok": bool(total <= BUDGET_BYTES)},
            "note": "tile load time is measured by the Godot smoke test, "
                    "not here"}


def clipping_baseline(path, center, size_km):
    """Per-kind baseline counts of the world's fixture, None for a kind
    not measured there; None when the file is missing or was measured
    on another area (rounded centre or size differ)."""
    if path is None or not path.is_file():
        return None
    base = json.loads(path.read_text())
    if ([round(c, 3) for c in base["center"]], round(base["size_km"], 3)) \
            != ([round(c, 3) for c in center], round(size_km, 3)):
        return None
    return {"date": base["date"], "commit": base.get("commit"),
            "counts": {k: v["count"] if v["measured"] else None
                       for k, v in base["counts"].items()}}


def write_metrics(network, out_dir, run_info, dem, base, frame,
                  route_points, horizon_dem=None, ground=None,
                  route_stats=None, tunnels=None, bridges=None,
                  skirts=None, markings=None, rails=None, sidewalks=None,
                  clipping=None, clipping_baseline_path=None):
    """Compute the report from the network and the exported tiles;
    clipping_baseline_path is the world's clipping ratchet fixture."""
    t0 = time.time()
    net = network
    out_dir = Path(out_dir)
    half = run_info["half"]
    dem_half = run_info.get("dem_half", half)
    tiles = load_roads(out_dir)
    if clipping is not None:
        lon, lat = frame.to_lonlat(0.0, 0.0)
        clipping = {**clipping, "baseline": clipping_baseline(
            clipping_baseline_path, (float(lat), float(lon)),
            float(2 * np.broadcast_to(half, 2)[0] / 1000))}
    allv = np.vstack(list(tiles.values())) if tiles else np.zeros((0, 3))
    sh = shared_heights(net, VertexIndex(allv))
    centre, edge = road_vs_terrain(net, dem, base, half, dem_half)
    report = {
        "run": run_block(run_info, out_dir),
        "gates": {},
        "terrain": terrain_block(run_info, dem, base, horizon_dem, half,
                                 out_dir),
        "roads": roads_block(net),
        "graph": graph_block(net),
        "links": links_block(net),
        "crossings_without_node": crossings(net),
        "shared_heights": sh,
        "seams": seams(tiles, half, run_info["tile_m"]),
        "slope": slope(net, dem, base, half, dem_half),
        "node_heights": node_heights_block(net, half),
        "structures": structures_block(net),
        "tunnels": tunnels,
        "bridges": bridges,
        "skirts": skirts,
        "sidewalks": sidewalks,
        "markings": markings,
        "rails": rails,
        "clipping": clipping,
        "road_vs_terrain": centre,
        "road_edge": edge,
        "route_start": route_start(net, route_points),
        "route": route_stats,
        "terrain_below_roads": terrain_below_roads(net, ground, base, half)
        if ground is not None else None,
    }
    run = report["run"]
    run["stages_s"]["metrics"] = num(time.time() - t0, 1)
    total = time.time() - run_info["started"]
    run["stages_s"]["total"] = num(total, 1)
    run["loadavg_end"] = load_avg()
    run["budget"]["build_s_ok"] = bool(total <= BUDGET_S)
    budget_ok = run["budget"]["build_s_ok"] and run["budget"][
        "tile_bytes_ok"]
    tb = report["terrain_below_roads"]
    passed = {"shared_heights": sh["passed"],
              "terrain_below_roads": None if tb is None else tb["passed"],
              "max_grade": report["slope"]["passed"],
              "node_heights": report["node_heights"]["ground"]["passed"]}
    report["gates"] = {
        **{k: "SKIPPED" if passed[k] is None
           else "PASS" if passed[k] else "FAIL" for k in HARD_GATES},
        "informational": {
            "components_99pct": "PASS" if report["graph"]["components"][
                "passed"] else "FAIL",
            "budget": "PASS" if budget_ok else "FAIL"}}
    if clipping is not None:
        # clipping.py imports this module for GATE_TOLERANCE
        from clipping import ratchet
        gate, allowed, count, limit = ratchet(clipping)
        clipping.update(allowed=allowed, measured_total=count,
                        baseline_total=limit)
        report["gates"]["informational"]["clipping"] = gate
    (out_dir / "metrics.json").write_text(
        json.dumps(report, indent=1, allow_nan=False, ensure_ascii=False)
        + "\n", encoding="utf-8")
    (out_dir / "metrics.md").write_text(markdown(report), encoding="utf-8")
    return report


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |",
             "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        lines.append("| " + " | ".join("" if c is None else str(c)
                                       for c in r) + " |")
    return "\n".join(lines) + "\n"


def node_heights_md(nh):
    gr, st, rx = nh["ground"], nh["structure"], nh["relax"]
    md = ["## Node heights (gate)\n"]
    md.append("Smoothed node height - DGM1 median within 3 m, nodes inside "
              "the playable area. Ground nodes are gated; structure nodes "
              "(touching a bridge or tunnel edge) take the DGM1 step of the "
              "abutment or portal and are only listed.\n")
    md.append(table(["item", "value"], [
        ["ground nodes", gr["n"]],
        ["ground p50 / p95 / max m",
         f"{gr['p50']} / {gr['p95']} / {gr['max']}"],
        ["ground max limit / p95 target m",
         f"{gr['max_limit_m']} / {gr['p95_target_m']}"],
        ["structure nodes / max m", f"{st['count']} / {st['max_m']}"],
        ["portal/abutment nodes: n / p50 / p95 / max m",
         f"{st['portal']['n']} / {st['portal']['p50']} / "
         + f"{st['portal']['p95']} / {st['portal']['max']}"],
        ["portal/abutment nodes from ground profile (whole graph)",
         rx["portal_nodes"]],
        ["relax iterations / edges over limit / max excess m",
         f"{rx['iterations']} / {rx['edges_over_limit']} / "
         + f"{rx['max_excess_m']:.3f}"],
        ["result", "PASS" if gr["passed"] else "FAIL"]]))
    md.append(table(["node", "deviation m", "ways", "names"],
                    [[t["node"], t["deviation_m"],
                      ", ".join(map(str, t["ways"])), ", ".join(t["names"])]
                     for t in st["top"]]))
    return md


def route_md(ro):
    md = ["## Route line\n"]
    if ro is None:
        md.append("No route given.\n")
        return md
    md.append(f"{ro['points']} route points, {ro['snapped']} snapped to the "
              "drawn road surface (bridges and tunnels included), "
              f"{ro['fallback']} farther than "
              f"{ro['fallback_distance_m']} m from every road and placed "
              f"on the conformed terrain. Snap distance max "
              f"{ro['max_snap_m']} m, p95 {ro['snap_p95_m']} m; "
              f"{ro['on_structure']} points on a bridge or tunnel.\n")
    if ro["far"]:
        md.append(table(["x", "y", "distance m"],
                        [[f["x"], f["y"], f["distance_m"]]
                         for f in ro["far"]]))
    return md


def structures_md(sb):
    md = ["## Structures\n", f"Note: {sb['note']}.\n"]
    md.append(table(["kind", "edges", "chains", "km"],
                    [[k, v["edges"], v["chains"], v["km"]]
                     for k, v in sb["kinds"].items()]))
    return md


def tunnels_md(tu, conform_stats):
    md = ["## Tunnels\n"]
    if not tu or not tu.get("edges"):
        md.append("No tunnels.\n")
        return md
    cl = tu["ceiling_clearance_m"]
    md.append("Per 5 m segment of a tunnel edge: covered (terrain at least "
              f"{tu['cover_min_m']} m above the road on the centre and both "
              "wall lines) gets a tube with the ceiling at "
              f"min(road + {tu['clearance_m']}, terrain - "
              f"{tu['ceiling_cover_m']}) m; a slot (terrain partly above "
              "the road) cuts the terrain between the wall lines and gets "
              "retaining walls; open (terrain below the road) gets nothing. "
              "Not gated.\n")
    md.append(table(["item", "value"], [
        ["tunnel edges", tu["edges"]],
        ["covered / slot / open km",
         f"{tu['covered_km']} / {tu['slot_km']} / {tu['open_km']}"],
        ["portal faces", tu["portal_faces"]],
        ["ceiling clearance p50 / min m (n samples)",
         f"{cl['p50']} / {cl['min']} ({cl['n']})"],
        ["terrain cover p50 m (all tunnel samples)", tu["cover_p50_m"]],
        ["wall pieces left out on other strips",
         tu["wall_pieces_dropped"]],
        ["terrain triangles clipped / removed",
         f"{tu['terrain_triangles_clipped']} / "
         + f"{tu['terrain_triangles_removed']}"],
        ["cut area m2", tu["cut_area_m2"]],
        ["conform grid points kept on DGM1 (nearer a tunnel than a road)",
         conform_stats.get("points_kept_over_tunnels")
         if conform_stats else None]]))
    return md


def bridges_md(br, conform_stats):
    md = ["## Bridges\n"]
    if not br or not br.get("edges"):
        md.append("No bridges.\n")
        return md
    pa, ab, cr, ra = br["params"], br["abutments"], br["crossings"], \
        br["raise"]
    md.append("Per 5 m segment of a bridge edge: deck (underside "
              f"{pa['deck_depth_m']} m below the surface, at least "
              f"{pa['gap_min_m']} m above DGM1 on the centre and both deck "
              "edge lines) gets walkway, parapet, sides and underside, and "
              "the terrain under it stays DGM1; low (everything else) gets "
              "no deck body and is conformed like a ground road. Deck runs "
              f"shorter than {pa['min_deck_run_m']} m between two abutments "
              "become low. Where a bridge crosses a road at least "
              f"{pa['grade_sep_m']} m below it, the deck is lifted to a "
              f"clearance of {pa['clear_min_m']} m (ramps "
              f"{pa['ramp_grade'] * 100:.0f} %); where the deck cannot go "
              "that high, the ground road below gets a dip. Abutment step "
              "= deck ground - conformed terrain across the abutment line. "
              "The terrain triangles crossing it are pinned to the deck "
              "plane (deck grade on the deck side, the grade of the next "
              "segment on the other); where another road strip in the same "
              "cells lies lower (a road below, a parallel carriageway, a "
              "kink) the push-down pass lowers them again (pushed). Not "
              "gated.\n")
    md.append(table(["item", "value"], [
        ["bridge edges", br["edges"]],
        ["segments deck / low", f"{br['segments']['deck']} / "
         f"{br['segments']['low']}"],
        ["deck / low km", f"{br['deck_km']} / {br['low_km']}"],
        ["short deck runs made low", br["short_deck_runs_to_low"]],
        ["abutment lines", ab["n"]],
        *[[f"abutment step, {label}: n / p50 / p95 / max m / above "
           f"{pa['step_tol_m']} m",
           f"{ab[key]['n']} / {ab[key]['p50_m']} / {ab[key]['p95_m']} / "
           f"{ab[key]['max_m']} / {ab[key]['over_tol']}"]
          for key, label in (("all", "all"),
                             ("held", "plane held"),
                             ("pushed", "pushed down by a road"))
          if key in ab],
        ["crossings: grade-separated, bridge on top / other",
         f"{cr['grade_separated_bridge_on_top']} / "
         f"{cr['at_grade_or_below']}"],
        ["clearance over crossing roads min / p50 m",
         f"{cr.get('min_clearance_m')} / {cr.get('p50_clearance_m')}"],
        [f"crossings below {pa['clear_min_m']} m",
         cr.get("below_clear_min")],
        ["deck lift: rounds / nodes / edges / max m",
         f"{ra['rounds']} / {ra['nodes_raised']} / {ra['edges_raised']} / "
         f"{ra['max_raise_m']}"],
        ["roads below dipped: edges / max m",
         f"{ra['edges_dipped']} / {ra['max_dip_m']}"],
        ["parapet pieces left out on other strips",
         br.get("parapet_pieces_dropped")],
        ["deck end faces / junction undersides",
         f"{br.get('end_faces')} / {br.get('junction_undersides')}"],
        ["conform grid points kept on DGM1 (nearer a deck than a road)",
         conform_stats.get("points_kept_under_bridges")
         if conform_stats else None],
        ["terrain corners pinned at abutments / pushed down again",
         f"{conform_stats.get('corners_pinned_at_abutments')} / "
         f"{conform_stats.get('pinned_corners_pushed_down')}"
         if conform_stats else None]]))
    if cr.get("lowest"):
        md.append("Lowest clearances:\n")
        md.append(table(["bridge way", "bridge", "below way", "below",
                         "class", "x", "y", "clearance m"],
                        [[c["bridge_way"], c["bridge"], c["below_way"],
                          c["below"], c["below_class"], c["x"], c["y"],
                          c["clearance_m"]] for c in cr["lowest"]]))
    if ab.get("worst"):
        md.append("Largest abutment steps:\n")
        md.append(table(["way", "name", "x", "y", "step m", "plane held"],
                        [[w["way"], w["name"], w["x"], w["y"], w["step_m"],
                          "yes" if w["held"] else "no"]
                         for w in ab["worst"]]))
    return md


def sidewalks_md(sw):
    if not sw:
        return []
    left, right, both = sw["edges_left_right_both"]
    return ["## Sidewalks\n",
            f"{sw['km']} km of ground edges with a sidewalk of "
            f"{sw['width_m']} m on a {sw['kerb_m']} m kerb (edges with a "
            f"sidewalk on the left only / right only / both: {left} / "
            f"{right} / {both}) and {sw['junction_corners']} corner "
            "pieces round the junctions; the skirt starts at their outer "
            "edge. Segments and corners lying on another road yield: "
            f"{sw.get('walk_clipped')} segments left out, corners kept / "
            f"left out {sw.get('corners_kept')} / "
            f"{sw.get('corners_clipped')}. Not gated.\n"]


def skirts_md(sk):
    if not sk:
        return []
    return ["## Road skirts\n",
            f"Every ground strip edge and junction hull gets a skirt "
            f"{sk['angle_deg']:.0f} degrees below the horizontal, down to "
            f"{sk['sink_m']} m under the conformed terrain, at least "
            f"{sk['min_depth_m']} m and at most {sk['max_depth_m']} m deep "
            f"and at most {sk['max_run_m']} m wide (deeper ones steepen "
            "into walls). Not gated.\n",
            table(["item", "value"], [
                ["faces", sk["faces"]],
                ["depth p50 / p95 / max m",
                 f"{sk['depth_p50_m']} / {sk['depth_p95_m']} / "
                 f"{sk['depth_max_m']}"],
                ["skirt segments yielding to another road",
                 sk.get("skirt_clipped")],
                ["edge points limited by a narrow median",
                 sk.get("median_limited")],
                ["edge points steepened to walls", sk["steepened"]],
                ["edge points at max depth (not reaching the ground)",
                 sk["at_max_depth"]]]),
            table(["x", "z"], [[w["x"], w["z"]] for w in sk["worst"]])
            if sk["worst"] else ""]


def rails_md(rl):
    if not rl:
        return []
    return ["## Railways\n",
            f"{rl['ways']} ways, {rl['km']} km of track: {rl['km_bed']} km "
            f"on a ballast bed, {rl['km_on_road']} km as rails on a road "
            f"(the road wins), {rl['km_bridge']} km on bridges (straight "
            "grade, no deck); layer `rails` (no collision). Not gated.\n"]


def markings_md(mk):
    if not mk:
        return []
    return ["## Road markings\n",
            f"{mk['dashes']} dashes of {mk['dash_m']} m every "
            f"{mk['dash_m'] + mk['gap_m']} m on "
            f"{', '.join(mk['classes'])} roads: centre lines on two-way "
            "roads, lane lines on oneway carriageways with `lanes`; layer "
            "`markings` (no collision); edge lines "
            f"{mk.get('edge_line_km')} km on "
            f"{', '.join(mk.get('edge_line_classes', [])) or '-'} roads. "
            "Not gated.\n"]


def clipping_md(cl, gate):
    """Counts against the baseline, the worst findings per kind."""
    if not cl:
        return []
    base = cl.get("baseline") or {}
    counts = base.get("counts", {})
    md = ["## Clipping\n",
          "Places where drawn road pieces cut into each other or into the "
          "terrain (pipeline/clipping.py): zfight m2, overlap and median m "
          "short of their limit, width_step, terrain_above, bank_buried, "
          "skirt_cross and dip m. One finding per pair of owners or per "
          f"run of segments, inside the playable square; {cl['seconds']} "
          "s. Informational gate (ratchet): no kind above its allowed "
          "count (baseline plus a small slack, rounded up) and the total "
          "of the measured kinds not above the baseline total "
          + (f"(baseline {base['date']}, {base.get('commit')}): {gate}.\n"
             if base else f"(no baseline for this world): {gate}.\n")]
    allowed = cl.get("allowed", {})
    rows = []
    for k, n in cl["counts"].items():
        b = counts.get(k)
        rows.append([k, "-" if b is None else b, allowed.get(k, "-"),
                     n if cl["measured"].get(k, True) else "-",
                     "yes" if b is not None else "no"])
    rows.append(["total of measured kinds", cl.get("baseline_total", "-"),
                 cl.get("baseline_total", "-"),
                 cl.get("measured_total", "-"), ""])
    rows.append(["total of all kinds", "", "", cl["total"], ""])
    md.append(table(["kind", "baseline", "allowed", "count",
                     "baseline measured"], rows))
    worst = [[k, f["way"], f["name"], f["x"], f["y"], f["severity"]]
             for k, fs in cl["worst"].items() for f in fs]
    if worst:
        md.append(table(["kind", "way", "name", "x", "y", "severity"],
                        worst))
    return md


def markdown(r):
    run, g = r["run"], r["gates"]
    md = ["# Build metrics\n"]
    md.append("Generated by `pipeline/metrics.py` from the exported tiles. "
              "Hard gates (the build exits with code 3 if one fails): "
              + "; ".join(HARD_GATES.values())
              + ". Everything else is reported. Tile load time is measured "
              "by the Godot smoke test, not here.\n")
    md.append("## Run\n")
    rows = [["host", run["hostname"]],
            ["load start / end", f"{' '.join(run['loadavg_start'])} / "
             f"{' '.join(run['loadavg_end'])}"]]
    rows += [[f"{k} s", v] for k, v in run["stages_s"].items()]
    rows += [["tiles", run["tiles"]],
             ["tile MB", f"{run['tile_bytes'] / 1e6:.1f}"],
             ["largest tile MB", f"{run['largest_tile_bytes'] / 1e6:.2f}"]]
    md.append(table(["item", "value"], rows))
    md.append("## Gates\n")
    b = run["budget"]
    md.append(table(["gate", "kind", "result"], [
        *[[label, "hard", g[k]] for k, label in HARD_GATES.items()],
        ["largest component >= 99 % of km", "informational",
         g["informational"]["components_99pct"]],
        [f"budget: build <= {b['build_s_max']:.0f} s, tiles <= "
         f"{b['tile_bytes_max'] / 1e6:.0f} MB", "informational",
         g["informational"]["budget"]],
        *([["clipping not above its baseline", "informational",
            g["informational"]["clipping"]]]
          if "clipping" in g["informational"] else [])]))
    t = r["terrain"]
    md.append("## Terrain\n")
    rows = [["terrain file", t["terrain_file"]],
            ["base height m", t["base_height_m"]]]
    if "copernicus_minus_dgm1_at_center_m" in t:
        c = t["copernicus_minus_dgm1_grid50"]
        rows += [["Copernicus - DGM1 at centre m",
                  t["copernicus_minus_dgm1_at_center_m"]],
                 ["Copernicus - DGM1, 50 m grid: median / p95 m",
                  f"{c['median_m']} / {c['p95_m']}"]]
    f = t["fidelity"]
    rows.append([f"{f['measures']}, {f['n']} points: p50 / p95 / max m",
                 f"{f['p50']} / {f['p95']} / {f['max']}"])
    md.append(table(["item", "value"], rows))
    ro = r["roads"]
    md.append("## Roads\n")
    md.append(f"Drivable: {ro['km_total']} km. Note: {ro['note']}.\n")
    md.append(table(["class", "edges", "km"],
                    [[k, v["edges"], v["km"]]
                     for k, v in ro["per_class"].items()]))
    md.append(table(["excluded (reason)", "ways"],
                    [[k, v] for k, v in ro["excluded_ways"].items()]))
    gr = r["graph"]
    cp = gr["components"]
    md.append("## Graph\n")
    md.append(table(["item", "value"], [
        ["nodes", gr["nodes"]], ["edges", gr["edges"]],
        ["boundary nodes", gr["boundary_nodes"]],
        ["junction nodes (degree >= 3)", gr["junction_nodes"]],
        ["junction surfaces emitted", gr["junction_surfaces"]],
        ["edge ends too short to cut back fully",
         gr["edge_ends_too_short_to_cut"]],
        ["bridge/tunnel nodes interpolated",
         gr["structure_nodes_interpolated"]],
        ["components", cp["count"]],
        ["largest component km / share",
         f"{cp['largest_km']} / {cp['largest_share'] * 100:.2f} %"],
        ["other components: boundary / osm_gap / km",
         f"{cp['others_boundary']} / {cp['others_osm_gap']} / "
         f"{cp['others_km']}"]]))
    md.append(table(["degree", "nodes"],
                    list(gr["degree_histogram"].items())))
    md.append(f"Other components ({len(cp['others'])} of "
              f"{cp['others_total']} listed):\n")
    md.append(table(["km", "edges", "reason", "ways"],
                    [[o["km"], o["edges"], o["reason"],
                      ", ".join(map(str, o["ways"]))]
                     for o in cp["others"]]))
    lk = r["links"]
    md.append("## Links\n")
    md.append(f"{lk['link_edges']} `*_link` edges; "
              f"{lk['dangling_link_ways']} link ways end without a "
              "connection and away from the boundary: "
              f"{', '.join(map(str, lk['ways'])) or 'none'}.\n")
    cr = r["crossings_without_node"]
    md.append("## Crossings without a shared node\n")
    md.append(table(["kind", "pairs"], [
        ["layer differs", cr["layer_differs"]], ["bridge", cr["bridge"]],
        ["tunnel", cr["tunnel"]], ["unexplained", cr["unexplained"]]]))
    md.append(f"Unexplained way pairs ({len(cr['unexplained_list'])} of "
              f"{cr['unexplained_way_pairs']} listed): "
              + (", ".join(f"{a}/{b}" for a, b in cr["unexplained_list"])
                 or "none") + "\n")
    sh = r["shared_heights"]
    md.append("## Shared heights at nodes (gate)\n")
    md.append(table(["item", "value"], [
        ["tolerance m", sh["tolerance_m"]],
        ["nodes checked", sh["nodes_checked"]],
        ["nodes with every vertex found", sh["nodes_all_vertices_found"]],
        ["vertices expected / missing",
         f"{sh['vertices_expected']} / {sh['vertices_missing']}"],
        ["max deviation m", sh["max_deviation_m"]],
        ["nodes above tolerance", sh["nodes_above_tolerance"]],
        ["max offset from expected height m",
         sh["max_offset_from_expected_m"]],
        ["nodes outside the tiles (not checked)",
         sh["nodes_skipped_outside_tiles"]],
        ["result", "PASS" if sh["passed"] else "FAIL"]]))
    md.append(table(["node", "deviation m", "missing", "classes"],
                    [[w["node"], w["deviation_m"], w["missing_vertices"],
                      ", ".join(w["classes"])] for w in sh["worst"]]))
    se = r["seams"]
    md.append("## Tile seams\n")
    md.append("Roads vertices on or beyond the border of their tile, "
              "looked up in the neighbouring tile at the same (x, z). A "
              "vertex without counterpart is a strip end or junction "
              "spilling over, not an error.\n")
    md.append(table(["item", "value"], [
        ["vertices checked", se["vertices_checked"]],
        ["with counterpart", se["with_counterpart"]],
        ["without counterpart", se["without_counterpart"]],
        ["height mismatches (> 1 mm)", se["height_mismatches"]],
        ["max height difference m", se["max_height_difference_m"]]]))
    sl = r["slope"]
    a = sl["abs_grade_pct"]
    md.append("## Slope\n")
    md.append(f"Absolute grade over {sl['segments']} road segments of 5 m in "
              f"the playable area: p50 {a['p50']} %, p90 {a['p90']} %, "
              f"p95 {a['p95']} %, p99 {a['p99']} %, max {a['max']} %. "
              f"{sl['steep_sections']} sections above "
              f"{sl['threshold_pct']:.0f} % ({sl['steep_km']} km).\n")
    md.append(f"Largest grade {sl['max_grade_pct']} % (limit "
              f"{sl['max_grade_limit_pct']} %): "
              f"{'PASS' if sl['passed'] else 'FAIL'}. Reasons of the steep "
              "sections: " + ", ".join(f"{k} {v}" for k, v in
                                       sl["reasons"].items()) + ".\n")
    md.append(table(["way", "name", "class", "grade %", "terrain %",
                     "length m", "reason"],
                    [[s["way"], s["name"], s["class"], s["grade_pct"],
                      s["terrain_grade_pct"], s["length_m"], s["reason"]]
                     for s in sl["sections"]]))
    md += node_heights_md(r["node_heights"])
    md += structures_md(r["structures"])
    tb_ = r["terrain_below_roads"]
    md += tunnels_md(r.get("tunnels"), tb_["conform"] if tb_ else None)
    md += bridges_md(r.get("bridges"), tb_["conform"] if tb_ else None)
    md += sidewalks_md(r.get("sidewalks"))
    md += skirts_md(r.get("skirts"))
    md += markings_md(r.get("markings"))
    md += rails_md(r.get("rails"))
    md += clipping_md(r.get("clipping"),
                      g["informational"].get("clipping"))
    rv, rd = r["road_vs_terrain"], r["road_edge"]
    tb = r["terrain_below_roads"]
    if tb is not None:
        c = tb["conform"]
        md.append("## Terrain conformed to roads (gate)\n")
        md.append(f"Grid {c['grid_step_m']:.0f} m; flat up to "
                  f"{c['flat_m']:.0f} m beyond a strip edge, blended back "
                  f"to DGM1 over {c['shoulder_m']:.0f} m; bridges and "
                  "tunnels excluded. Clearance = road surface - conformed "
                  "terrain at strip centre and both edges; below "
                  f"{tb['min_clearance_m']} m the terrain shows through.\n")
        md.append(table(["item", "value"], [
            ["grid points / flat / changed",
             f"{c['grid_points']} / {c['points_flat']} / "
             f"{c['points_changed']}"],
            ["max cut / max fill m",
             f"{c['cut_max_m']:.2f} / {c['fill_max_m']:.2f}"],
            ["abs change p95 m (changed points)",
             f"{c['abs_change_p95_m']:.2f}"],
            ["clearance p50 / p95 / min m",
             f"{tb['p50']} / {tb['p95']} / {tb['min_m']}"],
            ["points / ways below", f"{tb['points_below']} / "
             f"{tb['ways_below']}"]]))
        if tb["worst"]:
            md.append(table(["way", "name", "class", "clearance m"],
                            [[w["way"], w["name"], w["class"],
                              w["clearance_m"]] for w in tb["worst"]]))
    md.append("## Road vs DGM1 (before conforming)\n")
    md.append(table(["measure", "p50 m", "p95 m", "max m", "samples"], [
        ["centre: road ground - DGM1 (no lift, no bridges/tunnels)",
         rv["p50"], rv["p95"], rv["max"], rv["n"]],
        ["strip edge vertex - DGM1 (with lift)", rd["p50"], rd["p95"],
         rd["max"], rd["n"]]]))
    rs = r["route_start"]
    md.append("## Route start\n")
    if rs is None:
        md.append("No route given.\n")
    else:
        md.append(f"Nearest drivable edge to the first route point: "
                  f"{rs['class']} \"{rs['name']}\" (way {rs['way']}) at "
                  f"{rs['distance_m']} m; on a drivable road: "
                  f"{'yes' if rs['on_drivable_road'] else 'no'}.\n")
    md += route_md(r.get("route"))
    return "\n".join(md)
# - revised 2026-10-22 (clipping block, ratchet, new report keys)
# - revised 2026-10-23 (clipping baseline per world, next to the recipe)
# - revised 2026-10-23 (rectangular playable area)
# - revised 2026-10-25 (position of the worst terrain_below_roads points)
# - revised 2026-11-04 (railway report)
