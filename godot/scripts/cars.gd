# file generated with AI assistance: Claude Code - 2026-10-22 15:30:00 UTC
extends RefCounted
## The cars of the start menu: three versions of the 1980s Audi quattro
## and the Lamborghini Huracán STO. car.gd reads physics, drivetrain and
## engine from an entry, car_model.gd the body, car_audio.gd the sound.
##
## Keys of an entry:
##   name, body (car_model.gd BODIES), paint, rim colour
##   wheels: mounts relative to the car origin, front pair first
##   rest, radius: suspension travel and tyre radius (m), one radius for
##     all four wheels; tyre_width: front, rear (m) for the model
##   mass, spring, damper, mu (tyre grip), brake (total force, N)
##   drag: half rho * cd * area; downforce: the same for the down force
##   com_y, com_z: centre of mass (height, behind the wheelbase centre)
##   box/box_y: collision box size and height
##   gears, reverse, final_drive, driveline (efficiency)
##   front_drive: share of the drive force on the front axle
##   idle, redline, launch_rpm (clutch slip in first and reverse),
##   shift_s, downshift_rpm, kickdown_rpm (pull a gear down at full
##   pedal below this), torque: full-load curve [rpm, Nm]
##   boost_rpm, lag_s, boost: turbo builds above boost_rpm with the time
##     constant lag_s and adds the share boost of the torque; 0 = none
##   firing: firing pulses per crank turn (cylinders / 2), orders: extra
##     tones [share of the firing frequency, level] for car_audio.gd
##
## Audi peaks from the data sheets: quattro WR 147 kW at 5500/min and
## 285 Nm at 3500/min, 20V RR 162 kW at 5900/min and 309 Nm at 1950/min,
## Sport quattro 225 kW at 6700/min and 350 Nm at 3700/min; the points in
## between are estimates. The final drive of the long quattro is an
## assumption that puts its top speed near the power peak in 5th.
## From the route start (the smoke test) they do 0-100 km/h in 6.8 / 6.2
## / 4.9 s (data sheets: 7.1 / 6.3 / 4.9 s).
##
## Huracán STO from Lamborghini's data sheet and the auto motor und sport
## test table: 5.2 l V10 without turbo, 470 kW at 8000/min, 565 Nm at
## 6500/min, rear-wheel drive, 7-speed dual clutch, 245/30 R20 front and
## 305/30 R20 rear, track 1688 / 1647 mm, wheelbase 2620 mm, 1339 kg
## dry and about 1450 kg ready to drive, about 58 % of it on the rear
## axle (the centre of mass 0.2 m behind the middle), 420 kg down force
## at 280 km/h, 0-100 km/h in 3.0 s, 310 km/h. The table lists the
## gears as 3.31, 2.59, 1.88, 1.14, 0.98, 0.98, 0.84 (a doubled 0.98 and
## no step between 1.88 and 1.14): 4th is taken as 1.47 and 5th as 1.14.
## Drag and down force are fitted to the top speed and the 420 kg.

const QUATTRO_WHEELS := [
	Vector3(-0.71, -0.1, -1.2625), Vector3(0.71, -0.1, -1.2625),
	Vector3(-0.73, -0.1, 1.2625), Vector3(0.73, -0.1, 1.2625)]
## five-cylinder: firing at 2.5 per crank turn, the 0.5 and 1.5 crank
## orders (1/5 and 3/5 of the firing frequency) make the warble
const FIVE_ORDERS := [[0.2, 0.3], [0.6, 0.25]]
const QUATTRO_GEARS := [3.600, 2.125, 1.360, 0.971, 0.778]

const CARS: Array[Dictionary] = [
	{"name": "Audi quattro WR, 200 PS", "body": "quattro",
	"paint": Color(0.66, 0.67, 0.69), "rim": Color(0.75, 0.76, 0.78),
	# wheelbase 2.525 m, track about 1.42 m front and 1.46 m rear,
	# 205/60 R 15
	"wheels": QUATTRO_WHEELS, "rest": 0.40, "radius": 0.314,
	"tyre_width": [0.205, 0.205],
	"mass": 1335.0, "spring": 36000.0, "damper": 3200.0, "mu": 1.15,
	"brake": 20000.0,
	# cd 0.43, frontal area 1.85 m2
	"drag": 0.48, "downforce": 0.0,
	"com_y": -0.35, "com_z": 0.0, "box": Vector3(1.7, 0.6, 4.3), "box_y": -0.15,
	"gears": QUATTRO_GEARS, "reverse": 3.5, "final_drive": 3.889,
	"driveline": 0.88, "front_drive": 0.5,
	"idle": 900.0, "redline": 6500.0, "launch_rpm": 3000.0,
	"shift_s": 0.45, "downshift_rpm": 2600.0, "kickdown_rpm": 3200.0,
	"torque": [[900, 130], [2000, 200], [3000, 270], [3500, 285],
		[4500, 280], [5500, 255], [6500, 205]],
	"boost_rpm": 2200.0, "lag_s": 0.6, "boost": 0.4,
	"firing": 2.5, "orders": FIVE_ORDERS},
	{"name": "Audi quattro 20V, 220 PS", "body": "quattro",
	"paint": Color(0.78, 0.05, 0.06), "rim": Color(0.55, 0.57, 0.6),
	"wheels": QUATTRO_WHEELS, "rest": 0.40, "radius": 0.314,
	"tyre_width": [0.215, 0.215],
	"mass": 1350.0, "spring": 36000.0, "damper": 3200.0, "mu": 1.15,
	"brake": 20000.0, "drag": 0.48, "downforce": 0.0,
	"com_y": -0.35, "com_z": 0.0, "box": Vector3(1.7, 0.6, 4.3), "box_y": -0.15,
	"gears": QUATTRO_GEARS, "reverse": 3.5, "final_drive": 3.889,
	"driveline": 0.88, "front_drive": 0.5,
	"idle": 900.0, "redline": 6900.0, "launch_rpm": 2600.0,
	"shift_s": 0.45, "downshift_rpm": 2600.0, "kickdown_rpm": 3200.0,
	"torque": [[900, 150], [1950, 309], [3500, 309], [4500, 300],
		[5900, 262], [6900, 215]],
	"boost_rpm": 2000.0, "lag_s": 0.5, "boost": 0.4,
	"firing": 2.5, "orders": FIVE_ORDERS},
	{"name": "Audi Sport quattro, 306 PS", "body": "sport_quattro",
	"paint": Color(0.93, 0.93, 0.91), "rim": Color(0.92, 0.92, 0.9),
	# wheelbase 2.224 m (30 cm shorter; some sources give 2.204 m),
	# 1.78 m wide, 235/45 VR 15
	"wheels": [
		Vector3(-0.74, -0.1, -1.112), Vector3(0.74, -0.1, -1.112),
		Vector3(-0.76, -0.1, 1.112), Vector3(0.76, -0.1, 1.112)],
	"rest": 0.40, "radius": 0.296, "tyre_width": [0.235, 0.235],
	"mass": 1300.0, "spring": 38000.0, "damper": 3300.0, "mu": 1.18,
	"brake": 21000.0, "drag": 0.48, "downforce": 0.0,
	"com_y": -0.35, "com_z": 0.0, "box": Vector3(1.75, 0.6, 4.05), "box_y": -0.15,
	"gears": QUATTRO_GEARS, "reverse": 3.5, "final_drive": 3.889,
	"driveline": 0.88, "front_drive": 0.5,
	"idle": 900.0, "redline": 7500.0, "launch_rpm": 4300.0,
	"shift_s": 0.45, "downshift_rpm": 2600.0, "kickdown_rpm": 3200.0,
	"torque": [[900, 110], [2500, 210], [3700, 350], [5000, 345],
		[6700, 321], [7500, 270]],
	"boost_rpm": 2800.0, "lag_s": 0.8, "boost": 0.5,
	"firing": 2.5, "orders": FIVE_ORDERS},
	{"name": "Lamborghini Huracán STO, 640 PS", "body": "sto",
	"paint": Color(0.30, 0.66, 0.84), "rim": Color(0.06, 0.06, 0.07),
	"wheels": [
		Vector3(-0.84, -0.1, -1.31), Vector3(0.84, -0.1, -1.31),
		Vector3(-0.82, -0.1, 1.31), Vector3(0.82, -0.1, 1.31)],
	"rest": 0.30, "radius": 0.337, "tyre_width": [0.245, 0.305],
	"mass": 1450.0, "spring": 55000.0, "damper": 4500.0, "mu": 1.35,
	"brake": 27000.0, "drag": 0.64, "downforce": 0.68,
	"com_y": -0.36, "com_z": 0.2, "box": Vector3(1.9, 0.55, 4.4), "box_y": -0.26,
	"gears": [3.31, 2.59, 1.88, 1.47, 1.14, 0.98, 0.84], "reverse": 2.65,
	"final_drive": 3.94, "driveline": 0.9, "front_drive": 0.0,
	"idle": 1000.0, "redline": 8500.0, "launch_rpm": 4500.0,
	"shift_s": 0.12, "downshift_rpm": 3800.0, "kickdown_rpm": 5000.0,
	"torque": [[1000, 330], [3000, 450], [4500, 510], [6500, 565],
		[8000, 561], [8500, 520]],
	"boost_rpm": 0.0, "lag_s": 1.0, "boost": 0.0,
	# even-firing V10: five pulses per crank turn, the bank beat at half
	# the firing frequency and a rasp at one and a half
	"firing": 5.0, "orders": [[0.5, 0.18], [1.5, 0.22]]},
]
