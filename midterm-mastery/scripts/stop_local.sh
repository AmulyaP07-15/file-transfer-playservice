#!/usr/bin/env bash
# Stops the backend and gateway that start_local.sh started.
# Reads the process ids from .local_pids, sends a normal kill first so they can
# finish in flight requests, waits a second, then force kills anything left.
# As a backstop it also frees the known ports in case a stray process is stuck.
#
# usage
#   scripts/stop_local.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MM="$(dirname "$HERE")"
PIDFILE="$MM/.local_pids"

if [ -f "$PIDFILE" ]; then
	# first pass, polite kill so they can drain
	while read -r pid; do
		[ -n "$pid" ] || continue
		if kill -0 "$pid" 2>/dev/null; then
			kill "$pid" 2>/dev/null || true
		fi
	done <"$PIDFILE"
	sleep 1
	# second pass, anything still alive gets a hard kill
	while read -r pid; do
		[ -n "$pid" ] || continue
		if kill -0 "$pid" 2>/dev/null; then
			kill -9 "$pid" 2>/dev/null || true
		fi
	done <"$PIDFILE"
	rm -f "$PIDFILE"
fi

# backstop, make sure the ports are actually free before the next start
for port in 8080 8081 8082; do
	pids="$(lsof -ti tcp:"$port" 2>/dev/null; lsof -ti udp:"$port" 2>/dev/null)"
	for p in $pids; do
		kill -9 "$p" 2>/dev/null || true
	done
done

echo "Stopped"
