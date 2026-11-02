#!/usr/bin/env bash
# Builds and starts the backend and gateway on my laptop, serving files out of
# midterm-mastery/testfiles. Saves both process ids to .local_pids and waits
# until both health checks answer before it returns.
#
# usage
#   scripts/start_local.sh [SEND_LOSS RECV_LOSS]
# the two optional numbers are loss percents from 0 to 100, default is 0 and 0.
# Experiment 1 uses this to restart the backend at each loss level.
#
# ports are backend UDP 8080, backend health 8081, gateway 8082.
# note, the repo readme curl example says 8080 but our gateway is on 8082.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MM="$(dirname "$HERE")"
ROOT="$(dirname "$MM")"
FILES="$MM/testfiles"
PIDFILE="$MM/.local_pids"
LOGDIR="$MM/logs"

SEND_LOSS="${1:-0}"
RECV_LOSS="${2:-0}"

GW_PORT=8082
BE_PORT=8080
BE_HEALTH=8081

mkdir -p "$LOGDIR" "$ROOT/bin"

# stop early if I forgot to make the test files
if [ ! -d "$FILES" ] || [ -z "$(ls -A "$FILES" 2>/dev/null)" ]; then
	echo "No test files in $FILES, run scripts/make_test_files.sh first" >&2
	exit 1
fi

# if something is already running from last time, stop it so the ports are free
if [ -f "$PIDFILE" ]; then
	echo "Found an existing $PIDFILE, stopping it first"
	"$HERE/stop_local.sh" || true
fi

echo "Building backend and gateway"
( cd "$ROOT" && go build -o bin/backend ./transfer-server )
( cd "$ROOT" && go build -o bin/gateway ./transfer-frontend )

echo "Starting backend, send loss ${SEND_LOSS} percent, receive loss ${RECV_LOSS} percent"
"$ROOT/bin/backend" udp \
	-dir="$FILES" -port="$BE_PORT" -health-port="$BE_HEALTH" \
	-send-loss="$SEND_LOSS" -recv-loss="$RECV_LOSS" \
	>"$LOGDIR/backend.log" 2>&1 &
BE_PID=$!

echo "Starting gateway on port $GW_PORT"
"$ROOT/bin/gateway" \
	-transport=udp -upstream="localhost:$BE_PORT" -listen=":$GW_PORT" \
	>"$LOGDIR/gateway.log" 2>&1 &
GW_PID=$!

printf "%s\n%s\n" "$BE_PID" "$GW_PID" >"$PIDFILE"

# poll both health endpoints until they answer, give it about ten seconds.
# also stop early if either process died, so I am not waiting on a dead server.
ok=1
for _ in $(seq 1 50); do
	if curl -fs -o /dev/null "http://localhost:$BE_HEALTH/health" 2>/dev/null \
		&& curl -fs -o /dev/null "http://localhost:$GW_PORT/health" 2>/dev/null; then
		ok=0
		break
	fi
	if ! kill -0 "$BE_PID" 2>/dev/null; then
		echo "Backend died, see $LOGDIR/backend.log" >&2
		cat "$LOGDIR/backend.log" >&2
		exit 1
	fi
	if ! kill -0 "$GW_PID" 2>/dev/null; then
		echo "Gateway died, see $LOGDIR/gateway.log" >&2
		cat "$LOGDIR/gateway.log" >&2
		exit 1
	fi
	sleep 0.2
done

if [ "$ok" != 0 ]; then
	echo "Services did not become healthy in time" >&2
	echo "backend log" >&2
	cat "$LOGDIR/backend.log" >&2
	echo "gateway log" >&2
	cat "$LOGDIR/gateway.log" >&2
	"$HERE/stop_local.sh" || true
	exit 1
fi

echo "Up, backend pid $BE_PID gateway pid $GW_PID"
echo "Gateway is at http://localhost:$GW_PORT/files?name=hello.txt"
