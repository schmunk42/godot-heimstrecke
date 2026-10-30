# file generated with AI assistance: Claude Code - 2026-10-23 16:40:00 UTC
extends Control
## HUD minimap at the bottom right: the roads of road_index.gd within
## RADIUS_M of the car, turned so the view direction points up, wider and
## brighter by road rank (motorway blue, trunk and primary yellow,
## secondary white, the rest grey), the car as a triangle in the middle.
## Redrawn at REDRAW_HZ, not every frame.

const SIZE_PX := 220.0
const RADIUS_M := 600.0
const REDRAW_HZ := 20.0
const MOTORWAY := Color(0.35, 0.6, 1.0)
const MAJOR := Color(1.0, 0.85, 0.25)
const SECONDARY := Color(0.95, 0.95, 0.95)
const MINOR := Color(0.7, 0.7, 0.7, 0.8)

var roads: RefCounted
var _centre := Vector3.ZERO
var _heading := 0.0
var _wait := 0.0


func _init() -> void:
	custom_minimum_size = Vector2(SIZE_PX, SIZE_PX)
	size = custom_minimum_size
	mouse_filter = Control.MOUSE_FILTER_IGNORE


## Centre and turn the map on `car`; the view direction is the camera's.
func follow(car: Node3D, camera: Node3D, delta: float) -> void:
	_wait -= delta
	if _wait > 0.0:
		return
	_wait = 1.0 / REDRAW_HZ
	_centre = car.global_position
	var forward := -camera.global_basis.z
	if Vector2(forward.x, forward.z).length() > 0.01:
		_heading = atan2(forward.x, -forward.z)
	queue_redraw()


func _draw() -> void:
	var half := SIZE_PX / 2.0
	var mid := Vector2(half, half)
	draw_circle(mid, half, Color(0.05, 0.06, 0.08, 0.6))
	if roads != null:
		var scale := half / RADIUS_M
		var c := cos(-_heading)
		var s := sin(-_heading)
		for i: int in roads.segments_near(_centre, RADIUS_M):
			var ends: Array[Vector3] = roads.segment(i)
			var a := _to_map(ends[0], mid, scale, c, s)
			var b := _to_map(ends[1], mid, scale, c, s)
			if a.distance_to(mid) > half and b.distance_to(mid) > half:
				continue
			var rank: int = roads.rank(i)
			if rank >= 8:
				draw_line(a, b, MOTORWAY, 4.0)
			elif rank >= 6:
				draw_line(a, b, MAJOR, 3.5)
			elif rank >= 5:
				draw_line(a, b, SECONDARY, 2.5)
			else:
				draw_line(a, b, MINOR, 1.5)
	draw_arc(mid, half - 1.0, 0.0, TAU, 64, Color(1, 1, 1, 0.6), 2.0, true)
	draw_colored_polygon(PackedVector2Array([mid + Vector2(0, -9),
		mid + Vector2(-6, 7), mid + Vector2(6, 7)]), Color(1.0, 0.3, 0.2))


## World x/z to map pixels: relative to the centre, turned by the
## heading (screen up = view direction), -z is up on screen.
func _to_map(p: Vector3, mid: Vector2, scale: float, c: float,
		s: float) -> Vector2:
	var dx := p.x - _centre.x
	var dz := p.z - _centre.z
	return mid + Vector2(dx * c - dz * s, dx * s + dz * c) * scale
