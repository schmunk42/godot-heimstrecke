# file generated with AI assistance: Claude Code - 2026-10-21 02:05:00 UTC
extends Node
## Synthesised car sounds, no audio files: the engine at the firing
## frequency rpm / 60 * `firing` of the car's cars.gd entry with its extra
## `orders` (the warble of the Audi five-cylinder, the bank beat of the
## V10), turbo whistle with the boost and a blow-off hiss when the pedal
## comes up under boost, road noise, tyre squeal on slip and a thud on
## hard impacts. Reads spec, speed_kmh, rpm, gear, boost, throttle_input,
## slip and linear_velocity from the parent car.
##
## The rumble: every firing pulse is a decaying exhaust beat with its own
## random strength (lumpy at idle, even near the redline) and a burst of
## combustion noise under load, plus the half crank order of the four-
## stroke cycle underneath. A resonant low-pass, opened by the pedal and
## the engine speed, is the exhaust, a soft clipper the warmth.
##
## Backfires: an upshift cuts the ignition for the shift time and bangs
## once or twice, a downshift crackles three to six times, lifting off at
## high revs pops two to five times and the overrun keeps crackling now
## and then. Each pop is a noise crack over a falling thump.

const MIX_RATE := 22050.0
const BUFFER_S := 0.1
const SQUEAL_SLIP := 2.5
const IMPACT_DV := 4.0
## overrun pops above this share of the redline
const POP_RPM := 0.5
## random overrun crackles per second at full rpm with the pedal up
const CRACKLE_RATE := 1.2

var _car: RigidBody3D
var _playback: AudioStreamGeneratorPlayback
var _last_velocity := Vector3.ZERO
var _rng := RandomNumberGenerator.new()

# targets, set per frame in _update
var _freq_target := 37.5
var _motor_target := 0.0
var _load_target := 0.0
var _whistle_target := 0.0
var _road_target := 0.0
var _squeal_target := 0.0
var _rev := 0.0
var _last_throttle := 0.0
var _last_gear := 1
var _cut_left := 0.0

# smoothed parameters and oscillator state
var _freq := 37.5
var _motor := 0.0
var _load := 0.0
var _whistle := 0.0
var _blowoff := 0.0
var _road := 0.0
var _squeal := 0.0
var _impact := 0.0
var _phase := [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
var _noise_lp := 0.0
var _thud_lp := 0.0
var _beat := 1.0
var _lp_low := 0.0
var _lp_band := 0.0
var _dc := 0.0

# backfires: pops still to come, seconds to the next, their strength
var _pops_left := 0
var _pop_wait := 0.0
var _pop_gap := Vector2(0.05, 0.12)
var _pop_strength := 0.0
var _pop_env := 0.0
var _pop_lp := 0.0


func _ready() -> void:
	_car = get_parent()
	var stream := AudioStreamGenerator.new()
	stream.mix_rate = MIX_RATE
	stream.buffer_length = BUFFER_S
	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.volume_db = -4.0
	add_child(player)
	player.play()
	_playback = player.get_stream_playback()


func _physics_process(_delta: float) -> void:
	var dv := (_car.linear_velocity - _last_velocity).length()
	_last_velocity = _car.linear_velocity
	if dv > IMPACT_DV and not _car.freeze:
		_impact = minf(1.0, maxf(_impact, (dv - IMPACT_DV) / 8.0 + 0.3))


func _process(delta: float) -> void:
	if _playback == null:
		return
	_update(delta)
	_playback.push_buffer(_render(_playback.get_frames_available()))


## Targets from the car, shift and lift-off backfires.
func _update(delta: float) -> void:
	var speed: float = _car.speed_kmh / 3.6
	var throttle: float = _car.throttle_input
	var running := 0.0 if _car.freeze else 1.0
	var spec: Dictionary = _car.spec
	var gear: int = _car.gear
	_rev = minf(_car.rpm / spec.redline, 1.0)
	_cut_left = maxf(0.0, _cut_left - delta)

	if running > 0.0 and gear > 0 and _last_gear > 0 and speed > 2.0:
		if gear == _last_gear + 1 and throttle > 0.3:
			# ignition cut for the shift, the unburnt mixture bangs
			_cut_left = spec.shift_s
			_backfire(1 + _rng.randi() % 2, 1.0, Vector2(0.03, 0.09))
		elif gear == _last_gear - 1:
			_backfire(3 + _rng.randi() % 4, 0.65, Vector2(0.04, 0.14))
	_last_gear = gear
	if _last_throttle - throttle > 0.5 and _rev > POP_RPM and running > 0.0:
		_backfire(2 + _rng.randi() % 4, 0.55, Vector2(0.05, 0.16))
	elif throttle < 0.05 and _rev > POP_RPM and _pops_left == 0 \
			and running > 0.0 and _rng.randf() < CRACKLE_RATE * delta \
			* (_rev - POP_RPM) / (1.0 - POP_RPM):
		_backfire(1, 0.35, _pop_gap)

	_freq_target = _car.rpm / 60.0 * spec.firing
	var cut := 0.25 if _cut_left > 0.0 else 1.0
	_motor_target = (0.1 + 0.12 * throttle * cut + 0.05 * _rev) * running
	_load_target = throttle * cut
	_whistle_target = 0.05 * _car.boost * throttle * running
	if _last_throttle - throttle > 0.5 and _car.boost > 0.5:
		_blowoff = 0.25 * _car.boost * running
	_last_throttle = throttle
	_road_target = 0.18 * minf(speed / 50.0, 1.0) * running
	_squeal_target = 0.0
	if speed > 3.0:
		_squeal_target = clampf((_car.slip - SQUEAL_SLIP) / 6.0, 0.0, 1.0) \
			* 0.22 * running


## Queue `count` pops of `strength` with gaps in `gap` (s); a weaker
## series does not replace a running one.
func _backfire(count: int, strength: float, gap: Vector2) -> void:
	if _pops_left > 0 and strength < _pop_strength:
		return
	_pops_left = count
	_pop_strength = strength
	_pop_gap = gap
	_pop_wait = _rng.randf_range(gap.x, gap.y)


func _render(frames: int) -> PackedVector2Array:
	var out := PackedVector2Array()
	out.resize(frames)
	var spec: Dictionary = _car.spec
	var orders: Array = spec.orders
	var firing: float = spec.firing
	var dt := 1.0 / MIX_RATE
	var smooth := 1.0 / (0.05 * MIX_RATE)
	# lumpy pulses at idle, even ones at high revs
	var lump := 0.35 * (1.0 - _rev) + 0.08
	var pop_decay := 1.0 - 1.0 / (0.045 * MIX_RATE)
	for i in frames:
		_freq += (_freq_target - _freq) * smooth
		_motor += (_motor_target - _motor) * smooth
		_load += (_load_target - _load) * smooth
		_whistle += (_whistle_target - _whistle) * smooth
		_blowoff *= 1.0 - 1.0 / (0.35 * MIX_RATE)
		_road += (_road_target - _road) * smooth
		_squeal += (_squeal_target - _squeal) * smooth * 2.0
		_impact *= 1.0 - 1.0 / (0.25 * MIX_RATE)
		var noise := _rng.randf_range(-1.0, 1.0)

		# exhaust beat: a decaying pulse per firing, new strength each time
		var p: float = _phase[0] + _freq * dt
		if p >= 1.0:
			p -= 1.0
			_beat = 1.0 + lump * _rng.randf_range(-1.0, 1.0)
		_phase[0] = p
		var env := exp(-p * (5.0 + 4.0 * _load))
		var beat := _beat * (env * (1.0 + 0.6 * _load * noise) - 0.3)
		var motor: float = beat + 0.55 * _osc(8, _freq / firing * 0.5) \
			+ 0.25 * _osc(1, _freq * 2.0) \
			+ orders[0][1] * _osc(2, _freq * orders[0][0]) \
			+ orders[1][1] * _osc(6, _freq * orders[1][0])
		# exhaust: resonant low-pass, opened by pedal and revs
		var cutoff := minf(160.0 + _freq * (1.2 + 2.5 * _load), 3000.0)
		var f := 2.0 * sin(PI * cutoff * dt)
		_lp_low += f * _lp_band
		_lp_band += f * (motor - _lp_low - 0.9 * _lp_band)
		_dc += (_lp_low - _dc) * 0.002
		var engine := (_lp_low - _dc) * 1.6

		# backfires
		if _pops_left > 0:
			_pop_wait -= dt
			if _pop_wait <= 0.0:
				_pops_left -= 1
				_pop_env = _pop_strength * _rng.randf_range(0.6, 1.0)
				_pop_wait = _rng.randf_range(_pop_gap.x, _pop_gap.y)
		var pop := 0.0
		if _pop_env > 0.001:
			_pop_lp += (noise - _pop_lp) * 0.3
			var thump := _osc(9, 45.0 + 120.0 * _pop_env / _pop_strength)
			pop = (_pop_lp * 1.8 + thump) * _pop_env
			_pop_env *= pop_decay

		var whistle := _osc(7, 2400.0 + 3500.0 * _car.boost) \
			* (0.8 + 0.2 * noise)
		var hiss := noise * _blowoff
		_noise_lp += (noise - _noise_lp) * 0.08
		var vibrato := 1.0 + 0.04 * _osc(4, 7.0)
		var squeal := _osc(3, 950.0 * vibrato) * (0.8 + 0.2 * noise)
		_thud_lp += (noise - _thud_lp) * 0.02
		var thud := (_thud_lp * 4.0 + _osc(5, 55.0)) * _impact

		var v: float = engine * _motor + pop * 0.9 \
			+ whistle * _whistle + hiss \
			+ _noise_lp * 2.5 * _road \
			+ squeal * _squeal + thud * 0.6
		# soft clip: warm instead of a hard edge
		v = tanh(v * 1.3) * 0.9
		out[i] = Vector2(v, v)
	return out


func _osc(i: int, freq: float) -> float:
	_phase[i] = fmod(_phase[i] + freq / MIX_RATE, 1.0)
	return sin(TAU * _phase[i])
