# file generated with AI assistance: Claude Code - 2026-10-22 23:05:00 UTC
extends Control
## World selection, the main scene: one button per world that
## WorldLoader.find_worlds() finds (name, version, package or directory
## with its path, size, build time, number of routes; a world that does
## not open is listed disabled with the reason) and the data attribution
## of the highlighted world at the bottom. Keys 1-9 and 0 or a click
## choose, Up/Down highlight, Enter/Space take the highlighted world, C
## or the Credits button shows the credits (credits.gd) with the data of
## the highlighted world. The chosen world replaces this scene with the
## drive scene. With --world <path> the selection is skipped (the
## launcher interface).

const DRIVE_SCENE := "res://scenes/drive.tscn"
## preloaded: without the editor's class cache class_name is unknown
const WORLD_LOADER := preload("res://scripts/world_loader.gd")
const CREDITS := preload("res://scripts/credits.gd")

var _worlds: Array[Dictionary] = []
var _buttons: Array[Button] = []
var _attribution: Label
var _highlighted := -1
var _credits: Control


func _ready() -> void:
	var launch := WORLD_LOADER.args()
	if not launch.world.is_empty():
		_start_drive.call_deferred(launch.world)
		return
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_worlds = WORLD_LOADER.find_worlds()
	_build()


func _build() -> void:
	var shade := ColorRect.new()
	shade.color = Color(0.05, 0.06, 0.08)
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(shade)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var list := VBoxContainer.new()
	list.add_theme_constant_override("separation", 6)
	center.add_child(list)

	var title := Label.new()
	title.text = "Choose a world"
	title.add_theme_font_size_override("font_size", 30)
	list.add_child(title)
	for i in _worlds.size():
		var button := Button.new()
		button.text = "%s   %s" % [_key_name(i), _describe(_worlds[i])]
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.add_theme_font_size_override("font_size", 18)
		button.disabled = not _worlds[i].error.is_empty()
		button.pressed.connect(_choose.bind(i))
		button.focus_entered.connect(_highlight.bind(i))
		button.mouse_entered.connect(_highlight.bind(i))
		list.add_child(button)
		_buttons.append(button)
	if _worlds.is_empty():
		var none := Label.new()
		none.text = "No worlds found. Build one with make world (see " \
			+ "README) or put a .world file into %s" \
			% ProjectSettings.globalize_path(WORLD_LOADER.USER_WORLDS)
		list.add_child(none)

	_attribution = Label.new()
	_attribution.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_attribution.custom_minimum_size = Vector2(900, 0)
	_attribution.add_theme_font_size_override("font_size", 14)
	_attribution.modulate = Color(1, 1, 1, 0.8)
	list.add_child(_attribution)
	var hint := Label.new()
	hint.text = "1-9, 0 or click choose   Up/Down highlight   " \
		+ "Enter / Space start   C credits"
	hint.modulate = Color(1, 1, 1, 0.7)
	list.add_child(hint)
	var credits := Button.new()
	credits.text = "Credits and licences"
	credits.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	credits.pressed.connect(_open_credits)
	list.add_child(credits)
	_credits = Control.new()
	_credits.set_script(CREDITS)
	add_child(_credits)
	_credits.closed.connect(_focus_highlighted)

	for i in _buttons.size():
		if not _buttons[i].disabled:
			_buttons[i].grab_focus.call_deferred()
			_highlight(i)
			break


## Two lines per world: name, version, routes, size, build time; then
## package or directory with its path (or why it does not open).
func _describe(world: Dictionary) -> String:
	var kind := "package" if world.is_package else "directory"
	if not world.error.is_empty():
		return "%s (unavailable)\n      %s" % [
			world.path.get_file(), world.error]
	var manifest: Dictionary = world.manifest
	var parts: Array[String] = [str(manifest.get("name",
		manifest.get("id", world.path.get_file())))]
	if manifest.has("version"):
		parts.append("v%s" % manifest.version)
	var routes := WORLD_LOADER.routes_of(manifest).size()
	parts.append("%d route%s" % [routes, "" if routes == 1 else "s"])
	if manifest.get("size_bytes") is float:
		parts.append("%.1f MB" % (manifest.size_bytes / 1.0e6))
	if manifest.has("built"):
		parts.append("built %s" % manifest.built)
	return "%s\n      %s  %s" % ["   ".join(parts), kind, world.path]


func _highlight(index: int) -> void:
	_highlighted = index
	var world: Dictionary = _worlds[index]
	var text := str(world.manifest.get("attribution", ""))
	_attribution.text = text if not text.is_empty() \
		else "%s: no attribution in its manifest" % world.path.get_file()


func _choose(index: int) -> void:
	if _buttons[index].disabled:
		return
	_start_drive(_worlds[index].path)


## Replaces this scene with the drive scene on the world at `path`.
func _start_drive(path: String) -> void:
	var drive: Node = load(DRIVE_SCENE).instantiate()
	drive.set("world_path", path)
	var tree := get_tree()
	tree.root.add_child(drive)
	tree.current_scene = drive
	queue_free()


func _open_credits() -> void:
	_credits.open(_worlds[_highlighted].manifest if _highlighted >= 0 \
		else {})


func _focus_highlighted() -> void:
	if _highlighted >= 0:
		_buttons[_highlighted].grab_focus()


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed):
		return
	if _credits.visible:
		return
	if event.keycode == KEY_C:
		get_viewport().set_input_as_handled()
		_open_credits()
		return
	var index := _key_index(event.keycode)
	if index >= 0 and index < _worlds.size():
		get_viewport().set_input_as_handled()
		_choose(index)


## Digit keys 1-9 and 0 stand for the worlds 1-10; -1 for any other key.
func _key_index(code: Key) -> int:
	if code == KEY_0:
		return 9
	if code >= KEY_1 and code <= KEY_9:
		return code - KEY_1
	return -1


## Key label of world index, blank for worlds without a key.
func _key_name(index: int) -> String:
	if index < 9:
		return str(index + 1)
	return "0" if index == 9 else "  "
# - revised 2026-10-25 (credits and licences)
