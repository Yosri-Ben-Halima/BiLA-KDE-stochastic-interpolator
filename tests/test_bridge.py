import json

import numpy as np
import pandas as pd
import pytest

from bilakde import BiLAKDEBridge, BridgeError, BridgeResult, SamplingConfig, SummaryPrecisionError
from bilakde.inputs import prepare


def observed(missing=3):
    x = np.r_[0.0, np.cumsum(np.random.default_rng(8).normal(size=204 + missing))]
    x[101 : 101 + missing] = np.nan
    return x


def test_public_inference_preserves_observations_and_reports_actual_final_block():
    x = observed()
    model = BiLAKDEBridge(random_state=42)
    result = model.fit_transform(x)
    assert result.status == "success"
    assert result.samples.shape == (2000, 5)
    assert result.chains.shape == (4, 500, 5)
    np.testing.assert_array_equal(result.samples, result.chains.reshape(2000, 5))
    np.testing.assert_array_equal(result.imputed_series[~np.isnan(x)], x[~np.isnan(x)])
    np.testing.assert_allclose(result.imputed_series[101:104], result.samples[:, 1:-1].mean(axis=0))
    assert not result.samples.flags.writeable
    assert not result.chains.flags.writeable
    assert np.isnan(x[101:104]).all()
    assert result.diagnostics["draws_per_chain"] == 500
    assert result.diagnostics["diagnostics_pass"]
    json.dumps(result.diagnostics, allow_nan=False)


def test_seeded_fixed_iteration_calls_and_pandas_metadata():
    x = pd.Series(
        observed(),
        index=pd.date_range("2026-10-20", periods=208, freq="h", tz="Europe/Paris"),
        name="sensor",
    )
    config = SamplingConfig(max_draws_per_chain=2500, stopping="fixed_iterations")
    model = BiLAKDEBridge(random_state=12, sampling=config)
    one, two = model.fit_transform(x), model.fit_transform(x)
    np.testing.assert_array_equal(one.samples, two.samples)
    assert one.imputed_series.index.equals(x.index)
    assert one.imputed_series.name == "sensor"


def test_failed_calls_raise_diagnostics_without_partial_outputs():
    with pytest.raises(BridgeError) as exc:
        BiLAKDEBridge(sampling=SamplingConfig(time_limit_seconds=0.05)).fit_transform(observed())
    assert exc.value.status == "time_limit"
    assert not hasattr(exc.value, "samples")
    assert not hasattr(exc.value, "imputed_series")


def test_quantiles_keep_probability_order_and_exact_endpoints():
    gap = prepare(observed(), 100)
    rng = np.random.default_rng(6)
    interior = rng.normal(size=(4, 2000, 3))
    chains = np.concatenate(
        [np.full((4, 2000, 1), gap.a), interior, np.full((4, 2000, 1), gap.b)], axis=2
    )
    result = BridgeResult(gap, chains, {})
    quantiles = result.quantiles([0.9, 0.1, 0.5])
    assert quantiles.values.shape == (3, 5)
    np.testing.assert_array_equal(quantiles.levels, [0.9, 0.1, 0.5])
    np.testing.assert_array_equal(quantiles.values[:, 0], np.full(3, gap.a))
    np.testing.assert_array_equal(quantiles.values[:, -1], np.full(3, gap.b))
    np.testing.assert_array_equal(quantiles.mcse[:, [0, -1]], np.zeros((3, 2)))
    assert np.all(quantiles.values[0, 1:-1] > quantiles.values[1, 1:-1])


def test_unmixed_chains_do_not_produce_validated_quantiles():
    gap = prepare(observed(), 100)
    chains = np.zeros((4, 500, 5))
    chains[:, :, 0], chains[:, :, -1] = gap.a, gap.b
    chains[:, :, 1:-1] = np.arange(4)[:, None, None]
    result = BridgeResult(gap, chains, {})
    with pytest.raises(SummaryPrecisionError):
        result.quantiles([0.025, 0.975])


def test_large_level_offset_cannot_certify_rounded_away_variation():
    from bilakde.bridge import _fit
    from bilakde.errors import SamplingError
    from bilakde.resources import Budget

    r = np.r_[np.zeros(98), 2.0, -2.0]
    x = 1e16 + np.r_[0.0, np.cumsum(r), np.nan, 0.0, np.cumsum(r)]
    config = SamplingConfig(time_limit_seconds=30, max_draws_per_chain=2000)
    with pytest.raises(SamplingError) as exc:
        _fit(x, (100, 100), 42, 2000, config, budget=Budget(config))
    assert exc.value.status == "numerical_failure"
