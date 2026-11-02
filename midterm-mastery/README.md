# CS6650 Midterm Mastery Part 2, empirical evaluation of the file transfer service

- I forked the file transfer play service, deployed it on AWS, and ran three experiments to see how it behaves.
- This folder holds all the test code, the raw data, the charts, and the presentation.
- Every number below comes from a CSV in this folder. Nothing is estimated.
- To reproduce any of it, see HOW_TO_RUN.md.

## The service in short

- A client asks for a file over HTTP from the **gateway** (transfer-frontend).
- The gateway fetches the file from the **backend** (transfer-server) over UDP, in 64 byte chunks, up to about 4 MB.
- Gateway replies: **200** ok, **404** not found, **503** busy (no free transfer slot on the gateway), **504** (the backend never finished the transfer).
- On AWS the gateway runs 2 to 4 Fargate tasks behind an ALB and scales on **request count**.
- The backend runs 2 to 4 Fargate tasks behind an NLB and scales on **CPU** (60 percent target).

## Which experiment ran where

- **Experiment 1 (packet loss)** ran **locally**. On AWS a 1 MB file fails even at 0 percent loss, so an AWS loss sweep would be a flat, meaningless chart. Local gives the clean tolerance curve.
- **Experiment 2 (file size)** ran in **both** places, so I could compare simulated loss against the real network.
- **Experiment 3 (load and autoscaling)** ran on **AWS only**. Autoscaling does not exist locally, there is nothing to scale.

## Experiment 1, packet loss vs reliability (local)

- **Question** how much simulated loss can the service tolerate before a download stops working.
- **Vary** backend loss 0, 1, 2, 3, 5, 10 percent.
- **Fixed** 1 MB file, default retries, one request at a time, 20 downloads per level.
- **Results** (exp1-loss/summary_local.csv, chart in exp1-loss/chart_local.png)
  - 0 percent loss, 100 percent success, median 2.15 s
  - 1 percent loss, 95 percent success, median 12.3 s
  - 2, 3, 5, 10 percent loss, 0 percent success, all 504
- **Finding** the 1 MB file falls off a cliff between 1 and 2 percent loss. At 1 percent it still works but latency jumps almost 6 times, because the client keeps asking for dropped chunks. At 2 percent and up it never completes.

## Experiment 2, file size vs reliability (local and AWS)

- **Question** do bigger files fail more than their size alone would suggest.
- **Hypothesis** yes, a bigger file is many more chunks, so there are more chances one is lost on every retry.
- **Vary** file size 10 KB, 100 KB, 1 MB, 4 MB.
- **Fixed** local at 10 percent loss, AWS at 0 percent configured loss, 20 downloads per size.
- **Results local, 10 percent loss** (exp2-size/summary_local.csv, chart_local.png)
  - 10 KB, 100 percent. 100 KB, 70 percent. 1 MB, 0 percent. 4 MB, 0 percent.
- **Results AWS, 0 percent configured loss** (exp2-size/summary_aws.csv, chart_aws.png)
  - 10 KB, 100 percent. 100 KB, 35 percent. 1 MB, 0 percent. 4 MB, 0 percent.
- **Finding** the hypothesis holds. And AWS at 0 percent configured loss is worse than local at 10 percent. 0 percent is the fair AWS baseline, because the real UDP path through the NLB already adds its own loss, and it still loses to 10 percent injected locally.

## Experiment 3, load and autoscaling (AWS)

- **Question** as load rises, does the service scale out, and which part is the bottleneck.
- **Vary** Locust load 10, then 50, then 200, then 0 users, 5 minutes per stage.
- **Fixed** 10 KB file, 0 percent loss, deploy defaults. (10 KB because it is the only size reliable at a single request on AWS, so load stays the real variable.)
- **Results** (exp3-load/locust_report.html and screenshots, chart_exp3_autoscaling.png, chart_cloudwatch.png, task_counts.csv)
  - 14,364 requests, about 63 percent failed, every failure a 503.
  - At 200 users, about 37 requests per second, median 5.1 s, p95 7.1 s.
  - Gateway scaled 2 to 4 tasks. Backend stayed at 2.
  - CloudWatch shows ECS CPU near 3 percent the whole time, far below the 60 percent target.
- **Finding** the gateway scales on request count and grows 2 to 4. The backend scales on CPU, but a UDP server is not CPU bound, so CPU stays near 3 percent and it never scales. Even at 4 gateway tasks, max inflight 4 means most of 200 users are shed with 503. CPU is the wrong scaling signal for this backend.

## What this reveals

- It cannot tolerate loss on large files. The chunked UDP protocol with a fixed retry budget stops converging once more than a few chunks go missing.
- It scales on the wrong signal. The backend scales on CPU but is never CPU bound.
- It sheds load early. The gateway allows only four transfers in flight per task, so it returns 503 well before it is truly saturated.
- The AWS network behaves like a lossy link even with no configured loss.

## Limitations and what I would test next

- 20 downloads per level shows the cliffs but does not put error bars on the edges.
- Experiment 3 effectively ended near 15 minutes, and I did not wait for the slow scale in.
- Next, finer loss levels around 1 to 2 percent with more repeats.
- Next, raise the gateway max inflight and run the load test again.
- Next, change the backend scaling signal from CPU to active transfers or NLB flow count, and see whether it finally scales.

## Findings and screenshots

- Experiment 1 and 2 charts
  - exp1-loss/chart_local.png, success rate and latency vs loss
  - exp2-size/chart_local.png and chart_aws.png, success rate and latency vs file size
- Experiment 3, load and autoscaling
  - exp3-load/locust_report.html, the full Locust report (open it in a browser)
  - exp3-load/locust_report_stats.jpg and locust_report_charts.jpg, screenshots of that Locust report
  - exp3-load/chart_exp3_autoscaling.png, ECS running tasks vs the offered load over time
  - exp3-load/chart_cloudwatch.png, the AWS side view, ALB request count and 5xx, response time, and ECS CPU
  - exp3-load/task_counts.csv and locust_results_*.csv, the raw time series behind those charts

## Monitoring note

- For the AWS side metrics I used CloudWatch (ECS CPU per service, ALB request count, ALB response time), pulled with the AWS CLI and charted by exp3-load/plot_cloudwatch.py, rather than the Prometheus and Grafana stack from HW6.
- CloudWatch is the native source for ECS and ALB metrics, so it is the authoritative place to read the autoscaling signals, and ECS CPU is exactly what the backend autoscaler itself watches.

## Files in this folder

- **HOW_TO_RUN.md** exact commands in order to reproduce everything.
- **CHANGES.md** what, if anything, changed in the service (no service code was changed).
- **EXPERIMENT_PRESENTATION.pdf** the experiment presentation.
- **scripts/** shared helpers, the local start and stop, the smoke test, and the chart maker.
- **exp1-loss/ exp2-size/ exp3-load/** the runners, charts, and data for each experiment.
- **aws/** helpers to upload the test files to S3 and smoke test the deployed gateway.
- The service itself lives in a separate fork and is not copied here.
