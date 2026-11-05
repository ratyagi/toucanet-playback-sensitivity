#!/usr/bin/env python3
"""Run pre-specified short-window tests and a matched placebo-in-time audit."""

from __future__ import annotations

import argparse
import json
import os
import warnings
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/kwf-matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm
from statsmodels.regression.mixed_linear_model import MixedLM
from statsmodels.tools.sm_exceptions import ConvergenceWarning


CURVE_METRICS = ["call_rate", "taxa_count", "entropy", "embedding_dispersion"]


def clock_distance(left: pd.Series, right: int) -> pd.Series:
    difference = (left - right).abs()
    return np.minimum(difference, 1440 - difference)


def load_hypotheses(path: Path) -> dict:
    specification = json.loads(path.read_text(encoding="utf-8"))
    if len(specification["hypotheses"]) not in (1, 2):
        raise ValueError("Pre-specification must contain one or two hypotheses")
    return specification


def event_contrasts(paths: pd.DataFrame, specification: dict) -> pd.DataFrame:
    pre = specification["pre_window"]
    post = specification["post_window"]
    rows = []
    for event_id, event in paths.groupby("event_id", sort=False):
        metadata = event.iloc[0]
        for hypothesis in specification["hypotheses"]:
            column = f"{hypothesis['metric']}_deviation"
            pre_values = event.loc[
                event["relative_minutes"].between(
                    pre["start_minutes"], pre["end_minutes_exclusive"], inclusive="left"
                ),
                column,
            ].dropna()
            post_values = event.loc[
                event["relative_minutes"].between(
                    post["start_minutes"], post["end_minutes_exclusive"], inclusive="left"
                ),
                column,
            ].dropna()
            rows.append(
                {
                    "event_id": event_id,
                    "recorder": metadata["recorder"],
                    "onset": metadata["onset"],
                    "hypothesis": hypothesis["name"],
                    "metric": hypothesis["metric"],
                    "alternative": hypothesis["alternative"],
                    "pre_mean": pre_values.mean() if len(pre_values) else np.nan,
                    "post_mean": post_values.mean() if len(post_values) else np.nan,
                    "contrast": post_values.mean() - pre_values.mean()
                    if len(pre_values) and len(post_values)
                    else np.nan,
                    "pre_bins": len(pre_values),
                    "post_bins": len(post_values),
                }
            )
    return pd.DataFrame(rows)


def fit_random_intercept(data: pd.DataFrame) -> dict:
    usable = data.dropna(subset=["contrast", "recorder"]).copy()
    result = {
        "n_events": len(usable),
        "n_recorders": usable["recorder"].nunique(),
        "estimate": np.nan,
        "standard_error": np.nan,
        "z": np.nan,
        "one_sided_p_less": np.nan,
        "random_intercept_variance": np.nan,
        "residual_variance": np.nan,
        "icc": np.nan,
        "converged": False,
        "fit_method": "mixedlm",
    }
    if len(usable) < 3 or usable["recorder"].nunique() < 2:
        return result
    exog = np.ones((len(usable), 1))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        warnings.simplefilter("ignore", UserWarning)
        warnings.simplefilter("ignore", RuntimeWarning)
        try:
            fitted = MixedLM(
                usable["contrast"].to_numpy(),
                exog,
                groups=usable["recorder"].to_numpy(),
            ).fit(reml=True, method="lbfgs", disp=False)
        except Exception:
            try:
                fitted = MixedLM(
                    usable["contrast"].to_numpy(),
                    exog,
                    groups=usable["recorder"].to_numpy(),
                ).fit(reml=True, method="powell", disp=False)
                result["fit_method"] = "mixedlm_powell"
            except Exception:
                return result
    estimate = float(fitted.fe_params[0])
    standard_error = float(fitted.bse_fe[0])
    random_variance = float(np.asarray(fitted.cov_re)[0, 0])
    residual_variance = float(fitted.scale)
    result.update(
        {
            "estimate": estimate,
            "standard_error": standard_error,
            "z": estimate / standard_error if standard_error > 0 else np.nan,
            "one_sided_p_less": norm.cdf(estimate / standard_error)
            if standard_error > 0
            else np.nan,
            "random_intercept_variance": random_variance,
            "residual_variance": residual_variance,
            "icc": random_variance / (random_variance + residual_variance)
            if random_variance + residual_variance > 0
            else np.nan,
            "converged": bool(fitted.converged),
        }
    )
    return result


def holm_adjust(values: pd.Series) -> pd.Series:
    result = pd.Series(np.nan, index=values.index, dtype=float)
    valid = values.dropna().sort_values()
    running = 0.0
    total = len(valid)
    for rank, (index, value) in enumerate(valid.items()):
        adjusted = min(1.0, float(value) * (total - rank))
        running = max(running, adjusted)
        result.loc[index] = running
    return result


def add_residuals(bins: pd.DataFrame) -> pd.DataFrame:
    clean = bins.loc[~bins["event_contaminated"]]
    baseline = (
        clean.groupby(["recorder", "tod_bin"])[CURVE_METRICS]
        .median()
        .add_suffix("_baseline")
        .reset_index()
    )
    result = bins.merge(baseline, on=["recorder", "tod_bin"], how="left")
    for metric in CURVE_METRICS:
        result[f"{metric}_deviation"] = result[metric] - result[f"{metric}_baseline"]
    return result


def candidate_placebos(
    bins: pd.DataFrame,
    components: pd.DataFrame,
    real_events: pd.DataFrame,
    relative_minutes: list[int],
    tod_tolerance: int,
) -> tuple[pd.DataFrame, dict[str, list[pd.Timestamp]]]:
    component_days = (
        components.groupby("recorder")["onset"]
        .agg(lambda values: set(values.dt.date.astype(str)))
        .to_dict()
    )
    all_days = bins.groupby("recorder")["date"].agg(set).to_dict()
    index = bins.set_index(["recorder", "bin_time"], drop=False)
    pools: dict[str, list[pd.Timestamp]] = {}
    rows = []
    for event in real_events.itertuples(index=False):
        target_tod = event.onset.hour * 60 + event.onset.minute
        free_days = all_days.get(event.recorder, set()) - component_days.get(event.recorder, set())
        possible = bins.loc[
            (bins["recorder"] == event.recorder)
            & (bins["date"].isin(free_days))
            & (clock_distance(bins["tod_bin"], target_tod) <= tod_tolerance)
        ]
        accepted = []
        for candidate in possible["bin_time"].drop_duplicates():
            keys = [
                (event.recorder, candidate + pd.Timedelta(int(offset), unit="min"))
                for offset in relative_minutes
            ]
            if not all(key in index.index for key in keys):
                continue
            path = index.loc[keys]
            if isinstance(path, pd.Series):
                path = path.to_frame().T
            if path["event_contaminated"].astype(bool).any():
                continue
            accepted.append(pd.Timestamp(candidate))
            rows.append(
                {
                    "event_id": event.event_id,
                    "recorder": event.recorder,
                    "real_onset": event.onset,
                    "placebo_onset": candidate,
                    "clock_difference_minutes": int(
                        min(
                            abs(candidate.hour * 60 + candidate.minute - target_tod),
                            1440 - abs(candidate.hour * 60 + candidate.minute - target_tod),
                        )
                    ),
                    "event_free_date": candidate.date().isoformat(),
                }
            )
        pools[event.event_id] = accepted
    return pd.DataFrame(rows), pools


def balanced_recorder_mean(data: pd.DataFrame) -> float:
    recorder_means = data.groupby("recorder")["contrast"].mean().dropna()
    return float(recorder_means.mean()) if len(recorder_means) else np.nan


def run_placebos(
    bins: pd.DataFrame,
    real_events: pd.DataFrame,
    pools: dict[str, list[pd.Timestamp]],
    specification: dict,
    relative_minutes: list[int],
    replicates: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    eligible = real_events.loc[real_events["event_id"].map(lambda value: bool(pools.get(value)))].copy()
    index = bins.set_index(["recorder", "bin_time"], drop=False)
    rng = np.random.default_rng(seed)
    assignments = []
    null_rows = []
    curve_values: dict[tuple[str, str, int], list[float]] = defaultdict(list)

    path_cache: dict[tuple[str, pd.Timestamp], pd.DataFrame] = {}
    for event in eligible.itertuples(index=False):
        for candidate in pools[event.event_id]:
            keys = [
                (event.recorder, candidate + pd.Timedelta(int(offset), unit="min"))
                for offset in relative_minutes
            ]
            path = index.loc[keys].copy().reset_index(drop=True)
            path["relative_minutes"] = relative_minutes
            path_cache[(event.event_id, candidate)] = path

    for replicate in range(1, replicates + 1):
        chosen_paths = []
        for event in eligible.itertuples(index=False):
            candidate = pools[event.event_id][rng.integers(len(pools[event.event_id]))]
            assignments.append(
                {
                    "replicate": replicate,
                    "event_id": event.event_id,
                    "recorder": event.recorder,
                    "real_onset": event.onset,
                    "placebo_onset": candidate,
                }
            )
            path = path_cache[(event.event_id, candidate)].copy()
            path["event_id"] = event.event_id
            path["onset"] = candidate
            chosen_paths.append(path)
        combined = pd.concat(chosen_paths, ignore_index=True)
        contrasts = event_contrasts(combined, specification)
        for hypothesis, group in contrasts.groupby("hypothesis"):
            null_rows.append(
                {
                    "replicate": replicate,
                    "hypothesis": hypothesis,
                    "recorder_balanced_contrast": balanced_recorder_mean(group),
                    "events": group["contrast"].notna().sum(),
                    "recorders": group.loc[group["contrast"].notna(), "recorder"].nunique(),
                }
            )
        for (recorder, relative), group in combined.groupby(["recorder", "relative_minutes"]):
            for metric in CURVE_METRICS:
                curve_values[(recorder, metric, int(relative))].append(
                    group[f"{metric}_deviation"].mean()
                )
        for relative, group in combined.groupby("relative_minutes"):
            for metric in CURVE_METRICS:
                per_recorder = group.groupby("recorder")[f"{metric}_deviation"].mean()
                curve_values[("Pooled", metric, int(relative))].append(per_recorder.mean())
        if replicate % 100 == 0:
            print(f"  placebo replicates: {replicate}/{replicates}", flush=True)

    envelope_rows = []
    for (scope, metric, relative), values in curve_values.items():
        finite = np.asarray(values, dtype=float)
        finite = finite[np.isfinite(finite)]
        envelope_rows.append(
            {
                "scope": scope,
                "metric": metric,
                "relative_minutes": relative,
                "q025": np.quantile(finite, 0.025) if len(finite) else np.nan,
                "median": np.quantile(finite, 0.5) if len(finite) else np.nan,
                "q975": np.quantile(finite, 0.975) if len(finite) else np.nan,
                "valid_replicates": len(finite),
            }
        )
    return pd.DataFrame(assignments), pd.DataFrame(null_rows), pd.DataFrame(envelope_rows)


def plot_pooled_placebo(
    paths: pd.DataFrame,
    eligible_ids: set[str],
    envelope: pd.DataFrame,
    output: Path,
) -> None:
    real = paths.loc[paths["event_id"].isin(eligible_ids)].copy()
    labels = {
        "call_rate": "Call rate",
        "taxa_count": "Taxa count",
        "entropy": "Taxonomic entropy",
        "embedding_dispersion": "Embedding dispersion",
    }
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    for axis, (metric, label) in zip(axes.flat, labels.items()):
        observed = (
            real.groupby(["recorder", "relative_minutes"])[f"{metric}_deviation"]
            .mean()
            .groupby("relative_minutes")
            .mean()
        )
        noise = envelope.loc[
            (envelope["scope"] == "Pooled") & (envelope["metric"] == metric)
        ].sort_values("relative_minutes")
        x = noise["relative_minutes"] / 60
        axis.fill_between(x, noise["q025"], noise["q975"], color="#b8b8b8", alpha=0.5, label="95% placebo envelope")
        axis.plot(x, noise["median"], color="#777777", linewidth=1, linestyle=":")
        axis.plot(observed.index / 60, observed.values, color="#176b87", linewidth=1.8, label="observed")
        axis.axvline(0, color="#b22222", linestyle="--", linewidth=1.1)
        axis.axhline(0, color="#444444", linewidth=0.8)
        axis.set_ylabel(f"Deviation in {label}")
        axis.grid(alpha=0.2)
    axes[0, 0].legend(fontsize=8)
    axes[1, 0].set_xlabel("Hours from onset")
    axes[1, 1].set_xlabel("Hours from onset")
    fig.suptitle("Observed isolated events vs matched placebo-in-time noise floor")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def write_report(
    path: Path,
    model_results: pd.DataFrame,
    heterogeneity: pd.DataFrame,
    placebo_tests: pd.DataFrame,
    eligibility: pd.DataFrame,
    replicates: int,
) -> None:
    lines = [
        "# Pre-specified hypothesis and placebo report",
        "",
        "The contrast is mean residual activity in [0, 60) minutes minus mean residual activity in [-60, 0) minutes. Negative values support the pre-specified drop hypotheses.",
        "",
        "## Random-intercept results",
        "",
        "Recorder is modeled as a random intercept. The isolated-event analysis is primary; overlapping complete events are a robustness analysis.",
        "",
        "| Analysis | Hypothesis | Events | Recorders | Estimate | One-sided p | Holm p | Recorder variance | ICC |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in model_results.itertuples(index=False):
        lines.append(
            f"| {row.analysis} | {row.hypothesis} | {row.n_events} | {row.n_recorders} | "
            f"{row.estimate:.3f} | {row.one_sided_p_less:.4f} | {row.holm_p:.4f} | "
            f"{row.random_intercept_variance:.3f} | {row.icc:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Between-recorder heterogeneity for the primary isolated analysis",
            "",
            "| Hypothesis | Recorder | Events | Mean contrast |",
            "|---|---|---:|---:|",
        ]
    )
    primary_heterogeneity = heterogeneity.loc[
        heterogeneity["analysis"] == "primary_isolated"
    ]
    for row in primary_heterogeneity.itertuples(index=False):
        lines.append(
            f"| {row.hypothesis} | {row.recorder} | {row.events} | "
            f"{row.mean_contrast:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Placebo-in-time calibration",
            "",
            f"The empirical null uses {replicates:,} draws from all-component-free days at the same recorder and within 30 clock minutes. It requires complete, uncontaminated -3/+12-hour paths.",
            "",
            "| Hypothesis | Eligible real events | Recorders | Observed balanced contrast | Empirical one-sided p | Holm p |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in placebo_tests.itertuples(index=False):
        lines.append(
            f"| {row.hypothesis} | {row.events} | {row.recorders} | "
            f"{row.observed_recorder_balanced_contrast:.3f} | {row.empirical_p_less:.4f} | "
            f"{row.holm_p:.4f} |"
        )
    placebo_by_recorder = eligibility.groupby("recorder")["candidate_placebo_bins"].sum()
    unavailable = placebo_by_recorder.loc[placebo_by_recorder == 0].index.tolist()
    primary_count = int(eligibility["primary_isolated"].sum())
    modeled_count = int(
        model_results.loc[
            model_results["analysis"] == "primary_isolated", "n_events"
        ].min()
    )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            f"- Recorders without any eligible placebo bin: {', '.join(unavailable)}.",
            f"- The isolation rule selected {primary_count} events; {modeled_count} had complete residual contrasts. Missing time-of-day baselines removed the remainder from the model.",
            "- The mixed-model p-values use an asymptotic normal approximation with only six recorder groups; the empirical placebo p-value is preferred where available.",
            "- The placebo comparison is restricted to isolated real events that have a valid matched placebo pool, so it does not represent recorders lacking event-free days.",
            "- Overlap is defined using other human-presence onsets across the full -3/+12-hour window. Secondary vehicle, gunshot, and chainsaw components remain part of the direct-sound sensitivity question.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=root / "analysis" / "outputs")
    parser.add_argument("--output-dir", type=Path, default=root / "analysis" / "outputs" / "placebo")
    parser.add_argument("--hypotheses", type=Path, default=root / "analysis" / "hypotheses.json")
    parser.add_argument("--replicates", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20251002)
    parser.add_argument("--tod-tolerance-minutes", type=int, default=30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    specification = load_hypotheses(args.hypotheses)
    minutes = int(specification["bin_minutes"])
    relative_minutes = list(range(-180, 720 + minutes, minutes))

    paths = pd.read_csv(args.input_dir / "event_paths.csv", parse_dates=["onset", "bin_time"])
    bins = pd.read_csv(args.input_dir / "bin_descriptors.csv", parse_dates=["bin_time"])
    components = pd.read_csv(args.input_dir / "events.csv", parse_dates=["onset"])
    overlap = pd.read_csv(args.input_dir / "event_overlap_audit.csv")
    bins = add_residuals(bins)

    contrasts = event_contrasts(paths, specification)
    overlap_flags = overlap.set_index("event_id")
    isolated_ids = set(
        overlap_flags.loc[
            (overlap_flags["coverage_fraction"] == 1)
            & (overlap_flags["other_presence_onsets_in_window"] == 0)
        ].index
    )
    overlapping_ids = set(
        overlap_flags.loc[
            (overlap_flags["coverage_fraction"] == 1)
            & (overlap_flags["other_presence_onsets_in_window"] > 0)
        ].index
    )
    contrasts["analysis"] = np.select(
        [contrasts["event_id"].isin(isolated_ids), contrasts["event_id"].isin(overlapping_ids)],
        ["primary_isolated", "robustness_overlapping"],
        default="excluded_incomplete",
    )
    contrasts.to_csv(args.output_dir / "event_hypothesis_contrasts.csv", index=False)

    model_rows = []
    heterogeneity_rows = []
    for analysis in ["primary_isolated", "robustness_overlapping"]:
        for hypothesis in [item["name"] for item in specification["hypotheses"]]:
            subset = contrasts.loc[
                (contrasts["analysis"] == analysis)
                & (contrasts["hypothesis"] == hypothesis)
            ]
            result = fit_random_intercept(subset)
            result.update({"analysis": analysis, "hypothesis": hypothesis})
            model_rows.append(result)
            for recorder, group in subset.groupby("recorder"):
                values = group["contrast"].dropna()
                heterogeneity_rows.append(
                    {
                        "analysis": analysis,
                        "hypothesis": hypothesis,
                        "recorder": recorder,
                        "events": len(values),
                        "mean_contrast": values.mean(),
                        "sd_contrast": values.std(ddof=1) if len(values) > 1 else np.nan,
                    }
                )
    model_results = pd.DataFrame(model_rows)
    model_results["holm_p"] = model_results.groupby("analysis")["one_sided_p_less"].transform(holm_adjust)
    model_results.to_csv(args.output_dir / "mixed_effects_results.csv", index=False)
    pd.DataFrame(heterogeneity_rows).to_csv(
        args.output_dir / "between_recorder_heterogeneity.csv", index=False
    )

    real_events = components.loc[components["is_presence"]].copy()
    candidates, pools = candidate_placebos(
        bins,
        components,
        real_events,
        relative_minutes,
        args.tod_tolerance_minutes,
    )
    candidates.to_csv(args.output_dir / "placebo_candidates.csv", index=False)
    eligibility = real_events[["event_id", "recorder", "onset"]].copy()
    eligibility["candidate_placebo_bins"] = eligibility["event_id"].map(
        lambda value: len(pools.get(value, []))
    )
    eligibility["primary_isolated"] = eligibility["event_id"].isin(isolated_ids)
    eligibility.to_csv(args.output_dir / "placebo_eligibility.csv", index=False)

    eligible_isolated = real_events.loc[
        real_events["event_id"].isin(isolated_ids)
        & real_events["event_id"].map(lambda value: bool(pools.get(value)))
    ].copy()
    eligible_pools = {event_id: pools[event_id] for event_id in eligible_isolated["event_id"]}
    print(
        f"Running placebos for {len(eligible_isolated)} isolated events across "
        f"{eligible_isolated['recorder'].nunique()} recorders..."
    )
    assignments, null, envelope = run_placebos(
        bins,
        eligible_isolated,
        eligible_pools,
        specification,
        relative_minutes,
        args.replicates,
        args.seed,
    )
    assignments.to_csv(args.output_dir / "placebo_assignments.csv", index=False)
    null.to_csv(args.output_dir / "placebo_hypothesis_null.csv", index=False)
    envelope.to_csv(args.output_dir / "placebo_event_study_envelope.csv", index=False)

    observed_rows = []
    eligible_contrasts = contrasts.loc[
        contrasts["event_id"].isin(set(eligible_isolated["event_id"]))
    ]
    for hypothesis, group in eligible_contrasts.groupby("hypothesis"):
        observed = balanced_recorder_mean(group)
        null_values = null.loc[
            null["hypothesis"] == hypothesis, "recorder_balanced_contrast"
        ].dropna()
        observed_rows.append(
            {
                "hypothesis": hypothesis,
                "events": group["event_id"].nunique(),
                "recorders": group["recorder"].nunique(),
                "observed_recorder_balanced_contrast": observed,
                "null_q025": null_values.quantile(0.025),
                "null_median": null_values.quantile(0.5),
                "null_q975": null_values.quantile(0.975),
                "empirical_p_less": (1 + (null_values <= observed).sum())
                / (len(null_values) + 1),
            }
        )
    placebo_tests = pd.DataFrame(observed_rows)
    placebo_tests["holm_p"] = holm_adjust(placebo_tests["empirical_p_less"])
    placebo_tests.to_csv(args.output_dir / "placebo_hypothesis_tests.csv", index=False)

    plot_pooled_placebo(
        paths,
        set(eligible_isolated["event_id"]),
        envelope,
        args.output_dir / "placebo_event_study_pooled.png",
    )
    write_report(
        args.output_dir / "placebo_hypothesis_report.md",
        model_results,
        pd.DataFrame(heterogeneity_rows),
        placebo_tests,
        eligibility,
        args.replicates,
    )
    print(f"Done. Outputs: {args.output_dir}")


if __name__ == "__main__":
    main()
