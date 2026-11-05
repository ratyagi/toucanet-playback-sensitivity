#!/usr/bin/env python3
"""Build a pre-modeling event study and matched-control feasibility audit."""

from __future__ import annotations

import argparse
import ast
import math
import os
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/kwf-matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PRESENCE_TYPES = {"Human Presence on Trail", "Human Presence off Trail"}
WEATHER_COLUMNS = ["Temperature", "Windspeed", "Precipitation", "Humidity"]
WEATHER_SCALES = {
    "Temperature": 5.0,
    "Windspeed": 2.0,
    "Precipitation": 2.0,
    "Humidity": 15.0,
}
NPZ_NAME = re.compile(r"^(Audio_Moth_\d+)_(\d{8}_\d{6})\.npz$")


def parse_list(value: object) -> list:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    if isinstance(value, list):
        return value
    text = str(value).strip()
    if not text or text == "[]":
        return []
    try:
        result = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return []
    return result if isinstance(result, list) else [result]


def floor_timestamp(series: pd.Series, minutes: int) -> pd.Series:
    return series.dt.floor(f"{minutes}min")


def reconstruct_events(dataset: Path, chunksize: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Infer event onsets as clip timestamp minus the supplied relative time."""
    support: Counter = Counter()
    usecols = ["Recorder", "Timestamp", "Sim Type", "Sim Relative Time"]
    for chunk_number, chunk in enumerate(
        pd.read_csv(dataset, usecols=usecols, chunksize=chunksize), start=1
    ):
        timestamps = pd.to_datetime(chunk["Timestamp"], format="%Y%m%d_%H%M%S")
        for recorder, timestamp, types_raw, times_raw in zip(
            chunk["Recorder"], timestamps, chunk["Sim Type"], chunk["Sim Relative Time"]
        ):
            types = parse_list(types_raw)
            relative_times = parse_list(times_raw)
            for event_type, relative_time in zip(types, relative_times):
                try:
                    relative_time = float(relative_time)
                except (TypeError, ValueError):
                    continue
                onset = timestamp - pd.to_timedelta(relative_time, unit="s")
                support[(str(recorder), str(event_type), onset)] += 1
        print(f"  onset pass: chunk {chunk_number}", flush=True)

    records = [
        {"recorder": key[0], "event_type": key[1], "onset": key[2], "support_clips": count}
        for key, count in support.items()
    ]
    components = pd.DataFrame(records).sort_values(["recorder", "onset", "event_type"])
    components["is_presence"] = components["event_type"].isin(PRESENCE_TYPES)
    components["event_id"] = [f"event_{i:03d}" for i in range(1, len(components) + 1)]

    presence = components.loc[components["is_presence"]].copy().reset_index(drop=True)
    presence["event_date"] = presence["onset"].dt.date.astype(str)
    return components.reset_index(drop=True), presence


def shannon_entropy(species: list[str]) -> float:
    if not species:
        return float("nan")
    counts = np.fromiter(Counter(species).values(), dtype=float)
    probabilities = counts / counts.sum()
    return float(-(probabilities * np.log(probabilities)).sum())


def aggregate_descriptors(dataset: Path, minutes: int, chunksize: int) -> pd.DataFrame:
    """Aggregate species activity, weather, and recording coverage into bins."""
    usecols = ["Recorder", "Timestamp", "species", *WEATHER_COLUMNS]
    totals: dict[tuple[str, pd.Timestamp], dict] = {}

    for chunk_number, chunk in enumerate(
        pd.read_csv(dataset, usecols=usecols, chunksize=chunksize), start=1
    ):
        chunk["timestamp"] = pd.to_datetime(chunk["Timestamp"], format="%Y%m%d_%H%M%S")
        chunk["bin_time"] = floor_timestamp(chunk["timestamp"], minutes)
        chunk["species_list"] = chunk["species"].map(parse_list)
        for (recorder, bin_time), group in chunk.groupby(["Recorder", "bin_time"], sort=False):
            key = (str(recorder), pd.Timestamp(bin_time))
            accumulator = totals.setdefault(
                key,
                {
                    "clip_count": 0,
                    "species": [],
                    "weather_sum": {column: 0.0 for column in WEATHER_COLUMNS},
                    "weather_count": {column: 0 for column in WEATHER_COLUMNS},
                },
            )
            accumulator["clip_count"] += len(group)
            for values in group["species_list"]:
                accumulator["species"].extend(str(value) for value in values)
            for column in WEATHER_COLUMNS:
                values = pd.to_numeric(group[column], errors="coerce").dropna()
                accumulator["weather_sum"][column] += float(values.sum())
                accumulator["weather_count"][column] += int(values.size)
        print(f"  descriptor pass: chunk {chunk_number}", flush=True)

    rows = []
    for (recorder, bin_time), value in totals.items():
        recorded_minutes = value["clip_count"] * 3.0 / 60.0
        species = value["species"]
        row = {
            "recorder": recorder,
            "bin_time": bin_time,
            "clip_count": value["clip_count"],
            "recorded_minutes": recorded_minutes,
            "detection_count": len(species),
            "call_rate": len(species) / recorded_minutes if recorded_minutes else np.nan,
            "taxa_count": len(set(species)),
            "entropy": shannon_entropy(species),
        }
        for column in WEATHER_COLUMNS:
            count = value["weather_count"][column]
            row[column] = value["weather_sum"][column] / count if count else np.nan
        rows.append(row)
    result = pd.DataFrame(rows).sort_values(["recorder", "bin_time"]).reset_index(drop=True)
    result["date"] = result["bin_time"].dt.date.astype(str)
    result["tod_bin"] = result["bin_time"].dt.hour * 60 + result["bin_time"].dt.minute
    return result


def embedding_bin_metrics(
    embedding_dir: Path,
    minutes: int,
    cache_path: Path,
    reuse_cache: bool,
    workers: int,
    max_abs: float,
) -> pd.DataFrame:
    if reuse_cache and cache_path.exists():
        cached = pd.read_csv(cache_path, parse_dates=["bin_time"])
        print(f"Reusing embedding cache: {cache_path}")
        return cached

    accumulators: dict[tuple[str, pd.Timestamp], dict] = {}
    paths = sorted(embedding_dir.glob("*.npz"))

    def load_embedding(
        path: Path,
    ) -> tuple[str, pd.Timestamp, np.ndarray | None] | None:
        match = NPZ_NAME.match(path.name)
        if not match:
            return None
        recorder, timestamp_text = match.groups()
        timestamp = pd.to_datetime(timestamp_text, format="%Y%m%d_%H%M%S")
        bin_time = timestamp.floor(f"{minutes}min")
        with np.load(path, allow_pickle=False) as archive:
            with np.errstate(invalid="ignore", over="ignore"):
                vector = np.asarray(archive["segments"], dtype=np.float64).mean(axis=0)
        if not np.isfinite(vector).all() or float(np.max(np.abs(vector))) > max_abs:
            return recorder, bin_time, None
        return recorder, bin_time, vector

    invalid_embeddings = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        loaded = executor.map(load_embedding, paths, chunksize=128)
        for index, item in enumerate(loaded, start=1):
            if item is None:
                continue
            recorder, bin_time, vector = item
            if vector is None:
                invalid_embeddings += 1
                continue
            key = (recorder, bin_time)
            value = accumulators.get(key)
            if value is None:
                accumulators[key] = {
                    "count": 1,
                    "sum": vector.copy(),
                    "sum_sq_norm": float(vector @ vector),
                }
            else:
                value["count"] += 1
                value["sum"] += vector
                value["sum_sq_norm"] += float(vector @ vector)
            if index % 5000 == 0:
                print(f"Read {index:,}/{len(paths):,} embedding files", flush=True)
    if invalid_embeddings:
        print(
            f"Skipped {invalid_embeddings:,} non-finite or out-of-range embedding files",
            flush=True,
        )

    rows = []
    for (recorder, bin_time), value in accumulators.items():
        count = value["count"]
        centroid = value["sum"] / count
        dispersion = max(0.0, value["sum_sq_norm"] / count - float(centroid @ centroid))
        rows.append(
            {
                "recorder": recorder,
                "bin_time": bin_time,
                "embedding_count": count,
                "embedding_dispersion": dispersion,
            }
        )
    result = pd.DataFrame(rows).sort_values(["recorder", "bin_time"])
    result.to_csv(cache_path, index=False)
    pd.DataFrame(
        [
            {
                "files_examined": len(paths),
                "vectors_accepted": len(paths) - invalid_embeddings,
                "vectors_rejected": invalid_embeddings,
                "max_abs_threshold": max_abs,
            }
        ]
    ).to_csv(cache_path.with_name("embedding_qc.csv"), index=False)
    return result


def mark_event_contamination(
    bins: pd.DataFrame,
    components: pd.DataFrame,
    minutes: int,
    pre_buffer_minutes: int,
    post_buffer_minutes: int,
) -> pd.DataFrame:
    bins = bins.copy()
    bins["event_contaminated"] = False
    half_bin = pd.Timedelta(int(minutes), unit="min")
    for row in components.itertuples(index=False):
        # Presence labels span about +/-10 min; secondary components about 0-5 min.
        natural_pre = 10 if row.is_presence else 0
        natural_post = 10 if row.is_presence else 5
        start = row.onset - pd.Timedelta(
            int(max(pre_buffer_minutes, natural_pre)), unit="min"
        )
        end = row.onset + pd.Timedelta(
            int(max(post_buffer_minutes, natural_post)), unit="min"
        )
        mask = (
            (bins["recorder"] == row.recorder)
            & (bins["bin_time"] + half_bin > start)
            & (bins["bin_time"] <= end)
        )
        bins.loc[mask, "event_contaminated"] = True
    return bins


def build_event_paths(
    bins: pd.DataFrame,
    presence: pd.DataFrame,
    minutes: int,
    pre_hours: float,
    post_hours: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics = ["call_rate", "taxa_count", "entropy", "embedding_dispersion"]
    clean = bins.loc[~bins["event_contaminated"]].copy()
    baseline = clean.groupby(["recorder", "tod_bin"])[metrics].agg(["median", "count"])
    baseline.columns = [f"{metric}_baseline" if stat == "median" else f"{metric}_baseline_n" for metric, stat in baseline.columns]
    baseline = baseline.reset_index()

    indexed = bins.set_index(["recorder", "bin_time"], drop=False)
    pre_bins = int(round(pre_hours * 60 / minutes))
    post_bins = int(round(post_hours * 60 / minutes))
    records = []
    for event in presence.itertuples(index=False):
        event_bin = event.onset.floor(f"{minutes}min")
        for relative_bin in range(-pre_bins, post_bins + 1):
            bin_time = event_bin + pd.Timedelta(
                int(relative_bin * minutes), unit="min"
            )
            key = (event.recorder, bin_time)
            if key not in indexed.index:
                records.append(
                    {
                        "event_id": event.event_id,
                        "recorder": event.recorder,
                        "event_type": event.event_type,
                        "onset": event.onset,
                        "relative_minutes": relative_bin * minutes,
                        "bin_time": bin_time,
                        "observed": False,
                    }
                )
                continue
            observation = indexed.loc[key]
            if isinstance(observation, pd.DataFrame):
                observation = observation.iloc[0]
            record = {
                "event_id": event.event_id,
                "recorder": event.recorder,
                "event_type": event.event_type,
                "onset": event.onset,
                "relative_minutes": relative_bin * minutes,
                "bin_time": bin_time,
                "observed": True,
                "event_contaminated": bool(observation["event_contaminated"]),
            }
            for metric in metrics:
                record[metric] = observation.get(metric, np.nan)
            records.append(record)

    paths = pd.DataFrame(records)
    paths["tod_bin"] = paths["bin_time"].dt.hour * 60 + paths["bin_time"].dt.minute
    paths = paths.merge(baseline, on=["recorder", "tod_bin"], how="left")
    for metric in metrics:
        paths[f"{metric}_deviation"] = paths[metric] - paths[f"{metric}_baseline"]
    return paths, baseline


def summarize_paths(paths: pd.DataFrame) -> pd.DataFrame:
    metrics = ["call_rate", "taxa_count", "entropy", "embedding_dispersion"]
    rows = []
    for (recorder, relative_minutes), group in paths.groupby(["recorder", "relative_minutes"]):
        for metric in metrics:
            values = group[f"{metric}_deviation"].dropna()
            n = int(values.size)
            mean = float(values.mean()) if n else np.nan
            se = float(values.std(ddof=1) / np.sqrt(n)) if n > 1 else np.nan
            rows.append(
                {
                    "recorder": recorder,
                    "relative_minutes": relative_minutes,
                    "metric": metric,
                    "mean_deviation": mean,
                    "se": se,
                    "ci_low": mean - 1.96 * se if n > 1 else np.nan,
                    "ci_high": mean + 1.96 * se if n > 1 else np.nan,
                    "n_events": n,
                }
            )
    return pd.DataFrame(rows)


def make_plots(summary: pd.DataFrame, output_dir: Path) -> None:
    labels = {
        "call_rate": "Call rate\n(detections/min)",
        "taxa_count": "Taxa count",
        "entropy": "Taxonomic entropy",
        "embedding_dispersion": "Embedding dispersion",
    }
    for recorder, recorder_data in summary.groupby("recorder"):
        fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
        for axis, (metric, label) in zip(axes.flat, labels.items()):
            data = recorder_data.loc[recorder_data["metric"] == metric].sort_values("relative_minutes")
            x = data["relative_minutes"] / 60.0
            axis.axvline(0, color="#b22222", linestyle="--", linewidth=1.2, label="onset")
            axis.axhline(0, color="#555555", linewidth=0.8)
            axis.plot(x, data["mean_deviation"], color="#176b87", linewidth=1.7)
            axis.fill_between(x, data["ci_low"], data["ci_high"], color="#64ccc5", alpha=0.3)
            axis.set_ylabel(f"Deviation in {label}")
            axis.grid(alpha=0.2)
        axes[1, 0].set_xlabel("Hours from presence onset")
        axes[1, 1].set_xlabel("Hours from presence onset")
        fig.suptitle(f"Event study: {recorder}")
        fig.tight_layout()
        fig.savefig(output_dir / f"event_study_{recorder}.png", dpi=180)
        plt.close(fig)


def weather_distance(event_row: pd.Series, candidate_row: pd.Series) -> float:
    pieces = []
    for column in WEATHER_COLUMNS:
        left, right = event_row.get(column), candidate_row.get(column)
        if pd.notna(left) and pd.notna(right):
            pieces.append(((float(left) - float(right)) / WEATHER_SCALES[column]) ** 2)
    return float(np.sqrt(sum(pieces))) if pieces else np.nan


def matched_control_audit(
    bins: pd.DataFrame, presence: pd.DataFrame, minutes: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    presence_days = presence.groupby("recorder")["event_date"].agg(set).to_dict()
    all_days = bins.groupby("recorder")["date"].agg(lambda values: set(values)).to_dict()
    event_lookup = bins.set_index(["recorder", "bin_time"], drop=False)
    candidates = []

    for event in presence.itertuples(index=False):
        event_bin = event.onset.floor(f"{minutes}min")
        key = (event.recorder, event_bin)
        if key not in event_lookup.index:
            continue
        event_row = event_lookup.loc[key]
        if isinstance(event_row, pd.DataFrame):
            event_row = event_row.iloc[0]
        valid_days = all_days.get(event.recorder, set()) - presence_days.get(event.recorder, set())
        pool = bins.loc[
            (bins["recorder"] == event.recorder)
            & (bins["tod_bin"] == event_row["tod_bin"])
            & (bins["date"].isin(valid_days))
            & (~bins["event_contaminated"])
        ]
        for _, candidate in pool.iterrows():
            candidates.append(
                {
                    "event_id": event.event_id,
                    "recorder": event.recorder,
                    "onset": event.onset,
                    "event_bin": event_bin,
                    "control_bin": candidate["bin_time"],
                    "control_date": candidate["date"],
                    "weather_distance": weather_distance(event_row, candidate),
                }
            )

    candidate_frame = pd.DataFrame(candidates)
    if candidate_frame.empty:
        matched = candidate_frame.copy()
    else:
        candidate_frame = candidate_frame.sort_values(
            ["event_id", "weather_distance", "control_bin"], na_position="last"
        )
        candidate_frame["weather_rank"] = candidate_frame.groupby("event_id").cumcount() + 1
        matched = candidate_frame.loc[candidate_frame["weather_rank"] == 1].copy()

    matched_ids = set(matched.get("event_id", []))
    rows = []
    for recorder, events in presence.groupby("recorder"):
        recorder_days = all_days.get(recorder, set())
        no_presence_days = recorder_days - presence_days.get(recorder, set())
        rows.append(
            {
                "recorder": recorder,
                "presence_events": len(events),
                "matched_events": sum(event_id in matched_ids for event_id in events["event_id"]),
                "recorded_days": len(recorder_days),
                "presence_free_days": len(no_presence_days),
                "presence_free_day_list": ";".join(sorted(no_presence_days)),
            }
        )
    return candidate_frame, matched, pd.DataFrame(rows)


def overlap_audit(
    paths: pd.DataFrame, presence: pd.DataFrame, components: pd.DataFrame
) -> pd.DataFrame:
    rows = []
    for event in presence.itertuples(index=False):
        path = paths.loc[paths["event_id"] == event.event_id]
        other = components.loc[
            (components["recorder"] == event.recorder)
            & (components["onset"] != event.onset)
            & (components["onset"] >= path["bin_time"].min())
            & (components["onset"] <= path["bin_time"].max())
        ]
        rows.append(
            {
                "event_id": event.event_id,
                "recorder": event.recorder,
                "onset": event.onset,
                "observed_bins": int(path["observed"].sum()),
                "requested_bins": len(path),
                "coverage_fraction": float(path["observed"].mean()),
                "other_component_onsets_in_window": len(other),
                "other_presence_onsets_in_window": int(other["is_presence"].sum()),
            }
        )
    return pd.DataFrame(rows)


def write_report(
    output_path: Path,
    components: pd.DataFrame,
    presence: pd.DataFrame,
    bins: pd.DataFrame,
    matchability: pd.DataFrame,
    overlap: pd.DataFrame,
    skip_embeddings: bool,
) -> None:
    total_clips = int(bins["clip_count"].sum())
    lines = [
        "# Event-study audit report",
        "",
        f"- Source clips aggregated: {total_clips:,}",
        f"- Recorders: {bins['recorder'].nunique()}",
        f"- Human-presence onsets: {len(presence)}",
        f"- All simulated component onsets: {len(components)}",
        f"- Events with another presence onset inside the requested window: "
        f"{int((overlap['other_presence_onsets_in_window'] > 0).sum())}/{len(overlap)}",
        f"- Events with incomplete requested-window coverage: "
        f"{int((overlap['coverage_fraction'] < 1).sum())}/{len(overlap)}",
        "",
        "## Strict matched-control feasibility",
        "",
        "A strict control is from the same recorder and time-of-day bin on a day with no recorded human-presence event.",
        "",
        "| Recorder | Events | Matched | Recorded days | Presence-free days |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in matchability.itertuples(index=False):
        lines.append(
            f"| {row.recorder} | {row.presence_events} | {row.matched_events} | "
            f"{row.recorded_days} | {row.presence_free_days} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation cautions",
            "",
            "- The deployment spans only a few days. Long post-event paths frequently overlap later staged events.",
            "- Recorder identity is used as the grouping unit; the directory does not establish that recorders are independent geographic sites.",
            "- Weather is hourly, so weather matching is coarse relative to the acoustic bins.",
            "- Baselines use clean bins at the same recorder and clock time. They may come from a day containing an event at another time; strict day-level matching is reported separately.",
            "- Confidence intervals describe variation across the small set of staged events and should be treated as exploratory.",
        ]
    )
    if skip_embeddings:
        lines.append("- Embedding dispersion was skipped for this run.")
    else:
        qc_path = output_path.with_name("embedding_qc.csv")
        if qc_path.exists():
            qc = pd.read_csv(qc_path).iloc[0]
            lines.append(
                f"- Embedding QC accepted {int(qc['vectors_accepted']):,}/"
                f"{int(qc['files_examined']):,} vectors and rejected "
                f"{int(qc['vectors_rejected']):,} non-finite or out-of-range vectors."
            )
        lines.append(
            "- Embedding dispersion is conditional on species-positive clips; "
            "inspect embedding coverage before interpreting it."
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=root / "bioacoustics_dataset.csv")
    parser.add_argument("--embedding-dir", type=Path, default=root / "raw_segments_per_clip")
    parser.add_argument("--output-dir", type=Path, default=root / "analysis" / "outputs")
    parser.add_argument("--bin-minutes", type=int, default=15)
    parser.add_argument("--pre-hours", type=float, default=3.0)
    parser.add_argument("--post-hours", type=float, default=12.0)
    parser.add_argument("--baseline-pre-buffer-minutes", type=int, default=10)
    parser.add_argument("--baseline-post-buffer-minutes", type=int, default=60)
    parser.add_argument("--chunksize", type=int, default=100_000)
    parser.add_argument("--skip-embeddings", action="store_true")
    parser.add_argument("--embedding-workers", type=int, default=8)
    parser.add_argument("--embedding-max-abs", type=float, default=100.0)
    parser.add_argument("--no-reuse-embedding-cache", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    print("Reconstructing event onsets...")
    components, presence = reconstruct_events(args.dataset, args.chunksize)
    components.to_csv(args.output_dir / "events.csv", index=False)

    print("Aggregating clip descriptors...")
    bins = aggregate_descriptors(args.dataset, args.bin_minutes, args.chunksize)
    if args.skip_embeddings:
        bins["embedding_count"] = np.nan
        bins["embedding_dispersion"] = np.nan
    else:
        embedding_cache = args.output_dir / "embedding_bin_metrics.csv"
        embedding_metrics = embedding_bin_metrics(
            args.embedding_dir,
            args.bin_minutes,
            embedding_cache,
            reuse_cache=not args.no_reuse_embedding_cache,
            workers=args.embedding_workers,
            max_abs=args.embedding_max_abs,
        )
        bins = bins.merge(embedding_metrics, on=["recorder", "bin_time"], how="left")
        bins["embedding_count"] = bins["embedding_count"].fillna(0).astype(int)
    bins["embedding_coverage"] = bins["embedding_count"] / bins["clip_count"]
    bins = mark_event_contamination(
        bins,
        components,
        args.bin_minutes,
        args.baseline_pre_buffer_minutes,
        args.baseline_post_buffer_minutes,
    )
    bins.to_csv(args.output_dir / "bin_descriptors.csv", index=False)

    print("Building event paths and plots...")
    paths, _ = build_event_paths(
        bins, presence, args.bin_minutes, args.pre_hours, args.post_hours
    )
    summary = summarize_paths(paths)
    paths.to_csv(args.output_dir / "event_paths.csv", index=False)
    summary.to_csv(args.output_dir / "event_study_summary.csv", index=False)
    make_plots(summary, args.output_dir)

    print("Auditing matched controls and overlap...")
    candidates, matched, matchability = matched_control_audit(
        bins, presence, args.bin_minutes
    )
    candidates.to_csv(args.output_dir / "matched_control_candidates.csv", index=False)
    matched.to_csv(args.output_dir / "matched_controls.csv", index=False)
    matchability.to_csv(args.output_dir / "matchability_by_recorder.csv", index=False)
    overlap = overlap_audit(paths, presence, components)
    overlap.to_csv(args.output_dir / "event_overlap_audit.csv", index=False)
    write_report(
        args.output_dir / "audit_report.md",
        components,
        presence,
        bins,
        matchability,
        overlap,
        args.skip_embeddings,
    )
    print(f"Done. Outputs: {args.output_dir}")


if __name__ == "__main__":
    main()
