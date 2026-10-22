"""Regression for the exact smoke application that previously timed out."""

import numpy as np

from benchmarks.methods import evaluate
from benchmarks.scenarios import generate, seed_for
from bilakde.config import SamplingConfig
from bilakde.resources import Budget


def test_full_ar_gap_prediction_and_quantiles_fit_original_budget():
    case = {
        "id": "smoke-ar_gaussian-gap30",
        "scenario": "ar_gaussian",
        "missing": 30,
        "replicate": 0,
        "partition": "smoke",
    }
    series, truth = generate(case, 2026)
    seed = seed_for(2026, case["id"], "bila")
    config = SamplingConfig(time_limit_seconds=60)
    result = evaluate("bila", series, truth, seed, 24000, config, budget=Budget(config))
    assert result["diagnostics"]["diagnostics_pass"]
    assert result["chains"].shape == (4, 6000, 32)
    assert np.isfinite(result["metrics"]["energy"])
    # Keep 20 seconds of headroom for worker startup, scoring and laptop load.
    assert result["diagnostics"]["elapsed_seconds"] < 40
