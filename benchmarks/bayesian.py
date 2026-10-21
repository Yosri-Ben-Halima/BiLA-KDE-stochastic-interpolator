"""Noiseless Bayesian state-space controls with the gap likelihood retained."""

from dataclasses import dataclass

import numpy as np
from scipy.special import logsumexp, roots_legendre

from bilakde.errors import SamplingError


def observations(gap):
    left = len(gap.left)
    right = len(gap.right)
    indexes = np.r_[
        np.arange(gap.start - 1 - left, gap.start), np.arange(gap.stop, gap.stop + right + 1)
    ]
    return gap.values[indexes], np.diff(indexes)


def local_level_posterior(gap, shape=2.0, scale=1.0):
    y, d = observations(gap)
    return shape + len(d) / 2, scale + 0.5 * np.sum(np.diff(y) ** 2 / d)


def variance_sums(phi, maximum):
    phi = np.atleast_1d(phi)
    result = np.zeros((len(phi), maximum + 1))
    for i in range(1, maximum + 1):
        result[:, i] = 1 + phi * phi * result[:, i - 1]
    return result


def ar_loglikelihood(y, steps, mu, phi, variance):
    phi, mu, variance = np.broadcast_arrays(
        np.atleast_1d(phi), np.atleast_1d(mu), np.atleast_1d(variance)
    )
    a = variance_sums(phi, int(np.max(steps)))[:, steps]
    predicted = mu[:, None] + phi[:, None] ** steps * (y[:-1] - mu[:, None])
    out = -0.5 * np.sum(
        np.log(2 * np.pi * variance[:, None] * a)
        + (y[1:] - predicted) ** 2 / (variance[:, None] * a),
        axis=1,
    )
    return out.item() if len(out) == 1 else out


def ar_paths(mu, phi, variance, a, b, T, rng):
    mu, phi, variance = np.broadcast_arrays(
        np.atleast_1d(mu), np.atleast_1d(phi), np.atleast_1d(variance)
    )
    sums = variance_sums(phi, T)
    x = np.empty((len(mu), T + 1))
    x[:, 0], x[:, -1] = a, b
    for t in range(1, T):
        remaining = T - t + 1
        ordinary = mu + phi * (x[:, t - 1] - mu)
        prediction = mu + phi**remaining * (x[:, t - 1] - mu)
        gain = phi ** (remaining - 1) / sums[:, remaining]
        mean = ordinary + gain * (b - prediction)
        var = variance * sums[:, remaining - 1] / sums[:, remaining]
        x[:, t] = mean + np.sqrt(var) * rng.normal(size=len(mu))
    return x


@dataclass
class ARPosterior:
    phi: np.ndarray
    weights: np.ndarray
    mu: np.ndarray
    kappa: np.ndarray
    alpha: float
    beta: np.ndarray
    metadata: dict

    @property
    def parameter_means(self):
        return (
            float(self.weights @ self.mu),
            float(self.weights @ self.phi),
            float(self.weights @ (self.beta / (self.alpha - 1))),
        )

    def draw(self, rng, count):
        index = rng.choice(len(self.phi), size=count, p=self.weights)
        variance = self.beta[index] / rng.gamma(self.alpha, size=count)
        mu = self.mu[index] + np.sqrt(variance / self.kappa[index]) * rng.normal(size=count)
        return mu, self.phi[index], variance


def fit_ar(gap, budget, shape=2.0, scale=1.0, kappa0=0.01):
    y, steps = observations(gap)
    origin = y[0]
    centered = y - origin
    alpha = shape + len(steps) / 2
    previous = None
    for nodes in (256, 512, 1024, 2048):
        budget.check()
        phi, quadrature_weights = roots_legendre(nodes)
        sums = variance_sums(phi, int(max(steps)))
        a = sums[:, steps]
        powered = phi[:, None] ** steps
        design = 1 - powered
        response = centered[1:] - powered * centered[:-1]
        kappa = kappa0 + np.sum(design * design / a, axis=1)
        mean = np.sum(design * response / a, axis=1) / kappa
        beta = scale + 0.5 * (np.sum(response * response / a, axis=1) - kappa * mean * mean)
        if np.any(beta <= 0) or not np.isfinite(beta).all():
            raise SamplingError("numerical_failure", "invalid AR conjugate posterior scale")
        log_mass = (
            np.log(quadrature_weights)
            + np.log1p(-phi * phi)
            - 0.5 * np.log(a).sum(axis=1)
            + 0.5 * np.log(kappa0 / kappa)
            - alpha * np.log(beta)
        )
        weight = np.exp(log_mass - logsumexp(log_mass))
        mu = mean + origin
        ev = beta / (alpha - 1)
        mid = gap.T // 2
        all_sums = variance_sums(phi, gap.T)
        gain = all_sums[:, mid] * phi ** (gap.T - mid) / all_sums[:, gap.T]
        coefficient = 1 - phi**mid - gain * (1 - phi**gap.T)
        prediction = mu + phi**mid * (gap.a - mu) + gain * (gap.b - mu - phi**gap.T * (gap.a - mu))
        residual = (
            all_sums[:, mid]
            - all_sums[:, mid] ** 2 * phi ** (2 * (gap.T - mid)) / all_sums[:, gap.T]
        )
        predictive_second = ev * (residual + coefficient**2 / kappa) + prediction**2
        moments = np.array(
            [
                weight @ phi,
                weight @ mu,
                weight @ ev,
                weight @ prediction,
                weight @ predictive_second,
            ]
        )
        cdf = np.interp(
            [-0.9, -0.5, 0, 0.5, 0.9, 0.99],
            np.r_[-1, phi, 1],
            np.r_[0, np.cumsum(weight) - 0.5 * weight, 1],
        )
        if previous is not None:
            cdf_error = float(np.max(np.abs(cdf - previous[0])))
            moment_error = float(np.max(np.abs(moments - previous[1]) / (1 + np.abs(moments))))
            if cdf_error <= 0.001 and moment_error <= 0.01:
                return ARPosterior(
                    phi,
                    weight,
                    mu,
                    kappa,
                    alpha,
                    beta,
                    {
                        "quadrature_pass": True,
                        "nodes": nodes,
                        "cdf_refinement_error": cdf_error,
                        "moment_refinement_error": moment_error,
                    },
                )
        previous = cdf, moments
    raise SamplingError(
        "diagnostic_failure",
        "AR quadrature did not converge",
        {"nodes": 2048, "cdf_error": cdf_error, "moment_error": moment_error},
    )
