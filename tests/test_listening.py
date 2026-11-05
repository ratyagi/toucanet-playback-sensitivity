"""Tests for the listening sample. Run: python tests/test_listening.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import listening_sample as ls  # noqa: E402
import analyze_listening as al  # noqa: E402


def fake_pool():
    rng = np.random.default_rng(1)
    rows = []
    for i in range(3000):
        rel = float(rng.integers(-598, 600))
        rows.append(dict(clip_name=f"c{i:05d}.wav", recorder=f"Audio_Moth_{1 + i % 6}", timestamp="x",
                         relative_seconds=rel, yamnet_label="Speech" if i % 10 == 0 else "no",
                         yamnet_score=0.5, yamnet_positive=(i % 10 == 0)))
    pool = pd.DataFrame(rows)
    pool["stratum"] = ls.position_stratum(pool["relative_seconds"])
    return pool


def test_allocate_sums_and_caps():
    a = ls.allocate(pd.Series({"a": 50, "b": 30, "c": 5}), 40)
    assert a.sum() == 40 and (a <= pd.Series({"a": 50, "b": 30, "c": 5})).all()
    small = ls.allocate(pd.Series({"a": 3, "b": 2}), 40)
    assert small.sum() == 5


def test_strata_edges():
    s = ls.position_stratum(pd.Series([-598.0, -361.0, -360.0, -1.0, 0.0, 119.0, 120.0, 599.0, 700.0]))
    assert list(s) == [0, 0, 1, 2, 2, 2, 3, 4, -1]


def test_sample_shape_and_balance():
    sample = ls.draw_sample(fake_pool())
    assert sample["yamnet_positive"].sum() == 100 and (~sample["yamnet_positive"]).sum() == 100
    neg = sample.loc[~sample["yamnet_positive"]]
    assert set(neg.groupby("stratum").size()) == {20}
    assert sample["clip_name"].is_unique
    assert sample["recorder"].nunique() == 6


def test_deterministic_and_seed_sensitive():
    pool = fake_pool()
    a, b = ls.draw_sample(pool), ls.draw_sample(pool)
    assert a.equals(b)
    assert not a["clip_name"].equals(ls.draw_sample(pool, seed=1)["clip_name"])


def test_pool_excludes_other_components_and_outside_window():
    clips = pd.DataFrame([
        dict(clip_name="a.wav", Recorder="r", Timestamp="t", **{"Sim Type": "['Human Presence on Trail']", "Sim Relative Time": "[10.0]"}, **{"Human Activity": "no", "Human Activity Score": 0.0}),
        dict(clip_name="b.wav", Recorder="r", Timestamp="t", **{"Sim Type": "['Human Presence on Trail', 'Vehicle']", "Sim Relative Time": "[10.0, 5.0]"}, **{"Human Activity": "no", "Human Activity Score": 0.0}),
        dict(clip_name="c.wav", Recorder="r", Timestamp="t", **{"Sim Type": "['Human Presence on Trail']", "Sim Relative Time": "[900.0]"}, **{"Human Activity": "no", "Human Activity Score": 0.0}),
        dict(clip_name="d.wav", Recorder="r", Timestamp="t", **{"Sim Type": "['Vehicle']", "Sim Relative Time": "[3.0]"}, **{"Human Activity": "no", "Human Activity Score": 0.0}),
        dict(clip_name="e.wav", Recorder="r", Timestamp="t", **{"Sim Type": "[]", "Sim Relative Time": "[]"}, **{"Human Activity": "no", "Human Activity Score": 0.0}),
    ])
    pool, info = ls.build_pool(clips)
    assert list(pool["clip_name"]) == ["a.wav"]
    assert info["clips_other_component_excluded"] == 1 and info["clips_outside_window_excluded"] == 1


def test_allocate_census_like_pool():
    pool = pd.Series({"m1": 3, "m2": 4, "m3": 0, "m4": 13, "m5": 9, "m6": 75})
    a = ls.allocate(pool, 100)
    assert a.sum() == 100 and a["m6"] == 72 and a["m4"] == 12 and "m3" not in a.index


def test_weights_restore_pool_sizes():
    pool = fake_pool()
    sample = ls.draw_sample(pool)
    neg_pool = pool.loc[~pool["yamnet_positive"]]
    neg = sample.loc[~sample["yamnet_positive"]]
    assert abs(neg["weight"].sum() - len(neg_pool)) < 1e-6
    pos = sample.loc[sample["yamnet_positive"]]
    assert abs(pos["weight"].sum() - pool["yamnet_positive"].sum()) < 1e-6


def test_review_sheet_hides_labels():
    sample = ls.draw_sample(fake_pool())
    sheet = sample[["blind_id"]].assign(audible="", notes="")
    assert list(sheet.columns) == ["blind_id", "audible", "notes"]


def test_wilson_and_summary():
    lo, hi = al.wilson(5, 10)
    assert 0.23 < lo < 0.24 and 0.76 < hi < 0.77
    joined = pd.DataFrame(dict(yamnet_positive=[True, True, False, False, False], stratum=[2, 2, 0, 0, 4],
                               audible=["yes", "no", "yes", "unsure", "no"], weight=[1.0, 1.0, 1.0, 1.0, 8.0]))
    t = al.summarise(joined).set_index("group")
    assert t.loc["yamnet_negative_all", "n"] == 3 and t.loc["yamnet_negative_all", "unsure"] == 1
    assert t.loc["yamnet_positive_all", "share_yes"] == 0.5
    assert abs(t.loc["yamnet_negative_all", "share_yes_pool_weighted"] - 0.1) < 1e-9  # 1 yes of weight 10


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
