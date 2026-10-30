# file generated with AI assistance: Claude Code - 2026-10-26 16:13:04 UTC
extends Node3D
## The chosen route in the world: red chevrons on the road, pointing the
## way to drive, and a red and white chevron board across every road that
## leaves the route (side roads, the arms of crossings, the road straight
## on where the route turns), its chevrons pointing where the route goes.
##
## The band follows the route points like a road marking: lifted above
## the markings (0.02 m) and bridge decks, a flat strip with mitred
## corners; route points carry the road surface height, the tunnel floor
## lies below it. The chevrons are a texture repeating along the strip,
## so they follow every bend.
##
## The arms come from the road centre lines (roads.bin, road_index.gd):
## an edge with half of its samples within ON_M of the route is part of
## it; any other edge with an end within JOIN_M of the route (and DY_M in
## height, so not a bridge over it) is an arm, if that end lies within
## ON_M or points at the route (TOWARD). The pipeline cuts the drawn road
## ends back at junctions (pipeline/roads.py cut_back, up to 8 m beyond
## the half width), so the ends do not meet. The board stands on the arm
## where it is CLEAR_M from the route, across it, facing the junction.
## With a collision layer every board gets a box (drive mode).
##
## Before every curve of the route's pace notes (pace_notes.gd) stand
## pace note signs, built by signs.gd, upright: the grade, 1 to 6 or H
## for a hairpin, above a bent arrow the way the curve goes; white for
## grades 4 to 6, yellow for 2 and 3, red for 1 and hairpin (SIGN_KINDS),
## SIGN_SCALE times a signpost line. A curve linked "into" the next shows
## both pairs on one sign, in driving order, coloured by the tighter.
## Every curve gets two signs, at SIGN_AHEAD_M before it, one after the
## other, both SIGN_SIDE_M from the route on the outside of the curve
## (left of a right curve, right of a left curve). A
## sign stands at least SIGN_AFTER_M past the previous curve (the
## nearest moves closer, the others are left out) and SIGN_MIN_M before
## its own, else there is none. Signs have no collision.
##
## The chevron band on the road is hidden unless show_band(true): it
## helps in a town, where the route turns at junctions, more than on a
## country road (world.gd toggles it with G).

const HALF_WIDTH := 1.0
const LIFT := 0.08
## mitre limit: the band widens at most this much at a sharp turn
const MITRE_MAX := 2.0
## one ground chevron every PERIOD_M; the ends of a chevron lie SWEEP of
## a period behind its tip, INK of a period is red
const PERIOD_M := 4.0
const SWEEP := 0.35
const INK := 0.2
const JOIN_M := 15.0
const DY_M := 4.0
const ON_M := 3.0
## progress() finds the car on the route up to this far from it
const OFF_ROUTE_M := 30.0
const TOWARD := 0.5
const CLEAR_M := 7.0
## the board is looked for this far along the arm
const LOOK_M := 30.0
## boards closer than this to one already placed are left out
const BOARD_GAP_M := 3.0
## the chevrons point to the route this far beyond the junction
const AHEAD_M := 25.0
const BOARD_W := 7.0
## arms whose boards stand this close form one junction
const CONNECT_M := 32.0
## an arm shorter than this and with another board close by is fenced in
## by the barrier around it and gets none of its own
const SHORT_M := 60.0
## the route's probe either side of a junction, for the gap in the arc
const ROUTE_PROBE_M := 14.0
## no arc around more than this
const ARC_MAX := 2.7
const ARC_STEP_M := 2.0
## the advertising band on top of the chevron band
const AD_BOTTOM := 1.0
const AD_H := 0.65
const AD_W := 3.4
const AD_PIXEL := 0.011
const AD_TEXT_M := 200.0
## fake brands (oil, tyres), text colour and background
const ADS := [["ZEDRA OIL", Color(1, 1, 1), Color(0.0, 0.45, 0.2)],
	["TYREX", Color(1.0, 0.9, 0.1), Color(0.05, 0.2, 0.7)],
	["VOLTURA LUBE", Color(1, 1, 1), Color(0.7, 0.08, 0.08)],
	["GRIPTON PNEUS", Color(1, 1, 1), Color(0.0, 0.35, 0.65)],
	["OCTANE MAX", Color(1.0, 0.85, 0.0), Color(0.08, 0.08, 0.08)],
	["ROTOLO TYRES", Color(0.05, 0.25, 0.65), Color(0.97, 0.97, 0.95)],
	["BARDOS MOTOROIL", Color(1.0, 0.9, 0.1), Color(0.0, 0.4, 0.2)],
	["MAXGRIP", Color(1, 1, 1), Color(0.9, 0.4, 0.0)]]
const BOARD_H := 0.5
const BOARD_BOTTOM := 0.5
const BOARD_PERIOD_M := 1.25
const BOARD_SWEEP := 0.2
const BOARD_INK := 0.45
const BOARD_DEPTH := 0.08
const POST_W := 0.1
const CELL_M := 25.0
const TEX_SIZE := Vector2i(256, 64)
const RED := Color(0.85, 0.08, 0.06)
const WHITE := Color(0.95, 0.95, 0.93)
const POST := Color(0.55, 0.56, 0.58)
const PACE_NOTES := preload("res://scripts/pace_notes.gd")
const SIGNS := preload("res://scripts/signs.gd")
## signs.gd kind of a pace note sign by grade (0 = hairpin)
const SIGN_KINDS := ["pace_tight", "pace_tight", "pace_sharp",
	"pace_sharp", "pace", "pace", "pace"]
## the two signs of a curve, nearest first
const SIGN_AHEAD_M := [50.0, 100.0]
const SIGN_AFTER_M := 10.0
const SIGN_MIN_M := 15.0
const SIGN_SIDE_M := 6.0
const SIGN_SCALE := 1.6
## panel bottom before scaling: 1.15 m above the road
const SIGN_BOTTOM := 0.6

## the route's pace notes (pace_notes.gd), for the co-driver
var notes: Array[Dictionary] = []
var signs := 0
var _band: MeshInstance3D

var _pts: Array[Vector3] = []
## route point index -> distance along the route
var _along := PackedFloat32Array()
## cell -> segment indices, each segment in its cells and their neighbours
var _cells := {}
## the backs of boards and signs and their posts, one grey mesh
var _backs := SurfaceTool.new()
var _back_count := 0
## ad band quads by ADS index, and the ads placed so far
var _ad_faces := {}
var _ad_count := 0


## Builds the band of `points` (route points [x, y, z]), the curve signs
## and, with `roads` (road_index.gd, or null), the boards; `layer` is the
## collision layer of the boards, 0 for none. Returns the number of
## boards; `notes` and `signs` hold the pace notes and the sign count.
func build(points: Array, roads: RefCounted, layer: int) -> int:
	for p: Array in points:
		_pts.append(Vector3(p[0], p[1], p[2]))
	if _pts.size() < 2:
		return 0
	_along.resize(_pts.size())
	_along[0] = 0.0
	for i in range(1, _pts.size()):
		_along[i] = _along[i - 1] + _flat(_pts[i] - _pts[i - 1]).length()
	_add_band()
	_backs.begin(Mesh.PRIMITIVE_TRIANGLES)
	notes = PACE_NOTES.analyse(points)
	signs = _add_signs()
	var boards := 0
	if roads != null:
		_index()
		boards = _add_boards(roads.edge_lines(), layer)
	if _back_count > 0:
		_commit(_backs, _material(null, POST))
	return boards


func _add_band() -> void:
	var dirs: Array[Vector3] = []
	var last := Vector3.RIGHT
	for i in _pts.size() - 1:
		var d := _flat(_pts[i + 1] - _pts[i])
		if d.length() > 0.001:
			last = d.normalized()
		dirs.append(last)
	dirs.append(last)
	var mesh := ImmediateMesh.new()
	var band := StandardMaterial3D.new()
	band.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	band.albedo_texture = chevron_texture(SWEEP, INK, Color(RED, 0.0))
	band.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	band.texture_filter = \
		BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	band.cull_mode = BaseMaterial3D.CULL_DISABLED
	mesh.surface_begin(Mesh.PRIMITIVE_TRIANGLE_STRIP, band)
	for i in _pts.size():
		var d_out := dirs[i]
		var d: Vector3 = d_out if i == 0 else dirs[i - 1] + d_out
		d = d_out if d.length() < 0.001 else d.normalized()
		var side := Vector3(-d.z, 0.0, d.x) * HALF_WIDTH \
			* minf(1.0 / maxf(d.dot(d_out), 0.001), MITRE_MAX)
		var at := _pts[i] + Vector3.UP * LIFT
		var u := _along[i] / PERIOD_M
		mesh.surface_set_uv(Vector2(u, 0.0))
		mesh.surface_add_vertex(at - side)
		mesh.surface_set_uv(Vector2(u, 1.0))
		mesh.surface_add_vertex(at + side)
	mesh.surface_end()
	_band = MeshInstance3D.new()
	_band.mesh = mesh
	_band.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_band.visible = false
	add_child(_band)


## Shows or hides the chevron band on the road.
func show_band(on: bool) -> void:
	if _band != null:
		_band.visible = on


## A texture of chevron stripes: u runs along the stripes (one chevron
## per unit), each chevron points to +u, its ends `sweep` behind its tip,
## `ink` of a unit red, the rest `ground`.
static func chevron_texture(sweep: float, ink: float,
		ground: Color) -> ImageTexture:
	var image := Image.create(TEX_SIZE.x, TEX_SIZE.y, false,
		Image.FORMAT_RGBA8)
	for y in TEX_SIZE.y:
		var v := (y + 0.5) / TEX_SIZE.y
		for x in TEX_SIZE.x:
			var u := (x + 0.5) / TEX_SIZE.x
			var red := fposmod(u + sweep * absf(v - 0.5) * 2.0, 1.0) < ink
			image.set_pixel(x, y, RED if red else ground)
	image.generate_mipmaps()
	return ImageTexture.create_from_image(image)


func _index() -> void:
	for i in _pts.size() - 1:
		var a := _pts[i]
		var b := _pts[i + 1]
		for cx in range(floori(minf(a.x, b.x) / CELL_M) - 1,
				floori(maxf(a.x, b.x) / CELL_M) + 2):
			for cz in range(floori(minf(a.z, b.z) / CELL_M) - 1,
					floori(maxf(a.z, b.z) / CELL_M) + 2):
				var key := Vector2i(cx, cz)
				if not _cells.has(key):
					_cells[key] = PackedInt32Array()
				_cells[key].append(i)


## The route segment nearest to `p` in x/z among those within DY_M in
## height: [horizontal distance, segment index, nearest point]; the
## distance is INF when no segment lies within a cell.
func _nearest(p: Vector3) -> Array:
	var key := Vector2i(floori(p.x / CELL_M), floori(p.z / CELL_M))
	var best: Array = [INF, -1, p]
	for i: int in _cells.get(key, PackedInt32Array()):
		var a := _pts[i]
		var d := _pts[i + 1] - a
		var flat := _flat(d)
		var t := 0.0
		if flat.length_squared() > 0.0:
			t = clampf(_flat(p - a).dot(flat) / flat.length_squared(),
				0.0, 1.0)
		var q := a + d * t
		if absf(q.y - p.y) > DY_M:
			continue
		var h := _flat(p - q).length()
		if h < best[0]:
			best = [h, i, q]
	return best


## The distance along the route (x/z, the scale of the pace notes'
## start_m) of the route point nearest to `p`, -1 where `p` is not within
## OFF_ROUTE_M of the route.
func progress(p: Vector3) -> float:
	var near := _nearest(p)
	if near[1] < 0 or near[0] > OFF_ROUTE_M:
		return -1.0
	return _along[near[1]] + _flat(near[2] - _pts[near[1]]).length()


func _add_boards(lines: Array[PackedVector3Array], layer: int) -> int:
	var faces := SurfaceTool.new()
	faces.begin(Mesh.PRIMITIVE_TRIANGLES)
	var body: StaticBody3D = null
	if layer != 0:
		body = StaticBody3D.new()
		body.collision_layer = layer
		body.collision_mask = 0
		add_child(body)
	var cands: Array[Dictionary] = []
	for line in lines:
		if _on_route(line):
			continue
		var length := 0.0
		for k in range(1, line.size()):
			length += line[k].distance_to(line[k - 1])
		for reverse in [false, true]:
			var board := _board(line, reverse)
			if board.is_empty():
				continue
			var at: Vector3 = board[0]
			var dup := false
			for c in cands:
				if _flat(c.at - at).length() < BOARD_GAP_M:
					dup = true
			if not dup:
				cands.append({"at": at, "away": board[1],
					"across": board[2], "node": board[3], "short":
					length < SHORT_M})
	# a short road next to another board is fenced in by the barrier
	var kept: Array[Dictionary] = []
	for c in cands:
		var covered := false
		if c.short:
			for d in cands:
				if d != c and _flat(d.at - c.at).length() < CONNECT_M:
					covered = true
		if not covered:
			kept.append(c)
	var count := 0
	for c in kept:
		_add_board(faces, body, c.at, c.away, c.across)
		count += 1
	count += _add_arcs(kept, faces, body)
	if count == 0:
		if body != null:
			body.queue_free()
		return 0
	_commit(faces, _material(chevron_texture(BOARD_SWEEP, BOARD_INK,
		WHITE), WHITE))
	for key: int in _ad_faces:
		_commit(_ad_faces[key], _material(null, ADS[key][2]))
	return count


## Joins the boards of one junction into a barrier: between two boards
## next to each other around the junction a quarter circle (or what the
## angle gives) from the end of one to the end of the other, on the side
## away from the route. Returns the number of arcs.
func _add_arcs(boards: Array[Dictionary], faces: SurfaceTool,
		body: StaticBody3D) -> int:
	var groups: Array = []
	var seen := {}
	for i in boards.size():
		if seen.has(i):
			continue
		var group: Array[int] = [i]
		seen[i] = true
		var k := 0
		while k < group.size():
			for j in boards.size():
				if not seen.has(j) and _flat(boards[j].at
						- boards[group[k]].at).length() < CONNECT_M:
					seen[j] = true
					group.append(j)
			k += 1
		if group.size() > 1:
			groups.append(group)
	var arcs := 0
	for group: Array in groups:
		var centre := Vector3.ZERO
		var route_angles: Array[float] = []
		for i: int in group:
			centre += boards[i].node[2] / group.size()
		for i: int in group:
			var along: float = _along[boards[i].node[1]]
			for d in [-ROUTE_PROBE_M, ROUTE_PROBE_M]:
				var q: Vector3 = _place(along + d)[0]
				route_angles.append(_angle(q - centre))
		var order := group.duplicate()
		order.sort_custom(func(a: int, b: int) -> bool:
			return _angle(boards[a].at - centre) \
				< _angle(boards[b].at - centre))
		var n := order.size()
		for k in n:
			var a: Dictionary = boards[order[k]]
			var b: Dictionary = boards[order[(k + 1) % n]]
			var from := _angle(a.at - centre)
			var span := fposmod(_angle(b.at - centre) - from, TAU)
			var blocked := false
			for r in route_angles:
				if fposmod(r - from, TAU) < span:
					blocked = true
			if blocked or span > ARC_MAX:
				continue
			arcs += _arc(a, b, centre, faces, body)
	return arcs


func _angle(v: Vector3) -> float:
	return fposmod(atan2(v.z, v.x), TAU)


## The barrier from the counter-clockwise end of board `a` to the
## clockwise end of board `b`, around `centre`.
func _arc(a: Dictionary, b: Dictionary, centre: Vector3,
		faces: SurfaceTool, body: StaticBody3D) -> int:
	var ends := []
	for pair in [[a, 1.0], [b, -1.0]]:
		var board: Dictionary = pair[0]
		var best: Vector3 = board.at
		var base := _angle(board.at - centre)
		for sgn in [-1.0, 1.0]:
			var e: Vector3 = board.at + board.across * sgn * BOARD_W / 2.0
			if fposmod((_angle(e - centre) - base) * pair[1], TAU) < PI:
				best = e
		ends.append(best)
	var start: Vector3 = ends[0]
	var finish: Vector3 = ends[1]
	var a0 := _angle(start - centre)
	var span := fposmod(_angle(finish - centre) - a0, TAU)
	if span > ARC_MAX or span < 0.05:
		return 0
	var r0 := _flat(start - centre).length()
	var r1 := _flat(finish - centre).length()
	var steps := maxi(2, ceili(span * maxf(r0, r1) / ARC_STEP_M))
	var pts: Array[Vector3] = []
	for k in steps + 1:
		var t := float(k) / steps
		var ang := a0 + span * t
		var p := centre + Vector3(cos(ang), 0.0, sin(ang)) \
			* lerpf(r0, r1, t)
		p.y = lerpf(start.y, finish.y, t)
		pts.append(p)
	# the chevrons point to where the route goes
	var mid: Vector3 = pts[steps / 2]
	var forward := _flat(pts[mini(steps / 2 + 1, steps)] - mid)
	var ahead := _flat(_ahead(a.node[1], a.node[2]) - mid)
	var reverse := forward.dot(ahead) < 0.0
	var u := 0.0
	for k in steps:
		var p: Vector3 = pts[k]
		var q: Vector3 = pts[k + 1]
		var d := _flat(q - p)
		var len := d.length()
		if len < 0.01:
			continue
		var along_dir := d / len
		var radial := Vector3(along_dir.z, 0.0, -along_dir.x)
		if radial.dot(_flat(p - centre)) < 0.0:
			radial = -radial
		var mid_p := (p + q) / 2.0
		var u0 := u / BOARD_PERIOD_M
		var u1 := (u + len) / BOARD_PERIOD_M
		if reverse:
			u0 = -u0
			u1 = -u1
		_panel(faces, mid_p, along_dir, radial, -len / 2.0, len / 2.0,
			BOARD_BOTTOM, BOARD_BOTTOM + BOARD_H, u0, u1)
		u += len
		_post(mid_p + radial * BOARD_DEPTH * 2.0,
			AD_BOTTOM + AD_H)
		if body != null:
			var shape := CollisionShape3D.new()
			var box := BoxShape3D.new()
			box.size = Vector3(len + 0.2, AD_BOTTOM + AD_H, 0.3)
			shape.shape = box
			shape.transform = Transform3D(
				Basis(along_dir, Vector3.UP, radial), mid_p
				+ Vector3.UP * (AD_BOTTOM + AD_H) / 2.0
				+ radial * BOARD_DEPTH)
			body.add_child(shape)
	# ads along the arc, one per AD_W, on its chord pieces
	var total := u
	var pieces := maxi(1, floori(total / AD_W))
	var piece := total / pieces
	for m in pieces:
		var s0 := piece * m
		var s1 := s0 + piece
		var p0 := _arc_point(pts, s0)
		var p1 := _arc_point(pts, s1)
		var d := _flat(p1 - p0)
		if d.length() < 0.01:
			continue
		var dir := d.normalized()
		var radial := Vector3(dir.z, 0.0, -dir.x)
		if radial.dot(_flat(p0 - centre)) < 0.0:
			radial = -radial
		_ad((p0 + p1) / 2.0, dir, radial, d.length())
	return 1


## The point `along` metres along the polyline `pts`.
func _arc_point(pts: Array[Vector3], along: float) -> Vector3:
	var walked := 0.0
	for k in range(1, pts.size()):
		var len := _flat(pts[k] - pts[k - 1]).length()
		if walked + len >= along:
			return pts[k - 1].lerp(pts[k], (along - walked) / maxf(len, 0.001))
		walked += len
	return pts[pts.size() - 1]


## One ad on top of the chevron band: a coloured quad `width` wide
## centred on `at`, along `right`, its back towards `behind`, with the
## brand as a Label3D.
func _ad(at: Vector3, right: Vector3, behind: Vector3, width: float) -> void:
	var ad: Array = ADS[_ad_count % ADS.size()]
	var key := _ad_count % ADS.size()
	_ad_count += 1
	if not _ad_faces.has(key):
		var fresh := SurfaceTool.new()
		fresh.begin(Mesh.PRIMITIVE_TRIANGLES)
		_ad_faces[key] = fresh
	var tool: SurfaceTool = _ad_faces[key]
	var lo := Vector3.UP * AD_BOTTOM
	var hi := Vector3.UP * (AD_BOTTOM + AD_H)
	var quad := [at - right * width / 2.0 + lo, at + right * width / 2.0 + lo,
		at + right * width / 2.0 + hi, at - right * width / 2.0 + hi]
	for k in [0, 1, 2, 0, 2, 3]:
		tool.add_vertex(quad[k])
	for k in [0, 2, 1, 0, 3, 2]:
		_backs.add_vertex(quad[k] + behind * BOARD_DEPTH)
	_back_count += 1
	var label := Label3D.new()
	label.text = ad[0]
	label.font_size = 64
	label.pixel_size = AD_PIXEL
	label.modulate = ad[1]
	label.outline_size = 0
	label.shaded = false
	label.double_sided = false
	label.visibility_range_end = AD_TEXT_M
	label.transform = Transform3D(Basis.looking_at(behind, Vector3.UP),
		at + Vector3.UP * (AD_BOTTOM + AD_H / 2.0) - behind * 0.01)
	add_child(label)


## An unshaded material, both sides, with `texture` or in `colour`.
static func _material(texture: Texture2D,
		colour: Color) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	if texture == null:
		mat.albedo_color = colour
	else:
		mat.albedo_texture = texture
		mat.texture_filter = \
			BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	return mat


func _commit(tool: SurfaceTool, mat: StandardMaterial3D) -> void:
	var node := MeshInstance3D.new()
	node.mesh = tool.commit()
	node.material_override = mat
	add_child(node)


## A panel facing away from `behind`: the quad from `at` + right * x0 to
## `at` + right * x1, `bottom` to `top` above `at`, u running from u0 to
## u1 along it (chevrons point to growing u); its back, BOARD_DEPTH
## further along `behind`, goes into the grey mesh.
func _panel(faces: SurfaceTool, at: Vector3, right: Vector3,
		behind: Vector3, x0: float, x1: float, bottom: float, top: float,
		u0: float, u1: float) -> void:
	var lo := Vector3.UP * bottom
	var hi := Vector3.UP * top
	var quad := [at + right * x0 + lo, at + right * x1 + lo,
		at + right * x1 + hi, at + right * x0 + hi]
	var uvs := [Vector2(u0, 1), Vector2(u1, 1), Vector2(u1, 0),
		Vector2(u0, 0)]
	for k in [0, 1, 2, 0, 2, 3]:
		faces.set_uv(uvs[k])
		faces.add_vertex(quad[k])
	for k in [0, 2, 1, 0, 3, 2]:
		_backs.add_vertex(quad[k] + behind * BOARD_DEPTH)
	_back_count += 1


## A post from the ground at `foot` up to `height`, into the grey mesh.
func _post(foot: Vector3, height: float) -> void:
	_box(_backs, foot + Vector3.UP * height / 2.0,
		Vector3(POST_W, height, POST_W))
	_back_count += 1


func _on_route(line: PackedVector3Array) -> bool:
	var near := 0
	for p in line:
		if _nearest(p)[0] < ON_M:
			near += 1
	return near * 2 >= line.size()


## The board of the arm `line` at its first end (last with `reverse`):
## [position, direction along the arm away from the route, direction the
## chevrons point, nearest route point (_nearest)], empty if that end is
## no arm.
func _board(line: PackedVector3Array, reverse: bool) -> Array:
	var seq := line.duplicate()
	if reverse:
		seq.reverse()
	if seq.size() < 2:
		return []
	var end: Array = _nearest(seq[0])
	if end[0] > JOIN_M:
		return []
	var out := _flat(seq[0] - seq[1]).normalized()
	if end[0] > ON_M and out.dot(_flat(end[2] - seq[0]).normalized()) \
			< TOWARD:
		return []
	var walked := 0.0
	for k in seq.size():
		if k > 0:
			walked += seq[k].distance_to(seq[k - 1])
		if walked > LOOK_M:
			return []
		if _nearest(seq[k])[0] < CLEAR_M:
			continue
		var away := _flat(seq[k] - seq[maxi(k - 1, 0)] if k > 0
			else seq[1] - seq[0]).normalized()
		var across := Vector3(-away.z, 0.0, away.x)
		if across.dot(_ahead(end[1], end[2]) - seq[k]) < 0.0:
			across = -across
		return [seq[k], away, across, end]
	return []


## The route point AHEAD_M beyond point `at` on segment `index`.
func _ahead(index: int, at: Vector3) -> Vector3:
	var goal := _along[index] + _flat(at - _pts[index]).length() + AHEAD_M
	var i := index + 1
	while i < _pts.size() - 1 and _along[i] < goal:
		i += 1
	return _pts[i]


## A board at `at` across the arm (`away` from the route), chevrons
## pointing along `across`, its face towards the junction, on two posts.
func _add_board(faces: SurfaceTool, body: StaticBody3D, at: Vector3,
		away: Vector3, across: Vector3) -> void:
	var top := AD_BOTTOM + AD_H
	_panel(faces, at, across, away, -BOARD_W / 2.0, BOARD_W / 2.0,
		BOARD_BOTTOM, BOARD_BOTTOM + BOARD_H, 0.0,
		BOARD_W / BOARD_PERIOD_M)
	_ad(at, across, away, BOARD_W - 2.0 * POST_W)
	var back := away * BOARD_DEPTH
	var hi := Vector3.UP * top
	for side in [-1.0, 1.0]:
		_post(at + across * side * (BOARD_W / 2.0 - POST_W) + back * 2.0,
			top)
	if body == null:
		return
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(BOARD_W, hi.y, 0.3)
	shape.shape = box
	shape.transform = Transform3D(Basis(across, Vector3.UP, away),
		at + hi / 2.0 + back)
	body.add_child(shape)


## The pace note signs of `notes`; returns their number.
func _add_signs() -> int:
	var data := []
	var i := 0
	while i < notes.size():
		var note := notes[i]
		var lines := _sign_lines(note)
		var tightest: int = note.grade
		var next := i + 1
		if note.link == "into" and next < notes.size():
			lines += _sign_lines(notes[next])
			tightest = mini(tightest, notes[next].grade)
			next += 1
		var after: float = notes[i - 1].end_m + SIGN_AFTER_M if i > 0 \
			else 0.0
		# on the outside of the curve: left of a right curve and vice versa
		var side := -1.0 if note.dir == "right" else 1.0
		# farthest first, so the signs stand in driving order
		for k in range(SIGN_AHEAD_M.size() - 1, -1, -1):
			var at: float = note.start_m - SIGN_AHEAD_M[k]
			if at < after:
				if k > 0:
					continue
				at = after
			if note.start_m - at >= SIGN_MIN_M:
				data.append(_sign(at, side, lines, SIGN_KINDS[tightest]))
		i = next
	if data.is_empty():
		return 0
	var node := Node3D.new()
	node.set_script(SIGNS)
	add_child(node)
	return node.load_signs({"signs": data})


## The sign lines of a note: its grade (H for a hairpin) above a bent
## arrow the way it turns (signs.gd draws "@curve_*" as geometry).
static func _sign_lines(note: Dictionary) -> Array:
	return ["H" if note.grade == 0 else str(note.grade),
		"@curve_" + str(note.dir)]


## A signs.gd sign `along` metres into the route, SIGN_SIDE_M to its
## right (`side` 1) or left (-1), facing the traffic.
func _sign(along: float, side: float, lines: Array,
		kind: String) -> Dictionary:
	var place := _place(along)
	var forward: Vector3 = place[1]
	var at: Vector3 = place[0] \
		+ Vector3(-forward.z, 0.0, forward.x) * SIGN_SIDE_M * side
	return {"pos": [at.x, at.y, at.z], "face": [-forward.x, -forward.z],
		"kind": kind, "lines": lines, "scale": SIGN_SCALE,
		"bottom": SIGN_BOTTOM}


## The route point `along` metres into the route (x/z) and the horizontal
## direction there: [point, direction].
func _place(along: float) -> Array:
	var i := 0
	while i < _pts.size() - 2 and _along[i + 1] < along:
		i += 1
	var length := _along[i + 1] - _along[i]
	var t := 0.0 if length <= 0.0 else clampf((along - _along[i]) / length,
		0.0, 1.0)
	var d := _flat(_pts[i + 1] - _pts[i])
	return [_pts[i].lerp(_pts[i + 1], t),
		d.normalized() if d.length() > 0.001 else Vector3.FORWARD]


## An axis-aligned box of `size` around `centre`.
func _box(tool: SurfaceTool, centre: Vector3, size: Vector3) -> void:
	var h := size / 2.0
	for axis in 3:
		for sign in [-1.0, 1.0]:
			var n := Vector3.ZERO
			n[axis] = sign
			var a := Vector3.ZERO
			a[(axis + 1) % 3] = 1.0
			var b := Vector3.ZERO
			b[(axis + 2) % 3] = 1.0
			var c := centre + n * h
			var corners := [c - a * h - b * h, c + a * h - b * h,
				c + a * h + b * h, c - a * h + b * h]
			for k in [0, 1, 2, 0, 2, 3]:
				tool.add_vertex(corners[k])


static func _near_any(points: Array[Vector3], at: Vector3,
		radius: float) -> bool:
	for q in points:
		if q.distance_to(at) < radius:
			return true
	return false


static func _flat(v: Vector3) -> Vector3:
	return Vector3(v.x, 0.0, v.z)
# - revised 2026-10-26 (curve signs from the pace notes)
# - revised 2026-10-26 (pace note signs with grade, band hidden by default)
# - revised 2026-10-26 (upright signs, two or three per curve, sides by turns)
