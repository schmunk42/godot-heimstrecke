# file generated with AI assistance: Claude Code - 2026-10-20 22:37:57 UTC
# Data pipeline, game and software rendering. The world targets are file
# targets: `make drive` rebuilds only what is older than its inputs
# (downloads, extract, world), so after a pull that touched pipeline/
# the world is rebuilt before the game starts.

# The world: `make world W=<id>` builds worlds/<id>/world.json into
# data/out/worlds/<id>/. Area, raw input files, download URL, route and
# starts all come from the recipe, so a new world needs no edit here.
W ?= stuttgart
RAW := data/raw
OUT := data/out
RECIPE := worlds/$(W)/world.json
WORLD_DIR := $(OUT)/worlds/$(W)
WORLD := $(WORLD_DIR)/world.json
# the extract depends on the recipe's bbox, so it lives per world
EXTRACT := $(WORLD_DIR)/extract.pkl
PACKAGES := $(OUT)/packages
COP_URL := https://copernicus-dem-30m.s3.amazonaws.com
COP_TILE = $(subst _,_00_,$*)_00

# Goals that need no recipe; everything else reads it once.
NO_RECIPE_GOALS := help init clean build render
define NL


endef
ifneq ($(filter-out $(NO_RECIPE_GOALS),$(or $(MAKECMDGOALS),help)),)
ifeq ($(wildcard $(RECIPE)),)
$(error recipe $(RECIPE) not found (W=$(W), see worlds/))
endif
# One uv call prints CENTER, SIZE, EPSG, BBOX, COP, TERRAIN_SOURCE, TERRAIN,
# PBF, PBF_GLOB, PBF_URL, ROUTE, STARTS and TRACKS as KEY=value lines
# (pipeline/world.py).
WORLD_VARS := $(shell uv run python pipeline/world.py vars --raw $(RAW) \
	$(RECIPE) | tr '\n' ';')
$(eval $(subst ;,$(NL),$(WORLD_VARS)))
ifeq ($(CENTER),)
$(error cannot read recipe $(RECIPE), see the error above)
endif
# an existing regional extract under another name (a dated download) is
# reused
PBF := $(firstword $(wildcard $(PBF_GLOB)) $(PBF))
endif

GODOT ?= godot
STEP := tools/step.sh

# The render image; render.sh reads the same name from RENDER_IMAGE.
RENDER_IMAGE ?= heimstrecke-render:latest
export RENDER_IMAGE

# Desktop export, see export/Dockerfile. GODOT_VERSION is also set in the
# CI configuration; change both together.
GODOT_VERSION ?= 4.7.2
EXPORT_IMAGE ?= heimstrecke-export:$(GODOT_VERSION)

# a failed step must not leave a fresh-looking output behind
.DELETE_ON_ERROR:
.PHONY: help init download extract world rebuild-world pack drive up fly \
	test test-notes test-gates test-codriver dev clean build render export-image export public

# Help based on https://gist.github.com/prwhite/8168133 thanks to @nowox and @prwhite
# And add help text after each target name starting with '\#\#'
# A category can be added with @category

HELP_FUN = \
		%help; \
		while(<>) { push @{$$help{$$2 // 'options'}}, [$$1, $$3] if /^([\w-]+)\s*:.*\#\#(?:@([\w-]+))?\s(.*)$$/ }; \
		print "\nusage: make [target ...]\n\n"; \
	for (keys %help) { \
		print "$$_:\n"; \
		for (@{$$help{$$_}}) { \
			$$sep = "." x (25 - length $$_->[0]); \
			print "  $$_->[0]$$sep$$_->[1]\n"; \
		} \
		print "\n"; }

help: ##@system show this help
	#
	# General targets
	#
	@perl -e '$(HELP_FUN)' $(MAKEFILE_LIST)

init: ##@data create data/raw/dgm1, data/raw/lidarhd, data/raw/gedtm30 and data/out
	@mkdir -p $(RAW)/dgm1 $(RAW)/lidarhd $(RAW)/gedtm30 $(OUT)

download: init $(PBF) $(COP) $(TERRAIN) ##@data download OSM, Copernicus and the terrain model (DGM1, LiDAR HD or GEDTM30) of world W=<id> (Stuttgart about 750 MB, skips what exists)

$(PBF):
	@mkdir -p $(RAW)
	@$(STEP) --plain "download OSM extract $(notdir $@)" \
		curl -fL --progress-bar -o $@.part $(PBF_URL)
	@mv $@.part $@

# $* is the tile like N48_E009, the bucket name is N48_00_E009_00
$(RAW)/cop30_%.tif:
	@mkdir -p $(RAW)
	@$(STEP) --plain "download Copernicus tile $* (about 45 MB)" \
		curl -fL --progress-bar -o $@.part \
		$(COP_URL)/Copernicus_DSM_COG_10_$(COP_TILE)_DEM/Copernicus_DSM_COG_10_$(COP_TILE)_DEM.tif
	@mv $@.part $@

$(TERRAIN):
	@$(STEP) "download $(TERRAIN_SOURCE) terrain and convert (DGM1 Stuttgart about 450 MB, LiDAR HD Bavella about 1.6 GB)" \
		uv run python pipeline/fetch.py --center $(CENTER) --size $(SIZE) \
		--width $(WIDTH) --heading $(HEADING) --epsg $(EPSG) \
		--source $(TERRAIN_SOURCE) --out $(RAW)

$(EXTRACT): $(PBF) $(RECIPE) pipeline/extract.py
	@mkdir -p $(WORLD_DIR)
	@$(STEP) "extract roads, areas, buildings (about 40 s)" \
		uv run python pipeline/extract.py $(PBF) --bbox $(BBOX) --out $@ \
		$(if $(TRACKS),--tracks $(TRACKS))

extract: $(EXTRACT) ##@data cut the OSM extract for world W=<id> (when missing or outdated)

$(WORLD): $(EXTRACT) $(TERRAIN) $(COP) $(RECIPE) $(ROUTE) $(STARTS) \
	$(wildcard pipeline/*.py)
	@$(STEP) "build world tiles, terrain, tunnels, metrics (about 45 s)" \
		uv run python pipeline/build.py $(EXTRACT) \
		--terrain $(TERRAIN) --horizon-dem $(COP) \
		--recipe $(RECIPE) --out $(WORLD_DIR)

world: $(WORLD) ##@data build world W=<id> (default stuttgart) into data/out/worlds/<id>/ (when missing or older than its inputs)

rebuild-world: ##@data rebuild extract and world W=<id> even if they look current
	@rm -f $(EXTRACT) $(WORLD)
	@$(MAKE) --no-print-directory world

pack: $(WORLD) ##@data pack world W=<id> into data/out/packages/<id>-<version>.world (ZIP, max 500 MB)
	@$(STEP) "pack world $(W) (about 10 s)" \
		uv run python pipeline/pack.py --recipe $(RECIPE) \
		--world $(WORLD_DIR) --out $(PACKAGES)

drive: world ##@game start the drive scene with the start menu
	@$(STEP) --plain "drive (Esc menu, R reset, F upright)" \
		$(GODOT) --path godot res://scenes/drive.tscn \
		-- --world $(WORLD_DIR)

up: drive ##@game same as drive

fly: world ##@game start the free camera (WASD/arrows, QE, mouse look, 1-9 jump)
	@$(STEP) --plain "fly" $(GODOT) --path godot res://scenes/fly.tscn \
		-- --world $(WORLD_DIR)

test: world ##@test run the headless drive smoke test
	@$(STEP) "smoke test (headless)" \
		$(GODOT) --headless --path godot --script res://tests/drive_smoke.gd \
		-- --world $(WORLD_DIR)

test-notes: ##@test check the pace notes of drawn routes (no world needed)
	@$(STEP) "pace notes test (headless)" \
		$(GODOT) --headless --path godot --script res://tests/pace_notes_test.gd

test-gates: ##@test check gate spacing and barrier arcs of a synthetic route (no world needed)
	@$(STEP) "route gates test (headless)" \
		$(GODOT) --headless --path godot --script res://tests/route_gates_test.gd

test-codriver: ##@test check when the co-driver calls the pace notes (no world needed)
	@$(STEP) "co-driver test (headless)" \
		$(GODOT) --headless --path godot --script res://tests/co_driver_test.gd

dev: download world drive ##@game everything from a fresh checkout: download, build, drive

clean: ##@data delete data/out/worlds/<id>/ of world W=<id>, extract included (downloads stay)
	rm -rf $(WORLD_DIR)

build: ##@render build the software-render image (Godot, Xvfb, Mesa llvmpipe)
	docker build -t $(RENDER_IMAGE) render

public: ##@release write the public snapshot of HEAD to the branch master (tools/public.sh)
	@tools/public.sh

render: ##@render render the viewpoints to data/out/screenshots/<timestamp>/
	./render/render.sh

export-image: ##@export build the export image (Godot and templates for Linux, Windows, macOS)
	docker build --build-arg GODOT_VERSION=$(GODOT_VERSION) -t $(EXPORT_IMAGE) export

export: ##@export export all three presets to build/<preset>/ (needs make export-image)
	docker run --rm --user "$$(id -u):$$(id -g)" -e HOME=/tmp \
		-v "$(CURDIR):/work" -w /work $(EXPORT_IMAGE) ./export/export.sh
# - revised 2026-10-22 (world recipe, world.json manifest)
# - revised 2026-10-22 (make world W=<id>, variables from the recipe)
# - revised 2026-10-22 (pack target, --world for the Godot targets)
# - revised 2026-10-23 (terrain source from the recipe: DGM1 or LiDAR HD)
# - revised 2026-10-23 (width and heading for fetch.py)
# - revised 2026-10-26 (public snapshot)
