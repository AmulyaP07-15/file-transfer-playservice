# Quick smoke test tool.
# Downloads one file from the gateway a few times, times each download,
# and checks the bytes with a sha256 hash so I know the file came back correct.
# I run this before the real experiments just to confirm the service works.
#
# usage
#   python fetch_bench.py <gateway_url> <file_name> <original_file_path> <num_downloads>
# example
#   python fetch_bench.py http://localhost:8082 1mb.bin ../testfiles/1mb.bin 3

import sys
import time
import hashlib
import requests
import numpy as np


# read the sha256 hash of the original file so I can compare downloads to it
def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


# download the file once and time the whole request including reading the body
def download_once(url, name, timeout=60):
    start = time.time()
    try:
        resp = requests.get(f"{url}/files?name={name}", timeout=timeout)
        elapsed_ms = (time.time() - start) * 1000
        return resp.status_code, elapsed_ms, resp.content
    except requests.exceptions.RequestException:
        # no reply at all (refused or timed out), status 0 means no response
        return 0, (time.time() - start) * 1000, b""


def main():
    url = sys.argv[1]
    name = sys.argv[2]
    original = sys.argv[3]
    n = int(sys.argv[4])

    want = sha256_of_file(original)

    times = []
    good = 0
    for i in range(n):
        status, ms, body = download_once(url, name)
        ok = status == 200 and hashlib.sha256(body).hexdigest() == want
        if ok:
            good += 1
            times.append(ms)
        print(f"download {i + 1}, status {status}, {ms:.0f}ms, correct {ok}")

    print(f"\n{good} of {n} downloads arrived complete and correct")
    if times:
        print(f"median {np.median(times):.0f}ms, p95 {np.percentile(times, 95):.0f}ms")

    # exit 0 only if every download worked, so this can gate the smoke test
    sys.exit(0 if good == n else 1)


main()
