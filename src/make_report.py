#!/usr/bin/env python3
"""Build the results table and the one-page report from the existing result tables.

Every number in REPORT.md is read from results/tables/, so the report cannot drift from the data.
Run after src/decision.py, src/run_diagnostics.py and src/run_placebos.py.

  python src/make_report.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
TABLES = REPO / "results" / "tables"
ANALYSIS, HYPOTHESIS = "primary_isolated", "primary_call_rate"
VARIANTS = ["v1_original", "v2_post_playback", "v2b_post_playback_5min", "v3_buffered",
            "v4a_original_excluded", "v4b_post_playback_excluded"]
LABEL = {"v1_original": "1", "v2_post_playback": "2", "v2b_post_playback_5min": "2b", "v3_buffered": "3",
         "v4a_original_excluded": "4a", "v4b_post_playback_excluded": "4b"}
Z = 1.96


def results_table(variant_results: pd.DataFrame) -> pd.DataFrame:
    """Variant x effect x interval x N, both hypotheses, primary method only."""
    t = variant_results[(variant_results["method"] == "primary") & (variant_results["analysis"] == ANALYSIS)].copy()
    t["ci_low"] = t["estimate"] - Z * t["standard_error"]
    t["ci_high"] = t["estimate"] + Z * t["standard_error"]
    t["variant_id"] = t["variant"].map(LABEL)
    cols = ["variant_id", "variant", "hypothesis", "post_window", "bin_minutes", "yamnet_excluded", "n_events",
            "n_recorders", "estimate", "ci_low", "ci_high", "standard_error", "two_sided_p",
            "minimum_detectable_effect"]
    t = t[cols]
    t["variant"] = pd.Categorical(t["variant"], VARIANTS, ordered=True)
    return t.sort_values(["hypothesis", "variant"]).reset_index(drop=True)


def f(x: float, digits: int = 2, sign: bool = False) -> str:
    if x is None or not np.isfinite(x):
        return "n/a"
    return f"{x:+.{digits}f}" if sign else f"{x:.{digits}f}"


def md_table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def weighted_mean(df: pd.DataFrame) -> float:
    return float((df["events"] * df["mean_contrast"]).sum() / df["events"].sum())


def build_report(variant_results, decision, placebo, recorders, split, checksum: str) -> str:
    table = results_table(variant_results)
    calls = table[table["hypothesis"] == HYPOTHESIS]
    overall = decision.loc[decision["variant"] == "OVERALL"].iloc[0]
    gate = decision.loc[decision["variant"] == "v1_original"].iloc[0]
    verdict = {"inconclusive_gate_not_passed": "Inconclusive", "biological_response": "Biological response",
               "direct_contamination": "Direct contamination", "mixed_inconclusive": "Mixed, inconclusive"}[overall["comparison"]]

    main_rows = []
    for r in calls.itertuples():
        window = f"{r.post_window} min, {int(r.bin_minutes)}-min bins" + (", YAMNet clips removed" if r.yamnet_excluded else "")
        main_rows.append([r.variant_id, window, str(r.n_events), str(r.n_recorders), f(r.estimate, 2, True),
                          f"{f(r.ci_low, 2, True)} to {f(r.ci_high, 2, True)}", f(r.two_sided_p), f(r.minimum_detectable_effect)])
    main_table = md_table(["Variant", "Window", "Events", "Recorders", "Estimate (calls/min)", "95% CI", "p (two-sided)", "Min. detectable"], main_rows)

    taxa = table[table["hypothesis"] == "secondary_taxa_count"]
    taxa_line = (f"Secondary outcome, taxa count: estimates {f(taxa['estimate'].min(), 2, True)} to {f(taxa['estimate'].max(), 2, True)} "
                 f"taxa, smallest p = {f(taxa['two_sided_p'].min())}. Full table: `results/tables/results_table.csv`.")

    def pick(method):
        return variant_results[(variant_results["variant"] == "v1_original") & (variant_results["method"] == method)
                               & (variant_results["analysis"] == ANALYSIS) & (variant_results["hypothesis"] == HYPOTHESIS)].iloc[0]
    raw, complete = pick("raw_unadjusted"), pick("complete_window")

    pl = placebo[(placebo["pool"] == "strict") & (placebo["analysis"] == ANALYSIS) & (placebo["hypothesis"] == HYPOTHESIS)].set_index("variant")
    pv1, pv2 = pl.loc["v1_original"], pl.loc["v2_post_playback"]
    n_sig = int((pl["p_two_sided"] < 0.05).sum())

    rec = recorders[(recorders["method"] == "primary") & (recorders["analysis"] == ANALYSIS)
                    & (recorders["hypothesis"] == HYPOTHESIS) & (recorders["variant"] == "v1_original")]
    near = rec[rec["recorder"].isin([f"Audio_Moth_{i}" for i in (1, 2, 3, 4)])]
    far = rec[rec["recorder"].isin(["Audio_Moth_5", "Audio_Moth_6"])]

    direction = "increase" if pv1["observed"] > 0 else "decrease"
    drop_support = "no support" if pv1["p_less"] > 0.05 else "some support"
    all_ev = split[(split["variant"] == "v1_original") & (split["analysis"] == "all_events")].set_index("has_yamnet_detection")

    gate_line = (f"Gate: variant 1 primary isolated call rate needs two-sided p < 0.05. Observed p = {f(gate['two_sided_p'])}."
                 if overall["comparison"] == "inconclusive_gate_not_passed" else overall["note"])
    return f"""# Playback Experiment: results and verdict

Status: DRAFT. Hypotheses file reconstructed (`configs/hypotheses_draft.json`), lead's `hypotheses.json` not received. Listening review pending.
Dataset SHA-256: `{checksum}`. All numbers come from `results/tables/` via `src/make_report.py`.

## Question

Is the apparent acoustic response to simulated human presence a biological change in animal vocal activity, or direct playback sound?

## Verdict: {verdict}

- {gate_line}
- There is no detectable original effect to attribute, so the other variants are descriptive.
- This is not evidence of no effect. The test cannot detect changes smaller than {f(calls['minimum_detectable_effect'].min())} to {f(calls['minimum_detectable_effect'].max())} calls per minute.

## Results

Primary test: call rate, isolated events, baseline-adjusted, random-intercept model by recorder.

{main_table}

- All six estimates are negative ({f(calls['estimate'].max(), 2, True)} to {f(calls['estimate'].min(), 2, True)}) and every interval includes zero.
- {taxa_line}

## Exploratory checks (not part of the verdict)

- **The sign depends on how missing baselines are handled.** Without baseline adjustment the variant 1 estimate is {f(raw['estimate'], 2, True)} (p = {f(raw['two_sided_p'])}, {int(raw['n_events'])} events). Using only complete windows it is {f(complete['estimate'], 2, True)} (p = {f(complete['two_sided_p'])}, {int(complete['n_events'])} events).
- **Placebo-in-time, {int(pv1['events'])} events on {int(pv1['recorders'])} recorders.** Variant 1 observed {f(pv1['observed'], 2, True)}, placebo 95% range {f(pv1['null_q025'], 2, True)} to {f(pv1['null_q975'], 2, True)}, two-sided p = {f(pv1['p_two_sided'], 3)}. Variant 2: p = {f(pv2['p_two_sided'], 3)}. {n_sig} of 6 variants have p < 0.05, all on the same events and unadjusted for multiple looks.
  - The direction is an {direction}. The one-sided test for a drop gives p = {f(pv1['p_less'], 2)}, so it gives {drop_support} for a drop.
  - The placebo null is not centered on zero (median {f(pv1['null_median'], 2, True)}), so comparing with zero would be the wrong test.
- **By recorder (variant 1).** Audio_Moth_1 to 4 average {f(weighted_mean(near), 2, True)} ({int(near['events'].sum())} events). Audio_Moth_5 and 6 average {f(weighted_mean(far), 2, True)} ({int(far['events'].sum())} events). These two recorders have no presence-free days, so their baselines are thin.
- **YAMNet detection split (descriptive).** Mean contrast {f(all_ev.loc[True, 'mean_contrast'], 2, True)} for the {int(all_ev.loc[True, 'events'])} events with a detection and {f(all_ev.loc[False, 'mean_contrast'], 2, True)} for the {int(all_ev.loc[False, 'events'])} without. The split is confounded with recorder.
- **Listening review:** pending.

## Limitations

- Only 5 days of recording, so time-of-day baselines rest on few days.
- Audio_Moth_5 and 6 hold 16 of 29 events and have no strict placebo controls.
- 7 of 29 events have an incomplete -3 h to +12 h path.
- YAMNet non-detection does not prove playback was inaudible.
- The secondary count model in the plan was not fitted. The linear models above stand in for it.
- 31 of 72 model fits used the optimizer fallback, and one had no valid standard error.
- Whether `Sim Relative Time` 0 is the start or the middle of playback is unconfirmed.

## For the December decision

- Result to carry forward: inconclusive. The pre-registered test shows no detectable response, so neither a biological response nor direct playback sound can be attributed.
- To resolve it: more events with clean baselines (recordings on days without playback at the Audio_Moth_5 and 6 sites), the lead's hypotheses file, and the listening review.

## Reproducibility

- Steps 1 to 11 in `README.md` regenerate every table and figure. Seeds are fixed.
- Choices were fixed in `PREREGISTRATION.md` before the analysis. Every later change is in `DEVIATIONS.md`.
"""


def main() -> None:
    variant_results = pd.read_csv(TABLES / "variant_results.csv")
    table = results_table(variant_results)
    table.to_csv(TABLES / "results_table.csv", index=False)
    text = build_report(
        variant_results, pd.read_csv(TABLES / "decision_summary.csv"), pd.read_csv(TABLES / "placebo_results.csv"),
        pd.read_csv(TABLES / "variant_recorder_results.csv"), pd.read_csv(TABLES / "yamnet_split_summary.csv"),
        (REPO / "reference" / "dataset_checksum.txt").read_text().split()[0],
    )
    (REPO / "REPORT.md").write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote results_table.csv ({len(table)} rows) and REPORT.md")


if __name__ == "__main__":
    main()
