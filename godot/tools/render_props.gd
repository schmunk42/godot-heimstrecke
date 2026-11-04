# file generated with AI assistance: Claude Code - 2026-11-04 08:30:00 UTC
extends SceneTree
## Renders the route props as the game builds them, to judge a look
## without a world: a junction where the route turns, built by
## route_marks.gd (chevron board straight on, bales across the side road,
## ads on the arc between them, in both arc styles, the pace note sign
## before the turn), the pace note signs and signposts of signs.gd. Each
## sheet is one image; a sheet of variants side by side gets a code above
## each. No world data needed. Needs a display (a desktop window, or
## Xvfb + Mesa llvmpipe in the render image); --headless renders nothing
## and is rejected.
##
##   godot --path godot --resolution 1600x900 \
##       --script res://tools/render_props.gd -- --out <abs dir> \
##       [--no-shadows]
##
## Prints one "RENDER name=..." line per image and "RENDER OK views=<n>"
## with exit code 0, or "RENDER FAILED: <reason>" with exit code 1.

const MARKS := preload("res://scripts/route_marks.gd")
const SIGNS := preload("res://scripts/signs.gd")
const SETTLE_FRAMES := 3
const WATCHDOG_S := 600.0
## the variants of a sheet stand this far apart along x
const SLOT_M := 8.5
## the junction: the route comes in along +x and turns to -z at the
## origin, arms go on along +x and off along +z; samples this far apart
const ARM_M := 150.0
const SAMPLE_M := 2.5
## views by sheet: [eye, look at]
const VIEWS := {
	"junction-fence": [Vector3(-16.0, 7.0, -14.0), Vector3(4.0, 0.5, 4.0)],
	"junction-boards": [Vector3(-16.0, 7.0, -14.0), Vector3(4.0, 0.5, 4.0)],
	"junction-approach": [Vector3(-62.0, 1.5, -1.0),
		Vector3(10.0, 1.0, 0.0)],
	"pace-signs": [Vector3(0.0, 1.5, 16.0), Vector3(0.0, 1.4, 0.0)],
	"road-signs": [Vector3(0.0, 1.5, 14.0), Vector3(0.0, 1.4, 0.0)],
}

var _done := false


## The road centre lines of the junction for route_marks.gd.
class Roads extends RefCounted:
	var lines: Array[PackedVector3Array] = []

	func edge_lines() -> Array[PackedVector3Array]:
		return lines


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
	_add_stage(stage, no_shadows)
	var camera := Camera3D.new()
	camera.fov = 70.0
	stage.add_child(camera)
	camera.make_current()

	var sheets := {
		"junction-fence": [["", _junction.bind(0)]],
		"junction-boards": [["", _junction.bind(1)]],
		"junction-approach": [["", _junction.bind(0)]],
		"pace-signs": [["5", _pace.bind("pace", ["5", "@curve_right"])],
			["3", _pace.bind("pace_sharp", ["3", "@curve_left"])],
			["H", _pace.bind("pace_tight", ["H", "@curve_right"])],
			["4 into 2", _pace.bind("pace_sharp", ["4", "@curve_left",
				"2", "@curve_right"])]],
		"road-signs": [["federal", _road_sign.bind("federal", 0)],
			["local", _road_sign.bind("local", 1)],
			["motorway", _road_sign.bind("motorway", 1)],
			["town", _road_sign.bind("town", 2)]],
	}
	var count := 0
	for sheet: String in sheets:
		var row := Node3D.new()
		stage.add_child(row)
		var variants: Array = sheets[sheet]
		for k in variants.size():
			var slot := Node3D.new()
			slot.position.x = (k - (variants.size() - 1) / 2.0) * SLOT_M
			row.add_child(slot)
			variants[k][1].call(slot)
			if not variants[k][0].is_empty():
				_caption(slot, variants[k][0])
		var started := Time.get_ticks_msec()
		camera.look_at_from_position(VIEWS[sheet][0], VIEWS[sheet][1])
		for f in SETTLE_FRAMES:
			await process_frame
		await RenderingServer.frame_post_draw
		var image := root.get_viewport().get_texture().get_image()
		var file := out.path_join(sheet + ".png")
		if image == null or image.is_empty() or image.save_png(file) != OK:
			_fail("cannot write %s" % file)
			return
		count += 1
		print("RENDER name=%s ms=%d file=%s" % [sheet,
			Time.get_ticks_msec() - started, file])
		row.free()
	_done = true
	print("RENDER OK views=%d" % count)
	quit(0)


## Sky, sun and grass.
func _add_stage(stage: Node3D, no_shadows: bool) -> void:
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
	_flat(stage, Vector2(400.0, 400.0), Vector3.ZERO,
		Color(0.36, 0.45, 0.26))


func _flat(parent: Node3D, size: Vector2, at: Vector3, colour: Color) -> void:
	var mesh := PlaneMesh.new()
	mesh.size = size
	mesh.material = _shaded(colour)
	var node := MeshInstance3D.new()
	node.mesh = mesh
	node.position = at
	parent.add_child(node)


func _caption(slot: Node3D, text: String) -> void:
	var label := Label3D.new()
	label.text = text
	label.font_size = 48
	label.pixel_size = 0.012
	label.outline_size = 12
	label.modulate = Color.WHITE
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.fixed_size = false
	label.position = Vector3(0.0, 5.0, 0.0)
	slot.add_child(label)


## The junction through route_marks.gd, its first arc in ARC_STYLES
## number `arc_style`; the roads as grey strips.
func _junction(slot: Node3D, arc_style: int) -> void:
	var west := _line(Vector3(-ARM_M, 0.0, 0.0), Vector3.ZERO)
	var north := _line(Vector3.ZERO, Vector3(0.0, 0.0, -ARM_M))
	var route: Array = []
	for p in west + north.slice(1):
		route.append([p.x, p.y, p.z])
	var roads := Roads.new()
	roads.lines = [west, north, _line(Vector3.ZERO, Vector3(ARM_M, 0, 0)),
		_line(Vector3.ZERO, Vector3(0.0, 0.0, ARM_M))]
	for d in [Vector3(1, 0, 0), Vector3(0, 0, 1)]:
		_flat(slot, Vector2(2.0 * ARM_M * d.x + 7.0 * d.z,
			2.0 * ARM_M * d.z + 7.0 * d.x), Vector3(0.0, 0.01, 0.0),
			Color(0.3, 0.3, 0.32))
	var marks := Node3D.new()
	marks.set_script(MARKS)
	slot.add_child(marks)
	marks.arc_count = arc_style
	marks.build(route, roads, 0)


## Points SAMPLE_M apart from `a` to `b`.
func _line(a: Vector3, b: Vector3) -> PackedVector3Array:
	var n := ceili(a.distance_to(b) / SAMPLE_M)
	var line := PackedVector3Array()
	for k in n + 1:
		line.append(a.lerp(b, float(k) / n))
	return line


## A pace note sign of `kind` as route_marks.gd places it.
func _pace(slot: Node3D, kind: String, lines: Array) -> void:
	_signs(slot, [{"pos": [0.0, 0.0, 0.0], "face": [0.0, 1.0],
		"kind": kind, "lines": lines, "scale": MARKS.SIGN_SCALE,
		"bottom": MARKS.SIGN_BOTTOM}])


## A signpost of `kind`: `which` 0 with a ref and two places, 1 with
## arrows, 2 a town name.
func _road_sign(slot: Node3D, kind: String, which: int) -> void:
	_signs(slot, [{"pos": [0.0, 0.0, 0.0], "face": [0.0, 1.0],
		"kind": kind, "lines": [["Waiblingen", "Stuttgart"],
			["↑ Schorndorf", "← Backnang", "→ Esslingen"],
			["Waiblingen"]][which], "ref": ["B 14", "", ""][which]}])


func _signs(slot: Node3D, data: Array) -> void:
	var node := Node3D.new()
	node.set_script(SIGNS)
	slot.add_child(node)
	node.load_signs({"signs": data})


# --- helpers ----------------------------------------------------------

func _shaded(colour: Color) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = colour
	mat.roughness = 0.95
	return mat


func _fail(reason: String) -> void:
	_done = true
	printerr("RENDER FAILED: %s" % reason)
	quit(1)


func _on_watchdog() -> void:
	if not _done:
		_fail("watchdog after %d s" % WATCHDOG_S)
# - revised 2026-11-04 (the chosen looks from the game code, a junction)
