"""Regression for the unchanged third visual example."""

import numpy as np

from bilakde.bridge import _fit
from bilakde.config import SamplingConfig
from bilakde.errors import BridgeError
from bilakde.resources import Budget


def test_changing_skewed_gap_meets_original_quality_checks():
    rng = np.random.default_rng(21)
    transition = np.clip((np.arange(211) - 85) / 40, 0, 1)
    increments = (0.6 + transition) * (rng.exponential(size=211) - 1) + 0.4 * transition
    masked = np.r_[0.0, np.cumsum(increments)]
    masked[101:111] = np.nan
    # A bounded loop isolates the mixing failure without the old 10,000-update run.
    config = SamplingConfig(time_limit_seconds=60, max_draws_per_chain=2000)
    try:
        result = _fit(masked, (100, 100), 42, 8000, config, budget=Budget(config))
    except BridgeError as exc:
        raise AssertionError(f"{exc.status}: {exc.diagnostics}") from exc
    assert result.diagnostics["diagnostics_pass"]
    assert np.array_equal(result.imputed_series[:101], masked[:101])
    assert np.array_equal(result.imputed_series[111:], masked[111:])
    assert result.samples.shape == (8000, 12)
