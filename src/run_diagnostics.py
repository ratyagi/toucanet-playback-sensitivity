#!/usr/bin/env python3
"""Week 5 diagnostics (descriptive only, nothing here enters the decision rules).

1. Per-recorder figures: for every human-presence event, YAMNet-positive clips, call rate and
   taxa count in 15-minute bins from -180 to +180 minutes around the onset, with the
   recorder-by-time-of-day baseline.
2. YAMNet split: events with at least one YAMNet detection (22) versus none (7), with the
   event contrasts side by side. No significance test, the groups are too small. The split is
   confounded with recorder (all 8 Audio_Moth_6 events have a detection, 4 of the 7 events
   without one are on Audio_Moth_5), so a recorder table is written next to it.

Needs the outputs of steps 3 to 6 of the README (results/intermediate/...).

  python src/run_diagnostics.py --dataset PATH_TO_CSV
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
INTERMEDIATE = REPO / "results" / "intermediate"
BIN_MINUTES = 15
XLIM = (-180, 180)
BLUE, ORANGE, GREY = "#1f77b4", "#d95f02", "#7f7f7f"


def yamnet_by_bin(clips: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Count YAMNet-positive clips per event and 15-minute bin (relative to the floored onset).

    clips: Recorder, clip_time, positive. events: event_id, recorder, onset.
    """
    rows = []
    for ev in events.itertuples():
        sel = clips.loc[clips["Recorder"] == ev.recorder]
        onset_bin = ev.onset.floor(f"{BIN_MINUTES}min")
        rel = (sel["clip_time"].dt.floor(f"{BIN_MINUTES}min") - onset_bin) / pd.Timedelta(minutes=1)
        keep = (rel >= XLIM[0]) & (rel < XLIM[1])
        frame = pd.DataFrame({"relative_minutes": rel[keep], "positive": sel.loc[keep, "positive"]})
        grouped = frame.groupby("relative_minutes").agg(clips=("positive", "size"), yamnet_positive=("positive", "sum"))
        grouped = grouped.reset_index()
        grouped.insert(0, "event_id", ev.event_id)
        rows.append(grouped)
    return pd.concat(rows, ignore_index=True)


def split_table(contrasts: pd.DataFrame, spans: pd.DataFrame) -> pd.DataFrame:
    presence = spans.loc[spans["is_presence"], ["event_id", "recorder", "has_yamnet_detection", "yamnet_positive_clips"]]
    return presence.merge(contrasts, on="event_id", how="left")


def split_summary(table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    table = table.dropna(subset=["variant"])
    every = table.assign(analysis="all_events")  # each event appears once per variant
    for (variant, analysis), sub in pd.concat([table, every]).groupby(["variant", "analysis"], dropna=True):
        for flag, group in sub.groupby("has_yamnet_detection"):
            values = group["contrast"].dropna()
            rows.append(dict(variant=variant, analysis=analysis, has_yamnet_detection=bool(flag),
                             events=len(group), events_with_contrast=len(values),
                             mean_contrast=values.mean() if len(values) else np.nan,
                             median_contrast=values.median() if len(values) else np.nan,
                             min_contrast=values.min() if len(values) else np.nan,
                             max_contrast=values.max() if len(values) else np.nan))
    return pd.DataFrame(rows)


def plot_recorder(recorder: str, events: pd.DataFrame, paths: pd.DataFrame, ybins: pd.DataFrame, out: Path) -> None:
    n = len(events)
    fig, axes = plt.subplots(n, 3, figsize=(12, 1.9 * n + 0.6), squeeze=False, sharex=True)
    for row, ev in enumerate(events.itertuples()):
        p = paths.loc[paths["event_id"] == ev.event_id].sort_values("relative_minutes")
        p = p.loc[(p["relative_minutes"] >= XLIM[0]) & (p["relative_minutes"] < XLIM[1])]
        y = ybins.loc[ybins["event_id"] == ev.event_id]
        a0, a1, a2 = axes[row]
        a0.bar(y["relative_minutes"] + BIN_MINUTES / 2, y["yamnet_positive"], width=BIN_MINUTES * 0.9, color=ORANGE)
        a1.plot(p["relative_minutes"] + BIN_MINUTES / 2, p["call_rate"], color=BLUE, lw=1.4, label="observed")
        a1.plot(p["relative_minutes"] + BIN_MINUTES / 2, p["call_rate_baseline"], color=GREY, lw=1.2, ls="--", label="baseline")
        a2.plot(p["relative_minutes"] + BIN_MINUTES / 2, p["taxa_count"], color=BLUE, lw=1.4)
        a2.plot(p["relative_minutes"] + BIN_MINUTES / 2, p["taxa_count_baseline"], color=GREY, lw=1.2, ls="--")
        label = f"{ev.event_id}\n{pd.Timestamp(ev.onset):%m-%d %H:%M}\n{'YAMNet+ in labeled clips' if ev.has_yamnet_detection else 'none in labeled clips'}"
        a0.set_ylabel(label, fontsize=7, rotation=0, ha="right", va="center", labelpad=34)
        for ax in (a0, a1, a2):
            ax.axvspan(0, 60, color=GREY, alpha=0.10, lw=0)  # pre-registered 0-60 response window
            ax.axvline(0, color="black", lw=0.8)
            ax.tick_params(labelsize=7)
            ax.set_xlim(*XLIM)
        if row == 0:
            a0.set_title("YAMNet-positive clips per bin", fontsize=9)
            a1.set_title("Call rate (detections/min)", fontsize=9)
            a2.set_title("Taxa count", fontsize=9)
            a1.legend(fontsize=7, frameon=False)
    for ax in axes[-1]:
        ax.set_xlabel("Minutes from onset (grey band = 0-60 window)", fontsize=8)
    fig.suptitle(f"{recorder}: human-presence events (YAMNet bars count every clip in the bin, labeled or not)", fontsize=10, y=0.995)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, required=True)
    args = parser.parse_args()

    spans = pd.read_csv(REPO / "reference" / "event_spans.csv", parse_dates=["onset"])
    presence = spans.loc[spans["is_presence"]].sort_values(["recorder", "onset"]).reset_index(drop=True)
    paths = pd.read_csv(INTERMEDIATE / "event_paths.csv")
    clips = pd.read_csv(args.dataset, usecols=["Recorder", "Timestamp", "Human Activity"])
    clips["clip_time"] = pd.to_datetime(clips["Timestamp"], format="%Y%m%d_%H%M%S")
    clips["positive"] = clips["Human Activity"] != "no"

    ybins = yamnet_by_bin(clips, presence)
    figures = REPO / "results" / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    for recorder, events in presence.groupby("recorder"):
        plot_recorder(recorder, events, paths, ybins, figures / f"event_diagnostics_{recorder}.png")

    tables = REPO / "results" / "tables"
    frames = []
    for variant in ("v1_original", "v2_post_playback"):
        c = pd.read_csv(INTERMEDIATE / "variants" / variant / "event_contrasts.csv")
        frames.append(c.loc[c["hypothesis"] == "primary_call_rate", ["variant", "event_id", "analysis", "contrast", "pre_bins", "post_bins"]])
    table = split_table(pd.concat(frames, ignore_index=True), spans)
    table.to_csv(tables / "yamnet_split_events.csv", index=False)
    summary = split_summary(table)
    summary.to_csv(tables / "yamnet_split_summary.csv", index=False)
    by_recorder = pd.crosstab(spans.loc[spans["is_presence"], "recorder"],
                              spans.loc[spans["is_presence"], "has_yamnet_detection"]).rename(
        columns={False: "events_without_detection", True: "events_with_detection"})
    by_recorder.reset_index().to_csv(tables / "yamnet_split_by_recorder.csv", index=False)
    print(f"Figures: {len(list(figures.glob('event_diagnostics_*.png')))} in {figures}")
    print(summary.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
