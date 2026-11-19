"""Tests for the Colab fetch notebook. Run: python tests/test_colab_notebook.py"""
import ast
import io
import json
import re
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import make_colab_fetch_notebook as nb  # noqa: E402

KEY = pd.read_csv(REPO / "results" / "listening" / "sample_key.csv")
NOTEBOOK = json.loads((REPO / "notebooks" / "fetch_listening_clips.ipynb").read_text(encoding="utf-8"))


def code_cells():
    return ["".join(c["source"]) for c in NOTEBOOK["cells"] if c["cell_type"] == "code"]


def test_notebook_is_current_with_the_key():
    assert NOTEBOOK == nb.build()  # regenerate with src/make_colab_fetch_notebook.py if the key changes


def test_every_code_cell_compiles():
    for source in code_cells():
        ast.parse(source)


def test_packed_list_matches_the_key_and_hides_labels():
    packed = nb.unpack(nb.pack(KEY))
    assert list(packed.columns) == ["blind_id", "clip_name"]
    assert packed.equals(KEY[["blind_id", "clip_name"]])
    text = json.dumps(NOTEBOOK)
    for secret in ("yamnet_label", "yamnet_score", "yamnet_positive", "relative_seconds", "stratum", "weight"):
        assert secret not in text.lower(), secret
    assert packed["clip_name"].is_unique and packed["blind_id"].tolist() == [f"L{i:03d}" for i in range(1, 201)]


def test_list_cell_runs_and_checks_200():
    ns = {"pd": pd, "io": io}
    import base64, gzip
    ns.update(base64=base64, gzip=gzip)
    exec(code_cells()[1], ns)
    assert len(ns["clips"]) == 200


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self, num_retries=0):
        return self.payload


def recorder_of(name):
    return re.match(r"Audio_Moth_(\d)_", name).group(1)


class FakeFiles:
    """A tiny Drive. Every clip sits in Audio Moth Data / Segmented Foldered / Audio Moth N / 100_200.
    Three clips also have copies in Segmented and in team Toucanet Data (listed first on purpose)."""
    def __init__(self, names, twin_in_tree=False, differ=False, only_outside=(), wrong_recorder=()):
        self.names = list(names)
        self.twin_in_tree = twin_in_tree
        self.differ = differ
        self.only_outside = set(only_outside)
        self.wrong_recorder = set(wrong_recorder)
        self.outside = set(sorted(names)[:3])
        self.tree = {"root": ("Audio Moth Data", []), "sf": ("Segmented Foldered", ["root"]),
                     "seg": ("Segmented", ["root"]), "team": ("team Toucanet Data", [])}
        for n in range(1, 7):
            self.tree[f"am{n}"] = (f"Audio Moth {n}", ["sf"])
            self.tree[f"r{n}"] = ("100_200", [f"am{n}"])
            self.tree[f"seg{n}"] = ("100_200", ["seg"])
            self.tree[f"filt{n}"] = (f"filtered_clips_{n}", ["team"])
        self.tree["twin"] = ("100_200", ["am1"])

    def list(self, q, **kw):
        wanted = re.findall(r"name = '([^']+)'", q)
        files = []
        for n in wanted:
            if n not in self.names:
                continue
            r = recorder_of(n)
            if n in self.outside:
                files.append({"id": f"seg-{n}", "name": n, "parents": [f"seg{r}"], "md5Checksum": f"md5-{n}"})
                files.append({"id": f"team-{n}", "name": n, "parents": [f"filt{r}"], "md5Checksum": "older"})
            if n in self.only_outside:
                continue
            if n in self.wrong_recorder:
                files.append({"id": f"wrong-{n}", "name": n, "parents": [f"r{int(r) % 6 + 1}"], "md5Checksum": f"md5-{n}"})
                continue
            files.append({"id": f"id-{n}", "name": n, "parents": [f"r{r}"], "md5Checksum": f"md5-{n}"})
            if self.twin_in_tree and n == sorted(self.names)[0]:
                files.append({"id": f"twin-{n}", "name": n, "parents": ["twin"],
                              "md5Checksum": "other" if self.differ else f"md5-{n}"})
            if n in self.outside:
                files.append({"id": f"sc-{n}", "name": n, "parents": [f"seg{r}"],
                              "mimeType": "application/vnd.google-apps.shortcut"})
        files.sort(key=lambda f: not f["id"].startswith(("seg-", "team-")))  # outside copies come first
        return FakeRequest({"files": files})

    def get(self, fileId, **kw):
        name, parents = self.tree.get(fileId, ("?", []))
        return FakeRequest({"name": name, "parents": parents})


class FakeService:
    def __init__(self, names, **kw):
        self._files = FakeFiles(names, **kw)

    def files(self):
        return self._files


def run_find(**kw):
    import base64, gzip
    ns = {"pd": pd, "io": io, "base64": base64, "gzip": gzip}
    exec(code_cells()[1], ns)
    names = list(ns["clips"]["clip_name"])
    ns["service"] = FakeService(names[: len(names) - kw.pop("drop", 0)], **kw)
    exec(code_cells()[2], ns)
    return ns


def test_only_segmented_foldered_copies_are_accepted():
    ns = run_find()
    assert len(ns["chosen"]) == 200 and ns["missing"] == []
    assert all(f["id"].startswith("id-") for f in ns["chosen"].values())  # never the Segmented or team copy
    assert ns["ignored"] == 6  # 3 clips x (Segmented + team Toucanet Data); the shortcut is dropped before counting


def test_a_clip_that_only_exists_outside_segmented_foldered_is_missing():
    only = sorted(run_find()["clips"]["clip_name"])[:1]
    ns = run_find(only_outside=only)
    assert ns["missing"] == only and len(ns["chosen"]) == 199


def test_a_copy_under_the_wrong_audio_moth_folder_is_rejected():
    wrong = sorted(run_find()["clips"]["clip_name"])[5:6]
    ns = run_find(wrong_recorder=wrong)
    assert ns["missing"] == wrong


def test_identical_twins_inside_the_tree_pass_and_different_twins_are_reported():
    for differ, expected in ((False, 0), (True, 1)):
        ns = run_find(twin_in_tree=True, differ=differ)
        assert len(ns["ambiguous"]) == 1 and len(ns["differing"]) == expected, (differ, ns["differing"])
        assert len(ns["chosen"]) == 200


def test_missing_clips_are_reported_not_hidden():
    ns = run_find(drop=2)
    assert len(ns["missing"]) == 2 and len(ns["chosen"]) == 198


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
