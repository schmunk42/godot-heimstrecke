---
name: heimstrecke-worlds
description: Use when creating, changing or debugging a Heimstrecke world or the world pipeline (pipeline/*.py, worlds/<id>/): recipe, data sources (OSM, DGM1, LiDAR HD, Copernicus, OSRM), sea, biome, turned worlds, road heights, terrain conform, clipping, z-fighting, flicker and shimmer, sun and shadows, tunnels, bridges, sidewalks, start points, gates, packaging, licences. Also load it on any feedback about how a world looks or drives (a screenshot, a screen recording, the # position line, "flickers", "floats", "clips"), and fold the lesson back into this skill. Not for cars or audio.
---
<!-- file generated with AI assistance: Claude Code - 2026-10-23 14:50:00 UTC -->

# Heimstrecke worlds

Full text: `docs/world-creation.md` (how a world is made, constants, known limits), `docs/licences.md` (data and software licences), `docs/reference.md` (make targets, launcher arguments). Read the section you need before changing pipeline code; the sections below are the rules that cost the most time to learn. The code is the truth: constants named here can be found with `grep`.

## New world

1. Recipe `worlds/<id>/world.json` (copy `sources`, `attribution`, `osm_region` from a neighbour, `bbox` = centre ± 0.075° lon / ± 0.05° lat for 10 km, `horizon_km` 40). Check `uv run python pipeline/world.py vars worlds/<id>/world.json` before downloading.
2. `nice -n 19 make world W=<id>` (host rules below). Four hard gates must PASS.
3. `starts.json` from edge midpoints of the extract, with `road`; no `toward` means an arbitrary direction. Never use a map coordinate for `at` (it snaps tens of metres away); never name a road whose extract edge has no name.
4. Drive it. Then baselines from an *unchanged* build: `clipping_baseline.json` (else the ratchet says SKIPPED), `godot/tests/reference_<id>.json`.
5. `make pack W=<id>` (limit 500 MB). Only add `route.json` when asked; a world without route is valid.
6. Outside Baden-Württemberg (France): `"terrain": "lidarhd"`; Corsica also `"biome": "mediterranean"`. Elsewhere `"terrain": "gedtm30"` and, outside UTM zone 32, `"epsg"` (Cyprus 32636); Cyprus has `"biome": "mediterranean-dry"`. A road that runs diagonally gets a turned strip (`width_km`, `heading_deg`): fit the heading through the road's nodes in the extract, do not guess it from a map.

## Data

- DGM1 (LGL BW) has **no bridges and no buildings**: steep ramps at bridge or tunnel ends are artefacts of the end node taking a DGM1 median on the embankment. Look at structure ends before believing a grade.
- LiDAR HD (IGN WMS): values below -5 m are no data (the service resamples -9999 into the coast); a turned raster needs `TURNED_PAD_M` beyond the margin, else `Dgm1Raster` refuses it or the clipping report reads past it. Blocks are cached, the warp still takes minutes.
- Sea comes from the OSM coastline (land left, sea right); NaN inland stays NaN on purpose, never fill it silently.
- Copernicus is a surface model, 2.5 to 6 m too high: horizon only. Pick its 1° tiles from the **horizon** square.
- Outside Germany and France: `"terrain": "gedtm30"` (since 2026-10-27), a window of the global GEDTM30 COG, no key. Its file says `scale 0.1`, the values are metres; sea is no data. 30 m is a substitute raster: measure the gates, do not loosen them (Ayia Napa passes all four). The UTM zone comes from the recipe's `epsg` (default 25832, a raster in another zone gets `_<epsg>` in its name). Look for an open 1 m model of the country first; alternatives and licences in `docs/world-creation.md`, "Terrain sources outside Germany and France".
- Corsica is maquis, not bare ground (2026-11-04, compared with Street View on the D 268): OSM maps only part of it, so `biome.MAQUIS` fills the land without another cover below 1300 m and below the first rock slope with wide shrubs over a dark olive ground. It costs instances: Bavella went from 2.8 to 3.8 million plants; watch load time and render memory. For a look question, open Street View at the `#` position (`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=<lat>,<lon>&heading=<deg>&pitch=<deg>`).
- Signs know `de`, `fr` and `cy` (`country_of()` from the Geofabrik path); any other country gets the German style. Cyprus: signs on the left (`LEFT_HAND`), Greek over Latin from the places' name variants (`extract.PLACE_NAMES`), motorway green, B roads and signposts blue.
- `fetch.py` deletes the zips after building the GeoTIFF: keep the GeoTIFF, copy it from another machine if `opengeodata.lgl-bw.de` is down. DGM1 stops at the state border (nodata cells, Crailsheim 0.3 %).
- An old `extract.pkl` (changed `ROAD_TAGS`) makes `build.py` exit 2; `make world` re-extracts. Every recipe edit re-extracts.
- Tracks: recipe `"tracks": ["grade1", "grade2"]` makes `highway=track` gravel roads (3 m, rank 0, access ignored, `TRACK_CLEAR` through forest), plus plain `service` ways linking a track to a road. Without the key no track and no service way is extracted; keep it that way so the other worlds stay byte-identical. Gravel has no own grip yet.
- OSM: `layer` tags are unreliable, use plan-view geometry; street names do not identify junctions or tunnels; `service` roads are not in the network; access-restricted roads are excluded.
- The OSRM demo server is flaky and has a usage policy: fetch once, commit the response.
- Licences travel in the manifest (`sources`, `attribution`); never drop them from a recipe. The ODbL share-alike question for shared packages is open, see `docs/licences.md`.

## Geometry rules

- **New geometry goes into a new tile layer**, never into `roads`: `metrics.shared_heights()` indexes every `roads` vertex by (x, z), any other surface at the same position breaks the gate.
- Godot materials are one-sided: emit structure surfaces with both windings, ceilings and tubes on separate vertices.
- Read widths from `net.half[s]` (per sample), not per-edge width; conform with the old width fails `terrain_below_roads` after the taper.
- Terrain is a 10 m grid and `push_down` lowers every triangle corner under a road: terrain above the road is not possible with the 2 cm gate; the edge falls off with the 20° skirt only, no bank rises above it (removed 2026-10-25, it read as a raised kerb).
- Conform has a keep rule: grid points nearer to a tunnel or deck segment than to a conformed road keep DGM1. Without it every portal gets a 15 to 40 m trench and every bridge start an embankment.
- Inland water is a surface in the `water` layer over a bed carved into the terrain mesh only (`water.py`, 2026-11-04: rivers were blue paint on slopes). Its level comes from the banks, never the raster inside the polygon, and the bed has a minimum depth with no cap, because terrain left near the surface flickers. Clip the polygons to the playable square (the raster ends beyond it; a sample outside stops the build). In `build_terrain` the local `water` is the colour mask; the parameter is `inland`.
- Tunnels: cut the terrain only where it meets the cross-section (no lid, no masks); classes covered / slot / open by `COVER_MIN`; drop wall pieces that stand on another carriageway.
- Bridges: find crossings by geometry; raise decks to `CLEAR_MIN` + `DECK_DEPTH`; `low` (creek) bridges are plain roads; transverse end walls and parapet ends must not stand on a carriageway (the smoke drive caught this).
- Buildings under a deck or a raised road end 1 m below it (`RoadsOver` in `build.py`); only roads more than 2 m above the building's floor count, so footprints touching a street at their own level stay as they are; a footprint at least half under such roads is capped as a whole (`UNDER_SHARE`).
- Clipping: skirts, sidewalks and corners **yield** to carriageways (`priority.py`); a sidewalk corner must ignore its own arms and its own node hull. Equal-class strips overlapping (z-fight) are an open problem, not a regression.

## Gates, determinism, tests

- Hard gates (exit 3): `shared_heights`, `terrain_below_roads`, `max_grade` (25 %), `node_heights` (2 m). The clipping report is a ratchet against the committed baseline with 2 % slack.
- Recipe switches (`terrain`, `biome`, `width_km`, `heading_deg`) must leave the default path untouched: the square temperate worlds stay byte-identical, Stuttgart and Bavella are the references. `half` is a scalar or `[hx, hy]`, unpack it with `np.broadcast_to(half, 2)`.
- Before a change: build the unchanged `master` into a baseline directory. A refactor must keep `sha256sum tile_*.glb horizon.glb` identical; commit it separately before the behaviour change. Two builds of the same code are byte-identical; if not, something is non-deterministic.
- Do not judge geometry on a substitute raster (Copernicus as DGM1): grade, braking and tunnel checks fail for no good reason.
- Smoke test: steered drives (`smoke.json`), because a straight drive does not reach a portal. Do not rewrite `reference_<id>.json` unless `car.gd` changed.
- A route start or start point must lie on a drivable road with free space around it.
- Do not change the car (`car.gd`) in world work.
- Screenshots (software render, no shadows) illustrate, the metrics are the gate. Software renders show fewer minor roads than a GPU.

## Look on the GPU

- Ask for the `#` position line and a 3-5 s screen recording (the user's recordings land in `~/Videos/`). Extract frames with `ffmpeg -i <mp4> -vf fps=4 f%03d.png`, then crop the same region from two consecutive frames at full resolution and compare them side by side; one frame shows no flicker.
- Tell the two flickers apart: z-fighting is two coplanar surfaces swapping (whole patches, also with a still camera); shadow shimmer is a fine dot or diagonal raster on lit faces and at shadow edges that moves on the slightest camera move. The 2026-11-03 report "textures flicker" was shadow shimmer, the buildings have no textures.
- The sun is built in `world.gd` (`_setup_environment`): its shadow range follows the tree shadows (`trees.gd`, up to 450 m), currently 500 m with blend splits, `shadow_bias` 0.15, `shadow_normal_bias` 1.5 and an 8192 shadow map in `project.godot`. A longer range coarsens the near texels (1500 m shimmered); walls nearly parallel to the sun show acne when the biases drop.
- The software render (`make render`) cannot confirm a GPU look fix: it runs without shadows and draws stipple with them. The user checks with `make drive`.
- "The world looks flat" (Bavella, 2026-11-04) was not missing shadows: pale uniform ground under full sky light. The world material reads the vertex colours as linear, so a palette colour shows much lighter than its numbers (0.70 olive came out near white); judge `biome.py` colours in a render, not by their values. The sun scene has half the ambient light and SSAO (`world.gd`); the mediterranean ground darkens on slopes and is mottled (`ground_shade`). Bavella renders need `RENDER_MEMORY=6g` (2.8 million trees, 3 GB is killed).
- Fine stripes in a texture (the old chevron boards) shimmer on the GPU when the camera moves: draw such patterns as solid-colour geometry a little in front of their plate (`STRIPE_LIFT` in `route_marks.gd`). Red and white stands only across the road straight on where the route turns; every other arm gets hay bales (the user's choice, 2026-11-04), because red and white everywhere flickers and loses its meaning.
- A new look for props (barriers, ads, signs) is offered before it goes into a world: `godot/tools/render_props.gd` renders the game code on a synthetic junction and sign rows in the render container (the `make render` docker flags with `--script res://tools/render_props.gd -- --out /work/out`); for a choice, add variants side by side with a code above each and let the user pick. It needs no world data and takes seconds.

## Host (workhorse, 4 vCPU, 7.6 GiB, shared)

`cat /proc/loadavg` below 4 and `free -h` above 1 GiB before downloads, builds, renders; `nice -n 19`; one heavy job at a time; no database containers. Docker cannot see `/tmp`, render from a path under the home directory. A worktree has no `data/`: symlink `data/raw` from the main checkout and `cp -a` `data/out` (about 430 MB). Its first `make test` imports all assets into a fresh `.godot/` and loads in about 14 s against the 15 s limit; a second run is the measurement. Areas much larger than 10 km are built on a developer machine.

## Process

The main branch is `master`. Larger work runs on a branch in its own worktree and is fast-forwarded into `master`; small fixes may be committed on `master` directly (the developer allows it, `HRZG_GUARD_OFF` in the local settings). Conventional Commits with `[*]`, no amend, no force push, additive merge of `origin/master` on conflicts. Report deviations over 10 % from expected numbers instead of accepting them. Update `docs/world-creation.md` when a rule here changes.

## Feedback improves this skill

After acting on feedback about a world (a bug report, a screenshot, a recording, a correction of how you worked), add what was learnt here before closing the task: one rule with its reason, in the section it belongs to, a date where it helps, and a `revised` line at the end. Change a rule that turned out wrong instead of adding a second one beside it. Leave out what the code or `docs/` already say; point to them. Commit the skill change with the fix.
<!-- - revised 2026-10-23 (LiDAR HD, sea, biome, turned worlds) -->
<!-- - revised 2026-10-25 (buildings under roads) -->
<!-- - revised 2026-10-25 (terrain sources outside Germany and France) -->
<!-- - revised 2026-10-25 (tracks) -->
<!-- - revised 2026-10-27 (GEDTM30, epsg, mediterranean-dry, signs outside DE/FR) -->
<!-- - revised 2026-10-27 (signs in Cyprus) -->
<!-- - revised 2026-11-03 (GPU look and shadow shimmer, worktree data/out, master, feedback loop) -->
<!-- - revised 2026-11-04 (texture stripes shimmer, red and white only straight on, render_props for looks) -->
<!-- - revised 2026-11-04 (flat look: linear vertex colours, ambient, SSAO, ground shade) -->
<!-- - revised 2026-11-04 (inland water as a surface) -->
<!-- - revised 2026-11-04 (Corsican maquis, Street View link) -->
