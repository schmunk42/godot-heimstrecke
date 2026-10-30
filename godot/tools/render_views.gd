# file generated with AI assistance: Claude Code - 2026-10-20 22:29:15 UTC
extends SceneTree
## Renders still images of fixed viewpoints of the fly scene to PNG files,
## one per view of a viewpoint list (res://tools/viewpoints.json). Needs a
## real display server (Xvfb + Mesa llvmpipe in the screenshot container);
## --headless renders nothing and is rejected.
##
##   godot --path godot --display-driver x11 --rendering-driver opengl3 \
##       --rendering-method gl_compatibility --audio-driver Dummy \
##       --resolution 1280x720 --script res://tools/render_views.gd \
##       -- --out <abs dir> [--views <res:// or abs path>] \
##       [--world <world dir or .world file>] [--no-shadows]
##
## --world defaults to the built Stuttgart world (WorldLoader
## default_path()). A view has a name ([a-z0-9_-]+, the PNG file name) and
## either a
## "waypoint" index into world.json waypoints (camera at waypoint + "offset",
## default [0, 80, 120], as the 1-9 keys of the fly scene) or an absolute
## "position" plus "look_at". Prints one "RENDER name=..." line per view and
## "RENDER OK views=<n>" with exit code 0, or "RENDER FAILED: <reason>"
## with exit code 1.

const SCENE := "res://scenes/fly.tscn"
const DEFAULT_VIEWS := "res://tools/viewpoints.json"
## preloaded: without the editor's class cache class_name is unknown
const WORLD_LOADER := preload("res://scripts/world_loader.gd")
const DEFAULT_OFFSET := [0.0, 80.0, 120.0]
const SETTLE_FRAMES := 3
const WATCHDOG_S := 1800.0

var _done := false


func _initialize() -> void:
	create_timer(WATCHDOG_S).timeout.connect(_on_watchdog)
	_start()


func _start() -> void:
	var args := _parse_args(OS.get_cmdline_user_args())
	if args.is_empty():
		return
	var views := _load_views(args.views)
	if views.is_empty():
		return
	var loader := WORLD_LOADER.new()
	loader.open(args.world)
	if not _check_world(loader, views):
		return
	if DisplayServer.get_name() == "headless":
		_fail("headless display server renders nothing, run under Xvfb "
			+ "with --display-driver x11")
		return
	print("RENDER INFO adapter=%s method=%s driver=%s display=%s" % [
		RenderingServer.get_video_adapter_name(),
		RenderingServer.get_current_rendering_method(),
		RenderingServer.get_current_rendering_driver_name(),
		DisplayServer.get_name()])

	# the world's _ready() runs on the first main loop iteration
	var world: Node = load(SCENE).instantiate()
	world.set("world_path", args.world)
	root.add_child(world)
	if not world.is_node_ready():
		await world.ready
	var camera: Camera3D = world.get("_camera")
	var waypoints: Array = world.get("_waypoints")
	if camera == null:
		_fail("fly scene has no camera")
		return
	if args.no_shadows:
		for light: DirectionalLight3D in world.find_children(
				"*", "DirectionalLight3D", true, false):
			light.shadow_enabled = false

	for view: Dictionary in views:
		var started := Time.get_ticks_msec()
		if view.has("waypoint"):
			var p := _vec(waypoints[int(view.waypoint)])
			camera.position = p + _vec(view.get("offset", DEFAULT_OFFSET))
			camera.look_at(p)
		else:
			camera.position = _vec(view.position)
			camera.look_at(_vec(view.look_at))
		# a single frame can still show the previous camera
		for i in SETTLE_FRAMES:
			await process_frame
		await RenderingServer.frame_post_draw
		var image := root.get_viewport().get_texture().get_image()
		if image == null or image.is_empty():
			_fail("empty viewport image for view %s" % view.name)
			return
		var file: String = args.out.path_join(view.name + ".png")
		var err := image.save_png(file)
		if err != OK:
			_fail("cannot write %s (%s)" % [file, error_string(err)])
			return
		print("RENDER name=%s ms=%d size=%dx%d file=%s" % [view.name,
			Time.get_ticks_msec() - started, image.get_width(),
			image.get_height(), file])

	_done = true
	print("RENDER OK views=%d" % views.size())
	quit(0)


## Returns {out, views, world, no_shadows} or {} after failing.
func _parse_args(argv: PackedStringArray) -> Dictionary:
	var args := {"out": "", "views": DEFAULT_VIEWS,
		"world": WORLD_LOADER.default_path(), "no_shadows": false}
	var i := 0
	while i < argv.size():
		var arg := argv[i]
		if arg == "--no-shadows":
			args.no_shadows = true
		elif arg in ["--out", "--views", "--world"]:
			if i + 1 >= argv.size() or argv[i + 1].begins_with("--"):
				_fail("%s needs a value" % arg)
				return {}
			i += 1
			args[arg.trim_prefix("--")] = argv[i]
		else:
			_fail("unknown argument %s" % arg)
			return {}
		i += 1
	if args.out.is_empty():
		_fail("--out <dir> is required")
		return {}
	if not DirAccess.dir_exists_absolute(args.out):
		_fail("output directory missing: %s" % args.out)
		return {}
	args.world = WORLD_LOADER.absolute_path(args.world)
	return args


## Returns the validated views or [] after failing.
func _load_views(path: String) -> Array:
	if not FileAccess.file_exists(path):
		_fail("views file missing: %s" % path)
		return []
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not data is Dictionary or not data.get("views") is Array \
			or data.views.is_empty():
		_fail("views file is not valid JSON with a non-empty views list: %s"
			% path)
		return []
	var names := {}
	var name_re := RegEx.create_from_string("^[a-z0-9_-]+$")
	for view: Variant in data.views:
		var name: Variant = view.get("name") if view is Dictionary else null
		if not name is String or name_re.search(name) == null:
			_fail("view without a valid name ([a-z0-9_-]+): %s" % [view])
			return []
		if names.has(name):
			_fail("duplicate view name %s" % name)
			return []
		names[name] = true
		var by_waypoint: bool = view.has("waypoint") \
			and view.waypoint is float and view.waypoint >= 0 \
			and view.waypoint == floorf(view.waypoint) \
			and (not view.has("offset") or _is_vec(view.offset))
		var by_position: bool = _is_vec(view.get("position")) \
			and _is_vec(view.get("look_at"))
		if not by_waypoint and not by_position:
			_fail("view %s needs a waypoint index (optional offset [x, y, z])"
				% name + " or position and look_at [x, y, z]")
			return []
	return data.views


## Checks that `loader` has opened the world and the waypoint indices
## against its manifest.
func _check_world(loader: WORLD_LOADER, views: Array) -> bool:
	if not loader.error.is_empty():
		_fail(loader.error)
		return false
	var waypoints: Variant = loader.manifest.get("waypoints")
	var count: int = waypoints.size() if waypoints is Array else 0
	for view: Dictionary in views:
		if view.has("waypoint") and int(view.waypoint) >= count:
			_fail("view %s: waypoint %d out of range (world has %d, built "
				% [view.name, int(view.waypoint), count] + "with --route?)")
			return false
	return true


func _is_vec(value: Variant) -> bool:
	return value is Array and value.size() == 3 \
		and value.all(func(v: Variant) -> bool: return v is float)


func _vec(p: Array) -> Vector3:
	return Vector3(p[0], p[1], p[2])


func _on_watchdog() -> void:
	if _done:
		return
	_fail("watchdog after %d s" % WATCHDOG_S)


func _fail(reason: String) -> void:
	_done = true
	print("RENDER FAILED: ", reason)
	quit(1)
# - revised 2026-10-22 (world.json manifest)
# - revised 2026-10-22 (world loader)
# - revised 2026-10-22 (--world argument, .world packages)
