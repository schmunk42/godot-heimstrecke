#!/bin/bash
# file generated with AI assistance: Claude Code - 2026-10-20 22:37:42 UTC
# Renders still images (PNG) of the viewpoints in godot/tools/viewpoints.json
# without a GPU: Godot runs in the render image (make build) under Xvfb with
# Mesa llvmpipe. Output: data/out/screenshots/<YYYY-MM-DD_hh-ii>/ with one
# PNG per view, godot.log (complete Godot output) and report.txt (timings,
# load, memory, image sizes).
#
#   make build && make render
#   RENDER_NO_SHADOWS=0 RENDER_RESOLUTION=1920x1080 ./render/render.sh
#
# Environment:
#   RENDER_IMAGE       image name (default heimstrecke-render:latest)
#   RENDER_RESOLUTION  Godot window size WxH (default 1280x720)
#   RENDER_TIMEOUT     seconds before the render is killed (default 1800)
#   RENDER_NO_SHADOWS  1 = pass --no-shadows (default), 0 = sun shadows on;
#                      shadows in llvmpipe's Compatibility renderer come
#                      out as a stipple pattern and wash out the colours
#                      (tested 2026-10-20, also with a larger shadow bias)
#   RENDER_VIEWS       viewpoint file (default res://tools/viewpoints.json)
#   RENDER_WORLD       world to render, a directory with world.json or a
#                      .world package; relative to the repository root
#                      unless absolute (default data/out/worlds/stuttgart)
#   RENDER_MEMORY      memory limit of the container (default 3g); the
#                      Bavella world with its maquis needs about 4g
#
# The host is shared: the script refuses to start below 1 GiB available
# memory, at a 1-minute load of 4 or more, or while another render
# container runs. The container is limited to 2 CPUs and RENDER_MEMORY.
#
# Requires docker and, on Linux, free. `timeout` runs inside the
# container, so the host does not need it (a fresh macOS has none).
set -u

RENDER_IMAGE="${RENDER_IMAGE:-heimstrecke-render:latest}"
RENDER_RESOLUTION="${RENDER_RESOLUTION:-1280x720}"
RENDER_TIMEOUT="${RENDER_TIMEOUT:-1800}"
RENDER_NO_SHADOWS="${RENDER_NO_SHADOWS:-1}"
RENDER_VIEWS="${RENDER_VIEWS:-res://tools/viewpoints.json}"
RENDER_WORLD="${RENDER_WORLD:-data/out/worlds/stuttgart}"
RENDER_MEMORY="${RENDER_MEMORY:-3g}"
MIN_AVAILABLE_MB=1024
MAX_LOAD=4
# Smallest Xvfb screen; it grows when the resolution is larger.
XVFB_MIN_W=1600
XVFB_MIN_H=900

# Portable on macOS: no readlink -f / realpath.
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SHOTS_DIR="$REPO_ROOT/data/out/screenshots"
CONTAINER_NAME=""
# The world's path inside the container, set by check_world.
WORLD_MOUNT=""

die() {
	echo "render.sh: $*" >&2
	exit 1
}

require_tool() {
	command -v "$1" >/dev/null 2>&1 \
		|| die "'$1' is required but not installed ($2)"
}

has_proc() {
	[ -r /proc/loadavg ]
}

load_1min() {
	cut -d ' ' -f 1 /proc/loadavg
}

available_mb() {
	free -m | awk '/^Mem:/ { print $7 }'
}

# One line with the host state, used for the start check and the report.
host_state() {
	if has_proc; then
		echo "load $(cut -d ' ' -f 1-3 /proc/loadavg)," \
			"available ${1:-$(available_mb)} MiB"
	else
		echo "load/memory unknown (no /proc on this system)"
	fi
}

# The checks need /proc and free (Linux, like the shared host); on macOS
# Docker runs in its own VM and the checks are skipped with a note.
check_host() {
	local load mem
	if ! has_proc; then
		echo "render.sh: no /proc/loadavg, host checks skipped" >&2
		return
	fi
	require_tool free "procps"
	load="$(load_1min)"
	mem="$(available_mb)"
	echo "host: $(host_state "$mem")"
	if ! awk -v l="$load" -v m="$MAX_LOAD" 'BEGIN { exit !(l < m) }'; then
		die "1-minute load $load is not below $MAX_LOAD;" \
			"the host is busy, try again later"
	fi
	if [ "$mem" -lt "$MIN_AVAILABLE_MB" ]; then
		die "only $mem MiB available, need $MIN_AVAILABLE_MB MiB"
	fi
}

check_not_running() {
	local running
	running="$(docker ps -q --filter "ancestor=$RENDER_IMAGE")" \
		|| die "docker ps failed, is the docker daemon reachable?"
	if [ -n "$running" ]; then
		die "a container of $RENDER_IMAGE is already running" \
			"($running); one render at a time"
	fi
}

check_image() {
	docker image inspect "$RENDER_IMAGE" >/dev/null 2>&1 \
		|| die "image $RENDER_IMAGE not found, run 'make build' first"
}

# Makes RENDER_WORLD absolute, checks it and sets WORLD_MOUNT: a .world
# file mounts as a single file, anything else as a world directory.
check_world() {
	case "$RENDER_WORLD" in
		/*) ;;
		*) RENDER_WORLD="$REPO_ROOT/$RENDER_WORLD" ;;
	esac
	case "$RENDER_WORLD" in
		*.world)
			[ -f "$RENDER_WORLD" ] \
				|| die "world package missing: $RENDER_WORLD not found" \
					"(see README.md)"
			WORLD_MOUNT="/work/world.world"
			;;
		*)
			[ -d "$RENDER_WORLD" ] && [ -f "$RENDER_WORLD/world.json" ] \
				|| die "world data missing: $RENDER_WORLD/world.json not" \
					"found; build it with make world or set RENDER_WORLD" \
					"to a world directory or .world file (see README.md)"
			WORLD_MOUNT="/work/world"
			;;
	esac
}

# Sets RES_W, RES_H and XVFB_SCREEN from RENDER_RESOLUTION.
parse_resolution() {
	case "$RENDER_RESOLUTION" in
		[1-9]*x[1-9]*) ;;
		*) die "RENDER_RESOLUTION must look like 1280x720," \
			"got '$RENDER_RESOLUTION'" ;;
	esac
	RES_W="${RENDER_RESOLUTION%x*}"
	RES_H="${RENDER_RESOLUTION#*x}"
	local xw="$XVFB_MIN_W" xh="$XVFB_MIN_H"
	[ "$RES_W" -gt "$xw" ] && xw="$RES_W"
	[ "$RES_H" -gt "$xh" ] && xh="$RES_H"
	XVFB_SCREEN="${xw}x${xh}x24"
}

# Pixel size from the PNG header (IHDR width and height, big endian),
# with od because file/identify are not everywhere.
png_size() {
	od -An -tu1 -j16 -N8 "$1" | awk '{
		printf "%dx%d", (($1*256+$2)*256+$3)*256+$4,
			(($5*256+$6)*256+$7)*256+$8 }'
}

# docker run's signal proxy cannot stop the container (the entrypoint is
# PID 1 and ignores SIGINT/SIGTERM), so an interrupt kills it by name.
# Invoked through the trap in main.
# shellcheck disable=SC2329
on_interrupt() {
	echo "render.sh: interrupted, stopping $CONTAINER_NAME" >&2
	docker kill "$CONTAINER_NAME" >/dev/null 2>&1
	rm -f "$status_file"
	exit 130
}

# /work/godot is mounted read-only: an exported-style run (no editor)
# writes nothing into the project, no .godot/ is created, and the shader
# and user:// caches go to HOME=/tmp inside the container (tested with a
# probe script on 2026-10-20). Runtime glb loading via GLTFDocument needs
# no import cache either. The world (directory or .world file) is
# read-only as well; only the run's own output directory is writable.
run_container() {
	local out_rel="$1" shadow_arg=""
	[ "$RENDER_NO_SHADOWS" = "1" ] && shadow_arg="--no-shadows"
	# $shadow_arg is unquoted on purpose: empty means no argument.
	# shellcheck disable=SC2086
	docker run --rm --name "$CONTAINER_NAME" --network none \
		--user "$(id -u):$(id -g)" -e HOME=/tmp \
		--memory="$RENDER_MEMORY" --memory-swap="$RENDER_MEMORY" --cpus=2 \
		-e LP_NUM_THREADS=2 -e LIBGL_ALWAYS_SOFTWARE=1 \
		-e GALLIUM_DRIVER=llvmpipe \
		-e RENDER_TIMEOUT="$RENDER_TIMEOUT" \
		-e XVFB_SCREEN="$XVFB_SCREEN" \
		-v "$REPO_ROOT/godot:/work/godot:ro" \
		-v "$RENDER_WORLD:$WORLD_MOUNT:ro" \
		-v "$REPO_ROOT/$out_rel:/work/$out_rel:rw" \
		"$RENDER_IMAGE" \
		godot --path /work/godot --display-driver x11 \
		--rendering-driver opengl3 \
		--rendering-method gl_compatibility --audio-driver Dummy \
		--resolution "$RENDER_RESOLUTION" \
		--script res://tools/render_views.gd \
		-- --out "/work/$out_rel" --views "$RENDER_VIEWS" \
		--world "$WORLD_MOUNT" $shadow_arg
}

write_report() {
	local out="$1" status="$2" seconds="$3" log="$1/godot.log" f
	{
		echo "Heimstrecke software render report"
		echo "host:        $(hostname)"
		echo "started:     $STARTED"
		echo "finished:    $(date '+%Y-%m-%d %H:%M:%S %z')"
		echo "image:       $RENDER_IMAGE"
		echo "resolution:  $RENDER_RESOLUTION (Xvfb $XVFB_SCREEN)"
		echo "world:       $RENDER_WORLD"
		echo "no shadows:  $RENDER_NO_SHADOWS"
		echo "before:      $STATE_BEFORE"
		echo "after:       $(host_state)"
		echo "renderer:    $(grep -m 1 '^OpenGL API' "$log")"
		echo "exit code:   $status"
		echo "result:      $(grep -E '^RENDER (OK|FAILED)' "$log" \
			| tail -n 1)"
		echo "wall time:   ${seconds} s total"
		echo "peak memory: $(sed -n \
			's/^RENDER_CONTAINER memory_peak_bytes=//p' "$log" \
			| awk '$1 ~ /^[0-9]+$/ {
				printf "%d MiB (%s)", $1 / 1048576, $2; next }
				{ print }')"
		echo
		echo "views (wall time per view from the Godot script):"
		grep '^RENDER name=' "$log" | sed 's/^RENDER /  /'
		echo
		echo "files:"
		for f in "$out"/*.png; do
			[ -f "$f" ] || continue
			echo "  $(png_size "$f")  $(ls -l "$f")"
		done
	} > "$out/report.txt"
}

main() {
	local ts out_rel out status=0 start end status_file
	require_tool docker "https://docs.docker.com/get-docker/"
	check_host
	check_world
	check_image
	check_not_running
	parse_resolution

	ts="$(date '+%Y-%m-%d_%H-%M')"
	out_rel="data/out/screenshots/$ts"
	out="$REPO_ROOT/$out_rel"
	mkdir -p "$SHOTS_DIR"
	# Plain mkdir fails when the directory exists: no silent overwrite of
	# a run started in the same minute.
	mkdir "$out" || die "$out exists already, wait a minute"
	CONTAINER_NAME="heimstrecke-render-$ts"
	STARTED="$(date '+%Y-%m-%d %H:%M:%S %z')"
	STATE_BEFORE="$(host_state)"

	echo "render: $out_rel ($RENDER_RESOLUTION, timeout" \
		"$RENDER_TIMEOUT s)"
	status_file="$(mktemp)"
	trap on_interrupt INT TERM
	start="$(date +%s)"
	# bash runs a trap only after the foreground job ends, which for a
	# hung render is the timeout; `wait` on a background job returns at
	# once on a signal. The status file carries docker's exit code out of
	# the pipeline (no PIPESTATUS for background jobs, no `wait` on a
	# process substitution in the bash 3.2 of macOS).
	{ run_container "$out_rel"; echo "$?" > "$status_file"; } 2>&1 \
		| tee "$out/godot.log" &
	wait "$!"
	end="$(date +%s)"
	trap - INT TERM
	status="$(cat "$status_file")"
	status="${status:-1}"
	rm -f "$status_file"

	write_report "$out" "$status" "$((end - start))"
	echo "report: $out_rel/report.txt (exit code $status)"
	exit "$status"
}

main "$@"
# - revised 2026-10-20 (shadows off by default after the integration run)
# - revised 2026-10-22 (world.json manifest)
# - revised 2026-10-22 (world under data/out/worlds/stuttgart)
# - revised 2026-10-22 (RENDER_WORLD: world directory or .world file)
# - revised 2026-10-23 (RENDER_MEMORY)
