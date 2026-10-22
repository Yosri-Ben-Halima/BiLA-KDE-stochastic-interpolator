import numpy as np
import pandas as pd
import pytest

from bilakde.config import SamplingConfig, validate_request
from bilakde.errors import BridgeInputError
from bilakde.inputs import prepare


def series():
    x = np.arange(52, dtype=float)
    x[24:27] = np.nan
    return x


def test_windows_use_only_observed_forward_increments():
    x = series()
    gap = prepare(x, (20, 20))
    assert (gap.start, gap.stop) == (24, 27)
    np.testing.assert_array_equal(gap.left, np.ones(20))
    np.testing.assert_array_equal(gap.right, np.ones(20))
    assert np.isnan(x[24:27]).all()


@pytest.mark.parametrize("kind", ["no_gap", "two_gaps", "edge", "inf", "bool", "complex"])
def test_rejects_unsupported_data(kind):
    x = series()
    if kind == "no_gap":
        x = np.arange(52.0)
    if kind == "two_gaps":
        x[4] = np.nan
    if kind == "edge":
        x[0] = np.nan
    if kind == "inf":
        x[3] = np.inf
    if kind == "bool":
        x = np.ones(52, dtype=bool)
    if kind == "complex":
        x = x.astype(complex)
    with pytest.raises(BridgeInputError) as exc:
        prepare(x, 20)
    assert exc.value.status == "invalid_input"


def test_window_shortage_is_not_silently_shrunk():
    with pytest.raises(BridgeInputError) as exc:
        prepare(series(), 100)
    assert exc.value.status == "insufficient_data"


def test_pandas_utc_regular_grid_and_metadata():
    index = pd.date_range("2026-10-25", periods=52, freq="h", tz="Europe/Paris")
    x = pd.Series(series(), index=index, name="sensor")
    gap = prepare(x, 20)
    assert gap.index.equals(index[23:28])
    assert gap.original.name == "sensor"


def test_local_daily_dst_grid_is_rejected():
    x = pd.Series(series(), index=pd.date_range("2026-10-01", periods=52, tz="Europe/Paris"))
    with pytest.raises(BridgeInputError):
        prepare(x, 20)


def test_nullable_numeric_series_is_supported_but_lossy_integers_are_not():
    index = pd.date_range("2026-01-01", periods=52, freq="h")
    x = pd.Series(range(52), index=index, dtype="Int64")
    x.iloc[24:27] = pd.NA
    assert prepare(x, 20).start == 24
    x.iloc[0] = 2**60 + 1
    with pytest.raises(BridgeInputError):
        prepare(x, 20)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"time_limit_seconds": 0},
        {"memory_limit_bytes": True},
        {"max_draws_per_chain": 499},
        {"stopping": "other"},
    ],
)
def test_invalid_sampling_configuration(kwargs):
    with pytest.raises(BridgeInputError):
        SamplingConfig(**kwargs)


def test_requested_sample_count_and_seed_are_validated():
    with pytest.raises(BridgeInputError):
        validate_request(20, True, 2000, SamplingConfig())
    with pytest.raises(BridgeInputError):
        validate_request(20, 42, 2001, SamplingConfig())
    with pytest.raises(BridgeInputError):
        validate_request(19, 42, 2000, SamplingConfig())


def test_numpy_configuration_scalars_have_json_serializable_diagnostics():
    import json
    from dataclasses import asdict

    config = SamplingConfig(
        time_limit_seconds=np.float32(1.5),
        memory_limit_bytes=np.int64(2**31),
        max_draws_per_chain=np.int64(1000),
    )
    encoded = json.dumps(asdict(config), allow_nan=False)
    assert json.loads(encoded)["time_limit_seconds"] == 1.5
