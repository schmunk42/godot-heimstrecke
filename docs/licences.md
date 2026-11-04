<!-- file generated with AI assistance: Claude Code - 2026-10-23 15:10:00 UTC -->

# Licences and data terms

Review of the licences of the map material and the software of Heimstrecke, state of 2026-10-23; decisions and corrections of 2026-10-25 in [Decisions](#decisions). It was done by reading the official texts (URLs below) and the repository. **It is not legal advice**; the open legal points are collected in [Open questions](#open-questions-for-legal-review). Statements marked *(from memory)* or *not verified* were not checked against a primary source.

## Summary

- Five data sources are used and all five allow redistribution of derived data with attribution: OpenStreetMap (ODbL 1.0), DGM1 of the LGL Baden-Württemberg (dl-de/by-2-0), the LiDAR HD of the IGN for the Corsican worlds (Licence Ouverte 2.0, Etalab), GEDTM30 of OpenGeoHub for the Cyprus world (CC BY 4.0), Copernicus DEM GLO-30 (Copernicus WorldDEM-30 licence).
- The `sources` and `attribution` strings of the recipes were not the wording the licences ask for; they are corrected since 2026-10-25, see [Decisions](#decisions).
- Since 2026-10-25 the world selection has a credits screen with the data credits and links, the data licence and the Godot notices; the attribution also shows for five seconds after the start.
- Whether the generated tiles are a Produced Work or a Derivative Database under the ODbL is not settled by any OSMF guideline. Decided on 2026-10-25: the world data is put under the ODbL as a whole, so a shared `.world` package is fine either way.
- The repository bundles no fonts or textures. Since 2026-11-04 it bundles the co-driver's voice clips, synthesised with Piper from a voice trained on public domain recordings, see [Co-driver voice](#co-driver-voice). The project's own code is under the MIT License since 2026-10-25.

## Decisions

Taken on 2026-10-25:

- **World data under the ODbL.** The tiles and tree files of every world are licensed under the ODbL 1.0 as a whole, as recommended in [ODbL analysis](#odbl-analysis) point 4; terrain and horizon keep the licences of their sources, stated per source. This removes the Produced-Work-or-database question for distribution. Every manifest carries it as `data_licence` and a `notice` (ODbL notice, the offer of pipeline, recipe and source extracts at the public repository `github.com/schmunk42/godot-heimstrecke`, the Copernicus liability sentence), written by `pipeline/world.py` and validated by `worlds/world.schema.json`.
- **Code under MIT.** Code, world recipes and documentation of the repository are under the MIT License (`LICENSE`, copyright Tobias Munk); the licence file says that it does not cover the world data.
- **Credits corrected** in all five recipes as proposed in [Credits in the recipes](#credits-in-the-recipes): DGM1 with licence and change note, Copernicus in the "produced using" form with years and rights holders, OSM with the copyright link in the attribution. The IGN credit names the retrieval month (2026-10) in place of the date of the last update, which was not looked up.
- **Credits screen.** The world selection has "Credits and licences" (key C, `godot/scripts/credits.gd`): the game's licence, sources, data licence and notice of the highlighted world, Godot's licence text, its third-party components (Jolt Physics, MIT/Expat, among them) and all their licence texts from `Engine.get_license_info()`. A game started with `--world` skips the selection and with it the credits screen; the attribution still shows for five seconds.

The [open questions](#open-questions-for-legal-review) stay open for a legal review; questions 1 to 4 lose their weight for distribution with the ODbL on the whole world data.

## Data sources

| Data | Licence | Required credit | Derived data | Our status |
|---|---|---|---|---|
| OpenStreetMap (roads, land cover, buildings, trees) via a Geofabrik regional extract | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), [openstreetmap.org/copyright](https://www.openstreetmap.org/copyright) | "OpenStreetMap", linked to the copyright page and naming the ODbL; "© OpenStreetMap contributors" is still accepted. Games: splash screen, game view, credits page or menu, details must be findable ([Attribution Guidelines](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines)) | Produced Work: any licence, with a notice (4.3). Derivative Database: ODbL (4.4) and an offer of the database (4.6) | Credit string correct; add the link; share-alike question open |
| Geofabrik extract | ODbL 1.0 (page footer: "Data processed by Geofabrik GmbH and created by OpenStreetMap Contributors") | no separate duty found | as OSM | Geofabrik's "Technical details" page not read |
| DGM1, LGL Baden-Württemberg | [Datenlizenz Deutschland Namensnennung 2.0](https://www.govdata.de/dl-de/by-2-0) | LGL: `Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0`; a DGM1 metadata record gives `LGL-BW (<year of retrieval>) Datenlizenz Deutschland - Namensnennung - Version 2.0, www.lgl-bw.de`. **Changes must be marked** in the source note | Allowed: reproduce, alter, pass on, merge, also commercially | Credit lacks licence and change note |
| IGN LiDAR HD, MNT 1 m (ground of `bavella`, `korsika-aleria-corte`), Géoplateforme WMS `data.geopf.fr/wms-r` | [Licence Ouverte 2.0 / Etalab](https://www.etalab.gouv.fr/licence-ouverte-open-licence/), as listed for RGE ALTI on [data.gouv.fr](https://www.data.gouv.fr/datasets/referentiel-a-grande-echelle-rge/) and in the Earth Engine catalogue; the LiDAR HD page of the IGN was not read | The licence asks for the source (at least the producer) and the date of the last update *(from memory, not verified against the licence text)*; the recipes say `© IGN – LiDAR HD`, without a date | Allowed: reuse, alter, redistribute, also commercially *(from memory)* | Credit without update date; licence page to be read |
| GEDTM30 v1.2, OpenGeoHub (ground of `zypern-ayia-napa`), global COG on `s3.opengeohub.org` | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), stated in the [repository](https://codeberg.org/openlandmap/GEDTM30) and on Zenodo | Name the creator and the licence, link it, mark changes; the recipe says `GEDTM30 v1.2 © OpenGeoHub (retrieved 2026-10), CC BY 4.0, modified` | Allowed: share and adapt, also commercially | Credit with licence and change note; the Zenodo record still says "testing purposes only" |
| Copernicus DEM GLO-30 (horizon ring), AWS bucket `copernicus-dem-30m` | Copernicus WorldDEM-30 licence, free of charge ([AWS registry](https://registry.opendata.aws/copernicus-dem/)) | `© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.` For modified data prefixed with `produced using Copernicus WorldDEM-30`. Plus: "The organisations in charge of the Copernicus programme by law or by delegation do not incur any liability for any use of the Copernicus WorldDEM-30." | Allowed to the public with these notices | Credit shortened, no modified form, no disclaimer |
| OSRM response (`route.json`) | server: no licence stated, no guarantees; data: OSM, ODbL | OSM credit | committed as a fixture | One manual fetch, see below |
| Nominatim | usage policy of the OSMF | none for single results (Geocoding guideline) | not stored | Coordinates of Berglen and Crailsheim were looked up once, nothing stored |

Usage policies: the OSRM demo server asks for at most one request per second, a real User-Agent and "reasonable, non-commercial" use ([wiki](https://github.com/Project-OSRM/osrm-backend/wiki/Api-usage-policy)); Nominatim the same, plus caching and no bulk queries ([policy](https://operations.osmfoundation.org/policies/nominatim/)). A route is fetched once by hand and committed; the pipeline itself never calls a server (it only parses an OSRM response).

## Credits in the recipes

`sources[].credit` and `attribution` are identical in `stuttgart`, `berglen`, `crailsheim` and in the README of the time. Corrections, applied to all recipes on 2026-10-25 (see [Decisions](#decisions)):

| Source | Now | Proposed |
|---|---|---|
| OpenStreetMap | `© OpenStreetMap contributors` | keep; make "OpenStreetMap" a link in the credits screen |
| DGM1 | `Datenquelle: LGL, www.lgl-bw.de` | `Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0 (verändert)`, or the metadata form `LGL-BW (<year>) Datenlizenz Deutschland - Namensnennung - Version 2.0, www.lgl-bw.de, verändert` with the year of retrieval |
| Copernicus | `© DLR e.V. / Airbus, provided under COPERNICUS by the European Union and ESA` | `produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.` The liability sentence goes to the credits screen and the package README |

Proposed `attribution`: `Data: © OpenStreetMap contributors (ODbL, openstreetmap.org/copyright); terrain: Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0 (verändert); horizon: produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.` The German "verändert" belongs to the German LGL wording. Whether `worlds/world.schema.json` limits the length of these strings was not checked.

## ODbL analysis

Relevant clauses of the ODbL: **4.2** whoever publicly conveys the database, a Derivative Database or a Collective Database includes the licence or its URI. **4.3** a publicly used Produced Work needs a notice that the content comes from the database and is available under the ODbL. **4.4** a publicly used Derivative Database must be ODbL. **4.5** the share-alike duty does not apply to Collective Databases, to producing Produced Works, or to purely internal use. **4.6** whoever publicly uses a Derivative Database, or a Produced Work from one, offers a machine-readable copy of the whole Derivative Database or an alteration file, free over the internet.

What the [OSMF guidelines](https://osmfoundation.org/wiki/Licence/Community_Guidelines) say: a Produced Work is usually an image or a printed map, not a database dump; the test is whether the published result is meant for extracting the original data. 3D models, games and glTF are not mentioned. A 10 km by 10 km world is far above every "Substantial" threshold of the Substantial guideline. Non-OSM data (DGM1 heights) that adds or replaces a property from a single source fits the Collective Database guideline.

Assessment:

1. **Tiles.** Triangulated road ribbons, kerbs, markings and building meshes, with most OSM attributes lost and play as the purpose, are most likely a Produced Work (notice only). Against that: the vertex positions reproduce OSM geometry over the whole area, road centrelines could be recovered from ribbons, and the per-tile tree instance files (`.trees`, `.trunks`) are close to a list of positions of mapped trees. The tree files and anything that keeps node or way data are the weakest part. No tile was inspected for recoverability.
2. **The game shows the map.** Public use of a Produced Work: show the 4.3 notice. Internal use needs nothing under 4.4 and 4.5; demonstrations at events and builds sent outside the company are public use.
3. **Distributing `.world` packages.** If the tiles are a pure Produced Work, the notice is enough. The intermediate data of the pipeline (road graph, conformed terrain, lifted bridge decks) is plausibly a Derivative Database; then 4.6 still asks for an offer of it or of an alteration file. Publishing the pipeline and the recipes and naming the Geofabrik extract is a reasonable alteration file, but no guideline says that it satisfies 4.6. The conformed terrain blends OSM roads and DGM1 heights and is the case where a Derivative Database claim is hardest to rule out. The Copernicus horizon contains no OSM data.
4. **Practical recommendation.** Share a package only if it carries the OSM notice, the ODbL link, the `sources` and the Copernicus disclaimer, plus an offer text such as "The tiles are generated from OpenStreetMap data; the pipeline, the recipe and the source extract URL to regenerate them are at <public repository URL>". Make the repository with pipeline and recipes public before sharing outside the team. The safest variant is to put the tile geometry and the tree files under the ODbL as well and distribute the package as "contains ODbL-licensed data" with the DGM1 and Copernicus parts under their own notices: it removes the Produced-Work-or-database question and costs a hobby game nothing. Do not claim one licence over the whole package; state it per source.
5. **Game builds** without world data contain no OSM data. A build that embeds a world needs the same notice. The licence of the builds is the project's decision.

## Software

Build-time Python dependencies of the pipeline (`pyproject.toml`, versions from `uv.lock`); no Python code goes into game builds or packages:

| Package | Licence |
|---|---|
| osmium (pyosmium) 4.3.2 | BSD-2-Clause (verified) |
| shapely 2.2.0 | BSD-3-Clause, wheels bundle GEOS (LGPL-2.1) *(from memory)* |
| pyproj 3.8.0 | MIT *(from memory)* |
| rasterio 1.5.2 | BSD-3-Clause, wheels bundle GDAL *(from memory)* |
| numpy 2.5.4 | BSD-3-Clause *(from memory)* |
| trimesh 5.1.1 | MIT *(from memory)* |
| mapbox-earcut 2.1.0 | ISC *(from memory)* |
| requests 2.34.2 | Apache-2.0 *(from memory)* |
| jsonschema 4.26.0 | MIT *(from memory)* |

Transitive packages are MIT or BSD except certifi (MPL-2.0, file-level copyleft) *(from memory)*. The only copyleft code (GEOS, certifi) is not distributed with the game or the packages; re-check if the pipeline is ever shipped as a container or executable. An authoritative list needs a licence tool over `uv pip list`; that was not done.

**Godot** is MIT: the copyright notice and licence text must be included in distributed games, a link in the credits is described as acceptable ([godotengine.org/license](https://godotengine.org/license/)); the third-party components inside the engine are listed in Godot's `COPYRIGHT.txt`. Jolt Physics is MIT *(from memory)*. Godot offers `Engine.get_license_text()`, `Engine.get_license_info()` and `Engine.get_copyright_info()` for a credits screen *(from memory, check the 4.7 documentation)*. Godot 4.7.2 itself was not checked.

**Bundled assets**: the co-driver's voice clips in `godot/audio/codriver/` (see below). Otherwise `godot/` holds scripts, scenes, JSON and configuration only; cars are procedural bodies and the engine sounds are synthesised in code (`car_audio.gd`); no fonts, textures or images, no `addons/`.

## Co-driver voice

Decided on 2026-11-04. The clips in `godot/audio/codriver/` (one Ogg Vorbis file per word or phrase of the pace notes) are made by `tools/codriver_voice.py` (`make voice`) with [Piper](https://github.com/OHF-Voice/piper1-gpl) and the voice `en_US-norman-medium` from [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices) at a fixed revision:

- **Voice model**: the repository is MIT; the model card names the dataset as LibriVox recordings, public domain, and the training as "trained from scratch" by Bryce Beattie ([brycebeattie.com/files/tts](https://brycebeattie.com/files/tts/)). No other voice went into it, so the clips carry no dataset licence. The clips are put under the MIT License of the game; the credits screen names Piper, the voice and its maker.
- **Piper** itself (piper-tts 1.8.0, GPL-3.0-or-later per its package metadata) is a tool run once on the developer's machine; it is neither committed nor shipped, and its licence does not reach the audio it makes.
- **Voices not taken**: `en_US-joe-medium` sounded best and its own dataset is CC0, but its model card says it is fine-tuned from `en_US-lessac`, which is trained on the Blizzard 2013 Lessac data under a research licence granted only to the named licensee; `en_US-john-medium` is fine-tuned from a voice whose data is not stated. Both were left out for that reason. `en_GB-cori-high` (LibriVox, from scratch) would be clean as well.

## Open questions for legal review

1. Are the glTF tiles and the tree-instance files a Produced Work or a Derivative Database, or each by part? No guideline covers 3D game geometry.
2. Do the intermediate data of the pipeline count as a publicly used Derivative Database when only the tiles are shared, and does a public pipeline repository plus recipe satisfy the 4.6 offer?
3. Does conforming the terrain to the OSM roads pull the DGM1 part under the ODbL, and is that compatible with dl-de/by-2-0 (which permits merging and passing on, with the change note)?
4. Is the whole package under the ODbL acceptable next to the Copernicus licence, whose notices stay with the horizon files?
5. From which point is showing the game "public use": events, shared builds, external testers?
6. Do the committed `route.json` files (OSRM output, OSM-derived) need more than the OSM credit?
7. Which licence do the project's own code and content get, and does a build with an embedded world fall under the ODbL notice duty?

## Checklist for a new world

1. The area lies in Baden-Württemberg (DGM1) or France (LiDAR HD); elsewhere GEDTM30 (CC BY 4.0) is wired, but look for an open 1 m source of the country and its licence first.
2. `osm_region` is the right Geofabrik path.
3. Copy `sources` and `attribution` from the reference world (corrected as above), with the year of the DGM1 retrieval.
4. A route from OSRM is fetched once by hand, below one request per second, with an identifying User-Agent, preferably from the FOSSGIS server; commit the response.
5. Lookups such as Nominatim are one-off and not stored.
6. After `make world W=<id>` check `sources` and `attribution` in the built `world.json`.
7. Before `make pack` for sharing: the package carries the OSM notice, the ODbL link, the offer text, the Copernicus disclaimer and the repository URL, and pipeline and recipe are public.
8. The credits screen shows the Godot MIT notice, Jolt and the three data credits with links.
9. Re-check the [open questions](#open-questions-for-legal-review) with legal before the first external release.

## Could not verify

- The LGL DGM1 product page and its own terms (the portal gave no text, the metadata record fetch failed); the "LGL-BW (year)" form comes from a search-result snippet, and the "Rechtliches" section is generic for LGL open data.
- The full Copernicus licence PDF (the notices are quoted from the ESA Dataspace page and the Earth Engine catalogue).
- The German FOSSGIS policy of the OSRM demo server and whether `router.project-osrm.org` is now served from `routing.openstreetmap.de`.
- Geofabrik's "Technical details" page and any fair-use limit.
- The Python package licences marked *(from memory)*, Godot 4.7.2's exact third-party list, Jolt's licence, the wheel contents.
- The OSMF Regional Cuts and Horizontal Map Layers guidelines.
<!-- - revised 2026-10-23 (IGN LiDAR HD for the Corsican worlds) -->
<!-- - revised 2026-10-25 (decisions: ODbL world data, MIT code, credits corrected, credits screen) -->
<!-- - revised 2026-10-27 (GEDTM30 for Cyprus) -->
