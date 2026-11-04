# file generated with AI assistance: Claude Code - 2026-10-23 21:00:00 UTC
extends Node3D
## Direction signs of pipeline/signs.py (signs.json): a post, a panel in
## the colour of its kind and one Label3D per line, facing the traffic.
## The kind follows the road the sign stands on and the country
## (pipeline/signs.py); `town` signs take TOWN_STYLE of the country.
## motorway: blue, white text; federal (Bundesstraße): yellow, black
## text; primary (French N/T roads): green, white text; local: white,
## black text. Cyprus (COUNTRY_COLOURS): motorway green, primary blue,
## both with white text; a line with tone `el` (signs.json `tones`, the
## Greek line of a bilingual pair) takes the third colour of its kind
## when there is one, yellow on the motorway panels. The ref goes in
## front of the first line. Text shows up
## to TEXT_M, the panel up to PANEL_M; signs have no collision. A sign
## with `gantry` hangs on a gantry over the carriageway: two posts, a
## beam, one panel per lane group (GANTRY_*). Panels
## are unshaded (retroreflective sheeting reads in its own colour), a
## line about 0.45 m high, roughly the size of a real signpost. A line
## starting with an arrow (↑ ← →, from the plain signs) gets the arrow as
## geometry in the text colour, because the built-in font has no arrow
## glyphs. A sign may carry `scale` (the whole sign, default 1) and
## `bottom` (panel bottom before scaling, default PANEL_BOTTOM): the pace
## note signs of route_marks.gd are larger and lower than a signpost.
## Every panel but the town signs is framed: rounded corners and a
## border in the text colour, FRAME_MARGIN inside the edge, so a thin rim
## of the panel colour stays outside it; the text is centred on the
## panel, an arrow sits left of it, and the padding is split above and
## below the lines. `"style": "plain"` in the data draws the square
## panels of before (tools/render_props.gd compares them). Every panel
## shows its colour on the front only: back and edges are bare metal in
## the grey of the posts (_slab()).
## Pace note signs (kinds starting with "pace") have their own layout:
## per grade and curve pair a column PACE_W wide, the grade large at
## PACE_GRADE_Y of the height above the bent arrow at PACE_CURVE_Y.

const PANEL_BOTTOM := 2.2
const LINE_H := 0.62
const CHAR_W := 0.27
const PAD := 0.35
const DEPTH := 0.06
const POST_RADIUS := 0.06
const TEXT_M := 250.0
const PANEL_M := 1500.0
const FONT_SIZE := 64
const PIXEL := 0.0075
const COLOURS := {
	"motorway": [Color(0.0, 0.29, 0.63), Color.WHITE],
	"federal": [Color(1.0, 0.8, 0.0), Color(0.05, 0.05, 0.05)],
	"primary": [Color(0.0, 0.42, 0.24), Color.WHITE],
	"local": [Color(0.95, 0.95, 0.93), Color(0.05, 0.05, 0.05)],
	# pace note signs of the chosen route (route_marks.gd) by how tight
	# the curve is: grades 4 to 6, 2 and 3, 1 and hairpin
	"pace": [Color(0.95, 0.95, 0.93), Color(0.05, 0.05, 0.05)],
	"pace_sharp": [Color(1.0, 0.8, 0.0), Color(0.05, 0.05, 0.05)],
	"pace_tight": [Color(0.8, 0.08, 0.06), Color(0.97, 0.97, 0.96)]}
## kinds whose colours differ by country: panel, text, Greek text
const COUNTRY_COLOURS := {
	"cy": {
		"motorway": [Color(0.0, 0.42, 0.24), Color.WHITE,
			Color(1.0, 0.82, 0.0)],
		"primary": [Color(0.0, 0.29, 0.63), Color.WHITE]}}
const POST := Color(0.55, 0.56, 0.58)
## the surfaces of a panel (_slab())
const SLAB_FRONT := 0
const SLAB_BACK := 1
## town signs by country: panel, border, text. Germany: Ortstafel, yellow
## with a black border; France: panneau d'entrée, white with a red
## border, the name in capitals; Cyprus: white with a black border, Greek
## over Latin
const TOWN_STYLE := {
	"de": [Color(1.0, 0.8, 0.0), Color(0.05, 0.05, 0.05),
		Color(0.05, 0.05, 0.05)],
	"fr": [Color(0.97, 0.97, 0.96), Color(0.8, 0.08, 0.08),
		Color(0.05, 0.05, 0.05)],
	"cy": [Color(0.97, 0.97, 0.96), Color(0.05, 0.05, 0.05),
		Color(0.05, 0.05, 0.05)]}
const TOWN_BOTTOM := 1.4
const BORDER := 0.12
## panels wider than this stand on two posts, POST_INSET from the ends
const TWO_POSTS_W := 2.2
const POST_INSET := 0.35

const ARROWS := {"↑": 0.0, "←": PI / 2.0, "→": -PI / 2.0}
## gantries (signs.json `gantry`): clearance under the panels, posts this
## far beyond the carriageway edge, the beam behind the panels
const GANTRY_CLEAR := 5.0
const GANTRY_SIDE := 1.2
const GANTRY_TEXT_M := 400.0
const BEAM_H := 0.4
const BEAM_DEPTH := 0.3
## gantry posts this many times as thick as a sign post (0.3 m across)
const GANTRY_POST := 2.5
const ARROW_W := 0.42
## A line "@curve_right" or "@curve_left" is a bent arrow drawn as
## geometry, CURVE_H high (pace note signs); the widest line it counts as
## CURVE_CHARS characters.
const CURVE_PREFIX := "@curve_"
const CURVE_H := 1.1
const CURVE_CHARS := 2
const CURVE_STROKE := 0.17
const FRAME_W := 0.05
const FRAME_MARGIN := 0.025
const FRAME_R := 0.1
const FRAME_STEPS := 4
## pace note panel: size per pair, grade and arrow centres (share of the
## height), grade glyph size, arrow scale
const PACE_W := 1.24
const PACE_H := 2.07
const PACE_GRADE_Y := 0.73
const PACE_CURVE_Y := 0.28
const PACE_PIXEL := 0.0155
const PACE_CURVE_SCALE := 0.74

var _materials := {}
var _country := "de"
var _post_mesh := CylinderMesh.new()
var _arrow_mesh: ArrayMesh
var _curve_mesh: ArrayMesh
var _framed := false


## Adds every sign of `data` (the parsed signs.json); returns the count.
func load_signs(data: Dictionary) -> int:
	_post_mesh.top_radius = POST_RADIUS
	_post_mesh.bottom_radius = POST_RADIUS
	# one unit high: _post() scales it to the post height in metres (the
	# default of 2 made every post twice as tall, poking out on top)
	_post_mesh.height = 1.0
	_post_mesh.radial_segments = 6
	_post_mesh.rings = 0
	_arrow_mesh = _make_arrow()
	_curve_mesh = _make_curve()
	_country = str(data.get("country", "de"))
	_framed = str(data.get("style", "framed")) == "framed"
	var count := 0
	for sign: Dictionary in data.get("signs", []):
		_add(sign)
		count += 1
	return count


func _add(sign: Dictionary) -> void:
	var p: Array = sign.pos
	var f: Array = sign.face
	var face := Vector3(f[0], 0.0, f[1]).normalized()
	var colours: Array = COUNTRY_COLOURS.get(_country, {}).get(sign.kind,
		COLOURS.get(sign.kind, COLOURS["local"]))
	var root := Node3D.new()
	root.position = Vector3(p[0], p[1], p[2])
	# +Z of the sign points at the traffic, +X to the driver's right
	root.basis = Basis.looking_at(-face, Vector3.UP)
	root.scale = Vector3.ONE * float(sign.get("scale", 1.0))
	add_child(root)
	if sign.has("gantry"):
		_add_gantry(root, sign.gantry, colours)
		return
	var lines: Array = sign.lines
	var bottom := float(sign.get("bottom", PANEL_BOTTOM))
	if sign.kind == "town":
		var style: Array = TOWN_STYLE.get(_country, TOWN_STYLE["de"])
		colours = [style[0], style[2]]
		bottom = TOWN_BOTTOM
		if _country == "fr":
			lines = lines.map(func(l: String) -> String: return l.to_upper())
	var size: Vector2
	if str(sign.kind).begins_with("pace"):
		size = _pace_panel(root, bottom, lines, colours)
	else:
		size = _panel(root, 0.0, bottom, lines, str(sign.get("ref", "")),
			colours, 0.0, TEXT_M, sign.get("tones", []),
			_framed and sign.kind != "town")
	if sign.kind == "town":
		_border(root, size, bottom, TOWN_STYLE.get(_country,
			TOWN_STYLE["de"])[1])
	# the pipeline puts the panel beside the road (pos = its centre); a
	# wide panel stands on two posts
	if size.x > TWO_POSTS_W:
		for x in [-size.x / 2.0 + POST_INSET, size.x / 2.0 - POST_INSET]:
			_post(root, x, bottom + size.y, -DEPTH)
	else:
		_post(root, 0.0, bottom + size.y, -DEPTH)


## A frame of `colour` around a panel of `size` (a plate behind it).
func _border(root: Node3D, size: Vector2, bottom: float,
		colour: Color) -> void:
	var plate := _slab_instance(_square_panel(size.x + 2.0 * BORDER,
		size.y + 2.0 * BORDER), colour)
	plate.position = Vector3(0.0, bottom + size.y / 2.0, -DEPTH * 0.6)
	plate.visibility_range_end = PANEL_M
	root.add_child(plate)


## A gantry over the carriageway: posts GANTRY_SIDE beyond both edges, a
## beam behind the panels, every panel over its lanes with its bottom at
## GANTRY_CLEAR above the road.
func _add_gantry(root: Node3D, gantry: Dictionary, colours: Array) -> void:
	var tallest := 0.0
	for panel: Dictionary in gantry.panels:
		var size := _panel(root, panel.offset, GANTRY_CLEAR, panel.lines,
			str(panel.get("ref", "")), colours,
			maxf(float(panel.span) - 0.3, 0.0), GANTRY_TEXT_M,
			panel.get("tones", []), _framed)
		tallest = maxf(tallest, size.y)
	var side: float = float(gantry.half) + GANTRY_SIDE
	var top := GANTRY_CLEAR + tallest
	for x in [-side, side]:
		_post(root, x, top, -BEAM_DEPTH, GANTRY_POST)
	var beam := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(2.0 * side, BEAM_H, BEAM_DEPTH)
	beam.mesh = box
	beam.position = Vector3(0.0, top - BEAM_H, -BEAM_DEPTH)
	beam.material_override = _material(POST)
	beam.visibility_range_end = PANEL_M
	root.add_child(beam)


## A post from the ground to `height` at x, z of the sign.
func _post(root: Node3D, x: float, height: float, z: float,
		thick := 1.0) -> void:
	var post := MeshInstance3D.new()
	post.mesh = _post_mesh
	post.scale = Vector3(thick, height, thick)
	post.position = Vector3(x, height / 2.0, z)
	post.material_override = _material(POST)
	post.visibility_range_end = PANEL_M
	root.add_child(post)


## A panel centred at x with its bottom at `bottom`: arrows parsed first
## (a ↑ ← → in front of a line), the ref in front of the first line,
## at least min_w wide; a line with tone `el` takes colours[2] if there is
## one; returns its size.
func _panel(root: Node3D, x: float, bottom: float, source: Array,
		ref: String, colours: Array, min_w: float, text_m: float,
		tones: Array = [], frame := false) -> Vector2:
	var lines: Array = source.duplicate()
	var arrows: Array = []
	var curves: Array = []
	for i in lines.size():
		curves.append(lines[i].begins_with(CURVE_PREFIX))
		var head: String = lines[i].substr(0, 1)
		arrows.append(null if curves[i] else ARROWS.get(head, null))
		if arrows[i] != null:
			lines[i] = lines[i].substr(1).strip_edges()
	if not ref.is_empty() and not lines.is_empty():
		lines[0] = "%s  %s" % [ref, lines[0]]
	var inset := FRAME_MARGIN + FRAME_W if frame else 0.0
	var widest := 0
	# framed: half the padding above and below, so the lines sit in the
	# middle (plain panels have all of it on top)
	var h := (PAD / 2.0 if frame else PAD) + inset
	var tops := []
	for i in lines.size():
		widest = maxi(widest, CURVE_CHARS if curves[i] else lines[i].length())
		tops.append(h)
		h += CURVE_H if curves[i] else LINE_H
	h += (PAD / 2.0 if frame else 0.0) + inset
	var with_arrows := arrows.any(func(a: Variant) -> bool: return a != null)
	# framed: room for the arrow on both sides, so the text is centred
	var arrow_room := ARROW_W * (2.0 if frame else 1.0) if with_arrows \
		else 0.0
	var w := maxf(min_w,
		PAD * 2.0 + CHAR_W * widest + arrow_room + 2.0 * inset)

	var panel := _slab_instance(_rounded_panel(w, h) if frame
		else _square_panel(w, h), colours[0])
	if frame:
		var ring := MeshInstance3D.new()
		ring.mesh = _frame_ring(w, h)
		ring.material_override = _arrow_material(colours[1])
		ring.position = Vector3(x, bottom + h / 2.0, DEPTH / 2.0 + 0.005)
		ring.visibility_range_end = PANEL_M
		root.add_child(ring)
	panel.position = Vector3(x, bottom + h / 2.0, 0.0)
	panel.visibility_range_end = PANEL_M
	root.add_child(panel)

	for i in lines.size():
		var line_h: float = CURVE_H if curves[i] else LINE_H
		var y: float = bottom + h - tops[i] - line_h / 2.0
		if curves[i]:
			var bend := MeshInstance3D.new()
			bend.mesh = _curve_mesh
			bend.material_override = _arrow_material(colours[1])
			bend.position = Vector3(x, y, DEPTH / 2.0 + 0.01)
			bend.scale = Vector3(-1.0 if lines[i] == CURVE_PREFIX + "left" \
				else 1.0, 1.0, 1.0)
			bend.visibility_range_end = PANEL_M
			root.add_child(bend)
			continue
		var label := Label3D.new()
		label.text = lines[i]
		label.font_size = FONT_SIZE
		label.pixel_size = PIXEL
		var greek: bool = i < tones.size() and tones[i] == "el" \
			and colours.size() > 2
		label.modulate = colours[2] if greek else colours[1]
		label.outline_size = 0
		label.shaded = false
		label.double_sided = false
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.position = Vector3(x + (ARROW_W / 2.0 if with_arrows
			and not frame else 0.0), y, DEPTH / 2.0 + 0.01)
		label.visibility_range_end = text_m
		root.add_child(label)
		if arrows[i] != null:
			var arrow := MeshInstance3D.new()
			arrow.mesh = _arrow_mesh
			arrow.material_override = _material(colours[1], true)
			arrow.position = Vector3(x - w / 2.0 + inset + PAD
				+ ARROW_W / 2.0 - 0.05, y, DEPTH / 2.0 + 0.01)
			arrow.rotation.z = arrows[i]
			arrow.visibility_range_end = text_m
			root.add_child(arrow)
	return Vector2(w, h)


## A pace note panel with its bottom at `bottom`: `lines` in pairs of
## grade and "@curve_*", one column per pair side by side, in the
## order given; returns its size.
func _pace_panel(root: Node3D, bottom: float, lines: Array,
		colours: Array) -> Vector2:
	var pairs := lines.size() / 2
	var size := Vector2(PACE_W * pairs, PACE_H)
	var centre := Vector3(0.0, bottom + PACE_H / 2.0, 0.0)
	var panel := _slab_instance(_rounded_panel(size.x, size.y) if _framed
		else _square_panel(size.x, size.y), colours[0])
	if _framed:
		var ring := MeshInstance3D.new()
		ring.mesh = _frame_ring(size.x, size.y)
		ring.material_override = _arrow_material(colours[1])
		ring.position = centre + Vector3(0.0, 0.0, DEPTH / 2.0 + 0.005)
		ring.visibility_range_end = PANEL_M
		root.add_child(ring)
	panel.position = centre
	panel.visibility_range_end = PANEL_M
	root.add_child(panel)
	for k in pairs:
		var x := -size.x / 2.0 + PACE_W * (k + 0.5)
		var label := Label3D.new()
		label.text = lines[2 * k]
		label.font_size = FONT_SIZE
		label.pixel_size = PACE_PIXEL
		label.modulate = colours[1]
		label.outline_size = 0
		label.shaded = false
		label.double_sided = false
		label.position = Vector3(x, bottom + PACE_H * PACE_GRADE_Y,
			DEPTH / 2.0 + 0.01)
		label.visibility_range_end = TEXT_M
		root.add_child(label)
		var bend := MeshInstance3D.new()
		bend.mesh = _curve_mesh
		bend.material_override = _arrow_material(colours[1])
		bend.position = Vector3(x, bottom + PACE_H * PACE_CURVE_Y,
			DEPTH / 2.0 + 0.01)
		var mirror := -1.0 if lines[2 * k + 1] == CURVE_PREFIX + "left" \
			else 1.0
		bend.scale = Vector3(mirror, 1.0, 1.0) * PACE_CURVE_SCALE
		bend.visibility_range_end = PANEL_M
		root.add_child(bend)
	return size


## An arrow pointing up (+Y), about LINE_H high, facing +Z: a shaft and
## a head as one flat mesh.
func _make_arrow() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	st.set_normal(Vector3.BACK)
	# clockwise seen from +Z (the traffic), Godot's front face
	var pts := [
		# shaft
		Vector2(-0.05, -0.22), Vector2(0.05, 0.04), Vector2(0.05, -0.22),
		Vector2(-0.05, -0.22), Vector2(-0.05, 0.04), Vector2(0.05, 0.04),
		# head
		Vector2(-0.16, 0.02), Vector2(0.0, 0.24), Vector2(0.16, 0.02)]
	for v: Vector2 in pts:
		st.add_vertex(Vector3(v.x, v.y, 0.0))
	return st.commit()


## A bent arrow turning right (+X), CURVE_H high and about 0.7 wide, as a
## stroke along a path: up, a quarter circle, then the head; mirrored by
## the caller for a left curve.
func _make_curve() -> ArrayMesh:
	var half := CURVE_STROKE / 2.0
	var bottom := -CURVE_H * 0.5
	var radius := 0.3
	var path: Array[Vector2] = [Vector2(-0.3, bottom)]
	var corner := Vector2(-0.3, 0.08)
	path.append(corner)
	var centre := corner + Vector2(radius, 0.0)
	for k in range(1, 9):
		var a := PI - (PI / 2.0) * k / 8.0
		path.append(centre + Vector2(cos(a), sin(a)) * radius)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	st.set_normal(Vector3.BACK)
	# mitred: every path point offset along the mean of the normals of its
	# two segments, so the pieces meet without notches on the outside
	var offsets: Array[Vector2] = []
	for k in path.size():
		var d_in := (path[k] - path[maxi(k - 1, 0)]).normalized()
		var d_out := (path[mini(k + 1, path.size() - 1)] - path[k]) \
			.normalized()
		var d := (d_in + d_out).normalized()
		var n := Vector2(-d.y, d.x)
		var n_seg := Vector2(-d_out.y, d_out.x) if k == 0 \
			else Vector2(-d_in.y, d_in.x)
		offsets.append(n * half / maxf(n.dot(n_seg), 0.5))
	for k in range(path.size() - 1):
		var a0 := path[k] + offsets[k]
		var a1 := path[k] - offsets[k]
		var b0 := path[k + 1] + offsets[k + 1]
		var b1 := path[k + 1] - offsets[k + 1]
		for v: Vector2 in [a0, a1, b0, b0, a1, b1]:
			st.add_vertex(Vector3(v.x, v.y, 0.0))
	# the head points along +X at the end of the arc
	var tip := path[path.size() - 1]
	for v: Vector2 in [tip + Vector2(0.0, 0.2), tip + Vector2(0.0, -0.2),
			tip + Vector2(0.3, 0.0)]:
		st.add_vertex(Vector3(v.x, v.y, 0.0))
	return st.commit()


## The outline of a w x h rectangle centred on the origin, `inset` in
## from its edge, corners rounded with FRAME_R - inset.
static func _rounded_outline(w: float, h: float,
		inset: float) -> Array[Vector2]:
	var r := maxf(FRAME_R - inset, 0.0)
	var hx := w / 2.0 - inset - r
	var hy := h / 2.0 - inset - r
	var pts: Array[Vector2] = []
	for corner: Vector2 in [Vector2(hx, hy), Vector2(-hx, hy),
			Vector2(-hx, -hy), Vector2(hx, -hy)]:
		var start := atan2(signf(corner.y), signf(corner.x)) - PI / 4.0
		for k in FRAME_STEPS + 1:
			var a := start + PI / 2.0 * k / FRAME_STEPS
			pts.append(corner + Vector2(cos(a), sin(a)) * r)
	return pts


## A panel w x h x DEPTH with rounded corners, centred on the origin.
func _rounded_panel(w: float, h: float) -> ArrayMesh:
	return _slab(_rounded_outline(w, h, 0.0))


## A panel w x h x DEPTH with square corners, centred on the origin.
func _square_panel(w: float, h: float) -> ArrayMesh:
	var x := w / 2.0
	var y := h / 2.0
	return _slab([Vector2(x, y), Vector2(-x, y), Vector2(-x, -y),
		Vector2(x, -y)])


## A flat plate DEPTH thick around the origin with the convex outline
## `pts`: surface 0 is the front (+Z), surface 1 the back and the edges
## (_slab_instance() gives them their materials).
func _slab(pts: Array[Vector2]) -> ArrayMesh:
	var mesh := ArrayMesh.new()
	var f := DEPTH / 2.0
	var n := pts.size()
	for side in [SLAB_FRONT, SLAB_BACK]:
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		for k in n:
			var a := pts[k]
			var b := pts[(k + 1) % n]
			var z := f if side == SLAB_FRONT else -f
			for v: Vector2 in [Vector2.ZERO, a, b]:
				st.add_vertex(Vector3(v.x, v.y, z))
			if side == SLAB_BACK:
				for v: Vector3 in [Vector3(a.x, a.y, f), Vector3(b.x, b.y, f),
						Vector3(b.x, b.y, -f), Vector3(a.x, a.y, f),
						Vector3(b.x, b.y, -f), Vector3(a.x, a.y, -f)]:
					st.add_vertex(v)
		st.commit(mesh)
	return mesh


## `mesh` (_slab()) with the front in `colour` and back and edges in the
## grey of the posts. Both are drawn from either side, as the winding of
## the slab is not kept; the nearer face hides the other.
func _slab_instance(mesh: ArrayMesh, colour: Color) -> MeshInstance3D:
	var plate := MeshInstance3D.new()
	plate.mesh = mesh
	plate.set_surface_override_material(SLAB_FRONT, _arrow_material(colour))
	plate.set_surface_override_material(SLAB_BACK, _arrow_material(POST))
	return plate


## The border of a framed w x h panel: a flat ring FRAME_W wide,
## FRAME_MARGIN inside the edge.
func _frame_ring(w: float, h: float) -> ArrayMesh:
	var outer := _rounded_outline(w, h, FRAME_MARGIN)
	var inner := _rounded_outline(w, h, FRAME_MARGIN + FRAME_W)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var n := outer.size()
	for k in n:
		var j := (k + 1) % n
		for v: Vector2 in [outer[k], outer[j], inner[j], outer[k],
				inner[j], inner[k]]:
			st.add_vertex(Vector3(v.x, v.y, 0.0))
	return st.commit()


## Like _material, but visible from both sides: the curve arrow is
## mirrored for a left curve, which flips the winding.
func _arrow_material(colour: Color) -> StandardMaterial3D:
	var key := ["arrow", colour]
	if not _materials.has(key):
		var m := _material(colour, true).duplicate()
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
		_materials[key] = m
	return _materials[key]


func _material(colour: Color, unshaded := false) -> StandardMaterial3D:
	var key := [colour, unshaded]
	if _materials.has(key):
		return _materials[key]
	var m := StandardMaterial3D.new()
	m.albedo_color = colour
	m.roughness = 0.6
	if unshaded:
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_materials[key] = m
	return m
# - revised 2026-10-23 (arrows as geometry)
# - revised 2026-10-23 (gantries, arrows before the ref)
# - revised 2026-10-25 (posts end at the panel and the beam)
# - revised 2026-10-25 (town signs by country, two posts, panel beside the road)
# - revised 2026-10-26 (pace note kinds, scale and bottom per sign)
# - revised 2026-10-27 (Cyprus: country colours, Greek line in yellow, town style)
# - revised 2026-11-04 (framed style trial: rounded corners, border, centred text)
# - revised 2026-11-04 (framed by default, large pace note layout)
# - revised 2026-11-04 (grey back and edges on every panel)
