# file generated with AI assistance: Claude Code - 2026-10-20 19:20:00 UTC
extends RigidBody3D
## Simcade raycast car: four suspension rays, tire grip clamped by a
## friction circle, the drive split between the axles by the car's
## `front_drive` share. Proportions, drivetrain and engine come from an
## entry of cars.gd (eight cars after real ones, under made-up names),
## the body from car_model.gd: an engine with a torque curve and
## optional turbo lag, gears shifted automatically, sounds in
## car_audio.gd. Front is -Z.
##
## Keyboard: W/S or arrows throttle/brake, A/D steer, Space handbrake,
## R back to the start or the route, F onto the nearest road (both in
## world.gd; F upright on the spot when nothing handles it). Gamepad:
## RT/LT, left stick, A, Y, X. The car is chosen in the start menu
## (set_car).

signal reset_requested
signal road_requested

const CARS := preload("res://scripts/cars.gd").CARS
const MODEL := preload("res://scripts/car_model.gd")
## Collision layers: terrain, roads and tunnels on GROUND, buildings on
## BUILDINGS (world.gd). The car hits both; the rays that look for a
## place to put the car down only see GROUND, so a car lying against a
## building is not put onto its roof.
const LAYER_GROUND := 1
const LAYER_BUILDINGS := 2
## distances around the car that upright() tries, in metres
const UPRIGHT_RADII := [0.0, 2.0, 4.0, 8.0]

const LATERAL_GAIN := 0.55
## the handbrake locks the rear wheels: they slide with this share of the
## tyre grip against their contact patch velocity, take no drive and
## hold the car at a standstill
const HANDBRAKE_GRIP := 0.7
const ROLLING_RESISTANCE := 0.013
const HOLD_SPEED := 1.5
const STEER_MAX := deg_to_rad(32.0)
const STEER_MIN := deg_to_rad(6.0)
const STEER_RATE := 3.5

var steer := 0.0
var speed_kmh := 0.0
## read by car_audio.gd and the HUD: pedal 0-1, the largest tyre slip in
## m/s, engine speed, gear (1 up, -1 reverse), boost 0-1
var throttle_input := 0.0
var slip := 0.0
var rpm := 900.0
var gear := 1
var boost := 0.0
## index into CARS and its entry
var car_index := 0
var spec: Dictionary = CARS[0]
var _shift_left := 0.0
var _compression := [0.0, 0.0, 0.0, 0.0]
var _spin := [0.0, 0.0, 0.0, 0.0]
var _wheel_nodes: Array[MeshInstance3D] = []
var _model: Node3D
# R and F are polled like the pedals: a focused menu button must not
# swallow them, and only the press (not the hold) counts
var _reset_held := false
var _upright_held := false
var _body_shape: CollisionShape3D


func _ready() -> void:
	center_of_mass_mode = RigidBody3D.CENTER_OF_MASS_MODE_CUSTOM
	can_sleep = false
	# air drag and rolling resistance are modelled below; the default
	# linear damp of 0.1/s alone would cost 3.7 kN at 100 km/h
	linear_damp_mode = RigidBody3D.DAMP_MODE_REPLACE
	linear_damp = 0.0
	angular_damp = 0.5
	collision_mask = LAYER_GROUND | LAYER_BUILDINGS

	_body_shape = CollisionShape3D.new()
	_body_shape.shape = BoxShape3D.new()
	add_child(_body_shape)
	_build()
	var audio := Node.new()
	audio.set_script(preload("res://scripts/car_audio.gd"))
	add_child(audio)


## Switches to car `index` of CARS: mass, collision box, body and wheels
## are rebuilt in place, the drivetrain starts in first gear.
func set_car(index: int) -> void:
	car_index = index
	spec = CARS[index]
	gear = 1
	boost = 0.0
	_shift_left = 0.0
	# the old car's spring travel would kick the new car's dampers
	_compression = [0.0, 0.0, 0.0, 0.0]
	_spin = [0.0, 0.0, 0.0, 0.0]
	if is_inside_tree():
		_build()


func _build() -> void:
	mass = spec.mass
	center_of_mass = Vector3(0.0, spec.com_y, spec.com_z)
	rpm = spec.idle
	var box: BoxShape3D = _body_shape.shape
	box.size = spec.box
	_body_shape.position.y = spec.box_y

	if _model != null:
		_model.queue_free()
	for wheel in _wheel_nodes:
		wheel.queue_free()
	# the body model sits on the ground at rest: mount, spring travel at
	# rest (mass * g / 4 / spring) and tyre radius below the car origin
	var sag: float = spec.mass * 9.81 / 4.0 / spec.spring
	var hidden := _model != null and not _model.visible
	_model = Node3D.new()
	_model.visible = not hidden
	_model.position.y = spec.wheels[0].y - (spec.rest - sag) - spec.radius
	add_child(_model)
	_wheel_nodes = MODEL.build(_model, self, spec)
	for wheel in _wheel_nodes:
		wheel.visible = not hidden


func _poll_keys() -> void:
	var reset := Input.is_key_pressed(KEY_R) \
		or Input.is_joy_button_pressed(0, JOY_BUTTON_Y)
	var up := Input.is_key_pressed(KEY_F) \
		or Input.is_joy_button_pressed(0, JOY_BUTTON_X)
	if reset and not _reset_held:
		reset_requested.emit()
	elif up and not _upright_held:
		if road_requested.get_connections().is_empty():
			upright()
		else:
			road_requested.emit()
	_reset_held = reset
	_upright_held = up


## Full-load torque at `at_rpm` with the current boost, Nm.
func torque_at(at_rpm: float) -> float:
	var curve: Array = spec.torque
	var nm: float = curve[-1][1]
	for k in range(1, curve.size()):
		if at_rpm <= curve[k][0]:
			var a: Array = curve[k - 1]
			var b: Array = curve[k]
			nm = lerpf(a[1], b[1], clampf(
				(at_rpm - a[0]) / (b[0] - a[0]), 0.0, 1.0))
			break
	var share: float = spec.boost
	return nm * (1.0 - share + share * boost)


## Engine speed with the clutch closed in gear `g` at road speed `v`.
func gear_rpm(g: int, v: float) -> float:
	var ratio: float = spec.reverse if g < 0 else spec.gears[g - 1]
	return absf(v) / spec.radius * ratio * spec.final_drive * 60.0 / TAU


## Automatic box: up at the redline, down below `downshift_rpm` or for
## more pull when the next lower gear has more wheel force.
func _shift(v: float, throttle: float, delta: float) -> void:
	_shift_left = maxf(0.0, _shift_left - delta)
	if gear < 0 or _shift_left > 0.0:
		return
	var redline: float = spec.redline
	if gear < spec.gears.size() and gear_rpm(gear, v) > redline - 150.0:
		gear += 1
		_shift_left = spec.shift_s
	elif gear > 1 and (gear_rpm(gear, v) < spec.downshift_rpm
			or (throttle > 0.9
			and gear_rpm(gear - 1, v) < redline - 900.0
			and gear_rpm(gear, v) < spec.kickdown_rpm)):
		gear -= 1
		_shift_left = spec.shift_s


func place(origin: Vector3, look_target: Vector3) -> void:
	var t := Transform3D.IDENTITY.looking_at(
		Vector3(look_target.x, origin.y, look_target.z) - origin, Vector3.UP)
	t.origin = origin
	global_transform = t
	linear_velocity = Vector3.ZERO
	angular_velocity = Vector3.ZERO


## Shows or hides the body and wheels (the driver's view hides them).
func show_body(on: bool) -> void:
	if _model != null:
		_model.visible = on
	for wheel in _wheel_nodes:
		wheel.visible = on


## Puts the car back on its wheels where it is, keeping the heading:
## 1.2 m above the ground below it (terrain, road or tunnel floor, never a
## building). If the body would overlap a building or a wall there, it
## tries the heading turned by 90 and 180 degrees and then spots at the
## UPRIGHT_RADII around, so it is not pushed out and rolled over again.
func upright() -> void:
	var heading := -global_basis.z
	heading.y = 0.0
	if heading.length() < 0.1:
		heading = global_basis.y
		heading.y = 0.0
	heading = heading.normalized()
	var space := get_world_3d().direct_space_state
	var first := _upright_transform(
		_ground_below(space, global_position), heading)
	for radius: float in UPRIGHT_RADII:
		for k in (1 if radius == 0.0 else 8):
			var offset: Vector3 = Vector3.FORWARD.rotated(Vector3.UP,
				TAU * k / 8.0) * radius
			var origin := _ground_below(space, global_position + offset)
			for turn: float in [0.0, PI / 2.0, PI, -PI / 2.0]:
				var t := _upright_transform(origin,
					heading.rotated(Vector3.UP, turn))
				if _body_free(space, t):
					_apply_upright(t)
					return
	# nothing free nearby: put it down where it is anyway
	_apply_upright(first)


func _ground_below(space: PhysicsDirectSpaceState3D, at: Vector3) -> Vector3:
	var query := PhysicsRayQueryParameters3D.create(at + Vector3.UP * 3.0,
		at - Vector3.UP * 200.0, LAYER_GROUND, [get_rid()])
	var hit := space.intersect_ray(query)
	var origin: Vector3 = hit.position if not hit.is_empty() else at
	return origin + Vector3.UP * 1.2


func _upright_transform(origin: Vector3, heading: Vector3) -> Transform3D:
	var t := Transform3D.IDENTITY.looking_at(heading, Vector3.UP)
	t.origin = origin
	return t


## True if the body box at transform t touches nothing (ground included,
## so a spot on a steep slope also counts as blocked).
func _body_free(space: PhysicsDirectSpaceState3D, t: Transform3D) -> bool:
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = _body_shape.shape
	query.transform = t * _body_shape.transform
	query.collision_mask = LAYER_GROUND | LAYER_BUILDINGS
	query.exclude = [get_rid()]
	return space.intersect_shape(query, 1).is_empty()


func _apply_upright(t: Transform3D) -> void:
	place(t.origin, t.origin - t.basis.z)


func _physics_process(delta: float) -> void:
	if freeze:
		return
	_poll_keys()
	var throttle := maxf(_axis(JOY_AXIS_TRIGGER_RIGHT),
		1.0 if Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP)
		else 0.0)
	var brake := maxf(_axis(JOY_AXIS_TRIGGER_LEFT),
		1.0 if Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_DOWN)
		else 0.0)
	var handbrake := Input.is_key_pressed(KEY_SPACE) \
		or Input.is_joy_button_pressed(0, JOY_BUTTON_A)
	throttle_input = throttle
	var steer_in := _axis(JOY_AXIS_LEFT_X)
	if Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT):
		steer_in -= 1.0
	if Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT):
		steer_in += 1.0
	steer_in = clampf(steer_in, -1.0, 1.0)

	var forward := -global_basis.z
	var v_long := linear_velocity.dot(forward)
	speed_kmh = absf(v_long) * 3.6
	var steer_limit := lerpf(STEER_MAX, STEER_MIN,
		clampf(absf(v_long) / 40.0, 0.0, 1.0))
	steer = move_toward(steer, -steer_in * steer_limit, STEER_RATE * delta)

	# S brakes while rolling forward and reverses once stopped
	if brake > 0.0 and throttle == 0.0 and gear > 0 and v_long < 0.5:
		gear = -1
	elif throttle > 0.0 and gear < 0 and v_long > -1.0:
		gear = 1
	_shift(v_long, throttle, delta)
	var pedal := brake if gear < 0 else throttle
	var engaged := gear_rpm(gear, v_long)
	var idle: float = spec.idle
	var redline: float = spec.redline
	var launch := lerpf(idle, spec.launch_rpm, pedal) \
		if gear in [1, -1] else idle
	rpm = clampf(maxf(engaged, launch), idle, redline)
	var boost_target := 0.0
	if spec.boost > 0.0:
		boost_target = pedal * clampf(
			(rpm - spec.boost_rpm) / 1500.0, 0.0, 1.0)
	boost += (boost_target - boost) * (1.0 - exp(-delta / spec.lag_s))
	var radius: float = spec.radius
	var drive := 0.0
	var braking := 0.0
	if pedal > 0.0 and _shift_left == 0.0 and engaged < redline:
		var ratio: float = spec.reverse if gear < 0 else spec.gears[gear - 1]
		drive = torque_at(rpm) * pedal * ratio * spec.final_drive \
			* spec.driveline / radius * (-1.0 if gear < 0 else 1.0)
	if gear > 0:
		braking = spec.brake * brake
	else:
		braking = spec.brake * throttle

	var space := get_world_3d().direct_space_state
	var up := global_basis.y
	var wheels: Array = spec.wheels
	var rest: float = spec.rest
	var spring: float = spec.spring
	var damper: float = spec.damper
	var front_drive: float = spec.front_drive
	slip = 0.0
	for i in wheels.size():
		var front := i < 2
		var mount: Vector3 = global_transform * wheels[i]
		var query := PhysicsRayQueryParameters3D.create(
			mount, mount - up * (rest + radius))
		query.exclude = [get_rid()]
		var hit := space.intersect_ray(query)
		var wheel_basis := global_basis
		if front:
			wheel_basis = wheel_basis.rotated(up, steer)
		if hit.is_empty():
			_compression[i] = 0.0
			_update_wheel(i, rest, front, v_long, delta)
			continue

		var dist: float = mount.distance_to(hit.position) - radius
		var x := rest - dist
		var x_vel: float = (x - _compression[i]) / delta
		_compression[i] = x
		var wheel_load := maxf(0.0, spring * x + damper * x_vel)
		var normal: Vector3 = hit.normal
		var contact: Vector3 = hit.position
		var offset := contact - global_position
		apply_force(normal * wheel_load, offset)

		var w_fwd := (-wheel_basis.z).slide(normal).normalized()
		var w_right := wheel_basis.x.slide(normal).normalized()
		var v_point := linear_velocity + angular_velocity.cross(offset)
		var v_lat := v_point.dot(w_right)
		var v_fwd := v_point.dot(w_fwd)

		var locked := handbrake and not front
		var v_slip := w_right * v_lat + w_fwd * v_fwd
		var tire: Vector3
		if locked and v_slip.length() > HOLD_SPEED:
			# a locked wheel slides: kinetic friction against the contact
			# patch velocity, which is mostly along the wheel, so the rear
			# barely holds sideways and swings out
			tire = -v_slip.normalized() * spec.mu * HANDBRAKE_GRIP \
				* wheel_load
			slip = maxf(slip, v_slip.length())
		else:
			var f_lat := -v_lat * (mass / 4.0) / delta * LATERAL_GAIN
			slip = maxf(slip, absf(v_lat))
			var f_long := -clampf(v_fwd / 0.5, -1.0, 1.0) \
				* ROLLING_RESISTANCE * wheel_load
			# open differentials: each axle's share split evenly between
			# its two wheels; a locked wheel takes none
			if not locked:
				f_long += drive \
					* (front_drive if front else 1.0 - front_drive) / 2.0
			var brake_share := 0.3 if front else 0.2
			f_long -= signf(v_fwd) * braking * brake_share
			if absf(v_fwd) < HOLD_SPEED and (locked
					or pedal == 0.0 and brake == 0.0):
				# static friction so the parked car does not creep downhill
				f_long = -v_fwd * (mass / 4.0) / delta * LATERAL_GAIN
			tire = w_right * f_lat + w_fwd * f_long
			var limit: float = spec.mu * wheel_load
			if tire.length() > limit:
				tire = tire.normalized() * limit
		apply_force(tire, offset)
		_update_wheel(i, dist, front, 0.0 if locked else v_fwd, delta)

	var v2 := linear_velocity.length_squared()
	apply_central_force(-linear_velocity * sqrt(v2) * spec.drag)
	if spec.downforce > 0.0:
		apply_central_force(-up * v_long * v_long * spec.downforce)


func _update_wheel(i: int, dist: float, front: bool, v: float,
		delta: float) -> void:
	_spin[i] = wrapf(_spin[i] + v / spec.radius * delta, -PI, PI)
	var node := _wheel_nodes[i]
	var b := Basis(Vector3.RIGHT, -_spin[i]) * Basis(Vector3.FORWARD, PI / 2)
	if front:
		b = Basis(Vector3.UP, steer) * b
	node.basis = b
	node.position = spec.wheels[i] - Vector3.UP * dist


func _axis(axis: JoyAxis) -> float:
	var value := Input.get_joy_axis(0, axis)
	return value if absf(value) > 0.12 else 0.0
# - revised 2026-10-23 (F asks world.gd for the nearest road)
# - revised 2026-10-23 (show_body for the driver view)
# - revised 2026-11-04 (handbrake locks the rear wheels for hairpins)
# - revised 2026-11-06 (car list in the doc comment)
