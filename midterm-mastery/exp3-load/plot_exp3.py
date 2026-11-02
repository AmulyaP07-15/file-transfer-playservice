# Experiment 3 autoscaling chart. This only shows what Locust itself cannot,
# the number of ECS tasks each service was running over time (from the ECS
# describe-services polling in task_counts.csv), against the offered load.
# The throughput, latency and failure charts come straight from the Locust
# report (locust_report.html), so I do not redraw them here.
#
# usage, arguments optional
#   python plot_exp3.py [task_counts_csv] [output_png]

import os
import sys
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# bigger fonts so the chart stays readable when it is shrunk onto a slide
plt.rcParams.update({
    "font.size": 16, "axes.titlesize": 18, "axes.labelsize": 16,
    "xtick.labelsize": 14, "ytick.labelsize": 14, "legend.fontsize": 15,
    "lines.linewidth": 2.6,
})

HERE = os.path.dirname(os.path.abspath(__file__))

# the staged load I drove with Locust (from shapes.py), as (minute, users).
# I draw this as a reference so I can see the task count react to the load.
LOAD_STAGES = [(0, 10), (5, 50), (10, 200), (15, 0), (20, 0)]


def load_tasks(path):
    # task_counts.csv into {service: (minutes_since_start, running_count)}
    series = {}
    t0 = None
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            try:
                epoch = float(r["epoch"])
            except (TypeError, ValueError, KeyError):
                continue
            if t0 is None:
                t0 = epoch
            svc = r["service"]
            series.setdefault(svc, ([], []))
            series[svc][0].append((epoch - t0) / 60.0)
            series[svc][1].append(float(r["running"]))
    return series


def main():
    tasks_csv = sys.argv[1] if len(sys.argv) >= 2 else os.path.join(HERE, "task_counts.csv")
    out_png = sys.argv[2] if len(sys.argv) >= 3 else os.path.join(HERE, "chart_exp3_autoscaling.png")

    series = load_tasks(tasks_csv)

    fig, ax = plt.subplots(figsize=(11, 5.8))

    # running tasks per service, step plot since the count changes in jumps
    colors = {"gateway": "blue", "backend": "green"}
    for svc in sorted(series):
        mins, run = series[svc]
        ax.step(mins, run, where="post", label=svc + " tasks", color=colors.get(svc), linewidth=2)
    ax.set_ylabel("running ECS tasks")
    ax.set_xlabel("minutes since test start")
    ax.set_ylim(0, 5)
    ax.grid(True, alpha=0.3)

    # offered load on a second axis so I can see the tasks react to it
    ax2 = ax.twinx()
    stage_x = [s[0] for s in LOAD_STAGES]
    stage_y = [s[1] for s in LOAD_STAGES]
    ax2.step(stage_x, stage_y, where="post", color="gray", linestyle="--", label="offered users")
    ax2.set_ylabel("offered users")

    # one combined legend
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    ax.set_title("ECS running tasks vs offered load")
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    print(f"wrote {out_png}")


main()
