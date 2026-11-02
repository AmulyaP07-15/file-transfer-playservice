# Makes the chart for Experiment 1 or Experiment 2 from a summary csv.
# Two panels, success rate on the left and latency (median and p95) on the right.
#
# usage
#   python plot_results.py <summary_csv> <x_label> <title> <output_png>
# example
#   python plot_results.py ../exp1-loss/summary_local.csv "loss percent" "Exp 1 loss" ../exp1-loss/chart_local.png

import sys
import csv
import matplotlib
matplotlib.use("Agg")  # save the plot to a file instead of opening a window
import matplotlib.pyplot as plt

# bigger fonts so the chart is readable when it is shrunk onto a slide
plt.rcParams.update({
    "font.size": 16, "axes.titlesize": 19, "axes.labelsize": 16,
    "xtick.labelsize": 15, "ytick.labelsize": 15, "legend.fontsize": 15,
    "lines.linewidth": 2.5, "lines.markersize": 9,
})


def main():
    summary_csv = sys.argv[1]
    x_label = sys.argv[2]
    title = sys.argv[3]
    out_png = sys.argv[4]

    # read the summary csv, the first column is whatever I varied (loss or size)
    with open(summary_csv, newline="") as f:
        rows = list(csv.DictReader(f))

    first_col = list(rows[0].keys())[0]
    x_labels = [r[first_col] for r in rows]
    success = [float(r["success_rate"]) * 100 for r in rows]
    median = [float(r["median_ms"]) for r in rows]
    p95 = [float(r["p95_ms"]) for r in rows]

    # plot against evenly spaced positions, then label them with the real values
    x = range(len(x_labels))

    plt.figure(figsize=(13, 5.6))

    # left panel, reliability
    plt.subplot(1, 2, 1)
    plt.plot(x, success, "o-", color="green")
    plt.ylim(0, 105)
    plt.xticks(x, x_labels)
    plt.xlabel(x_label)
    plt.ylabel("success rate (percent)")
    plt.title("Reliability")
    plt.grid(True, alpha=0.3)

    # right panel, latency of the downloads that succeeded
    plt.subplot(1, 2, 2)
    plt.plot(x, median, "o-", color="blue", label="median")
    plt.plot(x, p95, "s--", color="orange", label="p95")
    plt.xticks(x, x_labels)
    plt.xlabel(x_label)
    plt.ylabel("latency (ms)")
    plt.title("Latency of successful downloads")
    plt.legend()
    plt.grid(True, alpha=0.3)

    plt.suptitle(title)
    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    print(f"wrote {out_png}")


main()
