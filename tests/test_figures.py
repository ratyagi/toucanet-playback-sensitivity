"""Tests for the figure script. Run: python tests/test_figures.py"""
import sys
import tempfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import make_figures as mf  # noqa: E402

T = REPO / "results" / "tables"


def test_every_variant_has_a_label_and_a_row():
    results = pd.read_csv(T / "results_table.csv")
    assert set(mf.ORDER) == set(results["variant"].unique())


def test_figures_are_drawn_from_the_tables():
    mf.plt.rcParams.update(mf.STYLE)
    with tempfile.TemporaryDirectory() as t:
        out = Path(t)
        mf.variants_figure(pd.read_csv(T / "results_table.csv"), out / "a.png")
        mf.placebo_figure(pd.read_csv(T / "placebo_results.csv"), out / "b.png")
        mf.loro_figure(pd.read_csv(T / "robustness_leave_one_recorder.csv"), out / "c.png")
        assert mf.count_model_figure(pd.read_csv(T / "robustness_count_model.csv"), out / "d.png")
        for name in "abcd":
            assert (out / f"{name}.png").stat().st_size > 10_000


def test_count_figure_is_skipped_without_the_week_9_columns():
    with tempfile.TemporaryDirectory() as t:
        old = pd.read_csv(T / "robustness_count_model.csv").drop(columns=["post_over_pre_rate_ratio"])
        assert mf.count_model_figure(old, Path(t) / "x.png") is False


def test_no_dashes_in_figure_text():
    source = (REPO / "src" / "make_figures.py").read_text(encoding="utf-8")
    assert "—" not in source and "–" not in source


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
