"""YAMNet-based clip exclusion used by the detection-excluded variants."""

from __future__ import annotations

import numpy as np
import pandas as pd


def yamnet_exclusion_mask(clips: pd.DataFrame, tail_seconds: float = 300.0) -> pd.Series:
    """Return a boolean Series, True for clips to drop.

    A clip is dropped when it is YAMNet-positive (`Human Activity != "no"`), or when it
    was recorded within `tail_seconds` after a YAMNet-positive clip from the same recorder.

    Required columns: Recorder, clip_time (datetime), Human Activity.
    """
    drop = pd.Series(False, index=clips.index)
    positive = clips["Human Activity"] != "no"
    for _, group in clips.groupby("Recorder"):
        positive_times = np.sort(group.loc[positive.loc[group.index], "clip_time"].to_numpy())
        if positive_times.size == 0:
            continue
        times = group["clip_time"].to_numpy()
        nearest = np.searchsorted(positive_times, times, side="right") - 1
        valid = nearest >= 0
        gap = np.full(times.shape, np.inf)
        gap[valid] = (times[valid] - positive_times[nearest[valid]]) / np.timedelta64(1, "s")
        drop.loc[group.index] = gap <= tail_seconds
    return drop
