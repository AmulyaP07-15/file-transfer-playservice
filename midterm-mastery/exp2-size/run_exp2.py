# Experiment 2, file size versus latency and reliability, under a fixed 10
# percent loss. I change the file size, keep the loss at 10 percent, default
# retries, one request at a time, and measure the success rate and latency for
# each size.
#
# My guess is that bigger files fail more than their size alone would suggest.
# A file is sent in 64 byte chunks, so a bigger file is many more chunks, and
# more chunks means more chances that one of them gets dropped on every retry.
# I report what the data actually shows, not what I guessed.
#
# Local run, the default. Start the backend once at 10 percent loss, then
# download each size many times. Writes results_local.csv and summary_local.csv.
#   python run_exp2.py
#
# AWS run. Point at an ALB that was deployed with 10 percent loss already.
#   python run_exp2.py http://<ALB_DNS>

import os
import sys
import time
import hashlib
import subprocess
import csv
import requests
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MM = os.path.dirname(HERE)
SCRIPTS = os.path.join(MM, "scripts")
TESTFILES = os.path.join(MM, "testfiles")

GATEWAY = "http://localhost:8082"
LOSS = 10
TRIES = 20
# the sizes I test, as (label for the chart, actual file name)
SIZES = [
    ("10KB", "10kb.bin"),
    ("100KB", "100kb.bin"),
    ("1MB", "1mb.bin"),
    ("4MB", "4mb.bin"),
]


def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def download_once(url, name, timeout=60):
    start = time.time()
    try:
        resp = requests.get(f"{url}/files?name={name}", timeout=timeout)
        return resp.status_code, (time.time() - start) * 1000, resp.content
    except requests.exceptions.RequestException:
        return 0, (time.time() - start) * 1000, b""


def run_tries(url, name, want, tries):
    rows = []
    for _ in range(tries):
        status, ms, body = download_once(url, name)
        ok = status == 200 and hashlib.sha256(body).hexdigest() == want
        rows.append((status, ms, ok))
    return rows


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
    aws = len(sys.argv) >= 2
    url = sys.argv[1] if aws else GATEWAY

    # locally I start the backend myself at 10 percent loss, on AWS it is already up
    if not aws:
        print(f"Local run, backend at {LOSS} percent loss, {TRIES} downloads per size")
        subprocess.run([os.path.join(SCRIPTS, "start_local.sh"), str(LOSS), str(LOSS)], check=True)
        time.sleep(0.5)
    else:
        print(f"AWS run, {TRIES} downloads per size from {url}")

    results = []  # list of (size_label, rows)
    try:
        for label, name in SIZES:
            want = sha256_of_file(os.path.join(TESTFILES, name))
            print(f"\n{label} ({name})")
            rows = run_tries(url, name, want, TRIES)
            s = summarize(rows)
            print(f"  {s['successes']} of {s['trials']} ok, {s['success_rate'] * 100:.0f} percent")
            results.append((label, rows))
    finally:
        # always stop the local servers, even if something failed partway through
        if not aws:
            subprocess.run([os.path.join(SCRIPTS, "stop_local.sh")], check=False)

    tag = "aws" if aws else "local"
    raw_path = os.path.join(HERE, f"results_{tag}.csv")
    summary_path = os.path.join(HERE, f"summary_{tag}.csv")

    with open(raw_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["size", "trial", "status", "time_ms", "correct"])
        for label, rows in results:
            for i, (status, ms, ok) in enumerate(rows, start=1):
                w.writerow([label, i, status, round(ms, 1), int(ok)])

    with open(summary_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["size", "trials", "successes", "success_rate",
                    "median_ms", "p95_ms", "n_200", "n_404", "n_503", "n_504", "n_noresp"])
        for label, rows in results:
            s = summarize(rows)
            w.writerow([label, s["trials"], s["successes"], round(s["success_rate"], 3),
                        round(s["median_ms"], 1), round(s["p95_ms"], 1),
                        s["n_200"], s["n_404"], s["n_503"], s["n_504"], s["n_noresp"]])

    print(f"\nwrote {raw_path}")
    print(f"wrote {summary_path}")


main()
