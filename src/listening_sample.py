#!/usr/bin/env python3
"""Draw the blind listening-review sample (PREREGISTRATION.md, "Quality checks").

100 YAMNet-positive and 100 YAMNet-negative simulation clips, fixed seed.
  Positives: stratified by recorder (proportional to the positive pool).
  Negatives: five 4-minute position strata of the labeled window, 20 per stratum, spread
             across recorders in proportion to each recorder's negative clips in that stratum.

Pool (see DEVIATIONS.md): clips of "Human Presence on Trail" events that carry no other
simulated component, so the reviewer judges playback and not a passing vehicle.

Writes:
  results/listening/review_sheet.csv   blind_id, audible, notes   (give this to the reviewer)
  results/listening/sample_key.csv     labels and positions        (keep away from the reviewer)

  python src/listening_sample.py --dataset PATH_TO_CSV
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
SEED = 20251002
N_POSITIVE = 100
N_NEGATIVE = 100
EVENT_TYPE = "Human Presence on Trail"
STRATUM_EDGES = [-600.0, -360.0, -120.0, 120.0, 360.0, 601.0]  # seconds from onset, 4 minutes each
N_STRATA = len(STRATUM_EDGES) - 1


def parse_list(value: object) -> list:
    text = str(value).strip()
    if not text or text == "[]":
        return []
    result = ast.literal_eval(text)
    return result if isinstance(result, list) else [result]


def position_stratum(relative_seconds: pd.Series) -> pd.Series:
    """0..4 for the five 4-minute strata; -1 outside -600..+600 s."""
    index = np.digitize(relative_seconds.to_numpy(float), STRATUM_EDGES) - 1
    index[(index < 0) | (index >= N_STRATA)] = -1
    return pd.Series(index, index=relative_seconds.index)


def allocate(counts: pd.Series, total: int) -> pd.Series:
    """Proportional allocation by largest remainder, never above the pool of a group."""
    counts = counts[counts > 0].astype(int)
    total = min(total, int(counts.sum()))
    alloc = pd.Series(0, index=counts.index, dtype=int)
    while alloc.sum() < total:
        room = counts - alloc
        open_groups = room[room > 0]
        left = total - int(alloc.sum())
        share = open_groups / open_groups.sum() * left
        base = np.minimum(np.floor(share).astype(int), open_groups)
        alloc[base.index] += base
        left = total - int(alloc.sum())
        if left == 0:
            break
        room = counts - alloc
        frac = (share - np.floor(share))[room[base.index] > 0].sort_values(ascending=False, kind="stable")
        for group in frac.index[:left]:
            alloc[group] += 1
    return alloc


def build_pool(clips: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """clips: clip_name, Recorder, Timestamp, Sim Type, Sim Relative Time, Human Activity, Human Activity Score."""
    rows, other_component, outside_window = [], 0, 0
    for r in clips.loc[clips["Sim Type"] != "[]"].to_dict("records"):
        types = parse_list(r["Sim Type"])
        times = parse_list(r["Sim Relative Time"])
        if EVENT_TYPE not in types:
            continue
        if len(types) != 1:
            other_component += 1
            continue
        rows.append(
            dict(
                clip_name=r["clip_name"], recorder=r["Recorder"], timestamp=r["Timestamp"],
                relative_seconds=float(times[0]), yamnet_label=r["Human Activity"],
                yamnet_score=r["Human Activity Score"], yamnet_positive=r["Human Activity"] != "no",
            )
        )
    pool = pd.DataFrame(rows)
    pool["stratum"] = position_stratum(pool["relative_seconds"])
    outside_window = int((pool["stratum"] < 0).sum())
    pool = pool.loc[pool["stratum"] >= 0].reset_index(drop=True)
    info = {"clips_other_component_excluded": other_component, "clips_outside_window_excluded": outside_window,
            "pool_positive": int(pool["yamnet_positive"].sum()), "pool_negative": int((~pool["yamnet_positive"]).sum())}
    return pool, info


def draw_sample(pool: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    pool = pool.sort_values("clip_name").reset_index(drop=True)
    picked = []

    positives = pool.loc[pool["yamnet_positive"]]
    for recorder, n in allocate(positives.groupby("recorder").size(), N_POSITIVE).items():
        group = positives.loc[positives["recorder"] == recorder]
        picked.append(group.iloc[rng.choice(len(group), size=n, replace=False)])

    negatives = pool.loc[~pool["yamnet_positive"]]
    per_stratum = N_NEGATIVE // N_STRATA
    for stratum in range(N_STRATA):
        in_stratum = negatives.loc[negatives["stratum"] == stratum]
        for recorder, n in allocate(in_stratum.groupby("recorder").size(), per_stratum).items():
            group = in_stratum.loc[in_stratum["recorder"] == recorder]
            picked.append(group.iloc[rng.choice(len(group), size=n, replace=False)])

    sample = pd.concat(picked, ignore_index=True)
    # Inverse sampling fraction of each sampling cell, so overall rates can be weighted back to
    # the pool. Negatives were drawn per (recorder, stratum), positives per recorder.
    pool_cells = pool.assign(cell=np.where(pool["yamnet_positive"], pool["recorder"] + "|pos",
                                           pool["recorder"] + "|neg|" + pool["stratum"].astype(str)))
    sample["cell"] = np.where(sample["yamnet_positive"], sample["recorder"] + "|pos",
                              sample["recorder"] + "|neg|" + sample["stratum"].astype(str))
    sample["weight"] = sample["cell"].map(pool_cells.groupby("cell").size() / sample.groupby("cell").size())
    sample = sample.drop(columns="cell")
    sample = sample.iloc[rng.permutation(len(sample))].reset_index(drop=True)
    sample.insert(0, "blind_id", [f"L{i:03d}" for i in range(1, len(sample) + 1)])
    return sample


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=REPO / "results" / "listening")
    args = parser.parse_args()

    columns = ["clip_name", "Recorder", "Timestamp", "Sim Type", "Sim Relative Time", "Human Activity",
               "Human Activity Score"]
    pool, info = build_pool(pd.read_csv(args.dataset, usecols=columns))
    sample = draw_sample(pool)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sample[["blind_id"]].assign(audible="", notes="").to_csv(args.output_dir / "review_sheet.csv", index=False)
    sample.to_csv(args.output_dir / "sample_key.csv", index=False)

    print(f"Pool: {info}")
    print(f"Sampled {int(sample['yamnet_positive'].sum())} positive, {int((~sample['yamnet_positive']).sum())} negative clips (seed {SEED}).")
    print(sample.groupby(["yamnet_positive", "recorder"]).size().unstack(fill_value=0).to_string())
    print("Negative clips per stratum, sample vs pool (the +2 to +6 min stratum is thin because other simulated sounds overlap it):")
    print(pd.DataFrame({"sample": sample.loc[~sample["yamnet_positive"]].groupby("stratum").size(),
                        "pool": pool.loc[~pool["yamnet_positive"]].groupby("stratum").size()}).to_string())


if __name__ == "__main__":
    main()
