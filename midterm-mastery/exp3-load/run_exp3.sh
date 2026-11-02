#!/usr/bin/env bash
# Experiment 3, runs the staged Locust load test headless against the AWS
# gateway. The shape in shapes.py controls the users and the run time (about 20
# minutes), so I do not pass user or time flags here.
#
# usage
#   exp3-load/run_exp3.sh <ALB_DNS_or_URL>
# example
#   exp3-load/run_exp3.sh file-transfer-gateway-123.us-west-2.elb.amazonaws.com
#
# writes, in this folder
#   locust_results_stats.csv, locust_results_stats_history.csv, locust_results_failures.csv
#   locust_report.html, which is the one to screenshot
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MM="$(dirname "$HERE")"
LOCUST="$MM/.venv/bin/locust"

if [ "$#" -lt 1 ]; then
	echo "usage, $0 <ALB_DNS_or_URL>" >&2
	exit 2
fi

# accept either a bare dns name or a full url
HOST="$1"
case "$HOST" in
http://*|https://*) ;;
*) HOST="http://$HOST" ;;
esac

if [ ! -x "$LOCUST" ]; then
	echo "locust not found at $LOCUST, expected the midterm-mastery venv" >&2
	echo "make it with python3 -m venv $MM/.venv and then install locust and matplotlib" >&2
	exit 1
fi

cd "$HERE"
echo "Load test against $HOST, stages 10 then 50 then 200 then 0, about 20 minutes"
echo "Started $(date '+%H:%M:%S'), leave it alone, it stops itself"

# run shapes.py, it imports the user from locustfile.py and adds the load shape
"$LOCUST" \
	-f "$HERE/shapes.py" \
	--host "$HOST" \
	--headless \
	--csv "$HERE/locust_results" \
	--csv-full-history \
	--html "$HERE/locust_report.html"

echo "Done $(date '+%H:%M:%S')"
echo "data is in locust_results_stats_history.csv and the others"
echo "report is $HERE/locust_report.html"
