# file generated with AI assistance: Claude Code - 2026-10-22 15:30:00 UTC
extends RefCounted
## The cars of the start menu: three versions of the 1980s Audi quattro,
## the Lamborghini Huracán STO, the Subaru Impreza WRX STI, the VW Golf
## II GTI 16V, the Ferrari F40 and the Porsche 911 GT3 RS. car.gd reads
## physics, drivetrain and engine from an entry, car_model.gd the body,
## car_audio.gd the sound. The menu shows made-up names, not the makes
## and models: those are trademarks, see docs/licences.md#vehicles. The
## comments below name the real cars the data comes from.
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
##
## Subaru Impreza WRX STI (GD, EU 2003-2005): EJ207 boxer turbo, 195 kW
## at 6000/min, 343 Nm at 4000/min, 1470 kg DIN, 58 % on the front axle,
## four-wheel drive with the base split of the DCCD centre diff, 35/65.
## The gears are the Japanese set (Subaru catalogue), assumed for the EU
## car; the redline of 8000/min is read off the rev counter.
## Golf II GTI 16V (KR, without catalyst): 102 kW at 6100/min, 168 Nm
## at 4600/min and at least 160 Nm from 2800 to 6100/min, 1035 kg (EU),
## front-wheel drive, the gears of the catalyst car (auto motor und
## sport). Ferrari F40: 2.9 l V8 with two turbos and a flat-plane crank,
## 352 kW at 7000/min, 577 Nm at 4000/min, 1254 kg (EU), mid engine,
## rear-wheel drive; the gear ratios come from forums, the final drive
## is fitted to 324 km/h at 7000/min in 5th (the published 2.727 leaves
## out a drop gear). Porsche 911 GT3 RS (992): 4.0 l flat six without
## turbo, 386 kW at 8500/min, 465 Nm at 6300/min, 9000/min, 1450 kg DIN,
## engine behind the rear axle (about 61 % on it), 409 kg down force at
## 200 km/h; Porsche publishes no ratios, the 992 GT3 gears are taken
## and the final drive fitted to 296 km/h at 9000/min in 7th. The
## torque curves between the peaks, idle speeds, weight distributions
## (except the Impreza) and tyre grip are estimates; the drag of the
## Impreza, the Golf and the F40 is fitted to the top speed. From the
## route start they do 0-100 km/h in 5.2 / 7.5 / 4.4 / 3.0 s (data
## sheets: 5.5 / 8.5 / 4.6 / 3.2 s).

const QUATTRO_WHEELS := [
	Vector3(-0.71, -0.1, -1.2625), Vector3(0.71, -0.1, -1.2625),
	Vector3(-0.73, -0.1, 1.2625), Vector3(0.73, -0.1, 1.2625)]
## five-cylinder: firing at 2.5 per crank turn, the 0.5 and 1.5 crank
## orders (1/5 and 3/5 of the firing frequency) make the warble
const FIVE_ORDERS := [[0.2, 0.3], [0.6, 0.25]]
const QUATTRO_GEARS := [3.600, 2.125, 1.360, 0.971, 0.778]

const CARS: Array[Dictionary] = [
	{"name": "Rally Coupé Turbo, 200 PS", "body": "quattro",
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
	{"name": "Rally Coupé 20V, 220 PS", "body": "quattro",
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
	{"name": "Rally Coupé Short, 306 PS", "body": "sport_quattro",
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
	{"name": "Wedge V10, 640 PS", "body": "sto",
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
	{"name": "Boxer Saloon Turbo, 265 PS", "body": "impreza",
	"paint": Color(0.08, 0.2, 0.55), "rim": Color(0.78, 0.62, 0.28),
	# wheelbase 2.525 m, track 1.49 / 1.48 m, 225/45 R 17
	"wheels": [
		Vector3(-0.745, -0.1, -1.2625), Vector3(0.745, -0.1, -1.2625),
		Vector3(-0.74, -0.1, 1.2625), Vector3(0.74, -0.1, 1.2625)],
	"rest": 0.40, "radius": 0.317, "tyre_width": [0.225, 0.225],
	"mass": 1470.0, "spring": 40000.0, "damper": 3700.0, "mu": 1.2,
	"brake": 24000.0, "drag": 0.50, "downforce": 0.0,
	"com_y": -0.33, "com_z": -0.2, "box": Vector3(1.72, 0.6, 4.35),
	"box_y": -0.15,
	"gears": [3.636, 2.375, 1.761, 1.346, 1.062, 0.842], "reverse": 3.545,
	"final_drive": 3.9, "driveline": 0.85, "front_drive": 0.35,
	"idle": 800.0, "redline": 8000.0, "launch_rpm": 4000.0,
	"shift_s": 0.4, "downshift_rpm": 3000.0, "kickdown_rpm": 4000.0,
	"torque": [[800, 150], [2000, 200], [3000, 270], [4000, 343],
		[5000, 335], [6000, 310], [7000, 265], [8000, 215]],
	"boost_rpm": 2800.0, "lag_s": 0.6, "boost": 0.5,
	# flat four with unequal-length headers: the rumble at the first and
	# half crank order (1/2 and 1/4 of the firing frequency)
	"firing": 2.0, "orders": [[0.5, 0.35], [0.25, 0.2]]},
	{"name": "Hot Hatch 16V, 139 PS", "body": "golf",
	"paint": Color(0.05, 0.05, 0.06), "rim": Color(0.6, 0.62, 0.65),
	# wheelbase 2.475 m, track 1.427 / 1.422 m, 185/60 R 14
	"wheels": [
		Vector3(-0.71, -0.1, -1.2375), Vector3(0.71, -0.1, -1.2375),
		Vector3(-0.71, -0.1, 1.2375), Vector3(0.71, -0.1, 1.2375)],
	"rest": 0.38, "radius": 0.289, "tyre_width": [0.185, 0.185],
	"mass": 1035.0, "spring": 30000.0, "damper": 2600.0, "mu": 1.05,
	"brake": 14000.0, "drag": 0.43, "downforce": 0.0,
	"com_y": -0.30, "com_z": -0.3, "box": Vector3(1.66, 0.6, 3.95),
	"box_y": -0.12,
	"gears": [3.46, 2.12, 1.44, 1.13, 0.91], "reverse": 3.17,
	"final_drive": 3.67, "driveline": 0.9, "front_drive": 1.0,
	"idle": 900.0, "redline": 6800.0, "launch_rpm": 3500.0,
	"shift_s": 0.45, "downshift_rpm": 2500.0, "kickdown_rpm": 3200.0,
	"torque": [[900, 110], [2000, 145], [2800, 160], [4600, 168],
		[6100, 160], [6800, 140]],
	"boost_rpm": 0.0, "lag_s": 1.0, "boost": 0.0,
	"firing": 2.0, "orders": [[0.5, 0.2], [1.5, 0.15]]},
	{"name": "Twin Turbo V8, 478 PS", "body": "f40",
	"paint": Color(0.78, 0.04, 0.03), "rim": Color(0.55, 0.57, 0.6),
	# wheelbase 2.45 m, track 1.594 / 1.606 m, 245/40 ZR 17 front and
	# 335/35 ZR 17 rear (one radius for both)
	"wheels": [
		Vector3(-0.797, -0.1, -1.225), Vector3(0.797, -0.1, -1.225),
		Vector3(-0.803, -0.1, 1.225), Vector3(0.803, -0.1, 1.225)],
	"rest": 0.28, "radius": 0.324, "tyre_width": [0.245, 0.335],
	"mass": 1250.0, "spring": 55000.0, "damper": 4100.0, "mu": 1.2,
	"brake": 24000.0, "drag": 0.42, "downforce": 0.0,
	"com_y": -0.32, "com_z": 0.2, "box": Vector3(1.95, 0.5, 4.3),
	"box_y": -0.25,
	"gears": [2.77, 1.72, 1.23, 0.96, 0.77], "reverse": 2.77,
	"final_drive": 3.43, "driveline": 0.9, "front_drive": 0.0,
	"idle": 1000.0, "redline": 7750.0, "launch_rpm": 4000.0,
	"shift_s": 0.35, "downshift_rpm": 3500.0, "kickdown_rpm": 4500.0,
	"torque": [[1000, 250], [2500, 330], [3500, 500], [4000, 577],
		[5000, 560], [6000, 520], [7000, 480], [7750, 430]],
	"boost_rpm": 3200.0, "lag_s": 1.1, "boost": 0.7,
	# flat-plane V8: four even pulses per crank turn, little burble, a
	# rasp at one and a half
	"firing": 4.0, "orders": [[0.5, 0.12], [1.5, 0.15]]},
	{"name": "Flat Six Track, 525 PS", "body": "gt3rs",
	"paint": Color(0.42, 0.74, 0.2), "rim": Color(0.22, 0.22, 0.24),
	# wheelbase 2.457 m, track 1.63 / 1.582 m, 275/35 R 20 front and
	# 335/30 R 21 rear (one radius for both)
	"wheels": [
		Vector3(-0.815, -0.1, -1.2285), Vector3(0.815, -0.1, -1.2285),
		Vector3(-0.79, -0.1, 1.2285), Vector3(0.79, -0.1, 1.2285)],
	"rest": 0.30, "radius": 0.358, "tyre_width": [0.275, 0.335],
	"mass": 1450.0, "spring": 60000.0, "damper": 4600.0, "mu": 1.4,
	"brake": 30000.0, "drag": 0.52, "downforce": 1.3,
	"com_y": -0.36, "com_z": 0.27, "box": Vector3(1.88, 0.55, 4.5),
	"box_y": -0.26,
	"gears": [3.75, 2.38, 1.72, 1.34, 1.11, 0.96, 0.84], "reverse": 3.0,
	"final_drive": 4.89, "driveline": 0.9, "front_drive": 0.0,
	"idle": 900.0, "redline": 9000.0, "launch_rpm": 4500.0,
	"shift_s": 0.1, "downshift_rpm": 4500.0, "kickdown_rpm": 6000.0,
	"torque": [[900, 250], [3000, 360], [4500, 420], [6300, 465],
		[7500, 455], [8500, 434], [9000, 400]],
	"boost_rpm": 0.0, "lag_s": 1.0, "boost": 0.0,
	# flat six: three even pulses per crank turn
	"firing": 3.0, "orders": [[0.5, 0.15], [1.5, 0.2]]},
]
# - revised 2026-11-04 (Impreza, Golf GTI, F40 and 911 GT3 RS)
# - revised 2026-11-06 (made-up names in the menu, no trademarks)
