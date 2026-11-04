# file generated with AI assistance: Claude Code - 2026-10-27 17:20:00 UTC
extends SceneTree
## Checks co_driver.gd without a world: when a call is due at a speed, a
## passed curve is not called, curves linked into one are one call, a
## grade and its direction (after a link too) are one phrase clip, the
## words of the notes of a drawn route all have a clip name, every clip
## name has its Ogg clip in res://audio/codriver/ and the clip loader
## reads a wav file. Exit code 1 on a failure.
##
##   godot --headless --path godot --script res://tests/co_driver_test.gd

const CO_DRIVER := preload("res://scripts/co_driver.gd")
const PACE_NOTES := preload("res://scripts/pace_notes.gd")

var _failed := false


func _initialize() -> void:
	var notes: Array[Dictionary] = [
		_note(500.0, ["4", "right", "into"], "into"),
		_note(540.0, ["3", "left", "open"], ""),
		_note(900.0, ["hairpin", "left"], "")]
	_expect("far", CO_DRIVER.due(notes, 0, 100.0, 50.0), {"next": 0})
	_expect("lead at 50 km/h", CO_DRIVER.lead_m(50.0), 83.33333)
	_expect("min lead", CO_DRIVER.lead_m(10.0), 80.0)
	_expect("max lead", CO_DRIVER.lead_m(300.0), 500.0)
	_expect("near, slow", CO_DRIVER.due(notes, 0, 400.0, 30.0),
		{"next": 0})
	_expect("near, fast", CO_DRIVER.due(notes, 0, 400.0, 120.0), {"next": 2,
		"words": ["4", "right", "into", "3", "left", "open"]})
	_expect("passed", CO_DRIVER.due(notes, 0, 600.0, 50.0), {"next": 2})
	_expect("last", CO_DRIVER.due(notes, 2, 850.0, 50.0),
		{"next": 3, "words": ["hairpin", "left"]})
	_expect("none left", CO_DRIVER.due(notes, 3, 950.0, 50.0), {"next": 3})

	var clips := CO_DRIVER.clip_words()
	var seen := {}
	for word in clips:
		seen[word] = true
	_expect("no duplicate clips", seen.size(), clips.size())
	_expect("the drawn route has notes",
		PACE_NOTES.analyse(_route()).size() > 0, true)
	var missing := _words_without_clip(clips)
	_expect("every word has a clip name", missing, [])
	_expect("every clip is in the game", _clips_missing(clips), [])
	var has := func(name: String) -> bool: return name in clips
	_expect("phrases", CO_DRIVER.clip_names(["4", "right", "into", "3",
		"left", "open"], has), ["4_right", "into_3_left", "open"])
	_expect("hairpin phrase and distance", CO_DRIVER.clip_names(
		["hairpin", "left", "150"], has), ["hairpin_left", "150"])
	_expect("words without a phrase", CO_DRIVER.clip_names(
		["4", "right"], func(_name: String) -> bool: return false),
		["4", "right"])

	var path := "user://co_driver_test.wav"
	_write_wav(path)
	var stream := AudioStreamWAV.load_from_file(path)
	_expect("wav loads", stream != null and stream.get_length() > 0.0, true)
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))

	print("CO-DRIVER " + ("FAILED" if _failed else "OK"))
	quit(1 if _failed else 0)


func _note(start: float, words: Array, link: String) -> Dictionary:
	return {"start_m": start, "words": words, "link": link}


## the words of the calls of a few curves that are not in clip_words()
func _words_without_clip(clips: Array[String]) -> Array:
	var missing := []
	var route := _route()
	for note in PACE_NOTES.analyse(route):
		for word: String in note.words:
			if word not in clips:
				missing.append(word)
	return missing


## the clip names without a playable clip in res://audio/codriver/ (made
## by tools/codriver_voice.py)
func _clips_missing(clips: Array[String]) -> Array:
	var missing := []
	for word in clips:
		var path := "res://audio/codriver/%s.ogg" % word
		var stream := AudioStreamOggVorbis.load_from_file(path) \
			if FileAccess.file_exists(path) else null
		if stream == null or stream.get_length() <= 0.0:
			missing.append(word)
	return missing


## a route with curves of every kind: 90° at 30 m, a hairpin, an S-bend
func _route() -> Array:
	var points: Array = []
	var pos := Vector2.ZERO
	var dir := Vector2(0, -1)
	for turn in [[0.0, 0.0, 100.0], [30.0, -PI / 2.0, 0.0],
			[12.0, PI, 0.0], [70.0, PI / 3.0, 0.0], [50.0, -PI / 3.0, 0.0],
			[300.0, -deg_to_rad(20.0), 0.0], [0.0, 0.0, 100.0]]:
		var radius: float = turn[0]
		var angle: float = turn[1]
		if radius == 0.0:
			for m in range(0, int(turn[2])):
				points.append([pos.x, 0.0, pos.y])
				pos += dir
			continue
		var steps := int(absf(angle) * radius)
		for k in steps:
			points.append([pos.x, 0.0, pos.y])
			dir = dir.rotated(angle / steps)
			pos += dir
	return points


func _write_wav(path: String) -> void:
	var samples := PackedByteArray()
	samples.resize(2205 * 2)
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_buffer("RIFF".to_ascii_buffer())
	file.store_32(36 + samples.size())
	file.store_buffer("WAVEfmt ".to_ascii_buffer())
	file.store_32(16)
	file.store_16(1)
	file.store_16(1)
	file.store_32(22050)
	file.store_32(44100)
	file.store_16(2)
	file.store_16(16)
	file.store_buffer("data".to_ascii_buffer())
	file.store_32(samples.size())
	file.store_buffer(samples)
	file.close()


func _expect(name: String, got: Variant, want: Variant) -> void:
	var ok: bool = is_equal_approx(got, want) if got is float else got == want
	_failed = _failed or not ok
	print("  %s  %s%s" % ["ok  " if ok else "FAIL", name,
		"" if ok else ": got %s, want %s" % [got, want]])
