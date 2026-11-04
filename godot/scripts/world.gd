# file generated with AI assistance: Claude Code - 2026-10-20 19:10:00 UTC
extends Node3D
## Loads the pipeline's glb tiles and trees (trees.gd) at runtime, adds
## sky, sun and the chosen route (route_marks.gd: chevrons on the road,
## boards across the roads leaving it). Fly mode: free camera, keys 1-9
## jump to the route waypoints.
## Drive mode: collision, car, chase camera, lap timer over the waypoints,
## a compass and a start menu with the routes of WorldLoader.routes(),
## free drive and the start points of the world manifest (Esc opens it);
## the world's name and data attribution show for CREDITS_S when the
## first drive starts. Launcher arguments (after --): --world <dir or
## .world file>, --route <id> (the route chosen at the start instead of
## the world's own), --start <index> (drive mode: skip the start menu).
## G shows or hides the route's chevron band on the road (off at first).
## # shows the position readout (world, nearest road, lat/lon, heading,
## camera as a viewpoint), keeps it current while it shows and copies it
## to the clipboard, for screenshots with a note of where they were taken.

const CHECKPOINT_RADIUS := 30.0
const CAR := preload("res://scripts/car.gd")
## preloaded: without the editor's class cache (render container) the
## class_name WorldLoader is unknown
const WORLD_LOADER := preload("res://scripts/world_loader.gd")
## start points and route points lie on the road surface; the lowest
## tunnel ceiling is 3.5 m above it (pipeline/tunnels.py), the lowest
## bridge deck over a road about 4 m (pipeline/bridges.py)
const PLACE_RAY_UP := 3.0
const CO_DRIVER := preload("res://scripts/co_driver.gd")
const ROAD_INDEX := preload("res://scripts/road_index.gd")
## F puts the car on a road only this close, else upright on the spot
const ROAD_RESET_MAX_M := 2000.0
const CREDITS_S := 5.0
## the shown position readout follows the camera at this interval
const READOUT_REFRESH_S := 0.2
## _start of a start chosen on the map (-1: none yet)
const FREE_START := -2
## _start of a route started on its first point (not on a lap start)
const ROUTE_START := -3

@export var drive := false
## the smoke test turns the menu off and drives from the route start
@export var start_menu := true
## the world to load (directory or .world file); empty = the --world
## argument, else WorldLoader.default_path()
@export var world_path := ""

var _material := StandardMaterial3D.new()
var _water := StandardMaterial3D.new()
## the routes to choose from (WorldLoader.routes()), the chosen one (-1:
## free drive), its points and its marks in the world
var _routes: Array[Dictionary] = []
var _route_index := -1
var _route: Array = []
var _route_marks: Node3D
## the route's start, finish and checkpoint gates (route_gates.gd)
var _route_gates: Node3D
## the route is driven from its last point to its first
var _reversed := false
## reads the pace notes of the route (M mutes it)
var _co_driver: Node
var _co_driver_on := true
## the chevron band of the route on the road, toggled with G
var _show_band := false
## the manifest's start with the lap flag, the start of the world's route
var _lap_start := -1
## road centre lines (roads.bin) for F, null for a world without them
var _roads: RefCounted = null
var _waypoints: Array = []
var _starts: Array = []
var _start := -1
var _lap_mode := true
var _menu: CanvasLayer
var _env: Environment
var _size_m := 0.0
var _camera: Camera3D
var _car: RigidBody3D
var _hud: Label
var _compass: Control
var _minimap: Control
## a start chosen on the map or a route's first point: [position,
## look-at], used by R
var _free_start: Array = []
var _heading_deg := 0.0
var _world_id := ""
var _center := Vector2.ZERO
var _road_names: Array = []
var _readout: Label
var _readout_age := 0.0
var _next_checkpoint := 1
var _lap_started := -1
var _last_lap := ""
## the time of the checkpoint passed last, "" before the first
var _split := ""
var _world_name := ""
var _attribution := ""
var _launch_start := -1
var _credits: Label
var _credits_due := true


func _ready() -> void:
	_material.vertex_color_use_as_albedo = true
	_material.roughness = 1.0
	_water.vertex_color_use_as_albedo = true
	_water.roughness = 0.15
	_water.metallic_specular = 0.8
	_water.cull_mode = BaseMaterial3D.CULL_DISABLED
	_setup_environment()

	var launch := WORLD_LOADER.args()
	var searched: Array[String] = [world_path]
	if world_path.is_empty() and not launch.world.is_empty():
		world_path = launch.world
		searched = [world_path]
	elif world_path.is_empty():
		world_path = WORLD_LOADER.default_path()
		searched = WORLD_LOADER.default_candidates()
	var loader := WORLD_LOADER.new()
	if loader.open(world_path) != OK:
		_show_missing_world(loader.error, searched)
		return
	var meta := loader.manifest
	var started := Time.get_ticks_msec()
	for tile_name: String in meta.tiles:
		_add_scene(loader.load_scene(tile_name), drive)
	_add_scene(loader.load_scene(meta.horizon), false)
	if meta.get("roads") is String:
		_roads = ROAD_INDEX.new()
		var roads_started := Time.get_ticks_msec()
		var segments: int = _roads.load_rows(loader.read_bytes(meta.roads))
		print("loaded %d road segments in %d ms" % [segments,
			Time.get_ticks_msec() - roads_started])
		if segments == 0:
			_roads = null
	print("loaded %d tiles in %d ms (collision: %s)" % [
		meta.tiles.size(), Time.get_ticks_msec() - started, drive])
	if meta.get("trees") != null:
		started = Time.get_ticks_msec()
		var trees := Node3D.new()
		trees.set_script(preload("res://scripts/trees.gd"))
		add_child(trees)
		var count: int = trees.load_trees(loader, meta.trees,
			CAR.LAYER_BUILDINGS if drive else 0)
		print("loaded %d trees in %d ms" % [count,
			Time.get_ticks_msec() - started])

	if meta.get("signs") is String:
		var data: Variant = JSON.parse_string(
			loader.read_bytes(meta.signs).get_string_from_utf8())
		if data is Dictionary:
			var signs := Node3D.new()
			signs.set_script(preload("res://scripts/signs.gd"))
			add_child(signs)
			print("loaded %d signs" % signs.load_signs(data))

	_starts = meta.get("starts", [])
	_lap_start = _starts.find_custom(
		func(s: Dictionary) -> bool: return s.lap)
	_routes = loader.routes()
	# the world's own route reads as its lap start ("Ötlinger Rundkurs"),
	# not as the world
	if _lap_start >= 0 and not _routes.is_empty() \
			and _routes[0].id == "world":
		_routes[0].name = _starts[_lap_start].name
	var route_index := 0 if not _routes.is_empty() else -1
	if not launch.route.is_empty():
		var found := _routes.find_custom(
			func(r: Dictionary) -> bool: return r.id == launch.route)
		if found < 0:
			push_error("unknown route %s, driving the world's own route"
				% launch.route)
		else:
			route_index = found
	_reversed = launch.reverse
	_set_route(route_index)
	_world_name = loader.display_name()
	_attribution = loader.attribution()
	_launch_start = launch.start
	_size_m = meta.size_km * 1000.0
	_heading_deg = float(meta.get("heading_deg", 0.0))
	_world_id = str(meta.get("id", ""))
	var c: Array = meta.get("center", [0.0, 0.0])
	_center = Vector2(c[0], c[1])
	if meta.get("road_names") is String:
		var names: Variant = JSON.parse_string(
			loader.read_bytes(meta.road_names).get_string_from_utf8())
		if names is Array:
			_road_names = names

	_camera = Camera3D.new()
	_camera.far = 40000.0
	if drive:
		_setup_drive()
	else:
		_camera.set_script(preload("res://scripts/fly_cam.gd"))
		add_child(_camera)
		_jump_to(0)


## An export finds no world on its own; say why the world did not open
## and where it looked instead of crashing.
func _show_missing_world(reason: String, searched: Array[String]) -> void:
	var text := "No world: %s\nSearched:\n  " % reason \
		+ "\n  ".join(searched) \
		+ "\nPut a world folder (world.json) or a .world file there, or " \
		+ "start with -- --world <path>."
	push_error(text)
	var layer := CanvasLayer.new()
	var label := Label.new()
	label.text = text
	label.position = Vector2(24, 20)
	label.add_theme_font_size_override("font_size", 22)
	layer.add_child(label)
	add_child(layer)


func _setup_drive() -> void:
	_car = RigidBody3D.new()
	_car.set_script(CAR)
	add_child(_car)
	_car.reset_requested.connect(_reset_car)
	_car.road_requested.connect(_put_on_road)
	_place_car_at(0)
	_camera.set_script(preload("res://scripts/chase_cam.gd"))
	_camera.target = _car
	add_child(_camera)
	_camera.global_position = _car.global_position + Vector3(0, 3, 8)

	var layer := CanvasLayer.new()
	_hud = Label.new()
	_hud.position = Vector2(24, 20)
	_hud.add_theme_font_size_override("font_size", 28)
	_hud.add_theme_color_override("font_outline_color", Color.BLACK)
	_hud.add_theme_constant_override("outline_size", 6)
	layer.add_child(_hud)
	_compass = Control.new()
	_compass.set_script(preload("res://scripts/compass.gd"))
	layer.add_child(_compass)
	_compass.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT,
		Control.PRESET_MODE_KEEP_SIZE, 20)
	_compass.north_offset_deg = -_heading_deg
	_minimap = Control.new()
	_minimap.set_script(preload("res://scripts/minimap.gd"))
	_minimap.roads = _roads
	layer.add_child(_minimap)
	_minimap.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT,
		Control.PRESET_MODE_KEEP_SIZE, 20)
	if _roads == null:
		_minimap.hide()
	_credits = Label.new()
	_credits.text = "%s\n%s" % [_world_name, _attribution]
	_credits.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_credits.add_theme_font_size_override("font_size", 14)
	_credits.add_theme_color_override("font_outline_color", Color.BLACK)
	_credits.add_theme_constant_override("outline_size", 4)
	_credits.modulate = Color(1, 1, 1, 0.8)
	layer.add_child(_credits)
	_credits.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE,
		Control.PRESET_MODE_MINSIZE, 24)
	_credits.hide()
	add_child(layer)

	if start_menu and not _starts.is_empty():
		_menu = CanvasLayer.new()
		_menu.set_script(preload("res://scripts/start_menu.gd"))
		add_child(_menu)
		var names: Array = CAR.CARS.map(func(c: Dictionary): return c.name)
		_menu.setup(_starts, _size_m, _env, names, _car.car_index,
			_world_name, _routes, _route_index, _reversed)
		_menu.car_chosen.connect(_car.set_car)
		_menu.route_chosen.connect(_choose_route)
		_menu.direction_chosen.connect(_choose_direction)
		_menu.route_start_chosen.connect(start_route)
		_menu.start_chosen.connect(start_at)
		_menu.point_chosen.connect(start_free)
		_menu.resumed.connect(_resume)
		_open_menu()
	if _launch_start >= 0:
		if _launch_start < _starts.size():
			if _menu != null:
				_menu.hide()
			start_at.call_deferred(_launch_start)
		else:
			push_error("--start %d: the world has %d start points"
				% [_launch_start, _starts.size()])


## Puts the car on start point `index` of meta.starts; a start with the
## lap flag drives the chosen route with the lap timer, the others and
## any start in free drive drive free.
func start_at(index: int) -> void:
	var start: Dictionary = _starts[index]
	_start = index
	_new_lap(start.lap and _route.size() >= 2)
	var p: Array = start.pos
	var q: Array = start.look
	var at := Vector3(p[0], p[1], p[2])
	var look := Vector3(q[0], q[1], q[2])
	# the start points face along the route, so they face the chosen way
	if _reversed and _route.size() >= 2 and not start.lap:
		look = at * 2.0 - look
	_resume()
	_begin(at, look)


## Starts the chosen route with the lap timer: the world's own route on
## its lap start, any other on its first point.
func start_route() -> void:
	if _route.size() < 2:
		return
	if _routes[_route_index].id == "world" and _lap_start >= 0 \
			and not _reversed:
		start_at(_lap_start)
		return
	_start = ROUTE_START
	_new_lap(true)
	_resume()
	var p: Array = _route[0]
	var q: Array = _route[mini(3, _route.size() - 1)]
	# R after a route change mid-drive comes back here
	_free_start = [Vector3(p[0], p[1], p[2]), Vector3(q[0], p[1], q[2])]
	_begin(_free_start[0], _free_start[1])


## A start chosen on the map: the nearest road to `at` (x/z only), along
## it; back to the menu if the world has no road lines or none is near.
func start_free(at: Vector3) -> void:
	var near: Dictionary = {} if _roads == null else _roads.nearest(
		at, Vector3.FORWARD, true)
	if near.is_empty():
		_open_menu()
		return
	_start = FREE_START
	_lap_mode = false
	_free_start = [near.point, near.point + near.dir * 10.0]
	_resume()
	_begin(_free_start[0], _free_start[1])


func _new_lap(lap: bool) -> void:
	_lap_mode = lap
	_lap_started = -1
	_next_checkpoint = 1
	_last_lap = ""
	_split = ""


## A route chosen in the menu (-1: free drive); a drive under way goes on
## without the lap timer.
func _choose_route(index: int) -> void:
	_set_route(index)
	_new_lap(false)


## Shows route `index` of _routes in the world (route_marks.gd) and makes
## it the route of the lap starts, the lap timer and R; -1 is free drive:
## no route in the world, no lap.
func _set_route(index: int) -> void:
	if _route_marks != null:
		if index == _route_index:
			return
		_route_marks.queue_free()
		_route_marks = null
		_route_gates.queue_free()
		_route_gates = null
		_co_driver = null
	_route_index = index
	_route = [] if index < 0 else _routes[index].points
	if _reversed:
		_route = _route.duplicate()
		_route.reverse()
	if _route.size() < 2:
		_waypoints = []
		return
	_route_gates = Node3D.new()
	_route_gates.set_script(preload("res://scripts/route_gates.gd"))
	add_child(_route_gates)
	_route_gates.build(_route)
	# start, checkpoints every 4 to 10 km and finish
	_waypoints = _route_gates.indices.map(
		func(i: int) -> Array: return _route[i])
	var started := Time.get_ticks_msec()
	_route_marks = Node3D.new()
	_route_marks.set_script(preload("res://scripts/route_marks.gd"))
	add_child(_route_marks)
	var boards: int = _route_marks.build(_route, _roads,
		CAR.LAYER_BUILDINGS if drive else 0)
	_route_marks.show_band(_show_band)
	if drive and _car != null:
		_co_driver = CO_DRIVER.new()
		_co_driver.on = _co_driver_on
		_route_marks.add_child(_co_driver)
		_co_driver.setup(_route_marks, _car)
	print("route %s: %d boards, %d pace notes, %d curve signs in %d ms"
		% [_routes[index].id, boards, _route_marks.notes.size(),
		_route_marks.signs, Time.get_ticks_msec() - started])


## The direction chosen in the menu: false from the route's first point
## to its last, true the other way. The route marks are built again; a
## drive under way goes on without the lap timer.
func _choose_direction(reversed: bool) -> void:
	if reversed == _reversed:
		return
	_reversed = reversed
	var index := _route_index
	if _route_marks != null:
		_route_marks.queue_free()
		_route_marks = null
		_route_gates.queue_free()
		_route_gates = null
	_set_route(index)
	_new_lap(false)


func _begin(pos: Vector3, look: Vector3) -> void:
	if _credits != null and _credits_due:
		_credits_due = false
		_credits.show()
		get_tree().create_timer(CREDITS_S).timeout.connect(_credits.hide)
	_place_car(pos, look)
	_camera.global_position = _car.global_position \
		+ _car.global_basis.z * 8.0 + Vector3.UP * 3.0


func _open_menu() -> void:
	_car.freeze = true
	_hud.hide()
	_compass.hide()
	_minimap.hide()
	_menu.can_resume = _start != -1
	_menu.open()


func _resume() -> void:
	_car.freeze = false
	_hud.show()
	_compass.show()
	_minimap.visible = _roads != null


func _physics_process(delta: float) -> void:
	if _car == null:
		return
	_compass.follow(_camera)
	_minimap.follow(_car, _camera, delta)
	var gauge := "%3d km/h  %s  %4d/min\n%s" % [_car.speed_kmh,
		"R" if _car.gear < 0 else str(_car.gear), _car.rpm,
		_car.spec.name]
	if not _lap_mode or _waypoints.is_empty():
		_hud.text = "%s\n%s" % [gauge, _start_name()]
		return
	var now := Time.get_ticks_msec()
	var pos := _car.global_position
	if _lap_started < 0 and _car.speed_kmh > 2.0:
		_lap_started = now
		_next_checkpoint = 1
	if _lap_started >= 0:
		var target := _waypoint(_next_checkpoint % _waypoints.size())
		if Vector2(pos.x - target.x, pos.z - target.z).length() \
				< CHECKPOINT_RADIUS:
			if _next_checkpoint == _waypoints.size() - 1 \
					or _next_checkpoint == _waypoints.size():
				_last_lap = _format_time(now - _lap_started)
				_lap_started = -1
			else:
				_split = _format_time(now - _lap_started)
				_next_checkpoint += 1
	var lap := _format_time(now - _lap_started) if _lap_started >= 0 \
		else "--:--.-"
	_hud.text = "%s\nTime %s\nCheckpoint %d/%d  %s\nLast %s" % [
		gauge, lap, _next_checkpoint, _waypoints.size() - 1, _split,
		_last_lap]


## # : shows the position readout top centre (or hides it), copies it to
## the clipboard and prints it. While it shows, _process keeps it current,
## so a screenshot carries the spot it was taken at; the clipboard keeps
## the line of the key press.
func _toggle_readout() -> void:
	if _readout == null:
		var layer := CanvasLayer.new()
		layer.layer = 5
		add_child(layer)
		_readout = Label.new()
		_readout.add_theme_font_size_override("font_size", 16)
		_readout.add_theme_color_override("font_outline_color", Color.BLACK)
		_readout.add_theme_constant_override("outline_size", 6)
		_readout.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		layer.add_child(_readout)
		_readout.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP,
			Control.PRESET_MODE_MINSIZE, 12)
		_readout.hide()
	_readout.visible = not _readout.visible
	if _readout.visible:
		var text := _position_text()
		_readout.text = text
		DisplayServer.clipboard_set(text)
		print("POSITION " + text.replace("\n", " | "))
		_readout_age = 0.0


## in _process, not _physics_process: the readout shows in fly mode too
func _process(delta: float) -> void:
	if _readout == null or not _readout.visible:
		return
	_readout_age += delta
	if _readout_age >= READOUT_REFRESH_S:
		_readout_age = 0.0
		_readout.text = _position_text()


## World, nearest road, lat/lon (from the manifest centre and heading,
## a plane approximation good to metres), true heading, camera view and
## the camera as a viewpoint (local metres, as in godot/tools/*.json).
func _position_text() -> String:
	var at: Vector3 = _car.global_position if _car != null \
		else _camera.global_position
	var road := ""
	if _roads != null:
		var near: Dictionary = _roads.nearest(at, Vector3.FORWARD)
		if not near.is_empty():
			var e: int = near.edge
			road = str(_road_names[e]) if e < _road_names.size() else ""
			road = "%s (%.0f m)" % [road if not road.is_empty()
				else "unnamed road", near.distance]
	var a := deg_to_rad(_heading_deg)
	var east := at.x * cos(a) + at.z * sin(a)
	var north := at.x * sin(a) - at.z * cos(a)
	var lat := _center.x + north / 111320.0
	var lon := _center.y + east / (111320.0 * cos(deg_to_rad(_center.x)))
	var forward := -_camera.global_basis.z
	var yaw := fposmod(rad_to_deg(atan2(forward.x, -forward.z))
		- _heading_deg, 360.0)
	var pitch := rad_to_deg(asin(clampf(forward.y, -1.0, 1.0)))
	var look := _camera.global_position + forward * 20.0
	var view: String = "free" if not "view" in _camera \
		else ["far", "close", "driver"][_camera.view]
	var p := _camera.global_position
	return ("%s  %s  %.5f,%.5f  heading %03d°  pitch %+.0f°  camera %s\n"
		+ "{\"position\": [%.1f, %.1f, %.1f], \"look_at\": "
		+ "[%.1f, %.1f, %.1f]}") % [_world_id, road, lat, lon,
		roundi(yaw) % 360, pitch, view, p.x, p.y, p.z, look.x, look.y,
		look.z]


func _start_name() -> String:
	if _start >= 0:
		return _starts[_start].name
	if _start == ROUTE_START:
		return _routes[_route_index].name if _route_index >= 0 else ""
	return "Free start" if _start == FREE_START else ""


func _format_time(ms: int) -> String:
	return "%02d:%04.1f" % [ms / 60000, (ms % 60000) / 1000.0]


func _waypoint(index: int) -> Vector3:
	var p: Array = _waypoints[index]
	return Vector3(p[0], p[1], p[2])


## Places the car on route point `route_index`, facing along the route;
## a world without a route uses its first start point (or the origin).
func _place_car_at(route_index: int) -> void:
	if _route.size() < 2:
		var start: Dictionary = _starts[0] if not _starts.is_empty() \
			else {"pos": [0.0, 0.0, 0.0], "look": [0.0, 0.0, -1.0]}
		var s: Array = start.pos
		var l: Array = start.look
		_place_car(Vector3(s[0], s[1], s[2]), Vector3(l[0], l[1], l[2]))
		return
	var i := clampi(route_index, 0, _route.size() - 2)
	var p: Array = _route[i]
	var q: Array = _route[mini(i + 3, _route.size() - 1)]
	_place_car(Vector3(p[0], p[1], p[2]), Vector3(q[0], p[1], q[2]))


## Drops the car 1.2 m above the collision surface below `origin`. The
## ray starts PLACE_RAY_UP above it, below the lowest tunnel ceiling, so a
## point in a tunnel lands on the road and not on the hill above.
func _place_car(origin: Vector3, look: Vector3) -> void:
	var ray := PhysicsRayQueryParameters3D.create(
		origin + Vector3.UP * PLACE_RAY_UP, origin - Vector3.UP * 200.0,
		CAR.LAYER_GROUND)
	var hit := get_world_3d().direct_space_state.intersect_ray(ray)
	if not hit.is_empty():
		origin = hit.position
	_car.place(origin + Vector3.UP * 1.2, look)


## F: the car on the centre line of the nearest road (3D, so under a
## bridge the road below), along it in the direction it was heading; on
## the spot upright if the world has no road lines or none is near.
func _put_on_road() -> void:
	var near: Dictionary = {} if _roads == null else _roads.nearest(
		_car.global_position, -_car.global_basis.z)
	if near.is_empty() or _car.global_position.distance_to(near.point) \
			> ROAD_RESET_MAX_M:
		_car.upright()
		return
	_place_car(near.point, near.point + near.dir * 10.0)


func _reset_car() -> void:
	if _start == FREE_START or (_start == ROUTE_START and not _lap_mode):
		_place_car(_free_start[0], _free_start[1])
		return
	if not _lap_mode:
		start_at(_start)
		return
	var best := 0
	var best_dist := INF
	for i in _route.size():
		var p: Array = _route[i]
		var d := _car.global_position.distance_squared_to(
			Vector3(p[0], p[1], p[2]))
		if d < best_dist:
			best_dist = d
			best = i
	_place_car_at(best)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo \
			and (event.unicode == 35 or event.keycode == KEY_NUMBERSIGN):
		get_viewport().set_input_as_handled()
		_toggle_readout()
		return
	if event is InputEventKey and event.pressed and not event.echo \
			and event.keycode == KEY_G:
		get_viewport().set_input_as_handled()
		_show_band = not _show_band
		if _route_marks != null:
			_route_marks.show_band(_show_band)
		return
	if drive and event is InputEventKey and event.pressed and not event.echo \
			and event.keycode == KEY_M:
		get_viewport().set_input_as_handled()
		_co_driver_on = not _co_driver_on
		if _co_driver != null:
			_co_driver.on = _co_driver_on
		return
	if drive:
		if _menu != null and not _menu.visible and event is InputEventKey \
				and event.pressed and event.keycode == KEY_ESCAPE:
			get_viewport().set_input_as_handled()
			_open_menu()
		return
	if event is InputEventKey and event.pressed:
		var index: int = event.keycode - KEY_1
		if index >= 0 and index < 9:
			_jump_to(index)


func _jump_to(index: int) -> void:
	if index >= _waypoints.size():
		return
	var p: Array = _waypoints[index]
	_camera.position = Vector3(p[0], p[1] + 80.0, p[2] + 120.0)
	_camera.look_at(Vector3(p[0], p[1], p[2]))


## Adds a world scene with the vertex colour material; with `collide`
## every mesh but the markings, the rails and the water gets trimesh
## collision. The
## water surface (pipeline/water.py) takes _water: smooth, so it shines,
## and opaque (the bed lies below it). Skips a null scene (the loader has
## reported it).
func _add_scene(scene: Node, collide: bool) -> void:
	if scene == null:
		return
	for mesh: MeshInstance3D in scene.find_children("*", "MeshInstance3D"):
		if mesh.name.begins_with("water"):
			mesh.material_override = _water
			continue
		mesh.material_override = _material
		if collide and mesh.name != "markings" and mesh.name != "rails":
			mesh.create_trimesh_collision()
			if mesh.name.contains("buildings"):
				var body: StaticBody3D = mesh.get_child(-1)
				body.collision_layer = CAR.LAYER_BUILDINGS
	add_child(scene)


func _setup_environment() -> void:
	var sky := Sky.new()
	sky.sky_material = ProceduralSkyMaterial.new()
	var env := Environment.new()
	_env = env
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	# half the sky light on the shaded side, and ambient occlusion in
	# hollows, at the road edges and under trees: with the full sky light
	# and no occlusion the pale Corsican hills looked flat (2026-11-04).
	# SSAO needs Forward+; the compatibility renderer ignores it.
	env.ambient_light_energy = 0.5
	env.ssao_enabled = true
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.fog_enabled = true
	env.fog_density = 0.00012
	env.fog_aerial_perspective = 0.6
	var world_env := WorldEnvironment.new()
	world_env.environment = env
	add_child(world_env)

	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-40.0, -30.0, 0.0)
	sun.shadow_enabled = true
	# 500 m covers the tree shadows (trees.gd, up to 450 m); 1500 m made
	# the near shadow texels so coarse that they shimmered on every camera
	# move. The biases keep walls almost parallel to the sun free of acne.
	sun.directional_shadow_max_distance = 500.0
	sun.directional_shadow_blend_splits = true
	sun.shadow_bias = 0.15
	sun.shadow_normal_bias = 1.5
	add_child(sun)
# - revised 2026-10-22 (world.json manifest)
# - revised 2026-10-22 (world loader)
# - revised 2026-10-22 (--world argument)
# - revised 2026-10-22 (--route, --start, world credits)
# - revised 2026-10-22 (merge: missing-world notice through the loader)
# - revised 2026-10-23 (route band)
# - revised 2026-10-23 (F onto the nearest road)
# - revised 2026-10-23 (free start on the map, minimap, compass north offset)
# - revised 2026-10-23 (# position readout)
# - revised 2026-10-23 (direction signs)
# - revised 2026-10-26 (position readout follows the camera)
# - revised 2026-10-26 (route choice, free drive, chevrons and boards)
# - revised 2026-10-26 (pace notes and curve signs in the route log line)
# - revised 2026-10-26 (G toggles the route band)
# - revised 2026-11-03 (sun shadows: shorter range, blend splits, bias)
# - revised 2026-11-04 (half the ambient light, SSAO)
# - revised 2026-11-04 (water surface material, no collision)
