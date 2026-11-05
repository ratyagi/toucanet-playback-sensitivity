# Blind listening review: protocol

Purpose: estimate how often YAMNet misses audible playback, and where in the labeled window playback is audible. Descriptive. It does not enter the decision rules.

## Reviewer
- Reviewer: the experiment owner. This is weaker than an independent reviewer, so the report states it. Blinding is kept on the two things that could bias the call: each clip's YAMNet label and its position in the window.

## Before listening
- Do not open `sample_key.csv` until the sheet is complete.
- Make the neutral folder: `python src/prepare_listening_audio.py --audio-dir <wav folder> --output-dir <review folder>`. Clips become L001.wav to L200.wav, in random order.
- Use headphones, the same volume, one quiet sitting if possible.

## For each clip
- Listen up to twice. Do not look at the spectrogram.
- Fill `audible` in `review_sheet.csv` with one of:
  - `yes`: simulated human presence is clearly audible (voice, footsteps, equipment).
  - `unsure`: something may be human-made but it could be wind, insects, or noise.
  - `no`: nothing human-made.
- Use `notes` for anything unusual (another sound source, clipping, silence).

## After listening
- Save the completed sheet as `results/listening/review_sheet_completed.csv`. Do not edit answers after the summary has been seen.
- Run `python src/analyze_listening.py --sheet results/listening/review_sheet_completed.csv`.
- Commit the completed sheet and `results/tables/listening_summary.csv`, then rerun `src/make_report.py`.
