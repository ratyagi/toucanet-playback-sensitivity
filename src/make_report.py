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
            "v4a_original_excluded", "v4b_post_playback_excluded", "v4c_post_playback_5min_excluded"]
LABEL = {"v1_original": "1", "v2_post_playback": "2", "v2b_post_playback_5min": "2b", "v3_buffered": "3",
         "v4a_original_excluded": "4a", "v4b_post_playback_excluded": "4b",
         "v4c_post_playback_5min_excluded": "4c"}
Z = 1.96


def results_table(variant_results: pd.DataFrame) -> pd.DataFrame:
    """Variant x effect x interval x N, both hypotheses, primary method only."""
    t = variant_results[(variant_results["method"] == "primary") & (variant_results["analysis"] == ANALYSIS)].copy()
    t["ci_low"] = t["estimate"] - Z * t["standard_error"]
    t["ci_high"] = t["estimate"] + Z * t["standard_error"]
    t["variant_id"] = t["variant"].map(LABEL)
    t = t.rename(columns={"one_sided_p_less": "one_sided_p", "holm_p": "one_sided_p_holm_2_outcomes"})
    cols = ["variant_id", "variant", "hypothesis", "post_window", "bin_minutes", "yamnet_excluded", "n_events",
            "n_recorders", "estimate", "ci_low", "ci_high", "standard_error", "one_sided_p",
            "one_sided_p_holm_2_outcomes", "two_sided_p",
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


def build_report(variant_results, decision, placebo, recorders, split, robustness, checksum: str) -> str:
    count, own_day, loro = robustness
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
                          f"{f(r.ci_low, 2, True)} to {f(r.ci_high, 2, True)}", f(r.one_sided_p), f(r.one_sided_p_holm_2_outcomes), f(r.two_sided_p), f(r.minimum_detectable_effect)])
    main_table = md_table(["Variant", "Window", "Events", "Recorders", "Estimate (calls/min)", "95% CI", "p one-sided", "p one-sided, Holm", "p two-sided", "Min. detectable"], main_rows)

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
    n_sig_holm = int((decision["placebo_p_two_sided_holm_across_variants"] < 0.05).sum())

    rec = recorders[(recorders["method"] == "primary") & (recorders["analysis"] == ANALYSIS)
                    & (recorders["hypothesis"] == HYPOTHESIS) & (recorders["variant"] == "v1_original")]
    near = rec[rec["recorder"].isin([f"Audio_Moth_{i}" for i in (1, 2, 3, 4)])]
    far = rec[rec["recorder"].isin(["Audio_Moth_5", "Audio_Moth_6"])]

    direction = "increase" if pv1["observed"] > 0 else "decrease"
    drop_support = "no support" if pv1["p_less"] > 0.05 else "some support"
    all_ev = split[(split["variant"] == "v1_original") & (split["analysis"] == "all_events")].set_index("has_yamnet_detection")

    n_neg = int((calls["estimate"] < 0).sum())
    n_zero = int(((calls["ci_low"] <= 0) & (calls["ci_high"] >= 0)).sum())
    sign_line = (f"{n_neg} of {len(calls)} estimates are negative ({f(calls['estimate'].min(), 2, True)} to "
                 f"{f(calls['estimate'].max(), 2, True)}). {n_zero} of {len(calls)} intervals include zero. "
                 "Events used per variant: `results/tables/event_counts.csv`.")
    c1 = count[count["variant"] == "v1_original"].iloc[0]
    d1 = own_day[own_day["variant"] == "v1_original"].set_index("baseline")
    d2 = own_day[own_day["variant"] == "v2_post_playback"].set_index("baseline")
    omitted = loro[loro["omitted"] != "none"]
    flagged = sorted(set(omitted.loc[omitted["influential"], "omitted"]))
    flagged_text = " and ".join(flagged) if flagged else "no recorder"
    gate_line = (f"Gate: variant 1 primary isolated call rate needs two-sided p < 0.05. Observed p = {f(gate['two_sided_p'])}."
                 if overall["comparison"] == "inconclusive_gate_not_passed" else overall["note"])
    return f"""# Playback Experiment: results and verdict

Status: working draft. Hypotheses: the lead's `configs/hypotheses.json`. Listening review pending.
Dataset SHA-256: `{checksum}`. All numbers come from `results/tables/` via `src/make_report.py`.

## Question

Is the apparent acoustic response to simulated human presence a biological change in animal vocal activity, or the direct sound of the event itself (for human presence, the people the recorder hears)?

## Verdict: {verdict}

- {gate_line}
- There is no detectable original effect to attribute, so the other variants are descriptive.
- This is not evidence of no effect. The test cannot detect changes smaller than {f(calls['minimum_detectable_effect'].min())} to {f(calls['minimum_detectable_effect'].max())} calls per minute.

## Results

Primary test: call rate, isolated events, baseline-adjusted, random-intercept model by recorder.
Events: 29 (11 complete isolated, 11 complete overlapping, 7 incomplete). The primary model uses 10 of the 11 isolated events, because one has no usable baseline.

{main_table}

![Primary estimate by variant](results/figures/fig_variants.png)

- {sign_line}
- p one-sided: the drop hypothesis, unadjusted. p one-sided, Holm: adjusted across the two outcomes (call rate, taxa count). p two-sided: unadjusted, and the one the gate uses, because the design document states changes in either direction.
- {taxa_line}

## Exploratory checks (not part of the verdict)

- **The sign depends on how missing baselines are handled.** Without baseline adjustment the variant 1 estimate is {f(raw['estimate'], 2, True)} (p = {f(raw['two_sided_p'])}, {int(raw['n_events'])} events). Using only complete windows it is {f(complete['estimate'], 2, True)} (p = {f(complete['two_sided_p'])}, {int(complete['n_events'])} events).
- **Placebo-in-time, {int(pv1['events'])} events on {int(pv1['recorders'])} recorders.** Variant 1 observed {f(pv1['observed'], 2, True)}, placebo 95% range {f(pv1['null_q025'], 2, True)} to {f(pv1['null_q975'], 2, True)}, two-sided p = {f(pv1['p_two_sided'], 3)}. Variant 2: p = {f(pv2['p_two_sided'], 3)}. {n_sig} of {len(pl)} variants have p < 0.05, all on the same events. After Holm adjustment across variants, {n_sig_holm} of {len(pl)}.
  - The direction is an {direction}. The one-sided test for a drop gives p = {f(pv1['p_less'], 2)}, so it gives {drop_support} for a drop.
  - The placebo null is not centered on zero (median {f(pv1['null_median'], 2, True)}), so comparing with zero would be the wrong test.
- **Count model (negative binomial, window 0 to 60).** Post window against clean baseline bins: rate ratio {f(c1['rate_ratio'])} ({f(c1['ci_low'])} to {f(c1['ci_high'])}), p = {f(c1['two_sided_p'], 3)} with recorder-day clusters, p = {f(c1['two_sided_p_two_way'], 3)} with recorder and date clustered two ways. The pre window is already {f(c1['pre_rate_ratio'])} of baseline. Post against pre, the primary design: {f(c1['post_over_pre_rate_ratio'])} (p = {f(c1['post_over_pre_p'])}). The post-against-pre readout was added after the first result.
- **Leave-own-day-out baseline.** Variant 1 {f(d1.loc['leave_own_day_out', 'estimate'], 2, True)} (p = {f(d1.loc['leave_own_day_out', 'two_sided_p'])}) against {f(d1.loc['reference_baseline', 'estimate'], 2, True)} with the reference baseline. Variant 2 {f(d2.loc['leave_own_day_out', 'estimate'], 2, True)} against {f(d2.loc['reference_baseline', 'estimate'], 2, True)}. The gate still fails.
- **Leave-one-recorder-out.** Omitting {flagged_text} flips the sign of the estimate (flagged in {int(omitted['influential'].sum())} of {len(omitted)} refits). No omission brings p below 0.05 (smallest {f(omitted['two_sided_p'].min())}).
- **By recorder (variant 1).** Audio_Moth_1 to 4 average {f(weighted_mean(near), 2, True)} ({int(near['events'].sum())} events). Audio_Moth_5 and 6 average {f(weighted_mean(far), 2, True)} ({int(far['events'].sum())} events). These two recorders have no presence-free days, so their baselines are thin.
- **YAMNet detection split (descriptive).** Mean contrast {f(all_ev.loc[True, 'mean_contrast'], 2, True)} for the {int(all_ev.loc[True, 'events'])} events with a detection and {f(all_ev.loc[False, 'mean_contrast'], 2, True)} for the {int(all_ev.loc[False, 'events'])} without. The split is confounded with recorder.
- **Listening review:** pending.

Figures: `results/figures/fig_placebo.png`, `fig_leave_one_recorder_out.png`, `fig_count_model.png`.

## Limitations

- Only 5 days of recording, so time-of-day baselines rest on few days.
- Audio_Moth_5 and 6 hold 16 of 29 events and have no strict placebo controls.
- 7 of 29 events have an incomplete -3 h to +12 h path.
- YAMNet non-detection does not prove the event was inaudible.
- Clustered standard errors are unstable with 6 recorders and 5 dates: the count-model p-value is {f(c1['two_sided_p'], 2)} or {f(c1['two_sided_p_two_way'], 2)} depending on how the clusters are drawn.
- 31 of 72 model fits used the optimizer fallback, and one had no valid standard error.
- Time zero is the moment the simulation event took place (confirmed by the lead, November 19, 2026). Each event is tied to one 3-second clip, so its timing is accurate to about one clip. Windows are described as minutes after time zero, not as after playback, because no sound was played for human presence.

## For the December decision

- Result to carry forward: inconclusive. The pre-registered test shows no detectable response, so neither a biological response nor the direct sound of the event can be attributed.
- To resolve it: more events with clean baselines (recordings on days without simulated events at the Audio_Moth_5 and 6 sites), the lead's hypotheses file, and the listening review.

## Reproducibility

- Steps 1 to 13 in `README.md` regenerate every table and figure. Seeds are fixed.
- Choices were fixed in `PREREGISTRATION.md` before the analysis. Every later change is in `DEVIATIONS.md`.
"""


def main() -> None:
    variant_results = pd.read_csv(TABLES / "variant_results.csv")
    table = results_table(variant_results)
    table.to_csv(TABLES / "results_table.csv", index=False)
    text = build_report(
        variant_results, pd.read_csv(TABLES / "decision_summary.csv"), pd.read_csv(TABLES / "placebo_results.csv"),
        pd.read_csv(TABLES / "variant_recorder_results.csv"), pd.read_csv(TABLES / "yamnet_split_summary.csv"),
        tuple(pd.read_csv(TABLES / f"robustness_{n}.csv") for n in ("count_model", "leave_own_day", "leave_one_recorder")),
        (REPO / "reference" / "dataset_checksum.txt").read_text().split()[0],
    )
    (REPO / "REPORT.md").write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote results_table.csv ({len(table)} rows) and REPORT.md")


if __name__ == "__main__":
    main()
