import numpy as np
import pytest
from scipy.special import logsumexp

from bilakde.density import GaussianKernelMixture


def test_cached_kernel_density_matches_frozen_formula_including_zero_weights():
    centers = np.array([-2.0, 0.0, 3.0])
    variances = np.array([0.2, 1.0, 0.5])
    mixing = np.array([[0.1, 0.7, 0.2], [0.0, 0.0, 1.0]])
    model = GaussianKernelMixture(centers, variances, mixing)
    r = np.array([[-3.0, 0.0], [0.0, 3.0], [2.0, -1.0], [1e100, -1e100]])
    with np.errstate(divide="ignore"):
        expected = logsumexp(
            np.log(mixing)
            - 0.5 * ((r[..., None] - centers) ** 2 / variances + np.log(2 * np.pi * variances)),
            axis=-1,
        ).sum(axis=-1)
    np.testing.assert_allclose(model.log_increments(r), expected, rtol=1e-13, atol=1e-12)
    assert np.isneginf(model.log_increments(np.full((1, 2), 1e308)))[0]


def test_component_refresh_reduces_to_exact_conditional_gaussian():
    model = GaussianKernelMixture(np.array([0.4]), np.array([2.0]), np.ones((3, 1)))
    rngs = [np.random.default_rng(s) for s in np.random.SeedSequence(19).spawn(12000)]
    states = model.conditional_refresh(np.zeros((12000, 2)), 1.8, rngs)
    np.testing.assert_allclose(states.mean(axis=0), [0.6, 1.2], atol=0.04)
    np.testing.assert_allclose(
        np.cov(states, rowvar=False), [[4 / 3, 2 / 3], [2 / 3, 4 / 3]], atol=0.05
    )


@pytest.mark.parametrize("mixing", [np.array([[0.0, 0.0]]), np.array([[1.0, -0.1]])])
def test_invalid_mixture_weights_are_rejected(mixing):
    with pytest.raises(ValueError):
        GaussianKernelMixture(np.array([0.0, 1.0]), np.ones(2), mixing)


def test_zero_uniform_cannot_select_a_zero_probability_component():
    class ZeroStream:
        def uniform(self, size):
            return np.zeros(size)

        def normal(self, size):
            return np.zeros(size)

    model = GaussianKernelMixture(
        np.array([-100.0, 100.0]), np.ones(2), np.array([[0.0, 1.0], [1.0, 0.0]])
    )
    result = model.conditional_refresh(np.array([[100.0]]), 0.0, [ZeroStream()])
    np.testing.assert_array_equal(result, [[100.0]])
