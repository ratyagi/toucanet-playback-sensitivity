#!/usr/bin/env python3
"""Event-count table: how many of the 29 events each variant uses, and why the others are not used.

Reads results/intermediate/variants/<variant>/event_contrasts.csv (written by src/run_variants.py).
Writes results/tables/event_counts.csv, one row per variant and event group, call-rate outcome.

Groups (fixed by variant 1, see PREREGISTRATION.md):
  primary_isolated        complete window, no other presence onset in it (the primary test)
  robustness_overlapping  complete window, another presence onset inside it
  excluded_incomplete     window not fully covered by the recording

An event is usable when it has a contrast, which needs at least one clean baseline bin
for the pre window and one for the post window. Otherwise it is "no_baseline".

  python src/event_counts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
WORK = REPO / "results" / "intermediate" / "variants"
OUT = REPO / "results" / "tables" / "event_counts.csv"
GROUPS = ["primary_isolated", "robustness_overlapping", "excluded_incomplete"]
OUTCOME = "primary_call_rate"


def count_events(contrasts: pd.DataFrame) -> pd.DataFrame:
    """contrasts: event_contrasts rows for one variant (one row per event and outcome)."""
    c = contrasts[contrasts["hypothesis"] == OUTCOME]
    rows = []
    for group in GROUPS:
        g = c[c["analysis"] == group]
        usable = int(g["contrast"].notna().sum())
        rows.append({"variant": c["variant"].iloc[0], "group": group, "events": int(g["event_id"].nunique()),
                     "usable": usable, "no_baseline": int(g["event_id"].nunique()) - usable})
    return pd.DataFrame(rows)


def main() -> None:
    folders = sorted(p for p in WORK.iterdir() if (p / "event_contrasts.csv").exists())
    if not folders:
        raise SystemExit(f"No event_contrasts.csv under {WORK}. Run src/run_variants.py first.")
    order = ["v1_original", "v2_post_playback", "v2b_post_playback_5min", "v3_buffered",
             "v4a_original_excluded", "v4b_post_playback_excluded", "v4c_post_playback_5min_excluded"]
    table = pd.concat([count_events(pd.read_csv(p / "event_contrasts.csv")) for p in folders], ignore_index=True)
    table["variant"] = pd.Categorical(table["variant"], order, ordered=True)
    table = table.sort_values(["variant", "group"], key=lambda s: s.map({g: i for i, g in enumerate(GROUPS)})
                              if s.name == "group" else s).reset_index(drop=True)
    table["variant"] = table["variant"].astype(str)
    table.to_csv(OUT, index=False)
    print(table.to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
