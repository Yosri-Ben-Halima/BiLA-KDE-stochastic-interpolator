from dataclasses import dataclass

import numpy as np
import pandas as pd
import psutil

from .diagnostics import quantile_mcse
from .errors import BridgeInputError, ResourceLimitError, SummaryPrecisionError


@dataclass(frozen=True)
class QuantileResult:
    levels: np.ndarray
    values: np.ndarray
    mcse: np.ndarray
    index: object

    def __post_init__(self):
        for value in (self.levels, self.values, self.mcse):
            value.setflags(write=False)


class BridgeResult:
    status = "success"

    def __init__(self, gap, chains, diagnostics):
        self.gap_start, self.gap_stop = gap.start, gap.stop
        self.gap_index = gap.index.copy()
        self.chains = np.ascontiguousarray(chains, dtype=float)
        self.samples = self.chains.reshape(-1, self.chains.shape[-1])
        self.diagnostics = diagnostics
        completed = gap.values.copy()
        completed[gap.start : gap.stop] = self.samples[:, 1:-1].mean(axis=0)
        self.imputed_series = (
            pd.Series(completed, index=gap.original.index.copy(), name=gap.original.name)
            if isinstance(gap.original, pd.Series)
            else completed
        )
        self._seal()

    def _seal(self):
        self.chains.setflags(write=False)
        self.samples.setflags(write=False)

    def quantiles(self, levels):
        try:
            levels = np.asarray(levels, dtype=float)
        except (TypeError, ValueError) as exc:
            raise BridgeInputError(
                "invalid_config", "quantile levels must be probabilities"
            ) from exc
        if (
            levels.ndim != 1
            or not len(levels)
            or not np.isfinite(levels).all()
            or np.any((levels <= 0) | (levels >= 1))
        ):
            raise BridgeInputError(
                "invalid_config", "quantile levels must lie strictly inside (0,1)"
            )
        ceiling = self.diagnostics.get("config", {}).get("memory_limit_bytes", 2**31)
        estimated = len(levels) * self.samples.shape[-1] * 16 + self.chains.nbytes * 3
        if psutil.Process().memory_info().rss + estimated > ceiling:
            raise ResourceLimitError("memory_limit", "quantile working set exceeds ceiling")
        values = np.quantile(self.samples, levels, axis=0, method="linear")
        mcse = np.zeros_like(values)
        for i, p in enumerate(levels):
            mcse[i, 1:-1] = quantile_mcse(self.chains[:, :, 1:-1], float(p))
        sd = self.samples[:, 1:-1].std(axis=0, ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            ratios = mcse[:, 1:-1] / sd
        if not np.isfinite(ratios).all() or np.any(ratios > 0.10):
            finite = ratios[np.isfinite(ratios)]
            raise SummaryPrecisionError(
                "summary_precision",
                "requested quantiles lack Monte Carlo precision",
                {
                    "levels": levels.tolist(),
                    "finite_mcse": bool(np.isfinite(ratios).all()),
                    "max_mcse_ratio": float(finite.max()) if finite.size else None,
                },
            )
        values[:, 0], values[:, -1] = self.samples[0, 0], self.samples[0, -1]
        return QuantileResult(levels.copy(), values, mcse, self.gap_index.copy())
