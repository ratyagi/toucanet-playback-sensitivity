"""Tests for the Week 9 robustness checks on simulated data. Run: python tests/test_robustness.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import robustness as rb  # noqa: E402


def simulate_counts(true_rr, seed=1, n_event_bins=300):
    """Counts with recorder levels, a daily cycle, NB2 noise, and a known post-window rate ratio."""
    rng = np.random.default_rng(seed)
    rows = []
    recorders = [f"R{i}" for i in range(6)]
    for r_i, rec in enumerate(recorders):
        for day in range(5):
            for tod in range(0, 1440, 15):
                rate = np.exp(1.0 + 0.2 * r_i + 0.6 * np.sin(2 * np.pi * tod / 1440) + 0.3 * np.cos(4 * np.pi * tod / 1440))
                rows.append((rec, f"2025-03-{17 + day}", tod, 15.0, rate, "baseline"))
    for k in range(n_event_bins):
        rec, tod = recorders[k % 6], (k * 45) % 1440
        rate = np.exp(1.0 + 0.2 * (k % 6) + 0.6 * np.sin(2 * np.pi * tod / 1440) + 0.3 * np.cos(4 * np.pi * tod / 1440))
        role = "pre" if k % 2 == 0 else "post"
        rows.append((rec, f"2025-03-{17 + k % 5}", tod, 15.0, rate * (true_rr if role == "post" else 1.0), role))
    d = pd.DataFrame(rows, columns=["recorder", "date", "tod_bin", "recorded_minutes", "rate", "role"])
    mean = d["rate"] * d["recorded_minutes"]
    alpha = 0.4
    d["count"] = rng.negative_binomial(1 / alpha, 1 / (1 + alpha * mean))
    return d.drop(columns="rate")


def test_count_model_recovers_a_known_rate_ratio():
    for true_rr in (0.6, 1.0):
        out = rb.fit_count_model(simulate_counts(true_rr))
        assert out["estimable"] and out["converged"], out
        assert out["ci_low"] < true_rr < out["ci_high"], (true_rr, out)
        assert abs(np.log(out["rate_ratio"]) - np.log(true_rr)) < 0.2, out


def test_count_model_reports_both_clusterings():
    out = rb.fit_count_model(simulate_counts(0.6))
    assert out["recorder_days"] == 30 and out["standard_error_log"] > 0
    # the literal two-way version is either a valid number or explicitly missing, never a wrong number
    assert np.isnan(out["standard_error_log_two_way"]) or out["standard_error_log_two_way"] > 0


def test_count_model_post_over_pre_separates_a_general_event_effect():
    """If pre and post bins are both depressed by the same amount, post vs baseline looks like a drop
    but post vs pre is about 1. This is why the pre/post contrast is reported next to it."""
    d = simulate_counts(1.0, seed=7)
    pre = d["role"] == "pre"
    rng = np.random.default_rng(11)
    d.loc[pre, "count"] = rng.binomial(d.loc[pre, "count"].astype(int), 0.6)  # pre bins thinned to ~60%
    post = d["role"] == "post"
    d.loc[post, "count"] = rng.binomial(d.loc[post, "count"].astype(int), 0.6)  # post bins thinned the same
    out = rb.fit_count_model(d)
    assert out["rate_ratio"] < 0.8 and out["pre_rate_ratio"] < 0.8, out
    assert abs(np.log(out["post_over_pre_rate_ratio"])) < 0.25, out


def test_count_model_detects_a_drop_and_not_a_null():
    drop = rb.fit_count_model(simulate_counts(0.5, seed=3))
    null = rb.fit_count_model(simulate_counts(1.0, seed=3))
    assert drop["two_sided_p"] < 0.05 < null["two_sided_p"], (drop["two_sided_p"], null["two_sided_p"])


def test_count_model_offset_matters():
    d = simulate_counts(1.0, seed=5)
    short = d["role"] == "post"
    d.loc[short, "recorded_minutes"] = 7.5
    d.loc[short, "count"] = (d.loc[short, "count"] / 2).round()
    out = rb.fit_count_model(d)  # half the minutes, half the counts: rate ratio stays near 1
    assert abs(np.log(out["rate_ratio"])) < 0.25, out


def test_count_model_not_estimable_without_post_bins():
    d = simulate_counts(0.7)
    out = rb.fit_count_model(d.loc[d["role"] != "post"])
    assert not out["estimable"] and out["problem"]


def toy_bins():
    rows = []
    for day, value in zip(["2025-03-17", "2025-03-18", "2025-03-19"], [1.0, 3.0, 8.0]):
        rows.append(("A", pd.Timestamp(f"{day} 09:00"), 540, value, value + 10, False))
    rows.append(("A", pd.Timestamp("2025-03-20 09:00"), 540, 99.0, 99.0, True))  # contaminated: never in a baseline
    return pd.DataFrame(rows, columns=["recorder", "bin_time", "tod_bin", "call_rate", "taxa_count", "event_contaminated"])


def test_own_day_baseline_leaves_the_own_day_out():
    bins = toy_bins()
    paths = bins.loc[[1]].assign(event_id="e1")  # the 18th, value 3.0
    out = rb.own_day_deviations(paths, bins)
    assert out["call_rate_baseline"].iloc[0] == np.median([1.0, 8.0])  # not [1, 3, 8]
    assert out["call_rate_deviation"].iloc[0] == 3.0 - 4.5
    # the reference baseline would be the median of all three clean days
    assert np.median([1.0, 3.0, 8.0]) == 3.0


def test_own_day_baseline_is_missing_when_only_the_own_day_exists():
    bins = toy_bins().iloc[[0]]
    out = rb.own_day_deviations(bins.assign(event_id="e1"), bins)
    assert np.isnan(out["call_rate_deviation"].iloc[0])


def fake_fit(data):
    d = data.dropna(subset=["contrast"])
    est = float(d["contrast"].mean()) if len(d) else np.nan
    se = 1.0
    return {"n_events": len(d), "n_recorders": d["recorder"].nunique(), "estimate": est,
            "standard_error": se, "z": est / se if len(d) else np.nan}


def test_leave_one_recorder_out_flags_an_influential_recorder():
    rows = [("A", -2.0), ("A", -2.5), ("B", 0.3), ("B", -0.2), ("C", 0.1), ("C", 0.2), ("D", -0.1), ("D", 0.0)]
    c = pd.DataFrame(rows, columns=["recorder", "contrast"])
    out = rb.leave_one_recorder_out(c, fake_fit).set_index("omitted")
    assert out.loc["none", "n_events"] == 8 and not out.loc["none", "influential"]
    assert out.loc["A", "sign_flip"] and out.loc["A", "influential"]   # drops the negative recorder: sign flips
    assert not out.loc["D", "influential"]
    assert set(out.index) == {"none", "A", "B", "C", "D"}


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
