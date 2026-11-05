"""Tests for the Week 5 diagnostics helpers. Run: python tests/test_diagnostics.py"""
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import run_diagnostics as rd  # noqa: E402


def test_yamnet_bins_relative_to_floored_onset():
    onset = pd.Timestamp("2025-03-19 07:35:52")
    clips = pd.DataFrame({
        "Recorder": ["A", "A", "A", "B"],
        "clip_time": pd.to_datetime(["2025-03-19 07:31:00", "2025-03-19 07:50:00", "2025-03-19 04:00:00", "2025-03-19 07:31:00"]),
        "positive": [True, False, True, True],
    })
    events = pd.DataFrame({"event_id": ["e1"], "recorder": ["A"], "onset": [onset]})
    out = rd.yamnet_by_bin(clips, events).set_index("relative_minutes")
    assert out.loc[0.0, "yamnet_positive"] == 1      # 07:31 is in the 07:30 bin, relative 0
    assert out.loc[15.0, "yamnet_positive"] == 0     # 07:50 is in the 07:45 bin
    assert -180.0 not in out.index or out.loc[-180.0, "clips"] == 1
    assert out["clips"].sum() == 2  # 04:00 is -210 min, outside the window


def test_split_keeps_events_without_contrast():
    spans = pd.DataFrame({"event_id": ["e1", "e2"], "recorder": ["A", "A"], "is_presence": [True, True],
                          "has_yamnet_detection": [True, False], "yamnet_positive_clips": [3, 0]})
    contrasts = pd.DataFrame({"variant": ["v1"], "event_id": ["e1"], "analysis": ["primary_isolated"],
                              "contrast": [1.5], "pre_bins": [4], "post_bins": [4]})
    table = rd.split_table(contrasts, spans)
    assert len(table) == 2 and table.loc[table["event_id"] == "e2", "contrast"].isna().all()
    s = rd.split_summary(table.dropna(subset=["variant"]))
    assert int(s.loc[s["has_yamnet_detection"], "events_with_contrast"].iloc[0]) == 1


def test_split_has_all_events_group():
    spans = pd.DataFrame({"event_id": ["e1", "e2", "e3"], "recorder": ["A", "A", "B"], "is_presence": [True] * 3,
                          "has_yamnet_detection": [True, False, True], "yamnet_positive_clips": [3, 0, 1]})
    contrasts = pd.DataFrame({"variant": ["v1"] * 3, "event_id": ["e1", "e2", "e3"],
                              "analysis": ["primary_isolated", "primary_isolated", "robustness_overlapping"],
                              "contrast": [1.0, 3.0, 5.0], "pre_bins": [4] * 3, "post_bins": [4] * 3})
    s = rd.split_summary(rd.split_table(contrasts, spans))
    a = s.loc[(s["analysis"] == "all_events") & s["has_yamnet_detection"]].iloc[0]
    assert a["events"] == 2 and a["mean_contrast"] == 3.0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
