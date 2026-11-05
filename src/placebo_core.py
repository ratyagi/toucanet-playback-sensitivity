"""Building blocks for the placebo-in-time calibration (Week 3).

Pure functions and one small class, kept separate from the runner so they can be tested.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

CLIP_SECONDS = 3.0


def position_index(times: np.ndarray, bin_start: pd.Timestamp) -> np.ndarray:
    """Clip position (in 3-second steps) relative to the start of a bin."""
    seconds = (times - bin_start.to_datetime64()) / np.timedelta64(1, "s")
    return np.floor(seconds / CLIP_SECONDS).astype(int)


def balanced_mean(values: np.ndarray, recorder_codes: np.ndarray) -> float:
    """Mean of per-recorder means, ignoring NaN (same rule as the reference pipeline)."""
    means = []
    for code in np.unique(recorder_codes):
        chosen = values[recorder_codes == code]
        chosen = chosen[np.isfinite(chosen)]
        if chosen.size:
            means.append(chosen.mean())
    return float(np.mean(means)) if means else float("nan")


def simulate_null(
    pool_values: list[dict[str, np.ndarray]],
    recorder_codes: np.ndarray,
    hypotheses: list[str],
    replicates: int,
    seed: int,
) -> dict[str, np.ndarray]:
    """Draw one placebo candidate per event per replicate.

    pool_values[i][hypothesis] holds the contrast of every candidate for event i, in pool order.
    The draw order and seed match the reference pipeline, so strict-pool results are comparable.
    """
    rng = np.random.default_rng(seed)
    out = {name: np.empty(replicates) for name in hypotheses}
    for replicate in range(replicates):
        draws = [int(rng.integers(len(item[hypotheses[0]]))) for item in pool_values]
        for name in hypotheses:
            values = np.array([item[name][draw] for item, draw in zip(pool_values, draws)], dtype=float)
            out[name][replicate] = balanced_mean(values, recorder_codes)
    return out


def empirical_p(null: np.ndarray, observed: float) -> dict[str, float]:
    finite = null[np.isfinite(null)]
    if not finite.size or not np.isfinite(observed):
        return {"p_less": np.nan, "p_greater": np.nan, "p_two_sided": np.nan}
    p_less = (1 + (finite <= observed).sum()) / (len(finite) + 1)
    p_greater = (1 + (finite >= observed).sum()) / (len(finite) + 1)
    return {"p_less": p_less, "p_greater": p_greater, "p_two_sided": min(1.0, 2 * min(p_less, p_greater))}


class ClipContext:
    """Clip-level view of the dataset: time, global-exclusion flag, and species text per clip."""

    def __init__(self, clips: pd.DataFrame, parse_list):
        self._parse = lru_cache(maxsize=None)(lambda text: tuple(str(v) for v in parse_list(text)))
        self.by_recorder: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for recorder, group in clips.sort_values("clip_time").groupby("Recorder"):
            self.by_recorder[recorder] = (
                group["clip_time"].to_numpy(),
                group["drop"].to_numpy(bool),
                group["species"].to_numpy(object),
            )

    def window(self, recorder: str, start: pd.Timestamp, end: pd.Timestamp):
        times, drop, species = self.by_recorder[recorder]
        low = np.searchsorted(times, start.to_datetime64(), side="left")
        high = np.searchsorted(times, end.to_datetime64(), side="left")
        return times[low:high], drop[low:high], species[low:high]

    def removal_pattern(self, recorder, bin_start, start_minutes, end_minutes) -> set[int]:
        """Positions (relative to bin_start) of clips removed by the global YAMNet filter."""
        times, drop, _ = self.window(
            recorder,
            bin_start + pd.Timedelta(minutes=start_minutes),
            bin_start + pd.Timedelta(minutes=end_minutes),
        )
        return set(position_index(times, bin_start)[drop].tolist())

    def path(self, recorder, bin_start, offsets, bin_minutes, pattern, baseline) -> pd.DataFrame:
        """Recompute call rate and taxa count per bin after dropping the matched positions.

        Clips flagged by the global filter are always dropped. Clips at positions in `pattern`
        (relative to bin_start) are dropped as well. Deviations use the reference baseline.
        """
        first, last = min(offsets), max(offsets) + bin_minutes
        times, drop, species = self.window(
            recorder, bin_start + pd.Timedelta(minutes=first), bin_start + pd.Timedelta(minutes=last)
        )
        positions = position_index(times, bin_start)
        keep = ~drop & ~np.isin(positions, list(pattern)) if pattern else ~drop
        step = np.floor(positions * CLIP_SECONDS / 60.0 / bin_minutes).astype(int) * bin_minutes
        rows = []
        for offset in offsets:
            chosen = keep & (step == offset)
            count = int(chosen.sum())
            bin_time = bin_start + pd.Timedelta(minutes=int(offset))
            call_rate = taxa = np.nan
            if count:
                entries = [item for text in species[chosen] for item in self._parse(text)]
                call_rate = len(entries) / (count * CLIP_SECONDS / 60.0)
                taxa = float(len(set(entries)))
            tod = bin_time.hour * 60 + bin_time.minute
            base_rate, base_taxa = baseline.get((recorder, tod), (np.nan, np.nan))
            rows.append(
                {
                    "relative_minutes": offset,
                    "clips": count,
                    "call_rate_deviation": call_rate - base_rate if count else np.nan,
                    "taxa_count_deviation": taxa - base_taxa if count else np.nan,
                }
            )
        return pd.DataFrame(rows)
