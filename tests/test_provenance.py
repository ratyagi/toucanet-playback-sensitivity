"""Recompute the checksums recorded in the provenance files. Run: python tests/test_provenance.py"""
import hashlib
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def check(provenance: Path) -> int:
    rows = 0
    for line in provenance.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if match:
            name, expected = match.groups()
            assert sha((provenance.parent / name).resolve()) == expected, f"{name} changed"
            rows += 1
    return rows


def test_lead_scripts_unmodified():
    assert check(REPO / "src" / "lead" / "PROVENANCE.md") == 2


def test_reference_files_unmodified():
    assert check(REPO / "reference" / "PROVENANCE.md") == 8


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
