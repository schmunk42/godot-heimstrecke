# file generated with AI assistance: Claude Code - 2026-10-26 18:55:00 UTC
extends SceneTree
## Checks pace_notes.gd on drawn routes: a straight has no note, a 90°
## left of 30 m radius is a "2 left", a 180° turn of 12 m radius a
## hairpin, a right of 70 m linked straight into a left of 50 m is
## "4 right into" and "3 left", a 20° left of 300 m radius a "6 left"
## (the T 50 east of the Tavignano bridge), a route that runs to a point and back
## has no note. Exit code 1 on a failure.
##
##   godot --headless --path godot --script res://tests/pace_notes_test.gd

const PACE_NOTES := preload("res://scripts/pace_notes.gd")

var _failed := false


func _initialize() -> void:
	var straight := _line(Vector2.ZERO, Vector2(0, -1), 300.0)
	_expect("straight", PACE_NOTES.analyse(straight), [])

	var left := _line(Vector2.ZERO, Vector2(0, -1), 100.0)
	left += _arc(_end(left), Vector2(0, -1), 30.0, -PI / 2.0)
	left += _line(_end(left), Vector2(-1, 0), 100.0)
	_expect("left 90 r30", PACE_NOTES.analyse(left), ["2 left"])

	var pin := _line(Vector2.ZERO, Vector2(0, -1), 100.0)
	pin += _arc(_end(pin), Vector2(0, -1), 12.0, PI)
	pin += _line(_end(pin), Vector2(0, 1), 100.0)
	_expect("hairpin", PACE_NOTES.analyse(pin), ["hairpin right"])

	var s_bend := _line(Vector2.ZERO, Vector2(0, -1), 100.0)
	s_bend += _arc(_end(s_bend), Vector2(0, -1), 70.0, PI / 3.0)
	var d := Vector2(0, -1).rotated(PI / 3.0)
	s_bend += _arc(_end(s_bend), d, 50.0, -PI / 3.0)
	s_bend += _line(_end(s_bend), Vector2(0, -1), 100.0)
	_expect("s-bend", PACE_NOTES.analyse(s_bend),
		["4 right into", "3 left"])

	var slight := _line(Vector2.ZERO, Vector2(0, -1), 100.0)
	slight += _arc(_end(slight), Vector2(0, -1), 300.0, -deg_to_rad(20.0))
	slight += _line(_end(slight), Vector2(0, -1).rotated(-deg_to_rad(20.0)),
		100.0)
	_expect("slight left 20 r300", PACE_NOTES.analyse(slight), ["6 left"])

	var back := _line(Vector2.ZERO, Vector2(0, -1), 200.0)
	back += _line(_end(back), Vector2(0, 1), 200.0)
	_expect("there and back", PACE_NOTES.analyse(back), [])

	print("PACE NOTES " + ("FAILED" if _failed else "OK"))
	quit(1 if _failed else 0)


func _expect(name: String, notes: Array, calls: Array) -> void:
	var got := notes.map(func(n: Dictionary) -> String: return n.call)
	var ok := got == calls
	_failed = _failed or not ok
	print("  %s  %s: %s" % ["ok  " if ok else "FAIL", name, got])


## Points every metre from `from` along `dir` (x/z; -z is ahead) for
## `length` metres, as [x, 0, z].
func _line(from: Vector2, dir: Vector2, length: float) -> Array:
	var pts := []
	for i in range(1 if not from.is_zero_approx() else 0, int(length) + 1):
		var p := from + dir * i
		pts.append([p.x, 0.0, p.y])
	return pts


## Points every metre on an arc of `radius` from `from`, heading `dir`,
## turning `angle` (positive: to the right).
func _arc(from: Vector2, dir: Vector2, radius: float,
		angle: float) -> Array:
	var right := Vector2(-dir.y, dir.x)
	var centre := from + right * radius * signf(angle)
	var start := from - centre
	var pts := []
	var steps := int(absf(angle) * radius)
	for i in range(1, steps + 1):
		var p := centre + start.rotated(angle * i / steps)
		pts.append([p.x, 0.0, p.y])
	return pts


func _end(pts: Array) -> Vector2:
	return Vector2(pts[-1][0], pts[-1][2])
