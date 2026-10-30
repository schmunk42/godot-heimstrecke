# file generated with AI assistance: Claude Code - 2026-10-21 17:30:00 UTC
"""Tunnel tubes and portal cuts (stage A2.2c).

conform.py leaves the DGM1 terrain over tunnels alone, so a tunnel road
runs inside the hill. Every tunnel edge is split into the segments
between its 5 m samples, and the conformed terrain is read at the centre
and on both wall lines (WALL_GAP beyond the strip edge) of every sample:

- covered: at both ends the terrain is at least COVER_MIN above the road
  surface on all three lines. The segment gets a tube: walls from below
  the road up to the ceiling, the ceiling at
  min(surface + CLEARANCE, terrain - CEILING_COVER).
- slot: not covered, but somewhere at its ends the terrain is above the
  road (the cut in front of a portal, a shallow stretch). The terrain
  mesh is cut away between the wall lines (cut_mesh) and retaining walls
  run from below the road to PARAPET above the terrain.
- open: the terrain is below the road at both ends; nothing is added.

Where a tube ends without another tube following, a portal face closes
the gap between the ceiling and the terrain. Both kinds get a floor
between the wall lines just below the road. Wall pieces whose foot lies
on another drivable strip (a ramp branching off inside the tunnel) are
left out. Every face is emitted with both windings, because the Godot
material and the trimesh collision are one-sided; everything goes into
the `tunnels` layer, which world.gd loads with collision like every other
layer.
"""
import mapbox_earcut
import numpy as np
import shapely

from conform import tunnel_segment_index
from frame import xyz
from roads import tile_keys
from structures import Strips, StructureGeometry

COVER_MIN = 4.0
CLEARANCE = 5.5
CEILING_COVER = 0.5
WALL_GAP = 0.5
# walls reach FOOT below the road surface, slot walls and portal faces
# PARAPET above the terrain (hides the step between the straight wall
# top and the terrain triangles), the floor lies FLOOR_DROP under the road
FOOT = 0.3
PARAPET = 0.3
FLOOR_DROP = 0.05
# pieces per segment for slot walls (about 1 m), metres per face piece
WALL_SUB = 5
FACE_STEP = 1.0
COLORS = {"wall": (0.62, 0.61, 0.58), "ceiling": (0.40, 0.40, 0.41),
          "portal": (0.55, 0.54, 0.51), "floor": (0.24, 0.24, 0.26)}


class TunnelGeometry(StructureGeometry):
    """Tunnel quads plus cut: union of the slot footprints or None."""

    def __init__(self):
        super().__init__()
        self.cut = None


def end_neighbours(net, covered_end):
    """Per edge end (u, v): does a tube go on past the node.

    True at a junction (a face there would close the other branches)
    and at a degree-2 node whose other edge ends in a covered segment;
    False at portals and dead ends.
    """
    m = len(net.edges)
    ends = np.concatenate([net.u, net.v])
    cov = np.concatenate([covered_end[:, 0], covered_end[:, 1]])
    order = np.argsort(ends, kind="stable")
    out = net.degree[ends] >= 3
    pair = order[net.degree[ends[order]] == 2].reshape(-1, 2)
    out[pair[:, 0]] = cov[pair[:, 1]]
    out[pair[:, 1]] = cov[pair[:, 0]]
    return out.reshape(2, m).T


def build_tunnels(net, ground, base, tiles):
    """Classify tunnel segments, build tubes, slots and portal faces."""
    geo = TunnelGeometry()
    k = tunnel_segment_index(net)
    tunnel_edges = np.flatnonzero(net.kind == "tunnel")
    if not len(k):
        geo.stats = {"edges": 0}
        return geo
    # every sample of a tunnel edge (segment starts plus the last one)
    s = np.unique(np.concatenate([k, k + 1]))
    edge = net.edge_of[s]
    p = np.column_stack([net.sx[s], net.sy[s]])
    nrm = np.column_stack([-net.tangent[s, 1], net.tangent[s, 0]])
    off = (net.half[s] + WALL_GAP)[:, None] * nrm
    left, right = p + off, p - off
    surf = net.surface[s]
    t = [ground.height(q[:, 0], q[:, 1]) - base for q in (p, left, right)]
    cover = np.minimum.reduce(t) - surf
    above = np.maximum.reduce(t) > surf
    ceil = surf + np.clip(cover - CEILING_COVER, 0.0, CLEARANCE)
    pos = np.searchsorted(s, k)
    a, b = pos, pos + 1
    covered = (cover[a] >= COVER_MIN) & (cover[b] >= COVER_MIN)
    slot = ~covered & (above[a] | above[b])
    seg_edge = edge[a]

    # walls: covered up to the ceiling, slots up to the terrain
    sub = np.linspace(0.0, 1.0, WALL_SUB + 1)
    walls = covered | slot
    wa, wb = a[walls], b[walls]
    wcov = covered[walls]
    dropped = 0
    strips = Strips(net)
    for side in (left, right):
        t0, t1 = sub[:-1], sub[1:]
        q0 = side[wa][:, None] + (side[wb] - side[wa])[:, None] \
            * t0[None, :, None]
        q1 = side[wa][:, None] + (side[wb] - side[wa])[:, None] \
            * t1[None, :, None]
        f0 = surf[wa][:, None] + (surf[wb] - surf[wa])[:, None] * t0 - FOOT
        f1 = surf[wa][:, None] + (surf[wb] - surf[wa])[:, None] * t1 - FOOT
        c0 = ceil[wa][:, None] + (ceil[wb] - ceil[wa])[:, None] * t0
        c1 = ceil[wa][:, None] + (ceil[wb] - ceil[wa])[:, None] * t1
        q0, q1 = q0.reshape(-1, 2), q1.reshape(-1, 2)
        g0 = ground.height(q0[:, 0], q0[:, 1]) - base + PARAPET
        g1 = ground.height(q1[:, 0], q1[:, 1]) - base + PARAPET
        cov = np.repeat(wcov, WALL_SUB)
        top0 = np.where(cov, c0.ravel(), g0)
        top1 = np.where(cov, c1.ravel(), g1)
        f0, f1 = f0.ravel(), f1.ravel()
        own = np.repeat(seg_edge[walls], WALL_SUB)
        inside = strips.inside(q0, f0 + FOOT, own) \
            | strips.inside(q1, f1 + FOOT, own)
        keep = ~inside & ((top0 > f0) | (top1 > f1))
        dropped += int(np.count_nonzero(inside))
        q0, q1 = q0[keep], q1[keep]
        top0 = np.maximum(top0[keep], f0[keep])
        top1 = np.maximum(top1[keep], f1[keep])
        geo.add(tiles, (q0 + q1) / 2,
                (xyz(q0[:, 0], f0[keep], q0[:, 1]),
                 xyz(q1[:, 0], f1[keep], q1[:, 1]),
                 xyz(q1[:, 0], top1, q1[:, 1]),
                 xyz(q0[:, 0], top0, q0[:, 1])), COLORS["wall"])

    # ceilings over covered segments, floors under covered and slots
    ca, cb = a[covered], b[covered]
    mid = (p[a] + p[b]) / 2
    geo.add(tiles, mid[covered],
            (xyz(left[ca, 0], ceil[ca], left[ca, 1]),
             xyz(left[cb, 0], ceil[cb], left[cb, 1]),
             xyz(right[cb, 0], ceil[cb], right[cb, 1]),
             xyz(right[ca, 0], ceil[ca], right[ca, 1])), COLORS["ceiling"])
    fl = surf - FLOOR_DROP
    geo.add(tiles, mid[walls],
            (xyz(left[wa, 0], fl[wa], left[wa, 1]),
             xyz(left[wb, 0], fl[wb], left[wb, 1]),
             xyz(right[wb, 0], fl[wb], right[wb, 1]),
             xyz(right[wa, 0], fl[wa], right[wa, 1])), COLORS["floor"])

    faces = portal_faces(net, geo, tiles, ground, base, (s, a, b, covered),
                         (left, right, ceil))
    if np.any(slot):
        sa, sb = a[slot], b[slot]
        rings = np.stack([left[sa], left[sb], right[sb], right[sa],
                          left[sa]], axis=1)
        geo.cut = shapely.union_all(shapely.polygons(rings))
        shapely.prepare(geo.cut)

    seg_len = np.hypot(*(p[b] - p[a]).T)
    inside = tile_keys(tiles, mid[:, 0], mid[:, 1]) >= 0
    clear = (ceil - surf)[np.unique(np.concatenate([ca, cb]))]
    km = {name: float(seg_len[inside & sel].sum()) / 1000
          for name, sel in (("covered", covered), ("slot", slot),
                            ("open", ~covered & ~slot))}
    geo.stats = {
        "edges": len(tunnel_edges),
        "covered_km": round(km["covered"], 3),
        "slot_km": round(km["slot"], 3),
        "open_km": round(km["open"], 3),
        "portal_faces": faces,
        "wall_pieces_dropped": dropped,
        "ceiling_clearance_m": {
            "p50": round(float(np.median(clear)), 2) if len(clear) else None,
            "min": round(float(clear.min()), 2) if len(clear) else None,
            "n": len(clear)},
        "cover_p50_m": round(float(np.median(cover)), 2),
        "cover_min_m": COVER_MIN, "clearance_m": CLEARANCE,
        "ceiling_cover_m": CEILING_COVER,
        "cut_area_m2": round(float(geo.cut.area), 1)
        if geo.cut is not None else 0.0}
    return geo


def portal_faces(net, geo, tiles, ground, base, seg, lines):
    """Faces from the ceiling up to the terrain where a tube ends.

    A tube end needs one unless the next segment is covered: within the
    edge that is the neighbouring segment, at an edge end see
    end_neighbours.
    """
    s, a, b, covered = seg
    left, right, ceil = lines
    edge = net.edge_of[s[a]]
    first = np.r_[True, edge[1:] != edge[:-1]]
    last = np.r_[edge[1:] != edge[:-1], True]
    prev_cov = np.r_[False, covered[:-1]] & ~first
    next_cov = np.r_[covered[1:], False] & ~last
    m = len(net.edges)
    end_cov = np.zeros((m, 2), dtype=bool)
    end_cov[edge[first], 0] = covered[first]
    end_cov[edge[last], 1] = covered[last]
    across = end_neighbours(net, end_cov)
    prev_cov |= first & across[edge, 0]
    next_cov |= last & across[edge, 1]
    at = np.concatenate([a[covered & ~prev_cov], b[covered & ~next_cov]])
    n = int(np.ceil(np.max(np.hypot(*(left - right).T)) / FACE_STEP)) + 1
    w = np.linspace(0.0, 1.0, n)
    q = left[at][:, None] + (right[at] - left[at])[:, None] * w[None, :,
                                                                None]
    top = ground.height(q[..., 0].ravel(), q[..., 1].ravel()) - base \
        + PARAPET
    top = np.maximum(top.reshape(len(at), n), ceil[at][:, None])
    q0, q1 = q[:, :-1].reshape(-1, 2), q[:, 1:].reshape(-1, 2)
    t0, t1 = top[:, :-1].ravel(), top[:, 1:].ravel()
    c = np.repeat(ceil[at], n - 1)
    keep = (t0 > c) | (t1 > c)
    q0, q1, t0, t1, c = q0[keep], q1[keep], t0[keep], t1[keep], c[keep]
    geo.add(tiles, (q0 + q1) / 2,
            (xyz(q0[:, 0], c, q0[:, 1]), xyz(q1[:, 0], c, q1[:, 1]),
             xyz(q1[:, 0], t1, q1[:, 1]), xyz(q0[:, 0], t0, q0[:, 1])),
            COLORS["portal"])
    return len(at)


def barycentric(tri, pts):
    """Weights of pts (k x 2) in the triangle tri (3 x 2)."""
    a, b, c = tri
    m = np.array([b - a, c - a]).T
    uv = np.linalg.solve(m, (pts - a).T).T
    return np.column_stack([1 - uv.sum(axis=1), uv])


def cut_mesh(xs, ys, hs, faces, colors, cut):
    """Terrain grid minus the cut footprint (plan view).

    Triangles clear of the cut stay as they are, triangles inside it go,
    the rest are clipped and re-triangulated on their own plane (heights
    and colours interpolated). Returns xs, ys, hs, faces, colors with the
    new vertices appended, and the clipped and removed triangle counts.
    """
    tri = np.stack([xs[faces], ys[faces]], axis=-1)
    lo, hi = tri.min(axis=1), tri.max(axis=1)
    x0, y0, x1, y1 = cut.bounds
    near = np.flatnonzero((hi[:, 0] >= x0) & (lo[:, 0] <= x1)
                          & (hi[:, 1] >= y0) & (lo[:, 1] <= y1))
    polys = shapely.polygons(np.concatenate([tri[near], tri[near, :1]],
                                            axis=1))
    hit = shapely.intersects(cut, polys)
    near = near[hit]
    if not len(near):
        return xs, ys, hs, faces, colors, 0, 0
    rest = shapely.difference(polys[hit], cut)
    drop = np.zeros(len(faces), dtype=bool)
    drop[near] = True
    nx, ny, nh, nc, nf = [], [], [], [], []
    n = len(xs)
    clipped = 0
    for i, geom in zip(near, rest):
        area = shapely.area(geom)
        ab, ac = tri[i, 1] - tri[i, 0], tri[i, 2] - tri[i, 0]
        whole = abs(ab[0] * ac[1] - ab[1] * ac[0]) / 2
        if area >= whole * (1 - 1e-9):
            drop[i] = False
            continue
        if area < 1e-4:
            continue
        clipped += 1
        for poly in getattr(geom, "geoms", [geom]):
            if poly.geom_type != "Polygon" or poly.area < 1e-4:
                continue
            rings = [np.asarray(poly.exterior.coords)[:-1]]
            rings += [np.asarray(r.coords)[:-1] for r in poly.interiors]
            flat = np.vstack(rings)
            ends = np.cumsum([len(r) for r in rings]).astype(np.uint32)
            t = mapbox_earcut.triangulate_float64(flat, ends).reshape(-1, 3)
            if not len(t):
                continue
            ab, ac = flat[t[:, 1]] - flat[t[:, 0]], flat[t[:, 2]] - flat[
                t[:, 0]]
            flip = ab[:, 0] * ac[:, 1] - ab[:, 1] * ac[:, 0] < 0
            t[flip] = t[flip][:, [0, 2, 1]]
            w = barycentric(tri[i], flat)
            nx.append(flat[:, 0])
            ny.append(flat[:, 1])
            nh.append(w @ hs[faces[i]])
            nc.append(w @ colors[faces[i]])
            nf.append(t + n)
            n += len(flat)
    removed = int(np.count_nonzero(drop)) - clipped
    if nf:
        xs = np.concatenate([xs, *nx])
        ys = np.concatenate([ys, *ny])
        hs = np.concatenate([hs, *nh])
        colors = np.vstack([colors, *nc])
        faces = np.vstack([faces[~drop], *nf])
    else:
        faces = faces[~drop]
    return xs, ys, hs, faces, colors, clipped, removed
