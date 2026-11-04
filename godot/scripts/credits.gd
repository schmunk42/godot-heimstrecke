# file generated with AI assistance: Claude Code - 2026-10-25 18:30:00 UTC
extends Control
## Credits overlay of the world selection: the game's own licence, the
## data of the highlighted world (sources with credit, licence and link,
## the data licence of its tiles and tree files, the notice with the
## Copernicus liability sentence) and Godot with its third-party
## components and all their licence texts, which an exported game has to
## carry (godotengine.org/license). Scrolls; Esc, C or the button close
## it. Text only, so it reads the same in the software render.

signal closed

const GAME := "Heimstrecke"
const GAME_LICENCE := "Code: MIT License, Copyright (c) 2026 Tobias Munk. " \
	+ "Source, pipeline and world recipes: " \
	+ "https://github.com/schmunk42/godot-heimstrecke"
const VOICE_CREDIT := "Co-driver voice: synthesised with Piper " \
	+ "(https://github.com/OHF-Voice/piper1-gpl), voice en_US-norman-medium " \
	+ "by Bryce Beattie, trained on public domain LibriVox recordings; " \
	+ "the clips are under the MIT License of the game."

var _text: RichTextLabel


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var shade := ColorRect.new()
	shade.color = Color(0.03, 0.04, 0.05, 0.97)
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(shade)
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 32)
	add_child(margin)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	margin.add_child(column)
	_text = RichTextLabel.new()
	_text.bbcode_enabled = true
	_text.selection_enabled = true
	_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_text.add_theme_font_size_override("normal_font_size", 15)
	_text.add_theme_font_size_override("bold_font_size", 18)
	_text.meta_clicked.connect(func(meta: Variant): OS.shell_open(str(meta)))
	column.add_child(_text)
	var close := Button.new()
	close.text = "Close (Esc)"
	close.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	close.pressed.connect(_close)
	column.add_child(close)
	hide()


## Shows the credits for the world manifest `world` (empty: no world).
func open(world: Dictionary) -> void:
	_text.text = text_for(world)
	_text.scroll_to_line(0)
	show()
	_text.grab_focus()


## The whole credits text (BBCode) for the world manifest `world`.
static func text_for(world: Dictionary) -> String:
	var out := PackedStringArray()
	out.append("[b]%s[/b]\n%s\n%s\n" % [GAME, _escape(GAME_LICENCE),
		_escape(VOICE_CREDIT)])
	out.append(_world_text(world))
	out.append("[b]Godot Engine[/b]\nThis game uses Godot Engine, " \
		+ "available under the following license:\n")
	out.append(_escape(Engine.get_license_text()))
	out.append("\n[b]Third-party components of Godot Engine[/b]")
	for component: Dictionary in Engine.get_copyright_info():
		var licences := PackedStringArray()
		var holders := PackedStringArray()
		for part: Dictionary in component.parts:
			if not licences.has(str(part.license)):
				licences.append(str(part.license))
			for holder: String in part.copyright:
				holders.append(holder)
		out.append("%s: %s, © %s" % [_escape(str(component.name)),
			", ".join(licences), _escape("; ".join(holders))])
	out.append("\n[b]Licence texts[/b]")
	var texts: Dictionary = Engine.get_license_info()
	var names := texts.keys()
	names.sort()
	for name: String in names:
		out.append("\n[b]%s[/b]\n%s" % [_escape(name), _escape(texts[name])])
	return "\n".join(out)


static func _world_text(world: Dictionary) -> String:
	if world.is_empty():
		return "[b]World data[/b]\nNo world selected.\n"
	var out := PackedStringArray()
	out.append("[b]World data: %s[/b]" % _escape(
		str(world.get("name", world.get("id", "")))))
	for source: Dictionary in world.get("sources", []):
		out.append("%s (%s): %s  %s" % [_escape(str(source.name)),
			_escape(str(source.licence)), _escape(str(source.credit)),
			_link(str(source.url))])
	var licence: Variant = world.get("data_licence")
	if licence is Dictionary:
		out.append("Licence of %s: %s  %s" % [_escape(str(licence.covers)),
			_escape(str(licence.name)), _link(str(licence.url))])
	var notice := str(world.get("notice", ""))
	if not notice.is_empty():
		out.append(_escape(notice))
	elif world.has("attribution"):
		out.append(_escape(str(world.attribution)))
	return "\n".join(out) + "\n"


static func _link(url: String) -> String:
	if url.is_empty():
		return ""
	return "[url=%s]%s[/url]" % [url, _escape(url)]


## Square brackets of plain text would be read as BBCode.
static func _escape(text: String) -> String:
	return text.replace("[", "[lb]")


func _close() -> void:
	hide()
	closed.emit()


func _unhandled_input(event: InputEvent) -> void:
	if not visible or not (event is InputEventKey and event.pressed):
		return
	if event.keycode in [KEY_ESCAPE, KEY_C]:
		get_viewport().set_input_as_handled()
		_close()
