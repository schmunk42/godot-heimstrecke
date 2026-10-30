# file generated with AI assistance: Claude Code - 2026-10-27 17:06:13 UTC
extends Node
## The co-driver: reads the pace notes of the chosen route (pace_notes.gd)
## over the radio, the way the signs show them ("3 left open", "4 right
## into 5 left", "hairpin left, 150"). A curve is called when it is
## LEAD_S seconds ahead at the current speed (at least MIN_LEAD_M, at most
## MAX_LEAD_M), so a fast car hears it earlier. Curves linked by "into" or
## "and" are one call, as on the sign; a curve already passed is not
## called, and a jump along the route (R, F, a new start) starts over from
## the car's place.
##
## The voice is one short clip per word (clip_words()), looked for as
## <word>.wav or <word>.ogg in user://codriver/ and res://audio/codriver/
## and read from the file, so they need no import. A word without a clip
## is skipped (and reported once), a call without any clip is silent; the
## game has no voice files yet. The clips play on the bus "CoDriver", a
## radio: band-pass 400 to 3200 Hz and a little distortion.

const PACE_NOTES := preload("res://scripts/pace_notes.gd")
const LEAD_S := 6.0
const MIN_LEAD_M := 80.0
const MAX_LEAD_M := 500.0
## a change of the place along the route bigger than this is a jump
const RESYNC_M := 100.0
const BUS := "CoDriver"
const DIRS := ["user://codriver", "res://audio/codriver"]
const EXTENSIONS := ["wav", "ogg"]

## a call starts: the words as text
signal said(text: String)

var on := true:
	set(value):
		on = value
		if not on:
			_queue.clear()
			_player.stop()

var _marks: Node3D
var _car: RigidBody3D
var _notes: Array[Dictionary] = []
var _next := 0
var _last := -1.0
var _player := AudioStreamPlayer.new()
var _queue: Array[AudioStream] = []
var _clips := {}


## Every word the co-driver says: the grades, the directions, the
## modifiers, the links and the distances.
static func clip_words() -> Array[String]:
	var words: Array[String] = []
	for grade in range(1, 7):
		words.append(str(grade))
	words.append_array(["hairpin", "left", "right", "long", "tightens",
		"open", "into", "and"])
	for d: int in PACE_NOTES.DISTANCES:
		words.append(str(d))
	return words


## How far ahead a curve is called at `speed_kmh`.
static func lead_m(speed_kmh: float) -> float:
	return clampf(speed_kmh / 3.6 * LEAD_S, MIN_LEAD_M, MAX_LEAD_M)


## The call due at place `along` (m along the route) and `speed_kmh`,
## looking from note `next` on: "next" is the note to look at next time
## (past passed curves and the called ones), "words" the call when one is
## due, else missing. A curve linked "into" or "and" to the following
## ones takes them into its call.
static func due(notes: Array[Dictionary], next: int, along: float,
		speed_kmh: float) -> Dictionary:
	var i := next
	while i < notes.size() and notes[i].start_m < along:
		i += 1
	if i >= notes.size() or notes[i].start_m - along > lead_m(speed_kmh):
		return {"next": i}
	var words: Array[String] = []
	while true:
		words.append_array(notes[i].words)
		var chained: bool = notes[i].link in ["into", "and"]
		i += 1
		if not chained or i >= notes.size():
			break
	return {"next": i, "words": words}


## Reads the notes of `marks` (route_marks.gd, already built) for `car`.
func setup(marks: Node3D, car: RigidBody3D) -> void:
	_marks = marks
	_car = car
	_notes = marks.notes


func _ready() -> void:
	_add_bus()
	_player.bus = BUS
	_player.finished.connect(_play_next)
	add_child(_player)


func _physics_process(_delta: float) -> void:
	if _marks == null or _car == null or not on:
		return
	var along: float = _marks.progress(_car.global_position)
	if along < 0.0:
		return
	if _last < 0.0 or absf(along - _last) > RESYNC_M:
		_next = 0
		_queue.clear()
		_player.stop()
	_last = along
	var call := due(_notes, _next, along, _car.speed_kmh)
	_next = call.next
	if call.has("words"):
		say(call.words)


## Says `words`: queues their clips and starts playing when idle.
func say(words: Array[String]) -> void:
	said.emit(" ".join(words))
	for word in words:
		var clip := _clip(word)
		if clip != null:
			_queue.append(clip)
	if not _player.playing:
		_play_next()


func _play_next() -> void:
	if _queue.is_empty():
		return
	_player.stream = _queue.pop_front()
	_player.play()


## The clip of `word`, null (and a message once) when there is none.
func _clip(word: String) -> AudioStream:
	if not _clips.has(word):
		_clips[word] = _load(word)
		if _clips[word] == null:
			print("co-driver: no clip for \"%s\" in %s" % [word, DIRS])
	return _clips[word]


static func _load(word: String) -> AudioStream:
	for dir: String in DIRS:
		for extension: String in EXTENSIONS:
			var path := "%s/%s.%s" % [dir, word, extension]
			if not FileAccess.file_exists(path):
				continue
			if extension == "wav":
				return AudioStreamWAV.load_from_file(path)
			return AudioStreamOggVorbis.load_from_file(path)
	return null


func _add_bus() -> void:
	if AudioServer.get_bus_index(BUS) >= 0:
		return
	var index := AudioServer.bus_count
	AudioServer.add_bus(index)
	AudioServer.set_bus_name(index, BUS)
	var high := AudioEffectHighPassFilter.new()
	high.cutoff_hz = 400.0
	var low := AudioEffectLowPassFilter.new()
	low.cutoff_hz = 3200.0
	var crackle := AudioEffectDistortion.new()
	crackle.mode = AudioEffectDistortion.MODE_OVERDRIVE
	crackle.drive = 0.15
	for effect: AudioEffect in [high, low, crackle]:
		AudioServer.add_bus_effect(index, effect)
