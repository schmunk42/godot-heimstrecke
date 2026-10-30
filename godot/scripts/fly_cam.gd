# file generated with AI assistance: Claude Code - 2026-10-20 19:10:00 UTC
extends Camera3D
## Free-flying camera. Keyboard: WASD or arrow keys move, Q/E down/up,
## Shift faster. Mouse: captured like a first-person shooter, moving it
## looks; Escape releases it, a click captures it again (released, a right
## mouse drag still looks); wheel changes speed. Gamepad: left stick
## moves, right stick looks, triggers down/up.

const LOOK_SPEED := 0.004
const STICK_LOOK := 2.0
const DEADZONE := 0.15

var speed := 60.0


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _exit_tree() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func _unhandled_input(event: InputEvent) -> void:
	var captured := Input.mouse_mode == Input.MOUSE_MODE_CAPTURED
	if event is InputEventMouseMotion and (captured
			or Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT)):
		_look(-event.relative.x * LOOK_SPEED, -event.relative.y * LOOK_SPEED)
	elif event is InputEventKey and event.pressed \
			and event.keycode == KEY_ESCAPE and captured:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_LEFT and not captured:
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		elif event.button_index == MOUSE_BUTTON_WHEEL_UP:
			speed *= 1.25
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			speed /= 1.25


func _process(delta: float) -> void:
	var move := Vector3.ZERO
	if Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP):
		move -= basis.z
	if Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_DOWN):
		move += basis.z
	if Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT):
		move -= basis.x
	if Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT):
		move += basis.x
	if Input.is_key_pressed(KEY_E):
		move += Vector3.UP
	if Input.is_key_pressed(KEY_Q):
		move -= Vector3.UP

	var stick := Vector2(_axis(JOY_AXIS_LEFT_X), _axis(JOY_AXIS_LEFT_Y))
	move += basis.x * stick.x + basis.z * stick.y
	move += Vector3.UP * (_axis(JOY_AXIS_TRIGGER_RIGHT)
		- _axis(JOY_AXIS_TRIGGER_LEFT))
	_look(-_axis(JOY_AXIS_RIGHT_X) * STICK_LOOK * delta,
		-_axis(JOY_AXIS_RIGHT_Y) * STICK_LOOK * delta)

	var boost := 4.0 if Input.is_key_pressed(KEY_SHIFT) else 1.0
	position += move.limit_length(1.0) * speed * boost * delta


func _look(yaw: float, pitch: float) -> void:
	rotation.y += yaw
	rotation.x = clampf(rotation.x + pitch, -1.5, 1.5)


func _axis(axis: JoyAxis) -> float:
	var value := Input.get_joy_axis(0, axis)
	return value if absf(value) > DEADZONE else 0.0
# - revised 2026-10-26 (mouse look like a first-person shooter, arrow keys)
