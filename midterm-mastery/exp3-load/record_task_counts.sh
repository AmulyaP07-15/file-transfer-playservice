#!/usr/bin/env bash
# Experiment 3, the other half. While the load test runs, this asks ECS every
# 15 seconds how many tasks the gateway and backend services have (desired and
# running) and writes them down. That is what lets me line up the load going up
# with the autoscaler adding tasks.
#
# Run this in a separate terminal, start it before run_exp3.sh, and press ctrl c
# a few minutes after the load test ends so I also catch the scale back down.
#
# usage
#   exp3-load/record_task_counts.sh
# env overrides if needed, CLUSTER default file-transfer, REGION default
# us-west-2, INTERVAL default 15 seconds.
#
# writes task_counts.csv with columns iso_time, epoch, service, desired, running
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/task_counts.csv"

CLUSTER="${CLUSTER:-file-transfer}"
REGION="${REGION:-us-west-2}"
INTERVAL="${INTERVAL:-15}"
SERVICES="gateway backend"

command -v aws >/dev/null 2>&1 || { echo "aws cli not found" >&2; exit 1; }

echo "iso_time,epoch,service,desired,running" >"$OUT"
echo "Recording ECS task counts for cluster $CLUSTER every ${INTERVAL}s into $OUT"
echo "Press ctrl c to stop, do it a few minutes after the load test ends"

while true; do
	now_iso="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
	now_epoch="$(date '+%s')"
	# one call grabs both services at once
	json="$(aws ecs describe-services \
		--cluster "$CLUSTER" --services $SERVICES \
		--region "$REGION" \
		--query 'services[].{name:serviceName,desired:desiredCount,running:runningCount}' \
		--output json 2>/dev/null || echo '[]')"

	# jq might not be installed, so I parse the json with python instead
	python3 - "$OUT" "$now_iso" "$now_epoch" "$json" <<'PY'
import csv, json, sys
out, iso, epoch, blob = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
data = json.loads(blob)
with open(out, "a", newline="") as f:
    w = csv.writer(f)
    for s in data:
        w.writerow([iso, epoch, s.get("name"), s.get("desired"), s.get("running")])
PY
	# print the latest lines so I can watch it live in the terminal
	tail -n 2 "$OUT" | sed 's/^/  /'
	sleep "$INTERVAL"
done
