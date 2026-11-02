# HOW TO RUN, CS6650 Midterm Mastery experiments

Exact commands in order, with a ✅ check after each. Run everything from the
repo root (the folder that has transfer-server, transfer-frontend and this
midterm-mastery folder). The python commands use the venv in
midterm-mastery/.venv.

```bash
export MM=midterm-mastery
export PY=$MM/.venv/bin/python
```

## 0. One time setup

```bash
python3 -m venv $MM/.venv
$MM/.venv/bin/pip install requests numpy matplotlib locust
$MM/scripts/make_test_files.sh
```
✅ midterm-mastery/testfiles has hello.txt, 10kb.bin, 100kb.bin, 1mb.bin, 4mb.bin.

## 1. Local setup and smoke test

```bash
$MM/scripts/start_local.sh
$PY $MM/scripts/fetch_bench.py http://localhost:8082 1mb.bin $MM/testfiles/1mb.bin 3
$MM/scripts/stop_local.sh
```
✅ `3 of 3 downloads arrived complete and correct`

## 2. Experiment 1 (loss) and Experiment 2 (size) locally, then plots

Each runner starts and stops the servers itself. Experiment 1 restarts the
backend once per loss level, Experiment 2 runs every size against one backend at
10 percent loss.

```bash
$PY $MM/exp1-loss/run_exp1.py
$PY $MM/exp2-size/run_exp2.py
$PY $MM/scripts/plot_results.py $MM/exp1-loss/summary_local.csv "loss percent" "Exp 1 loss vs reliability (local)" $MM/exp1-loss/chart_local.png
$PY $MM/scripts/plot_results.py $MM/exp2-size/summary_local.csv "file size" "Exp 2 size vs latency (local, 10 percent loss)" $MM/exp2-size/chart_local.png
```
✅ 100 rows in exp1-loss/results_local.csv (5 levels times 20) and 80 in
exp2-size/results_local.csv (4 sizes times 20), and both chart_local.png exist.
If a sweep runs long, lower TRIES from 20 to 10 at the top of the runner.

## 3. AWS deploy, upload, smoke

Do AUTO_SETUP.md steps 0 through 4 first (make the S3 bucket by hand, put its
name in terraform/terraform.tfvars, make the tmp folder). Then

```bash
scripts/deploy.sh
$MM/aws/upload_test_files.sh
$MM/aws/smoke_test.sh
```
✅ `All smoke tests passed`

## 4. Experiment 3 (load and autoscaling), two terminals

Get the ALB address with `terraform -chdir=terraform output -raw alb_dns_name`.

- Terminal A, start first, `$MM/exp3-load/record_task_counts.sh`
- Terminal B, `$MM/exp3-load/run_exp3.sh <ALB_DNS>`

The load test runs about 20 minutes on its own (10 then 50 then 200 then 0
users). Leave record_task_counts.sh running about 5 minutes past the end to
catch the scale back down, then press ctrl c. Then

```bash
$PY $MM/exp3-load/plot_exp3.py
```
Screenshot exp3-load/locust_report.html and the CloudWatch graphs (ALB
RequestCount, TargetResponseTime, ECS CPU per service) for the test window.
✅ exp3-load/chart_exp3.png, locust_report.html and task_counts.csv exist.

## 5. AWS confirmation of Experiment 1 and 2 at 10 percent loss

```bash
scripts/deploy.sh --var backend_send_loss=10 --var backend_recv_loss=10
ALB=$(terraform -chdir=terraform output -raw alb_dns_name)
$PY $MM/exp2-size/run_exp2.py http://$ALB
$PY $MM/exp1-loss/run_exp1.py http://$ALB 10
$PY $MM/scripts/plot_results.py $MM/exp2-size/summary_aws.csv "file size" "Exp 2 size (AWS, 10 percent loss)" $MM/exp2-size/chart_aws.png
```

## 6. Tear down, do not leave AWS running

```bash
scripts/destroy.sh
aws s3 rb "s3://<your bucket>" --force
```
✅ The ECS and Load Balancer consoles are empty.

## 7 and 8. Write up and presentation
See CLAUDE.md steps 7 and 8. README.md with one section per experiment (the
question, what varied and what stayed fixed, the real numbers from the
summary csv files, the chart, and a one line finding), CHANGES.md, and the 7
slide deck exported to EXPERIMENT_PRESENTATION.pdf.
```
