#!/usr/bin/env python3
"""Compare two output folders of the lead's placebo script, file by file.

Used to show that a change of input (for example the lead's hypotheses.json replacing our
reconstructed draft) changes nothing. CSV files are compared cell by cell (numbers to a tight
tolerance), Markdown files line by line ignoring line endings. Images are skipped.
The exit code is 1 if any file differs or is missing from one side.

  python src/compare_runs.py results/intermediate/placebo results/intermediate/placebo_lead_hypotheses
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RTOL = 1e-9
ATOL = 1e-12


def compare_csv(a: Path, b: Path) -> str | None:
    left, right = pd.read_csv(a), pd.read_csv(b)
    if list(left.columns) != list(right.columns):
        return "columns differ"
    if left.shape != right.shape:
        return f"shape differs: {left.shape} vs {right.shape}"
    for column in left.columns:
        x, y = left[column], right[column]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            same = np.isclose(x.to_numpy(float), y.to_numpy(float), rtol=RTOL, atol=ATOL, equal_nan=True)
        else:
            same = (x.astype(str) == y.astype(str)).to_numpy()
        if not same.all():
            return f"column {column!r} differs in {int((~same).sum())} rows"
    return None


def compare_text(a: Path, b: Path) -> str | None:
    left = a.read_text(encoding="utf-8").splitlines()
    right = b.read_text(encoding="utf-8").splitlines()
    return None if left == right else "text differs"


def compare_folders(folder_a: Path, folder_b: Path) -> list[tuple[str, str]]:
    """Return (file, problem) pairs. An empty list means the folders match."""
    problems = []
    names_a = {p.name for p in folder_a.iterdir() if p.suffix in {".csv", ".md"}}
    names_b = {p.name for p in folder_b.iterdir() if p.suffix in {".csv", ".md"}}
    for name in sorted(names_a ^ names_b):
        problems.append((name, "present in only one folder"))
    for name in sorted(names_a & names_b):
        compare = compare_csv if name.endswith(".csv") else compare_text
        problem = compare(folder_a / name, folder_b / name)
        if problem:
            problems.append((name, problem))
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder_a", type=Path)
    parser.add_argument("folder_b", type=Path)
    args = parser.parse_args()
    problems = compare_folders(args.folder_a, args.folder_b)
    checked = sorted(p.name for p in args.folder_a.iterdir() if p.suffix in {".csv", ".md"})
    for name in checked:
        problem = dict(problems).get(name)
        print(f"{'DIFFERENT' if problem else 'identical'}  {name}" + (f"  ({problem})" if problem else ""))
    for name, problem in problems:
        if name not in checked:
            print(f"DIFFERENT  {name}  ({problem})")
    if problems:
        print(f"{len(problems)} file(s) differ.")
        sys.exit(1)
    print(f"All {len(checked)} CSV and Markdown outputs are identical.")


if __name__ == "__main__":
    main()
