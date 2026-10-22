import numpy as np
import pytest
from scipy.stats import norm

from bilakde.density import GaussianKDE, InnovationModel
from bilakde.errors import DensityFitError
from bilakde.gaussian import GaussianBridge


def test_kde_density_and_variance_include_kernel_dispersion():
    kde = GaussianKDE(np.arange(1.0, 21.0))
    h = np.sqrt(35) * 20 ** (-0.2)
    assert kde.mean == 10.5
    assert kde.bandwidth == pytest.approx(h)
    assert kde.variance == pytest.approx(33.25 + h * h)
    expected = norm.pdf(5.0, loc=np.arange(1.0, 21.0), scale=h).mean()
    assert np.exp(kde.logpdf(np.array([5.0])))[0] == pytest.approx(expected)


@pytest.mark.parametrize("values", [np.ones(20), np.zeros(20), 1 + np.arange(20) * 1e-16])
def test_degenerate_density_does_not_add_jitter(values):
    with pytest.raises(DensityFitError) as exc:
        GaussianKDE(values)
    assert exc.value.status == "degenerate_density"


def test_blend_variance_includes_between_side_means():
    model = InnovationModel(np.tile([-1.0, 1.0], 10), np.tile([2.0, 4.0], 10), 2)
    assert model.means[0] == pytest.approx(1.5)
    assert model.variances[0] == pytest.approx(model.left.variance + 2.25)
    assert model.means[1] == pytest.approx(3.0)
    assert model.weights.tolist() == [0.5, 0.0]


def test_gaussian_sum_conditioning_matches_hand_derived_covariance():
    bridge = GaussianBridge(np.zeros(3), np.array([1.0, 2.0, 3.0]), 2.0)
    np.testing.assert_allclose(bridge.mean, [1 / 3, 1.0])
    np.testing.assert_allclose(bridge.covariance, [[5 / 6, 0.5], [0.5, 1.5]])
    x = bridge.draw(np.random.default_rng(42), 30_000)
    np.testing.assert_allclose(x.mean(axis=0), [1 / 3, 1.0], atol=0.02)
    np.testing.assert_allclose(np.cov(x, rowvar=False), [[5 / 6, 0.5], [0.5, 1.5]], atol=0.025)


def test_density_affine_scaling():
    x = np.arange(20.0)
    first, second = GaussianKDE(x), GaussianKDE(3 * x + 2)
    assert second.bandwidth == pytest.approx(3 * first.bandwidth)
    np.testing.assert_allclose(
        second.logpdf(np.array([8.0])), first.logpdf(np.array([2.0])) - np.log(3)
    )


@pytest.mark.parametrize("mode", ["linear", "fixed", "pooled", "left", "right"])
def test_cached_mixture_preserves_every_kde_ablation_with_unequal_windows(mode):
    rng = np.random.default_rng(13)
    model = InnovationModel(rng.normal(size=23), rng.exponential(size=37), 7, mode)
    r = rng.normal(size=(20, 7)) * 3
    expected = np.logaddexp(
        model.log_left + model.left.logpdf(r), model.log_right + model.right.logpdf(r)
    ).sum(axis=-1)
    np.testing.assert_allclose(model.log_increments(r), expected, rtol=1e-13, atol=1e-12)
