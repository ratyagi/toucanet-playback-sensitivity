"""Run with: python tests/test_placebo_core.py (or pytest)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from placebo_core import ClipContext, balanced_mean, empirical_p, position_index, simulate_null  # noqa: E402

START = pd.Timestamp("2025-03-17 08:00:00")


def parse(text):
    return [] if text == "[]" else text.split("|")


def make_context(drop_positions=()):
    times = [START + pd.Timedelta(seconds=3 * i) for i in range(-300, 1500)]  # 1,800 clips
    clips = pd.DataFrame(
        {
            "Recorder": "A",
            "clip_time": times,
            "species": ["x|y" if i % 2 == 0 else "[]" for i in range(len(times))],
            "drop": [(i - 300) in drop_positions for i in range(len(times))],
        }
    )
    return ClipContext(clips, parse)


def test_position_index_steps_of_three_seconds():
    times = np.array([START + pd.Timedelta(seconds=s) for s in (0, 2, 3, 5, 6)], dtype="datetime64[ns]")
    assert position_index(times, START).tolist() == [0, 0, 1, 1, 2]
    assert position_index(np.array([(START - pd.Timedelta(seconds=3)).to_datetime64()]), START).tolist() == [-1]


def test_balanced_mean_averages_recorders_not_events():
    values = np.array([1.0, 1.0, 1.0, 5.0])
    assert balanced_mean(values, np.array([0, 0, 0, 1])) == 3.0  # (1 + 5) / 2
    assert np.isnan(balanced_mean(np.array([np.nan]), np.array([0])))
    assert balanced_mean(np.array([1.0, np.nan, 3.0]), np.array([0, 0, 1])) == 2.0


def test_null_is_reproducible_and_seed_dependent():
    pools = [{"h": np.array([0.0, 1.0, 2.0])}, {"h": np.array([5.0, 6.0])}]
    codes = np.array([0, 1])
    first = simulate_null(pools, codes, ["h"], 50, 7)["h"]
    again = simulate_null(pools, codes, ["h"], 50, 7)["h"]
    other = simulate_null(pools, codes, ["h"], 50, 8)["h"]
    assert np.array_equal(first, again) and not np.array_equal(first, other)
    assert first.min() >= 2.5 and first.max() <= 4.0


def test_empirical_p_counts_with_plus_one():
    null = np.arange(10.0)
    p = empirical_p(null, 0.0)
    assert p["p_less"] == 2 / 11 and p["p_greater"] == 1.0 and p["p_two_sided"] == 4 / 11


def test_removal_pattern_and_matched_drop():
    event_drops = {10, 11, 12}
    event_ctx = make_context(event_drops)
    pattern = event_ctx.removal_pattern("A", START, -60, 60)
    assert pattern == event_drops
    placebo_ctx = make_context(())
    baseline = {("A", 480): (0.0, 0.0)}
    kept_all = placebo_ctx.path("A", START, [0], 15, set(), baseline)["clips"].iloc[0]
    kept_matched = placebo_ctx.path("A", START, [0], 15, pattern, baseline)["clips"].iloc[0]
    assert kept_all == 300 and kept_matched == 297


def test_path_without_extra_drops_matches_clip_counts():
    ctx = make_context({10, 11})
    row = ctx.path("A", START, [0, 15], 15, set(), {("A", 480): (1.0, 1.0), ("A", 495): (1.0, 1.0)}).iloc[0]
    assert row["clips"] == 298
    assert abs(row["call_rate_deviation"] - (149 * 2 / (298 * 3 / 60) - 1.0)) < 1e-9


if __name__ == "__main__":
    for name, func in list(globals().items()):
        if name.startswith("test_"):
            func()
            print("ok", name)
