#!/usr/bin/env python3
"""Write notebooks/fetch_listening_clips.ipynb, a Google Colab notebook that gathers the 200 sampled clips.

The notebook reads from Google Drive (through the shortcut to the shared audio folder), saves each clip
under its neutral name (L001.wav ...) into a new Drive folder, checks every clip is 3 seconds long,
and writes a .tar. Only blind_id and clip_name go into the notebook, packed and hidden, so the reviewer
does not see the YAMNet label or the clip position. The list comes from results/listening/sample_key.csv.

  python src/make_colab_fetch_notebook.py
"""

from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
KEY = REPO / "results" / "listening" / "sample_key.csv"
OUT = REPO / "notebooks" / "fetch_listening_clips.ipynb"


def pack(key: pd.DataFrame) -> str:
    """blind_id and clip_name only, as gzip then base64 text."""
    text = key[["blind_id", "clip_name"]].to_csv(index=False, lineterminator="\n")
    return base64.b64encode(gzip.compress(text.encode("utf-8"), mtime=0)).decode("ascii")


def unpack(blob: str) -> pd.DataFrame:
    import io
    return pd.read_csv(io.StringIO(gzip.decompress(base64.b64decode(blob)).decode("utf-8")))


def cell(kind: str, source: str, **meta) -> dict:
    lines = source.strip("\n").split("\n")
    body = {"cell_type": kind, "metadata": meta, "source": [l + "\n" for l in lines[:-1]] + [lines[-1]]}
    if kind == "code":
        body.update(execution_count=None, outputs=[])
    return body


INTRO = """# Fetch the 200 listening clips

What this does
- Finds the 200 sampled clips in the shared audio folder (through your shortcut in My Drive).
- Saves them as `L001.wav` to `L200.wav` in a new Drive folder, `Listening_Clips`.
- Checks each clip is 3 seconds long.
- Writes `Listening_Clips.tar` in My Drive. Download it from there.

Why neutral names: the original names show recorder and time. Neutral names keep you blind to the
YAMNet label and the clip position. The list in the second code cell is packed and hidden on purpose.
Do not open `sample_key.csv` until the review sheet is complete.

Run the cells from top to bottom. Colab asks you to sign in twice (Drive access)."""

SETUP = """# 1. Sign in and mount Drive (Drive is used to save the clips; the API is used to find them)
from google.colab import auth, drive
auth.authenticate_user()
drive.mount('/content/drive')

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import base64, gzip, io, os, shutil, tarfile, wave
import pandas as pd
import logging
logging.getLogger('google_auth_httplib2').setLevel(logging.ERROR)  # hides a harmless timeout warning

service = build('drive', 'v3', cache_discovery=False)
OUT_NAME = 'Listening_Clips'
print('Signed in.')"""

LIST = """#@title 2. Clip list (packed, please do not decode) { display-mode: "form" }
BLOB = "%s"
clips = pd.read_csv(io.StringIO(gzip.decompress(base64.b64decode(BLOB)).decode('utf-8')))
assert len(clips) == 200 and clips['blind_id'].is_unique
print(len(clips), 'clips to fetch')"""

FIND = """# 3. Find the clips by exact name, and accept only a copy at
#    Audio Moth Data / Segmented Foldered / Audio Moth N / <range folder>, with N the clip's own recorder.
#    Copies elsewhere (Segmented, team Toucanet Data, ...) are ignored.
import re

def list_by_name(names):
    q = '(' + ' or '.join(f"name = '{n}'" for n in names) + ') and trashed = false'
    found, token = [], None
    while True:
        r = service.files().list(q=q, corpora='user', supportsAllDrives=True, includeItemsFromAllDrives=True,
                                 fields='nextPageToken, files(id, name, size, md5Checksum, modifiedTime, parents, mimeType)',
                                 pageSize=200, pageToken=token).execute(num_retries=5)
        found += r.get('files', [])
        token = r.get('nextPageToken')
        if not token:
            return found

name_cache = {}
def folder_path(file_id, depth=0):
    if depth > 8:
        return '...'
    if file_id not in name_cache:
        try:
            name_cache[file_id] = service.files().get(fileId=file_id, fields='name, parents', supportsAllDrives=True).execute(num_retries=3)
        except Exception:
            name_cache[file_id] = {'name': '?', 'parents': []}
    info = name_cache[file_id]
    up = folder_path(info['parents'][0], depth + 1) + ' / ' if info.get('parents') else ''
    return up + info['name']

PATH_RE = re.compile(r'Audio Moth Data / Segmented Foldered / Audio Moth (\\d) / \\d+_\\d+$')
def valid_source(f, clip_name):
    if not f.get('parents'):
        return False
    m = PATH_RE.search(folder_path(f['parents'][0]))
    return bool(m) and clip_name.startswith(f'Audio_Moth_{m.group(1)}_')

names = list(clips['clip_name'])
by_name = {}
for i in range(0, len(names), 20):
    for f in list_by_name(names[i:i + 20]):
        if f.get('mimeType') == 'application/vnd.google-apps.shortcut':
            continue  # a shortcut points at a real file that is listed on its own
        by_name.setdefault(f['name'], []).append(f)

chosen, missing, ambiguous, ignored = {}, [], [], 0
for n in names:
    all_copies = by_name.get(n, [])
    options = [f for f in all_copies if valid_source(f, n)]
    ignored += len(all_copies) - len(options)
    if not options:
        missing.append(n)
        continue
    if len(options) > 1:
        ambiguous.append(n)
    chosen[n] = options[0]
    by_name[n] = options

print(f'Found {len(chosen)} of {len(names)} in Segmented Foldered. Missing: {len(missing)}.')
print(f'Copies ignored because they are outside Segmented Foldered / Audio Moth N: {ignored}')
if missing:
    print('Missing (first 5):', missing[:5])

# Only if a name has two copies INSIDE Segmented Foldered: they must be the same file.
differing = [n for n in ambiguous if len({f.get('md5Checksum') for f in by_name[n]}) > 1]
print(f'Names with two copies inside Segmented Foldered: {len(ambiguous)}. Of those, not identical: {len(differing)}')
for n in differing:
    print(n)
    for f in by_name[n]:
        print('   ', f.get('size'), 'bytes |', (f.get('md5Checksum') or 'no checksum')[:8], '|', f.get('modifiedTime', '')[:10], '|', folder_path(f['parents'][0]))"""


SAVE = """# 4. Download each clip and save it under its neutral name in a new Drive folder
assert not missing, 'Some clips were not found. Fix access to the audio folder, then rerun cells 3 and 4.'
dest = f'/content/drive/MyDrive/{OUT_NAME}'
os.makedirs(dest, exist_ok=True)
local = '/content/clips'
os.makedirs(local, exist_ok=True)

failed = []
for row in clips.itertuples():
    meta = chosen[row.clip_name]
    path = f'{local}/{row.blind_id}.wav'
    try:
        request = service.files().get_media(fileId=meta['id'], supportsAllDrives=True)
        with open(path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request, chunksize=8 * 1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk(num_retries=5)
        shutil.copy2(path, f'{dest}/{row.blind_id}.wav')
    except Exception as error:
        failed.append((row.blind_id, type(error).__name__))
print(f'Saved {len(clips) - len(failed)} of {len(clips)} clips to My Drive/{OUT_NAME}')
if failed:
    print('Failed (first 5):', failed[:5], '. If the error is about downloading, the owner has blocked downloads for this folder.')"""

CHECK = """# 5. Check every clip is 3 seconds long and not empty, then write the tar
bad = []
for row in clips.itertuples():
    p = f'/content/clips/{row.blind_id}.wav'
    try:
        with wave.open(p, 'rb') as w:
            seconds = w.getnframes() / w.getframerate()
        if abs(seconds - 3.0) > 0.05:
            bad.append((row.blind_id, round(seconds, 2)))
    except Exception as error:
        bad.append((row.blind_id, type(error).__name__))
print('Clips that are not 3 seconds or cannot be read:', bad if bad else 'none')

tar_path = '/content/drive/MyDrive/Listening_Clips.tar'
with tarfile.open(tar_path, 'w') as tar:
    for row in clips.itertuples():
        tar.add(f'/content/clips/{row.blind_id}.wav', arcname=f'Listening_Clips/{row.blind_id}.wav')
print('Wrote', tar_path, round(os.path.getsize(tar_path) / 1e6, 1), 'MB')"""

DOWNLOAD = """# 6. Optional: download the tar straight to your computer (it is also in My Drive)
from google.colab import files
files.download('/content/drive/MyDrive/Listening_Clips.tar')"""


def build() -> dict:
    key = pd.read_csv(KEY)
    assert len(key) == 200
    return {
        "cells": [
            cell("markdown", INTRO),
            cell("code", SETUP),
            cell("code", LIST % pack(key), cellView="form"),
            cell("code", FIND),
            cell("code", SAVE),
            cell("code", CHECK),
            cell("code", DOWNLOAD),
        ],
        "metadata": {"colab": {"name": "fetch_listening_clips.ipynb", "provenance": []},
                     "kernelspec": {"name": "python3", "display_name": "Python 3"}, "language_info": {"name": "python"}},
        "nbformat": 4, "nbformat_minor": 0,
    }


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(build(), indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
