#!/usr/bin/env python3
"""Summarise the completed blind listening review (descriptive, not part of the decision rules).

Reads the reviewer's sheet (blind_id, audible = yes/no/unsure, notes) and the key, then reports
how often playback was audible in YAMNet-positive and YAMNet-negative clips, overall and by
position stratum. "unsure" is never merged silently: both bounds are reported.
Negatives were sampled equally per position stratum, but the strata differ a lot in size, so the
overall rate must use `share_yes_pool_weighted` (weights = pool size / sample size per cell).
The Wilson interval belongs to the unweighted share and is not a pool-level interval.

  python src/analyze_listening.py --sheet PATH_TO_COMPLETED_SHEET
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
VALID = {"yes", "no", "unsure"}
STRATUM_LABELS = {0: "-10 to -6 min", 1: "-6 to -2 min", 2: "-2 to +2 min", 3: "+2 to +6 min", 4: "+6 to +10 min"}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (centre - half, centre + half)


def summarise(joined: pd.DataFrame) -> pd.DataFrame:
    rows = []

    def add(label: str, subset: pd.DataFrame) -> None:
        n = len(subset)
        yes = int((subset["audible"] == "yes").sum())
        no = int((subset["audible"] == "no").sum())
        unsure = int((subset["audible"] == "unsure").sum())
        low, high = wilson(yes, n)
        weighted = (np.average(subset["audible"].eq("yes"), weights=subset["weight"]) if n else np.nan)
        rows.append(dict(group=label, n=n, yes=yes, no=no, unsure=unsure,
                         share_yes=yes / n if n else np.nan, share_yes_pool_weighted=weighted, wilson_low=low, wilson_high=high,
                         share_yes_or_unsure=(yes + unsure) / n if n else np.nan))

    positive = joined.loc[joined["yamnet_positive"]]
    negative = joined.loc[~joined["yamnet_positive"]]
    add("yamnet_positive_all", positive)
    add("yamnet_negative_all", negative)
    for stratum, label in STRATUM_LABELS.items():
        add(f"yamnet_negative_{label}", negative.loc[negative["stratum"] == stratum])
    return pd.DataFrame(rows)


def load(sheet: Path, key: Path) -> pd.DataFrame:
    answers = pd.read_csv(sheet, dtype=str).fillna("")
    answers["audible"] = answers["audible"].str.strip().str.lower()
    bad = answers.loc[~answers["audible"].isin(VALID), "blind_id"]
    if len(bad):
        raise SystemExit(f"{len(bad)} rows lack yes/no/unsure, first: {list(bad[:5])}")
    joined = pd.read_csv(key).merge(answers[["blind_id", "audible"]], on="blind_id", how="left", validate="1:1")
    if joined["audible"].isna().any():
        raise SystemExit("Sheet and key do not cover the same clips.")
    return joined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sheet", type=Path, required=True)
    parser.add_argument("--key", type=Path, default=REPO / "results" / "listening" / "sample_key.csv")
    parser.add_argument("--output", type=Path, default=REPO / "results" / "tables" / "listening_summary.csv")
    args = parser.parse_args()
    table = summarise(load(args.sheet, args.key))
    table.to_csv(args.output, index=False)
    print(table.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
