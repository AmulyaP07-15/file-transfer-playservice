# CS6650 Midterm Mastery Part 2, empirical evaluation of the file transfer service

I forked the file transfer play service, deployed it on AWS, and ran three
experiments to see how it behaves. This folder has all of the test code, the
raw data, the charts, and a short presentation. Every number below comes from a
CSV in this folder, nothing is estimated.

To reproduce any of this, see HOW_TO_RUN.md.

## The service in one paragraph

The service hands a client a file over HTTP. The gateway (transfer-frontend)
takes a GET /files?name=FILE request and fetches the file from the backend
(transfer-server) over UDP, using a custom protocol. Files are sent in 64 byte
chunks, up to 65,536 chunks, so about 4 MB is the largest file. The gateway can
answer 200 (here is the file), 404 (not found), 503 (busy, no free transfer slot
within the queue wait), or 504 (the backend never answered). On AWS the gateway
runs 2 to 4 Fargate tasks behind an Application Load Balancer and scales on
request count per target. The backend runs 2 to 4 Fargate tasks behind a Network
Load Balancer and scales on CPU with a 60 percent target.

## Experiment 1, packet loss versus reliability (local)

Question. How much simulated packet loss can the service tolerate before a
download stops working.

Setup. I varied the backend loss (send loss equal to receive loss) over
0, 1, 2, 3, 5 and 10 percent. I kept everything else fixed, always the 1 MB
file, default retries, one request at a time, 20 downloads per level. Measured
success rate, latency, and the status codes. Data in exp1-loss/summary_local.csv,
chart in exp1-loss/chart_local.png.

| loss | success | median latency | p95 | codes |
|------|---------|----------------|-----|-------|
| 0 percent | 100 percent (20/20) | 2150 ms | 2183 ms | all 200 |
| 1 percent | 95 percent (19/20) | 12260 ms | 12312 ms | 19 of 200, 1 of 504 |
| 2 percent | 0 percent (0/20) | n/a | n/a | all 504 |
| 3 percent | 0 percent | n/a | n/a | all 504 |
| 5 percent | 0 percent | n/a | n/a | all 504 |
| 10 percent | 0 percent | n/a | n/a | all 504 |

Finding. The service falls off a cliff between 1 and 2 percent loss for a 1 MB
file. It still mostly works at 1 percent, but the median latency jumps almost 6
times, from 2.1 to 12.3 seconds, because the client spends its retry rounds
re-requesting dropped chunks. At 2 percent and above, a 1 MB file never
completes within the budget and every request returns 504.

## Experiment 2, file size versus reliability (local and AWS)

Question. Do bigger files fail more than their size alone would suggest.

Setup. I varied the file size over 10 KB, 100 KB, 1 MB and 4 MB, 20 downloads
each, one at a time. Locally I held the loss at 10 percent. On AWS I used the
deploy default of 0 percent configured loss, because the real network already
adds its own loss. Data in exp2-size/summary_local.csv and
exp2-size/summary_aws.csv, charts in exp2-size/chart_local.png and
exp2-size/chart_aws.png.

Local, 10 percent loss

| size | success | median | codes |
|------|---------|--------|-------|
| 10 KB | 100 percent (20/20) | 8015 ms | all 200 |
| 100 KB | 70 percent (14/20) | 10081 ms | 14 of 200, 6 of 503 |
| 1 MB | 0 percent | n/a | all 504 |
| 4 MB | 0 percent | n/a | all 504 |

AWS, 0 percent configured loss

| size | success | median | codes |
|------|---------|--------|-------|
| 10 KB | 100 percent (20/20) | 2236 ms | all 200 |
| 100 KB | 35 percent (7/20) | 2947 ms | 7 of 200, 13 of 503 |
| 1 MB | 0 percent | n/a | all 504 |
| 4 MB | 0 percent | n/a | all 504 |

Finding. The hypothesis holds, bigger files fail more than proportionally. A
file is many more chunks as it grows (10 KB is 160 chunks, 1 MB is 16,384), so
there are many more chances for a chunk to be lost on every retry round, and the
transfer stops converging. The AWS numbers make a sharper point. At 0 percent
configured loss, AWS only served 35 percent of 100 KB downloads, which is worse
than the local service at 10 percent injected loss. The real UDP path through the
Network Load Balancer is lossier than 10 percent simulated loss on one machine.

## Experiment 3, load and autoscaling (AWS)

Question. As load rises, does the service scale out, and which part becomes the
bottleneck.

Setup. I drove a staged Locust load of 10, then 50, then 200, then 0 users, 5
minutes per stage, every user downloading the 10 KB file (I used 10 KB because
it is the only size that is reliable at a single request on AWS, so load stays
the real variable). At the same time I polled ECS every 15 seconds for the
running task count of each service. Load and latency come from the Locust report
(exp3-load/locust_report.html, screenshots in the same folder). The autoscaling
is in exp3-load/chart_exp3_autoscaling.png, and the AWS side metrics are in
exp3-load/chart_cloudwatch.png. Raw data in exp3-load/locust_results_*.csv and
exp3-load/task_counts.csv.

Results. Over the run there were 14,364 requests with 9,035 failures, about 63
percent, and every failure was a 503. At the 200 user peak the throughput was
around 37 requests per second, the median response time was 5.1 seconds and p95
was 7.1 seconds. The gateway scaled from 2 to 4 tasks. The backend stayed at 2
the whole time. CloudWatch shows why, the ECS CPU for both services never left
about 3 percent, nowhere near the 60 percent scale out target.

Finding. The gateway scales correctly because its signal is request count, and
it went from 2 to 4 tasks as the load climbed. The backend never scales because
its signal is CPU, and the UDP backend is bound by its own protocol and network,
not by CPU, so CPU sits near 3 percent and the scale out alarm never fires. Even
at 4 gateway tasks, the gateway can only run 4 concurrent transfers each (max
inflight is 4), so under 200 users most requests find no free slot and are shed
with 503. The real bottleneck is the transfer concurrency, and the CPU based
rule on the backend is the wrong signal to relieve it.

## What this reveals about the service

The service works well for small files under light load and falls apart in three
predictable ways. It cannot tolerate loss on large files, because the chunked
UDP protocol with a fixed retry budget stops converging once more than a few
chunks go missing. It does not scale where it needs to, because the backend
scales on CPU but is never CPU bound. And it sheds load early under concurrency,
because the gateway allows only four transfers in flight per task. The AWS
environment itself behaves like a lossy network even with no configured loss.

## Limitations and what I would test next

These runs used 20 downloads per level for Experiments 1 and 2, enough to see
the cliffs but not to put error bars on the edges. I would add finer loss levels
around 1 to 2 percent and repeat each level more times to pin down the exact
transition. I would raise the gateway max inflight and re-run Experiment 3 to see
whether the 503 shedding moves or whether the backend then becomes the limit. I
would also change the backend scaling signal from CPU to something that tracks
its real work, such as active transfers or NLB flow count, and check whether the
backend finally scales.

## Files in this folder

See HOW_TO_RUN.md for the exact commands. CHANGES.md records what, if anything,
changed in the service. The scripts folder has the shared helpers, exp1-loss,
exp2-size and exp3-load have the runners, charts and data, and aws has the
upload and smoke test helpers. A copy of the results also lives in
midterm mastery/results-local-backup outside the fork.
