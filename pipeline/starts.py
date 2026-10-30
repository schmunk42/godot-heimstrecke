# file generated with AI assistance: Claude Code - 2026-10-21 00:35:00 UTC
"""Start points for the drive menu, snapped onto the road network.

Each start from the fixture is moved to the nearest drawn road sample
(of the named road, if given) and gets a driving direction along that
edge, the one closer to `toward`. A `route_start` entry uses the first
route point and the route's direction instead and enables the lap timer
in Godot.

A start without `toward` in a world with a route faces along the route
(from its first to its last point), so all starts of a world face the same
way; Godot turns them around when the route is driven backwards.
"""
import json

import numpy as np
import shapely

from frame import xyz

# a named road must be this close to `at`, otherwise any road is taken
NAMED_RADIUS = 300.0
LOOK_AHEAD = 10.0


class StartError(RuntimeError):
    pass


def nearest_edge(net, lines, x, y, road):
    d = shapely.distance(lines, shapely.Point(x, y))
    if road:
        named = np.array([e["tags"].get("name") == road for e in net.edges])
        if np.any(named & (d <= NAMED_RADIUS)):
            d = np.where(named, d, np.inf)
    k = int(np.argmin(d))
    return k, float(d[k])


def snap(net, lines, x, y, tx, ty, road):
    k, dist = nearest_edge(net, lines, x, y, road)
    s = slice(net.start[k], net.start[k + 1])
    sx, sy = net.sx[s], net.sy[s]
    i = int(np.argmin(np.hypot(sx - x, sy - y)))
    j = i + 1 if i + 1 < len(sx) else i - 1
    step = np.array([sx[j] - sx[i], sy[j] - sy[i]])
    if tx is not None and np.dot(step, [tx - sx[i], ty - sy[i]]) < 0:
        step = -step
    step = step / (np.linalg.norm(step) + 1e-12) * LOOK_AHEAD
    h = float(net.surface[s][i])
    e = net.edges[k]
    pos = xyz(sx[i], h, sy[i])[0]
    look = xyz(sx[i] + step[0], h, sy[i] + step[1])[0]
    return {"pos": pos.round(2).tolist(), "look": look.round(2).tolist(),
            "road": e["tags"].get("name", e["tags"]["highway"]),
            "way": int(e["way"]), "snap_m": round(dist, 2)}


def along_route(route_line, x, y):
    """The route point a little ahead of the route point nearest (x, y)."""
    pts = np.array([[p[0], -p[2]] for p in route_line])
    i = int(np.argmin(np.hypot(pts[:, 0] - x, pts[:, 1] - y)))
    if i + 1 < len(pts):
        ahead = pts[i + 1]
    else:
        ahead = pts[i] + (pts[i] - pts[i - 1])
    return float(ahead[0]), float(ahead[1])


def build_starts(path, net, frame, route_line):
    """meta["starts"]: name, lap flag, position and look-at point."""
    lines = np.array([shapely.LineString(e["coords"]) for e in net.edges])
    starts = []
    for entry in json.loads(path.read_text())["starts"]:
        if entry.get("route_start"):
            if not route_line:
                raise StartError(f"{entry['name']}: route_start needs "
                                 "--route")
            p, q = route_line[0], route_line[min(3, len(route_line) - 1)]
            x, y, tx, ty = p[0], -p[2], q[0], -q[2]
        else:
            x, y = frame.to_local(entry["at"][1], entry["at"][0])
            tx = ty = None
            if "toward" in entry:
                tx, ty = frame.to_local(entry["toward"][1],
                                        entry["toward"][0])
            elif route_line and len(route_line) > 1:
                tx, ty = along_route(route_line, float(x), float(y))
        start = snap(net, lines, float(x), float(y), tx, ty,
                     entry.get("road"))
        starts.append({"name": entry["name"],
                       "lap": bool(entry.get("route_start")), **start})
    return starts
