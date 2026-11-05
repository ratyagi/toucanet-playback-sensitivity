# toucanet-playback-sensitivity

Tests whether the apparent acoustic response to simulated human presence is a biological change in animal vocal activity, or just the playback sound being picked up in the recordings.

Part of Team Toucanet (Kashmir World Foundation), Fall 2026. Feeds Fall Plan next step 2 (stability vs. ecological interpretability) and the December go/no-go on the current embedding paradigm.

## Why this matters

- If the effect disappears once playback and YAMNet-positive clips are excluded, the signal is mostly a human-sound detector, not an ecological response.
- That is a "no" on the interpretability question and affects any recommendation to scale the current pipeline.
- YAMNet flags human sound in only 168 of 10,636 simulation clips (1.6%), but at least one detection falls in 22 of 29 events (76%).
- Sparse within events, concentrated around them. A clip with no detection does not prove the playback was inaudible.

## Research question

Do estimated changes in animal acoustic activity persist after the playback period and after clips with detectable human-related sound are removed?

## Hypotheses

- **Biological response:** call rate or taxa richness changes after exposure, and the change holds with playback and YAMNet-positive clips excluded.
- **Direct sound:** the effect sits inside the playback interval, or disappears once positive and adjacent clips are removed.
- **Null:** changes around events match ordinary variation at matched placebo times.

## Analysis design

- Exposure events: the 29 reconstructed human-presence events.
- Baseline: existing recorder-specific, time-of-day baseline with matched placebo times.
- Comparison: mean activity in each response window vs. the 60 minutes before onset.
- Primary outcome: species-detection call rate per recorded minute (divide by recorded minutes, not clip count).
- Secondary outcome: taxa count.
- Recorder is a grouping effect.
- Isolated events are primary. Events overlapping another event are a robustness analysis.

| Variant | Window (min after onset) | Exclusion |
|---|---|---|
| 1. Original | 0-60 | none |
| 2. Post-playback | 20-60 (or documented playback end to 60) | none |
| 3. Buffered | 30-60 | none |
| 4a. Original, detection-excluded | 0-60 | clips with `Human Activity != "no"` + next 5 min |
| 4b. Post-playback, detection-excluded | 20-60 | same as above |

Statistics:
- Primary: per-event (post rate minus pre rate), compared against the placebo delta distribution with a permutation test.
- Secondary: mixed-effects count model, recorder random intercept, log recorded minutes as offset.
- Report effect sizes and intervals, not only p-values. N is small.

## Interpretation criteria

- **Biological:** direction and rough size of the effect stay consistent across post-playback, buffered, and detection-excluded variants, and are unusual vs. placebo.
- **Direct contamination:** effect present at 0-60 but much smaller, reversed, or gone in the other variants. A larger effect among events with many YAMNet detections also points here.
- **Inconclusive:** wide intervals across all variants. Report as inconclusive, never as "no effect".

## Plan

### Week 1: Inputs and setup
- [x] Collect: `bioacoustics_dataset.csv`, existing baseline and matched-placebo code, the 29 event onset times, field-record playback end times.
- [x] Reproduce the existing 0-60 estimate. Do not move on until it matches.
- [x] Check all timestamps (dataset and field records) are in one timezone.
- [x] Commit `PREREGISTRATION.md` (windows, exclusions, primary outcome, criteria) before running any variant.

### Week 2: Windows as config
- [x] One config per variant (`configs/variants/`) and a runner (`src/run_variants.py`) that takes window spec + exclusion rule and returns the contrasts and models.
- [x] YAMNet exclusion filter (`src/exclusion.py`, tested in `tests/`).
- [x] All 6 variants implemented (the 5 in the table plus 2b: 20-60 at 5-minute bins). Variant 1 reproduces the reference results.

### Week 3: Placebo matching and event types
- [x] Define placebo exclusions (strict pool as primary, relaxed pool as sensitivity) and apply to every variant, with position-matched clip drops in the detection-excluded variants.
- [x] Split isolated vs. overlapping events.
- [x] Log usable events, clips, and recorders left under every rule (`results/tables/placebo_pool_summary.csv`, `variant_effort_summary.csv`).

### Week 4: Models
- [x] Event-level delta + placebo permutation test (primary): the pre-registered decision rules are applied in `src/decision.py` to the Week 2 models and Week 3 placebo tables (`results/tables/decision_summary.csv`).
- [ ] Mixed-effects **count** model (secondary, cross-check, log recorded minutes as offset). Not done: the Week 2 models are linear mixed models on the baseline-adjusted deviation (call rate and taxa count). The linear fits are reported next to the placebo result with the minimum detectable effect on every row, but they are not the count model in the plan. See `DEVIATIONS.md`.
- [x] Per-recorder view of the primary test (`results/tables/recorder_coverage.csv`).
- Result: the gate fails (variant 1, two-sided p = 0.64), so the verdict is **inconclusive** and the other variants are descriptive.

### Week 5: Diagnostics
- [x] Plot YAMNet-positive clips, call rate, and taxa count around each human-presence event (`results/figures/event_diagnostics_<recorder>.png`).
- [x] Exploratory split: 22 events with a YAMNet detection vs. 7 without. Descriptive only (`results/tables/yamnet_split_events.csv`, `yamnet_split_summary.csv`, `yamnet_split_by_recorder.csv`). The split is confounded with recorder.
- [x] Listening sample drawn with a fixed seed (100 YAMNet-positive, 100 YAMNet-negative; `results/listening/`). Note the positive pool has only 104 clips.
- [ ] Blind listening review done by a reviewer, then summarised with `src/analyze_listening.py`.

### Week 6: Write-up
- [x] One results table: variant x effect size x interval x N (`results/tables/results_table.csv`).
- [x] One-page verdict using the criteria above (`REPORT.md`, generated from the tables; draft until the listening review and the lead's hypotheses file arrive).
- [ ] Feed the verdict into the December LODO comparison and recommendation.

## Open issues

- **Placebo exclusion gap:** placebo times have no playback, so YAMNet-positive clips are rare there, and "same exclusions" would only trim real-event windows. Proposed fix: drop the same relative clip positions (same minutes after onset) in matched placebo windows. Confirm with the team.
- **Playback duration:** 20 minutes is approximate. Use field-record end times where they exist.
- **Power:** only 7 events have no YAMNet detection. That comparison stays exploratory.
- **Baseline code:** not yet located. Needed before week 2.

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
4. Run the contrast, model, and placebo script (needs a hypotheses file; the draft is `configs/hypotheses_draft.json`):
   ```
   .venv\Scripts\python src\lead\placebo_hypothesis_analysis.py --input-dir results\intermediate --output-dir results\intermediate\placebo --hypotheses configs\hypotheses_draft.json
   ```
   Check: primary isolated call-rate estimate near -0.41 with 10 events and 6 recorders, matching `reference/mixed_effects_results.csv`.

5. Derive each event's labeled span and YAMNet detection count:
   ```
   .venv\Scripts\python src\derive_event_spans.py --dataset ..\bioacoustics_dataset.csv --events reference\events.csv --output reference\event_spans.csv
   ```
   Check: it reports 61 events matched, 29 human-presence events, 22 of 29 with a YAMNet detection, and 168 YAMNet-positive clips.

6. Run the unit tests, then all six response-window variants (variant 1 must reproduce the reference, or the run stops):
   ```
   .venv\Scripts\python tests\test_exclusion.py
   .venv\Scripts\python src\run_variants.py --dataset ..\bioacoustics_dataset.csv
   ```
   Output: `results\tables\variant_results.csv`, `variant_recorder_results.csv`, `variant_effort_summary.csv`.

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
- `bioacoustics_dataset.csv`: clip-level data, includes the YAMNet `Human Activity` column.
- `cleaned_df.csv`: cleaned version, confirm how it differs before using it.

## Planned layout

```
toucanet-playback-sensitivity/
  README.md
  PREREGISTRATION.md
  data/            # gitignored
  configs/         # window and exclusion specs
  src/             # window function, placebo matching, models
  notebooks/       # diagnostics and plots
  results/         # tables, figures
```

## References

- Playback Experiment (design doc)
- Team Toucanet Fall Plan 2026
