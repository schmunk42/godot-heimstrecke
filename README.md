<!-- file generated with AI assistance: Claude Code - 2026-10-23 14:00:00 UTC -->

# Heimstrecke

A racing game on real roads: pick a world, pick a start, drive. Roads, buildings and trees come from OpenStreetMap, the ground from 1 m terrain models (LGL Baden-Württemberg, IGN LiDAR HD in Corsica), the far horizon from the Copernicus DEM.

Status: prototype. The game was called "Test Drive NT" until October 2026.

## Play

1. Download the game for your system from the [latest release](https://github.com/schmunk42/godot-heimstrecke/releases/latest): Linux, Windows or macOS, and unpack it.
2. Download one or more worlds (`.world` files) from the same release and put them next to the executable (on macOS next to the `.app`).
3. Start the game and pick a world.

| World | File | Size | |
|---|---|---|---|
| Stuttgart | `stuttgart-1.world` | about 85 MB | city, tunnels, bridges, lap route |
| Berglen | `berglen-1.world` | about 50 MB | villages and country roads, Rems-Murr |
| Crailsheim | `crailsheim-1.world` | about 45 MB | small town, Hohenlohe |
| Bavella | `bavella-1.world` | about 110 MB | Corsican mountain pass |
| Korsika: Aléria – Corte | `korsika-aleria-corte-1.world` | about 110 MB | a strip along the T 50 |

A world can also be given on the command line, a `.world` file or a world directory: `./heimstrecke.x86_64 -- --world /path/to/stuttgart-1.world`. On macOS remove the quarantine flag before the first start: `xattr -dr com.apple.quarantine "Heimstrecke.app"`. The macOS build is signed ad-hoc only, the Windows build has no icon yet.

## Drive

W/S throttle and brake, A/D steer, Space handbrake, F puts the car onto the nearest road (or back upright where it is in a world without road lines), R back to the start, V switches the camera (far, close, driver's seat), M mutes the co-driver who calls the pace notes of the route (once voice clips exist), # shows and copies the position (world, road, lat/lon, camera) for bug reports with a screenshot. In the start menu C switches the car, a click on the map starts on the nearest road there. A minimap sits at the bottom right; signs stand at the roads in the style of the country.

## Build from source

For developing the game or building worlds yourself (Linux or macOS, about 750 MB of downloads for Stuttgart, 4 GB RAM free):

```bash
# Prerequisites: git, make, curl, uv (https://docs.astral.sh/uv/), Godot 4.7
git clone https://github.com/schmunk42/godot-heimstrecke.git
cd godot-heimstrecke
make dev          # download, build the world Stuttgart, start the game
```

`make dev` downloads what is missing, builds the world into `./data/out/worlds/stuttgart/` and starts the game; later `make drive` is enough. Another world: `make dev W=berglen`, `W=crailsheim`, `W=bavella` or `W=korsika-aleria-corte` (the Corsican worlds download about 1.6 GB of LiDAR HD each). `make pack W=<id>` packs a built world into `./data/out/packages/<id>-<version>.world`, `make export` builds the desktop binaries into `./build/` (once before: `make export-image`). `GODOT=/path/to/godot make drive` if `godot` is not on the `PATH`; `make fly` opens a free camera, `make test` runs the headless smoke test.

## More

- [docs/world-creation.md](./docs/world-creation.md) – how a world is made: recipe, data, build, checks, pitfalls
- [docs/reference.md](./docs/reference.md) – layout, all make targets, launcher arguments, screenshots, desktop build
- [docs/licences.md](./docs/licences.md) – licences of the map data and the software, attribution
- AI assistants: the project skill [heimstrecke-worlds](./.claude/skills/heimstrecke-worlds/SKILL.md) knows the world pipeline and its pitfalls

## Licence

Code, world recipes and documentation: [MIT](./LICENSE). World data (the tiles and tree files in a `.world` package) contains OpenStreetMap data and is licensed under the [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/); terrain and horizon keep the licences of their sources. Every world carries its credits and this notice in `world.json`, the game shows them under "Credits and licences" in the world selection, details in [docs/licences.md](./docs/licences.md).

Data: © OpenStreetMap contributors (ODbL, [openstreetmap.org/copyright](https://www.openstreetmap.org/copyright)); terrain (DGM1): Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0 (verändert); terrain in Corsica: © IGN – LiDAR HD (retrieved 2026-10), Licence Ouverte 2.0, modified; horizon: produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
<!-- - revised 2026-10-23 (Corsican worlds, LiDAR HD, F onto the nearest road) -->
<!-- - revised 2026-10-23 (camera views, free start, minimap, signs, # readout) -->
<!-- - revised 2026-10-25 (Play first: binaries and worlds from GitHub releases) -->
<!-- - revised 2026-10-25 (licence: MIT code, ODbL world data, corrected credits) -->
<!-- - revised 2026-10-26 (clone from GitHub, internal docs out of the list) -->
