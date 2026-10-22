import numpy as np
import pytest
from scipy.stats import norm

from benchmarks.bayesian import ar_loglikelihood, ar_paths, fit_ar, local_level_posterior
from benchmarks.scoring import scores
from bilakde.config import SamplingConfig
from bilakde.inputs import prepare
from bilakde.resources import Budget


def fixture():
    x = np.arange(52.0)
    x[24:27] = np.nan
    return prepare(x, 20)


def test_local_level_posterior_includes_gap_displacement():
    # 40 observed unit increments and one 4-step displacement of 4.
    alpha, beta = local_level_posterior(fixture())
    assert alpha == 22.5
    assert beta == 23.0


def test_ar_likelihood_uses_multistep_gap_variance():
    actual = ar_loglikelihood(np.array([1.0, 2.0]), np.array([2]), 0.0, 0.5, 1.0)
    assert actual == pytest.approx(norm.logpdf(2.0, loc=0.25, scale=np.sqrt(1.25)))


def test_ar_paths_reduce_to_analytic_independent_level_bridge():
    rng = np.random.default_rng(4)
    x = ar_paths(np.full(20_000, 2.0), np.zeros(20_000), np.ones(20_000), 1.0, 3.0, 4, rng)
    np.testing.assert_array_equal(x[:, [0, -1]], np.tile([1.0, 3.0], (20_000, 1)))
    np.testing.assert_allclose(x[:, 1:-1].mean(axis=0), [2.0, 2.0, 2.0], atol=0.025)
    np.testing.assert_allclose(np.cov(x[:, 1:-1], rowvar=False), np.eye(3), atol=0.03)


def test_correlated_ar_bridge_matches_hand_derived_conditional_covariance():
    # phi=.5, innovation variance=1, X0=0, X3=1. Gaussian conditioning gives
    # E[X1,X2]=[4/21,10/21] and covariance [[20/21,8/21],[8/21,20/21]].
    count = 30_000
    x = ar_paths(
        np.zeros(count), np.full(count, 0.5), np.ones(count), 0.0, 1.0, 3, np.random.default_rng(91)
    )
    np.testing.assert_allclose(x[:, 1:-1].mean(axis=0), [4 / 21, 10 / 21], atol=0.025)
    np.testing.assert_allclose(
        np.cov(x[:, 1:-1], rowvar=False), [[20 / 21, 8 / 21], [8 / 21, 20 / 21]], atol=0.025
    )


def test_bayesian_ar_quadrature_is_proper_and_refined():
    posterior = fit_ar(fixture(), Budget(SamplingConfig(time_limit_seconds=30)))
    assert np.isclose(posterior.weights.sum(), 1)
    assert np.all((-1 < posterior.phi) & (posterior.phi < 1))
    assert posterior.metadata["quadrature_pass"]
    mu, phi, var = posterior.draw(np.random.default_rng(1), 2000)
    assert np.isfinite(mu).all() and np.all(var > 0) and np.all(np.abs(phi) < 1)


def test_perfect_point_prediction_has_zero_proper_scores():
    truth = np.array([1.0, 2.0, 3.0])
    draws = np.tile(truth, (4, 500, 1))
    result = scores(draws, truth, 42)
    assert result["energy"] == 0
    assert result["crps"] == 0
    assert result["rmse"] == 0


def test_path_score_detects_wrong_values_without_endpoint_dilution():
    draws = np.zeros((4, 500, 3))
    result = scores(draws, np.ones(3), 42)
    assert result["energy"] == pytest.approx(1.0)
    assert result["crps"] == pytest.approx(1.0)
    assert result["rmse"] == pytest.approx(1.0)


def test_energy_precision_accounts_for_different_correlated_chain_groups():
    draws = np.broadcast_to(np.array([0.0, 0.0, 1.0, 4.0])[:, None, None], (4, 500, 3))
    result = scores(draws, np.ones(3), 42)
    assert result["energy_chain_mcse"] > 0.2
    assert result["energy_mcse"] >= result["energy_chain_mcse"]


def test_gaussian_oracle_reports_cdf_and_monte_carlo_evidence():
    from benchmarks.oracles import reference_case

    config = SamplingConfig(time_limit_seconds=30)
    result = reference_case({"kind": "gaussian", "T": 3, "z": 0}, 42, config, budget=Budget(config))
    diagnostic = result["diagnostics"]
    assert diagnostic["oracle_midpoint_probability_error"] <= 0.05
    assert diagnostic["oracle_mean_mcse_sd"] > 0
    assert diagnostic["oracle_cov_mcse_relative"] > 0
    assert diagnostic["oracle_status"] == "pass"


def test_kde_oracle_exercises_production_gibbs_and_reference_tails():
    from benchmarks.oracles import reference_case

    config = SamplingConfig(time_limit_seconds=45)
    result = reference_case(
        {"kind": "kde_mixture", "T": 3, "z": 0, "n_samples": 16000},
        42,
        config,
        budget=Budget(config),
    )
    diagnostic = result["diagnostics"]
    assert diagnostic["transition_kernel"] == "elliptical_slice+kernel_gibbs"
    assert diagnostic["oracle_tail_quantile_error_sd"] >= 0
    assert diagnostic["oracle_path_quadratic_relative_error"] >= 0
    assert diagnostic["oracle_production_log_density_error"] < 1e-10
    assert diagnostic["oracle_status"] == "pass"
