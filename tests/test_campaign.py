import numpy as np

from benchmarks.runner import reserve_case, source_signature
from benchmarks.scenarios import generate, primary_cases


def test_case_grid_has_independent_replicates_and_balanced_prefixes():
    cases = list(primary_cases(30))
    assert len(cases) == 360
    assert len({c["id"] for c in cases}) == 360
    assert {c["scenario"] for c in cases[:12]} == {"gaussian", "skew", "scale", "shape"}
    assert {c["missing"] for c in cases[:12]} == {10, 30, 100}


def test_generators_are_seeded_and_masked_before_prediction():
    case = next(iter(primary_cases(1)))
    one, truth = generate(case, 2026)
    two, second = generate(case, 2026)
    np.testing.assert_array_equal(one, two)
    np.testing.assert_array_equal(truth, second)
    assert np.isnan(one).sum() == case["missing"]
    assert np.isfinite(truth).all()


def test_scheduler_reserves_whole_paired_batch_and_manifest_hashes_sources():
    assert not reserve_case(100, 12, 60)
    assert reserve_case(800, 12, 60)
    assert len(source_signature()) == 64
