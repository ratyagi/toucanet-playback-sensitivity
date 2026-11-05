# Pre-registration: Playback Sensitivity Experiment

Status: DRAFT for review. Not yet committed. After the commit, windows, exclusions, outcomes, and criteria do not change. Any change goes in `DEVIATIONS.md` with a date and a reason.

Project: Team Toucanet, Kashmir World Foundation, Fall 2026.
Source design: `Playback Experiment.docx`.

## Question

Do estimated changes in animal acoustic activity persist after the playback period and after clips containing detectable human-related sound are removed?

## Hypotheses

- **Biological response:** call rate or taxa count changes after exposure, and the change remains when the playback interval and YAMNet-positive clips are excluded.
- **Direct sound:** the effect sits inside the playback interval, or disappears once YAMNet-positive and adjacent clips are removed.
- **Null:** changes around event times are comparable to ordinary variation at matched placebo times.

## Data

- File: `bioacoustics_dataset.csv`, not stored in git.
- SHA-256: `54a74d263b668adc2253eda261c1b1f532086d2671c94d3ccd467bb36e3a5aeb` (221,726,307 bytes). Check with `src/verify_dataset.py`.
- 631,321 clips of 3 seconds, 6 recorders, 5 days (2025-03-17 to 2025-03-21).
- Timestamps: clip filename times are local time at UTC-06:00 for all clips (checked against the dataset's local-time and UTC columns). No field records exist, so there is no second time source.
- YAMNet `Human Activity` is non-"no" in 168 of 10,636 human-presence simulation clips (1.6%).

## Exposure events

- Human-presence events (on trail and off trail): 29, reconstructed as clip timestamp minus `Sim Relative Time`.
- Event table: `reference/events.csv` (from the team lead). Our rerun of `event_study.py` must reproduce it exactly.
- The 27 on-trail events are labeled from -10 to +10 minutes around the reconstructed onset (about 400 clips); 5 of them have fewer clips because of recording gaps. The 2 off-trail events are labeled from 0 to +5 minutes (about 100 clips).
- 22 of 29 events have at least one YAMNet detection. 7 have none.

## Outcomes

- **Primary:** species-detection call rate per recorded minute (detections divided by clips x 3 / 60).
- **Secondary:** taxa count.
- Both are baseline-adjusted: bin value minus the median of clean bins for the same recorder and time of day.

## Contrast

- Contrast per event = mean residual in the response window minus mean residual in the 60 minutes before onset.
- Negative values support a drop.
- Time bins: 15 minutes, matching the reference analysis so its estimate can be reproduced exactly. The post-playback window therefore starts at 15 minutes, because 20 minutes does not align with the bin edges.

## Response-window variants

| # | Variant | Response window (minutes after onset) | Exclusion |
|---|---|---|---|
| 1 | Original | 0-60 | none |
| 2 | Post-playback | 15-60 | none |
| 2b | Post-playback, as written in the design document | 20-60, run at 5-minute bins | none |
| 3 | Buffered | 30-60 | none |
| 4a | Original, detection-excluded | 0-60 | clips with `Human Activity != "no"` and clips in the following 5 minutes, same recorder |
| 4b | Post-playback, detection-excluded | same as variant 2 | same as 4a |

- Variants are run exactly as listed. No windows are added after seeing results.
- Variant 2b is a secondary run at 5-minute bins. It follows the design document's 20-60 window exactly. It is not expected to reproduce the reference estimate, because bin size changes the baselines. Variant 2 (15-60) is its bin-aligned counterpart at the reference bin size.
- Playback timing: no field records exist. Event spans are derived from the dataset (`Sim Relative Time`) by a script in this repo, and the labeled window (-10 to +10 minutes around the reconstructed onset) is the exposure interval. Reading the onset as the midpoint of that window is pending confirmation from the team lead.

## Populations

- **Primary:** isolated events, meaning the full -3h/+12h path is recorded and no other human-presence onset falls inside it.
- **Robustness:** overlapping events, meaning full path recorded and another human-presence onset inside the window.
- Events with an incomplete path are excluded from both. The count is reported for every variant.

## Analysis

- **Model:** random-intercept model on event contrasts, recorder as the grouping effect, one-sided test for a drop, Holm adjustment across the primary and secondary outcome.
- **Placebo calibration:** matched placebo-in-time draws on days with no simulated events, same recorder, within 30 clock minutes, 1,000 replicates, fixed seed.
- **Exclusion fairness:** in the detection-excluded variants, the clip positions removed from each real event window are removed from its matched placebo windows too, so the placebo null has the same coverage and noise as the real windows.
- Per-recorder results are reported next to every pooled result.
- The reference test is one-sided (drop). The design document states its hypotheses as changes in either direction, so two-sided p-values are reported alongside and are the ones used in the decision rules below.
- Secondary placebo sensitivity: candidates may come from any day for the same recorder, within 30 clock minutes of the event time, with the analysis window free of any simulated component. Earlier playbacks may carry over to later days, so this is reported as a sensitivity analysis and not as the primary placebo.
- Reference result to reproduce before any variant runs: primary isolated 0-60 call-rate estimate -0.41 (SE 0.87, 10 events, 6 recorders, one-sided p 0.32, ICC 0.64).

## Interpretation criteria

- **Biological response:** direction and approximate size of the effect stay consistent across variants 2, 3, 4a, and 4b, and are unusual relative to placebo.
- **Direct contamination:** the effect is present in variant 1 but becomes substantially smaller, reverses, or disappears in the others. A larger effect among events with many YAMNet detections also counts toward this.
- **Inconclusive:** estimates are imprecise across variants. Reported as inconclusive, never as "no effect".
- The design document gives no numeric thresholds, so the following rules are fixed in advance:
  - **Gate:** the original analysis (variant 1, primary isolated, call rate) must show a detectable change, meaning two-sided p < 0.05 in the random-intercept model. If it does not, the result is reported as inconclusive because there is no detectable original effect to attribute. The other variants are then reported descriptively, without interpretation.
  - **Comparison:** if the gate is passed, each of variants 2, 2b, 3, 4a, and 4b is compared with variant 1 through the ratio of estimates. Consistent: same sign and ratio of at least 0.5. Substantially smaller: ratio between 0 and 0.5. Reversed: opposite sign.
  - **Biological response:** all five variants are consistent, and the variant 2 estimate lies outside the 95% placebo range where a placebo exists.
  - **Direct contamination:** at least two of the five variants are substantially smaller or reversed.
  - **Any other pattern** is reported as mixed and inconclusive.
  - The minimum detectable effect (about 1.96 times the standard error) is reported with every result.

## Known limitations (stated in advance)

- Only 5 days of recording, so time-of-day baselines rest on very few days.
- Audio_Moth_5 and Audio_Moth_6 (16 of 29 events) have no presence-free days, so strict placebo controls do not exist for them.
- 7 of 29 events have an incomplete -3h/+12h path.
- YAMNet non-detection does not prove a playback was inaudible.
- Power is low. With the reference standard error of 0.87 (10 isolated events), only changes of about 1.7 calls per minute or more are detectable at two-sided p < 0.05.
- The 7 events without a detection are too few for a significance test. That comparison is exploratory.
- The lead's `hypotheses.json` was not available. Results run from our reconstructed `configs/hypotheses_draft.json` are labeled as draft.

## Quality checks

- Report usable events, clips, and recorders under every exclusion rule.
- Plot YAMNet score, call rate, and taxa count around each event.
- Manually review 100 YAMNet-positive and 100 YAMNet-negative simulation clips (about 10 minutes of audio), drawn with a fixed seed. Positives are stratified by recorder. Negatives are stratified by recorder and by position in the labeled window (five 4-minute strata). The reviewer is blind to the YAMNet label and the clip position, and records whether playback is audible (yes, no, unsure). The review estimates how often YAMNet misses audible playback and when playback is audible within the labeled window. It is descriptive and does not enter the decision rules.
- Apply the same exclusions to real and placebo windows.
