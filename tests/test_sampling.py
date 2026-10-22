import subprocess
import sys
import time

import numpy as np
import psutil
import pytest
from scipy.special import logsumexp

from bilakde.config import SamplingConfig
from bilakde.density import InnovationModel
from bilakde.errors import ResourceLimitError
from bilakde.gaussian import GaussianBridge, increments
from bilakde.resources import Budget, run_guarded
from bilakde.sampling import elliptical_sample


def test_conditional_refresh_preserves_exact_kde_bridge_law():
    # Two increments: enumerate every kernel pair to obtain the exact bridge mixture.
    model = InnovationModel(np.tile([-1.0, 0.0], 10), np.tile([0.5, 2.0], 10), 2)
    centers = np.r_[model.left.data, model.right.data]
    variances = np.r_[np.full(20, model.left.bandwidth**2), np.full(20, model.right.bandwidth**2)]
    weights = np.stack(
        [np.r_[np.full(20, w / 20), np.full(20, (1 - w) / 20)] for w in model.weights]
    )
    end = 0.7
    total = variances[:, None] + variances[None, :]
    log_weights = np.log(np.maximum(weights[0, :, None] * weights[1, None, :], 1e-300))
    log_weights -= 0.5 * (
        (end - centers[:, None] - centers[None, :]) ** 2 / total + np.log(2 * np.pi * total)
    )
    probabilities = np.exp(log_weights - logsumexp(log_weights)).ravel()
    means = (
        centers[:, None] + variances[:, None] / total * (end - centers[:, None] - centers[None, :])
    ).ravel()
    conditional_variances = (variances[:, None] * variances[None, :] / total).ravel()
    expected_mean = probabilities @ means
    expected_variance = probabilities @ (conditional_variances + means**2) - expected_mean**2
    rng = np.random.default_rng(73)
    components = rng.choice(len(probabilities), size=6000, p=probabilities)
    initial = rng.normal(means[components], np.sqrt(conditional_variances[components]))[:, None]
    streams = [np.random.default_rng(s) for s in np.random.SeedSequence(51).spawn(6000)]
    refreshed = model.conditional_refresh(initial, end, streams)[:, 0]
    assert abs(refreshed.mean() - expected_mean) < 0.04
    assert abs(refreshed.var() - expected_variance) < 0.04
    # Check distribution shape as well as moments; a Gaussian substitute fails this check.
    from scipy.special import ndtr

    for cutoff in [-0.8, -0.2, 0.4]:
        expected = probabilities @ ndtr((cutoff - means) / np.sqrt(conditional_variances))
        assert abs(np.mean(refreshed <= cutoff) - expected) < 0.025


def test_sampler_matches_unequal_variance_gaussian_bridge():
    reference = GaussianBridge(np.zeros(3), np.array([1.0, 2.0, 3.0]), 2.0)
    config = SamplingConfig(
        time_limit_seconds=30, max_draws_per_chain=2000, stopping="fixed_iterations"
    )
    chains, diag = elliptical_sample(reference.logpdf, reference, 42, 4000, config, Budget(config))
    assert chains.shape == (4, 1000, 2)
    assert diag["diagnostics_pass"]
    np.testing.assert_allclose(chains.mean(axis=(0, 1)), [1 / 3, 1.0], atol=0.09)
    np.testing.assert_allclose(
        np.cov(chains.reshape(-1, 2), rowvar=False), [[5 / 6, 0.5], [0.5, 1.5]], atol=0.12
    )


def test_density_ratio_preserves_non_gaussian_bridge_modes():
    reference = GaussianBridge(np.zeros(4), np.full(4, 1.25), 0.0)

    def target(x):
        r = increments(x, 0.0)
        return logsumexp(-0.5 * (r[..., None] - np.array([-1.0, 1.0])) ** 2 / 0.25, axis=-1).sum(
            axis=-1
        )

    config = SamplingConfig(
        time_limit_seconds=30, max_draws_per_chain=3000, stopping="fixed_iterations"
    )
    chains, diag = elliptical_sample(target, reference, 73, 4000, config, Budget(config))
    assert diag["diagnostics_pass"]
    midpoint = chains[:, :, 1].ravel()
    assert abs(np.mean(midpoint > 0) - 0.5) < 0.05
    # Exact 16-component enumeration gives midpoint variance ~1.59, not the
    # Gaussian reference's 1.25. Omitting target/reference correction fails here.
    assert 1.4 < np.var(midpoint) < 1.85


def _sleep(budget):
    time.sleep(30)


def _with_descendant(budget):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    budget.checkpoint({"descendant_pid": child.pid})
    time.sleep(30)


def test_actual_worker_is_stopped_on_deadline():
    started = time.perf_counter()
    with pytest.raises(ResourceLimitError) as exc:
        run_guarded(_sleep, (), SamplingConfig(time_limit_seconds=0.2))
    assert exc.value.status == "time_limit"
    assert time.perf_counter() - started < 3


def test_memory_limit_is_not_only_a_sample_array_estimate():
    with pytest.raises(ResourceLimitError) as exc:
        run_guarded(_sleep, (), SamplingConfig(time_limit_seconds=5, memory_limit_bytes=1024**2))
    assert exc.value.status == "memory_limit"


def test_timeout_cleans_up_launcher_descendants():
    with pytest.raises(ResourceLimitError) as exc:
        run_guarded(_with_descendant, (), SamplingConfig(time_limit_seconds=5))
    pid = exc.value.diagnostics.get("descendant_pid")
    assert pid is not None, exc.value.diagnostics
    assert not psutil.pid_exists(pid)
