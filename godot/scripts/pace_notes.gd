# file generated with AI assistance: Claude Code - 2026-10-26 18:40:00 UTC
extends RefCounted
## Pace notes of a route, the way a rally co-driver reads them: every
## curve with its direction, a grade on a scale of 1 to 6 (6 the fastest
## and gentlest, 1 the slowest, below 1 a hairpin), the modifiers long,
## tightens and opens, and how it links to the next curve: "into" (no
## straight between), "and" (a short one) or the distance in metres. The
## curve signs (route_marks.gd) are built from the notes; the co-driver
## will call them.
##
## The route is resampled every STEP_M in x/z. The curvature at a sample
## is the heading change over WINDOW samples on either side (15 m), so a
## polyline corner at a junction reads as a turn of about 20 m radius
## instead of a kink. A curve is a run of samples bending the same way
## more than 1/MAX_RADIUS_M; runs of one direction with up to MERGE_GAP
## straight samples between them are one curve. Curves turning less than
## MIN_TURN_DEG are left out, and so are reversals (REVERSAL_DEG within
## REVERSAL_M: a route that runs to a waypoint and back). The window
## widens a run by 15 m at either end, so a curve starts where the raw
## heading change of its run (sample to sample) passes EDGE of its turn
## and ends where it passes 1 - EDGE; length, long and the straights
## between curves use these ends. The grade comes
## from the smallest radius in the curve (GRADES); a hairpin also turns
## at least HAIRPIN_DEG, a tighter curve that turns less is a 1.

const STEP_M := 5.0
const WINDOW := 3
const MAX_RADIUS_M := 400.0
const MERGE_GAP := 3
const MIN_TURN_DEG := 15.0
const REVERSAL_DEG := 170.0
const REVERSAL_M := 20.0
const EDGE := 0.05
## [radius below which, grade]; grade 0 is a hairpin
const GRADES := [[15.0, 0], [25.0, 1], [40.0, 2], [60.0, 3], [90.0, 4],
	[140.0, 5], [400.0, 6]]
const HAIRPIN_DEG := 135.0
## long: at least LONG_M and LONG_DEG
const LONG_M := 50.0
const LONG_DEG := 90.0
## tightens (opens): the smallest radius of the last third of the curve is
## below CHANGE times that of the first third (the other way round)
const CHANGE := 0.7
## the straight to the next curve: up to INTO_M "into", up to AND_M
## "and", else the largest of DISTANCES that is not longer
const INTO_M := 25.0
const AND_M := 60.0
const DISTANCES := [50, 80, 100, 150, 200, 250, 300, 400, 500, 600, 700,
	800, 1000]


## The notes of the route `points` ([x, y, z] in metres) in driving order,
## each a dictionary: start_m and end_m along the route (x/z), dir "left"
## or "right", grade 0 (hairpin) to 6, radius_m (the smallest), turn_deg,
## long, tightens, opens, gap_m to the next curve (-1 for the last), link
## ("into", "and" or "" with a distance), words, what a co-driver says as
## clip names (["3", "left", "long", "into"]), and call, the same as text
## ("3 left long into", "5 right, 150").
static func analyse(points: Array) -> Array[Dictionary]:
	var samples := _resample(points)
	var notes: Array[Dictionary] = []
	if samples.size() < 2 * WINDOW + 2:
		return notes
	var heading := PackedFloat32Array()
	for k in samples.size() - 1:
		var d := samples[k + 1] - samples[k]
		heading.append(atan2(d.x, -d.y))
	heading.append(heading[-1])
	var curve := PackedFloat32Array()
	for k in heading.size():
		var a := maxi(0, k - WINDOW)
		var b := mini(heading.size() - 1, k + WINDOW)
		curve.append(wrapf(heading[b] - heading[a], -PI, PI)
			/ ((b - a) * STEP_M) if b > a else 0.0)
	for run in _runs(curve):
		var note := _note(run, heading, curve)
		if not note.is_empty():
			notes.append(note)
	for i in notes.size():
		_link(notes, i)
	return notes


## The route in x/z, one point every STEP_M along it.
static func _resample(points: Array) -> PackedVector2Array:
	var out := PackedVector2Array()
	if points.size() < 2:
		return out
	var prev := Vector2(points[0][0], points[0][2])
	out.append(prev)
	var carried := 0.0
	for i in range(1, points.size()):
		var next := Vector2(points[i][0], points[i][2])
		var length := prev.distance_to(next)
		var t := STEP_M - carried
		while t <= length:
			out.append(prev.lerp(next, t / length))
			t += STEP_M
		carried = length - (t - STEP_M)
		prev = next
	return out


## [first, last, sign] of every run of samples bending one way, sign 1
## to the right and -1 to the left, short gaps merged.
static func _runs(curve: PackedFloat32Array) -> Array:
	var runs := []
	var k := 0
	var bend := 1.0 / MAX_RADIUS_M
	while k < curve.size():
		if absf(curve[k]) < bend:
			k += 1
			continue
		var sign := signf(curve[k])
		var first := k
		while k < curve.size() and curve[k] * sign >= bend:
			k += 1
		if not runs.is_empty() and runs[-1][2] == sign \
				and first - runs[-1][1] <= MERGE_GAP + 1:
			runs[-1][1] = k - 1
		else:
			runs.append([first, k - 1, sign])
	return runs


## The note of `run`, empty for a curve too slight, a reversal or one too
## wide for the scale.
static func _note(run: Array, heading: PackedFloat32Array,
		curve: PackedFloat32Array) -> Dictionary:
	var first: int = run[0]
	var last: int = run[1]
	var turned := PackedFloat32Array([0.0])
	for k in range(first, mini(last + 1, heading.size() - 1)):
		turned.append(turned[-1]
			+ wrapf(heading[k + 1] - heading[k], -PI, PI))
	var turn := turned[-1]
	var turn_deg := absf(rad_to_deg(turn))
	# turned[j] is the turn up to the vertex first + j
	var begin := 1
	while begin < turned.size() - 1 \
			and absf(turned[begin]) < EDGE * absf(turn):
		begin += 1
	var end := begin
	while end < turned.size() - 1 \
			and absf(turned[end]) < (1.0 - EDGE) * absf(turn):
		end += 1
	var length := (end - begin) * STEP_M
	if turn_deg < MIN_TURN_DEG \
			or (turn_deg >= REVERSAL_DEG and length <= REVERSAL_M):
		return {}
	var radius := 1.0 / _sharpest(curve, first, last + 1)
	var grade := -1
	for limit: Array in GRADES:
		if radius < limit[0]:
			grade = limit[1]
			break
	if grade < 0:
		return {}
	if grade == 0 and turn_deg < HAIRPIN_DEG:
		grade = 1
	var third := maxi(1, (last - first + 1) / 3)
	var entry := 1.0 / _sharpest(curve, first, first + third)
	var exit := 1.0 / _sharpest(curve, last + 1 - third, last + 1)
	return {"start_m": (first + begin) * STEP_M,
		"end_m": (first + end) * STEP_M,
		"dir": "right" if run[2] > 0.0 else "left", "grade": grade,
		"radius_m": snappedf(radius, 0.1), "turn_deg": roundf(turn_deg),
		"long": grade > 0 and length >= LONG_M and turn_deg >= LONG_DEG,
		"tightens": exit < CHANGE * entry, "opens": entry < CHANGE * exit,
		"gap_m": -1.0, "link": "", "words": [], "call": ""}


## The largest curvature of samples [from, to).
static func _sharpest(curve: PackedFloat32Array, from: int,
		to: int) -> float:
	var most := 0.0
	for k in range(from, to):
		most = maxf(most, absf(curve[k]))
	return maxf(most, 1e-6)


## Fills gap_m, link and call of note `i` from the next note.
static func _link(notes: Array[Dictionary], i: int) -> void:
	var note := notes[i]
	var words: Array = ["hairpin", note.dir] if note.grade == 0 \
		else [str(note.grade), note.dir]
	for modifier in ["long", "tightens", "opens"]:
		if note[modifier]:
			words.append("open" if modifier == "opens" else modifier)
	var distance := ""
	if i + 1 < notes.size():
		var gap: float = notes[i + 1].start_m - note.end_m
		note.gap_m = gap
		if gap <= INTO_M:
			note.link = "into"
			words.append("into")
		elif gap <= AND_M:
			note.link = "and"
			words.append("and")
		else:
			var said: int = DISTANCES[0]
			for d: int in DISTANCES:
				if d <= gap:
					said = d
			distance = str(said)
			words.append(distance)
	note.words = words
	note.call = " ".join(words) if distance.is_empty() \
		else " ".join(words.slice(0, -1)) + ", " + distance
