"""Density equivalence and conditioning regressions at extreme scales."""

import numpy as np
import pytest

from bilakde.density import GaussianKernelMixture, InnovationModel


@pytest.mark.parametrize("mode", ["linear", "fixed", "pooled", "left", "right"])
@pytest.mark.parametrize("scale,point", [(1e150, 1e155), (3e-162, 0.0)])
def test_cached_density_preserves_fitted_bandwidth_at_extreme_scales(mode, scale, point):
    left = np.tile([-1.0, 1.0], 10) * scale
    right = np.tile([-1.0, 1.0], 10) * (scale * 2)
    model = InnovationModel(left, right, 2, mode)
    r = np.full((1, 2), point)
    expected = np.logaddexp(
        model.log_left + model.left.logpdf(r), model.log_right + model.right.logpdf(r)
    ).sum(axis=-1)
    assert np.isfinite(expected).all()
    np.testing.assert_allclose(model.log_increments(r), expected, rtol=1e-13, atol=1e-12)


def test_conditional_gaussian_refresh_uses_unrounded_kernel_scales():
    class FixedStream:
        def uniform(self, size):
            return np.full(size, 0.5)

        def normal(self, size):
            return np.array([1.0, 2.0])

    h = 1.7266381290922405e-162
    model = GaussianKernelMixture(
        np.array([0.0]), np.array([h**2]), np.ones((2, 1)), scales=np.array([h])
    )
    levels = model.conditional_refresh(np.zeros((1, 1)), 0.0, [FixedStream()])
    np.testing.assert_allclose(levels / h, [[-0.5]], rtol=1e-13, atol=0)


def test_extreme_component_variance_ratios_remain_finite():
    class FixedStream:
        def uniform(self, size):
            return np.full(size, 0.5)

        def normal(self, size):
            return np.array([1.0, 2.0])

    model = GaussianKernelMixture(
        np.zeros(2), np.array([1e308, 1e308]), np.array([[1.0, 0.0], [0.0, 1.0]])
    )
    levels = model.conditional_refresh(np.zeros((1, 1)), 0.0, [FixedStream()])
    np.testing.assert_allclose(levels / 1e154, [[-0.5]], rtol=1e-13, atol=0)
