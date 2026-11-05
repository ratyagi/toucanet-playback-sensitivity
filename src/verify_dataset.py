#!/usr/bin/env python3
"""Compute or verify the SHA-256 checksum of the dataset.

The dataset is not stored in git. The expected checksum is committed in
reference/dataset_checksum.txt so anyone can confirm they hold the same file.

  Write:   python src/verify_dataset.py PATH_TO_CSV --write
  Verify:  python src/verify_dataset.py PATH_TO_CSV
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

DEFAULT_CHECKSUM_FILE = Path(__file__).resolve().parents[1] / "reference" / "dataset_checksum.txt"


def sha256_of(path: Path, block_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--checksum-file", type=Path, default=DEFAULT_CHECKSUM_FILE)
    parser.add_argument("--write", action="store_true", help="record the checksum instead of verifying it")
    args = parser.parse_args()

    actual = sha256_of(args.dataset)
    size = args.dataset.stat().st_size
    if args.write:
        args.checksum_file.parent.mkdir(parents=True, exist_ok=True)
        args.checksum_file.write_text(f"{actual}  {args.dataset.name}  {size} bytes\n", encoding="utf-8")
        print(f"Wrote {args.checksum_file}\n{actual}")
        return 0

    if not args.checksum_file.exists():
        print(f"No checksum file at {args.checksum_file}. Run with --write first.")
        return 2
    expected = args.checksum_file.read_text(encoding="utf-8").split()[0]
    if actual == expected:
        print("OK: dataset matches the recorded checksum.")
        return 0
    print(f"MISMATCH\n expected {expected}\n actual   {actual}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
