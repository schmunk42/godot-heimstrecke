# file generated with AI assistance: Claude Code - 2026-10-21 22:20:00 UTC
"""Helpers shared by the structure layers (tunnels.py, bridges.py).

Structure geometry is a list of quads with both windings, because the
Godot material and the trimesh collision are one-sided; it is collected
per tile and emitted into one mesh layer. Strips answers whether a point
lies on another drivable strip, so walls and parapets can leave out the
pieces that would stand on a branching ramp.
"""
import numpy as np
import shapely

from roads import tile_keys

# a wall foot on another strip within this height is in its way (a ramp
# branching off); a strip farther above or below crosses over or under
STRIP_DH = 2.5


def quads(p0, p1, p2, p3):
    """Both windings of the quads p0-p1-p2-p3 (glTF vertices, m x 3)."""
    m = len(p0)
    v = np.stack([p0, p1, p2, p3], axis=1).reshape(-1, 3)
    o = 4 * np.arange(m)[:, None]
    f = np.vstack([o + [0, 1, 2], o + [0, 2, 3]])
    return np.vstack([v, v]), np.vstack([f, f[:, ::-1] + 4 * m])


class StructureGeometry:
    """Quads of one structure layer and the stats of their builder.

    pieces: (tile key, vertices, faces, colour) per batch of quads.
    """

    def __init__(self):
        self.pieces = []
        self.stats = {}

    def add(self, tiles, xy, p, color):
        """Quads p = (p0, p1, p2, p3), placed in tiles by plan point xy."""
        keys = tile_keys(tiles, xy[:, 0], xy[:, 1])
        for key in np.unique(keys):
            if key < 0:
                continue
            sel = keys == key
            verts, faces = quads(*(q[sel] for q in p))
            self.pieces.append((int(key), verts, faces, color))

    def emit(self, tiles, layer):
        """All quads into the tiles' `layer` buckets."""
        for key, verts, faces, color in self.pieces:
            tiles.bucket(key)[layer].add(verts, faces, color)


class Strips:
    """Every drawn segment of every drivable edge, for inside()."""

    def __init__(self, net):
        k = np.arange(len(net.sx) - 1)
        k = k[net.edge_of[k] == net.edge_of[k + 1]]
        self.edge = net.edge_of[k]
        self.hw = net.half[k]
        self.h = (net.surface[k] + net.surface[k + 1]) / 2
        self.tree = shapely.STRtree(shapely.linestrings(np.stack(
            [np.column_stack([net.sx[k], net.sy[k]]),
             np.column_stack([net.sx[k + 1], net.sy[k + 1]])], axis=1)))

    def inside(self, pts, h, own):
        """Per point: on the strip of an edge other than own, within
        STRIP_DH of the surface height h."""
        pi, si = self.tree.query(shapely.points(pts), predicate="dwithin",
                                 distance=float(self.hw.max()))
        keep = (self.edge[si] != own[pi]) \
            & (np.abs(self.h[si] - h[pi]) < STRIP_DH)
        pi, si = pi[keep], si[keep]
        d = shapely.distance(shapely.points(pts[pi]),
                             self.tree.geometries[si])
        out = np.zeros(len(pts), dtype=bool)
        out[pi[d < self.hw[si]]] = True
        return out
# - revised 2026-10-22 (tiles own their key lookup)
