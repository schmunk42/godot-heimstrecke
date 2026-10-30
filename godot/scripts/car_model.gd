# file generated with AI assistance: Claude Code - 2026-10-21 01:55:00 UTC
extends RefCounted
## Procedural car bodies: lofted bodies with box wheel arches, a
## greenhouse (all dark glass, or in the paint with glass windows), trim,
## lights and wheels with tyre and rim; the only brand mark is the four
## rings on the Audis. Three bodies (BODIES), chosen by the `body` key of
## a cars.gd entry: the 1980s Audi quattro (Typ 85) with its upright nose
## and sloping rear window down to the tail, the Sport quattro with the
## shorter wheelbase and the steeper windscreen, and the Lamborghini
## Huracán STO, a low wedge with an orange splitter and skirts, a roof
## scoop, a fin and a rear wing.
## Front is -Z, ground at y = 0.

## Body sections front to back, ground at y = 0: z, half width, sill
## height, top height. On the STO pairs of sections 2 cm apart raise the
## sill over each axle: square wheel openings. The Audis get round
## openings and flares from their `arches` entry instead (_arched). The
## Audis follow the side view
## of a Sport quattro (360 degree views of a 1:18 model): a nose 0.78 m
## high under a bonnet rising to the windscreen, the waist line at
## 0.92-0.97 m, box flares 3 cm proud of the doors, a sloping rear
## window down to a short tail deck with a black spoiler.
## quattro: front axle at z = -1.2625, 4.40 m long, 1.72 m wide over the
## flares; the Sport quattro stretched by 30 cm between the axles.
const QUATTRO_BODY := [
	[-2.19, 0.79, 0.30, 0.78],
	[-2.13, 0.83, 0.27, 0.81],
	[-1.64, 0.83, 0.26, 0.86],
	[-0.89, 0.83, 0.25, 0.92],
	[0.87, 0.83, 0.25, 0.93],
	[1.63, 0.83, 0.27, 0.96],
	[1.95, 0.83, 0.30, 0.97],
	[2.11, 0.81, 0.40, 0.97],
]
## Greenhouse sections: z, half width, base height, top height; roof at
## 1.344 m over a long flat roof, the windscreen, a long sloping rear
## window down to the tail deck (a coupé without a boot lid).
const QUATTRO_CANOPY := [
	[-0.92, 0.72, 0.88, 0.92],
	[-0.28, 0.67, 0.89, 1.33],
	[0.40, 0.66, 0.90, 1.344],
	[1.03, 0.65, 0.91, 1.33],
	[1.86, 0.59, 0.93, 1.04],
	[2.07, 0.57, 0.94, 0.99],
]
## Sport quattro: front axle at z = -1.112, 4.16 m long, 1.78 m wide
## over the flares.
const SPORT_BODY := [
	[-2.04, 0.82, 0.30, 0.78],
	[-1.98, 0.86, 0.27, 0.81],
	[-1.49, 0.86, 0.26, 0.86],
	[-0.74, 0.86, 0.25, 0.92],
	[0.72, 0.86, 0.25, 0.93],
	[1.48, 0.86, 0.27, 0.96],
	[1.80, 0.86, 0.30, 0.97],
	[1.96, 0.84, 0.40, 0.97],
]
## a steep windscreen, a short roof, the same sloping rear window
const SPORT_CANOPY := [
	[-0.58, 0.74, 0.88, 0.93],
	[-0.13, 0.69, 0.89, 1.33],
	[0.30, 0.68, 0.90, 1.345],
	[0.88, 0.67, 0.91, 1.33],
	[1.71, 0.61, 0.93, 1.04],
	[1.92, 0.59, 0.94, 0.99],
]
## Huracán STO: front axle at z = -1.31, 4.55 m long, 1.94 m wide, a low
## nose rising to the arches, a pinch at the side intakes.
const STO_BODY := [
	[-2.34, 0.80, 0.10, 0.28],
	[-2.26, 0.88, 0.10, 0.40],
	[-2.00, 0.92, 0.12, 0.54],
	[-1.73, 0.95, 0.12, 0.66],
	[-1.71, 0.95, 0.70, 0.74],
	[-0.91, 0.96, 0.70, 0.80],
	[-0.89, 0.96, 0.14, 0.80],
	[-0.40, 0.90, 0.14, 0.84],
	[0.40, 0.90, 0.14, 0.92],
	[0.89, 0.97, 0.14, 0.95],
	[0.91, 0.97, 0.72, 0.95],
	[1.71, 0.97, 0.72, 0.98],
	[1.73, 0.97, 0.18, 0.98],
	[2.05, 0.92, 0.20, 0.98],
	[2.21, 0.86, 0.26, 0.94],
]
## cab forward: a long raked windscreen, the roof at 1.22 m and the
## engine cover sloping down to the tail
const STO_CANOPY := [
	[-1.00, 0.80, 0.78, 0.80],
	[-0.55, 0.72, 0.80, 1.14],
	[-0.05, 0.64, 0.82, 1.22],
	[0.45, 0.62, 0.86, 1.21],
	[1.30, 0.66, 0.92, 1.02],
	[1.80, 0.74, 0.96, 0.99],
]
## Windows of a greenhouse in the paint (the 1980s Audis): windscreen
## and rear window as z ranges on the canopy top, each inside one canopy
## segment; side windows as outlines of z, y points on the canopy side,
## door window and rear side window apart for the B-pillar. The glass
## lies just outside the canopy, which supplies roof and pillars.
const QUATTRO_WINDOWS := {
	"front": [-0.88, -0.32], "rear": [1.07, 1.82],
	"side": [
		[[-0.74, 0.95], [-0.30, 1.28], [0.52, 1.28], [0.52, 0.95]],
		[[0.60, 0.95], [0.60, 1.28], [1.00, 1.28], [1.37, 0.95]]],
}
const SPORT_WINDOWS := {
	"front": [-0.54, -0.17], "rear": [0.92, 1.67],
	"side": [
		[[-0.48, 0.95], [-0.15, 1.28], [0.52, 1.28], [0.52, 0.95]],
		[[0.60, 0.95], [0.60, 1.28], [0.86, 1.28], [1.22, 0.95]]],
}
## body: sections, canopy, superellipse exponents of body and canopy
## (smaller is boxier), rim radius, windows (empty: all-glass canopy),
## arches: axle positions and half width over the flares (optional)
const BODIES := {
	"quattro": {"body": QUATTRO_BODY, "canopy": QUATTRO_CANOPY,
		"shape": Vector2(0.07, 0.14), "canopy_shape": Vector2(0.06, 0.1),
		"rim": 0.19, "windows": QUATTRO_WINDOWS,
		"arches": {"axles": [-1.2625, 1.2625], "flare": 0.86}},
	"sport_quattro": {"body": SPORT_BODY, "canopy": SPORT_CANOPY,
		"shape": Vector2(0.07, 0.14), "canopy_shape": Vector2(0.06, 0.1),
		"rim": 0.19, "windows": SPORT_WINDOWS,
		"arches": {"axles": [-1.112, 1.112], "flare": 0.89}},
	"sto": {"body": STO_BODY, "canopy": STO_CANOPY,
		"shape": Vector2(0.15, 0.3), "canopy_shape": Vector2(0.2, 0.35),
		"rim": 0.254, "windows": {}},
}
## glass offset outside the canopy, windscreen and rear window inset from
## its sides (the pillars), m
const GLASS_OFFSET := 0.008
const GLASS_INSET := 0.07
## round wheel openings: radius over the tyre radius, flare reach beyond
## the opening and the step from door to flare, resampling step, m
const ARCH_GAP := 0.05
const FLARE_REACH := 0.12
const FLARE_STEP := 0.06
const ARCH_STEP := 0.04
const RING := 16
const ORANGE := Color(0.95, 0.42, 0.06)
const HEADLIGHT := Color(1.0, 0.97, 0.9)
const TAIL_LIGHT := Color(1.0, 0.05, 0.03)
const INDICATOR := Color(1.0, 0.55, 0.05)


## Body parts of car `spec` (a cars.gd entry) go below `parent`, the four
## wheels below `wheel_parent` (the car positions them itself).
static func build(parent: Node3D, wheel_parent: Node3D,
		spec: Dictionary) -> Array[MeshInstance3D]:
	var body: Dictionary = BODIES[spec.body]
	var paint := StandardMaterial3D.new()
	paint.albedo_color = spec.paint
	paint.metallic = 0.2
	paint.roughness = 0.35
	paint.clearcoat_enabled = true
	var sections: Array = body.body
	if body.has("arches"):
		sections = _arched(sections, body.arches, spec.radius)
	_add(parent, _loft(sections, paint, body.shape), Vector3.ZERO)

	var glass := StandardMaterial3D.new()
	glass.albedo_color = Color(0.05, 0.06, 0.08)
	glass.metallic = 0.3
	glass.roughness = 0.05
	var windows: Dictionary = body.windows
	if windows.is_empty():
		_add(parent, _loft(body.canopy, glass, body.canopy_shape),
			Vector3.ZERO)
	else:
		_add(parent, _loft(body.canopy, paint, body.canopy_shape),
			Vector3.ZERO)
		glass.cull_mode = BaseMaterial3D.CULL_DISABLED
		_add(parent, _windows(body.canopy, windows, glass), Vector3.ZERO)

	var trim := StandardMaterial3D.new()
	trim.albedo_color = Color(0.04, 0.04, 0.045)
	trim.roughness = 0.7
	match spec.body:
		"quattro":
			_quattro_details(parent, trim)
		"sport_quattro":
			_sport_details(parent, trim)
		"sto":
			_sto_details(parent, paint, trim)

	var wheels: Array[MeshInstance3D] = []
	var tyre := StandardMaterial3D.new()
	tyre.albedo_color = Color(0.06, 0.06, 0.06)
	tyre.roughness = 0.9
	var rim := StandardMaterial3D.new()
	rim.albedo_color = spec.rim
	rim.metallic = 0.9
	rim.roughness = 0.3
	var radius: float = spec.radius
	for i in 4:
		var width: float = spec.tyre_width[0 if i < 2 else 1]
		var wheel := MeshInstance3D.new()
		var cyl := CylinderMesh.new()
		cyl.top_radius = radius
		cyl.bottom_radius = radius
		cyl.height = width
		cyl.material = tyre
		wheel.mesh = cyl
		var hub := MeshInstance3D.new()
		var disc := CylinderMesh.new()
		disc.top_radius = body.rim
		disc.bottom_radius = body.rim
		disc.height = width + 0.01
		disc.radial_segments = 10
		disc.material = rim
		hub.mesh = disc
		wheel.add_child(hub)
		wheel_parent.add_child(wheel)
		wheels.append(wheel)
	return wheels


## Ur-quattro: the front of the Sport quattro (below) with two
## rectangular headlights per side and a narrower grille, a smaller
## spoiler.
static func _quattro_details(parent: Node3D, trim: Material) -> void:
	var z := -2.21
	_box(parent, Vector3(0.62, 0.12, 0.04), Vector3(0.0, 0.71, z), trim)
	for side in [-1.0, 1.0]:
		_light(parent, Vector3(0.14, 0.12, 0.04),
			Vector3(side * 0.39, 0.71, z - 0.01), HEADLIGHT, 4.0)
		_light(parent, Vector3(0.20, 0.12, 0.04),
			Vector3(side * 0.58, 0.71, z - 0.01), HEADLIGHT, 4.0)
	_rings(parent, Vector3(0.0, 0.71, z - 0.02))
	_audi_front(parent, trim, z)
	_audi_rear(parent, trim, 2.13, 1.40)


## Sport quattro after the 1:18 model: one large rectangular headlight
## per side with the black grille and the rings between them, amber
## indicators and a black grille band in the bumper, a black lip; at the
## back a black panel with two tail lights, a black bumper strip and the
## large black spoiler on the tail deck.
static func _sport_details(parent: Node3D, trim: Material) -> void:
	var z := -2.06
	_box(parent, Vector3(0.90, 0.13, 0.04), Vector3(0.0, 0.71, z), trim)
	for side in [-1.0, 1.0]:
		_light(parent, Vector3(0.26, 0.12, 0.04),
			Vector3(side * 0.60, 0.71, z - 0.01), HEADLIGHT, 4.0)
	_rings(parent, Vector3(0.0, 0.71, z - 0.02))
	_audi_front(parent, trim, z)
	_audi_rear(parent, trim, 1.98, 1.50)


## Bumper of both Audis in the paint: black grille band, amber
## indicators, black lip; black sill strips along the doors.
static func _audi_front(parent: Node3D, trim: Material, z: float) -> void:
	_box(parent, Vector3(1.10, 0.06, 0.04), Vector3(0.0, 0.47, z), trim)
	_box(parent, Vector3(1.60, 0.04, 0.10), Vector3(0.0, 0.31, z + 0.03),
		trim)
	for side in [-1.0, 1.0]:
		_light(parent, Vector3(0.10, 0.06, 0.04),
			Vector3(side * 0.68, 0.52, z - 0.01), INDICATOR, 2.0)
		_box(parent, Vector3(0.02, 0.05, 1.30),
			Vector3(side * 0.835, 0.28, 0.0), trim)


## Rear of both Audis: black panel with two tail lights at the sides,
## black bumper strip, black spoiler `width` wide on the tail deck; z is
## the rear face.
static func _audi_rear(parent: Node3D, trim: Material, z: float,
		width: float) -> void:
	_box(parent, Vector3(1.50, 0.22, 0.04), Vector3(0.0, 0.76, z), trim)
	for side in [-1.0, 1.0]:
		_light(parent, Vector3(0.30, 0.18, 0.04),
			Vector3(side * 0.60, 0.76, z + 0.01), TAIL_LIGHT, 1.5)
	_box(parent, Vector3(1.64, 0.05, 0.06), Vector3(0.0, 0.50, z - 0.01),
		trim)
	_box(parent, Vector3(width, 0.04, 0.22), Vector3(0.0, 1.03, z - 0.12),
		trim, Vector3(0.08, 0.0, 0.0))


## The four interlaced rings in chrome, centred at `at`, facing forward.
static func _rings(parent: Node3D, at: Vector3) -> void:
	var chrome := StandardMaterial3D.new()
	chrome.albedo_color = Color(0.85, 0.86, 0.88)
	chrome.metallic = 1.0
	chrome.roughness = 0.2
	var ring := TorusMesh.new()
	ring.inner_radius = 0.036
	ring.outer_radius = 0.046
	ring.rings = 24
	ring.ring_segments = 8
	ring.material = chrome
	for k in 4:
		var x := (k - 1.5) * 0.068
		_add(parent, ring, at + Vector3(x, 0.0, 0.0)).rotation = \
			Vector3(PI / 2, 0.0, 0.0)


## Huracán STO: orange splitter and side skirts, black intakes, slim
## angled headlights, roof scoop and fin in the paint, a black rear wing
## on two pylons with orange end plates, tail light strip and diffuser.
static func _sto_details(parent: Node3D, paint: Material,
		trim: Material) -> void:
	var orange := StandardMaterial3D.new()
	orange.albedo_color = ORANGE
	orange.roughness = 0.4
	_box(parent, Vector3(1.86, 0.035, 0.30), Vector3(0.0, 0.09, -2.22),
		orange)
	_box(parent, Vector3(1.50, 0.18, 0.06), Vector3(0.0, 0.24, -2.30), trim)
	for side in [-1.0, 1.0]:
		_box(parent, Vector3(0.05, 0.07, 1.60),
			Vector3(side * 0.91, 0.13, 0.0), orange)
		_light(parent, Vector3(0.36, 0.035, 0.05),
			Vector3(side * 0.60, 0.50, -2.15), HEADLIGHT, 4.0,
			Vector3(0.0, side * 0.35, side * -0.15))
		_box(parent, Vector3(0.03, 0.26, 0.12),
			Vector3(side * 0.42, 1.08, 2.02), trim)
		_box(parent, Vector3(0.025, 0.20, 0.42),
			Vector3(side * 0.93, 1.20, 2.02), orange)
	_box(parent, Vector3(0.24, 0.10, 0.70), Vector3(0.0, 1.21, 0.25), paint)
	_box(parent, Vector3(0.03, 0.18, 1.00), Vector3(0.0, 1.08, 1.15), paint)
	_box(parent, Vector3(1.84, 0.035, 0.34), Vector3(0.0, 1.24, 2.02), trim,
		Vector3(-0.12, 0.0, 0.0))
	_light(parent, Vector3(1.50, 0.04, 0.04), Vector3(0.0, 0.86, 2.21),
		TAIL_LIGHT, 3.0)
	_box(parent, Vector3(1.60, 0.20, 0.30), Vector3(0.0, 0.24, 2.10), trim)


## The sections resampled every ARCH_STEP with round wheel openings: the
## sill follows a circle ARCH_GAP wider than the tyre around each axle
## (the wheel centre is `tyre` above the ground), and the half width
## widens to the flare over the opening and FLARE_REACH beyond it.
static func _arched(sections: Array, arches: Dictionary,
		tyre: float) -> Array:
	var radius := tyre + ARCH_GAP
	var zs: Array[float] = []
	var z: float = sections[0][0]
	while z < sections[-1][0]:
		zs.append(z)
		z += ARCH_STEP
	for s: Array in sections:
		zs.append(s[0])
	zs.sort()
	var out: Array = []
	for at in zs:
		if not out.is_empty() and at - out[-1][0] < 0.005:
			continue
		var hw := _section_at(sections, at, 1)
		var sill := _section_at(sections, at, 2)
		var top := _section_at(sections, at, 3)
		for axle: float in arches.axles:
			var dz := absf(at - axle)
			if dz < radius:
				sill = maxf(sill, tyre + sqrt(radius * radius - dz * dz))
			var reach := radius + FLARE_REACH
			if dz < reach:
				hw = maxf(hw, lerpf(arches.flare, hw,
					clampf((dz - reach + FLARE_STEP) / FLARE_STEP, 0.0, 1.0)))
		out.append([at, hw, sill, top])
	return out


## Glass faces on a canopy in the paint: windscreen and rear window
## between the pillars on the canopy top, the side windows on both sides.
static func _windows(canopy: Array, windows: Dictionary,
		glass: Material) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for key: String in ["front", "rear"]:
		var a: float = windows[key][0]
		var b: float = windows[key][1]
		var corners: Array[Vector3] = []
		for z: float in [a, b]:
			var hw := _section_at(canopy, z, 1) - GLASS_INSET
			var y := _section_at(canopy, z, 3) + GLASS_OFFSET
			corners.append(Vector3(-hw, y, z))
			corners.append(Vector3(hw, y, z))
		_tri(st, corners[0], corners[1], corners[3])
		_tri(st, corners[0], corners[3], corners[2])
	for outline: Array in windows.side:
		for side in [-1.0, 1.0]:
			var points: Array[Vector3] = []
			for p: Array in outline:
				var x: float = side * (_section_at(canopy, p[0], 1)
					+ GLASS_OFFSET)
				points.append(Vector3(x, p[1], p[0]))
			for k in range(1, points.size() - 1):
				_tri(st, points[0], points[k], points[k + 1])
	st.generate_normals()
	st.set_material(glass)
	return st.commit()


## Column `col` of the sections (1 half width, 2 sill, 3 top) at z, linear
## between neighbouring sections.
static func _section_at(sections: Array, z: float, col: int) -> float:
	for k in range(1, sections.size()):
		var a: Array = sections[k - 1]
		var b: Array = sections[k]
		if z <= b[0]:
			return lerpf(a[col], b[col],
				clampf((z - a[0]) / (b[0] - a[0]), 0.0, 1.0))
	return sections[-1][col]


## Closed loft through the sections; each ring is a rounded box shape
## (superellipse) between sill and top at the given half width.
static func _loft(sections: Array, material: Material,
		shape: Vector2) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var rings: Array = []
	for s: Array in sections:
		var ring: Array[Vector3] = []
		var mid: float = (s[2] + s[3]) / 2.0
		var half_h: float = (s[3] - s[2]) / 2.0
		for k in RING:
			var a := TAU * k / RING
			var c := cos(a)
			var sn := sin(a)
			var x: float = signf(c) * pow(absf(c), shape.x) * s[1]
			var y: float = signf(sn) * pow(absf(sn), shape.y) * half_h
			ring.append(Vector3(x, mid + y, s[0]))
		rings.append(ring)
	for r in rings.size() - 1:
		var a: Array[Vector3] = rings[r]
		var b: Array[Vector3] = rings[r + 1]
		for k in RING:
			var k2 := (k + 1) % RING
			_tri(st, a[k], b[k], b[k2])
			_tri(st, a[k], b[k2], a[k2])
	_cap(st, rings[0], true)
	_cap(st, rings[-1], false)
	st.generate_normals()
	st.set_material(material)
	return st.commit()


static func _tri(st: SurfaceTool, p: Vector3, q: Vector3, r: Vector3) -> void:
	st.add_vertex(p)
	st.add_vertex(q)
	st.add_vertex(r)


static func _cap(st: SurfaceTool, ring: Array[Vector3], front: bool) -> void:
	var centre := Vector3.ZERO
	for p in ring:
		centre += p
	centre /= ring.size()
	for k in RING:
		var p := ring[k]
		var q := ring[(k + 1) % RING]
		# clockwise seen from outside (Godot's front face)
		if front:
			_tri(st, centre, p, q)
		else:
			_tri(st, centre, q, p)


static func _light(parent: Node3D, size: Vector3, at: Vector3, color: Color,
		energy: float, rotation := Vector3.ZERO) -> void:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.emission_enabled = true
	mat.emission = color
	mat.emission_energy_multiplier = energy
	_box(parent, size, at, mat, rotation)


static func _box(parent: Node3D, size: Vector3, at: Vector3,
		material: Material, rotation := Vector3.ZERO) -> void:
	var box := BoxMesh.new()
	box.size = size
	box.material = material
	_add(parent, box, at).rotation = rotation


static func _add(parent: Node3D, mesh: Mesh, at: Vector3) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.mesh = mesh
	node.position = at
	parent.add_child(node)
	return node
