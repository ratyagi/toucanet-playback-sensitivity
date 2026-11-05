#!/usr/bin/env python3
"""Derive the labeled span and YAMNet detection count of every simulated event.

Onset = clip timestamp minus the clip's `Sim Relative Time` (same rule as the
reference pipeline). Each event is then summarised from its own clips.

  python src/derive_event_spans.py --dataset PATH_TO_CSV \
      --events reference/events.csv --output reference/event_spans.csv
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

import pandas as pd

CLIP_SECONDS = 3.0


def parse_list(value: object) -> list:
    text = str(value).strip()
    if not text or text == "[]":
        return []
    result = ast.literal_eval(text)
    return result if isinstance(result, list) else [result]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    usecols = ["Recorder", "Timestamp", "Sim Type", "Sim Relative Time", "Human Activity"]
    data = pd.read_csv(args.dataset, usecols=usecols)
    data = data.loc[data["Sim Type"] != "[]"].copy()
    data["clip_time"] = pd.to_datetime(data["Timestamp"], format="%Y%m%d_%H%M%S")
    data["yamnet_positive"] = data["Human Activity"] != "no"

    rows = []
    for clip in data.to_dict("records"):
        types = parse_list(clip["Sim Type"])
        relative_times = parse_list(clip["Sim Relative Time"])
        for event_type, relative in zip(types, relative_times):
            relative = float(relative)
            rows.append(
                {
                    "recorder": clip["Recorder"],
                    "event_type": event_type,
                    "onset": clip["clip_time"] - pd.to_timedelta(relative, unit="s"),
                    "relative_seconds": relative,
                    "clip_time": clip["clip_time"],
                    "yamnet_positive": bool(clip["yamnet_positive"]),
                }
            )
    clips = pd.DataFrame(rows)

    spans = (
        clips.groupby(["recorder", "event_type", "onset"])
        .agg(
            clips=("relative_seconds", "size"),
            rel_min_seconds=("relative_seconds", "min"),
            rel_max_seconds=("relative_seconds", "max"),
            first_clip=("clip_time", "min"),
            last_clip=("clip_time", "max"),
            yamnet_positive_clips=("yamnet_positive", "sum"),
        )
        .reset_index()
    )
    spans["labeled_start"] = spans["onset"] + pd.to_timedelta(spans["rel_min_seconds"], unit="s")
    spans["labeled_end"] = spans["onset"] + pd.to_timedelta(spans["rel_max_seconds"] + CLIP_SECONDS, unit="s")
    spans["has_yamnet_detection"] = spans["yamnet_positive_clips"] > 0

    events = pd.read_csv(args.events, parse_dates=["onset"])
    merged = events[["event_id", "recorder", "event_type", "onset", "is_presence"]].merge(
        spans, on=["recorder", "event_type", "onset"], how="outer", indicator=True
    )
    unmatched = int((merged["_merge"] != "both").sum())
    if unmatched:
        raise SystemExit(f"{unmatched} events differ between the dataset and {args.events}")
    merged = merged.drop(columns="_merge").sort_values("event_id")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.output, index=False)

    presence = merged.loc[merged["is_presence"]]
    print(f"Events matched to {args.events.name}: {len(merged)} (human presence: {len(presence)})")
    print(f"Human-presence events with a YAMNet detection: {int(presence['has_yamnet_detection'].sum())}/{len(presence)}")
    print(f"YAMNet-positive clips in human-presence events: {int(presence['yamnet_positive_clips'].sum())}")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
