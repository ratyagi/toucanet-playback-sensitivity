"""Checks that the lead's hypotheses file and our variant 1 config describe the same test.
Run: python tests/test_configs.py"""
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import compare_runs as cr  # noqa: E402

CONFIGS = REPO / "configs"


def load(name):
    return json.loads((CONFIGS / name).read_text(encoding="utf-8"))


def test_lead_file_matches_variant_1():
    lead, v1 = load("hypotheses.json"), load("variants/v1_original.json")
    assert lead["bin_minutes"] == v1["bin_minutes"]
    assert lead["pre_window"] == v1["pre_window"]
    assert lead["post_window"] == v1["post_window"]
    assert [(h["metric"], h["alternative"]) for h in lead["hypotheses"]] == \
           [(h["metric"], h["alternative"]) for h in v1["hypotheses"]]


def test_draft_and_lead_files_agree_on_the_test():
    draft, lead = load("hypotheses_draft.json"), load("hypotheses.json")
    key = lambda spec: [(h["name"], h["metric"], h["alternative"]) for h in spec["hypotheses"]]
    assert key(draft) == key(lead)
    for field in ("bin_minutes", "pre_window", "post_window"):
        assert draft[field] == lead[field]


def test_every_variant_tests_a_drop():
    for path in (CONFIGS / "variants").glob("*.json"):
        spec = json.loads(path.read_text(encoding="utf-8"))
        assert {h["alternative"] for h in spec["hypotheses"]} == {"less"}, path.name


def test_variant_4c_is_2b_plus_exclusion():
    """4c is the exact design-document analysis: 2b settings with the YAMNet exclusion of 4a and 4b."""
    v = lambda n: json.loads((CONFIGS / "variants" / n).read_text(encoding="utf-8"))
    b, c, a4 = v("v2b_post_playback_5min.json"), v("v4c_post_playback_5min_excluded.json"), v("v4b_post_playback_excluded.json")
    for field in ("bin_minutes", "pre_window", "post_window", "hypotheses"):
        assert b[field] == c[field], field
    assert (c["bin_minutes"], c["post_window"]["start_minutes"], c["post_window"]["end_minutes_exclusive"]) == (5, 20, 60)
    assert c["exclude_yamnet"] is True and c["yamnet_tail_seconds"] == a4["yamnet_tail_seconds"] == 300
    assert b["exclude_yamnet"] is False


def test_compare_runs_detects_a_change():
    with tempfile.TemporaryDirectory() as t:
        a, b = Path(t, "a"), Path(t, "b")
        a.mkdir(); b.mkdir()
        pd.DataFrame({"x": [1.0, 2.0], "s": ["p", "q"]}).to_csv(a / "f.csv", index=False)
        pd.DataFrame({"x": [1.0, 2.0], "s": ["p", "q"]}).to_csv(b / "f.csv", index=False)
        assert cr.compare_folders(a, b) == []
        pd.DataFrame({"x": [1.0, 2.0000001], "s": ["p", "q"]}).to_csv(b / "f.csv", index=False)
        assert cr.compare_folders(a, b)[0][0] == "f.csv"
        (a / "only_a.csv").write_text("x\n1\n")
        assert ("only_a.csv", "present in only one folder") in cr.compare_folders(a, b)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
