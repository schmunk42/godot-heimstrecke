# file generated with AI assistance: Claude Code - 2026-10-22 11:40:00 UTC
"""Dashed centre and lane lines on main roads.

A flat-shaded world gives the eye nothing that streams past, so speed
reads far lower than it is; a dashed line is the strongest cue there is.
Urban Leitlinie: DASH m of line, GAP m of gap, WIDTH m wide, LIFT above
the drawn surface, on CLASSES only, bridges and tunnels included. A
two-way road at least MIN_WIDTH wide gets a centre line; a oneway
carriageway (most main roads here are mapped as two) gets a line
between each of its `lanes`. The dash pattern runs on through nodes of
degree 2 (chain_phase), so it does not restart at every tag split.
EDGE_CLASSES get a continuous edge line EDGE_INSET inside both drawn
edges, which follows a width taper (net.half) and frames the
carriageway against the stone banks. Neither dashes nor edge lines are
drawn on junction surfaces, where they would cross the other road
(priority.py). The lines go into their own `markings` layer, which the
drive scene loads without collision.
"""
import numpy as np

from frame import xyz
from priority import road_area
from roads import add_ribbon, orient, ribbon, road_class, tile_keys

CLASSES = ("tertiary", "secondary", "primary", "trunk")
DASH = 3.0
GAP = 6.0
WIDTH = 0.12
LIFT = 0.02
MIN_WIDTH = 6.0
# continuous edge lines: EDGE_WIDTH wide, centred EDGE_INSET inside the
# drawn edge
EDGE_CLASSES = ("secondary", "primary", "trunk")
EDGE_WIDTH = 0.15
EDGE_INSET = 0.25


def line_offsets(tags, width):
    """Offsets of the lines from the centre line as fractions of the
    half width, left positive (the set of lines follows the edge width)."""
    if road_class(tags) not in CLASSES or tags["highway"].endswith("_link"):
        return []
    oneway = tags.get("oneway", "no") in ("yes", "1", "-1") \
        or tags.get("junction") == "roundabout"
    if not oneway:
        return [0.0] if width >= MIN_WIDTH else []
    try:
        lanes = int(tags["lanes"])
    except (KeyError, ValueError):
        return []
    return [2 * k / lanes - 1 for k in range(1, lanes)]


def chain_phase(net):
    """Chain coordinate of every edge as (offset, sign) arrays, so that
    offset + sign * net.dist runs on through nodes of degree 2."""
    ends = {}
    for e in range(len(net.edges)):
        for end, node in ((0, int(net.u[e])), (1, int(net.v[e]))):
            if net.degree[node] == 2:
                ends.setdefault(node, []).append((e, end))

    def other(e, end):
        """The edge end meeting end `end` (0 u, 1 v) of e, if any."""
        pair = ends.get(int(net.v[e] if end else net.u[e]))
        if pair is None or len(pair) != 2:
            return None
        return pair[1] if pair[0] == (e, end) else pair[0]

    offset = np.zeros(len(net.edges))
    sign = np.ones(len(net.edges))
    done = np.zeros(len(net.edges), dtype=bool)
    for first in range(len(net.edges)):
        if done[first]:
            continue
        # back to the start of the chain; `end` is where e is entered
        e, end, seen = first, 0, {first}
        while (prev := other(e, end)) is not None and prev[0] not in seen:
            e, end = prev[0], 1 - prev[1]
            seen.add(e)
        c = 0.0
        while not done[e]:
            done[e] = True
            offset[e], sign[e] = (c, 1.0) if end == 0 \
                else (c + net.length[e], -1.0)
            c += net.length[e]
            nxt = other(e, 1 - end)
            if nxt is None:
                break
            e, end = nxt
    return offset, sign


def emit_markings(tiles, net, color):
    """Dashes along every qualifying edge and edge lines; returns stats
    for the report."""
    area = road_area(net)
    offset, sign = chain_phase(net)
    dashes = 0
    for i, e in enumerate(net.edges):
        for frac in line_offsets(e["tags"], net.width[i]):
            dashes += emit_line(tiles, net, i, frac, color, area,
                                (offset[i], sign[i]))
    km = emit_edge_lines(tiles, net, area, color)
    return {"dashes": dashes, "classes": list(CLASSES),
            "dash_m": DASH, "gap_m": GAP,
            "edge_line_classes": list(EDGE_CLASSES),
            "edge_line_km": round(km, 1)}


def emit_edge_lines(tiles, net, area, color):
    """Continuous edge lines on both sides of EDGE_CLASSES edges, left
    out on junction surfaces; returns their length in km."""
    seg_owner = tile_keys(tiles, (net.sx[:-1] + net.sx[1:]) / 2,
                          (net.sy[:-1] + net.sy[1:]) / 2)
    length = 0.0
    for i, e in enumerate(net.edges):
        tags = e["tags"]
        if road_class(tags) not in EDGE_CLASSES \
                or tags["highway"].endswith("_link"):
            continue
        s0, s1 = net.start[i], net.start[i + 1]
        owner = seg_owner[s0:s1 - 1]
        if np.all(owner < 0):
            continue
        s = slice(s0, s1)
        nrm = np.column_stack([-net.tangent[s, 1], net.tangent[s, 0]])
        p = np.column_stack([net.sx[s], net.sy[s]])
        h = net.surface[s] + LIFT
        seg = np.diff(net.dist[s])
        for side in (1.0, -1.0):
            off = side * (net.half[s] - EDGE_INSET)
            mid = p + nrm * off[:, None]
            mx, my = (mid[:-1] + mid[1:]).T / 2
            own = np.where(area.in_junction(mx, my), -1, owner)
            half = nrm * (side * EDGE_WIDTH / 2)
            verts, faces = ribbon(mid - half, mid + half, h, h)
            add_ribbon(tiles, verts, orient(verts, faces, [0, 1, 0]), own,
                       color, "markings")
            length += float(seg[own >= 0].sum())
    return length / 1000


def emit_line(tiles, net, i, frac, color, area, phase=(0.0, 1.0)):
    """One dashed line of edge i, `frac` half widths left of its centre
    line, so it follows a width taper. The pattern starts where the
    chain coordinate phase[0] + phase[1] * dist (chain_phase) is a
    multiple of DASH + GAP; dashes centred on a junction surface are
    left out."""
    dashes = 0
    s = slice(net.start[i], net.start[i + 1])
    nrm = np.column_stack([-net.tangent[s, 1], net.tangent[s, 0]])
    offset = frac * net.half[s]
    cx = net.sx[s] + nrm[:, 0] * offset
    cy = net.sy[s] + nrm[:, 1] * offset
    dist = net.dist[s]
    period = DASH + GAP
    base, sign = phase
    chain = base + sign * dist
    lo, hi = chain.min(), chain.max()
    c0 = np.arange(np.ceil(lo / period) * period, hi - DASH, period)
    d0 = np.sort(c0 - base if sign > 0 else base - c0 - DASH)
    if not len(d0):
        return 0
    d1 = d0 + DASH
    x0, x1 = (np.interp(d, dist, cx) for d in (d0, d1))
    y0, y1 = (np.interp(d, dist, cy) for d in (d0, d1))
    on = area.in_junction((x0 + x1) / 2, (y0 + y1) / 2)
    if on.all():
        return 0
    d0, d1, x0, x1, y0, y1 = (v[~on] for v in (d0, d1, x0, x1, y0, y1))
    h0, h1 = (np.interp(d, dist, net.surface[s]) + LIFT
              for d in (d0, d1))
    along = np.column_stack([x1 - x0, y1 - y0])
    along /= np.maximum(np.linalg.norm(along, axis=1,
                                       keepdims=True), 1e-9)
    side = np.column_stack([-along[:, 1], along[:, 0]]) * WIDTH / 2
    a, b = np.column_stack([x0, y0]), np.column_stack([x1, y1])
    # left start, right start, right end, left end per dash
    quad = np.stack([a + side, a - side, b - side, b + side], axis=1)
    h = np.column_stack([h0, h0, h1, h1])
    keys = tile_keys(tiles, (x0 + x1) / 2, (y0 + y1) / 2)
    for key in np.unique(keys[keys >= 0]):
        sel = keys == key
        n = int(np.count_nonzero(sel))
        q = quad[sel].reshape(-1, 2)
        verts = xyz(q[:, 0], h[sel].ravel(), q[:, 1])
        o = 4 * np.arange(n)[:, None]
        # counter-clockwise seen from above, like the road strips
        faces = np.vstack([o + [0, 1, 2], o + [0, 2, 3]])
        bucket = tiles.bucket(key)["markings"]
        bucket.add(verts, faces, color)
        dashes += n
    return dashes
# - revised 2026-10-22 (edge lines, no lines on junctions, chained dash phase)
# - revised 2026-10-22 (tiles own their key lookup)
