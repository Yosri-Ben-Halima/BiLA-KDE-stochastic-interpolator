"""Observed-only Gaussian KDEs and fixed temporal mixtures."""

import numpy as np
from scipy.special import logsumexp

from .errors import DensityFitError, SamplingError
from .gaussian import GaussianBridge, increments


class GaussianKDE:
    def __init__(self, data):
        self.data = np.asarray(data, dtype=float).copy()
        if self.data.ndim != 1 or len(self.data) < 20 or not np.isfinite(self.data).all():
            raise DensityFitError("invalid_density", "KDE requires at least 20 finite increments")
        with np.errstate(over="ignore", under="ignore", invalid="ignore"):
            self.mean = float(np.mean(self.data))
            centered = self.data - self.mean
            self.sd = float(np.sqrt(np.dot(centered, centered) / (len(self.data) - 1)))
            self.factor = float(len(self.data) ** (-0.2))
            self.bandwidth = self.sd * self.factor
            self.variance = float(np.mean(centered**2) + self.bandwidth**2)
        threshold = 32 * np.finfo(float).eps * np.max(np.abs(self.data))
        if (
            not np.isfinite([self.mean, self.sd, self.bandwidth, self.variance]).all()
            or self.sd <= threshold
            or self.bandwidth <= 0
            or self.variance <= 0
            or self.bandwidth**2 == 0
        ):
            raise DensityFitError(
                "degenerate_density",
                "unresolved increment dispersion",
                {"count": len(self.data), "sd": self.sd if np.isfinite(self.sd) else None},
            )

    def logpdf(self, points):
        with np.errstate(over="ignore", invalid="ignore"):
            z = (np.asarray(points)[..., None] - self.data) / self.bandwidth
            return (
                logsumexp(-0.5 * z * z, axis=-1)
                - np.log(len(self.data) * self.bandwidth)
                - 0.5 * np.log(2 * np.pi)
            )

    def draw(self, rng, shape):
        return rng.choice(self.data, size=shape) + self.bandwidth * rng.normal(size=shape)

    def metadata(self):
        return {
            "count": len(self.data),
            "mean": self.mean,
            "sd": self.sd,
            "bandwidth": self.bandwidth,
            "factor": self.factor,
            "variance": self.variance,
        }


class GaussianKernelMixture:
    """Cached finite Gaussian mixture at each increment, with exact Gibbs updates."""

    def __init__(self, centers, variances, mixing, *, scales=None):
        self.centers = np.asarray(centers, dtype=float).copy()
        self.variances = np.asarray(variances, dtype=float).copy()
        # A rounded subnormal variance cannot recover the original KDE bandwidth.
        self.scales = (
            np.sqrt(self.variances) if scales is None else np.asarray(scales, dtype=float).copy()
        )
        mixing = np.asarray(mixing, dtype=float)
        if (
            self.centers.ndim != 1
            or self.variances.shape != self.centers.shape
            or mixing.ndim != 2
            or mixing.shape[1] != len(self.centers)
            or not np.isfinite(self.centers).all()
            or not np.isfinite(self.variances).all()
            or np.any(self.variances <= 0)
            or self.scales.shape != self.centers.shape
            or not np.isfinite(self.scales).all()
            or np.any(self.scales <= 0)
            or not np.isfinite(mixing).all()
            or np.any(mixing < 0)
            or not np.allclose(mixing.sum(axis=1), 1, rtol=0, atol=1e-12)
        ):
            raise ValueError("invalid Gaussian kernel mixture")
        with np.errstate(over="ignore", under="ignore"):
            if not np.allclose(self.scales**2, self.variances, rtol=1e-12, atol=0):
                raise ValueError("kernel scales and variances disagree")
        self.T = len(mixing)
        with np.errstate(divide="ignore"):
            self.log_coefficients = np.log(mixing) - np.log(self.scales)

    def _log_prob(self, r):
        with np.errstate(over="ignore", invalid="ignore"):
            standardized = (r[..., None] - self.centers) / self.scales
            return self.log_coefficients - 0.5 * standardized * standardized

    def log_increments(self, r):
        log_prob = self._log_prob(np.asarray(r))
        maximum = log_prob.max(axis=-1, keepdims=True)
        with np.errstate(invalid="ignore", divide="ignore"):
            shifted = np.where(np.isfinite(maximum), log_prob - maximum, -np.inf)
            values = maximum[..., 0] + np.log(np.exp(shifted).sum(axis=-1))
        return (values - 0.5 * np.log(2 * np.pi)).sum(axis=-1)

    def conditional_refresh(self, levels, end, rngs):
        log_prob = self._log_prob(increments(levels, end))
        maximum = log_prob.max(axis=-1, keepdims=True)
        if not np.isfinite(maximum).all():
            raise SamplingError("numerical_failure", "nonfinite conditional kernel probabilities")
        # Normalization cancels in categorical inverse-CDF sampling. One exp,
        # no log-sum-exp or second exp; subtracting the maximum prevents overflow.
        cumulative = np.cumsum(np.exp(log_prob - maximum), axis=-1)
        uniforms = np.stack([rng.uniform(size=self.T) for rng in rngs])
        total = cumulative[..., -1]
        uniforms = np.minimum(uniforms * total, np.nextafter(total, 0.0))
        labels = np.sum(cumulative <= uniforms[..., None], axis=-1)
        selected_scales = self.scales[labels]
        # Common scaling cancels from Gaussian sum-conditioning weights and
        # prevents overflow/underflow in the absolute variance sum.
        relative_variances = (selected_scales / selected_scales.max(axis=-1, keepdims=True)) ** 2
        noise = np.stack([rng.normal(size=self.T) for rng in rngs])
        proposal = self.centers[labels] + selected_scales * noise
        proposal += (
            relative_variances
            / relative_variances.sum(axis=-1, keepdims=True)
            * (end - proposal.sum(axis=-1, keepdims=True))
        )
        return np.cumsum(proposal, axis=-1)[..., :-1]


class InnovationModel:
    """Internal modes are benchmark ablations, not additional public estimators."""

    def __init__(self, left, right, T, mode="linear"):
        self.T = T
        self.mode = mode
        if mode == "pooled":
            self.left = self.right = GaussianKDE(np.concatenate([left, right]))
        elif mode == "left":
            self.left = self.right = GaussianKDE(left)
        elif mode == "right":
            self.left = self.right = GaussianKDE(right)
        else:
            self.left, self.right = GaussianKDE(left), GaussianKDE(right)
        if mode not in ("linear", "fixed", "pooled", "left", "right"):
            raise ValueError("unknown innovation-model ablation")
        self.weights = 1 - np.arange(1, T + 1) / T if mode == "linear" else np.full(T, 0.5)
        self.means = self.weights * self.left.mean + (1 - self.weights) * self.right.mean
        self.variances = self.weights * (self.left.variance + (self.left.mean - self.means) ** 2)
        self.variances += (1 - self.weights) * (
            self.right.variance + (self.right.mean - self.means) ** 2
        )
        self.log_left = np.full(T, -np.inf)
        self.log_right = np.full(T, -np.inf)
        np.log(self.weights, out=self.log_left, where=self.weights > 0)
        np.log(1 - self.weights, out=self.log_right, where=self.weights < 1)
        if self.left is self.right:
            # These ablations repeat one KDE on both sides; collapse identical
            # components algebraically without changing bandwidth or density.
            centers = self.left.data
            scales = np.full(len(centers), self.left.bandwidth)
            mixing = np.full((T, len(centers)), 1 / len(centers))
        else:
            centers = np.r_[self.left.data, self.right.data]
            scales = np.r_[
                np.full(len(self.left.data), self.left.bandwidth),
                np.full(len(self.right.data), self.right.bandwidth),
            ]
            mixing = np.concatenate(
                [
                    np.broadcast_to(
                        self.weights[:, None] / len(self.left.data), (T, len(self.left.data))
                    ),
                    np.broadcast_to(
                        (1 - self.weights[:, None]) / len(self.right.data),
                        (T, len(self.right.data)),
                    ),
                ],
                axis=1,
            )
        self.kernels = GaussianKernelMixture(centers, scales**2, mixing, scales=scales)

    def log_increments(self, r):
        return self.kernels.log_increments(r)

    def target(self, levels, end):
        return self.log_increments(increments(levels, end))

    def reference(self, end):
        return GaussianBridge(self.means, self.variances, end)

    def draw_increments(self, rng, count):
        shape = (count, self.T)
        side = rng.random(shape) < self.weights
        return np.where(side, self.left.draw(rng, shape), self.right.draw(rng, shape))

    def conditional_refresh(self, levels, end, rngs):
        """Blocked Gibbs update for the same endpoint-conditioned KDE target.

        First sample kernel labels conditional on current increments. Given those
        labels, independent Gaussian increments conditioned on their sum have an
        analytic bridge law. Conditioning is exact within this Gibbs transition;
        the resulting Markov-chain samples still need convergence diagnostics.
        """
        return self.kernels.conditional_refresh(levels, end, rngs)

    def metadata(self):
        return {
            "mode": self.mode,
            "left": self.left.metadata(),
            "right": self.right.metadata(),
            "weights": self.weights.tolist(),
            "means": self.means.tolist(),
            "variances": self.variances.tolist(),
        }
