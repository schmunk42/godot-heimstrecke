# file generated with AI assistance: Claude Code - 2026-10-27 18:00:00 UTC
extends Node3D
## The gates of a route: a black and white chequered banner over the road
## at its start and another at its finish (the same place on a circuit),
## and a blue and yellow checkpoint gate on the way, one every 4 to 10 km.
## A gate is two posts either side of the road and a banner between them
## (BANNER_H high, its lower edge BANNER_BOTTOM above the route point),
## with its label above it, readable from both directions. Gates have no collision.
##
## checkpoints() picks the checkpoint route points: the route is cut into
## the fewest equal legs of at most MAX_LEG_M (so each leg is longer than
## half of it, at least 5 km on a route over 10 km); a route up to
## MAX_LEG_M has only start and finish.

const MAX_LEG_M := 10000.0
const HALF_WIDTH := 6.5
const POST_W := 0.35
const POST_H := 5.6
const BANNER_BOTTOM := 4.3
const BANNER_H := 1.2
## squares of the chequered banner, in metres
const CHECK_M := 0.6
const START_AHEAD_M := 4.0
const LABEL_PIXEL := 0.012
const LABEL_M := 400.0
const BLACK := Color(0.05, 0.05, 0.05)
const WHITE := Color(0.97, 0.97, 0.95)
const BLUE := Color(0.05, 0.2, 0.7)
const YELLOW := Color(1.0, 0.85, 0.0)
const POST := Color(0.55, 0.56, 0.58)

## the route point indices of start, checkpoints and finish
var indices: Array[int] = []


## The indices into `points` ([x, y, z] rows) of start, checkpoints and
## finish: legs of equal length, none over MAX_LEG_M.
static func checkpoints(points: Array) -> Array[int]:
	var result: Array[int] = [0]
	if points.size() < 2:
		return result
	var along := PackedFloat32Array()
	along.resize(points.size())
	for i in range(1, points.size()):
		var a: Array = points[i - 1]
		var b: Array = points[i]
		along[i] = along[i - 1] + Vector2(b[0] - a[0], b[2] - a[2]).length()
	var legs := maxi(1, ceili(along[points.size() - 1] / MAX_LEG_M))
	var next := 1
	for i in points.size():
		while next < legs and along[i] >= along[points.size() - 1] \
				* next / legs:
			result.append(i)
			next += 1
	result.append(points.size() - 1)
	return result


## Builds the gates of `points` and returns their number. Start, finish
## and the checkpoints in between are labelled; `indices` holds the route
## points of all of them.
func build(points: Array) -> int:
	indices = checkpoints(points)
	var checks := SurfaceTool.new()
	checks.begin(Mesh.PRIMITIVE_TRIANGLES)
	var blue := SurfaceTool.new()
	blue.begin(Mesh.PRIMITIVE_TRIANGLES)
	var posts := SurfaceTool.new()
	posts.begin(Mesh.PRIMITIVE_TRIANGLES)
	for k in indices.size():
		var i := indices[k]
		var p := _point(points, i)
		var f := _heading(points, i)
		if k == 0:
			p += f * START_AHEAD_M
		var title := "START" if k == 0 else "FINISH" \
			if k == indices.size() - 1 else "CHECKPOINT %d" % k
		_gate(checks if k == 0 or k == indices.size() - 1 else blue, posts,
			p, f, title, k == 0 or k == indices.size() - 1)
	_commit(checks, _chequered())
	_commit(blue, _flat(BLUE))
	_commit(posts, _flat(POST))
	return indices.size()


static func _point(points: Array, i: int) -> Vector3:
	var p: Array = points[i]
	return Vector3(p[0], p[1], p[2])


## The horizontal direction of the route at point `i`.
static func _heading(points: Array, i: int) -> Vector3:
	var a := _point(points, maxi(i - 1, 0))
	var b := _point(points, mini(i + 1, points.size() - 1))
	var d := Vector3(b.x - a.x, 0.0, b.z - a.z)
	return d.normalized() if d.length() > 0.001 else Vector3.FORWARD


func _gate(banner: SurfaceTool, posts: SurfaceTool, at: Vector3,
		forward: Vector3, title: String, chequered: bool) -> void:
	var right := Vector3(-forward.z, 0.0, forward.x)
	var lo := Vector3.UP * BANNER_BOTTOM
	var hi := Vector3.UP * (BANNER_BOTTOM + BANNER_H)
	var l := at - right * HALF_WIDTH
	var r := at + right * HALF_WIDTH
	var quad := [l + lo, r + lo, r + hi, l + hi]
	var cols := HALF_WIDTH * 2.0 / (CHECK_M * 2.0)
	var uvs := [Vector2(0, 1), Vector2(cols, 1), Vector2(cols, 0),
		Vector2(0, 0)]
	for k in [0, 1, 2, 0, 2, 3]:
		banner.set_uv(uvs[k])
		banner.add_vertex(quad[k])
	for post in [l, r]:
		_box(posts, post + Vector3.UP * POST_H / 2.0,
			Vector3(POST_W, POST_H, POST_W))
	for side in [1.0, -1.0]:
		var label := Label3D.new()
		label.text = title
		label.font_size = 64
		label.pixel_size = LABEL_PIXEL
		label.modulate = BLACK if chequered else YELLOW
		label.outline_size = 12
		label.outline_modulate = WHITE if chequered else BLUE
		label.shaded = false
		label.double_sided = false
		label.visibility_range_end = LABEL_M
		# +Z of a label faces its reader: towards the oncoming traffic
		# on the near side, away from it on the far side
		label.transform = Transform3D(
			Basis.looking_at(forward * side, Vector3.UP),
			at + Vector3.UP * (BANNER_BOTTOM + BANNER_H + 0.55)
			- forward * side * 0.05)
		add_child(label)


func _box(tool: SurfaceTool, centre: Vector3, size: Vector3) -> void:
	var h := size / 2.0
	var c := [Vector3(-h.x, -h.y, -h.z), Vector3(h.x, -h.y, -h.z),
		Vector3(h.x, h.y, -h.z), Vector3(-h.x, h.y, -h.z),
		Vector3(-h.x, -h.y, h.z), Vector3(h.x, -h.y, h.z),
		Vector3(h.x, h.y, h.z), Vector3(-h.x, h.y, h.z)]
	for f in [[0, 1, 2, 3], [5, 4, 7, 6], [4, 0, 3, 7], [1, 5, 6, 2],
			[3, 2, 6, 7], [4, 5, 1, 0]]:
		for k in [0, 1, 2, 0, 2, 3]:
			tool.add_vertex(centre + c[f[k]])


func _commit(tool: SurfaceTool, mat: StandardMaterial3D) -> void:
	var node := MeshInstance3D.new()
	node.mesh = tool.commit()
	node.material_override = mat
	add_child(node)


static func _flat(colour: Color) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.albedo_color = colour
	return mat


## A 2 x 2 pixel chequer, repeated with hard edges.
static func _chequered() -> StandardMaterial3D:
	var image := Image.create(2, 2, false, Image.FORMAT_RGB8)
	image.set_pixel(0, 0, WHITE)
	image.set_pixel(1, 0, BLACK)
	image.set_pixel(0, 1, BLACK)
	image.set_pixel(1, 1, WHITE)
	var mat := _flat(WHITE)
	mat.albedo_texture = ImageTexture.create_from_image(image)
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	mat.texture_repeat = true
	return mat
