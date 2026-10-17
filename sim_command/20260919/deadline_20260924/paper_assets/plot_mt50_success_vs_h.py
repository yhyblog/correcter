#!/usr/bin/env python3
"""Plot observed MT50 means from the frozen 16-cell summary; no experiments."""

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


HORIZONS = (10, 20, 30, 40, 50)
STYLES = {
    "N": {"color": "#333333", "marker": "o", "linestyle": "-"},
    "Post": {"color": "#0072B2", "marker": "s", "linestyle": "-"},
    "Velocity": {"color": "#D55E00", "marker": "^", "linestyle": "--"},
    "R": {"color": "#CC79A7", "marker": "D", "linestyle": "None"},
}


def read_cells(csv_path):
    with csv_path.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    cells = {(row["method"], int(row["H"])): row for row in rows}
    expected = {(method, horizon) for method in ("N", "Post", "Velocity")
                for horizon in HORIZONS} | {("R", 10)}
    if len(rows) != 16 or set(cells) != expected:
        raise ValueError("Expected exactly 16 unique complete cells, including R at H=10 only.")
    for key, row in cells.items():
        if tuple(int(row[name]) for name in
                 ("tasks", "attempts", "terminal_episodes", "technical_failures")) != (50, 500, 500, 0):
            raise ValueError(f"Incomplete or unexpected sample counts in {key}.")
        observed = 100 * int(row["successes"]) / int(row["terminal_episodes"])
        if abs(observed - float(row["success_percent"])) > 1e-8:
            raise ValueError(f"Success count and percentage disagree in {key}.")
    return {key: float(row["success_percent"]) for key, row in cells.items()}


def make_figure(values):
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 8.5,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "axes.linewidth": 0.7,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.facecolor": "white",
    })
    fig, (left, right) = plt.subplots(1, 2, figsize=(7.2, 3.45))
    fig.subplots_adjust(left=0.078, right=0.985, bottom=0.16, top=0.81, wspace=0.30)

    for method in ("N", "Post", "Velocity"):
        left.plot(HORIZONS, [values[method, h] for h in HORIZONS],
                  **STYLES[method], linewidth=1.6, markersize=4,
                  markeredgewidth=0.65, markeredgecolor="white", zorder=3)
    # A single observation: deliberately no extrapolation, interpolation, or line.
    left.plot([10], [values["R", 10]], **STYLES["R"], markersize=5,
              markeredgewidth=0.7, markeredgecolor="white", zorder=5)
    left.annotate(f"R: {values['R', 10]:.1f}%", xy=(10, values["R", 10]),
                  xytext=(14.1, 71.15), ha="left", va="center", fontsize=7.7,
                  color="#7F3C75",
                  arrowprops={"arrowstyle": "-", "color": "#7F3C75",
                              "linewidth": 0.65, "shrinkA": 3, "shrinkB": 4},
                  zorder=6)
    left.set(title="(a) Observed success", ylabel="Success (%)", ylim=(35, 74))
    left.set_yticks((40, 50, 60, 70))

    right.axhline(0, color="#777777", linewidth=0.8, zorder=1)
    for method in ("Post", "Velocity"):
        gains = [values[method, h] - values["N", h] for h in HORIZONS]
        right.plot(HORIZONS, gains, **STYLES[method], linewidth=1.6,
                   markersize=4, markeredgewidth=0.65, markeredgecolor="white",
                   zorder=3)
    right.set(title="(b) Gain over the same-H N baseline",
              ylabel="Success gain (percentage points)", ylim=(-1, 25))
    right.set_yticks((0, 5, 10, 15, 20, 25))

    for ax in (left, right):
        ax.set_xlabel("Execution horizon H")
        ax.set_xlim(8, 52)
        ax.set_xticks(HORIZONS)
        ax.grid(axis="y", color="#D9DDE1", linewidth=0.55, zorder=0)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(direction="out", length=3, width=0.7)

    handles = [Line2D([], [], **STYLES[method], linewidth=1.6, markersize=4.8,
                      markeredgewidth=0.65, markeredgecolor="white",
                      label="R (H = 10 only)" if method == "R" else method)
               for method in ("N", "Post", "Velocity", "R")]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.995),
               ncol=4, frameon=False, columnspacing=2.0, handlelength=2.4)
    return fig


def main():
    assets = Path(__file__).resolve().parent
    campaign = assets.parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path,
                        default=campaign / "results/A/A_D24_MAIN_ONCE_V1/FINAL_CELLS.csv")
    parser.add_argument("--outdir", type=Path, default=assets)
    args = parser.parse_args()
    values = read_cells(args.csv)
    figure = make_figure(values)
    args.outdir.mkdir(parents=True, exist_ok=True)
    for extension in ("pdf", "svg", "png"):
        output = args.outdir / f"MT50_SUCCESS_VS_H.{extension}"
        figure.savefig(output, dpi=450, bbox_inches="tight", pad_inches=0.035)
        print(output)
    plt.close(figure)


if __name__ == "__main__":
    main()
