# Provenance of the lead's scripts

These two scripts were written by the team lead. They are copied here so the analysis can be reproduced from this repository alone. The lead confirmed on November 12, 2026 that they may stay in the repository, on the condition that their provenance and any modifications are documented.

| File | SHA-256 (line endings normalized to LF) | Source | Modified here? |
|---|---|---|---|
| `event_study.py` | `c3d8e4a28143b54264249d8a3f56b0891b711927e6f54df38ce377fddac45cd8` | Supplied by the team lead, October 2026 | No |
| `placebo_hypothesis_analysis.py` | `ad16dffd637692b1019368d0b3c43d1c420222f965d0c0856c903e7f08036166` | Supplied by the team lead, October 2026 | No |

## How the scripts are used

- `event_study.py` is run as is (README step 3). Its events table reproduces the lead's `reference/events.csv`.
- `placebo_hypothesis_analysis.py` is run as is (README step 4). With the lead's `configs/hypotheses.json` its outputs are identical to the run on our earlier reconstructed draft (checked November 19, 2026 with `src/compare_runs.py`).
- `src/run_variants.py`, `src/run_placebos.py`, and `src/decision.py` import functions from these files by path. They never edit them.

## Rules

- No modification has been made in this repository. If one is ever needed, make it in a copy outside `src/lead/` or log it here with the date, the diff, and the reason.
- `tests/test_provenance.py` recomputes the hashes above. A changed file makes the test fail.
