from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import windows
from .errors import BridgeInputError


@dataclass
class GapData:
    values: np.ndarray
    original: object
    start: int
    stop: int
    left: np.ndarray
    right: np.ndarray
    index: object

    @property
    def T(self):
        return self.stop - self.start + 1

    @property
    def a(self):
        return float(self.values[self.start - 1])

    @property
    def b(self):
        return float(self.values[self.stop])


def prepare(series, window_size):
    left_count, right_count = windows(window_size)
    is_series = isinstance(series, pd.Series)
    if is_series:
        idx = series.index
        if (
            not isinstance(idx, pd.DatetimeIndex)
            or idx.hasnans
            or not idx.is_unique
            or not idx.is_monotonic_increasing
        ):
            raise BridgeInputError(
                "invalid_input", "Series requires an increasing unique DatetimeIndex"
            )
        # asi8 uses the index's own common integer unit, including UTC for aware indexes.
        ticks = idx.asi8
        deltas = [int(ticks[i]) - int(ticks[i - 1]) for i in range(1, len(ticks))]
        if not deltas or deltas[0] <= 0 or any(d != deltas[0] for d in deltas):
            raise BridgeInputError(
                "invalid_input", "timestamps must have equal elapsed-time spacing"
            )
        if not pd.api.types.is_numeric_dtype(series.dtype) or pd.api.types.is_bool_dtype(
            series.dtype
        ):
            raise BridgeInputError("invalid_input", "values must be real numeric data")
        raw = list(series.array)
        if pd.api.types.is_complex_dtype(series.dtype):
            raise BridgeInputError("invalid_input", "complex values are unsupported")
        values = series.to_numpy(dtype=np.float64, na_value=np.nan).copy()
    else:
        try:
            raw = np.asarray(series)
        except (ValueError, TypeError) as exc:
            raise BridgeInputError("invalid_input", "expected a real numeric vector") from exc
        if raw.ndim != 1 or raw.dtype.kind not in "iuf":
            raise BridgeInputError("invalid_input", "expected a real numeric vector")
        with np.errstate(over="ignore", invalid="ignore"):
            values = raw.astype(np.float64, copy=True)
    if values.ndim != 1 or len(values) < 3:
        raise BridgeInputError("invalid_input", "expected a vector with an internal gap")
    # Python scalar equality catches integer rounding that NumPy's float coercion can hide.
    for before, after in zip(raw, values):
        if pd.isna(before):
            continue
        scalar = before.item() if isinstance(before, np.generic) else before
        if not np.isfinite(after) or scalar != float(after):
            raise BridgeInputError(
                "invalid_input", "observed values must be finite and losslessly float64"
            )
    missing = np.flatnonzero(np.isnan(values))
    if (
        not len(missing)
        or missing[0] == 0
        or missing[-1] == len(values) - 1
        or np.any(np.diff(missing) != 1)
        or np.isinf(values).any()
    ):
        raise BridgeInputError("invalid_input", "expected exactly one bounded NaN gap")
    start, stop = int(missing[0]), int(missing[-1] + 1)
    if start - 1 < left_count or len(values) - stop - 1 < right_count:
        raise BridgeInputError(
            "insufficient_data",
            "requested consecutive windows are unavailable",
            {"left_available": start - 1, "right_available": len(values) - stop - 1},
        )
    with np.errstate(over="ignore", invalid="ignore"):
        left = np.diff(values[start - 1 - left_count : start])
        right = np.diff(values[stop : stop + right_count + 1])
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise BridgeInputError("invalid_input", "observed increments overflow float64")
    index = (
        series.index[start - 1 : stop + 1].copy() if is_series else np.arange(start - 1, stop + 1)
    )
    original = series.copy(deep=True) if is_series else values.copy()
    return GapData(values, original, start, stop, left, right, index)
