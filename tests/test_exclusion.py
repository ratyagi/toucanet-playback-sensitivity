"""Run with: python tests/test_exclusion.py (or pytest)."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from exclusion import yamnet_exclusion_mask  # noqa: E402


def make_clips(recorder: str, seconds: list[int], positive_at: set[int]) -> pd.DataFrame:
    start = pd.Timestamp("2025-03-17 08:00:00")
    return pd.DataFrame(
        {
            "Recorder": recorder,
            "clip_time": [start + pd.Timedelta(seconds=s) for s in seconds],
            "Human Activity": ["Speech" if s in positive_at else "no" for s in seconds],
        }
    )


def test_tail_is_dropped_and_rest_kept():
    seconds = list(range(0, 900, 3))
    clips = make_clips("A", seconds, {30})
    drop = yamnet_exclusion_mask(clips, 300)
    dropped = [s for s, d in zip(seconds, drop) if d]
    assert min(dropped) == 30 and max(dropped) == 330  # positive clip plus 300 seconds
    assert not drop[clips["clip_time"] < pd.Timestamp("2025-03-17 08:00:30")].any()


def test_recorders_are_independent():
    seconds = list(range(0, 900, 3))
    clips = pd.concat([make_clips("A", seconds, {30}), make_clips("B", seconds, set())], ignore_index=True)
    drop = yamnet_exclusion_mask(clips, 300)
    assert drop[clips["Recorder"] == "B"].sum() == 0
    assert drop[clips["Recorder"] == "A"].sum() > 0


def test_overlapping_tails_merge():
    seconds = list(range(0, 1200, 3))
    drop = yamnet_exclusion_mask(make_clips("A", seconds, {30, 240}), 300)
    dropped = [s for s, d in zip(seconds, drop) if d]
    assert min(dropped) == 30 and max(dropped) == 540


def test_no_positives_drops_nothing():
    clips = make_clips("A", list(range(0, 300, 3)), set())
    assert yamnet_exclusion_mask(clips, 300).sum() == 0


if __name__ == "__main__":
    for name, func in list(globals().items()):
        if name.startswith("test_"):
            func()
            print("ok", name)
