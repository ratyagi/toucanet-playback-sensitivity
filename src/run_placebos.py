#!/usr/bin/env python3
"""Placebo-in-time calibration for every response-window variant (Week 3).

For each variant this script builds two placebo pools per event:
  * strict: the reference rule (days with no simulated event, same recorder, within 30 clock
    minutes, complete uncontaminated -3h/+12h path), via the lead's own function;
  * relaxed (secondary): any day, same recorder, within 30 clock minutes, analysis window free
    of any simulated component. Earlier playbacks may carry over, so this is a sensitivity check.

In detection-excluded variants, the clip positions removed from each real event window are
removed from its placebo windows too (see PREREGISTRATION.md).

Run src/run_variants.py first (it writes the observed event contrasts used here).

  python src/run_placebos.py --dataset PATH_TO_CSV
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "lead"))
sys.path.insert(0, str(REPO / "src"))

import event_study as es  # noqa: E402  (lead's module, unmodified)
import placebo_hypothesis_analysis as pha  # noqa: E402  (lead's module, unmodified)
import run_variants as rv  # noqa: E402
from exclusion import yamnet_exclusion_mask  # noqa: E402
from placebo_core import ClipContext, balanced_mean, empirical_p, simulate_null  # noqa: E402

ANALYSES = ["primary_isolated", "robustness_overlapping"]


def load_clip_context(dataset: Path, tail_seconds: float) -> ClipContext:
    clips = pd.read_csv(dataset, usecols=["Recorder", "Timestamp", "species", "Human Activity"])
    clips["clip_time"] = pd.to_datetime(clips["Timestamp"], format="%Y%m%d_%H%M%S")
    clips["drop"] = yamnet_exclusion_mask(clips, tail_seconds)
    return ClipContext(clips[["Recorder", "clip_time", "species", "drop"]], es.parse_list)


def relaxed_pools(bins: pd.DataFrame, real_events: pd.DataFrame, offsets: list[int], tolerance: int) -> dict:
    index = bins.set_index(["recorder", "bin_time"], drop=False)
    pools = {}
    for event in real_events.itertuples(index=False):
        target = event.onset.hour * 60 + event.onset.minute
        pool = bins.loc[
            (bins["recorder"] == event.recorder)
            & (pha.clock_distance(bins["tod_bin"], target) <= tolerance)
        ]
        accepted = []
        for candidate in pool["bin_time"].drop_duplicates():
            keys = [(event.recorder, candidate + pd.Timedelta(minutes=int(o))) for o in offsets]
            if not all(key in index.index for key in keys):
                continue
            if index.loc[keys, "event_contaminated"].astype(bool).any():
                continue
            accepted.append(pd.Timestamp(candidate))
        pools[event.event_id] = accepted
    return pools


def path_from_bins(index: pd.DataFrame, recorder: str, start: pd.Timestamp, offsets: list[int]) -> pd.DataFrame:
    rows = []
    for offset in offsets:
        key = (recorder, start + pd.Timedelta(minutes=int(offset)))
        row = {"relative_minutes": offset, "clips": 0, "call_rate_deviation": np.nan, "taxa_count_deviation": np.nan}
        if key in index.index:
            observed = index.loc[key]
            row.update(
                clips=int(observed["clip_count"]),
                call_rate_deviation=observed["call_rate_deviation"],
                taxa_count_deviation=observed["taxa_count_deviation"],
            )
        rows.append(row)
    return pd.DataFrame(rows)


def window_offsets(spec: dict) -> list[int]:
    minutes = int(spec["bin_minutes"])
    pre, post = spec["pre_window"], spec["post_window"]
    pre_offsets = range(pre["start_minutes"], pre["end_minutes_exclusive"], minutes)
    post_offsets = range(post["start_minutes"], post["end_minutes_exclusive"], minutes)
    return sorted(set(pre_offsets) | set(post_offsets))


def candidate_contrasts(events, pools, spec, offsets, index, context, baseline):
    """Contrast of every (event, candidate) pair, as {event_id: {hypothesis: array}} and window clips."""
    minutes = int(spec["bin_minutes"])
    span = (spec["pre_window"]["start_minutes"], spec["post_window"]["end_minutes_exclusive"])
    frames, clip_totals = [], []
    for event in events.itertuples(index=False):
        pattern = None
        if context is not None:
            event_bin = event.onset.floor(f"{minutes}min")
            pattern = context.removal_pattern(event.recorder, event_bin, *span)
        for candidate in pools[event.event_id]:
            if context is None:
                path = path_from_bins(index, event.recorder, candidate, offsets)
            else:
                path = context.path(event.recorder, candidate, offsets, minutes, pattern, baseline)
            clip_totals.append(int(path["clips"].sum()))
            path["event_id"] = f"{event.event_id}|{candidate.isoformat()}"
            path["recorder"] = event.recorder
            path["onset"] = candidate
            frames.append(path)
    if not frames:
        return {}, []
    result = pha.event_contrasts(pd.concat(frames, ignore_index=True), spec)
    lookup = {(row.event_id, row.hypothesis): row.contrast for row in result.itertuples(index=False)}
    names = [item["name"] for item in spec["hypotheses"]]
    values = {}
    for event in events.itertuples(index=False):
        values[event.event_id] = {
            name: np.array(
                [lookup.get((f"{event.event_id}|{c.isoformat()}", name), np.nan) for c in pools[event.event_id]],
                dtype=float,
            )
            for name in names
        }
    return values, clip_totals


def self_check(index, context, baseline, spec, offsets, events) -> int:
    """Recomputing a real event's own window from clips (no extra drops) must equal its binned values."""
    minutes = int(spec["bin_minutes"])
    checked = 0
    for event in events.itertuples(index=False):
        start = event.onset.floor(f"{minutes}min")
        binned = path_from_bins(index, event.recorder, start, offsets)
        rebuilt = context.path(event.recorder, start, offsets, minutes, set(), baseline)
        for column in ("call_rate_deviation", "taxa_count_deviation"):
            if not np.allclose(binned[column], rebuilt[column], equal_nan=True, atol=1e-9):
                raise SystemExit(f"Clip-level recompute disagrees with binned values for {event.event_id}.")
        checked += 1
    return checked


def check_lead_reference(results: pd.DataFrame, reference_path: Path) -> None:
    reference = pd.read_csv(reference_path)
    reference["hypothesis"] = reference["hypothesis"].str.replace(r"_drop_0_60m$", "", regex=True)
    ours = results.loc[
        (results["variant"] == "v1_original") & (results["pool"] == "strict")
        & (results["analysis"] == "primary_isolated")
    ].merge(reference, on="hypothesis", suffixes=("", "_ref"))
    if len(ours) != len(reference):
        raise SystemExit("Strict-pool rows for variant 1 do not line up with the lead-code placebo output.")
    pairs = [("observed", "observed_recorder_balanced_contrast"), ("null_q025", "null_q025_ref"),
             ("null_median", "null_median_ref"), ("null_q975", "null_q975_ref"), ("p_less", "empirical_p_less")]
    if not (ours["events"] == ours["events_ref"]).all() or not (ours["recorders"] == ours["recorders_ref"]).all():
        raise SystemExit("Strict-pool event or recorder counts for variant 1 differ from the lead-code output.")
    for mine, theirs in pairs:
        if not np.allclose(ours[mine], ours[theirs], atol=1e-9):
            raise SystemExit(f"Strict-pool placebo for variant 1 does NOT reproduce the lead-code output ({mine}).")
    print("Variant 1 strict-pool placebo reproduces the lead-code output.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--events", type=Path, default=REPO / "reference" / "events.csv")
    parser.add_argument("--configs", type=Path, default=REPO / "configs" / "variants")
    parser.add_argument("--work-dir", type=Path, default=REPO / "results" / "intermediate" / "variants")
    parser.add_argument("--tables-dir", type=Path, default=REPO / "results" / "tables")
    parser.add_argument("--lead-reference", type=Path, default=REPO / "reference" / "placebo_lead_code_output.csv")
    parser.add_argument("--replicates", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20251002)
    parser.add_argument("--tod-tolerance-minutes", type=int, default=30)
    args = parser.parse_args()

    components, _ = rv.load_events(args.events)
    real_events = components.loc[components["is_presence"]].reset_index(drop=True)
    specs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(args.configs.glob("*.json"))]
    context_cache: dict[float, ClipContext] = {}
    bins_cache: dict[tuple, pd.DataFrame] = {}
    results, pool_rows = [], []

    for spec in specs:
        name, minutes = spec["name"], int(spec["bin_minutes"])
        observed_path = args.work_dir / name / "event_contrasts.csv"
        if not observed_path.exists():
            raise SystemExit(f"{observed_path} not found. Run src/run_variants.py first.")
        observed = pd.read_csv(observed_path, parse_dates=["onset"])
        key = (minutes, bool(spec["exclude_yamnet"]), spec["yamnet_tail_seconds"])
        print(f"== {name}", flush=True)
        if key not in bins_cache:
            source = args.dataset
            if spec["exclude_yamnet"]:
                source = args.work_dir / name / "clips_filtered.csv"
                if not source.exists():
                    rv.write_filtered_clips(args.dataset, spec["yamnet_tail_seconds"], source)
            bins_cache[key] = pha.add_residuals(rv.build_bins(source, minutes, components))
        bins = bins_cache[key]
        index = bins.set_index(["recorder", "bin_time"], drop=False)
        baseline = {
            (row.recorder, row.tod_bin): (row.call_rate_baseline, row.taxa_count_baseline)
            for row in bins.drop_duplicates(["recorder", "tod_bin"]).itertuples(index=False)
        }
        context = None
        if spec["exclude_yamnet"]:
            tail = float(spec["yamnet_tail_seconds"])
            if tail not in context_cache:
                context_cache[tail] = load_clip_context(args.dataset, tail)
            context = context_cache[tail]
        offsets = window_offsets(spec)
        if context is not None:
            checked = self_check(index, context, baseline, spec, offsets, real_events)
            print(f"   clip-level recompute matches binned values for {checked} events", flush=True)

        relative = list(range(-180, 720 + minutes, minutes))
        _, strict = pha.candidate_placebos(bins, components, real_events, relative, args.tod_tolerance_minutes)
        pools_by_type = {
            "strict": strict,
            "relaxed": relaxed_pools(bins, real_events, offsets, args.tod_tolerance_minutes),
        }
        population = observed.drop_duplicates("event_id").set_index("event_id")["analysis"].to_dict()
        hypotheses = [item["name"] for item in spec["hypotheses"]]

        for pool_type, pools in pools_by_type.items():
            for analysis in ANALYSES:
                members = real_events.loc[real_events["event_id"].map(lambda e: population.get(e) == analysis)]
                eligible = members.loc[members["event_id"].map(lambda e: bool(pools.get(e)))]
                counts = [len(pools[e]) for e in eligible["event_id"]]
                row_base = {"variant": name, "pool": pool_type, "analysis": analysis}
                pool_rows.append(
                    {**row_base, "population_events": len(members), "events_with_candidates": len(eligible),
                     "recorders_with_candidates": eligible["recorder"].nunique(),
                     "recorders_without_candidates": ";".join(sorted(set(members["recorder"]) - set(eligible["recorder"]))),
                     "candidates_min": min(counts) if counts else np.nan,
                     "candidates_median": float(np.median(counts)) if counts else np.nan,
                     "candidates_max": max(counts) if counts else np.nan}
                )
                if eligible.empty:
                    for hypothesis in hypotheses:
                        results.append({**row_base, "hypothesis": hypothesis, "events": 0, "recorders": 0})
                    continue
                values, clip_totals = candidate_contrasts(eligible, pools, spec, offsets, index, context, baseline)
                pool_rows[-1]["median_candidate_window_clips"] = float(np.median(clip_totals))
                codes = pd.factorize(eligible["recorder"])[0]
                null = simulate_null([values[e] for e in eligible["event_id"]], codes, hypotheses,
                                     args.replicates, args.seed)
                subset = observed.loc[observed["event_id"].isin(set(eligible["event_id"]))]
                for hypothesis in hypotheses:
                    group = subset.loc[subset["hypothesis"] == hypothesis]
                    obs = pha.balanced_recorder_mean(group)
                    series = null[hypothesis][np.isfinite(null[hypothesis])]
                    results.append(
                        {**row_base, "hypothesis": hypothesis, "events": group["event_id"].nunique(),
                         "recorders": group.loc[group["contrast"].notna(), "recorder"].nunique(),
                         "observed": obs,
                         "null_q025": np.quantile(series, 0.025) if series.size else np.nan,
                         "null_median": np.quantile(series, 0.5) if series.size else np.nan,
                         "null_q975": np.quantile(series, 0.975) if series.size else np.nan,
                         **empirical_p(null[hypothesis], obs), "replicates": args.replicates, "seed": args.seed}
                    )
            print(f"   {pool_type} pool done", flush=True)

    table = pd.DataFrame(results)
    args.tables_dir.mkdir(parents=True, exist_ok=True)
    check_lead_reference(table, args.lead_reference)
    table.to_csv(args.tables_dir / "placebo_results.csv", index=False)
    pd.DataFrame(pool_rows).to_csv(args.tables_dir / "placebo_pool_summary.csv", index=False)
    print(f"Done. Tables in {args.tables_dir}", flush=True)


if __name__ == "__main__":
    main()
