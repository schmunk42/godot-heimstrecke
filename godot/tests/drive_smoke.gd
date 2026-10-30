# file generated with AI assistance: Claude Code - 2026-10-20 19:35:00 UTC
extends SceneTree
## Headless smoke test for the drive scene: settle 2 s, full throttle 6 s,
## steer right 1.5 s without throttle, brake. The car must stay upright.
## Then every start point of the menu: the car must settle upright on it.
## Then the car is moved 25 m off the road, rolled onto its side, and F
## must put it back upright; with road lines (roads.bin) on a road.
## Then the world's own runs from ../worlds/<world id>/smoke.json, in
## free drive (their paths leave the route, whose boards close the roads
## off it), each only when the file has it: "tunnel" puts the car on start `start` and
## steers it along `path` (x/z) at `kmh`: it must reach the last point
## within `timeout_s`, stay upright and not climb more than `rise_m`;
## "bridge" places it on the first point of `path` (x/y/z with the road
## surface height) and drives along it: it must reach the end, stay
## upright and never drop more than `sink_m` below the road surface.
## Then every car of the start menu (car.gd CARS) is put on the route
## start: it must settle upright, reach 100 km/h within CAR_TIMEOUT_S at
## full throttle and stay upright; the 0-100 times are printed.
## It measures 0-50 km/h (during the throttle phase) and 30-0 km/h in
## physics ticks (machine independent) plus the wall-clock load time, and
## compares them with res://tests/reference_<world id>.json. Exits
## non-zero on failure.
##
##   godot --headless --path godot --script res://tests/drive_smoke.gd \
##       [-- --world <world dir or .world file>] [--route <id>]
##   SMOKE_WRITE_REFERENCE=1 godot --headless --path godot \
##       --script res://tests/drive_smoke.gd   # (re)write the reference
##
## Tolerances: accel_0_50_s and brake_30_0_s within +-10 % of the reference,
## load_ms <= max(15000, 1.25 * reference load_ms). Without a reference
## for the world the comparison is skipped. The world (--world, default
## the built Stuttgart world in data/out/worlds/stuttgart) needs start
## points from its recipe (worlds/<id>/world.json); without a route only
## the start and upright checks run. A world that does not open fails at
## once with the reason.

## the timing reference of a world id
const REFERENCE := "res://tests/reference_%s.json"
## the world's own runs, relative to res://
const SMOKE_FILE := "../worlds/%s/smoke.json"
## preloaded: without the editor's class cache class_name is unknown
const WORLD_LOADER := preload("res://scripts/world_loader.gd")
const WATCHDOG_S := 180.0
const THROTTLE_S := 6
const BRAKE_TIMEOUT_S := 6.0
const TOLERANCE := 0.10
const LOAD_BUDGET_MS := 15000
const LOAD_FACTOR := 1.25
const TUNNEL_REACH_M := 10.0
const CAR_TIMEOUT_S := 12.0
# wanted wheel angle (rad) per unit of sideways aim error, and its cap;
# full A/D lock (about 25 degrees at 40 km/h) rolls the car over on the
# 3.4 m wide ramp
const TUNNEL_STEER_GAIN := 1.5
const TUNNEL_STEER_MAX := 0.12
const TUNNEL_STEER_DEAD := 0.01

var _failures: Array[String] = []
var _world_id := ""
var _reference := ""
var _smoke := {}
var _done := false
var _tps := float(Engine.physics_ticks_per_second)


func _initialize() -> void:
	create_timer(WATCHDOG_S).timeout.connect(_on_watchdog)
	_start()


## The world's _ready() (tile loading, collision) runs on the first main
## loop iteration, not inside add_child(), so wait for its ready signal.
func _start() -> void:
	var path := WORLD_LOADER.path_from_args(WORLD_LOADER.default_path())
	print("smoke world: ", path)
	var loader := WORLD_LOADER.new()
	if loader.open(path) != OK:
		_done = true
		print("SMOKE FAILED: ", loader.error)
		quit(1)
		return
	_world_id = str(loader.manifest.get("id", ""))
	loader.close()
	_reference = REFERENCE % _world_id
	_smoke = _load_smoke(_world_id)
	var started := Time.get_ticks_msec()
	var world: Node = load("res://scenes/drive.tscn").instantiate()
	world.set("start_menu", false)
	world.set("world_path", path)
	root.add_child(world)
	if not world.is_node_ready():
		await world.ready
	var load_ms := Time.get_ticks_msec() - started
	_run(world, load_ms)


func _run(world: Node, load_ms: int) -> void:
	var car: RigidBody3D = world.get("_car")
	var route: Array = world.get("_route") if world.get("_route") else []
	if car == null:
		_check(false, "drive scene has a car")
		_finish({"hostname": _hostname(), "accel_0_50_s": -1.0,
			"brake_30_0_s": -1.0, "load_ms": load_ms})
		return
	if route.is_empty():
		print("SKIPPED accelerate, steer, brake, tunnel, bridge and car runs "
			+ "(world has no route)")
		if not world.get("_starts").is_empty():
			world.call("start_at", 0)
		await _ticks(roundi(2.0 * _tps))
		await _check_starts(world, car)
		await _check_upright(world, car)
		_finish({"hostname": _hostname(), "accel_0_50_s": -1.0,
			"brake_30_0_s": -1.0, "load_ms": load_ms, "timed": false})
		return

	await _ticks(roundi(2.0 * _tps))
	var start := car.global_position
	_sample("settled", car)
	_check(car.linear_velocity.length() < 1.0, "car at rest after settling")

	var accel := await _measure_accel(car)
	_check(accel >= 0.0, "reaches 50 km/h within %d s" % THROTTLE_S)
	_check(car.global_basis.y.y > 0.8, "upright after straight run")

	_key(KEY_D, true)
	await _ticks(roundi(1.5 * _tps))
	_key(KEY_D, false)
	_sample("after steering", car)
	_check(car.global_basis.y.y > 0.8, "upright after steering")
	_check(car.global_position.y > start.y - 30.0, "did not fall through")

	var brake := await _measure_brake(car)
	_check(brake >= 0.0, "brakes from 30 to 0 km/h within %d s"
		% BRAKE_TIMEOUT_S)
	_check(car.global_position.y > start.y - 30.0, "did not fall through")

	await _check_starts(world, car)
	await _check_upright(world, car)
	# the tunnel and bridge paths leave the route, whose boards close the
	# roads off it: both run in free drive
	var chosen: int = world.get("_route_index")
	world.call("_set_route", -1)
	for run: String in ["tunnel", "bridge"]:
		if not _smoke.has(run):
			print("SKIPPED %s run (no smoke.json entry)" % run)
		elif run == "tunnel":
			await _check_tunnel(world, car, _smoke.tunnel)
		else:
			await _check_bridge(world, car, _smoke.bridge)
	world.call("_set_route", chosen)
	await _check_cars(world, car)
	_finish({"hostname": _hostname(), "accel_0_50_s": accel,
		"brake_30_0_s": brake, "load_ms": load_ms})


## Places the car on every start point, settles 1.5 s and checks that it
## rests upright within 2 m of the start.
func _check_starts(world: Node, car: RigidBody3D) -> void:
	var starts: Array = world.get("_starts")
	_check(not starts.is_empty(), "world.json has start points (starts in "
		+ "the world recipe?)")
	for i in starts.size():
		world.call("start_at", i)
		await _ticks(roundi(1.5 * _tps))
		var p: Array = starts[i].pos
		var off := car.global_position.distance_to(Vector3(p[0], p[1], p[2]))
		_sample("start %d" % (i + 1), car)
		_check(car.global_basis.y.y > 0.95 and off < 2.0
			and car.linear_velocity.length() < 1.0,
			"rests on start %d (%s)" % [i + 1, starts[i].name])


## Moves the car 25 m sideways off the road, rolls it with an impulse,
## presses F and checks that it stands upright and at rest 2 s later,
## and, if the world has road lines, within 1 m of the nearest road.
func _check_upright(world: Node, car: RigidBody3D) -> void:
	car.global_position += car.global_basis.x * 25.0 + Vector3.UP * 2.0
	await _ticks(roundi(1.0 * _tps))
	car.apply_impulse(Vector3.UP * 9000.0, car.global_basis.x)
	car.apply_torque_impulse(car.global_basis.z * 6000.0)
	await _ticks(roundi(2.0 * _tps))
	_sample("rolled", car)
	_key(KEY_F, true)
	await _ticks(3)
	_key(KEY_F, false)
	await _ticks(roundi(2.0 * _tps))
	_sample("after F", car)
	_check(car.global_basis.y.y > 0.95 and car.linear_velocity.length() < 1.0,
		"F puts the car back upright")
	var roads: RefCounted = world.get("_roads")
	if roads != null:
		var near: Dictionary = roads.nearest(car.global_position,
			-car.global_basis.z)
		var off := INF if near.is_empty() else Vector2(
			car.global_position.x - near.point.x,
			car.global_position.z - near.point.z).length()
		print("after F off_road_m=%.2f" % off)
		_check(off < 1.0, "F puts the car on the nearest road")


## Puts the car on start cfg.start and drives it along cfg.path (x/z).
## Checks that it reaches the last point, the highest point against the
## start height and that it stays upright and above ground.
func _check_tunnel(world: Node, car: RigidBody3D, cfg: Dictionary) -> void:
	var starts: Array = world.get("_starts")
	var index := int(cfg.start)
	if starts.size() <= index:
		_check(false, "start %d exists for the tunnel run" % (index + 1))
		return
	world.call("start_at", index)
	await _ticks(roundi(1.5 * _tps))
	var path: Array[Vector2] = []
	for p: Array in cfg.path:
		path.append(Vector2(p[0], p[1]))
	var run := await _follow(car, path, [], float(cfg.kmh),
		float(cfg.timeout_s), "tunnel")
	_check(run.reached, "tunnel run from start %d reaches the exit"
		% (index + 1))
	_check(run.top - run.start <= float(cfg.rise_m),
		"tunnel run rises at most %.0f m" % float(cfg.rise_m))
	_check(run.upright, "upright on the tunnel run")
	_check(run.low > run.start - 30.0,
		"did not fall through on the tunnel run")


## Places the car on the first point of cfg.path (x/y/z with the road
## surface height), facing the second, and drives it along the path over
## the bridge. Checks that it reaches the last point, stays upright and
## never sinks more than cfg.sink_m below the road surface at the nearest
## path point.
func _check_bridge(world: Node, car: RigidBody3D, cfg: Dictionary) -> void:
	var points: Array[Vector3] = []
	for p: Array in cfg.path:
		points.append(Vector3(p[0], p[1], p[2]))
	world.call("_place_car", points[0], points[1])
	await _ticks(roundi(1.5 * _tps))
	var path: Array[Vector2] = []
	var surface: Array[float] = []
	for p in points:
		path.append(Vector2(p.x, p.z))
		surface.append(p.y)
	var run := await _follow(car, path, surface, float(cfg.kmh),
		float(cfg.timeout_s), "bridge")
	print("bridge run: lowest %+.2f m against the road surface" % run.sink)
	_check(run.reached, "bridge run reaches the end of the bridge path")
	_check(run.upright, "upright on the bridge run")
	_check(run.sink > -float(cfg.sink_m),
		"bridge run stays on the deck (at most %.0f m below the surface)"
		% float(cfg.sink_m))


## The world's smoke.json ({} when it has none); a broken file fails.
func _load_smoke(id: String) -> Dictionary:
	var file := ProjectSettings.globalize_path("res://") \
		.path_join(SMOKE_FILE % id).simplify_path()
	if not FileAccess.file_exists(file):
		print("no smoke.json for %s: %s" % [id, file])
		return {}
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(file))
	var valid: bool = data is Dictionary and data.get("schema") == 1.0 \
		and (not data.has("tunnel") or data.tunnel.get("path") is Array) \
		and (not data.has("bridge") or (data.bridge.get("path") is Array
			and data.bridge.path.size() >= 2))
	_check(valid, "smoke.json is valid: %s" % file)
	return data if valid else {}


## Switches to every car in turn, settles it 2 s on the route start and
## holds W until 100 km/h or CAR_TIMEOUT_S; checks that it rests upright
## after settling, reaches 100 km/h and stays upright on the way.
func _check_cars(world: Node, car: RigidBody3D) -> void:
	var cars: Array = preload("res://scripts/cars.gd").CARS
	for i in cars.size():
		car.call("set_car", i)
		world.call("_place_car_at", 0)
		await _ticks(roundi(2.0 * _tps))
		var name: String = cars[i].name
		_sample("car %d settled" % (i + 1), car)
		_check(car.global_basis.y.y > 0.95
			and car.linear_velocity.length() < 1.0,
			"car %d (%s) rests upright" % [i + 1, name])
		_key(KEY_W, true)
		var limit := roundi(CAR_TIMEOUT_S * _tps)
		var ticks := 0
		var upright := true
		while ticks < limit and car.speed_kmh < 100.0:
			await physics_frame
			upright = upright and car.global_basis.y.y > 0.8
			ticks += 1
		_key(KEY_W, false)
		_sample("car %d at 100 km/h" % (i + 1), car)
		print("car %d (%s): 0-100 km/h in %.2f s" % [i + 1, name,
			ticks / _tps])
		_check(car.speed_kmh >= 100.0, "car %d (%s) reaches 100 km/h "
			% [i + 1, name] + "within %.0f s" % CAR_TIMEOUT_S)
		_check(upright, "car %d (%s) upright at full throttle"
			% [i + 1, name])
	car.call("set_car", 0)


## Drives the car along path (Godot x/z): W below kmh, A/D tapped until
## the car's wheel angle matches the aim at the next path point. Returns
## reached (all points), start/top/low heights, upright and, if surface
## holds the road height per path point, sink: the lowest car height
## against the surface at the nearest path point.
func _follow(car: RigidBody3D, path: Array[Vector2], surface: Array[float],
		kmh: float, timeout_s: float, label: String) -> Dictionary:
	var start := car.global_position
	var top := start.y
	var low := start.y
	var sink := INF
	var upright := true
	var next := 0
	var keys := {KEY_W: false, KEY_A: false, KEY_D: false}
	var limit := roundi(timeout_s * _tps)
	var i := 0
	while i < limit and next < path.size():
		var pos := Vector2(car.global_position.x, car.global_position.z)
		if pos.distance_to(path[next]) < TUNNEL_REACH_M:
			next += 1
			continue
		var right := Vector2(car.global_basis.x.x, car.global_basis.x.z)
		var side := (path[next] - pos).normalized().dot(right.normalized())
		# car.steer is positive to the left (A)
		var want := clampf(-TUNNEL_STEER_GAIN * side, -TUNNEL_STEER_MAX,
			TUNNEL_STEER_MAX)
		var steer: float = car.get("steer")
		_hold(keys, KEY_W, car.speed_kmh < kmh)
		_hold(keys, KEY_A, steer < want - TUNNEL_STEER_DEAD)
		_hold(keys, KEY_D, steer > want + TUNNEL_STEER_DEAD)
		await physics_frame
		top = maxf(top, car.global_position.y)
		low = minf(low, car.global_position.y)
		if not surface.is_empty():
			sink = minf(sink, car.global_position.y
				- surface[_nearest(path, car.global_position)])
		upright = upright and car.global_basis.y.y > 0.8
		i += 1
		if i % int(_tps) == 0:
			_sample("%s %ds" % [label, i / int(_tps)], car)
	for code in keys:
		_hold(keys, code, false)
	print("%s run: %d/%d path points in %.1f s, rise max %+.2f m, "
		% [label, next, path.size(), i / _tps, top - start.y]
		+ "drop max %+.2f m" % (low - start.y))
	return {"reached": next == path.size(), "start": start.y, "top": top,
		"low": low, "upright": upright, "sink": sink}


## Index of the path point nearest to position (Godot x/z).
func _nearest(path: Array[Vector2], position: Vector3) -> int:
	var pos := Vector2(position.x, position.z)
	var best := 0
	for k in path.size():
		if pos.distance_squared_to(path[k]) \
				< pos.distance_squared_to(path[best]):
			best = k
	return best


## Presses or releases a key only when its state in keys changes.
func _hold(keys: Dictionary, code: Key, pressed: bool) -> void:
	if keys[code] != pressed:
		keys[code] = pressed
		_key(code, pressed)


## Holds W for THROTTLE_S from rest; returns the seconds until
## speed_kmh >= 50 or -1.0 if 50 km/h is not reached. Releases W at the end.
func _measure_accel(car: RigidBody3D) -> float:
	_key(KEY_W, true)
	var limit := roundi(THROTTLE_S * _tps)
	var ticks := 0
	var reached := -1
	while ticks < limit:
		await physics_frame
		# the car reads the input in this tick's _physics_process
		if not Input.is_key_pressed(KEY_W):
			continue
		if reached < 0 and car.speed_kmh >= 50.0:
			reached = ticks
		ticks += 1
		if ticks % int(_tps) == 0:
			_sample("throttle %ds" % (ticks / int(_tps)), car)
	_key(KEY_W, false)
	return snappedf(reached / _tps, 0.001) if reached >= 0 else -1.0


## Brakes with S; returns the seconds from the first tick <= 30 km/h
## (the first tick if already slower) to the first tick < 1 km/h or -1.0
## on timeout.
func _measure_brake(car: RigidBody3D) -> float:
	var limit := roundi(BRAKE_TIMEOUT_S * _tps)
	var ticks := 0
	_key(KEY_S, true)
	var crossed := -1
	var result := -1.0
	while ticks < limit:
		await physics_frame
		if not Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_W):
			continue
		if crossed < 0 and car.speed_kmh <= 30.0:
			crossed = ticks
		if crossed >= 0 and car.speed_kmh < 1.0:
			result = snappedf((ticks - crossed) / _tps, 0.001)
			break
		ticks += 1
	_key(KEY_S, false)
	_sample("after braking", car)
	return result


func _finish(metrics: Dictionary) -> void:
	if OS.get_environment("SMOKE_WRITE_REFERENCE") == "1":
		_write_reference(metrics)
	elif FileAccess.file_exists(_reference):
		_compare(metrics)
	else:
		print("NO REFERENCE for %s (set SMOKE_WRITE_REFERENCE=1 to write "
			% _world_id + "one), comparison SKIPPED")

	print("SMOKE METRICS hostname=%s accel_0_50_s=%.3f brake_30_0_s=%.3f "
		% [metrics.hostname, metrics.accel_0_50_s, metrics.brake_30_0_s]
		+ "load_ms=%d" % metrics.load_ms)
	_done = true
	if _failures.is_empty():
		print("SMOKE OK")
		quit(0)
	else:
		print("SMOKE FAILED: ", ", ".join(_failures))
		quit(1)


func _write_reference(metrics: Dictionary) -> void:
	if metrics.accel_0_50_s < 0.0 or metrics.brake_30_0_s < 0.0:
		_check(false, "reference written (measurement failed)")
		return
	var data := {
		"hostname": metrics.hostname,
		"measured_at": Time.get_datetime_string_from_system(true) + "Z",
		"physics_ticks_per_second": Engine.physics_ticks_per_second,
		"accel_0_50_s": metrics.accel_0_50_s,
		"brake_30_0_s": metrics.brake_30_0_s,
		"load_ms": metrics.load_ms,
	}
	var file := FileAccess.open(_reference, FileAccess.WRITE)
	if file == null:
		_check(false, "reference written (%s)"
			% error_string(FileAccess.get_open_error()))
		return
	file.store_string(JSON.stringify(data, "  ", false) + "\n")
	file.close()
	print("REFERENCE WRITTEN ", _reference)


func _compare(metrics: Dictionary) -> void:
	var ref: Variant = JSON.parse_string(
		FileAccess.get_file_as_string(_reference))
	if not ref is Dictionary:
		_check(false, "reference file is valid JSON")
		return
	print("reference from %s, measured %s" % [
		ref.get("hostname", "?"), ref.get("measured_at", "?")])
	if int(ref.get("physics_ticks_per_second", 0)) \
			!= Engine.physics_ticks_per_second:
		print("  note: reference used %s physics ticks per second" %
			ref.get("physics_ticks_per_second"))
	for key in ["accel_0_50_s", "brake_30_0_s"]:
		if not metrics.get("timed", true):
			print("  %-13s SKIPPED (world has no route)" % key)
			continue
		var measured: float = metrics[key]
		var reference := float(ref.get(key, 0.0))
		_report(key, measured, reference)
		_check(measured >= 0.0 and reference > 0.0
			and absf(measured - reference) <= TOLERANCE * reference,
			"%s within %d %% of reference" % [key, roundi(TOLERANCE * 100)])
	var ref_load := float(ref.get("load_ms", 0.0))
	var budget := maxf(LOAD_BUDGET_MS, LOAD_FACTOR * ref_load)
	_report("load_ms", metrics.load_ms, ref_load)
	_check(metrics.load_ms <= budget, "load_ms <= %d" % roundi(budget))


func _report(key: String, measured: float, reference: float) -> void:
	var delta := (measured - reference) / reference * 100.0 \
		if reference > 0.0 else NAN
	print("  %-13s measured=%9.3f reference=%9.3f delta=%+6.1f %%" % [
		key, measured, reference, delta])


func _ticks(count: int) -> void:
	for i in count:
		await physics_frame


func _hostname() -> String:
	var name := OS.get_environment("HOSTNAME").strip_edges()
	if name.is_empty():
		var output := []
		if OS.execute("hostname", [], output) == 0 and not output.is_empty():
			name = str(output[0]).strip_edges()
	return name if not name.is_empty() else "unknown"


func _on_watchdog() -> void:
	if _done:
		return
	print("SMOKE FAILED: watchdog after %d s" % WATCHDOG_S)
	quit(1)


func _sample(label: String, car: RigidBody3D) -> void:
	print("%-16s pos=%s v=%5.1f km/h up=%.2f" % [
		label, car.global_position.snapped(Vector3.ONE * 0.1),
		car.speed_kmh, car.global_basis.y.y])


func _check(ok: bool, what: String) -> void:
	print(("  ok   " if ok else "  FAIL ") + what)
	if not ok:
		_failures.append(what)


func _key(code: Key, pressed: bool) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.physical_keycode = code
	event.pressed = pressed
	Input.parse_input_event(event)
	# apply now, not at the next frame, so the timing does not depend on
	# how many physics ticks the machine runs per frame
	Input.flush_buffered_events()
# - revised 2026-10-22 (world.json manifest)
# - revised 2026-10-22 (--world argument, recipe wording)
# - revised 2026-10-22 (per-world reference and smoke.json, no-route worlds)
# - revised 2026-10-23 (F: off the road first, then back on the nearest road)
# - revised 2026-10-26 (tunnel and bridge runs in free drive)
