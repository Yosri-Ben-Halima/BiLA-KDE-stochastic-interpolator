"""The original displaced-mixture reference must pass without relaxed tolerances."""

from benchmarks.oracles import reference_case
from bilakde.config import SamplingConfig
from bilakde.resources import Budget


def test_displaced_mixture_tail_reference():
    config = SamplingConfig(time_limit_seconds=60)
    result = reference_case(
        {"kind": "mixture", "T": 4, "z": 2, "n_samples": 32000},
        2026,
        config,
        budget=Budget(config),
    )
    assert result["diagnostics"]["oracle_status"] == "pass"
