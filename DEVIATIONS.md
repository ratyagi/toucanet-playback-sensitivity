# Deviations and clarifications

Changes to, or implementation choices within, `PREREGISTRATION.md` after it was committed. Each entry records the date, what was decided, why, and whether any variant results had been seen.

## 2026-11-05: Event population fixed from the unfiltered analysis (clarification)

- Pre-registration text: events with an incomplete path are excluded, and counts are reported for every variant.
- Clarification: membership of the isolated, overlapping, and incomplete groups is determined once, from variant 1 (unfiltered, 15-minute bins), and held fixed for every variant.
- Reason: the YAMNet filter and 5-minute bins can remove whole bins, which would drop events from the path-completeness rule for reasons unrelated to the research question.
- Per-variant usable events, recorders, and clips are still reported.
- Variant results seen when written: none (only the reference estimate, reproduced in Week 1).

## 2026-11-05: Definition of the detection exclusion tail (clarification)

- Pre-registration text: clips with `Human Activity != "no"`, together with clips recorded during the following five minutes.
- Clarification: a clip is excluded if it is YAMNet-positive, or if its timestamp is within 300 seconds after a YAMNet-positive clip from the same recorder.
- The rule is applied to every clip in the dataset (events, baseline, and placebo candidates alike).
- Variant results seen when written: none.

## 2026-11-05: Two exploratory analyses added after variant results were seen

- What: (1) a complete-window analysis, using only events whose pre and post windows have a usable baseline in every bin; (2) a raw pre/post contrast with no baseline adjustment (the design document's comparison of mean activity with the preceding 60 minutes), using all observed bins.
- Why: a coverage diagnostic showed that for Audio_Moth_5 and Audio_Moth_6, post-onset bins often have no usable baseline, because an event occurs around the same time of day on every recorded day. The baseline-adjusted contrast for those events rests on 0 to 2 bins.
- Status: post hoc and exploratory. Not part of the decision rules. Reported next to all other results, labeled by the `method` column.
- Caution: the raw contrast is confounded by the normal rise and fall of activity around dawn and dusk, when most events were staged.
- Variant results seen when written: yes, all six primary variants (all non-significant, two-sided p from 0.48 to 0.69). The motivation was data coverage, not the size or direction of any estimate.

## 2026-11-05: Placebo implementation choices (clarifications, recorded after the first placebo run)

- Written after the first run of `src/run_placebos.py`. The code defining these choices was written before any placebo result was seen.
- Matched clip positions: a clip's position is its time since the start of its bin, in 3-second steps. The positions removed by the YAMNet filter in a real event window (from the pre-window start to the post-window end) are removed from every placebo candidate window for that event, in addition to any clips the filter removes there itself.
- Placebo draws use the reference seed (20251002) and the reference draw order, once per analysis group (isolated, overlapping), so strict-pool results for variant 1 match the lead's code exactly.
- Two-sided empirical p = min(1, 2 x the smaller of the one-sided empirical p-values).
- Placebo tests cover only events that have at least one candidate. Audio_Moth_5 and Audio_Moth_6 isolated events have none under either pool.
- Placebo results are not part of the pre-registered gate. They enter the decision rules only through the "biological response" criterion after the gate is passed.

## Week 4: decision script (`src/decision.py`)

- The rules are implemented exactly as written in `PREREGISTRATION.md`. Two points the text left open were fixed in code before the script was run on the real tables:
  - The "variant 2 outside the 95% placebo range" check compares the variant 2 model estimate with the strict-pool null range (2.5th to 97.5th percentile). The model estimate uses all isolated events; the placebo uses only events with a candidate day, so the two are on different event sets. The script reports both and the placebo event count, and the criterion is only reached if the gate passes.
  - When no placebo exists for variant 2, the biological-response verdict rests on consistency alone and says so in the output.
- On the real tables the gate fails (variant 1 two-sided p = 0.64), so the verdict is inconclusive and this branch is not reached.
- Review after the first run found two gaps, both corrected before commit:
  - The plan lists a mixed-effects **count** model (log recorded minutes as offset) as the secondary cross-check. Weeks 2 to 4 only fit linear mixed models on the baseline-adjusted deviation, so that item is not complete and is unchecked in the README. A count model on 6 recorders would need a choice (for example a Poisson GLMM or a clustered Poisson GEE, whose standard errors are unreliable with so few clusters) and is not pre-registered. It is left as an open decision.
  - `decision_summary.csv` did not say the results come from the reconstructed draft hypotheses file, which `PREREGISTRATION.md` requires. A `hypotheses_source` column now carries that label.
- Fit note: 31 of 72 model fits needed the Powell optimizer fallback (`fit_method = mixedlm_powell`), and one had no valid standard error. This is the lead's fitting code, unchanged.
