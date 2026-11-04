# file generated with AI assistance: Claude Code - 2026-10-21 01:10:00 UTC
"""Terrain conformed to the roads (stage A2).

One height grid over the whole playable square, at the terrain mesh step,
so tiles cut from it meet at their seams by construction. Grid points up
to FLAT beyond a strip edge get the ground height of the nearest road;
beyond that the height blends back to DGM1 over SHOULDER. FLAT is larger
than a grid cell diagonal, so every terrain triangle touching a strip has
all three corners on road height. Where the road bends or changes grade
within a cell, or a second road at another height is nearer to a corner,
that is not enough, so a last pass checks strip points (centre and both
edges, every 0.625 m) and lowers the three corners of the triangle under
any point where the terrain is above the road ground by exactly that
excess, until no point is above. Only cells that need it change, so the
road stays flush elsewhere. Bridges and tunnels are left out; a grid
point nearer to a tunnel than to the nearest ground road keeps its DGM1
height, so the ground road at a portal does not dig FLAT + SHOULDER into
the hill over the tunnel (tunnels.py cuts the portals instead).

Bridges follow bridges.py: low segments are conformed like ground
roads; under deck segments the same rule as over tunnels keeps DGM1,
except at the abutments, where the corners of every terrain triangle
crossing an abutment line are pinned to the deck's ground plane, so the
terrain meets the deck end without a step. The push-down pass covers
deck segments too, so no terrain rises above a deck's ground either.

The push-down pass also keeps the terrain under the middle and outer
line of every sidewalk (sidewalks.py) and under every ground junction
surface: its points are the centre, the rim points and points between
every pair of them, because the hull edges between two strip ends are
not on any strip. It keeps the terrain under every island plate
(islands.py) too.
"""
import numpy as np
import shapely

from islands import plate_points
from sidewalks import KERB, MARGIN, WIDTH

FLAT = 15.0
# strip points per segment for the push-down pass (segments are 5 m)
PUSH_T = tuple(i / 8 for i in range(8))
SHOULDER = 25.0
CHUNK = 100_000


class ConformedTerrain:
    """height(x, y) like Dgm1Raster, from the conformed grid.

    Inside the grid the lookup interpolates on the mesh triangles
    (diagonal from (i+1, j) to (i, j+1), as in build.grid_mesh), so it
    returns exactly what the exported terrain shows; outside it asks the
    DGM1 raster. pin: the heights pin_lines set at the abutments (NaN
    elsewhere), before the push-down pass. The grid has rows along y and
    columns along x; half is a scalar or the pair hx, hy.
    """

    def __init__(self, dem, half, step, heights, stats):
        self.dem, self.half, self.step = dem, half, step
        self.hx, self.hy = np.broadcast_to(half, 2)
        self.h = heights
        self.rows, self.cols = heights.shape
        self.stats = stats

    def height(self, x, y):
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        scalar = x.ndim == 0
        x, y = np.atleast_1d(x), np.atleast_1d(y)
        fx = (x + self.hx) / self.step
        fy = (y + self.hy) / self.step
        inside = (fx >= 0) & (fy >= 0) & (fx <= self.cols - 1) \
            & (fy <= self.rows - 1)
        out = np.empty_like(x)
        if np.any(~inside):
            out[~inside] = self.dem.height(x[~inside], y[~inside])
        c = np.clip(np.floor(fx[inside]).astype(int), 0, self.cols - 2)
        r = np.clip(np.floor(fy[inside]).astype(int), 0, self.rows - 2)
        u, v = fx[inside] - c, fy[inside] - r
        h = self.h
        h00, h10 = h[r, c], h[r, c + 1]
        h01, h11 = h[r + 1, c], h[r + 1, c + 1]
        lower = u + v <= 1.0
        out[inside] = np.where(
            lower, h00 + u * (h10 - h00) + v * (h01 - h00),
            h11 + (1 - u) * (h01 - h11) + (1 - v) * (h10 - h11))
        return out[0] if scalar else out


def road_segment_index(net, extra=None):
    """First sample index of every drawn segment of a non-structure
    edge, plus the indices extra."""
    k = np.arange(len(net.sx) - 1)
    same = net.edge_of[k] == net.edge_of[k + 1]
    k = k[same & ~net.struct[net.edge_of[k]]]
    if extra is not None:
        k = np.sort(np.concatenate([k, extra]))
    return k


def road_segments(net, extra=None):
    """Consecutive drawn samples of non-structure edges as segments,
    plus the segments starting at the sample indices extra."""
    return segments(net, road_segment_index(net, extra))


def sidewalk_lift(net, k):
    """(segments, 2) sidewalk top minus MARGIN over the road ground on
    the left and right of segments k, 0 on a side without sidewalk."""
    lift = (net.slift[k] + net.slift[k + 1]) / 2 + KERB - MARGIN
    return np.where(net.walk[net.edge_of[k]], lift[:, None], 0.0)


def sidewalk_points(net, k, ts):
    """Points on the middle and outer line of every sidewalk at
    fractions ts of the segments k, and the ground the terrain must
    stay under there (absolute minus base)."""
    nrm = np.column_stack([-net.tangent[:, 1], net.tangent[:, 0]])
    lift = sidewalk_lift(net, k)
    hw = net.half[k]
    pts, gh = [], []
    for side, sign in ((0, 1.0), (1, -1.0)):
        on = lift[:, side] > 0
        kk = k[on]
        for t in ts:
            c = np.column_stack([net.sx[kk], net.sy[kk]]) * (1 - t) \
                + np.column_stack([net.sx[kk + 1], net.sy[kk + 1]]) * t
            n = nrm[kk] * (1 - t) + nrm[kk + 1] * t
            g = net.ground[kk] * (1 - t) + net.ground[kk + 1] * t
            for reach in (WIDTH / 2, WIDTH):
                pts.append(c + n * (sign * (hw[on] + reach))[:, None])
                gh.append(g + lift[on, side])
    return np.vstack(pts), np.concatenate(gh)


def corner_points(net):
    """Corners, edge midpoints and centre of every sidewalk corner at a
    junction, with the sidewalk top minus MARGIN over the base."""
    pts, gh = [], []
    for c in net.corners:
        poly = c["polygon"]
        mids = (poly + np.roll(poly, -1, axis=0)) / 2
        p = np.vstack([poly, mids, poly.mean(axis=0, keepdims=True)])
        pts.append(p)
        node = c["node"]
        gh.append(np.full(len(p), net.height[node] + net.lift[node]
                          + KERB - MARGIN))
    if not pts:
        return np.zeros((0, 2)), np.zeros(0)
    return np.vstack(pts), np.concatenate(gh)


JUNCTION_T = (0.25, 0.5, 0.75)


def junction_points(net):
    """Points covering every junction surface (centre, rim points and
    points between every pair of them) and its ground; the surface is
    flat, so these keep the terrain under its whole hull."""
    first, last = net.start[:-1], net.start[1:] - 1
    # junctions at a bridge or tunnel end lie on the structure, not on
    # the terrain
    rims = {int(n): [net.xy[n]]
            for n in np.flatnonzero(net.junction & ~net.node_struct)}
    for ends, smp in ((net.u, first), (net.v, last)):
        for node, s in zip(ends.tolist(), smp.tolist()):
            if node in rims:
                rims[node] += [net.left[s], net.right[s]]
    pts, gh = [], []
    for node, rim in rims.items():
        rim = np.array(rim)
        i, j = np.triu_indices(len(rim), 1)
        for t in JUNCTION_T:
            pts.append(rim[i] * (1 - t) + rim[j] * t)
        pts.append(rim)
        gh.append(np.full(len(i) * len(JUNCTION_T) + len(rim),
                          net.height[node]))
    if not pts:
        return np.zeros((0, 2)), np.zeros(0)
    return np.vstack(pts), np.concatenate(gh)


def segments(net, k):
    """Segments starting at sample indices k: ends, ground, half width."""
    a = np.column_stack([net.sx[k], net.sy[k]])
    b = np.column_stack([net.sx[k + 1], net.sy[k + 1]])
    return (a, b, net.ground[k], net.ground[k + 1],
            net.half[k])


def tunnel_segment_index(net):
    """First sample index of every drawn segment of a tunnel edge."""
    k = np.arange(len(net.sx) - 1)
    same = net.edge_of[k] == net.edge_of[k + 1]
    return k[same & (net.kind[net.edge_of[k]] == "tunnel")]


def segment_tree(net, k):
    """STRtree over the segments starting at sample indices k, or None."""
    if not len(k):
        return None
    a = np.column_stack([net.sx[k], net.sy[k]])
    b = np.column_stack([net.sx[k + 1], net.sy[k + 1]])
    return shapely.STRtree(shapely.linestrings(np.stack([a, b], axis=1)))


def project(p, a, b, ga, gb):
    """Distance from p to segment a-b and the ground height there."""
    ab = b - a
    t = np.einsum("ij,ij->i", p - a, ab) / np.maximum(
        np.einsum("ij,ij->i", ab, ab), 1e-12)
    t = np.clip(t, 0.0, 1.0)
    q = a + ab * t[:, None]
    return np.hypot(*(p - q).T), ga + (gb - ga) * t


def strip_points(a, b, ga, gb, hw, ts):
    """Centre and both edge points at fractions ts of every segment."""
    ab = b - a
    nrm = np.column_stack([-ab[:, 1], ab[:, 0]])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    pts, gh = [], []
    for t in ts:
        c = a + ab * t
        g = ga + (gb - ga) * t
        for side in (-1.0, 0.0, 1.0):
            pts.append(c + nrm * (hw * side)[:, None])
            gh.append(g)
    return np.vstack(pts), np.concatenate(gh)


def strip_crossings(a, b, ga, gb, hw, half, step):
    """Centre and edge points where a segment crosses a grid line or a
    triangle diagonal of the terrain mesh (rows along y, the diagonal
    from (i+1, j) to (i, j+1), fx + fy integer): terrain and road are
    piecewise linear, so the terrain rises highest over the road there or
    at the segment ends. Segments are shorter than a grid cell, so each
    of the three line families crosses at most once."""
    hx, hy = np.broadcast_to(half, 2)
    ab = b - a
    nrm = np.column_stack([-ab[:, 1], ab[:, 0]])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    pts, gh = [], []
    for side in (-1.0, 0.0, 1.0):
        p0 = a + nrm * (hw * side)[:, None]
        p1 = b + nrm * (hw * side)[:, None]
        fx0, fy0 = (p0[:, 0] + hx) / step, (p0[:, 1] + hy) / step
        fx1, fy1 = (p1[:, 0] + hx) / step, (p1[:, 1] + hy) / step
        for f0, f1 in ((fx0, fx1), (fy0, fy1), (fx0 + fy0, fx1 + fy1)):
            n = np.floor(np.maximum(f0, f1))
            cross = (np.floor(f0) != np.floor(f1)) & (f0 != f1)
            t = (n[cross] - f0[cross]) / (f1[cross] - f0[cross])
            t = np.clip(t, 0.0, 1.0)[:, None]
            pts.append(p0[cross] + (p1[cross] - p0[cross]) * t)
            gh.append(ga[cross] + (gb[cross] - ga[cross]) * t[:, 0])
    if not pts:
        return np.zeros((0, 2)), np.zeros(0)
    return np.vstack(pts), np.concatenate(gh)


PUSH_ROUNDS = 20
# below this barycentric weight of free corners a point moves locked ones
# too; a third (the centroid) keeps a free corner from dropping more than
# three times the excess, which would dig pits next to an abutment
LOCK_MIN_WEIGHT = 1 / 3


def push_down(h, half, step, pts, gh, locked=None):
    """Lower triangle corners until no point of pts is above gh.

    Every corner of the triangle under a point drops by the excess. With
    a boolean grid locked (the corners pin_lines set), only the free
    corners of that triangle drop, by excess / their barycentric weight
    at the point, so the pinned plane stays; a point (almost) on locked
    corners only (weight below LOCK_MIN_WEIGHT) moves them all anyway.
    """
    rows, cols = h.shape
    hx, hy = np.broadcast_to(half, 2)
    fx = (pts[:, 0] + hx) / step
    fy = (pts[:, 1] + hy) / step
    ok = (fx >= 0) & (fy >= 0) & (fx < cols - 1) & (fy < rows - 1)
    fx, fy, gh = fx[ok], fy[ok], gh[ok]
    c, r = np.floor(fx).astype(int), np.floor(fy).astype(int)
    u, v = fx - c, fy - r
    lower = u + v <= 1.0
    # the three corners of the triangle each point lies in, and weights
    corners = [(r, c + 1), (r + 1, c),
               (np.where(lower, r, r + 1), np.where(lower, c, c + 1))]
    weights = [np.where(lower, u, 1 - v), np.where(lower, v, 1 - u),
               np.where(lower, 1 - u - v, u + v - 1)]
    if locked is None:
        locked = np.zeros(h.shape, dtype=bool)
    free = [~locked[rr, cc] for rr, cc in corners]
    share = sum(np.where(f, w, 0.0) for f, w in zip(free, weights))
    stuck = share < LOCK_MIN_WEIGHT
    scale = np.where(stuck, 1.0, 1.0 / np.maximum(share, LOCK_MIN_WEIGHT))
    before = h.copy()
    for _ in range(PUSH_ROUNDS):
        h00, h10 = h[r, c], h[r, c + 1]
        h01, h11 = h[r + 1, c], h[r + 1, c + 1]
        t = np.where(lower, h00 + u * (h10 - h00) + v * (h01 - h00),
                     h11 + (1 - u) * (h01 - h11) + (1 - v) * (h10 - h11))
        excess = t - gh
        bad = excess > 1e-6
        if not np.any(bad):
            break
        drop = np.zeros_like(h)
        for (rr, cc), f in zip(corners, free):
            sel = bad & (f | stuck)
            np.maximum.at(drop, (rr[sel], cc[sel]), (excess * scale)[sel])
        h -= drop
    return int(np.count_nonzero(h < before - 1e-9))


PIN_STEP = 0.5


def line_corners(shape, half, step, lines):
    """Corners of every terrain triangle crossing one of the lines, in a
    grid of shape (rows, cols) around +-half (scalar or hx, hy).

    lines = (p, d, half_len, g0, grade_in, grade_out): centre, unit
    direction into the deck, half length across, ground height at p
    (absolute) and its grade along d on the deck side and on the other
    side. Returns row, column, line index and the plane height there
    (g0 + grade * (corner - p) . d, with the grade of the corner's side)
    per corner and line.
    """
    p, d, hl, g0, g_in, g_out = lines
    nrm = np.column_stack([-d[:, 1], d[:, 0]])
    cnt = int(np.ceil(2 * hl.max() / PIN_STEP)) + 1
    w = np.linspace(-1.0, 1.0, cnt)
    q = (p[:, None] + (hl[:, None, None] * w[None, :, None])
         * nrm[:, None]).reshape(-1, 2)
    line = np.repeat(np.arange(len(p)), cnt)
    rows, cols = shape
    hx, hy = np.broadcast_to(half, 2)
    fx, fy = (q[:, 0] + hx) / step, (q[:, 1] + hy) / step
    ok = (fx >= 0) & (fy >= 0) & (fx < cols - 1) & (fy < rows - 1)
    fx, fy, line = fx[ok], fy[ok], line[ok]
    c, r = np.floor(fx).astype(int), np.floor(fy).astype(int)
    lower = (fx - c) + (fy - r) <= 1.0
    rr = np.concatenate([r, r + 1, np.where(lower, r, r + 1)])
    cc = np.concatenate([c + 1, c, np.where(lower, c, c + 1)])
    li = np.tile(line, 3)
    _, first = np.unique((rr * cols + cc) * len(p) + li, return_index=True)
    rr, cc, li = rr[first], cc[first], li[first]
    cx, cy = cc * step - hx, rr * step - hy
    along = (cx - p[li, 0]) * d[li, 0] + (cy - p[li, 1]) * d[li, 1]
    grade = np.where(along >= 0, g_in[li], g_out[li])
    return rr, cc, li, g0[li] + grade * along


def pin_lines(h, half, step, lines):
    """Pin the corners of every triangle crossing a line to its plane
    (line_corners), the lowest one if several lines reach a corner.

    Returns the pinned heights as a grid, NaN where nothing is pinned
    (push_down keeps the pinned corners where it can).
    """
    rows, cols = h.shape
    pin = np.full(rows * cols, np.inf)
    if len(lines[0]):
        rr, cc, _, target = line_corners(h.shape, half, step, lines)
        np.minimum.at(pin, rr * cols + cc, target)
    hit = np.isfinite(pin)
    h.ravel()[hit] = pin[hit]
    pin[~hit] = np.nan
    return pin.reshape(rows, cols)


def conform(net, dem, base, half, step, bridges=None, islands=()):
    """Conformed grid (absolute heights) and a few numbers about it.

    bridges: a bridges.BridgeLayout (deck and low segments, abutments)
    or None; islands: the plates of islands.find_islands.
    """
    hx, hy = np.broadcast_to(half, 2)
    nx = int(round(2 * hx / step)) + 1
    ny = int(round(2 * hy / step)) + 1
    xs, ys = np.meshgrid(np.linspace(-hx, hx, nx), np.linspace(-hy, hy, ny))
    xs, ys = xs.ravel(), ys.ravel()
    orig = dem.height(xs, ys)
    target = np.full(len(xs), np.nan)
    weight = np.zeros(len(xs))

    no_k = np.zeros(0, dtype=int)
    low_k = bridges.low_k if bridges is not None else no_k
    deck_k = bridges.deck_k if bridges is not None else no_k
    k = road_segment_index(net, low_k)
    a, b, ga, gb, hw = segments(net, k)
    ga, gb = ga + base, gb + base
    tree = shapely.STRtree(shapely.linestrings(
        np.stack([a, b], axis=1)))
    reach = float(hw.max()) + FLAT + SHOULDER
    # grid points nearer to one of these than to a road keep DGM1
    keep_trees = {"tunnels": segment_tree(net, tunnel_segment_index(net)),
                  "bridges": segment_tree(net, deck_k)}
    kept = dict.fromkeys(keep_trees, 0)
    for s in range(0, len(xs), CHUNK):
        sl = slice(s, s + CHUNK)
        pts = shapely.points(xs[sl], ys[sl])
        p_xy = np.column_stack([xs[sl], ys[sl]])
        (pi, si), _ = tree.query_nearest(pts, max_distance=reach,
                                         return_distance=True)
        pi, first = np.unique(pi, return_index=True)
        si = si[first]
        d, gh = project(p_xy[pi], a[si], b[si], ga[si], gb[si])
        edge = np.clip((d - hw[si] - FLAT) / SHOULDER, 0.0, 1.0)
        w = 1.0 - edge * edge * (3.0 - 2.0 * edge)
        for name, keep_tree in keep_trees.items():
            if keep_tree is None:
                continue
            (ti, _), td = keep_tree.query_nearest(
                pts[pi], max_distance=reach, return_distance=True)
            dt = np.full(len(pi), np.inf)
            np.minimum.at(dt, ti, td)
            over = (dt < d) & (w > 0)
            kept[name] += int(np.count_nonzero(over))
            w[over] = 0.0
        idx = pi + s
        target[idx], weight[idx] = gh, w

    near = weight > 0
    h = orig.copy()
    h[near] = orig[near] + weight[near] * (target[near] - orig[near])
    h = h.reshape(ny, nx)
    pin = np.full(h.shape, np.nan)
    if bridges is not None:
        pin = pin_lines(h, half, step, bridges.lines(net, base))
    if len(deck_k):
        da, db, dga, dgb, dhw = segments(net, deck_k)
        a, b = np.vstack([a, da]), np.vstack([b, db])
        ga = np.concatenate([ga, dga + base])
        gb = np.concatenate([gb, dgb + base])
        hw = np.concatenate([hw, dhw])
    pts, gh = strip_points(a, b, ga, gb, hw, PUSH_T)
    cpts, cgh = strip_crossings(a, b, ga, gb, hw, half, step)
    pts, gh = np.vstack([pts, cpts]), np.concatenate([gh, cgh])
    for extra, extra_gh in (sidewalk_points(net, k, PUSH_T),
                            junction_points(net), corner_points(net),
                            plate_points(islands)):
        pts = np.vstack([pts, extra])
        gh = np.concatenate([gh, extra_gh + base])
    pushed = push_down(h, half, step, pts, gh, np.isfinite(pin))
    h = h.ravel()
    delta = h - orig
    changed = np.abs(delta) > 0.01
    stats = {"grid_step_m": step, "flat_m": FLAT, "shoulder_m": SHOULDER,
             "grid_points": int(len(h)),
             "points_flat": int(np.count_nonzero(weight >= 1.0)),
             "points_changed": int(np.count_nonzero(changed)),
             "points_pushed_down": pushed,
             "points_kept_over_tunnels": kept["tunnels"],
             "points_kept_under_bridges": kept["bridges"],
             "corners_pinned_at_abutments": int(np.count_nonzero(
                 np.isfinite(pin))),
             "pinned_corners_pushed_down": int(np.count_nonzero(
                 h.reshape(ny, nx) < pin - 1e-4)),
             "cut_max_m": float(-delta.min()),
             "fill_max_m": float(delta.max()),
             "abs_change_p95_m": float(np.percentile(
                 np.abs(delta[changed]), 95)) if np.any(changed) else 0.0}
    terrain = ConformedTerrain(dem, half, step, h.reshape(ny, nx), stats)
    terrain.pin = pin
    return terrain
# - revised 2026-10-23 (rectangular grid: rows along y, columns along x)
# - revised 2026-10-25 (push points where the strips cross the mesh lines)
# - revised 2026-11-04 (terrain kept under the island plates)
