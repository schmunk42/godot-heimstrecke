# file generated with AI assistance: Claude Code - 2026-10-21 01:55:00 UTC
extends RefCounted
## Procedural car bodies: lofted bodies with box wheel arches, a
## greenhouse (all dark glass, or in the paint with glass windows), trim,
## lights and wheels with tyre and rim; no brand marks (see
## docs/licences.md#vehicles). Sixteen bodies (BODIES), chosen by the
## `body` key of a cars.gd entry: the 1980s Audi quattro (Typ 85) with its upright nose
## and sloping rear window down to the tail, the Sport quattro with the
## shorter wheelbase and the steeper windscreen, the Lamborghini
## Huracán STO, a low wedge with an orange splitter and skirts, a roof
## scoop, a fin and a rear wing, the Subaru Impreza saloon with bonnet
## scoop and boot wing, the boxy Golf II hatchback, the Ferrari F40 with
## its full-width tail wing and the Porsche 911 GT3 RS with round
## headlights on the wings and the swan-neck wing; since 0.2.0 the
## Lancia Delta Integrale, the Renault 5 Turbo, the Ford Focus RS (Mk1),
## the BMW M Coupé, the Mercedes SL 63 (R230), a formula car of the V10
## years with open wheels, the VW Käfer 1303 S, the Trabant 601 and the
## Unimog U 5023 with its frame and cab above the wheels.
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
## Subaru Impreza WRX STI (GD): a four-door saloon, front axle at
## z = -1.2625, 4.42 m long, 1.74 m wide, a short boot deck behind the
## rear window.
const IMPREZA_BODY := [
	[-2.23, 0.80, 0.28, 0.66],
	[-2.17, 0.84, 0.24, 0.72],
	[-1.70, 0.85, 0.24, 0.84],
	[-0.80, 0.85, 0.25, 0.95],
	[0.90, 0.85, 0.25, 0.97],
	[1.70, 0.85, 0.26, 1.00],
	[2.10, 0.83, 0.30, 1.01],
	[2.19, 0.79, 0.38, 0.99],
]
## windscreen, roof at 1.42 m, rear window down to the boot lid
const IMPREZA_CANOPY := [
	[-0.82, 0.74, 0.90, 0.95],
	[-0.10, 0.68, 0.91, 1.42],
	[0.80, 0.67, 0.92, 1.42],
	[1.45, 0.63, 0.94, 1.03],
	[1.50, 0.62, 0.95, 1.00],
]
## Ferrari F40: front axle at z = -1.225, 4.36 m long, 1.97 m wide over
## the rear arches, 1.12 m high; a low nose, the cockpit and the long
## engine cover down to the tail wing.
const F40_BODY := [
	[-2.25, 0.80, 0.12, 0.30],
	[-2.18, 0.88, 0.11, 0.42],
	[-1.90, 0.92, 0.12, 0.56],
	[-1.30, 0.93, 0.13, 0.68],
	[-0.70, 0.93, 0.14, 0.74],
	[0.10, 0.90, 0.14, 0.80],
	[0.80, 0.96, 0.15, 0.86],
	[1.60, 0.97, 0.18, 0.92],
	[2.02, 0.95, 0.24, 0.96],
	[2.11, 0.92, 0.30, 0.95],
]
const F40_CANOPY := [
	[-1.00, 0.80, 0.70, 0.73],
	[-0.30, 0.66, 0.74, 1.10],
	[0.20, 0.62, 0.78, 1.124],
	[0.60, 0.64, 0.82, 1.08],
	[1.50, 0.74, 0.88, 0.94],
	[1.90, 0.80, 0.92, 0.96],
]
## Porsche 911 GT3 RS (992): front axle at z = -1.2285, 4.57 m long,
## 1.90 m wide, the engine behind the rear axle; a low bonnet between the
## wings and the fastback roof down to the engine lid.
const GT3RS_BODY := [
	[-2.26, 0.80, 0.14, 0.46],
	[-2.18, 0.87, 0.12, 0.56],
	[-1.90, 0.89, 0.13, 0.66],
	[-1.40, 0.90, 0.14, 0.72],
	[-0.80, 0.89, 0.16, 0.76],
	[0.40, 0.87, 0.18, 0.82],
	[1.10, 0.94, 0.20, 0.88],
	[1.80, 0.94, 0.22, 0.92],
	[2.22, 0.91, 0.26, 0.94],
	[2.31, 0.87, 0.34, 0.92],
]
const GT3RS_CANOPY := [
	[-0.98, 0.74, 0.74, 0.77],
	[-0.25, 0.66, 0.78, 1.30],
	[0.35, 0.64, 0.82, 1.322],
	[0.95, 0.66, 0.86, 1.20],
	[1.55, 0.72, 0.90, 1.04],
	[2.05, 0.78, 0.93, 0.95],
]
## VW Golf II GTI: front axle at z = -1.2375, 3.99 m long, 1.68 m wide, a
## box with a steep tailgate.
const GOLF_BODY := [
	[-2.05, 0.78, 0.28, 0.74],
	[-1.99, 0.81, 0.26, 0.78],
	[-1.50, 0.82, 0.26, 0.86],
	[-0.80, 0.82, 0.26, 0.93],
	[1.20, 0.82, 0.27, 0.95],
	[1.86, 0.81, 0.30, 0.96],
	[1.94, 0.78, 0.36, 0.95],
]
const GOLF_CANOPY := [
	[-0.84, 0.74, 0.90, 0.93],
	[-0.20, 0.68, 0.91, 1.39],
	[1.20, 0.67, 0.92, 1.405],
	[1.80, 0.64, 0.93, 1.03],
	[1.86, 0.63, 0.94, 0.98],
]
## Lancia Delta HF Integrale Evoluzione: front axle at z = -1.24, 3.90 m
## long, 1.77 m wide over the box flares, a tall five-door box.
const DELTA_BODY := [
	[-1.96, 0.78, 0.28, 0.64],
	[-1.90, 0.82, 0.25, 0.72],
	[-1.40, 0.82, 0.25, 0.82],
	[-0.80, 0.82, 0.26, 0.90],
	[1.30, 0.82, 0.27, 0.93],
	[1.86, 0.81, 0.30, 0.94],
	[1.94, 0.78, 0.36, 0.92],
]
## windscreen, roof at 1.36 m, a steep tailgate
const DELTA_CANOPY := [
	[-0.85, 0.72, 0.88, 0.91],
	[-0.25, 0.68, 0.90, 1.34],
	[1.35, 0.67, 0.92, 1.36],
	[1.85, 0.64, 0.93, 1.02],
	[1.92, 0.63, 0.94, 0.97],
]
## Renault 5 Turbo 2: front axle at z = -1.215, 3.66 m long, 1.75 m wide
## over the rear flares that carry the intakes for the mid engine.
const R5_BODY := [
	[-1.77, 0.74, 0.30, 0.62],
	[-1.70, 0.78, 0.27, 0.72],
	[-1.30, 0.78, 0.27, 0.80],
	[-0.80, 0.78, 0.27, 0.86],
	[0.40, 0.80, 0.27, 0.88],
	[0.70, 0.86, 0.27, 0.90],
	[1.70, 0.87, 0.28, 0.92],
	[1.90, 0.84, 0.33, 0.90],
]
## windscreen, roof at 1.32 m, the sloping hatch
const R5_CANOPY := [
	[-0.85, 0.66, 0.84, 0.88],
	[-0.30, 0.62, 0.86, 1.30],
	[0.75, 0.60, 0.88, 1.32],
	[1.55, 0.58, 0.90, 1.00],
	[1.70, 0.58, 0.91, 0.94],
]
## Ford Focus RS (Mk1): front axle at z = -1.3075, 4.17 m long, 1.79 m
## wide, a three-door hatchback.
const FOCUS_BODY := [
	[-2.17, 0.78, 0.28, 0.62],
	[-2.10, 0.84, 0.24, 0.70],
	[-1.60, 0.86, 0.24, 0.84],
	[-0.80, 0.87, 0.25, 0.96],
	[1.40, 0.88, 0.27, 0.99],
	[1.92, 0.86, 0.30, 1.00],
	[2.00, 0.80, 0.38, 0.98],
]
const FOCUS_CANOPY := [
	[-0.85, 0.74, 0.92, 0.96],
	[-0.05, 0.66, 0.94, 1.40],
	[1.20, 0.66, 0.96, 1.42],
	[1.80, 0.66, 0.98, 1.20],
	[1.98, 0.64, 0.99, 1.00],
]
## BMW M Coupé (E36/8): front axle at z = -1.2295, 4.03 m long, 1.74 m
## wide; a long bonnet and the flat roof running back to an upright
## tailgate (the "breadvan").
const MCOUPE_BODY := [
	[-2.03, 0.76, 0.28, 0.58],
	[-1.96, 0.82, 0.24, 0.66],
	[-1.50, 0.84, 0.24, 0.74],
	[-0.60, 0.85, 0.25, 0.82],
	[1.20, 0.86, 0.26, 0.86],
	[1.85, 0.85, 0.28, 0.90],
	[2.00, 0.80, 0.36, 0.88],
]
const MCOUPE_CANOPY := [
	[-0.62, 0.72, 0.80, 0.83],
	[-0.05, 0.64, 0.82, 1.25],
	[1.45, 0.64, 0.86, 1.26],
	[1.92, 0.66, 0.88, 1.10],
	[1.98, 0.66, 0.88, 0.95],
]
## Mercedes SL 63 AMG (R230): front axle at z = -1.28, 4.56 m long,
## 1.82 m wide, the long bonnet of a front-engined roadster with the
## hardtop up.
const SL_BODY := [
	[-2.23, 0.80, 0.28, 0.58],
	[-2.15, 0.86, 0.24, 0.66],
	[-1.70, 0.89, 0.24, 0.76],
	[-0.70, 0.90, 0.25, 0.86],
	[0.80, 0.90, 0.26, 0.90],
	[1.80, 0.89, 0.28, 0.93],
	[2.25, 0.86, 0.32, 0.92],
	[2.33, 0.80, 0.40, 0.88],
]
const SL_CANOPY := [
	[-0.75, 0.74, 0.84, 0.87],
	[-0.10, 0.66, 0.86, 1.28],
	[0.55, 0.64, 0.88, 1.30],
	[1.10, 0.66, 0.89, 1.12],
	[1.55, 0.72, 0.91, 0.94],
]
## Formula car of the V10 years (about 2004): axles at z = -1.55 and
## 1.55 (3.10 m wheelbase), 4.6 m long, open wheels; a thin nose, the
## monocoque, side pods 1.36 m across between the wheels and the
## gearbox between the rear wheels.
const F1_BODY := [
	[-2.55, 0.12, 0.10, 0.25],
	[-2.00, 0.17, 0.12, 0.42],
	[-1.30, 0.25, 0.10, 0.58],
	[-0.80, 0.32, 0.08, 0.66],
	[-0.70, 0.65, 0.08, 0.60],
	[0.30, 0.68, 0.08, 0.62],
	[1.00, 0.40, 0.08, 0.58],
	[1.25, 0.25, 0.10, 0.50],
	[2.05, 0.18, 0.15, 0.45],
]
## the airbox above the driver's head and the engine cover, in the paint
const F1_CANOPY := [
	[-0.25, 0.14, 0.60, 0.98],
	[0.00, 0.16, 0.60, 1.00],
	[0.90, 0.14, 0.58, 0.72],
	[1.50, 0.10, 0.48, 0.52],
]
## VW Käfer 1303 S: front axle at z = -1.21, 4.08 m long, 1.585 m wide
## over the wings; the rounded body below the dome of the cabin, which
## runs down to the engine lid.
const KAEFER_BODY := [
	[-2.02, 0.52, 0.40, 0.56],
	[-1.90, 0.64, 0.32, 0.70],
	[-1.50, 0.70, 0.30, 0.85],
	[-0.90, 0.72, 0.30, 0.94],
	[0.60, 0.74, 0.30, 0.98],
	[1.40, 0.72, 0.32, 0.96],
	[1.90, 0.62, 0.38, 0.78],
	[2.06, 0.50, 0.45, 0.60],
]
const KAEFER_CANOPY := [
	[-0.95, 0.66, 0.92, 0.96],
	[-0.50, 0.62, 0.94, 1.40],
	[0.10, 0.62, 0.96, 1.50],
	[0.70, 0.62, 0.97, 1.44],
	[1.20, 0.62, 0.97, 1.22],
	[1.70, 0.58, 0.90, 0.94],
]
## Trabant 601: front axle at z = -1.01, 3.56 m long, 1.51 m wide, a
## small notchback saloon.
const TRABANT_BODY := [
	[-1.73, 0.68, 0.30, 0.62],
	[-1.66, 0.72, 0.27, 0.72],
	[-1.20, 0.74, 0.27, 0.80],
	[-0.75, 0.74, 0.27, 0.86],
	[0.80, 0.75, 0.28, 0.88],
	[1.70, 0.74, 0.30, 0.90],
	[1.82, 0.70, 0.36, 0.86],
]
const TRABANT_CANOPY := [
	[-0.80, 0.66, 0.84, 0.87],
	[-0.25, 0.62, 0.86, 1.42],
	[0.70, 0.62, 0.87, 1.44],
	[1.10, 0.63, 0.88, 0.94],
]
## Unimog U 5023: axles at z = -1.925 and 1.925 (3.85 m wheelbase),
## 5.4 m long, 2.3 m wide; the frame with bonnet and flatbed lies above
## the wheels (no arches), the cab sits over the front axle.
const UNIMOG_BODY := [
	[-2.75, 1.00, 0.70, 1.15],
	[-2.62, 1.08, 1.25, 1.50],
	[-2.25, 1.10, 1.25, 1.62],
	[-0.95, 1.12, 1.25, 1.62],
	[-0.88, 1.15, 1.25, 1.50],
	[2.55, 1.15, 1.25, 1.50],
	[2.65, 1.12, 1.25, 1.45],
]
## the cab: windscreen, roof at 2.9 m, flat back wall
const UNIMOG_CANOPY := [
	[-2.30, 1.00, 1.60, 1.70],
	[-2.15, 1.02, 1.60, 2.85],
	[-0.95, 1.05, 1.60, 2.90],
	[-0.90, 1.05, 1.60, 2.85],
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
const IMPREZA_WINDOWS := {
	"front": [-0.78, -0.14], "rear": [0.84, 1.41],
	"side": [
		[[-0.62, 0.98], [-0.14, 1.36], [0.30, 1.36], [0.30, 0.98]],
		[[0.38, 0.98], [0.38, 1.36], [0.80, 1.36], [1.25, 0.98]]],
}
const GT3RS_WINDOWS := {
	"front": [-0.94, -0.29], "rear": [1.00, 1.50],
	"side": [
		[[-0.80, 0.86], [-0.28, 1.26], [0.50, 1.26], [0.95, 0.92]]],
}
const GOLF_WINDOWS := {
	"front": [-0.80, -0.24], "rear": [1.24, 1.76],
	"side": [
		[[-0.66, 0.98], [-0.24, 1.35], [0.45, 1.35], [0.45, 0.98]],
		[[0.53, 0.98], [0.53, 1.35], [1.10, 1.35], [1.40, 0.98]]],
}
const DELTA_WINDOWS := {
	"front": [-0.82, -0.28], "rear": [1.38, 1.82],
	"side": [
		[[-0.70, 0.94], [-0.27, 1.30], [0.35, 1.30], [0.35, 0.94]],
		[[0.43, 0.94], [0.43, 1.30], [1.05, 1.30], [1.05, 0.94]],
		[[1.12, 0.94], [1.12, 1.30], [1.32, 1.30], [1.55, 0.98]]],
}
const R5_WINDOWS := {
	"front": [-0.82, -0.33], "rear": [0.80, 1.50],
	"side": [
		[[-0.65, 0.90], [-0.30, 1.26], [0.40, 1.26], [0.40, 0.90]],
		[[0.48, 0.90], [0.48, 1.26], [0.75, 1.26], [1.25, 0.95]]],
}
const FOCUS_WINDOWS := {
	"front": [-0.82, -0.10], "rear": [1.25, 1.78],
	"side": [
		[[-0.62, 0.99], [-0.05, 1.36], [0.70, 1.36], [0.70, 0.99]],
		[[0.78, 0.99], [0.78, 1.36], [1.25, 1.34], [1.55, 1.02]]],
}
const MCOUPE_WINDOWS := {
	"front": [-0.60, -0.08], "rear": [1.50, 1.90],
	"side": [
		[[-0.45, 0.88], [-0.05, 1.22], [0.60, 1.22], [0.60, 0.88]],
		[[0.68, 0.88], [0.68, 1.22], [1.40, 1.22], [1.40, 0.90]]],
}
const SL_WINDOWS := {
	"front": [-0.72, -0.14], "rear": [0.60, 1.07],
	"side": [
		[[-0.55, 0.90], [-0.10, 1.24], [0.75, 1.24], [1.10, 0.92]]],
}
const KAEFER_WINDOWS := {
	"front": [-0.92, -0.52], "rear": [0.75, 1.15],
	"side": [
		[[-0.75, 0.98], [-0.42, 1.40], [0.35, 1.42], [0.35, 0.98]],
		[[0.43, 0.98], [0.43, 1.40], [0.80, 1.38], [1.10, 1.05]]],
}
const TRABANT_WINDOWS := {
	"front": [-0.77, -0.28], "rear": [0.74, 1.07],
	"side": [
		[[-0.62, 0.89], [-0.25, 1.38], [0.25, 1.38], [0.25, 0.89]],
		[[0.33, 0.89], [0.33, 1.38], [0.68, 1.38], [0.95, 0.92]]],
}
const UNIMOG_WINDOWS := {
	"front": [-2.29, -2.16], "rear": [-0.94, -0.91],
	"side": [
		[[-2.05, 1.95], [-2.12, 2.70], [-1.10, 2.70], [-1.10, 1.95]]],
}
## body: sections, canopy, superellipse exponents of body and canopy
## (smaller is boxier), rim radius, windows (empty: all-glass canopy),
## arches: axle positions and half width over the flares (optional),
## canopy_paint: the canopy in the paint without glass (optional)
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
	"impreza": {"body": IMPREZA_BODY, "canopy": IMPREZA_CANOPY,
		"shape": Vector2(0.12, 0.2), "canopy_shape": Vector2(0.1, 0.15),
		"rim": 0.216, "windows": IMPREZA_WINDOWS,
		"arches": {"axles": [-1.2625, 1.2625], "flare": 0.87}},
	"f40": {"body": F40_BODY, "canopy": F40_CANOPY,
		"shape": Vector2(0.15, 0.3), "canopy_shape": Vector2(0.2, 0.35),
		"rim": 0.216, "windows": {},
		"arches": {"axles": [-1.225, 1.225], "flare": 0.985}},
	"gt3rs": {"body": GT3RS_BODY, "canopy": GT3RS_CANOPY,
		"shape": Vector2(0.2, 0.35), "canopy_shape": Vector2(0.25, 0.4),
		"rim": 0.26, "windows": GT3RS_WINDOWS,
		"arches": {"axles": [-1.2285, 1.2285], "flare": 0.95}},
	"golf": {"body": GOLF_BODY, "canopy": GOLF_CANOPY,
		"shape": Vector2(0.07, 0.14), "canopy_shape": Vector2(0.06, 0.1),
		"rim": 0.178, "windows": GOLF_WINDOWS,
		"arches": {"axles": [-1.2375, 1.2375], "flare": 0.84}},
	"delta": {"body": DELTA_BODY, "canopy": DELTA_CANOPY,
		"shape": Vector2(0.06, 0.12), "canopy_shape": Vector2(0.05, 0.1),
		"rim": 0.203, "windows": DELTA_WINDOWS,
		"arches": {"axles": [-1.24, 1.24], "flare": 0.885}},
	"r5": {"body": R5_BODY, "canopy": R5_CANOPY,
		"shape": Vector2(0.07, 0.14), "canopy_shape": Vector2(0.06, 0.1),
		"rim": 0.17, "windows": R5_WINDOWS,
		"arches": {"axles": [-1.215, 1.215], "flare": 0.875}},
	"focus": {"body": FOCUS_BODY, "canopy": FOCUS_CANOPY,
		"shape": Vector2(0.12, 0.2), "canopy_shape": Vector2(0.1, 0.15),
		"rim": 0.229, "windows": FOCUS_WINDOWS,
		"arches": {"axles": [-1.3075, 1.3075], "flare": 0.89}},
	"mcoupe": {"body": MCOUPE_BODY, "canopy": MCOUPE_CANOPY,
		"shape": Vector2(0.15, 0.25), "canopy_shape": Vector2(0.1, 0.2),
		"rim": 0.216, "windows": MCOUPE_WINDOWS,
		"arches": {"axles": [-1.2295, 1.2295], "flare": 0.87}},
	"sl": {"body": SL_BODY, "canopy": SL_CANOPY,
		"shape": Vector2(0.2, 0.3), "canopy_shape": Vector2(0.2, 0.35),
		"rim": 0.241, "windows": SL_WINDOWS,
		"arches": {"axles": [-1.28, 1.28], "flare": 0.91}},
	"f1": {"body": F1_BODY, "canopy": F1_CANOPY,
		"shape": Vector2(0.35, 0.5), "canopy_shape": Vector2(0.6, 0.8),
		"rim": 0.17, "windows": {}, "canopy_paint": true},
	"kaefer": {"body": KAEFER_BODY, "canopy": KAEFER_CANOPY,
		"shape": Vector2(0.45, 0.6), "canopy_shape": Vector2(0.3, 0.5),
		"rim": 0.19, "windows": KAEFER_WINDOWS,
		"arches": {"axles": [-1.21, 1.21], "flare": 0.79}},
	"trabant": {"body": TRABANT_BODY, "canopy": TRABANT_CANOPY,
		"shape": Vector2(0.1, 0.18), "canopy_shape": Vector2(0.08, 0.14),
		"rim": 0.165, "windows": TRABANT_WINDOWS,
		"arches": {"axles": [-1.01, 1.01], "flare": 0.75}},
	"unimog": {"body": UNIMOG_BODY, "canopy": UNIMOG_CANOPY,
		"shape": Vector2(0.04, 0.08), "canopy_shape": Vector2(0.05, 0.08),
		"rim": 0.30, "windows": UNIMOG_WINDOWS},
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
	if body.get("canopy_paint", false):
		_add(parent, _loft(body.canopy, paint, body.canopy_shape),
			Vector3.ZERO)
	elif windows.is_empty():
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
		"impreza":
			_impreza_details(parent, paint, trim)
		"f40":
			_f40_details(parent, paint, trim)
		"gt3rs":
			_gt3rs_details(parent, trim)
		"golf":
			_golf_details(parent, trim)
		"delta":
			_delta_details(parent, paint, trim)
		"r5":
			_r5_details(parent, trim)
		"focus":
			_focus_details(parent, paint, trim)
		"mcoupe":
			_mcoupe_details(parent, trim)
		"sl":
			_sl_details(parent, paint, trim)
		"f1":
			_f1_details(parent, paint, trim)
		"kaefer":
			_kaefer_details(parent, trim)
		"trabant":
			_trabant_details(parent, trim)
		"unimog":
			_unimog_details(parent, paint, trim)

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
	_audi_front(parent, trim, z)
	_audi_rear(parent, trim, 2.13, 1.40)


## Sport quattro after the 1:18 model: one large rectangular headlight
## per side with the black grille between them, amber
## indicators and a black grille band in the bumper, a black lip; at the
## back a black panel with two tail lights, a black bumper strip and the
## large black spoiler on the tail deck.
static func _sport_details(parent: Node3D, trim: Material) -> void:
	var z := -2.06
	_box(parent, Vector3(0.90, 0.13, 0.04), Vector3(0.0, 0.71, z), trim)
	for side in [-1.0, 1.0]:
		_light(parent, Vector3(0.26, 0.12, 0.04),
			Vector3(side * 0.60, 0.71, z - 0.01), HEADLIGHT, 4.0)
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


## Impreza: slim headlights at the corners of the nose, the black
## grille and a wide intake below, the bonnet scoop in the paint, round
## tail lights and the tall wing on the boot lid.
static func _impreza_details(parent: Node3D, paint: Material,
		trim: Material) -> void:
	var z := -2.24
	_box(parent, Vector3(0.50, 0.10, 0.04), Vector3(0.0, 0.58, z), trim)
	_box(parent, Vector3(1.10, 0.14, 0.04), Vector3(0.0, 0.38, z), trim)
	_box(parent, Vector3(0.46, 0.07, 0.36), Vector3(0.0, 0.92, -1.25),
		paint, Vector3(0.06, 0.0, 0.0))
	_box(parent, Vector3(0.36, 0.04, 0.04), Vector3(0.0, 0.93, -1.44), trim)
	for side in [-1.0, 1.0]:
		_light(parent, Vector3(0.30, 0.10, 0.04),
			Vector3(side * 0.56, 0.58, z - 0.01), HEADLIGHT, 4.0,
			Vector3(0.0, side * 0.2, 0.0))
		_light(parent, Vector3(0.20, 0.14, 0.04),
			Vector3(side * 0.60, 0.86, 2.20), TAIL_LIGHT, 1.5)
		_box(parent, Vector3(0.04, 0.16, 0.10),
			Vector3(side * 0.55, 1.08, 1.95), trim)
		_box(parent, Vector3(0.02, 0.05, 1.30),
			Vector3(side * 0.845, 0.28, 0.0), trim)
	_box(parent, Vector3(1.40, 0.03, 0.26), Vector3(0.0, 1.17, 1.97), paint,
		Vector3(0.10, 0.0, 0.0))
	_box(parent, Vector3(1.50, 0.06, 0.06), Vector3(0.0, 0.40, 2.20), trim)


## F40: a black slot across the nose with the lights in it, three NACA
## ducts in the bonnet, intakes behind the doors, the full-width wing on
## the tail with side plates in the paint, four round tail lights and the
## black mesh below them.
static func _f40_details(parent: Node3D, paint: Material,
		trim: Material) -> void:
	_box(parent, Vector3(1.50, 0.08, 0.05), Vector3(0.0, 0.34, -2.24), trim)
	_box(parent, Vector3(1.40, 0.10, 0.05), Vector3(0.0, 0.18, -2.22), trim)
	for x in [-0.30, 0.0, 0.30]:
		_box(parent, Vector3(0.12, 0.02, 0.40), Vector3(x, 0.62, -1.55),
			trim, Vector3(0.12, 0.0, 0.0))
	for side in [-1.0, 1.0]:
		_light(parent, Vector3(0.30, 0.05, 0.04),
			Vector3(side * 0.55, 0.34, -2.27), HEADLIGHT, 4.0)
		_box(parent, Vector3(0.04, 0.22, 0.50),
			Vector3(side * 0.94, 0.60, 0.80), trim)
		_box(parent, Vector3(0.04, 0.26, 0.40),
			Vector3(side * 0.92, 1.05, 2.00), paint)
		for x in [0.38, 0.62]:
			_light(parent, Vector3(0.14, 0.14, 0.04),
				Vector3(side * x, 0.80, 2.12), TAIL_LIGHT, 1.5)
	_box(parent, Vector3(1.88, 0.04, 0.34), Vector3(0.0, 1.16, 2.00),
		paint, Vector3(-0.08, 0.0, 0.0))
	_box(parent, Vector3(1.50, 0.22, 0.05), Vector3(0.0, 0.50, 2.12), trim)


## 911 GT3 RS: round headlights on the front wings, the black intakes
## across the nose, vents in the bonnet, the swan-neck wing above the
## engine lid, the light strip across the tail and the diffuser.
static func _gt3rs_details(parent: Node3D, trim: Material) -> void:
	_box(parent, Vector3(1.60, 0.16, 0.05), Vector3(0.0, 0.28, -2.26), trim)
	_box(parent, Vector3(1.70, 0.03, 0.20), Vector3(0.0, 0.13, -2.20), trim)
	_box(parent, Vector3(0.80, 0.02, 0.30), Vector3(0.0, 0.73, -1.40), trim,
		Vector3(0.10, 0.0, 0.0))
	for side in [-1.0, 1.0]:
		_light(parent, Vector3(0.20, 0.10, 0.06),
			Vector3(side * 0.62, 0.58, -2.00), HEADLIGHT, 4.0,
			Vector3(0.5, 0.0, 0.0))
		_box(parent, Vector3(0.03, 0.42, 0.10),
			Vector3(side * 0.30, 1.16, 1.95), trim)
		_box(parent, Vector3(0.03, 0.18, 0.40),
			Vector3(side * 0.86, 1.36, 1.98), trim)
	_box(parent, Vector3(1.72, 0.035, 0.38), Vector3(0.0, 1.38, 1.98), trim,
		Vector3(-0.10, 0.0, 0.0))
	_light(parent, Vector3(1.60, 0.04, 0.04), Vector3(0.0, 0.90, 2.32),
		TAIL_LIGHT, 3.0)
	_box(parent, Vector3(1.50, 0.18, 0.25), Vector3(0.0, 0.26, 2.20), trim)


## Golf II GTI: black grille across the nose with the red line and two
## round headlights per side, black bumpers and side strips, square tail
## lights.
static func _golf_details(parent: Node3D, trim: Material) -> void:
	var z := -2.06
	var red := StandardMaterial3D.new()
	red.albedo_color = Color(0.8, 0.04, 0.04)
	_box(parent, Vector3(1.30, 0.16, 0.04), Vector3(0.0, 0.64, z), trim)
	_box(parent, Vector3(0.70, 0.015, 0.04), Vector3(0.0, 0.71, z - 0.01),
		red)
	_box(parent, Vector3(1.66, 0.14, 0.10), Vector3(0.0, 0.40, z + 0.02),
		trim)
	_box(parent, Vector3(1.66, 0.14, 0.10), Vector3(0.0, 0.42, 1.93), trim)
	for side in [-1.0, 1.0]:
		for x in [0.44, 0.62]:
			_light(parent, Vector3(0.15, 0.13, 0.04),
				Vector3(side * x, 0.64, z - 0.01), HEADLIGHT, 4.0)
		_light(parent, Vector3(0.30, 0.16, 0.04),
			Vector3(side * 0.58, 0.80, 1.95), TAIL_LIGHT, 1.5)
		_box(parent, Vector3(0.02, 0.06, 1.30),
			Vector3(side * 0.825, 0.40, 0.0), trim)


## Delta Integrale: four round headlights in the black grille band, the
## vents in the bonnet, black bumpers and sill strips, the spoiler on top
## of the tailgate and the tail light band.
static func _delta_details(parent: Node3D, paint: Material,
		trim: Material) -> void:
	var z := -1.97
	_box(parent, Vector3(1.50, 0.16, 0.04), Vector3(0.0, 0.64, z), trim)
	_box(parent, Vector3(1.62, 0.16, 0.10), Vector3(0.0, 0.40, z + 0.02),
		trim)
	_box(parent, Vector3(1.62, 0.16, 0.10), Vector3(0.0, 0.42, 1.93), trim)
	for x in [-0.15, 0.15]:
		_box(parent, Vector3(0.16, 0.02, 0.36), Vector3(x, 0.835, -1.30),
			trim, Vector3(0.08, 0.0, 0.0))
	for side in [-1.0, 1.0]:
		for x in [0.42, 0.62]:
			_lamp(parent, 0.075, Vector3(side * x, 0.64, z - 0.02),
				HEADLIGHT, 4.0)
		_light(parent, Vector3(0.40, 0.12, 0.04),
			Vector3(side * 0.52, 0.80, 1.95), TAIL_LIGHT, 1.5)
		_box(parent, Vector3(0.02, 0.07, 1.20),
			Vector3(side * 0.835, 0.36, 0.0), trim)
	_box(parent, Vector3(1.20, 0.03, 0.22), Vector3(0.0, 1.36, 1.84), paint,
		Vector3(0.12, 0.0, 0.0))


## R5 Turbo: rectangular headlights in a black panel across the nose,
## the big black intakes in the rear flanks, black bumpers, upright tail
## lights at the corners of the hatch.
static func _r5_details(parent: Node3D, trim: Material) -> void:
	var z := -1.78
	_box(parent, Vector3(1.40, 0.15, 0.04), Vector3(0.0, 0.64, z), trim)
	_box(parent, Vector3(1.58, 0.18, 0.12), Vector3(0.0, 0.38, z + 0.03),
		trim)
	_box(parent, Vector3(1.70, 0.18, 0.12), Vector3(0.0, 0.40, 1.90), trim)
	for side in [-1.0, 1.0]:
		_light(parent, Vector3(0.26, 0.12, 0.04),
			Vector3(side * 0.50, 0.64, z - 0.01), HEADLIGHT, 4.0)
		_light(parent, Vector3(0.10, 0.22, 0.04),
			Vector3(side * 0.74, 0.74, 1.92), TAIL_LIGHT, 1.5)
		_box(parent, Vector3(0.04, 0.26, 0.42),
			Vector3(side * 0.875, 0.68, 0.48), trim)


## Focus RS: the swept headlights, black mesh grille and the wide intake
## below, the roof spoiler over the tailgate and the tall tail lights in
## the rear pillars.
static func _focus_details(parent: Node3D, paint: Material,
		trim: Material) -> void:
	var z := -2.18
	_box(parent, Vector3(0.60, 0.10, 0.04), Vector3(0.0, 0.58, z), trim)
	_box(parent, Vector3(1.30, 0.18, 0.04), Vector3(0.0, 0.36, z), trim)
	_box(parent, Vector3(1.40, 0.04, 0.24), Vector3(0.0, 1.42, 1.70), paint,
		Vector3(0.10, 0.0, 0.0))
	for side in [-1.0, 1.0]:
		_light(parent, Vector3(0.36, 0.11, 0.04),
			Vector3(side * 0.58, 0.60, z + 0.04), HEADLIGHT, 4.0,
			Vector3(0.0, side * 0.35, 0.0))
		_light(parent, Vector3(0.08, 0.36, 0.04),
			Vector3(side * 0.64, 1.10, 1.95), TAIL_LIGHT, 1.5)
		_box(parent, Vector3(0.02, 0.07, 1.40),
			Vector3(side * 0.875, 0.32, 0.0), trim)
	_box(parent, Vector3(1.60, 0.14, 0.08), Vector3(0.0, 0.40, 2.00), trim)


## M Coupé: a slim black intake in place of a grille, wide flat
## headlights, the four tail pipes in the black lower rear and the tail
## lights wrapping round the corners.
static func _mcoupe_details(parent: Node3D, trim: Material) -> void:
	var z := -2.04
	_box(parent, Vector3(0.50, 0.08, 0.04), Vector3(0.0, 0.56, z), trim)
	_box(parent, Vector3(1.30, 0.14, 0.04), Vector3(0.0, 0.34, z), trim)
	_box(parent, Vector3(1.50, 0.18, 0.06), Vector3(0.0, 0.34, 2.00), trim)
	for side in [-1.0, 1.0]:
		_light(parent, Vector3(0.34, 0.09, 0.04),
			Vector3(side * 0.52, 0.58, z + 0.02), HEADLIGHT, 4.0,
			Vector3(0.0, side * 0.25, 0.0))
		_light(parent, Vector3(0.30, 0.10, 0.04),
			Vector3(side * 0.62, 0.78, 2.01), TAIL_LIGHT, 1.5)
		for x in [0.08, 0.20]:
			_pipe(parent, 0.04, Vector3(side * x, 0.30, 2.04))


## SL: a wide black grille without a badge, twin headlights per side,
## the two power domes on the bonnet, vents in the front wings, four
## tail pipes and wide tail lights.
static func _sl_details(parent: Node3D, paint: Material,
		trim: Material) -> void:
	var z := -2.24
	_box(parent, Vector3(0.80, 0.18, 0.04), Vector3(0.0, 0.52, z), trim)
	_box(parent, Vector3(1.40, 0.12, 0.04), Vector3(0.0, 0.32, z + 0.02),
		trim)
	_box(parent, Vector3(1.60, 0.16, 0.06), Vector3(0.0, 0.34, 2.33), trim)
	for side in [-1.0, 1.0]:
		_box(parent, Vector3(0.18, 0.04, 0.90), Vector3(side * 0.30, 0.78,
			-1.30), paint, Vector3(0.06, 0.0, 0.0))
		for x in [0.52, 0.70]:
			_lamp(parent, 0.065, Vector3(side * x, 0.60, z + 0.10),
				HEADLIGHT, 4.0)
		_box(parent, Vector3(0.03, 0.10, 0.24),
			Vector3(side * 0.90, 0.62, -1.00), trim)
		_light(parent, Vector3(0.40, 0.11, 0.04),
			Vector3(side * 0.58, 0.82, 2.31), TAIL_LIGHT, 1.5)
		for x in [0.42, 0.54]:
			_pipe(parent, 0.045, Vector3(side * x, 0.28, 2.36))


## Formula car: front wing with end plates under the nose, the cockpit
## opening with the helmet in it, wishbones out to the wheels, the rear
## wing on its end plates, the diffuser and the rain light.
static func _f1_details(parent: Node3D, paint: Material,
		trim: Material) -> void:
	_box(parent, Vector3(1.70, 0.03, 0.40), Vector3(0.0, 0.10, -2.40), trim)
	_box(parent, Vector3(1.50, 0.025, 0.18), Vector3(0.0, 0.16, -2.30),
		paint, Vector3(-0.25, 0.0, 0.0))
	_box(parent, Vector3(0.42, 0.03, 0.62), Vector3(0.0, 0.655, -0.55), trim)
	var helmet := StandardMaterial3D.new()
	helmet.albedo_color = Color(0.95, 0.8, 0.1)
	helmet.roughness = 0.3
	var sphere := SphereMesh.new()
	sphere.radius = 0.13
	sphere.height = 0.26
	sphere.material = helmet
	_add(parent, sphere, Vector3(0.0, 0.80, -0.42))
	for side in [-1.0, 1.0]:
		_box(parent, Vector3(0.02, 0.22, 0.46),
			Vector3(side * 0.85, 0.18, -2.40), paint)
		_box(parent, Vector3(0.02, 0.48, 0.60),
			Vector3(side * 0.46, 0.80, 2.10), paint)
		for y in [0.26, 0.40]:
			_box(parent, Vector3(0.50, 0.02, 0.06),
				Vector3(side * 0.48, y, -1.55), trim)
			_box(parent, Vector3(0.48, 0.02, 0.06),
				Vector3(side * 0.47, y, 1.55), trim)
	_box(parent, Vector3(0.90, 0.025, 0.30), Vector3(0.0, 0.88, 2.15), trim,
		Vector3(-0.10, 0.0, 0.0))
	_box(parent, Vector3(0.90, 0.025, 0.20), Vector3(0.0, 1.00, 2.05), trim,
		Vector3(-0.35, 0.0, 0.0))
	_box(parent, Vector3(0.90, 0.16, 0.36), Vector3(0.0, 0.14, 1.95), trim)
	_light(parent, Vector3(0.08, 0.10, 0.03), Vector3(0.0, 0.30, 2.08),
		TAIL_LIGHT, 3.0)


## Käfer 1303 S: round headlights on top of the front wings, chrome
## bumper blades, the running boards between the wings, the louvres in
## the engine lid and the big round tail lights on the rear wings.
static func _kaefer_details(parent: Node3D, trim: Material) -> void:
	var chrome := _chrome()
	_box(parent, Vector3(1.60, 0.07, 0.07), Vector3(0.0, 0.38, -2.06),
		chrome)
	_box(parent, Vector3(1.60, 0.07, 0.07), Vector3(0.0, 0.42, 2.10),
		chrome)
	for k in 4:
		_box(parent, Vector3(0.36, 0.015, 0.03),
			Vector3(0.0, 0.88 - k * 0.04, 1.72 + k * 0.05), trim,
			Vector3(0.9, 0.0, 0.0))
	for side in [-1.0, 1.0]:
		_lamp(parent, 0.09, Vector3(side * 0.56, 0.80, -1.72), HEADLIGHT,
			4.0, Vector3(0.0, 0.0, 0.0), 0.12)
		_lamp(parent, 0.07, Vector3(side * 0.60, 0.80, 1.86), TAIL_LIGHT,
			1.5, Vector3(PI, 0.0, 0.0), 0.06)
		_box(parent, Vector3(0.10, 0.03, 1.00),
			Vector3(side * 0.74, 0.30, 0.0), trim)


## Trabant: round headlights at the corners of the flat nose with the
## slim grille between them, thin chrome bumpers, small tail lights.
static func _trabant_details(parent: Node3D, trim: Material) -> void:
	var chrome := _chrome()
	var z := -1.74
	_box(parent, Vector3(0.62, 0.08, 0.03), Vector3(0.0, 0.62, z), trim)
	_box(parent, Vector3(1.40, 0.05, 0.06), Vector3(0.0, 0.36, z - 0.02),
		chrome)
	_box(parent, Vector3(1.40, 0.05, 0.06), Vector3(0.0, 0.40, 1.84),
		chrome)
	for side in [-1.0, 1.0]:
		_lamp(parent, 0.075, Vector3(side * 0.52, 0.64, z - 0.01),
			HEADLIGHT, 4.0)
		_light(parent, Vector3(0.12, 0.10, 0.04),
			Vector3(side * 0.56, 0.76, 1.83), TAIL_LIGHT, 1.5)


## Unimog: the black grille and bumper on the nose, round headlights,
## black mud guards over the wheels, the drop sides and tailgate of the
## flatbed and the exhaust stack behind the cab.
static func _unimog_details(parent: Node3D, paint: Material,
		trim: Material) -> void:
	_box(parent, Vector3(1.40, 0.30, 0.04), Vector3(0.0, 1.36, -2.64), trim)
	_box(parent, Vector3(2.10, 0.25, 0.25), Vector3(0.0, 0.82, -2.70), trim)
	_box(parent, Vector3(2.26, 0.50, 0.04), Vector3(0.0, 1.75, -0.86),
		paint)
	_box(parent, Vector3(2.26, 0.42, 0.04), Vector3(0.0, 1.71, 2.63), paint)
	_box(parent, Vector3(0.10, 1.30, 0.10), Vector3(0.95, 2.35, -0.80),
		trim)
	for side in [-1.0, 1.0]:
		_lamp(parent, 0.09, Vector3(side * 0.82, 1.36, -2.66), HEADLIGHT,
			4.0)
		_light(parent, Vector3(0.20, 0.12, 0.04),
			Vector3(side * 0.90, 1.30, 2.66), TAIL_LIGHT, 1.5)
		_box(parent, Vector3(0.04, 0.42, 3.45),
			Vector3(side * 1.13, 1.71, 0.88), paint)
		for axle in [-1.925, 1.925]:
			_box(parent, Vector3(0.46, 0.04, 1.30),
				Vector3(side * 0.96, 1.23, axle), trim)


## A round lamp facing forward (rotation PI about x faces it back),
## `depth` deep.
static func _lamp(parent: Node3D, radius: float, at: Vector3, color: Color,
		energy: float, rotation := Vector3.ZERO, depth := 0.04) -> void:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.emission_enabled = true
	mat.emission = color
	mat.emission_energy_multiplier = energy
	var disc := CylinderMesh.new()
	disc.top_radius = radius
	disc.bottom_radius = radius
	disc.height = depth
	disc.radial_segments = 16
	disc.material = mat
	_add(parent, disc, at).rotation = rotation + Vector3(PI / 2, 0.0, 0.0)


## A tail pipe in chrome pointing back.
static func _pipe(parent: Node3D, radius: float, at: Vector3) -> void:
	var tube := CylinderMesh.new()
	tube.top_radius = radius
	tube.bottom_radius = radius
	tube.height = 0.12
	tube.radial_segments = 12
	tube.material = _chrome()
	_add(parent, tube, at).rotation = Vector3(PI / 2, 0.0, 0.0)


static func _chrome() -> StandardMaterial3D:
	var chrome := StandardMaterial3D.new()
	chrome.albedo_color = Color(0.85, 0.86, 0.88)
	chrome.metallic = 1.0
	chrome.roughness = 0.2
	return chrome


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
# - revised 2026-11-04 (Impreza, F40, 911 GT3 RS and Golf GTI bodies)
# - revised 2026-11-06 (no brand marks: the four rings removed)
# - revised 2026-11-06 (nine more bodies, canopy_paint, round lamps)
