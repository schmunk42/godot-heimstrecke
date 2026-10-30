#!/bin/bash
# file generated with AI assistance: Claude Code - 2026-10-22 16:40:00 UTC
# Exports the presets Linux, Windows and macOS of godot/export_presets.cfg
# to build/<preset>/. It runs inside the export image: in the CI (job
# `export`) directly, on a host through `make export`.
#
#   ./export/export.sh [preset ...]            all presets without arguments
set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PRESETS=("$@")
[ "${#PRESETS[@]}" -gt 0 ] || PRESETS=(Linux Windows macOS)

# File name of a preset's main output, relative to build/<preset>/.
output_name() {
	case "$1" in
		Linux) echo "heimstrecke.x86_64" ;;
		Windows) echo "heimstrecke.exe" ;;
		macOS) echo "heimstrecke.zip" ;;
		*) echo "export.sh: unknown preset '$1'" >&2; return 1 ;;
	esac
}

export_preset() {
	local preset="$1" name out_dir
	name="$(output_name "$preset")"
	out_dir="$REPO_ROOT/build/$preset"
	rm -rf "$out_dir"
	mkdir -p "$out_dir"
	echo "export: $preset -> build/$preset/$name"
	godot --headless --path "$REPO_ROOT/godot" \
		--export-release "$preset" "$out_dir/$name"
	[ -s "$out_dir/$name" ] \
		|| { echo "export.sh: $preset produced no $name" >&2; return 1; }
}

# The import cache (.godot/) is gitignored, so it is built first. The
# project has few assets, this takes seconds.
main() {
	local preset
	godot --headless --path "$REPO_ROOT/godot" --import
	for preset in "${PRESETS[@]}"; do
		export_preset "$preset"
	done
	ls -lR "$REPO_ROOT/build"
}

main
