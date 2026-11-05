#!/usr/bin/env python3
"""Copy the sampled clips into a folder with neutral names (L001.wav ...).

The original file names contain the recorder and clock time. Neutral names keep the reviewer
blind to YAMNet label and clip position. Audio is not part of the repository.

  python src/prepare_listening_audio.py --audio-dir PATH_WITH_WAVS --output-dir PATH_FOR_REVIEWER
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--key", type=Path, default=REPO / "results" / "listening" / "sample_key.csv")
    args = parser.parse_args()

    key = pd.read_csv(args.key)
    found = {p.name: p for p in args.audio_dir.rglob("*.wav")}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    missing = []
    for row in key.itertuples():
        source = found.get(row.clip_name)
        if source is None:
            missing.append(row.clip_name)
            continue
        shutil.copy2(source, args.output_dir / f"{row.blind_id}.wav")
    print(f"Copied {len(key) - len(missing)} of {len(key)} clips to {args.output_dir}")
    if missing:
        print(f"Missing {len(missing)} clips, first five: {missing[:5]}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
