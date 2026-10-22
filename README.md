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
- [ ] Collect: `bioacoustics_dataset.csv`, existing baseline and matched-placebo code, the 29 event onset times, field-record playback end times.
- [ ] Reproduce the existing 0-60 estimate. Do not move on until it matches.
- [ ] Check all timestamps (dataset and field records) are in one timezone.
- [ ] Commit `PREREGISTRATION.md` (windows, exclusions, primary outcome, criteria) before running any variant.

### Week 2: Windows as config
- [ ] One function: window spec + exclusion rule in, pre/post rates out.
- [ ] Implement all 5 variants from the table above.

### Week 3: Placebo matching and event types
- [ ] Define placebo exclusions (see Open issues) and apply to every variant.
- [ ] Split isolated vs. overlapping events.
- [ ] Log usable events, clips, and recorders left under every rule.

### Week 4: Models
- [ ] Event-level delta + placebo permutation test (primary).
- [ ] Mixed-effects count model (secondary, cross-check).

### Week 5: Diagnostics
- [ ] Plot YAMNet score, call rate, taxa count around each event.
- [ ] Exploratory split: 22 events with a YAMNet detection vs. 7 without. Descriptive only.
- [ ] Manual listening on a stratified sample of YAMNet-positive and -negative clips. Fix the sample size up front.

### Week 6: Write-up
- [ ] One results table: variant x effect size x interval x N.
- [ ] One-page verdict using the criteria above.
- [ ] Feed the verdict into the December LODO comparison and recommendation.

## Open issues

- **Placebo exclusion gap:** placebo times have no playback, so YAMNet-positive clips are rare there, and "same exclusions" would only trim real-event windows. Proposed fix: drop the same relative clip positions (same minutes after onset) in matched placebo windows. Confirm with the team.
- **Playback duration:** 20 minutes is approximate. Use field-record end times where they exist.
- **Power:** only 7 events have no YAMNet detection. That comparison stays exploratory.
- **Baseline code:** not yet located. Needed before week 2.

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
