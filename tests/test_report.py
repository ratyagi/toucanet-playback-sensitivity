"""Tests for the report builder. Run: python tests/test_report.py"""
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import make_report as mr  # noqa: E402

T = REPO / "results" / "tables"


def build():
    return mr.build_report(pd.read_csv(T / "variant_results.csv"), pd.read_csv(T / "decision_summary.csv"),
                           pd.read_csv(T / "placebo_results.csv"), pd.read_csv(T / "variant_recorder_results.csv"),
                           pd.read_csv(T / "yamnet_split_summary.csv"),
                           (REPO / "reference" / "dataset_checksum.txt").read_text().split()[0])


def test_table_shape_and_interval():
    t = mr.results_table(pd.read_csv(T / "variant_results.csv"))
    assert len(t) == 12  # 6 variants x 2 hypotheses
    assert ((t["ci_high"] - t["ci_low"]) / 2 / t["standard_error"] - 1.96).abs().max() < 1e-9
    assert (t["n_events"] > 0).all()


def test_report_matches_tables():
    text = build()
    assert "## Verdict: Inconclusive" in text
    v1 = mr.results_table(pd.read_csv(T / "variant_results.csv")).query("variant_id == '1' and hypothesis == 'primary_call_rate'").iloc[0]
    assert f"{v1['estimate']:+.2f}" in text and f"{v1['two_sided_p']:.2f}" in text


def test_report_style():
    text = build()
    assert "—" not in text and "–" not in text  # no em or en dashes
    assert "honest" not in text.lower()
    assert len(text.splitlines()) < 90  # one page


def test_verdict_labels():
    text = build()
    assert "DRAFT" in text and "pending" in text


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
