# file generated with AI assistance: Claude Code - 2026-10-22 16:30:00 UTC
extends SceneTree
## Renders still images (PNG) of every car of cars.gd on a grey floor:
## front three-quarter, rear three-quarter and side view, one file
## <car index>-<view>.png each. No world data needed. Needs a display
## (a desktop window, or Xvfb + Mesa llvmpipe in the render image);
## --headless renders nothing and is rejected.
##
##   godot --path godot --resolution 1280x720 \
##       --script res://tools/render_cars.gd -- --out <abs dir> \
##       [--no-shadows]
##
## Prints one "RENDER name=..." line per image and "RENDER OK views=<n>"
## with exit code 0, or "RENDER FAILED: <reason>" with exit code 1.

const CARS := preload("res://scripts/cars.gd").CARS
const MODEL := preload("res://scripts/car_model.gd")
const SETTLE_FRAMES := 3
const WATCHDOG_S := 600.0
## camera position and look-at point, car front is -Z
const VIEWS := {
	"front": [Vector3(-4.2, 1.5, -5.4), Vector3(0.0, 0.55, -0.3)],
	"rear": [Vector3(4.2, 1.8, 5.4), Vector3(0.0, 0.6, 0.3)],
	"side": [Vector3(-7.5, 0.9, 0.0), Vector3(0.0, 0.6, 0.0)],
}

var _done := false


func _initialize() -> void:
	create_timer(WATCHDOG_S).timeout.connect(_on_watchdog)
	_start()


func _start() -> void:
	var out := ""
	var no_shadows := false
	var argv := OS.get_cmdline_user_args()
	var i := 0
	while i < argv.size():
		if argv[i] == "--out" and i + 1 < argv.size():
			i += 1
			out = argv[i]
		elif argv[i] == "--no-shadows":
			no_shadows = true
		else:
			_fail("unknown argument %s" % argv[i])
			return
		i += 1
	if out.is_empty() or not DirAccess.dir_exists_absolute(out):
		_fail("--out <existing dir> is required")
		return
	if DisplayServer.get_name() == "headless":
		_fail("headless display server renders nothing")
		return

	var stage := Node3D.new()
	root.add_child(stage)
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	env.sky.sky_material = ProceduralSkyMaterial.new()
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	var world_env := WorldEnvironment.new()
	world_env.environment = env
	stage.add_child(world_env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-40.0, -30.0, 0.0)
	sun.shadow_enabled = not no_shadows
	stage.add_child(sun)
	var floor_mesh := PlaneMesh.new()
	floor_mesh.size = Vector2(60.0, 60.0)
	var floor_mat := StandardMaterial3D.new()
	floor_mat.albedo_color = Color(0.42, 0.42, 0.44)
	floor_mesh.material = floor_mat
	var floor_node := MeshInstance3D.new()
	floor_node.mesh = floor_mesh
	stage.add_child(floor_node)
	var camera := Camera3D.new()
	camera.fov = 45.0
	stage.add_child(camera)
	camera.make_current()

	var count := 0
	for index in CARS.size():
		var car := _build_car(CARS[index])
		stage.add_child(car)
		for view: String in VIEWS:
			var started := Time.get_ticks_msec()
			camera.look_at_from_position(VIEWS[view][0], VIEWS[view][1])
			for k in SETTLE_FRAMES:
				await process_frame
			await RenderingServer.frame_post_draw
			var image := root.get_viewport().get_texture().get_image()
			var name := "%d-%s" % [index + 1, view]
			var file := out.path_join(name + ".png")
			if image == null or image.is_empty() \
					or image.save_png(file) != OK:
				_fail("cannot write %s" % file)
				return
			count += 1
			print("RENDER name=%s ms=%d file=%s" % [name,
				Time.get_ticks_msec() - started, file])
		car.free()
	_done = true
	print("RENDER OK views=%d" % count)
	quit(0)


## The car at rest on the floor: origin at the height car.gd keeps it
## (mount, spring travel at rest, tyre radius), wheels on the floor.
func _build_car(spec: Dictionary) -> Node3D:
	var sag: float = spec.mass * 9.81 / 4.0 / spec.spring
	var travel: float = spec.rest - sag
	var car := Node3D.new()
	car.position.y = -spec.wheels[0].y + travel + spec.radius
	var model := Node3D.new()
	model.position.y = -car.position.y
	car.add_child(model)
	var wheels: Array[MeshInstance3D] = MODEL.build(model, car, spec)
	for i in wheels.size():
		wheels[i].position = spec.wheels[i] - Vector3.UP * travel
		wheels[i].basis = Basis(Vector3.FORWARD, PI / 2)
	return car


func _on_watchdog() -> void:
	if not _done:
		_fail("watchdog after %d s" % WATCHDOG_S)


func _fail(reason: String) -> void:
	_done = true
	print("RENDER FAILED: %s" % reason)
	quit(1)
