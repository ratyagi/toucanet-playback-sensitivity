"""Tests for the pre-registered decision rules. Run: python tests/test_decision.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import decision as d  # noqa: E402

VARIANTS = [d.GATE_VARIANT, *d.COMPARED]


def model(estimates, p_v1):
    rows = []
    for v, e in zip(VARIANTS, estimates):
        rows.append(dict(variant=v, n_events=10, n_recorders=6, estimate=e, standard_error=1.0,
                         two_sided_p=p_v1 if v == d.GATE_VARIANT else 0.5,
                         minimum_detectable_effect=1.96))
    return pd.DataFrame(rows)


def placebo(q025, q975):
    return pd.DataFrame([dict(variant=d.PLACEBO_REFERENCE, events=5, observed=0.0, null_q025=q025,
                              null_q975=q975, p_two_sided=0.5)])


def verdict(estimates, p_v1, plc):
    return d.decide(model(estimates, p_v1), plc).attrs["verdict"]


def test_gate_fails():
    assert verdict([-2, -2, -2, -2, -2, -2], 0.64, placebo(-1, 1)) == "inconclusive_gate_not_passed"
    t = d.decide(model([-2] * 6, 0.64), placebo(-1, 1))
    assert set(t.loc[t["variant"].isin(d.COMPARED), "comparison"]) == {"descriptive_only"}


def test_gate_boundary():
    assert verdict([-2] * 6, 0.05, placebo(-1, 1)) == "inconclusive_gate_not_passed"


def test_biological():
    assert verdict([-2, -2, -1.5, -1.2, -2.2, -1.8], 0.01, placebo(-1, 1)) == "biological_response"


def test_consistent_but_inside_placebo_is_mixed():
    assert verdict([-2, -2, -1.5, -1.2, -2.2, -1.8], 0.01, placebo(-3, 3)) == "mixed_inconclusive"


def test_contamination():
    assert verdict([-2, -0.2, 0.5, -1.5, -1.5, -1.5], 0.01, placebo(-1, 1)) == "direct_contamination"


def test_one_smaller_is_mixed():
    assert verdict([-2, -0.2, -1.5, -1.5, -1.5, -1.5], 0.01, placebo(-1, 1)) == "mixed_inconclusive"


def test_ratio_classes():
    assert d.classify_ratio(-1.0, -2.0) == "consistent"
    assert d.classify_ratio(-0.9, -2.0) == "substantially_smaller"
    assert d.classify_ratio(1.0, -2.0) == "reversed"
    assert d.classify_ratio(1.0, 0.0) == "not_evaluable"


def test_real_tables_are_inconclusive():
    res = pd.read_csv(REPO / "results" / "tables" / "variant_results.csv")
    m = res[(res["method"] == "primary") & (res["analysis"] == d.ANALYSIS) & (res["hypothesis"] == d.HYPOTHESIS)]
    plc = pd.read_csv(REPO / "results" / "tables" / "placebo_results.csv")
    plc = plc[(plc["pool"] == "strict") & (plc["analysis"] == d.ANALYSIS) & (plc["hypothesis"] == d.HYPOTHESIS)]
    assert d.decide(m, plc).attrs["verdict"] == "inconclusive_gate_not_passed"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
