#!/usr/bin/env python3
"""Apply the pre-registered decision rules (PREREGISTRATION.md, "Interpretation criteria").

Reads only existing tables, so nothing heavy has to be rerun:
  results/tables/variant_results.csv          (Week 2 models)
  results/tables/variant_recorder_results.csv (Week 2 per-recorder contrasts)
  results/tables/placebo_results.csv          (Week 3 placebo calibration)

Writes:
  results/tables/decision_summary.csv   one row per variant plus an OVERALL row
  results/tables/recorder_coverage.csv  per-recorder contrasts for the primary test

Rules, fixed in advance:
  Gate        variant 1, primary isolated, call rate: two-sided p < 0.05.
              If it fails the verdict is inconclusive and the other variants are descriptive.
  Comparison  ratio = estimate / variant 1 estimate.
              consistent: same sign and ratio >= 0.5
              substantially_smaller: 0 < ratio < 0.5
              reversed: opposite sign
  Biological response  all five variants consistent AND the variant 2 estimate lies outside
              the 95% strict-pool placebo range (where a placebo exists).
  Direct contamination at least two of the five are substantially smaller or reversed.
  Anything else: mixed, inconclusive.

  python src/decision.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
TABLES = REPO / "results" / "tables"

GATE_VARIANT = "v1_original"
COMPARED = ["v2_post_playback", "v2b_post_playback_5min", "v3_buffered",
            "v4a_original_excluded", "v4b_post_playback_excluded"]
PLACEBO_REFERENCE = "v2_post_playback"
ALPHA = 0.05
MIN_RATIO = 0.5
MIN_SMALLER_FOR_CONTAMINATION = 2
HYPOTHESES_SOURCE = "DRAFT (configs/hypotheses_draft.json, lead's hypotheses.json not received)"
ANALYSIS = "primary_isolated"
HYPOTHESIS = "primary_call_rate"


def classify_ratio(estimate: float, reference: float) -> str:
    """Compare one variant with variant 1."""
    if not np.isfinite(estimate) or not np.isfinite(reference) or reference == 0:
        return "not_evaluable"
    ratio = estimate / reference
    if ratio < 0:
        return "reversed"
    if ratio >= MIN_RATIO:
        return "consistent"
    return "substantially_smaller"


def decide(model: pd.DataFrame, placebo: pd.DataFrame) -> pd.DataFrame:
    """model: one row per variant (estimate, standard_error, two_sided_p, n_events, ...).
    placebo: one row per variant (null_q025, null_q975, observed, p_two_sided, events), may be empty."""
    model = model.set_index("variant")
    placebo = placebo.set_index("variant") if len(placebo) else placebo
    ref = model.loc[GATE_VARIANT]
    gate_passed = bool(ref["two_sided_p"] < ALPHA)

    rows = []
    for variant in [GATE_VARIANT, *COMPARED]:
        if variant not in model.index:
            raise SystemExit(f"Missing variant in model table: {variant}")
        m = model.loc[variant]
        row = {
            "variant": variant,
            "n_events": int(m["n_events"]),
            "n_recorders": int(m["n_recorders"]),
            "estimate": m["estimate"],
            "standard_error": m["standard_error"],
            "two_sided_p": m["two_sided_p"],
            "minimum_detectable_effect": m["minimum_detectable_effect"],
            "ratio_to_variant1": np.nan if variant == GATE_VARIANT else m["estimate"] / ref["estimate"],
            "comparison": "gate_variant" if variant == GATE_VARIANT else classify_ratio(m["estimate"], ref["estimate"]),
        }
        if not gate_passed and variant != GATE_VARIANT:
            row["comparison"] = "descriptive_only"
        if len(placebo) and variant in placebo.index:
            p = placebo.loc[variant]
            row.update(placebo_events=int(p["events"]), placebo_observed=p["observed"],
                       placebo_q025=p["null_q025"], placebo_q975=p["null_q975"],
                       placebo_p_two_sided=p["p_two_sided"])
        else:
            row.update(placebo_events=0, placebo_observed=np.nan, placebo_q025=np.nan,
                       placebo_q975=np.nan, placebo_p_two_sided=np.nan)
        rows.append(row)
    table = pd.DataFrame(rows)

    if not gate_passed:
        verdict = "inconclusive_gate_not_passed"
        reason = (f"Variant 1 primary isolated call rate: two-sided p = {ref['two_sided_p']:.3f} "
                  f"(needs < {ALPHA}). No detectable original effect to attribute; "
                  f"other variants are descriptive.")
    else:
        compared = table[table["variant"].isin(COMPARED)]
        n_consistent = int((compared["comparison"] == "consistent").sum())
        n_bad = int(compared["comparison"].isin(["substantially_smaller", "reversed"]).sum())
        pr = table.loc[table["variant"] == PLACEBO_REFERENCE].iloc[0]
        has_placebo = bool(np.isfinite(pr["placebo_q025"]))
        outside = has_placebo and not (pr["placebo_q025"] <= pr["estimate"] <= pr["placebo_q975"])
        if n_consistent == len(COMPARED) and (outside or not has_placebo):
            verdict = "biological_response"
            reason = "All five variants consistent with variant 1" + (
                "; variant 2 outside the 95% placebo range." if outside
                else "; no placebo exists for variant 2, so this rests on consistency alone.")
        elif n_bad >= MIN_SMALLER_FOR_CONTAMINATION:
            verdict = "direct_contamination"
            reason = f"{n_bad} of {len(COMPARED)} variants are substantially smaller or reversed."
        else:
            verdict = "mixed_inconclusive"
            reason = (f"{n_consistent} consistent, {n_bad} smaller or reversed; "
                      "pattern fits neither pre-registered interpretation.")
    overall = {c: np.nan for c in table.columns}
    overall.update(variant="OVERALL", comparison=verdict)
    table = pd.concat([table, pd.DataFrame([overall])], ignore_index=True)
    table["hypotheses_source"] = HYPOTHESES_SOURCE
    table["note"] = ""
    table.loc[table["variant"] == "OVERALL", "note"] = reason
    table.attrs["verdict"] = verdict
    table.attrs["reason"] = reason
    return table


def recorder_coverage(recorders: pd.DataFrame) -> pd.DataFrame:
    """Per-recorder contrasts for the primary test, one column group per variant."""
    r = recorders[(recorders["method"] == "primary") & (recorders["analysis"] == ANALYSIS)
                  & (recorders["hypothesis"] == HYPOTHESIS)]
    events = r.pivot(index="recorder", columns="variant", values="events").add_prefix("events_")
    contrast = r.pivot(index="recorder", columns="variant", values="mean_contrast").add_prefix("contrast_")
    return events.join(contrast).reset_index()


def main() -> None:
    results = pd.read_csv(TABLES / "variant_results.csv")
    model = results[(results["method"] == "primary") & (results["analysis"] == ANALYSIS)
                    & (results["hypothesis"] == HYPOTHESIS)]
    placebo = pd.read_csv(TABLES / "placebo_results.csv")
    placebo = placebo[(placebo["pool"] == "strict") & (placebo["analysis"] == ANALYSIS)
                      & (placebo["hypothesis"] == HYPOTHESIS)]
    table = decide(model, placebo)
    table.to_csv(TABLES / "decision_summary.csv", index=False)
    recorder_coverage(pd.read_csv(TABLES / "variant_recorder_results.csv")).to_csv(
        TABLES / "recorder_coverage.csv", index=False)
    print(f"Hypotheses: {HYPOTHESES_SOURCE}")
    print(f"Verdict: {table.attrs['verdict']}")
    print(table.attrs["reason"])
    print(table[["variant", "n_events", "estimate", "two_sided_p", "minimum_detectable_effect",
                 "comparison"]].to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
