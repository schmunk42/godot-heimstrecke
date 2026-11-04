# file generated with AI assistance: Claude Code - 2026-10-23 12:50:00 UTC
"""Biomes: the look of a world's landscape, picked by the recipe key
`biome` (world.py).

temperate (the default) is the look the Baden-Wuerttemberg worlds were
built with, unchanged: build.COLORS, broadleaf and conifer trees, no
rock. mediterranean (Corsica) has drier, yellower ground and horizon,
grey rock on OSM bare rock and scree, above ROCK_FROM_M and on slopes
steeper than ROCK_SLOPE, and four tree kinds: holm oak, pine (maritime
and laricio pine, the umbrella crown of the stone pine), cypress for
mapped Cupressus and shrubs (the maquis) on natural=scrub/heath. Its
houses have terracotta, ochre, salmon and granite facades under tile-red
roofs (FACADES, ROOF), and a house standing alone outside the urban land
cover (fewer than ISOLATED_NEIGHBOURS others within ISOLATED_M) without
a height or levels tag has the ground floor only (GROUND_FLOOR_M).

mediterranean-dry (south-east Cyprus) is the drier, hotter variant:
red-brown terra rossa on the fields, ochre and dry olive ground, pale
limestone rock, no rock by height (the coast lies below 200 m), the
tree kinds of mediterranean (pine for the Calabrian pine, oak for carob
and olive, cypress, shrub for the garrigue), and whitewashed, cream and
light ochre houses with flat roofs (no ROOF, so the roof takes the
facade colour).

The mediterranean biomes also shade their ground (ground_shade): darker
on slopes (GROUND_SLOPE) and a gentle mottle by position (GROUND_MOTTLE),
so the relief reads on the bare, pale ground; the darker mediterranean
ground colours date from 2026-11-04, when Bavella looked flat.

A biome only overrides colours; a cover kind without a colour in the
palette is not painted (temperate has no rock or sand), so the same
extract gives the temperate worlds byte-identical tiles.
"""
import numpy as np

BIOMES = ("temperate", "mediterranean", "mediterranean-dry")
# biomes with the mediterranean tree kinds and the maquis (trees.py)
MEDITERRANEAN = ("mediterranean", "mediterranean-dry")

# colour overrides of build.COLORS per biome
PALETTES = {
    "temperate": {"scrub": (0.45, 0.68, 0.33)},
    "mediterranean": {
        "default": (0.60, 0.57, 0.34),
        "green": (0.56, 0.56, 0.32),
        "farmland": (0.66, 0.60, 0.36),
        "scrub": (0.42, 0.48, 0.26),
        "forest": (0.30, 0.36, 0.20),
        "sand": (0.86, 0.80, 0.62),
        "rock": (0.50, 0.47, 0.44),
        "horizon": (0.55, 0.56, 0.38),
    },
    "mediterranean-dry": {
        "default": (0.74, 0.63, 0.45),
        "urban": (0.72, 0.69, 0.64),
        "green": (0.60, 0.58, 0.37),
        "farmland": (0.64, 0.44, 0.31),
        "scrub": (0.52, 0.50, 0.32),
        "forest": (0.34, 0.39, 0.23),
        "sand": (0.90, 0.84, 0.68),
        "rock": (0.70, 0.66, 0.58),
        "horizon": (0.66, 0.56, 0.42),
    },
}

# rock (grey) blends in between these heights above sea level ...
ROCK_FROM_M = {"mediterranean": (1150.0, 1550.0)}
# ... and between these slopes (rise over run)
ROCK_SLOPE = {"mediterranean": (0.75, 1.2)}

# ground darkens by up to the share between these slopes (rise over run)
GROUND_SLOPE = {"mediterranean": (0.15, 0.6, 0.22),
                "mediterranean-dry": (0.15, 0.6, 0.18)}
# ground brightness varies by +- this share, over wavelengths of these
# metres (incommensurate, so no visible repeat)
GROUND_MOTTLE = {"mediterranean": (0.07, (173.0, 61.0, 23.0)),
                 "mediterranean-dry": (0.07, (173.0, 61.0, 23.0))}

# facade colours: (share, from, to); the share picks by the centroid hash
# (build.facade_color), the colour runs from `from` to `to` within it
FACADES = {"mediterranean": (
    (0.40, (0.80, 0.52, 0.36), (0.88, 0.63, 0.44)),  # terracotta
    (0.30, (0.88, 0.75, 0.55), (0.80, 0.64, 0.45)),  # ochre, sand
    (0.15, (0.90, 0.68, 0.58), (0.84, 0.58, 0.50)),  # salmon
    (0.15, (0.60, 0.57, 0.53), (0.70, 0.66, 0.60)),  # granite
), "mediterranean-dry": (
    (0.45, (0.95, 0.94, 0.91), (0.89, 0.88, 0.84)),  # whitewash
    (0.30, (0.92, 0.87, 0.75), (0.85, 0.78, 0.63)),  # cream, limestone
    (0.15, (0.88, 0.76, 0.56), (0.82, 0.68, 0.48)),  # light ochre
    (0.10, (0.74, 0.73, 0.70), (0.66, 0.65, 0.62)),  # concrete
)}
# roof colour; a biome without one draws the roof in the facade colour
ROOF = {"mediterranean": (0.66, 0.33, 0.22)}
GROUND_FLOOR_M = {"mediterranean": 3.5, "mediterranean-dry": 3.5}
ISOLATED_M = 60.0
ISOLATED_NEIGHBOURS = 3

# tree kinds in file order (trees.py), the Godot models are named alike
KINDS = {"temperate": ("broad", "conifer"),
         "mediterranean": ("oak", "pine", "cypress", "shrub"),
         "mediterranean-dry": ("oak", "pine", "cypress", "shrub")}


def palette(colors, biome):
    """build.COLORS with the biome's overrides."""
    return {**colors, **PALETTES[biome]}


def ground_shade(biome, xs, ys, slope):
    """Brightness factor per vertex (local metres, slope as rise over
    run): darker on slopes, mottled by position; ones for a biome
    without ground shading."""
    if biome not in GROUND_SLOPE:
        return np.ones(len(xs))
    lo, hi, dark = GROUND_SLOPE[biome]
    shade = 1.0 - dark * np.clip((slope - lo) / (hi - lo), 0.0, 1.0)
    amp, waves = GROUND_MOTTLE[biome]
    mottle = np.zeros(len(xs))
    for k, w in enumerate(waves):
        a = 2.0 * np.pi / w
        # each wave turned by its own angle, so the mottle has no axis
        c, s = np.cos(1.1 * k + 0.4), np.sin(1.1 * k + 0.4)
        mottle += np.sin(a * (c * xs + s * ys)) \
            * np.cos(a * 0.7 * (c * ys - s * xs))
    return shade + amp * mottle / len(waves)


def rock_share(biome, heights, slope):
    """0..1 per vertex: how much of the rock colour (absolute heights,
    slope as rise over run); zeros for a biome without rock."""
    if biome not in ROCK_FROM_M:
        return np.zeros(len(heights))
    lo, hi = ROCK_FROM_M[biome]
    by_height = np.clip((heights - lo) / (hi - lo), 0.0, 1.0)
    lo, hi = ROCK_SLOPE[biome]
    by_slope = np.clip((slope - lo) / (hi - lo), 0.0, 1.0)
    return np.maximum(by_height, by_slope)
# - revised 2026-10-23 (facades, roofs, single-storey houses)
# - revised 2026-10-27 (mediterranean-dry)
# - revised 2026-11-04 (darker mediterranean ground, slope shade, mottle)
