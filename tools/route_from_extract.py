# file generated with AI assistance: Claude Code - 2026-10-26 12:00:00 UTC
"""Route through the road network of a built extract, as an OSRM response.

The public OSRM server routes cars only, and its car profile does not know
`highway=track`, so a route over forest tracks cannot be fetched from it.
This tool runs Dijkstra on the extract of the world (`extract.pkl`, which
contains the tracks of the recipe's `tracks`) from waypoint to waypoint and
writes a response that `build.py` reads like an OSRM one (`routes[0]
.geometry.coordinates`, `waypoints[].location`).

Waypoints: a JSON list of `[lon, lat, track_factor]`; the factor scales
the cost of a track on the leg that starts at that waypoint (below 1
prefers tracks, 1 treats them like roads). The route is as long as the
sum of the legs; the 8 m/s duration is a placeholder.

    uv run python -I tools/route_from_extract.py \\
        data/out/worlds/<id>/extract.pkl waypoints.json worlds/<id>/route.json
"""
import collections
import heapq
import json
import math
import pickle
import sys

import shapely

LAT_M = 111e3  # metres per degree of latitude
# metres per degree of longitude, set from the waypoints' latitude in main
LON_M = 73.4e3
PLACEHOLDER_SPEED = 8.0


def load_graph(path):
    with open(path, "rb") as f:
        roads = pickle.load(f)["roads"]
    pos, adj = {}, collections.defaultdict(list)
    for r in roads:
        c = list(shapely.from_wkb(r["geom"]).coords)
        ns, t = r["nodes"], r["tags"]
        if len(ns) != len(c):
            continue
        oneway = t.get("oneway") in ("yes", "1")
        reverse = t.get("oneway") == "-1"
        for i in range(len(ns) - 1):
            a, b = ns[i], ns[i + 1]
            pos[a], pos[b] = c[i], c[i + 1]
            length = math.hypot((c[i][0] - c[i + 1][0]) * LON_M,
                                (c[i][1] - c[i + 1][1]) * LAT_M)
            track = t["highway"] == "track"
            if reverse:
                adj[b].append((a, length, track))
            else:
                adj[a].append((b, length, track))
                if not oneway:
                    adj[b].append((a, length, track))
    return pos, adj


def nearest(pos, lon, lat):
    return min(pos, key=lambda n: math.hypot((pos[n][0] - lon) * LON_M,
                                             (pos[n][1] - lat) * LAT_M))


def leg(adj, s, t, track_factor):
    pq, best, prev = [(0.0, s)], {s: 0.0}, {}
    while pq:
        cost, n = heapq.heappop(pq)
        if n == t:
            break
        if cost > best[n]:
            continue
        for m, length, track in adj[n]:
            k = cost + length * (track_factor if track else 1.0)
            if k < best.get(m, math.inf):
                best[m], prev[m] = k, (n, length)
                heapq.heappush(pq, (k, m))
    path, metres = [t], 0.0
    while path[-1] != s:
        n, length = prev[path[-1]]
        path.append(n)
        metres += length
    return path[::-1], metres


def main(extract, waypoints, out):
    global LON_M
    wps = json.load(open(waypoints))
    # 73.4 km at 48.6 N (Kirchheim), 82.2 km at 42.2 N (Corsica)
    LON_M = LAT_M * math.cos(math.radians(
        sum(lat for _, lat, _ in wps) / len(wps)))
    pos, adj = load_graph(extract)
    nodes = [nearest(pos, lon, lat) for lon, lat, _ in wps]
    coords, legs = [], []
    for i in range(len(nodes) - 1):
        path, metres = leg(adj, nodes[i], nodes[i + 1], wps[i][2])
        pts = [pos[n] for n in path]
        coords += pts if not coords else pts[1:]
        legs.append({"distance": round(metres, 1),
                     "duration": round(metres / PLACEHOLDER_SPEED, 1),
                     "weight": round(metres / PLACEHOLDER_SPEED, 1),
                     "summary": "", "steps": []})
        print(f"leg {i}: {metres:.0f} m")
    total = sum(x["distance"] for x in legs)
    response = {
        "code": "Ok",
        "routes": [{"legs": legs, "weight_name": "routability",
                    "geometry": {"type": "LineString", "coordinates": [
                        [round(x, 6), round(y, 6)] for x, y in coords]},
                    "distance": round(total, 1),
                    "duration": round(total / PLACEHOLDER_SPEED, 1),
                    "weight": round(total / PLACEHOLDER_SPEED, 1)}],
        "waypoints": [{"hint": "", "distance": 0.0,
                       "name": "", "location": [round(pos[n][0], 6),
                                                round(pos[n][1], 6)]}
                      for n in nodes]}
    json.dump(response, open(out, "w"), separators=(",", ":"))
    print(f"total {total:.0f} m, {len(coords)} points -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
# - revised 2026-10-26 (metres per degree of longitude from the waypoints)
