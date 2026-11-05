#!/usr/bin/env python3
"""Run every pre-registered response-window variant through the reference pipeline.

The team lead's functions (src/lead/) are imported unchanged. This script only adds:
  * one config per variant (configs/variants/*.json),
  * the YAMNet exclusion filter (src/exclusion.py), applied before binning,
  * a fixed event population taken from variant 1 (see DEVIATIONS.md),
  * two-sided p-values and the minimum detectable effect.

Variant 1 must reproduce reference/mixed_effects_results.csv, otherwise the run stops.

  python src/run_variants.py --dataset PATH_TO_CSV
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "lead"))
sys.path.insert(0, str(REPO / "src"))

import event_study as es  # noqa: E402  (lead's module, unmodified)
import placebo_hypothesis_analysis as pha  # noqa: E402  (lead's module, unmodified)
from exclusion import yamnet_exclusion_mask  # noqa: E402

CHUNKSIZE = 100_000
BASELINE_PRE_BUFFER_MINUTES = 10
BASELINE_POST_BUFFER_MINUTES = 60
ANALYSES = ["primary_isolated", "robustness_overlapping"]


def load_events(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    components = pd.read_csv(path, parse_dates=["onset"])
    presence = components.loc[components["is_presence"]].copy().reset_index(drop=True)
    presence["event_date"] = presence["onset"].dt.date.astype(str)
    return components, presence


def write_filtered_clips(dataset: Path, tail_seconds: float, out_csv: Path) -> dict:
    columns = ["Recorder", "Timestamp", "species", "Human Activity", *es.WEATHER_COLUMNS]
    clips = pd.read_csv(dataset, usecols=columns)
    clips["clip_time"] = pd.to_datetime(clips["Timestamp"], format="%Y%m%d_%H%M%S")
    drop = yamnet_exclusion_mask(clips, tail_seconds)
    kept_columns = ["Recorder", "Timestamp", "species", *es.WEATHER_COLUMNS]
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    clips.loc[~drop, kept_columns].to_csv(out_csv, index=False)
    return {
        "clips_total": len(clips),
        "yamnet_positive_clips": int((clips["Human Activity"] != "no").sum()),
        "clips_removed": int(drop.sum()),
        "minutes_removed": float(drop.sum()) * 3.0 / 60.0,
        "share_removed": float(drop.mean()),
    }


def build_bins(dataset: Path, minutes: int, components: pd.DataFrame) -> pd.DataFrame:
    bins = es.aggregate_descriptors(dataset, minutes, CHUNKSIZE)
    bins["embedding_count"] = np.nan
    bins["embedding_dispersion"] = np.nan
    bins["embedding_coverage"] = bins["embedding_count"] / bins["clip_count"]
    return es.mark_event_contamination(
        bins, components, minutes, BASELINE_PRE_BUFFER_MINUTES, BASELINE_POST_BUFFER_MINUTES
    )


def window_clips(paths: pd.DataFrame, bins: pd.DataFrame, spec: dict) -> pd.DataFrame:
    merged = paths.merge(
        bins[["recorder", "bin_time", "clip_count"]], on=["recorder", "bin_time"], how="left"
    )
    # Count only bins that contribute to the contrast (a baseline exists for that time of day).
    merged = merged.loc[merged["call_rate_deviation"].notna()]
    rows = []
    for event_id, event in merged.groupby("event_id", sort=False):
        row = {"event_id": event_id}
        for label, window in (("pre", spec["pre_window"]), ("post", spec["post_window"])):
            inside = event["relative_minutes"].between(
                window["start_minutes"], window["end_minutes_exclusive"], inclusive="left"
            )
            row[f"{label}_clips"] = float(event.loc[inside, "clip_count"].sum())
        rows.append(row)
    return pd.DataFrame(rows)


def fit_models(
    contrasts: pd.DataFrame, spec: dict, variant: str, method: str = "primary"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    model_rows, heterogeneity_rows = [], []
    for analysis in ANALYSES:
        for hypothesis in [item["name"] for item in spec["hypotheses"]]:
            subset = contrasts.loc[
                (contrasts["analysis"] == analysis) & (contrasts["hypothesis"] == hypothesis)
            ]
            result = pha.fit_random_intercept(subset)
            result.update({"variant": variant, "method": method, "analysis": analysis, "hypothesis": hypothesis})
            z = result["z"]
            result["two_sided_p"] = float(2 * norm.sf(abs(z))) if np.isfinite(z) else np.nan
            result["minimum_detectable_effect"] = 1.96 * result["standard_error"]
            model_rows.append(result)
            for recorder, group in subset.groupby("recorder"):
                values = group["contrast"].dropna()
                heterogeneity_rows.append(
                    {
                        "variant": variant,
                        "method": method,
                        "analysis": analysis,
                        "hypothesis": hypothesis,
                        "recorder": recorder,
                        "events": len(values),
                        "mean_contrast": values.mean(),
                        "sd_contrast": values.std(ddof=1) if len(values) > 1 else np.nan,
                    }
                )
    models = pd.DataFrame(model_rows)
    models["holm_p"] = models.groupby("analysis")["one_sided_p_less"].transform(pha.holm_adjust)
    return models, pd.DataFrame(heterogeneity_rows)


def check_reference(models: pd.DataFrame, reference_path: Path) -> None:
    reference = pd.read_csv(reference_path)
    reference["hypothesis"] = reference["hypothesis"].str.replace(r"_drop_0_60m$", "", regex=True)
    merged = models.merge(reference, on=["analysis", "hypothesis"], suffixes=("", "_ref"))
    if len(merged) != len(reference):
        raise SystemExit("Variant 1 rows do not line up with the reference results.")
    same_n = (merged["n_events"] == merged["n_events_ref"]).all()
    close = np.allclose(merged["estimate"], merged["estimate_ref"], atol=1e-6) and np.allclose(
        merged["standard_error"], merged["standard_error_ref"], atol=1e-6
    )
    if not (same_n and close):
        raise SystemExit("Variant 1 does NOT reproduce reference/mixed_effects_results.csv. Stopping.")
    print("Variant 1 reproduces the reference results.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--events", type=Path, default=REPO / "reference" / "events.csv")
    parser.add_argument("--reference", type=Path, default=REPO / "reference" / "mixed_effects_results.csv")
    parser.add_argument("--configs", type=Path, default=REPO / "configs" / "variants")
    parser.add_argument("--work-dir", type=Path, default=REPO / "results" / "intermediate" / "variants")
    parser.add_argument("--tables-dir", type=Path, default=REPO / "results" / "tables")
    args = parser.parse_args()

    args.work_dir.mkdir(parents=True, exist_ok=True)
    args.tables_dir.mkdir(parents=True, exist_ok=True)
    components, presence = load_events(args.events)
    specs = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(args.configs.glob("*.json"))]
    if not specs or specs[0]["name"] != "v1_original":
        raise SystemExit("configs/variants must start with v1_original (it fixes the event population).")

    bin_cache: dict[tuple, tuple[pd.DataFrame, dict]] = {}
    population: dict[str, set] = {}
    all_models, all_heterogeneity, all_summaries = [], [], []

    for spec in specs:
        name = spec["name"]
        minutes = int(spec["bin_minutes"])
        key = (minutes, bool(spec["exclude_yamnet"]), spec["yamnet_tail_seconds"])
        print(f"== {name}: bins {minutes} min, exclusion {spec['exclude_yamnet']}", flush=True)
        if key not in bin_cache:
            effort = {"clips_total": np.nan, "yamnet_positive_clips": np.nan,
                      "clips_removed": 0, "minutes_removed": 0.0, "share_removed": 0.0}
            source = args.dataset
            if spec["exclude_yamnet"]:
                source = args.work_dir / name / "clips_filtered.csv"
                effort = write_filtered_clips(args.dataset, spec["yamnet_tail_seconds"], source)
            bin_cache[key] = (build_bins(source, minutes, components), effort)
        bins, effort = bin_cache[key]

        paths, _ = es.build_event_paths(bins, presence, minutes, 3.0, 12.0)
        if name == "v1_original":
            overlap = es.overlap_audit(paths, presence, components).set_index("event_id")
            full = overlap["coverage_fraction"] == 1
            population["isolated"] = set(overlap.index[full & (overlap["other_presence_onsets_in_window"] == 0)])
            population["overlapping"] = set(overlap.index[full & (overlap["other_presence_onsets_in_window"] > 0)])
            print(f"   population: {len(population['isolated'])} isolated, "
                  f"{len(population['overlapping'])} overlapping, "
                  f"{len(overlap) - int(full.sum())} incomplete", flush=True)

        contrasts = pha.event_contrasts(paths, spec)
        contrasts["analysis"] = np.select(
            [contrasts["event_id"].isin(population["isolated"]),
             contrasts["event_id"].isin(population["overlapping"])],
            ["primary_isolated", "robustness_overlapping"],
            default="excluded_incomplete",
        )
        contrasts = contrasts.merge(window_clips(paths, bins, spec), on="event_id", how="left")
        contrasts.insert(0, "variant", name)
        (args.work_dir / name).mkdir(parents=True, exist_ok=True)
        contrasts.to_csv(args.work_dir / name / "event_contrasts.csv", index=False)

        models, heterogeneity = fit_models(contrasts, spec, name)
        if name == "v1_original":
            check_reference(models, args.reference)

        # Exploratory analyses (see DEVIATIONS.md): raw pre/post and complete-window.
        raw_paths = paths.copy()
        for metric in pha.CURVE_METRICS:
            raw_paths[f"{metric}_deviation"] = raw_paths[metric]
        raw = pha.event_contrasts(raw_paths, spec)
        raw["analysis"] = raw["event_id"].map(
            lambda value: "primary_isolated" if value in population["isolated"]
            else ("robustness_overlapping" if value in population["overlapping"] else "excluded_incomplete")
        )
        raw_models, raw_heterogeneity = fit_models(raw, spec, name, "raw_unadjusted")
        pre_w, post_w = spec["pre_window"], spec["post_window"]
        expected_pre = int((pre_w["end_minutes_exclusive"] - pre_w["start_minutes"]) // minutes)
        expected_post = int((post_w["end_minutes_exclusive"] - post_w["start_minutes"]) // minutes)
        complete = contrasts.loc[
            (contrasts["pre_bins"] == expected_pre) & (contrasts["post_bins"] == expected_post)
        ]
        complete_models, complete_heterogeneity = fit_models(complete, spec, name, "complete_window")

        for frame in (models, raw_models, complete_models):
            frame["bin_minutes"] = minutes
            frame["post_window"] = f"{post_w['start_minutes']}-{post_w['end_minutes_exclusive']}"
            frame["yamnet_excluded"] = bool(spec["exclude_yamnet"])
        all_models.extend([models, raw_models, complete_models])
        all_heterogeneity.extend([heterogeneity, raw_heterogeneity, complete_heterogeneity])
        post = spec["post_window"]
        usable = contrasts.loc[contrasts["analysis"] == "primary_isolated"].dropna(subset=["contrast"])
        all_summaries.append(
            {
                "variant": name,
                "bin_minutes": minutes,
                "post_window": f"{post['start_minutes']}-{post['end_minutes_exclusive']}",
                "yamnet_excluded": bool(spec["exclude_yamnet"]),
                "isolated_events_with_contrast": usable["event_id"].nunique(),
                "isolated_recorders": usable["recorder"].nunique(),
                "median_post_bins_used": float(usable["post_bins"].median()) if len(usable) else np.nan,
                "median_pre_bins_used": float(usable["pre_bins"].median()) if len(usable) else np.nan,
                "median_post_window_clips": float(usable["post_clips"].median()) if len(usable) else np.nan,
                "median_pre_window_clips": float(usable["pre_clips"].median()) if len(usable) else np.nan,
                "dataset_clips_removed": effort["clips_removed"],
                "dataset_minutes_removed": effort["minutes_removed"],
                "dataset_share_removed": effort["share_removed"],
            }
        )

    columns = ["variant", "method", "post_window", "bin_minutes", "yamnet_excluded", "analysis", "hypothesis",
               "n_events", "n_recorders", "estimate", "standard_error", "z", "one_sided_p_less",
               "two_sided_p", "holm_p", "minimum_detectable_effect", "icc",
               "random_intercept_variance", "residual_variance", "converged", "fit_method"]
    results = pd.concat(all_models, ignore_index=True)[columns]
    results.to_csv(args.tables_dir / "variant_results.csv", index=False)
    pd.concat(all_heterogeneity, ignore_index=True).to_csv(
        args.tables_dir / "variant_recorder_results.csv", index=False)
    pd.DataFrame(all_summaries).to_csv(args.tables_dir / "variant_effort_summary.csv", index=False)
    print(f"Done. Tables in {args.tables_dir}", flush=True)


if __name__ == "__main__":
    main()
