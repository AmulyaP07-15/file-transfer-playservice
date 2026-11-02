# Pulls the AWS side of Experiment 3 from CloudWatch and charts it, so the
# autoscaling evidence does not depend on catching live console screenshots.
# Three panels on a shared time axis.
#   1. ALB requests per minute, with target 5xx responses per minute on top
#   2. ALB target response time
#   3. ECS CPU for the gateway and backend services, with the 60 percent scale
#      out target drawn in (backend scales on CPU)
#
# Run it a few minutes AFTER the load test ends so every datapoint has landed.
#
# usage, times are UTC and optional, default is the last 45 minutes
#   python plot_cloudwatch.py [start_utc] [end_utc] [output_png]
# example
#   python plot_cloudwatch.py 2026-11-01T20:45:00Z 2026-11-01T21:15:00Z chart_cloudwatch.png

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REGION = "us-west-2"
CLUSTER = "file-transfer"
ALB_NAME = "file-transfer-gateway"


# run an aws cli command and give back the parsed json
def aws_json(args):
    out = subprocess.run(["aws"] + args + ["--region", REGION, "--output", "json"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        print("aws call failed,", " ".join(args))
        print(out.stderr.strip())
        sys.exit(1)
    return json.loads(out.stdout) if out.stdout.strip() else {}


# the CloudWatch LoadBalancer dimension is the part of the arn after loadbalancer/
def alb_dimension():
    data = aws_json(["elbv2", "describe-load-balancers", "--names", ALB_NAME])
    arn = data["LoadBalancers"][0]["LoadBalancerArn"]
    return arn.split("loadbalancer/")[1]


# ask CloudWatch for one metric over the window, returns sorted (time, value) pairs
def get_metric(namespace, metric, dims, stat, start, end, period=60):
    dim_args = []
    for name, value in dims:
        dim_args += ["Name=" + name + ",Value=" + value]
    data = aws_json([
        "cloudwatch", "get-metric-statistics",
        "--namespace", namespace,
        "--metric-name", metric,
        "--dimensions", *dim_args,
        "--start-time", start,
        "--end-time", end,
        "--period", str(period),
        "--statistics", stat,
    ])
    points = [(p["Timestamp"], p[stat]) for p in data.get("Datapoints", [])]
    points.sort()
    return points


# turn a list of (iso_time, value) into minutes since the window start and values
def to_series(points, t0):
    mins = []
    vals = []
    for ts, v in points:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        mins.append((t - t0).total_seconds() / 60.0)
        vals.append(v)
    return mins, vals


def main():
    now = datetime.now(timezone.utc)
    start = sys.argv[1] if len(sys.argv) >= 2 else (now - timedelta(minutes=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = sys.argv[2] if len(sys.argv) >= 3 else now.strftime("%Y-%m-%dT%H:%M:%SZ")
    out_png = sys.argv[3] if len(sys.argv) >= 4 else os.path.join(HERE, "chart_cloudwatch.png")

    t0 = datetime.fromisoformat(start.replace("Z", "+00:00"))
    alb_dim = alb_dimension()
    print(f"window {start} to {end}, alb {alb_dim}")

    # ALB metrics, all keyed on the LoadBalancer dimension
    reqs = get_metric("AWS/ApplicationELB", "RequestCount", [("LoadBalancer", alb_dim)], "Sum", start, end)
    fivexx = get_metric("AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", [("LoadBalancer", alb_dim)], "Sum", start, end)
    rt = get_metric("AWS/ApplicationELB", "TargetResponseTime", [("LoadBalancer", alb_dim)], "Average", start, end)

    # ECS CPU per service
    cpu_gw = get_metric("AWS/ECS", "CPUUtilization",
                        [("ClusterName", CLUSTER), ("ServiceName", "gateway")], "Average", start, end)
    cpu_be = get_metric("AWS/ECS", "CPUUtilization",
                        [("ClusterName", CLUSTER), ("ServiceName", "backend")], "Average", start, end)

    plt.figure(figsize=(10, 9))

    # panel 1, request volume and the 5xx failures the gateway returned
    ax1 = plt.subplot(3, 1, 1)
    m, v = to_series(reqs, t0)
    ax1.plot(m, v, color="blue", label="requests")
    m, v = to_series(fivexx, t0)
    ax1.plot(m, v, color="red", label="target 5xx")
    ax1.set_ylabel("count per minute")
    ax1.set_title("ALB request count and 5xx responses")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # panel 2, how long the gateway took to answer
    ax2 = plt.subplot(3, 1, 2)
    m, v = to_series(rt, t0)
    ax2.plot([x for x in m], [y * 1000 for y in v], color="purple")
    ax2.set_ylabel("ms")
    ax2.set_title("ALB target response time (average)")
    ax2.grid(True, alpha=0.3)

    # panel 3, CPU per service with the 60 percent scale out target
    ax3 = plt.subplot(3, 1, 3)
    m, v = to_series(cpu_gw, t0)
    ax3.plot(m, v, color="blue", label="gateway")
    m, v = to_series(cpu_be, t0)
    ax3.plot(m, v, color="green", label="backend")
    ax3.axhline(60, color="gray", linestyle="--", label="60 percent target")
    ax3.set_ylabel("CPU percent")
    ax3.set_xlabel("minutes since window start")
    ax3.set_title("ECS CPU per service")
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    plt.suptitle("Exp 3 CloudWatch, ALB and ECS during the load test")
    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    print(f"wrote {out_png}")


main()
