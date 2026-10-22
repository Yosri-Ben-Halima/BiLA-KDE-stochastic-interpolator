"""Analytic independent Gaussian increments conditioned on their sum."""

import numpy as np

from .errors import SamplingError


def increments(levels, end):
    levels = np.asarray(levels)
    return np.diff(
        np.concatenate(
            [np.zeros((*levels.shape[:-1], 1)), levels, np.full((*levels.shape[:-1], 1), end)],
            axis=-1,
        ),
        axis=-1,
    )


class GaussianBridge:
    def __init__(self, means, variances, end):
        self.means = np.asarray(means, dtype=float)
        self.variances = np.asarray(variances, dtype=float)
        self.end = float(end)
        if (
            not np.isfinite(self.means).all()
            or not np.isfinite(self.variances).all()
            or np.any(self.variances <= 0)
            or not np.isfinite(end)
        ):
            raise SamplingError("numerical_failure", "invalid Gaussian bridge moments")
        total = self.variances.sum()
        prefix = np.cumsum(self.variances)[:-1]
        self.mean = np.cumsum(self.means)[:-1] + prefix / total * (end - self.means.sum())
        self.covariance = np.minimum.outer(prefix, prefix) - np.outer(prefix, prefix) / total
        try:
            self.cholesky = np.linalg.cholesky(self.covariance)
        except np.linalg.LinAlgError as exc:
            raise SamplingError("numerical_failure", "singular Gaussian reference") from exc

    def logpdf(self, levels):
        r = increments(levels, self.end)
        return -0.5 * np.sum(
            (r - self.means) ** 2 / self.variances + np.log(2 * np.pi * self.variances), axis=-1
        )

    def draw(self, rng, count):
        return self.mean + rng.normal(size=(count, len(self.mean))) @ self.cholesky.T
