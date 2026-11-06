# file generated with AI assistance: Claude Code - 2026-10-20 19:20:00 UTC
extends Camera3D
## Follows the car from behind with exponential smoothing. The vertical
## field of view opens from FOV_SLOW to FOV_FAST up to FOV_KMH, so the
## road streams past faster at speed. V (gamepad RB) switches the view:
## far behind, close behind, and the driver's seat (fixed to the car,
## body hidden, no dashboard).

## far and close views: distance behind, height, look-at height, all
## times the car's `cam_scale` in cars.gd (1 if it has none)
const VIEWS := [[8.5, 2.3, 0.9], [5.0, 1.5, 0.8]]
## driver's eye relative to the car origin: left seat, above the
## collision box, a little behind the middle (front is -Z); a car's
## `eye` in cars.gd takes its place
const EYE := Vector3(-0.37, 0.55, 0.15)
const VIEW_NAMES := ["far", "close", "driver"]
const STIFFNESS := 6.0
const FOV_SLOW := 75.0
const FOV_FAST := 88.0
const FOV_KMH := 200.0

var target: Node3D
## 0 far, 1 close, 2 driver (VIEW_NAMES)
var view := 0
var _switch_held := false


## Next view; the car hides its body in the driver's view.
func next_view() -> void:
	view = (view + 1) % VIEW_NAMES.size()
	if target != null and target.has_method("show_body"):
		target.show_body(view != 2)


func _physics_process(delta: float) -> void:
	if target == null:
		return
	# polled like the car's R and F: a focused button must not swallow it
	var switch := Input.is_key_pressed(KEY_V) \
		or Input.is_joy_button_pressed(0, JOY_BUTTON_RIGHT_SHOULDER)
	if switch and not _switch_held and not target.get("freeze"):
		next_view()
	_switch_held = switch
	var t := target.global_transform
	var kmh: float = target.get("speed_kmh") if "speed_kmh" in target else 0.0
	var wide := lerpf(FOV_SLOW, FOV_FAST, clampf(kmh / FOV_KMH, 0.0, 1.0))
	var spec: Dictionary = target.spec if "spec" in target else {}
	if view == 2:
		var eye: Vector3 = spec.get("eye", EYE)
		global_transform = t * Transform3D(Basis.IDENTITY, eye)
		fov = lerpf(fov, wide - 10.0, 1.0 - exp(-delta * 2.0))
		return
	var flat := -t.basis.z
	flat.y = 0.0
	if flat.length() < 0.01:
		return
	flat = flat.normalized()
	var scale: float = spec.get("cam_scale", 1.0)
	var v: Array = VIEWS[view]
	var wanted: Vector3 = t.origin - flat * v[0] * scale \
		+ Vector3.UP * v[1] * scale
	global_position = global_position.lerp(
		wanted, 1.0 - exp(-delta * STIFFNESS))
	look_at(t.origin + Vector3.UP * v[2] * scale)
	fov = lerpf(fov, wide, 1.0 - exp(-delta * 2.0))
# - revised 2026-10-23 (V: far, close, driver view)
# - revised 2026-11-06 (eye per car)
