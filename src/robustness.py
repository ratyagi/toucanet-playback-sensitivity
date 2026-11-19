#!/usr/bin/env python3
"""Exploratory robustness checks for the primary test (Week 9). None can change the verdict.

Specifications are fixed in DEVIATIONS.md ("Week 4 addendum" and "Week 6 addendum"), written
before any of this was run. The lead's functions (src/lead/) are imported unchanged.

  A. Negative binomial count model (recorded-minutes offset, recorder fixed effects,
     time-of-day harmonics, standard errors clustered by recorder and date).
  B. Leave-own-day-out baseline (the event's own calendar day is left out of its baseline).
  C. Leave-one-recorder-out refit of the primary model.

Run src/run_variants.py first (it writes the event contrasts and fixes the event population).

  python src/robustness.py --dataset ..\\bioacoustics_dataset.csv
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "lead"))
sys.path.insert(0, str(REPO / "src"))

ALPHA = 0.05
HYPOTHESIS = "primary_call_rate"
ANALYSIS = "primary_isolated"
WINDOWS = {"v1_original": (0, 60), "v2_post_playback": (15, 60)}
PRE_WINDOW = (-60, 0)
HARMONICS = (1440, 720)  # minutes: 24 h and 12 h cycles


# ---------------------------------------------------------------- A. count model

def design_matrix(data: pd.DataFrame) -> pd.DataFrame:
    """Recorder fixed effects, time-of-day harmonics, pre and post indicators."""
    x = pd.get_dummies(data["recorder"], prefix="rec", drop_first=True, dtype=float)
    for period in HARMONICS:
        angle = 2 * np.pi * data["tod_bin"].to_numpy() / period
        x[f"sin_{period}"] = np.sin(angle)
        x[f"cos_{period}"] = np.cos(angle)
    x["pre"] = (data["role"] == "pre").astype(float).to_numpy()
    x["post"] = (data["role"] == "post").astype(float).to_numpy()
    return sm.add_constant(x, has_constant="add")


def _cluster_effects(model, start, x, groups) -> dict:
    """Refit with the given clusters (same estimate, new covariance) and return the effects on the log scale."""
    pos, pre = list(x.columns).index("post"), list(x.columns).index("pre")
    f = model.fit(start_params=start, disp=0, maxiter=300, cov_type="cluster", cov_kwds={"groups": groups})
    b, v = np.asarray(f.params), np.asarray(f.cov_params())
    with np.errstate(invalid="ignore"):
        return {"post": b[pos], "se_post": np.sqrt(v[pos, pos]), "pre": b[pre], "se_pre": np.sqrt(v[pre, pre]),
                "diff": b[pos] - b[pre], "se_diff": np.sqrt(v[pos, pos] + v[pre, pre] - 2 * v[pos, pre]),
                "alpha": b[-1]}


def _valid(se) -> bool:
    return bool(np.isfinite(se) and se > 0)


def fit_count_model(data: pd.DataFrame) -> dict:
    """Negative binomial (NB2), log link, offset log(recorded minutes), dispersion by ML.

    data columns: recorder, date, tod_bin (minutes), recorded_minutes, count, role (baseline, pre, post).
    Specified effect: post-window rate ratio against clean baseline bins.
    Primary standard error: clustered by recorder-day (each recorder on each date is one cluster).
    Also reported: the literal two-way clustering by recorder and by date, which can be not estimable.
    Added after the first real run (see DEVIATIONS.md): the pre-window rate ratio and the post over pre
    rate ratio, the count-model counterpart of the primary pre/post contrast.
    A row marked not estimable is never retried with another specification.
    """
    d = data.loc[data["recorded_minutes"] > 0].reset_index(drop=True)
    nan = np.nan
    out = {"rows": len(d), "event_bins_pre": int((d["role"] == "pre").sum()),
           "event_bins_post": int((d["role"] == "post").sum()), "estimable": False, "converged": False,
           "recorder_days": 0, "rate_ratio": nan, "ci_low": nan, "ci_high": nan, "two_sided_p": nan,
           "standard_error_log": nan, "standard_error_log_two_way": nan, "two_sided_p_two_way": nan,
           "detectable_rate_ratio_low": nan, "detectable_rate_ratio_high": nan, "alpha_dispersion": nan,
           "pre_rate_ratio": nan, "pre_p": nan,
           "post_over_pre_rate_ratio": nan, "post_over_pre_ci_low": nan, "post_over_pre_ci_high": nan,
           "post_over_pre_p": nan, "post_over_pre_p_two_way": nan, "problem": ""}
    if out["event_bins_post"] == 0 or out["event_bins_pre"] == 0:
        out["problem"] = "no event bins in a window"
        return out
    x = design_matrix(d)
    recorder_day = pd.factorize(d["recorder"] + "|" + d["date"].astype(str))[0]
    two_way = np.column_stack([pd.factorize(d["recorder"])[0], pd.factorize(d["date"])[0]])
    out["recorder_days"] = int(recorder_day.max() + 1)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = sm.NegativeBinomial(d["count"].to_numpy(float), x, offset=np.log(d["recorded_minutes"].to_numpy(float)))
            plain = model.fit(disp=0, maxiter=300)
            main = _cluster_effects(model, plain.params, x, recorder_day)
            try:
                alt = _cluster_effects(model, plain.params, x, two_way)
            except Exception:
                alt = None
    except Exception as error:
        out["problem"] = f"fit failed: {type(error).__name__}"
        return out
    out["converged"] = bool(plain.mle_retvals.get("converged", False))
    out["alpha_dispersion"] = float(main["alpha"])
    if not out["converged"]:
        out["problem"] = "did not converge"
        return out
    if not _valid(main["se_post"]):
        out["problem"] = "no valid clustered standard error"
        return out
    beta, se = float(main["post"]), float(main["se_post"])
    out.update(estimable=True, rate_ratio=float(np.exp(beta)), ci_low=float(np.exp(beta - 1.96 * se)),
               ci_high=float(np.exp(beta + 1.96 * se)), standard_error_log=se,
               two_sided_p=float(2 * norm.sf(abs(beta / se))),
               detectable_rate_ratio_low=float(np.exp(-1.96 * se)), detectable_rate_ratio_high=float(np.exp(1.96 * se)),
               pre_rate_ratio=float(np.exp(main["pre"])))
    if _valid(main["se_pre"]):
        out["pre_p"] = float(2 * norm.sf(abs(main["pre"] / main["se_pre"])))
    if _valid(main["se_diff"]):
        out.update(post_over_pre_rate_ratio=float(np.exp(main["diff"])),
                   post_over_pre_ci_low=float(np.exp(main["diff"] - 1.96 * main["se_diff"])),
                   post_over_pre_ci_high=float(np.exp(main["diff"] + 1.96 * main["se_diff"])),
                   post_over_pre_p=float(2 * norm.sf(abs(main["diff"] / main["se_diff"]))))
    if alt is not None and _valid(alt["se_post"]):
        out["standard_error_log_two_way"] = float(alt["se_post"])
        out["two_sided_p_two_way"] = float(2 * norm.sf(abs(alt["post"] / alt["se_post"])))
    if alt is not None and _valid(alt["se_diff"]):
        out["post_over_pre_p_two_way"] = float(2 * norm.sf(abs(alt["diff"] / alt["se_diff"])))
    return out


def count_model_data(bins: pd.DataFrame, paths: pd.DataFrame, event_ids: set, window: tuple) -> pd.DataFrame:
    """Event bins (pre and post windows of the given events) plus all clean bins as baseline.

    A bin in an event window keeps its window role, so no bin appears twice. Bins in the gap
    between the two windows are left out.
    """
    cols = ["recorder", "bin_time", "tod_bin", "recorded_minutes", "detection_count"]
    b = bins[cols + ["event_contaminated"]].copy()
    b["date"] = b["bin_time"].dt.date.astype(str)
    p = paths.loc[paths["event_id"].isin(event_ids) & paths["observed"], ["recorder", "bin_time", "relative_minutes"]]
    rel = p["relative_minutes"]
    p = p.assign(role=np.select([(rel >= PRE_WINDOW[0]) & (rel < PRE_WINDOW[1]), (rel >= window[0]) & (rel < window[1])],
                                ["pre", "post"], default="")).query("role != ''")
    ev = b.merge(p[["recorder", "bin_time", "role"]], on=["recorder", "bin_time"], how="inner")
    clean = b.loc[~b["event_contaminated"]].merge(ev[["recorder", "bin_time"]], on=["recorder", "bin_time"], how="left", indicator=True)
    clean = clean.loc[clean["_merge"] == "left_only"].drop(columns="_merge").assign(role="baseline")
    out = pd.concat([ev, clean], ignore_index=True).rename(columns={"detection_count": "count"})
    return out[["recorder", "date", "tod_bin", "recorded_minutes", "count", "role"]]


# ---------------------------------------------------------------- B. leave-own-day-out baseline

def own_day_deviations(paths: pd.DataFrame, bins: pd.DataFrame, metrics=("call_rate", "taxa_count")) -> pd.DataFrame:
    """Replace each path's deviation by value minus a baseline that leaves out the bin's own calendar date.

    Baseline: median of clean bins with the same recorder and time of day on other dates.
    A bin with no such clean bin gets no baseline (dropped, as in the reference method).
    """
    clean = bins.loc[~bins["event_contaminated"]].assign(date=lambda t: t["bin_time"].dt.date)
    lookup = {key: g for key, g in clean.groupby(["recorder", "tod_bin"])}
    paths = paths.copy()
    dates = paths["bin_time"].dt.date
    for metric in metrics:
        baseline = np.full(len(paths), np.nan)
        for i, (rec, tod, date) in enumerate(zip(paths["recorder"], paths["tod_bin"], dates)):
            g = lookup.get((rec, tod))
            if g is not None:
                values = g.loc[g["date"] != date, metric].dropna()
                if len(values):
                    baseline[i] = values.median()
        paths[f"{metric}_baseline"] = baseline
        paths[f"{metric}_deviation"] = paths[metric] - baseline
    return paths


# ---------------------------------------------------------------- C. leave-one-recorder-out

def leave_one_recorder_out(contrasts: pd.DataFrame, fit) -> pd.DataFrame:
    """Refit the primary model with each recorder omitted. `fit` is the lead's fit_random_intercept."""
    def row(label, subset, ref):
        r = fit(subset)
        p = float(2 * norm.sf(abs(r["z"]))) if np.isfinite(r["z"]) else np.nan
        flip = bool(ref is not None and np.isfinite(r["estimate"]) and np.sign(r["estimate"]) != np.sign(ref["estimate"]))
        cross = bool(ref is not None and np.isfinite(p) and (p < ALPHA) != (ref["p"] < ALPHA))
        return {"omitted": label, "n_events": r["n_events"], "n_recorders": r["n_recorders"], "estimate": r["estimate"],
                "standard_error": r["standard_error"], "two_sided_p": p, "estimable": bool(np.isfinite(p)),
                "sign_flip": flip, "p_crosses_0.05": cross, "influential": flip or cross, "_p": p}
    full = row("none", contrasts, None)
    ref = {"estimate": full["estimate"], "p": full["_p"]}
    rows = [full] + [row(rec, contrasts.loc[contrasts["recorder"] != rec], ref) for rec in sorted(contrasts["recorder"].dropna().unique())]
    return pd.DataFrame(rows).drop(columns="_p")


# ---------------------------------------------------------------- run

def main() -> None:
    import event_study as es  # noqa: E402
    import placebo_hypothesis_analysis as pha  # noqa: E402
    import run_variants as rv  # noqa: E402

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--events", type=Path, default=REPO / "reference" / "events.csv")
    parser.add_argument("--configs", type=Path, default=REPO / "configs" / "variants")
    parser.add_argument("--work-dir", type=Path, default=REPO / "results" / "intermediate" / "variants")
    parser.add_argument("--tables-dir", type=Path, default=REPO / "results" / "tables")
    args = parser.parse_args()

    components, presence = rv.load_events(args.events)
    bins = rv.build_bins(args.dataset, 15, components)
    paths, _ = es.build_event_paths(bins, presence, 15, 3.0, 12.0)
    specs = {n: json.loads((args.configs / f"{n}.json").read_text(encoding="utf-8")) for n in WINDOWS}
    v1 = pd.read_csv(args.work_dir / "v1_original" / "event_contrasts.csv")
    population = v1.drop_duplicates("event_id").set_index("event_id")["analysis"]
    primary_ids = set(v1.loc[(v1["analysis"] == ANALYSIS) & (v1["hypothesis"] == HYPOTHESIS) & v1["contrast"].notna(), "event_id"])
    print(f"{len(primary_ids)} primary isolated events with a usable variant 1 contrast", flush=True)

    # A. count model
    count_rows = []
    for name, window in WINDOWS.items():
        fit = fit_count_model(count_model_data(bins, paths, primary_ids, window))
        count_rows.append({"variant": name, "window": f"{window[0]}-{window[1]}", **fit})
        print(f"   count model {name}: " + (f"post vs baseline RR {fit['rate_ratio']:.2f} (p = {fit['two_sided_p']:.3f}, two-way {fit['two_sided_p_two_way']:.3f}); pre vs baseline {fit['pre_rate_ratio']:.2f}; post vs pre {fit['post_over_pre_rate_ratio']:.2f} (p = {fit['post_over_pre_p']:.3f}, two-way {fit['post_over_pre_p_two_way']:.3f})" if fit["estimable"] else f"not estimable ({fit['problem']})"), flush=True)
    pd.DataFrame(count_rows).to_csv(args.tables_dir / "robustness_count_model.csv", index=False)

    # B. leave-own-day-out baseline
    own_paths = own_day_deviations(paths, bins)
    day_rows = []
    for name in WINDOWS:
        contrasts = pha.event_contrasts(own_paths, specs[name])
        contrasts["analysis"] = contrasts["event_id"].map(population)
        for label, source in (("leave_own_day_out", contrasts), ("reference_baseline", pd.read_csv(args.work_dir / name / "event_contrasts.csv"))):
            sub = source.loc[(source["analysis"] == ANALYSIS) & (source["hypothesis"] == HYPOTHESIS)]
            r = pha.fit_random_intercept(sub)
            p = float(2 * norm.sf(abs(r["z"]))) if np.isfinite(r["z"]) else np.nan
            day_rows.append({"variant": name, "baseline": label, "n_events": r["n_events"], "n_recorders": r["n_recorders"],
                             "estimate": r["estimate"], "standard_error": r["standard_error"], "two_sided_p": p,
                             "converged": r["converged"], "fit_method": r["fit_method"]})
    pd.DataFrame(day_rows).to_csv(args.tables_dir / "robustness_leave_own_day.csv", index=False)

    # C. leave-one-recorder-out
    loro = []
    for name in WINDOWS:
        c = pd.read_csv(args.work_dir / name / "event_contrasts.csv")
        c = c.loc[(c["analysis"] == ANALYSIS) & (c["hypothesis"] == HYPOTHESIS)]
        loro.append(leave_one_recorder_out(c, pha.fit_random_intercept).assign(variant=name))
    loro = pd.concat(loro, ignore_index=True)
    loro.to_csv(args.tables_dir / "robustness_leave_one_recorder.csv", index=False)
    print(pd.DataFrame(day_rows).to_string(index=False))
    print(loro.to_string(index=False))


if __name__ == "__main__":
    main()
