# file generated with AI assistance: Claude Code - 2026-10-21 00:45:00 UTC
extends CanvasLayer
## Start menu of the drive scene: a top-down map of the loaded world with
## numbered markers and the chosen route as a red line, one toggle button
## per car, one per route plus "Free drive", and one button per start: the
## start of the chosen route (with the lap timer) and the start points of
## the world manifest but its lap start, which the route start stands
## for. C or a click chooses the car, T or a click the route, D or the
## button the direction of the route (direction_chosen), keys 1-9
## and 0 the first ten starts, a click any start, a click on the map a
## free start (point_chosen: the world point under the click, world.gd
## snaps it onto the nearest road), Esc resumes the current drive. The
## map stays square and shrinks to fit small windows, also after a
## resize.

signal start_chosen(index: int)
signal route_start_chosen
signal route_chosen(index: int)
signal direction_chosen(reversed: bool)
signal point_chosen(at: Vector3)
signal car_chosen(index: int)
signal resumed

const MAP_PX := 1024
const MAP_SHOWN := 640.0
## at most this share of the window height / width goes to the map
const MAP_SHARE := Vector2(0.45, 0.75)
const MAP_HEIGHT := 3000.0

var can_resume := false

var _map_view: SubViewport
var _map_camera: Camera3D
var _map_rect: TextureRect
var _starts: Array = []
var _car_buttons: Array[Button] = []
var _car := 0
var _routes: Array = []
## the chosen route, -1 for free drive
var _route := -1
var _route_buttons: Array[Button] = []
var _route_start: Button
## the direction button, and whether the route is driven backwards
var _direction: Button
var _reversed := false
## the chosen route on the map: the line and its points on the map texture
var _route_line: Line2D
var _route_px := PackedVector2Array()
## the start buttons in key order, each a Callable
var _entries: Array[Callable] = []
var _map_shown := MAP_SHOWN
## per start marker: its dot, its label and its point on the map texture
var _markers: Array = []


## size_m: edge of the playable square; env: the world's environment,
## copied without fog so the map stays readable from above; car_names:
## the cars to choose from, car: the one chosen now; world_name: a title
## line above the lists (none when empty); routes: WorldLoader.routes()
## (name, points), route: the one chosen now, -1 for free drive.
func setup(starts: Array, size_m: float, env: Environment,
		car_names: Array, car: int, world_name := "", routes: Array = [],
		route := -1, reversed := false) -> void:
	_starts = starts
	_reversed = reversed
	_car = car
	_routes = routes
	layer = 10

	_map_view = SubViewport.new()
	_map_view.size = Vector2i(MAP_PX, MAP_PX)
	_map_view.render_target_update_mode = SubViewport.UPDATE_DISABLED
	add_child(_map_view)
	_map_camera = Camera3D.new()
	_map_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	_map_camera.size = size_m
	_map_camera.far = MAP_HEIGHT * 2.0
	_map_camera.position = Vector3(0.0, MAP_HEIGHT, 0.0)
	_map_camera.rotation_degrees = Vector3(-90.0, 0.0, 0.0)
	var map_env: Environment = env.duplicate()
	map_env.fog_enabled = false
	_map_camera.environment = map_env
	_map_view.add_child(_map_camera)

	var shade := ColorRect.new()
	shade.color = Color(0.05, 0.06, 0.08, 0.85)
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(shade)

	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 32)
	center.add_child(row)

	_map_rect = TextureRect.new()
	_map_rect.texture = _map_view.get_texture()
	_map_rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	# the row would stretch the map to the height of the start list
	_map_rect.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_map_rect.mouse_filter = Control.MOUSE_FILTER_STOP
	_map_rect.mouse_default_cursor_shape = Control.CURSOR_CROSS
	_map_rect.gui_input.connect(_on_map_input)
	row.add_child(_map_rect)
	_route_line = Line2D.new()
	_route_line.width = 3.0
	_route_line.default_color = Color(1.0, 0.15, 0.1)
	_map_rect.add_child(_route_line)

	var list := VBoxContainer.new()
	list.add_theme_constant_override("separation", 6)
	list.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_child(list)
	if not world_name.is_empty():
		var world_title := Label.new()
		world_title.text = world_name
		world_title.add_theme_font_size_override("font_size", 36)
		list.add_child(world_title)
	var car_title := Label.new()
	car_title.text = "Choose a car"
	car_title.add_theme_font_size_override("font_size", 30)
	list.add_child(car_title)
	var group := ButtonGroup.new()
	for i in car_names.size():
		var button := Button.new()
		button.text = car_names[i]
		button.toggle_mode = true
		button.button_group = group
		button.button_pressed = i == car
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.add_theme_font_size_override("font_size", 18)
		button.pressed.connect(_choose_car.bind(i))
		list.add_child(button)
		_car_buttons.append(button)
	if not _routes.is_empty():
		var route_title := Label.new()
		route_title.text = "Choose a route"
		route_title.add_theme_font_size_override("font_size", 30)
		list.add_child(route_title)
		var routes_group := ButtonGroup.new()
		for i in _routes.size() + 1:
			var button := _button(list, _routes[i].name
				if i < _routes.size() else "Free drive")
			button.toggle_mode = true
			button.button_group = routes_group
			button.pressed.connect(_choose_route.bind(
				i if i < _routes.size() else -1))
			_route_buttons.append(button)
	if not _routes.is_empty():
		_direction = _button(list, "")
		_direction.pressed.connect(_toggle_direction)
	var title := Label.new()
	title.text = "Choose a start"
	title.add_theme_font_size_override("font_size", 30)
	list.add_child(title)
	if not _routes.is_empty():
		_route_start = _button(list, "")
		_route_start.pressed.connect(_start_route)
		_entries.append(_start_route)
	for i in _starts.size():
		var start: Dictionary = _starts[i]
		if start.lap and not _routes.is_empty():
			continue
		var key := _key_name(_entries.size())
		var button := _button(list, "%s   %s  –  %s%s" % [key, start.name,
			start.road, "  (lap)" if start.lap else ""])
		button.pressed.connect(_choose.bind(i))
		_entries.append(_choose.bind(i))
		var p: Array = start.pos
		_add_marker(key, Vector3(p[0], p[1], p[2]), Color(1.0, 0.85, 0.1))
	if not _routes.is_empty():
		_add_marker(_key_name(0), Vector3.ZERO, Color(1.0, 0.15, 0.1))
	var hint := Label.new()
	hint.text = "C next car   T next route   D direction   1-9, 0 or click start\n" \
		+ "Esc menu / resume   Click the map: start on the nearest road\n" \
		+ "R back to the start   F onto the nearest road   V camera\n" \
		+ "G route line on the road"
	hint.modulate = Color(1, 1, 1, 0.7)
	list.add_child(hint)
	_show_route(route)
	get_viewport().size_changed.connect(_fit)
	hide()


func open() -> void:
	_map_view.render_target_update_mode = SubViewport.UPDATE_ONCE
	show()


## Map size from the current window, markers placed to match.
func _fit() -> void:
	var window := get_viewport().get_visible_rect().size
	_map_shown = minf(MAP_SHOWN, minf(window.x * MAP_SHARE.x,
		window.y * MAP_SHARE.y))
	_map_rect.custom_minimum_size = Vector2(_map_shown, _map_shown)
	var ratio := _map_shown / MAP_PX
	for marker in _markers:
		var at: Vector2 = marker[2] * ratio
		marker[0].position = at - marker[0].size / 2
		marker[1].position = at + Vector2(6, -26)
	var line := PackedVector2Array()
	for px in _route_px:
		line.append(px * ratio)
	_route_line.points = line


## A button of the lists, left aligned.
func _button(list: VBoxContainer, text: String) -> Button:
	var button := Button.new()
	button.text = text
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.add_theme_font_size_override("font_size", 18)
	list.add_child(button)
	return button


## Route `index` (-1: free drive) as the pressed route button, the route
## start button and the line and start marker on the map.
func _show_route(index: int) -> void:
	_route = index
	_route_px.clear()
	if _route_buttons.is_empty():
		_fit()
		return
	_route_buttons[index if index >= 0 else _routes.size()] \
		.button_pressed = true
	_route_start.disabled = index < 0
	_direction.disabled = index < 0
	_direction.text = _direction_text(index)
	_route_start.text = "%s   %s" % [_key_name(0), "%s  (lap)"
		% _routes[index].name if index >= 0 else "No route (free drive)"]
	# the route start marker is the last marker
	var marker: Array = _markers[-1]
	marker[0].visible = index >= 0
	marker[1].visible = index >= 0
	if index >= 0:
		var points: Array = _routes[index].points
		for k in range(0, points.size(), maxi(1, points.size() / 400)):
			var p: Array = points[k]
			_route_px.append(_map_camera.unproject_position(
				Vector3(p[0], p[1], p[2])))
		marker[2] = _route_px[0]
	_fit()


func _add_marker(key: String, at: Vector3, colour: Color) -> void:
	var px := _map_camera.unproject_position(at)
	var dot := ColorRect.new()
	dot.color = colour
	dot.size = Vector2(10, 10)
	dot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_map_rect.add_child(dot)
	var label := Label.new()
	label.text = key
	label.add_theme_font_size_override("font_size", 18)
	label.add_theme_color_override("font_outline_color", Color.BLACK)
	label.add_theme_constant_override("outline_size", 8)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_map_rect.add_child(label)
	_markers.append([dot, label, px])


## A left click on the map: the world point under it (y = 0, the map
## camera looks straight down).
func _on_map_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton and event.pressed
			and event.button_index == MOUSE_BUTTON_LEFT):
		return
	var px: Vector2 = event.position * (MAP_PX / _map_shown)
	var at := _map_camera.project_position(px, MAP_HEIGHT)
	get_viewport().gui_release_focus()
	hide()
	point_chosen.emit(Vector3(at.x, 0.0, at.z))


func _choose(index: int) -> void:
	get_viewport().gui_release_focus()
	hide()
	start_chosen.emit(index)


func _start_route() -> void:
	if _route < 0:
		return
	get_viewport().gui_release_focus()
	hide()
	route_start_chosen.emit()


func _choose_route(index: int) -> void:
	_show_route(index)
	route_chosen.emit(index)


## "Direction  D   Aléria → Corte": the ends come from the route name
## ("… A – B"), else forward / backward.
func _direction_text(index: int) -> String:
	var from := ""
	var to := ""
	if index >= 0:
		var ends: PackedStringArray = _routes[index].name.split(" – ")
		if ends.size() == 2:
			from = ends[0].get_slice(": ", ends[0].get_slice_count(": ") - 1)
			to = ends[1]
	if from.is_empty():
		return "D   Direction: %s" % ("backward" if _reversed else "forward")
	return "D   Direction: %s → %s" % ([to, from] if _reversed
		else [from, to])


func _toggle_direction() -> void:
	_reversed = not _reversed
	_direction.text = _direction_text(_route)
	direction_chosen.emit(_reversed)


func _choose_car(index: int) -> void:
	_car = index
	_car_buttons[index].button_pressed = true
	car_chosen.emit(index)


func _unhandled_input(event: InputEvent) -> void:
	if not visible or not (event is InputEventKey and event.pressed):
		return
	var index := _key_index(event.keycode)
	if event.keycode == KEY_C and not event.echo:
		get_viewport().set_input_as_handled()
		_choose_car((_car + 1) % _car_buttons.size())
	elif event.keycode == KEY_T and not event.echo \
			and not _route_buttons.is_empty():
		get_viewport().set_input_as_handled()
		# the buttons are the routes, then free drive (-1)
		var next := (_route + 1) % (_routes.size() + 1)
		_choose_route(next if next < _routes.size() else -1)
	elif event.keycode == KEY_D and not event.echo \
			and _direction != null and not _direction.disabled:
		get_viewport().set_input_as_handled()
		_toggle_direction()
	elif index >= 0 and index < _entries.size():
		get_viewport().set_input_as_handled()
		_entries[index].call()
	elif event.keycode == KEY_ESCAPE and can_resume:
		get_viewport().set_input_as_handled()
		get_viewport().gui_release_focus()
		hide()
		resumed.emit()


## Digit keys 1-9 and 0 stand for the starts 1-10; -1 for any other key.
func _key_index(code: Key) -> int:
	if code == KEY_0:
		return 9
	if code >= KEY_1 and code <= KEY_9:
		return code - KEY_1
	return -1


## Key label of start index, blank for starts without a key.
func _key_name(index: int) -> String:
	if index < 9:
		return str(index + 1)
	return "0" if index == 9 else "  "
# - revised 2026-10-22 (optional world title)
# - revised 2026-10-23 (hint for F)
# - revised 2026-10-23 (free start by a click on the map)
# - revised 2026-10-25 (square map after the start list grew, refit on resize)
# - revised 2026-10-26 (route choice, free drive, route on the map)
# - revised 2026-10-26 (hint for G)
