#!/bin/bash
# file generated with AI assistance: Claude Code - 2026-10-22 00:10:00 UTC
#
# Runs one build step with a header, a live elapsed-time line and a
# result line, for the Makefile targets:
#
#   tools/step.sh [--plain] "<label>" <command> [args ...]
#
# On a terminal a ticker line "  ... <label>  12 s" is rewritten every
# second below the command's output; every output line of the command
# first clears the ticker line, so the two do not mix. --plain skips the
# ticker and passes the output through untouched, for commands with
# their own progress bar (curl). Without a terminal (CI, logs) only the
# header and the result line are added. The exit code is the command's.

set -u

plain=0
if [ "${1:-}" = "--plain" ]; then
	plain=1
	shift
fi
label="$1"
shift

# Python output would otherwise be block-buffered through the pipe and
# show up only when the step ends
export PYTHONUNBUFFERED=1

now() {
	# date +%s exists in GNU and BSD date
	date +%s
}

ticker() {
	local start="$1"
	while sleep 1; do
		printf '\r\033[K  ... %s  %d s' "$label" "$(($(now) - start))" >&2
	done
}

stop_ticker() {
	if [ -n "${ticker_pid:-}" ]; then
		kill "$ticker_pid" 2>/dev/null
		wait "$ticker_pid" 2>/dev/null
		printf '\r\033[K' >&2
		ticker_pid=""
	fi
}

start=$(now)
printf '\n\033[1m==> %s\033[0m\n' "$label"
ticker_pid=""
if [ "$plain" -eq 0 ] && [ -t 2 ]; then
	ticker "$start" &
	ticker_pid=$!
	trap 'stop_ticker' EXIT
	trap 'stop_ticker; exit 130' INT TERM
	"$@" 2>&1 | while IFS= read -r line; do
		printf '\r\033[K%s\n' "$line"
	done
	status=${PIPESTATUS[0]}
else
	"$@"
	status=$?
fi
stop_ticker

elapsed=$(($(now) - start))
if [ "$status" -eq 0 ]; then
	printf '\033[32m  ok\033[0m  %s  (%d s)\n' "$label" "$elapsed"
else
	printf '\033[31m  failed\033[0m  %s  (exit %d after %d s)\n' \
		"$label" "$status" "$elapsed"
fi
exit "$status"
