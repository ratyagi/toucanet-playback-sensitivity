# toucanet-playback-sensitivity

Tests whether the apparent acoustic response to simulated human presence is a biological change in animal vocal activity, or the sound of the simulated event itself being picked up in the recordings.

Part of Team Toucanet (Kashmir World Foundation), Fall 2026. Feeds Fall Plan next step 2 (stability vs. ecological interpretability) and the December go/no-go on the current embedding paradigm.

**Status (November 19, 2026):** analysis for Weeks 1 to 7 is complete and committed. Week 8 (variant 4c, p-value labels, event counts) is done and awaiting commit. The pre-registered verdict is **inconclusive**. The lead's feedback of November 12 is built into the plan below (Weeks 7 to 12). The result is not yet ready to support a biological-versus-direct-sound conclusion.

## Why this matters

- If the effect disappears once the event interval and YAMNet-positive clips are excluded, the signal is mostly a human-sound detector, not an ecological response.
- That is a "no" on the interpretability question and affects any recommendation to scale the current pipeline.
- YAMNet flags human sound in only 168 of 10,636 simulation clips (1.6%), but at least one detection falls in 22 of 29 events (76%).
- Detections are sparse within events and concentrated around them. A clip with no detection does not prove the event was inaudible.

## Research question

Do estimated changes in animal acoustic activity persist after the labeled event interval and after clips with detectable human-related sound are removed?

## What the simulation events are

Source: the field team, as relayed by Daan, November 2026. The lead has not yet confirmed this wording.

- Events were logged in the DeepData Capture app with a single timestamp, linked to one 3-second clip. `Sim Relative Time` was added during data processing. Time zero is the moment the simulation event took place. Negative time is before it, positive time is after it.
- **Human presence (on trail and off trail):** real people were present. No sound was played. Effects on vocalizations are assumed from 600 seconds before to 600 seconds after time zero.
- **Anthropogenic sound events:** a sound was played at time zero. Effects are assumed up to 300 seconds after.
- Consequence for this repository: "playback" in the design document applies to the sound events. For the 29 human-presence events, the direct-sound question is whether the recorder hears the people themselves. Prose now says "after time zero" instead of "post-playback". Variant and config file names keep their original names so results stay traceable.

## Hypotheses

- **Biological response:** call rate or taxa count changes after exposure, and the change holds with the labeled interval and YAMNet-positive clips excluded.
- **Direct sound:** the effect sits inside the labeled interval, or disappears once positive and adjacent clips are removed.
- **Null:** changes around events match ordinary variation at matched placebo times.
- The lead's `hypotheses.json` states the two tested hypotheses as drops (one-sided): call rate (primary) and taxa count (secondary) decrease in the 60 minutes after onset relative to the 60 minutes before.

## Analysis design

- **Events:** 29 human-presence events, reconstructed as clip timestamp minus `Sim Relative Time`. Groups, fixed once from variant 1: **11 complete isolated, 11 complete overlapping, 7 incomplete** (path not fully recorded).
  - Isolated: full -3 h to +12 h path recorded, no other human-presence onset inside it. Primary population.
  - Overlapping: full path recorded, another human-presence onset inside it. Robustness population.
  - The primary model uses 10 of the 11 isolated events, because one has no usable baseline.
- **Baseline:** median of clean 15-minute bins for the same recorder and time of day. A bin is clean if no simulated component falls from 10 minutes before to 60 minutes after.
- **Contrast per event:** mean baseline-adjusted value in the response window minus the mean in the 60 minutes before onset.
- **Outcomes:** primary is species-detection call rate per recorded minute. Secondary is taxa count.
- **Model:** random-intercept model on event contrasts, recorder as the grouping effect. Holm adjustment across the two outcomes.
- **Gate:** variant 1, primary isolated call rate, two-sided p < 0.05. If it fails, the verdict is inconclusive and the other variants are descriptive. The lead's hypothesis is one-sided, so both p-values are reported. The gate fails under either (0.32 one-sided, 0.64 two-sided). Week 8 reconciles the two in the report.
- **Placebo-in-time calibration:** 1,000 draws, fixed seed, strict and relaxed candidate pools. Exploratory, not part of the gate.
- **Always reported:** effect sizes, 95% intervals, and the minimum detectable effect (about 1.96 times the standard error). N is small.

| Variant | Response window (minutes after time zero) | Exclusion | Config |
|---|---|---|---|
| 1. Original | 0-60 | none | `v1_original` |
| 2. After the labeled interval | 15-60 | none | `v2_post_playback` |
| 2b. As written in the design document | 20-60, 5-minute bins | none | `v2b_post_playback_5min` |
| 3. Buffered | 30-60 | none | `v3_buffered` |
| 4a. Original, detection-excluded | 0-60 | `Human Activity != "no"` clips and clips within 300 s after one, same recorder | `v4a_original_excluded` |
| 4b. After the labeled interval, detection-excluded | 15-60 | same as 4a | `v4b_post_playback_excluded` |
| 4c. As written in the design document, detection-excluded (planned, Week 8) | 20-60, 5-minute bins | same as 4a | `v4c_...` |

## Interpretation criteria

Fixed in `PREREGISTRATION.md`. The design document gives no numeric thresholds, so these were set in advance.

- **Biological response:** all comparison variants consistent with variant 1 (same sign, ratio of at least 0.5), and the variant 2 estimate outside the 95% placebo range where a placebo exists.
- **Direct contamination:** at least two comparison variants substantially smaller (ratio between 0 and 0.5) or reversed.
- **Inconclusive:** the gate fails, or the pattern fits neither interpretation. Never reported as "no effect".
- Adding variant 4c changes "five comparison variants" to six. This is logged in `DEVIATIONS.md` (Week 8).

## Lead feedback of November 12, 2026 and where each point is handled

| Instruction | Week |
|---|---|
| Run the negative binomial model, leave-own-day-out baseline, and leave-one-recorder-out as exploratory checks. Clustered standard errors may be unstable with 6 recorders and 5 dates. None can change the primary verdict. | 9 |
| Listening review: document exclusions and sampling weights. Call the positive sample nearly a census. The experiment owner reviews all clips alone, agreed with the lead (November 19). The report states that the review is single-rater. | 10 |
| Keep `event_study.py` and `placebo_hypothesis_analysis.py`, with provenance and any modifications documented. See `src/lead/PROVENANCE.md`. | 7 (done) |
| Do not call later windows "post-playback" until `Sim Relative Time` is confirmed. Relayed answer recorded in `DEVIATIONS.md`; the lead will confirm. | 7 (done) |
| Reconcile the two-sided decision rule with the one-sided hypothesis. | 8 |
| Distinguish adjusted from unadjusted p-values. | 8 |
| Run the exact 20-60 minute detection-excluded analysis, or document the 15-60 substitution as a deviation. Decision: run it as variant 4c. | 8 |
| Describe event groups as 11 complete isolated, 11 complete overlapping, 7 incomplete. | 7 (done; deck in Week 11) |
| Receive `hypotheses.json`. Added unmodified and checked against our draft: all outputs identical. | 7 (done) |

## Plan

### Week 1: Inputs and setup
- [x] Collect: `bioacoustics_dataset.csv`, existing baseline and matched-placebo code, the 29 event onset times. No field records of event end times exist: events were logged as single timestamps.
- [x] Reproduce the existing 0-60 estimate. Do not move on until it matches.
- [x] Check all timestamps are in one timezone (UTC-06:00 for all clips; no second time source exists).
- [x] Commit `PREREGISTRATION.md` (windows, exclusions, primary outcome, criteria) before running any variant.

### Week 2: Windows as config
- [x] One config per variant (`configs/variants/`) and a runner (`src/run_variants.py`) that takes window spec + exclusion rule and returns the contrasts and models.
- [x] YAMNet exclusion filter (`src/exclusion.py`, tested in `tests/`).
- [x] Six variants implemented (1, 2, 2b, 3, 4a, 4b). Variant 1 reproduces the reference results.

### Week 3: Placebo matching and event types
- [x] Define placebo exclusions (strict pool as primary, relaxed pool as sensitivity) and apply to every variant, with position-matched clip drops in the detection-excluded variants.
- [x] Split isolated vs. overlapping events.
- [x] Log usable events, clips, and recorders left under every rule (`results/tables/placebo_pool_summary.csv`, `variant_effort_summary.csv`).

### Week 4: Models
- [x] Pre-registered decision rules applied in `src/decision.py` to the Week 2 models and Week 3 placebo tables (`results/tables/decision_summary.csv`).
- [x] Per-recorder view of the primary test (`results/tables/recorder_coverage.csv`).
- [x] Result: the gate fails (variant 1, two-sided p = 0.64), so the verdict is **inconclusive** and the other variants are descriptive.
- [ ] Count model (secondary): specification fixed in `DEVIATIONS.md` before fitting. Carried to Week 9.

### Week 5: Diagnostics
- [x] Plot YAMNet-positive clips, call rate, and taxa count around each human-presence event (`results/figures/event_diagnostics_<recorder>.png`).
- [x] Exploratory split: 22 events with a YAMNet detection vs. 7 without. Descriptive only, confounded with recorder (`results/tables/yamnet_split_*.csv`).
- [x] Listening sample drawn with a fixed seed (100 YAMNet-positive, 100 YAMNet-negative; `results/listening/`) and a review protocol (`results/listening/PROTOCOL.md`).
- [ ] Blind listening review. Carried to Week 10.

### Week 6: Write-up (first version)
- [x] One results table: variant x effect size x interval x N (`results/tables/results_table.csv`).
- [x] One-page draft verdict (`REPORT.md`, generated from the tables).
- [x] Progress review deck (`docs/`), sent to the lead. Feedback received November 12.
- [x] Specifications for the leakage and leave-one-recorder-out checks fixed in `DEVIATIONS.md` before running.

### Week 7: Feedback intake and inputs
- [x] Add the lead's `hypotheses.json` to `configs/` unmodified. Rerun the placebo script with it and compare with the draft run (`src/compare_runs.py`). Result: all 10 outputs identical. Logged in `DEVIATIONS.md`.
- [x] Remove DRAFT labels from the decision table and the report. Hypotheses are labeled as the lead's file.
- [x] Record the field team's description of `Sim Relative Time` in `DEVIATIONS.md`, with the lead's confirmation marked pending. `PREREGISTRATION.md` stays unedited and is read through the terminology entry. Prose uses "after time zero" and "labeled interval".
- [x] Provenance for the lead's scripts (`src/lead/PROVENANCE.md`) and the reference files (`reference/PROVENANCE.md`), checked by `tests/test_provenance.py`.
- [x] Group names "11 complete isolated, 11 complete overlapping, 7 incomplete" in the README and the report. The primary model uses 10 of the 11 isolated events.
- [ ] Carried to Week 11: the progress deck still uses the old wording and the draft label.
- **Done when:** every table regenerates from the lead's hypotheses file, and the comparison with the draft run is documented. Met.

### Week 8: Decision rules, p-values, and variant 4c
- [x] Add variant 4c (20-60 minutes, 5-minute bins, YAMNet-excluded). Config, run, and placebo calibration. Log it as an addition after feedback, with the reason.
- [x] Update the decision rule from five to six comparison variants. Update `src/decision.py` and its tests. Log it as a deviation. The gate still fails, so the verdict does not change.
- [x] Report the one-sided p (the lead's hypothesis) and the two-sided p side by side in `results_table.csv` and `REPORT.md`. State which one the gate uses and why. Show that the gate fails under both.
- [x] Label every p-value as unadjusted or adjusted. Model p-values: Holm across the two outcomes. Placebo p-values: unadjusted, plus Holm across the variants.
- [x] Add an event-count table (29 events by group, usable events per variant): `results/tables/event_counts.csv`, from `src/event_counts.py`.
- **Done when:** the report shows each p-value with its type, and the tests cover the six-variant rule.

### Week 9: Exploratory robustness checks
All three are exploratory and cannot change the verdict. Specifications are fixed in `DEVIATIONS.md` (Week 4 and Week 6 addenda).
- [ ] **Negative binomial count model:** recorded-minutes offset, recorder fixed effects, time-of-day harmonics, standard errors clustered by recorder and date. Windows 0-60 and 15-60. Test the code on simulated data first. Report non-convergence as not estimable.
- [ ] **Leave-own-day-out baseline:** report how many events keep a usable contrast.
- [ ] **Leave-one-recorder-out:** refit variants 1 and 2 six times. Flag a recorder as influential if dropping it flips the sign or crosses p = 0.05.
- [ ] State in the report that clustered standard errors may be unstable with 6 recorders and 5 dates.
- **Done when:** three result tables are committed in `results/tables/`, each with a convergence or estimability flag, and the tests pass.

### Week 10: Listening review
- [ ] Document the exclusions (2,400 overlapped clips, 63 of 167 positive clips, off-trail events) and the sampling weights in `results/listening/PROTOCOL.md` and the report.
- [ ] Describe the positive sample as nearly a census: 100 of 104 eligible clips, 75 of 104 from Audio_Moth_6, none from Audio_Moth_3.
- [ ] Get the audio files. Run `src/prepare_listening_audio.py`. Fix any missing clips before listening.
- [ ] Adjust the rubric wording for presence events: audible sound made by people who were present.
- [ ] Review all 200 clips blind to the label and the position. Do not edit answers after the summary is seen.
- [ ] Single reviewer, no second rater: the experiment owner reviews all 200 clips. This was agreed with the lead on November 19. State in the report that the review is not independent.
- [ ] Run `src/analyze_listening.py`. Report weighted and unweighted shares, with "unsure" shown separately.
- **Done when:** `listening_summary.csv` is committed and the report states the single-reviewer limit.

### Week 11: Final report, deck, and reproducibility check
- [ ] Regenerate `REPORT.md` with variant 4c, the p-value types, the exploratory checks, and the listening results.
- [ ] Add the recommendation section: go, no-go, or hold, mapped from the verdict. State that the mapping was written after the verdict was known, and that it covers this experiment only, not the December decision.
- [ ] Keep the statement that the result is not yet ready to support a biological-versus-direct-sound conclusion.
- [ ] Update the limitations list: clustered standard errors, the `Sim Relative Time` answer, the off-trail window, and the thin baselines at Audio_Moth_5 and 6.
- [ ] Rebuild the deck (`docs/`).
- [ ] Reproducibility check: clone the repository into a clean folder, create the environment, run steps 1 to 11, and compare every table with the committed one.
- **Done when:** the clean-clone run reproduces all tables, and the report has been read through once for accuracy.

### Week 12: Handover
- [ ] Send the final report and deck to the lead. Answer his follow-up on `Sim Relative Time` when it arrives, and update the documents if it differs from the relayed answer.
- [ ] Tag the repository (for example `v1.0-report`) and push.
- [ ] Hand the verdict to the team for the December LODO comparison. Ask the lead who collects it, since the Fall Plan names no owner.
- [ ] List follow-up needs: more recording days at the Audio_Moth_5 and 6 sites and days without simulated events, so baselines exist.
- **Done when:** the lead has signed off and the tag is pushed.

## Open issues

- **`Sim Relative Time`:** the lead is confirming with the people who set up the experiment. Until then, later windows are described as "after time zero".
- **Off-trail events:** the dataset labels the 2 off-trail events only from 0 to +5 minutes, but the field team's description assumes the same 600 seconds before and after as on-trail events. Ask which is intended.
- **Thin baselines:** Audio_Moth_5 and 6 hold 16 of 29 events and have no presence-free days. The reference baseline also includes the event's own day. The leave-own-day-out check (Week 9) tests this.
- **Placebo exclusion:** the position-matched drop was implemented and logged. Ask the team to confirm it.
- **Fit stability:** 31 of 72 model fits used the optimizer fallback and one had no valid standard error. This is the lead's fitting code, unchanged.
- **Listening review:** needs the audio files.
- **December LODO:** the Fall Plan names no owner for collecting this experiment's result.

## How to reproduce

Run from the repo root in PowerShell. The raw dataset is not in git and lives in the parent `KWF_Toucanet` folder. The team lead's scripts are in `src/lead/`.

1. Create the environment (Python 3.12; the pinned versions do not install on 3.14):
   ```
   py -3.12 -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```
2. Confirm you hold the same dataset (recorded checksum is in `reference/dataset_checksum.txt`):
   ```
   .venv\Scripts\python src\verify_dataset.py ..\bioacoustics_dataset.csv
   ```
3. Rebuild events, bins, baselines, and the control audit:
   ```
   .venv\Scripts\python src\lead\event_study.py --dataset ..\bioacoustics_dataset.csv --output-dir results\intermediate --skip-embeddings
   ```
   Check: `results\intermediate\events.csv` matches `reference\events.csv` (`fc.exe`; ignore line-ending differences), and `audit_report.md` reports 29 human-presence onsets.
4. Run the contrast, model, and placebo script with the lead's hypotheses file (`configs/hypotheses.json`, unmodified). Run the config and provenance tests first:
   ```
   .venv\Scripts\python tests\test_configs.py
   .venv\Scripts\python tests\test_provenance.py
   .venv\Scripts\python src\lead\placebo_hypothesis_analysis.py --input-dir results\intermediate --output-dir results\intermediate\placebo --hypotheses configs\hypotheses.json
   ```
   Check: primary isolated call-rate estimate near -0.41 with 10 events and 6 recorders, matching `reference/mixed_effects_results.csv`. To compare two runs of this script, for example after changing an input, use `src\compare_runs.py <folder A> <folder B>`. It prints `identical` or `DIFFERENT` for every file.

5. Derive each event's labeled span and YAMNet detection count:
   ```
   .venv\Scripts\python src\derive_event_spans.py --dataset ..\bioacoustics_dataset.csv --events reference\events.csv --output reference\event_spans.csv
   ```
   Check: it reports 61 events matched, 29 human-presence events, 22 of 29 with a YAMNet detection, and 168 YAMNet-positive clips.

6. Run the unit tests, then all seven response-window variants (variant 1 must reproduce the reference, or the run stops):
   ```
   .venv\Scripts\python tests\test_exclusion.py
   .venv\Scripts\python src\run_variants.py --dataset ..\bioacoustics_dataset.csv
   ```
   Output: `results\tables\variant_results.csv`, `variant_recorder_results.csv`, `variant_effort_summary.csv`.
   Then write the event-count table (events used per variant and group):
   ```
   .venv\Scripts\python src\event_counts.py
   ```
   Output: `results\tables\event_counts.csv`. In it, `usable` means the event has a contrast, and `no_baseline` means it has none.

7. Run the placebo-in-time calibration for every variant (strict pool and secondary relaxed pool; needs step 6 first):
   ```
   .venv\Scripts\python tests\test_placebo_core.py
   .venv\Scripts\python src\run_placebos.py --dataset ..\bioacoustics_dataset.csv
   ```
   Checks printed: `clip-level recompute matches binned values for 29 events` (detection-excluded variants) and `Variant 1 strict-pool placebo reproduces the lead-code output.` Output: `results\tables\placebo_results.csv` and `placebo_pool_summary.csv`.

8. Apply the pre-registered decision rules (reads existing tables only; needs steps 6 and 7 first):
   ```
   .venv\Scripts\python tests\test_decision.py
   .venv\Scripts\python src\decision.py
   ```
   Output: `results\tables\decision_summary.csv` (verdict per variant and an OVERALL row) and `results\tables\recorder_coverage.csv`.

9. Week 5 diagnostics (needs steps 3 to 6 first):
   ```
   .venv\Scripts\python tests\test_diagnostics.py
   .venv\Scripts\python src\run_diagnostics.py --dataset ..\bioacoustics_dataset.csv
   ```
   Output: six figures in `results\figures\` and `results\tables\yamnet_split_events.csv`, `yamnet_split_summary.csv`, `yamnet_split_by_recorder.csv`.

10. Draw the blind listening sample:
   ```
   .venv\Scripts\python tests\test_listening.py
   .venv\Scripts\python src\listening_sample.py --dataset ..\bioacoustics_dataset.csv
   ```
   Output: `results\listening\review_sheet.csv` (for the reviewer) and `sample_key.csv` (labels and positions; keep it away from the reviewer). With the audio folder at hand, `src\prepare_listening_audio.py --audio-dir <wav folder> --output-dir <reviewer folder>` copies the clips under neutral names (L001.wav ...). After the review, `src\analyze_listening.py --sheet <completed sheet>` writes `results\tables\listening_summary.csv`.

11. Build the results table and the report (reads existing tables only; needs steps 8 and 9 first):
   ```
   .venv\Scripts\python tests\test_report.py
   .venv\Scripts\python src\make_report.py
   ```
   Output: `results\tables\results_table.csv` and `REPORT.md`.

Seeds are fixed in the scripts (placebo default 20251002). Results in `results/intermediate/` are regenerated, never edited by hand. Choices fixed before analysis are in `PREREGISTRATION.md`; later changes go in `DEVIATIONS.md`.

## Presentation

- Progress review deck (November 5, 2026 snapshot): `docs/Playback_Experiment_Progress_Review.pdf`. The HTML source is `docs/progress_review_source.html`. Its numbers are copied from `REPORT.md` and are not regenerated.

## Data

Raw data is not committed (large files, gitignored).
- `bioacoustics_dataset.csv`: clip-level data, includes the YAMNet `Human Activity` column. Checksum in `reference/dataset_checksum.txt`.
- `cleaned_df.csv` was in the original folder but is not used here.

## Repository layout

```
toucanet-playback-sensitivity/
  README.md  PREREGISTRATION.md  DEVIATIONS.md  REPORT.md
  requirements.txt
  configs/          # hypotheses file and one JSON per window variant
  data/             # gitignored
  docs/             # progress review deck (PDF and HTML source)
  reference/        # lead's reference outputs, dataset checksum, event spans
  results/
    tables/         # all result tables
    figures/        # per-recorder event diagnostics
    listening/      # review protocol, blind sheet, sample key
    intermediate/   # regenerated, gitignored
  src/
    lead/           # lead's scripts, unmodified
    *.py            # variants, placebo, decision rules, diagnostics, listening, report
  tests/            # unit tests for each module
  notebooks/        # unused so far
```

## References

- Playback Experiment (design document)
- Team Toucanet Fall Plan 2026
- Lead's `hypotheses.json` (received November 12, 2026)
- Lead feedback of November 12, 2026 and the field team's description of simulation events (relayed by Daan)
