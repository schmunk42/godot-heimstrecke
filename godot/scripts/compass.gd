# file generated with AI assistance: Claude Code - 2026-10-21 10:20:00 UTC
extends Control
## HUD compass: a rose that turns with the view, N in red, the heading
## in degrees below. heading_deg: 0 = north, 90 = east (world -Z is
## north, +X east, see pipeline/frame.py; in a turned world north lies
## north_offset_deg = -(the manifest's heading_deg) off -Z).

const RADIUS := 46.0
const LABELS := {0: "N", 90: "E", 180: "S", 270: "W"}

var north_offset_deg := 0.0
var heading_deg := 0.0:
	set(value):
		heading_deg = fposmod(value, 360.0)
		queue_redraw()


func _init() -> void:
	custom_minimum_size = Vector2(RADIUS * 2.0 + 8.0, RADIUS * 2.0 + 40.0)
	size = custom_minimum_size
	mouse_filter = Control.MOUSE_FILTER_IGNORE


## Sets the heading from a node's forward axis (-Z).
func follow(node: Node3D) -> void:
	var forward := -node.global_basis.z
	if Vector2(forward.x, forward.z).length() > 0.01:
		heading_deg = rad_to_deg(atan2(forward.x, -forward.z)) \
			+ north_offset_deg


func _draw() -> void:
	var font := get_theme_default_font()
	var centre := Vector2(RADIUS + 4.0, RADIUS + 4.0)
	draw_circle(centre, RADIUS, Color(0.05, 0.06, 0.08, 0.55))
	draw_arc(centre, RADIUS, 0.0, TAU, 48, Color(1, 1, 1, 0.6), 2.0, true)
	for deg in range(0, 360, 30):
		var a := deg_to_rad(deg - heading_deg) - PI / 2.0
		var dir := Vector2(cos(a), sin(a))
		var inner := RADIUS - (10.0 if deg % 90 == 0 else 5.0)
		draw_line(centre + dir * inner, centre + dir * (RADIUS - 1.0),
			Color(1, 1, 1, 0.8), 2.0, true)
		if LABELS.has(deg):
			var text: String = LABELS[deg]
			var colour := Color(1.0, 0.25, 0.2) if deg == 0 else Color.WHITE
			var at := centre + dir * (RADIUS - 22.0)
			var w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT,
				-1, 18).x
			draw_string_outline(font, at + Vector2(-w / 2.0, 7.0), text,
				HORIZONTAL_ALIGNMENT_LEFT, -1, 18, 4, Color.BLACK)
			draw_string(font, at + Vector2(-w / 2.0, 7.0), text,
				HORIZONTAL_ALIGNMENT_LEFT, -1, 18, colour)
	# fixed marker for the view direction at the top
	draw_colored_polygon(PackedVector2Array([
		centre + Vector2(0, -RADIUS - 2.0),
		centre + Vector2(-6, -RADIUS + 8.0),
		centre + Vector2(6, -RADIUS + 8.0)]), Color(1.0, 0.85, 0.1))
	var label := "%03d°" % (roundi(heading_deg) % 360)
	var lw := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1,
		20).x
	var pos := Vector2(centre.x - lw / 2.0, RADIUS * 2.0 + 30.0)
	draw_string_outline(font, pos, label, HORIZONTAL_ALIGNMENT_LEFT, -1, 20,
		5, Color.BLACK)
	draw_string(font, pos, label, HORIZONTAL_ALIGNMENT_LEFT, -1, 20)
# - revised 2026-10-23 (north offset for turned worlds)
