# Playback Experiment: results and verdict

Status: DRAFT. Hypotheses file reconstructed (`configs/hypotheses_draft.json`), lead's `hypotheses.json` not received. Listening review pending.
Dataset SHA-256: `54a74d263b668adc2253eda261c1b1f532086d2671c94d3ccd467bb36e3a5aeb`. All numbers come from `results/tables/` via `src/make_report.py`.

## Question

Is the apparent acoustic response to simulated human presence a biological change in animal vocal activity, or direct playback sound?

## Verdict: Inconclusive

- Gate: variant 1 primary isolated call rate needs two-sided p < 0.05. Observed p = 0.64.
- There is no detectable original effect to attribute, so the other variants are descriptive.
- This is not evidence of no effect. The test cannot detect changes smaller than 1.59 to 2.64 calls per minute.

## Results

Primary test: call rate, isolated events, baseline-adjusted, random-intercept model by recorder.

| Variant | Window | Events | Recorders | Estimate (calls/min) | 95% CI | p (two-sided) | Min. detectable |
|---|---|---|---|---|---|---|---|
| 1 | 0-60 min, 15-min bins | 10 | 6 | -0.41 | -2.11 to +1.29 | 0.64 | 1.70 |
| 2 | 15-60 min, 15-min bins | 9 | 6 | -0.48 | -2.60 to +1.64 | 0.66 | 2.12 |
| 2b | 20-60 min, 5-min bins | 11 | 6 | -0.58 | -2.17 to +1.01 | 0.48 | 1.59 |
| 3 | 30-60 min, 15-min bins | 8 | 6 | -0.54 | -3.18 to +2.11 | 0.69 | 2.64 |
| 4a | 0-60 min, 15-min bins, YAMNet clips removed | 10 | 6 | -0.34 | -2.05 to +1.37 | 0.69 | 1.71 |
| 4b | 15-60 min, 15-min bins, YAMNet clips removed | 9 | 6 | -0.47 | -2.60 to +1.67 | 0.67 | 2.14 |

- All six estimates are negative (-0.34 to -0.58) and every interval includes zero.
- Secondary outcome, taxa count: estimates -0.08 to +0.40 taxa, smallest p = 0.48. Full table: `results/tables/results_table.csv`.

## Exploratory checks (not part of the verdict)

- **The sign depends on how missing baselines are handled.** Without baseline adjustment the variant 1 estimate is +0.68 (p = 0.28, 11 events). Using only complete windows it is +0.53 (p = 0.63, 5 events).
- **Placebo-in-time, 5 events on 4 recorders.** Variant 1 observed +0.47, placebo 95% range -1.36 to +0.47, two-sided p = 0.054. Variant 2: p = 0.010. 5 of 6 variants have p < 0.05, all on the same events and unadjusted for multiple looks.
  - The direction is an increase. The one-sided test for a drop gives p = 0.97, so it gives no support for a drop.
  - The placebo null is not centered on zero (median -0.31), so comparing with zero would be the wrong test.
- **By recorder (variant 1).** Audio_Moth_1 to 4 average +0.66 (5 events). Audio_Moth_5 and 6 average -1.91 (5 events). These two recorders have no presence-free days, so their baselines are thin.
- **YAMNet detection split (descriptive).** Mean contrast -0.36 for the 22 events with a detection and -0.32 for the 7 without. The split is confounded with recorder.
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
