#!/usr/bin/env python3
"""Result figures, drawn only from the tables in results/tables/ (no analysis happens here).

  fig_variants.png                    primary estimate and 95% interval for every variant
  fig_placebo.png                     observed estimate against the 95% placebo-in-time range (exploratory)
  fig_leave_one_recorder_out.png      estimate with each recorder omitted (exploratory)
  fig_count_model.png                 count-model rate ratios (exploratory; needs the Week 9 run)

  python src/make_figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402,F401
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
TABLES, FIGURES = REPO / "results" / "tables", REPO / "results" / "figures"
INK, MUTED, GRID = "#222222", "#6b6b6b", "#e4e4e4"
BLUE, BLUE_LIGHT, ORANGE = "#1f4e79", "#7a9cc0", "#c2571a"
LABEL = {"v1_original": "1  0-60 min", "v2_post_playback": "2  15-60 min", "v2b_post_playback_5min": "2b  20-60 min, 5-min bins",
         "v3_buffered": "3  30-60 min", "v4a_original_excluded": "4a  as 1, YAMNet clips out",
         "v4b_post_playback_excluded": "4b  as 2, YAMNet clips out", "v4c_post_playback_5min_excluded": "4c  as 2b, YAMNet clips out"}
ORDER = list(LABEL)
STYLE = {"font.size": 8, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": INK,
         "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 100, "savefig.dpi": 200}


def clean(ax, zero=0.0):
    ax.axvline(zero, color=MUTED, lw=0.9, ls=(0, (4, 3)), zorder=1)
    ax.grid(axis="x", color=GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    ax.spines["left"].set_visible(False)


def frame(fig, title, note):
    """Left-aligned title and footnote on the figure, so long text is never clipped by the axes."""
    fig.suptitle(title, x=0.01, ha="left", fontsize=9, fontweight="bold", color=INK)
    fig.text(0.01, 0.01, note, fontsize=7, color=MUTED, ha="left")
    fig.tight_layout(rect=(0, 0.05, 1, 0.94))


def fmt(x, digits=2):
    return f"{x:+.{digits}f}".replace("-", "-")


def variants_figure(results: pd.DataFrame, out: Path) -> None:
    t = results[results["hypothesis"] == "primary_call_rate"].set_index("variant").loc[ORDER]
    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    clean(ax)
    for i, (variant, r) in enumerate(t.iterrows()):
        y = len(ORDER) - 1 - i
        colour = BLUE if variant == "v1_original" else BLUE_LIGHT
        ax.plot([r["ci_low"], r["ci_high"]], [y, y], color=colour, lw=1.6, solid_capstyle="round", zorder=2)
        ax.plot(r["estimate"], y, "o", color=colour, ms=6, mec="white", mew=1.2, zorder=3)
        ax.text(3.0, y, f"n={int(r['n_events'])}   {fmt(r['estimate'])}   p={r['two_sided_p']:.2f}", va="center", fontsize=7.5, color=INK)
    ax.set_yticks(range(len(ORDER)))
    ax.set_yticklabels([LABEL[v] for v in ORDER][::-1])
    ax.set_xlim(-3.6, 5.4)
    ax.set_xticks(range(-3, 3))
    ax.set_xlabel("Change in call rate after time zero, calls per minute (95% interval)")
    frame(fig, "Primary test, isolated events: no variant shows a detectable change",
          "Variant 1 (dark) is the gate. Estimates are baseline-adjusted contrasts. p is two-sided and unadjusted.")
    fig.savefig(out)
    plt.close(fig)


def placebo_figure(placebo: pd.DataFrame, out: Path) -> None:
    t = placebo[(placebo["pool"] == "strict") & (placebo["analysis"] == "primary_isolated")
                & (placebo["hypothesis"] == "primary_call_rate")].set_index("variant").loc[ORDER]
    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    clean(ax)
    for i, (variant, r) in enumerate(t.iterrows()):
        y = len(ORDER) - 1 - i
        ax.plot([r["null_q025"], r["null_q975"]], [y, y], color="#b9b9b9", lw=7, solid_capstyle="butt", zorder=2)
        ax.plot(r["observed"], y, "o", color=ORANGE, ms=6, mec="white", mew=1.2, zorder=3)
        ax.text(1.3, y, f"{fmt(r['observed'])}   p={r['p_two_sided']:.3f}", va="center", fontsize=7.5, color=INK)
    ax.set_yticks(range(len(ORDER)))
    ax.set_yticklabels([LABEL[v] for v in ORDER][::-1])
    ax.set_xlim(-3.0, 2.6)
    ax.set_xlabel("Estimate, calls per minute")
    n, k = int(t["events"].iloc[0]), int(t["recorders"].iloc[0])
    frame(fig, "Placebo-in-time (exploratory): observed estimates are increases, at the top of the range",
          f"Grey bar: 95% range of {int(t['replicates'].iloc[0]):,} placebo draws. Dot: observed. {n} events on {k} recorders. p two-sided, unadjusted.")
    fig.savefig(out)
    plt.close(fig)


def loro_figure(loro: pd.DataFrame, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.0), sharey=True)
    names = {"v1_original": "Variant 1 (0-60 min)", "v2_post_playback": "Variant 2 (15-60 min)"}
    for ax, (variant, g) in zip(axes, loro.groupby("variant", sort=False)):
        clean(ax)
        g = g.reset_index(drop=True)
        for i, r in g.iterrows():
            y = len(g) - 1 - i
            base = r["omitted"] == "none"
            colour = BLUE if base else (ORANGE if r["influential"] else BLUE_LIGHT)
            half = 1.96 * r["standard_error"]
            ax.plot([r["estimate"] - half, r["estimate"] + half], [y, y], color=colour, lw=1.4, solid_capstyle="round", zorder=2)
            ax.plot(r["estimate"], y, "o", color=colour, ms=5.5, mec="white", mew=1.1, zorder=3)
        ax.set_yticks(range(len(g)))
        ax.set_yticklabels(["all recorders" if o == "none" else f"omit {o.replace('Audio_Moth_', 'Moth ')}" for o in g["omitted"]][::-1])
        ax.set_title(names[variant], loc="left", fontsize=8.5, color=INK, fontweight="bold")
        ax.set_xlim(-4.2, 2.6)
        ax.set_xlabel("Estimate, calls per minute")
    fig.suptitle("Leave-one-recorder-out (exploratory): omitting Moth 6 flips the sign", x=0.01, ha="left", fontsize=9, fontweight="bold", color=INK)
    fig.text(0.01, 0.01, "Dot and 95% interval of the primary model refit without one recorder. Orange: sign flips or p crosses 0.05.", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(out)
    plt.close(fig)


def count_model_figure(count: pd.DataFrame, out: Path) -> bool:
    needed = {"post_over_pre_rate_ratio", "pre_rate_ratio", "post_over_pre_ci_low"}
    if not needed <= set(count.columns):
        return False
    fig, ax = plt.subplots(figsize=(6.8, 2.8))
    clean(ax, zero=1.0)
    ax.set_xscale("log")
    rows = []
    for _, r in count.iterrows():
        w = f"window {r['window'].replace('-', ' to ')} min"
        rows.append((f"Post vs baseline, {w}", r["rate_ratio"], r["ci_low"], r["ci_high"], BLUE_LIGHT))
        rows.append((f"Post vs pre, {w}", r["post_over_pre_rate_ratio"], r["post_over_pre_ci_low"], r["post_over_pre_ci_high"], BLUE))
    for i, (label, rr, lo, hi, colour) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.plot([lo, hi], [y, y], color=colour, lw=1.6, solid_capstyle="round", zorder=2)
        ax.plot(rr, y, "o", color=colour, ms=6, mec="white", mew=1.2, zorder=3)
        ax.text(2.6, y, f"{rr:.2f}  ({lo:.2f} to {hi:.2f})", va="center", fontsize=7.5, color=INK)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows][::-1])
    ax.set_xlim(0.25, 2.5)
    ax.set_xticks([0.25, 0.5, 1, 2])
    ax.set_xticklabels(["0.25", "0.5", "1", "2"])
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xlabel("Rate ratio (below 1 means fewer detections)")
    pre = f"{count['pre_rate_ratio'].iloc[0]:.2f}"
    clusters = int(count["recorder_days"].iloc[0])
    frame(fig, "Count model (exploratory): against the pre window there is no detectable drop",
          f"The pre window is already {pre} of baseline. Intervals use recorder-day clusters ({clusters}). Two-way clustering gives wider intervals.")
    fig.savefig(out)
    plt.close(fig)
    return True


def main() -> None:
    plt.rcParams.update(STYLE)
    FIGURES.mkdir(parents=True, exist_ok=True)
    variants_figure(pd.read_csv(TABLES / "results_table.csv"), FIGURES / "fig_variants.png")
    placebo_figure(pd.read_csv(TABLES / "placebo_results.csv"), FIGURES / "fig_placebo.png")
    loro_figure(pd.read_csv(TABLES / "robustness_leave_one_recorder.csv"), FIGURES / "fig_leave_one_recorder_out.png")
    drawn = count_model_figure(pd.read_csv(TABLES / "robustness_count_model.csv"), FIGURES / "fig_count_model.png")
    print("Wrote fig_variants, fig_placebo, fig_leave_one_recorder_out" + (", fig_count_model" if drawn else ". fig_count_model needs the rerun of src/robustness.py"))


if __name__ == "__main__":
    sys.exit(main())
