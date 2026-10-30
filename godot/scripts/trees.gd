# file generated with AI assistance: Claude Code - 2026-10-23 03:10:00 UTC
extends Node3D
## The trees of pipeline/trees.py: per tile a <tile>.trees file with one
## MultiMesh instance per tree (16 floats, the buffer layout of a
## TRANSFORM_3D MultiMesh with colours), kind by kind, within a kind chunk
## by chunk. Each chunk gets a near MultiMeshInstance3D (trunk and crown,
## casts shadows) up to NEAR_M, each tile a far one (a few triangles,
## slightly smaller, so it hides inside the near crown) up to FAR_M; both
## take their slice of the same buffer, nothing loops over the trees.
## With collision every <tile>.trunks point gets a trunk cylinder on
## the buildings layer, one static body per tile.
## Kinds (pipeline/biome.py): broad and conifer in the temperate worlds;
## oak (holm oak, dark round crown), pine (tall bare trunk, flat
## umbrella crown), cypress (narrow spindle) and shrub (the maquis, a
## low dome, near only up to SHRUB_NEAR_M) in the mediterranean ones.

const FLOATS := 16
const NEAR_M := 450.0
const FAR_M := 3500.0
const TRUNK_RADIUS := 0.3
const TRUNK_HEIGHT := 5.0
const BARK := Color(0.33, 0.25, 0.18)
const SHRUB_NEAR_M := 220.0
const SHRUB_FAR_M := 1200.0
const LEAVES := {"broad": Color(0.22, 0.38, 0.16),
	"conifer": Color(0.12, 0.27, 0.14),
	"oak": Color(0.16, 0.26, 0.12),
	"pine": Color(0.21, 0.32, 0.14),
	"cypress": Color(0.10, 0.21, 0.10),
	"shrub": Color(0.25, 0.32, 0.14)}
## Far crowns: ring radius and height, top, bottom (-1 = none, a pyramid).
const FAR := {"broad": [0.22, 0.62, 0.95, 0.33],
	"conifer": [0.14, 0.2, 0.95, -1.0],
	"oak": [0.3, 0.6, 0.95, 0.25],
	"pine": [0.3, 0.76, 0.9, 0.62],
	"cypress": [0.07, 0.15, 0.97, -1.0],
	"shrub": [0.3, 0.35, 0.8, 0.0]}

var _near := {}
var _far := {}
var _materials := {}
var _trunk := CylinderShape3D.new()


## Loads every tile of `meta` (world.json "trees") through `loader` (an
## opened WorldLoader); `layer` is the collision layer of the trunks, 0
## for none.
func load_trees(loader: RefCounted, meta: Dictionary, layer: int) -> int:
	var kinds: Array = meta.kinds
	for kind: String in kinds:
		_near[kind] = _near_mesh(kind)
		_far[kind] = _far_mesh(kind)
	_trunk.radius = TRUNK_RADIUS
	_trunk.height = TRUNK_HEIGHT
	var total := 0
	for tile: Dictionary in meta.tiles:
		var expected := 0
		for counts: Array in tile.counts:
			for n: int in counts:
				expected += n
		if expected == 0:
			continue
		var buf: PackedFloat32Array = loader.read_bytes(
			tile.name + ".trees").to_float32_array()
		if buf.size() != expected * FLOATS:
			push_error("%s.trees: %d floats, expected %d" % [tile.name,
				buf.size(), expected * FLOATS])
			continue
		var start := 0
		for k in kinds.size():
			var counts: Array = tile.counts[k]
			var kind_start := start
			var shrub: bool = kinds[k] == "shrub"
			for n: int in counts:
				if n > 0:
					_add(_near[kinds[k]], buf, start, n,
						SHRUB_NEAR_M if shrub else NEAR_M, not shrub)
				start += n
			if start > kind_start:
				_add(_far[kinds[k]], buf, kind_start, start - kind_start,
					SHRUB_FAR_M if shrub else FAR_M, false)
		total += start
		if layer != 0 and tile.trunks > 0:
			_add_trunks(loader.read_bytes(tile.name + ".trunks") \
				.to_float32_array(), layer)
	return total


func _add(mesh: Mesh, buf: PackedFloat32Array, start: int, n: int,
		range_end: float, shadows: bool) -> void:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = mesh
	mm.instance_count = n
	mm.buffer = buf.slice(start * FLOATS, (start + n) * FLOATS)
	var node := MultiMeshInstance3D.new()
	node.multimesh = mm
	node.visibility_range_end = range_end
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON \
		if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)


func _add_trunks(feet: PackedFloat32Array, layer: int) -> void:
	var body := StaticBody3D.new()
	body.collision_layer = layer
	body.collision_mask = 0
	var rid := body.get_rid()
	var lift := Vector3.UP * TRUNK_HEIGHT * 0.5
	for i in range(0, feet.size(), 3):
		PhysicsServer3D.body_add_shape(rid, _trunk.get_rid(), Transform3D(
			Basis.IDENTITY, Vector3(feet[i], feet[i + 1], feet[i + 2]) + lift))
	# outside the space Jolt builds the compound once, inside on every add
	add_child(body)


## Trunk and crown, one unit high; the instance scales it to the tree.
func _near_mesh(kind: String) -> ArrayMesh:
	var mesh := ArrayMesh.new()
	var leaves: Color = LEAVES.get(kind, LEAVES["broad"])
	match kind:
		"conifer":
			_add_part(mesh, _cylinder(0.02, 0.02, 0.3, 5), 0.0, BARK)
			# three cones, overlapping so the far pyramid stays inside
			_add_part(mesh, _cylinder(0.0, 0.2, 0.45, 7), 0.15, leaves)
			_add_part(mesh, _cylinder(0.0, 0.15, 0.45, 7), 0.35, leaves)
			_add_part(mesh, _cylinder(0.0, 0.1, 0.4, 7), 0.6, leaves)
		"pine":
			_add_part(mesh, _cylinder(0.018, 0.03, 0.66, 5), 0.0, BARK)
			# a flat umbrella and a smaller cap on it, a little off centre
			_add_part(mesh, _sphere(0.34, 0.24, 9), 0.6, leaves)
			_add_part(mesh, _sphere(0.2, 0.16, 7), 0.74, leaves,
				Vector3(0.06, 0.0, -0.04))
		"oak":
			_add_part(mesh, _cylinder(0.03, 0.045, 0.32, 5), 0.0, BARK)
			_add_part(mesh, _sphere(0.38, 0.74, 8), 0.22, leaves)
		"cypress":
			_add_part(mesh, _cylinder(0.015, 0.02, 0.1, 5), 0.0, BARK)
			_add_part(mesh, _sphere(0.09, 0.92, 7), 0.06, leaves)
		"shrub":
			# a dome, its lower part in the ground
			_add_part(mesh, _sphere(0.36, 1.1, 7), -0.25, leaves)
		_:
			_add_part(mesh, _cylinder(0.025, 0.035, 0.45, 5), 0.0, BARK)
			_add_part(mesh, _sphere(0.3, 0.7, 8), 0.3, leaves)
	return mesh


## Crown only, a few triangles: an octahedron or a four-sided pyramid.
func _far_mesh(kind: String) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var ring: Array[Vector3] = []
	var far: Array = FAR.get(kind, FAR["broad"])
	for i in 4:
		var a := TAU * i / 4.0
		ring.append(Vector3(cos(a) * far[0], far[1], sin(a) * far[0]))
	var top := Vector3(0, far[2], 0)
	var bottom := Vector3(0, far[3], 0)
	for i in 4:
		var a := ring[i]
		var b := ring[(i + 1) % 4]
		# clockwise seen from outside, Godot's front face
		st.add_vertex(top)
		st.add_vertex(a)
		st.add_vertex(b)
		if far[3] >= 0.0:
			st.add_vertex(bottom)
			st.add_vertex(b)
			st.add_vertex(a)
	st.generate_normals()
	var mesh := st.commit()
	mesh.surface_set_material(0, _material(LEAVES.get(kind,
		LEAVES["broad"])))
	return mesh


func _sphere(radius: float, height: float, segments: int) -> SphereMesh:
	var crown := SphereMesh.new()
	crown.radius = radius
	crown.height = height
	crown.radial_segments = segments
	crown.rings = 4
	return crown


func _cylinder(top: float, bottom: float, height: float,
		segments: int) -> CylinderMesh:
	var c := CylinderMesh.new()
	c.top_radius = top
	c.bottom_radius = bottom
	c.height = height
	c.radial_segments = segments
	c.rings = 0
	c.cap_top = false
	c.cap_bottom = false
	return c


## Adds `part` as a surface of `mesh`, its foot lifted to `foot` and
## moved sideways by `shift`.
func _add_part(mesh: ArrayMesh, part: PrimitiveMesh, foot: float,
		color: Color, shift := Vector3.ZERO) -> void:
	var arrays := part.get_mesh_arrays()
	var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var lift := shift + Vector3.UP * (foot + part.get_aabb().size.y * 0.5)
	for i in verts.size():
		verts[i] += lift
	arrays[Mesh.ARRAY_VERTEX] = verts
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	mesh.surface_set_material(mesh.get_surface_count() - 1, _material(color))


## The instance colour (the tint of pipeline/trees.py) multiplies `color`.
func _material(color: Color) -> StandardMaterial3D:
	if _materials.has(color):
		return _materials[color]
	var m := StandardMaterial3D.new()
	_materials[color] = m
	m.albedo_color = color
	m.vertex_color_use_as_albedo = true
	m.roughness = 1.0
	return m
# - revised 2026-10-23 (mediterranean kinds: oak, pine, cypress, shrub)
