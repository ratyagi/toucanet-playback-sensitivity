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

## Week 5: diagnostics and listening sample

- The pre-registration does not say which simulation clips form the listening pool. Fixed before the draw: clips of "Human Presence on Trail" events (labeled window -600 to +600 s, so five 4-minute strata fit exactly) that carry no other simulated component. The two off-trail events (0 to +5 min) cannot fill five 4-minute strata and are left out.
- Clips that overlap a vehicle, gunshot, or chainsaw component are excluded (2,400 clips), so the reviewer judges playback and not another simulated sound. This also removes 63 of the 167 YAMNet-positive on-trail clips, which co-occur with another component (YAMNet may be reacting to that sound).
- Consequence: the positive pool has 104 clips, so the sample of 100 is almost a census. 75 of the 104 come from Audio_Moth_6 and none from Audio_Moth_3, so the positive side cannot be balanced across recorders. Negatives are balanced by position (20 per stratum) and spread across recorders in proportion to their clips.
- Allocation across recorders is proportional (largest remainder). Seed 20251002.
- Figures count YAMNet-positive clips in every clip of a bin, labeled or not. `has_yamnet_detection` (22 vs 7) counts only labeled simulation clips, so an event can be "none in labeled clips" and still show a bar from ordinary clips.
- The 22 vs 7 split is shown for variants 1 and 2 only, as descriptive tables with no test. Events without a contrast (incomplete paths or no baseline) are listed with an empty contrast.
- Review of the Week 5 work found three gaps, fixed before commit (the drawn sample did not change, only a `weight` column was added):
  - The +2 to +6 min position stratum has only 324 usable negative clips, against 1,672 to 2,160 in the others, because other simulated sounds overlap that part of the window. Equal sampling (20 per stratum) therefore samples it about six times more heavily. Per-stratum audibility rates are unaffected, but an overall rate must be weighted. The key now carries an inverse sampling-fraction `weight`, and `analyze_listening.py` reports `share_yes_pool_weighted`. The Wilson interval belongs to the unweighted share only.
  - The pool therefore describes clips with no overlapping simulated sound. Audibility estimates do not transfer to the overlapped clips that were excluded.
  - The 22-vs-7 split is confounded with recorder: all 8 Audio_Moth_6 events and all 3 Audio_Moth_2 events have a detection, while 4 of the 7 events without one are on Audio_Moth_5. A recorder table (`yamnet_split_by_recorder.csv`) and an all-events row (`analysis = all_events`) were added so the 22 vs 7 is visible directly. It stays descriptive.

## Week 4 addendum: secondary count model (specification fixed before fitting)

Written and committed before any count model was run. The plan lists a count model with a recorded-minutes offset as the secondary cross-check. Weeks 2 to 4 only fit linear models, so this closes that gap. It is exploratory and cannot change the verdict, which stays with the pre-registered call-rate model.

**Specification (one model per window, no alternatives)**
- Data: the 15-minute bins from `results/intermediate/bin_descriptors.csv` (detection count, recorded minutes, time-of-day bin, date, event-contamination flag).
- Outcome: detection count per bin.
- Rows: bins of the 10 primary isolated events with a usable contrast in variant 1, plus all clean bins (no simulated component from -10 to +60 min) as the baseline.
- Terms: recorder fixed effects, time-of-day harmonics (24 h and 12 h sine and cosine), a pre-window indicator (-60 to 0 min), a post-window indicator.
- Family: negative binomial (NB2), log link, offset = log(recorded minutes), dispersion estimated by maximum likelihood.
- Standard errors: clustered by recorder and date.
- Effect: rate ratio for the post-window indicator, with 95% interval, two-sided p, and the rate-ratio detectable at that standard error.
- Windows: 0 to 60 min (variant 1) and 15 to 60 min (variant 2). No other windows.

**Why this and not a random-intercept count model**
- The pinned statsmodels has no negative binomial mixed model, and 6 recorders are too few to estimate a random effect well. Recorder fixed effects with clustered standard errors are the stable equivalent.
- Time-of-day harmonics and clean baseline bins play the role of the recorder-by-time-of-day baseline in the linear model. Without them, a raw pre/post count comparison would confound response with the daily cycle.

**Rules for reporting**
- If a fit does not converge, it is reported as not estimable. No other family, window, or terms are tried afterward.
- Both fits are reported whether or not they agree with the linear model.
- The README item stays unchecked until the result is committed.

## Week 6 addendum: leakage and robustness checks (specification fixed before running)

Written and committed before either check was run. Both are exploratory sensitivity checks of the primary test. Neither can change the verdict, which stays with the pre-registered gate.

**Check A: leave-own-day-out baseline**
- Reason: the reference baseline is the median of all clean bins for the same recorder and time of day. That includes the event's own pre-window bins. With 5 days of recording, the event's own day can be one of at most 5 baseline values, so its pre-window residuals are shrunk toward zero.
- Method: for every bin, the baseline excludes clean bins of the same recorder and time of day that fall on the same calendar date as the bin. Everything else is unchanged: clean-bin definition, 15-minute bins, contrast definition, event set, and the lead's mixed model.
- Windows: variant 1 (0 to 60 min) and variant 2 (15 to 60 min).
- Bins left without any baseline are dropped, as in the reference method. The number of events with a usable contrast is reported next to the estimate.
- Output: estimate, standard error, two-sided p, events, next to the primary result.

**Check B: leave-one-recorder-out (the experiment's LODO analog)**
- Reason: recorders are the sites. The result should not depend on one of them.
- Method: refit the primary isolated call-rate model with each of the 6 recorders omitted in turn, for variants 1 and 2. Same model, same code.
- A recorder is flagged influential if omitting it flips the sign of the estimate or moves the two-sided p across 0.05.
- Output: estimate, standard error, two-sided p, and events for each omitted recorder, plus the range of estimates.
- A fit that fails is reported as not estimable.

**Recommendation section in `REPORT.md`**
- The mapping from verdict to action is written after the verdict (inconclusive) was known, and the report says so.
  - Biological response: go, the disturbance signal can be used as a label.
  - Direct contamination: no-go until the labels are cleaned.
  - Mixed or inconclusive: hold, the signal is unvalidated and clean-baseline data is needed first.
- The mapping is a recommendation for this experiment's scope. The team's December go/no-go on the embedding paradigm is a separate decision.

**Not adjusted**
- No multiplicity correction across variants. The gate is a single test, so the verdict is unaffected.
