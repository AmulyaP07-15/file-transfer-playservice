# Experiment 1, packet loss versus reliability.
# I change the simulated packet loss on the backend (send loss equals receive
# loss) over a few levels, keep everything else the same (always the 1mb file,
# default retries, one request at a time), and watch how the success rate and
# the latency change as loss goes up.
#
# Local run, the default. For each loss level I restart the backend at that
# loss, then download the 1mb file many times and record what happened. Writes
# results_local.csv and summary_local.csv, and stops the servers at the end.
#   python run_exp1.py
#
# AWS run. The deploy already set the loss, so here I just point at the ALB and
# label the row with that loss.
#   python run_exp1.py http://<ALB_DNS> 10

import os
import sys
import time
import hashlib
import subprocess
import csv
import requests
import numpy as np

# where things live, worked out from this file so it runs from anywhere
HERE = os.path.dirname(os.path.abspath(__file__))
MM = os.path.dirname(HERE)
SCRIPTS = os.path.join(MM, "scripts")
TESTFILES = os.path.join(MM, "testfiles")

# config for the sweep, change these if the run takes too long
GATEWAY = "http://localhost:8082"
TEST_FILE = "1mb.bin"
LOSS_LEVELS = [0, 1, 2, 3, 5, 10]
TRIES = 20


# sha256 of the original file, so I can tell if a download came back correct
def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


# one download, timed, with the status code and the bytes that came back
def download_once(url, name, timeout=60):
    start = time.time()
    try:
        resp = requests.get(f"{url}/files?name={name}", timeout=timeout)
        return resp.status_code, (time.time() - start) * 1000, resp.content
    except requests.exceptions.RequestException:
        # status 0 means the gateway never answered at all
        return 0, (time.time() - start) * 1000, b""


# download TRIES times and collect the status, time and whether it was correct
def run_tries(url, name, want, tries):
    rows = []
    for _ in range(tries):
        status, ms, body = download_once(url, name)
        ok = status == 200 and hashlib.sha256(body).hexdigest() == want
        rows.append((status, ms, ok))
    return rows


# restart the local backend at a given loss (send and receive both set to loss)
def start_backend(loss):
    subprocess.run([os.path.join(SCRIPTS, "start_local.sh"), str(loss), str(loss)], check=True)


def stop_backend():
    subprocess.run([os.path.join(SCRIPTS, "stop_local.sh")], check=False)


# turn a batch of rows into the numbers I care about for one level
def summarize(rows):
    good_times = [ms for (status, ms, ok) in rows if ok]
    codes = [status for (status, ms, ok) in rows]
    return {
        "trials": len(rows),
        "successes": len(good_times),
        "success_rate": len(good_times) / len(rows),
        "median_ms": np.median(good_times) if good_times else 0,
        "p95_ms": np.percentile(good_times, 95) if good_times else 0,
        "n_200": codes.count(200),
        "n_404": codes.count(404),
        "n_503": codes.count(503),
        "n_504": codes.count(504),
        "n_noresp": codes.count(0),
    }


def main():
    want = sha256_of_file(os.path.join(TESTFILES, TEST_FILE))
    results = []  # list of (loss, rows)

    if len(sys.argv) >= 2:
        # AWS mode, one loss level against the ALB
        aws_url = sys.argv[1]
        loss = int(sys.argv[2]) if len(sys.argv) >= 3 else 0
        print(f"AWS run, loss {loss} percent, {TRIES} downloads from {aws_url}")
        rows = run_tries(aws_url, TEST_FILE, want, TRIES)
        results.append((loss, rows))
        raw_path = os.path.join(HERE, "results_aws.csv")
        summary_path = os.path.join(HERE, "summary_aws.csv")
    else:
        # local mode, walk through every loss level and restart the backend each time
        print(f"Local run, loss levels {LOSS_LEVELS}, {TRIES} downloads each")
        for loss in LOSS_LEVELS:
            print(f"\nloss {loss} percent, restarting backend")
            start_backend(loss)
            time.sleep(0.5)
            rows = run_tries(GATEWAY, TEST_FILE, want, TRIES)
            s = summarize(rows)
            print(f"  {s['successes']} of {s['trials']} ok, {s['success_rate'] * 100:.0f} percent")
            results.append((loss, rows))
        stop_backend()
        raw_path = os.path.join(HERE, "results_local.csv")
        summary_path = os.path.join(HERE, "summary_local.csv")

    # raw csv, one row per download, in case I want to recheck later
    with open(raw_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["loss_pct", "trial", "status", "time_ms", "correct"])
        for loss, rows in results:
            for i, (status, ms, ok) in enumerate(rows, start=1):
                w.writerow([loss, i, status, round(ms, 1), int(ok)])

    # summary csv, one row per loss level, this is what the chart and writeup use
    with open(summary_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["loss_pct", "trials", "successes", "success_rate",
                    "median_ms", "p95_ms", "n_200", "n_404", "n_503", "n_504", "n_noresp"])
        for loss, rows in results:
            s = summarize(rows)
            w.writerow([loss, s["trials"], s["successes"], round(s["success_rate"], 3),
                        round(s["median_ms"], 1), round(s["p95_ms"], 1),
                        s["n_200"], s["n_404"], s["n_503"], s["n_504"], s["n_noresp"]])

    print(f"\nwrote {raw_path}")
    print(f"wrote {summary_path}")


main()
