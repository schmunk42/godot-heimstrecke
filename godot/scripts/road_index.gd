# file generated with AI assistance: Claude Code - 2026-10-23 14:30:00 UTC
extends RefCounted
## The road centre lines of a world (roads.bin from pipeline/build.py:
## float32 rows x, y, z, edge, rank, y the drawn road surface) in a grid
## of CELL_M cells, for "put the car back on the nearest road" (F), the
## start map (a click snaps onto a road) and the minimap.
## Consecutive rows of the same edge are a segment; nearest() projects
## onto the segments of the cells around the point, ring by ring, and
## compares in 3D, so a car under a bridge lands on the road below and
## one on the bridge on the deck; with flat (a map click, no height)
## only x and z count.

const CELL_M := 50.0
## rings of cells searched before giving up (about 2 km)
const MAX_RING := 40
const FLOATS := 5

var _rows := PackedFloat32Array()
var _cells := {}


## Reads the rows; returns the number of segments, 0 if there are none.
func load_rows(bytes: PackedByteArray) -> int:
	_rows = bytes.to_float32_array()
	_cells.clear()
	var count := 0
	var n := _rows.size() / FLOATS
	for i in n - 1:
		var a := i * FLOATS
		var b := a + FLOATS
		if _rows[a + 3] != _rows[b + 3]:
			continue
		var lo := Vector2i(floori(minf(_rows[a], _rows[b]) / CELL_M),
			floori(minf(_rows[a + 2], _rows[b + 2]) / CELL_M))
		var hi := Vector2i(floori(maxf(_rows[a], _rows[b]) / CELL_M),
			floori(maxf(_rows[a + 2], _rows[b + 2]) / CELL_M))
		for cx in range(lo.x, hi.x + 1):
			for cz in range(lo.y, hi.y + 1):
				var key := Vector2i(cx, cz)
				if not _cells.has(key):
					_cells[key] = PackedInt32Array()
				_cells[key].append(i)
		count += 1
	return count


## Every edge as a polyline of its rows, in row order (route_marks.gd
## finds the roads that leave a route).
func edge_lines() -> Array[PackedVector3Array]:
	var lines: Array[PackedVector3Array] = []
	var line := PackedVector3Array()
	for i in _rows.size() / FLOATS:
		var a := i * FLOATS
		if i > 0 and _rows[a + 3] != _rows[a + 3 - FLOATS]:
			lines.append(line)
			line = PackedVector3Array()
		line.append(_point(i))
	if not line.is_empty():
		lines.append(line)
	return lines


func is_empty() -> bool:
	return _cells.is_empty()


## The nearest point on a road to `at`: {"point", "dir"} with dir the
## horizontal unit direction of that segment, turned to agree with
## `heading`; an empty dictionary if no road lies within MAX_RING cells.
func nearest(at: Vector3, heading: Vector3, flat := false) -> Dictionary:
	var centre := Vector2i(floori(at.x / CELL_M), floori(at.z / CELL_M))
	var best := INF
	var best_i := -1
	var best_t := 0.0
	var seen := {}
	for ring in MAX_RING + 1:
		for cx in range(centre.x - ring, centre.x + ring + 1):
			for cz in range(centre.y - ring, centre.y + ring + 1):
				if maxi(absi(cx - centre.x), absi(cz - centre.y)) != ring:
					continue
				var key := Vector2i(cx, cz)
				if not _cells.has(key):
					continue
				for i: int in _cells[key]:
					if seen.has(i):
						continue
					seen[i] = true
					var a := _point(i)
					var ab := _point(i + 1) - a
					var rel := at - a
					if flat:
						ab.y = 0.0
						rel.y = 0.0
					var t := clampf(rel.dot(ab) / maxf(ab.dot(ab), 1e-9),
						0.0, 1.0)
					var d := rel.distance_squared_to(ab * t)
					if d < best:
						best = d
						best_i = i
						best_t = t
		# everything farther out lies beyond this ring
		if best_i >= 0 and sqrt(best) <= ring * CELL_M:
			break
	if best_i < 0:
		return {}
	var a := _point(best_i)
	var b := _point(best_i + 1)
	var dir := b - a
	dir.y = 0.0
	dir = dir.normalized()
	var level := Vector3(heading.x, 0.0, heading.z)
	if level.dot(dir) < 0.0:
		dir = -dir
	return {"point": a.lerp(b, best_t), "dir": dir,
		"edge": int(_rows[best_i * FLOATS + 3]),
		"distance": sqrt(best)}


## First rows of the segments in the cells within `radius` of `at`
## (each once), for the minimap.
func segments_near(at: Vector3, radius: float) -> PackedInt32Array:
	var out := PackedInt32Array()
	var seen := {}
	var lo := Vector2i(floori((at.x - radius) / CELL_M),
		floori((at.z - radius) / CELL_M))
	var hi := Vector2i(floori((at.x + radius) / CELL_M),
		floori((at.z + radius) / CELL_M))
	for cx in range(lo.x, hi.x + 1):
		for cz in range(lo.y, hi.y + 1):
			var key := Vector2i(cx, cz)
			if not _cells.has(key):
				continue
			for i: int in _cells[key]:
				if not seen.has(i):
					seen[i] = true
					out.append(i)
	return out


## Start and end of segment i (its first row and the next).
func segment(i: int) -> Array[Vector3]:
	return [_point(i), _point(i + 1)]


## Road rank of segment i (pipeline/roads.py ROAD_RANK: 2 residential,
## 4 tertiary, 5 secondary, 6 primary, 7 trunk, 8 motorway).
func rank(i: int) -> int:
	return int(_rows[i * FLOATS + 4])


func _point(i: int) -> Vector3:
	var k := i * FLOATS
	return Vector3(_rows[k], _rows[k + 1], _rows[k + 2])
# - revised 2026-10-23 (rank column, flat search, segments_near)
# - revised 2026-10-26 (edge_lines for the route boards)
