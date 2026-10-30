# file generated with AI assistance: Claude Code - 2026-10-27 19:00:00 UTC
extends SceneTree
## Checks the gates and the barriers of a route without a world:
## route_gates.gd puts a checkpoint every 4 to 10 km (a 41 km route
## gets 6 gates, a 6 km one start and finish only, a 10.5 km one 3); a
## route turning right at a T junction gets a board on each of the two
## side roads and one barrier arc between them (route_marks.gd), the
## same route straight on none; the curve sign carries a bent arrow and
## stands on the outside of the curve. Exit code 1 on a failure.
##
##   godot --headless --path godot --script res://tests/route_gates_test.gd

const GATES := preload("res://scripts/route_gates.gd")
const MARKS := preload("res://scripts/route_marks.gd")
const ROADS := preload("res://scripts/road_index.gd")

var _failed := false


func _initialize() -> void:
	_expect("41 km", GATES.checkpoints(_straight(41000.0)).size(), 6)
	_expect("6 km", GATES.checkpoints(_straight(6000.0)).size(), 2)
	_expect("10.5 km", GATES.checkpoints(_straight(10500.0)).size(), 3)
	var legs := GATES.checkpoints(_straight(41000.0))
	for k in range(1, legs.size()):
		var leg := (legs[k] - legs[k - 1]) * 5.0
		if leg < 4000.0 or leg > 10000.0:
			_fail("leg %d is %.0f m" % [k, leg])

	# a route from the west turning right (towards +z) at x = 100, a side
	# road straight on (east) and one to the north
	var turn: Array = []
	for x in range(0, 100, 5):
		turn.append([float(x), 0.0, 0.0])
	for z in range(0, 200, 5):
		turn.append([100.0, 0.0, float(z)])
	var rows := PackedFloat32Array()
	_edge(rows, turn, 0)
	_edge(rows, _line(Vector3(110, 0, 0), Vector3(200, 0, 0)), 1)
	_edge(rows, _line(Vector3(100, 0, -10), Vector3(100, 0, -100)), 2)
	var roads := ROADS.new()
	roads.load_rows(rows.to_byte_array())
	var marks := MARKS.new()
	root.add_child(marks)
	_expect("turn: 2 boards and an arc", marks.build(turn, roads, 0), 3)

	var straight_on: Array = []
	for x in range(0, 200, 5):
		straight_on.append([float(x), 0.0, 0.0])
	var rows2 := PackedFloat32Array()
	_edge(rows2, straight_on, 0)
	_edge(rows2, _line(Vector3(100, 0, -10), Vector3(100, 0, -100)), 1)
	_edge(rows2, _line(Vector3(100, 0, 10), Vector3(100, 0, 100)), 2)
	var roads2 := ROADS.new()
	roads2.load_rows(rows2.to_byte_array())
	var marks2 := MARKS.new()
	root.add_child(marks2)
	_expect("crossing: 2 boards, no arc", marks2.build(straight_on, roads2,
		0), 2)

	var lines: Array = MARKS._sign_lines({"grade": 3, "dir": "left"})
	_expect("sign lines", lines, ["3", "@curve_left"])

	print("ROUTE GATES " + ("FAILED" if _failed else "OK"))
	quit(1 if _failed else 0)


func _straight(length: float) -> Array:
	var points: Array = []
	for i in int(length / 5.0) + 1:
		points.append([i * 5.0, 0.0, 0.0])
	return points


func _line(a: Vector3, b: Vector3) -> Array:
	var points: Array = []
	var n := int(a.distance_to(b) / 5.0)
	for i in n + 1:
		var p := a.lerp(b, float(i) / n)
		points.append([p.x, p.y, p.z])
	return points


## The rows of roads.bin (x, y, z, edge, rank) of `points` as edge `id`.
func _edge(rows: PackedFloat32Array, points: Array, id: int) -> void:
	for p: Array in points:
		rows.append_array([p[0], p[1], p[2], float(id), 4.0])


func _expect(name: String, got: Variant, want: Variant) -> void:
	if got != want:
		_fail("%s: got %s, want %s" % [name, str(got), str(want)])


func _fail(message: String) -> void:
	push_error(message)
	_failed = true
