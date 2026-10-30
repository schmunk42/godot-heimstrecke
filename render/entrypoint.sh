#!/bin/bash
# file generated with AI assistance: Claude Code - 2026-10-20 22:28:12 UTC
# Container entrypoint of the render image: runs the given command under
# nice, a timeout and a virtual X server (Xvfb, Mesa llvmpipe), then prints
# the container's peak memory as one line for render.sh:
#   RENDER_CONTAINER memory_peak_bytes=<n> source=<cgroup|time>
#
#   docker run ... heimstrecke-render godot --path /work/godot ...
#   docker run ... heimstrecke-render glxinfo -B
#
# Environment: RENDER_TIMEOUT (seconds, default 1800), XVFB_SCREEN
# (default 1600x900x24, must be at least the Godot window size).
set -u

RENDER_TIMEOUT="${RENDER_TIMEOUT:-1800}"
XVFB_SCREEN="${XVFB_SCREEN:-1600x900x24}"
TIME_LOG="$(mktemp /tmp/render-time.XXXXXX)"

# The cgroup v2 file is the container-wide peak (Xvfb + Godot); the
# /usr/bin/time value is the peak RSS of the command alone and only the
# fallback for kernels without memory.peak (before 5.19).
print_memory_peak() {
	local peak
	if [ -r /sys/fs/cgroup/memory.peak ]; then
		peak="$(cat /sys/fs/cgroup/memory.peak)"
		echo "RENDER_CONTAINER memory_peak_bytes=${peak} source=cgroup"
		return
	fi
	peak="$(sed -n 's/.*Maximum resident set size (kbytes): //p' \
		"$TIME_LOG")"
	if [ -n "$peak" ]; then
		echo "RENDER_CONTAINER memory_peak_bytes=$((peak * 1024))" \
			"source=time"
	else
		echo "RENDER_CONTAINER memory_peak_bytes=unknown source=none"
	fi
}

if [ "$#" -eq 0 ]; then
	echo "usage: render-entrypoint <command> [args...]" >&2
	exit 2
fi

status=0
# -a picks a free display number; -nolisten tcp keeps Xvfb off the network.
# The kill-after makes sure a hung Godot that ignores SIGTERM goes as well.
nice -n 19 timeout -k 30 "$RENDER_TIMEOUT" \
	xvfb-run -a -s "-screen 0 ${XVFB_SCREEN} -nolisten tcp" \
	/usr/bin/time -v -o "$TIME_LOG" "$@" || status=$?
if [ "$status" -eq 124 ]; then
	echo "RENDER_CONTAINER timeout after ${RENDER_TIMEOUT} s" >&2
fi
print_memory_peak
rm -f "$TIME_LOG"
exit "$status"
