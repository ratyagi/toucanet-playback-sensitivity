# Provenance of the reference files and inputs

| File | SHA-256 (line endings normalized to LF) | Origin |
|---|---|---|
| `events.csv` | `715aa706f8a8e9ae7f3871fb0de69f98ea1655603521966d3ea57fd1ac661f12` | Supplied by the team lead. Our rerun of `event_study.py` reproduces it (README step 3). |
| `mixed_effects_results.csv` | `1eccdbbcde832e1037ea93f952392011d4aa9f470c192dd1fb3e163cbbe96933` | Supplied by the team lead. Variant 1 reproduces it (README steps 4 and 6). |
| `between_recorder_heterogeneity.csv` | `2969dbc0d045a31b5f2dbe9f79f57f6c85159589e141e08913bc3f1bff9f7b46` | Supplied by the team lead. Identical to our rerun. |
| `event_spans.csv` | `26b813af67789997573c2f005ac98f2d4251ab73ab8cd83bf440f893bcab9c6a` | Derived here by `src/derive_event_spans.py` (README step 5). |
| `placebo_lead_code_output.csv` | `468e91f8b326d1428bc137c42550f81de7d734d7c1d7914188e35bf907f55bfd` | Output of the lead's placebo script on our draft configuration (Week 3). Used as the check target in `src/run_placebos.py`. |
| `dataset_checksum.txt` | `07c7e0e84b1cf8ab0ee12d4d17bd6b74908ebb5082f270ec79d7421a1dbe85c4` | Recorded here from the dataset file (`src/verify_dataset.py`). |
| `../configs/hypotheses.json` | `380b032eda16ced85c90b30e307e41c9fbfe320ca559aefc1fa073ef9c75c5f5` | Supplied by the team lead, November 12, 2026. Unmodified. |
| `../configs/hypotheses_draft.json` | `331a464467d09c46488b4bb428cd4a6b3fb08bd75c0136d975369238430e4d8c` | Reconstructed by us from the lead's script before his file arrived. Superseded, kept for the record. |

- The raw dataset is not in git. Its SHA-256 is in `dataset_checksum.txt`.
- Hashes are taken after replacing Windows line endings (CRLF) with LF, so they match on every operating system.
