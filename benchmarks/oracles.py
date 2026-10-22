import itertools

import numpy as np
from scipy.optimize import brentq
from scipy.special import logsumexp, ndtr
from scipy.stats import norm

from bilakde.density import GaussianKernelMixture, InnovationModel
from bilakde.diagnostics import quantile_mcse
from bilakde.errors import SamplingError
from bilakde.gaussian import GaussianBridge, increments
from bilakde.inputs import GapData
from bilakde.sampling import elliptical_sample

from .bayesian import ar_paths, fit_ar, local_level_posterior


def oracle_cases():
    return (
        [{"kind": "gaussian", "T": T, "z": z} for T in (11, 31, 101) for z in (0, 2)]
        + [{"kind": "mixture", "T": T, "z": z} for T in (4, 6) for z in (0, 2)]
        + [{"kind": "kde_mixture", "T": T, "z": z} for T in (4, 6) for z in (0, 2)]
    )


def kde_reference(T, z):
    """Independent enumeration of every kernel label in a tiny fitted KDE bridge."""
    left, right = np.tile([-1.0, 1.0], 10), np.tile([-0.5, 2.0], 10)
    centers = np.array([-1.0, 1.0, -0.5, 2.0])
    h = np.array([left.std(ddof=1), right.std(ddof=1)]) * 20 ** (-0.2)
    variances = np.repeat(h**2, 2)
    weight = 1 - np.arange(1, T + 1) / T
    mixing = np.column_stack([weight / 2, weight / 2, (1 - weight) / 2, (1 - weight) / 2])
    means = mixing @ centers
    marginal_variances = mixing @ (variances + centers**2) - means**2
    end = float(means.sum() + z * np.sqrt(marginal_variances.sum()))
    with np.errstate(divide="ignore"):
        log_mixing = np.log(mixing)
    labels = np.array(list(itertools.product(range(4), repeat=T)))
    mu, v = centers[labels], variances[labels]
    total = v.sum(axis=1)
    log_weights = log_mixing[np.arange(T), labels].sum(axis=1)
    log_weights -= 0.5 * ((end - mu.sum(axis=1)) ** 2 / total + np.log(2 * np.pi * total))
    keep = np.isfinite(log_weights)
    mu, v, total, log_weights = mu[keep], v[keep], total[keep], log_weights[keep]
    weights = np.exp(log_weights - logsumexp(log_weights))
    prefix = np.cumsum(v, axis=1)[:, :-1]
    component_means = (
        np.cumsum(mu, axis=1)[:, :-1] + prefix / total[:, None] * (end - mu.sum(axis=1))[:, None]
    )
    component_covs = (
        np.minimum(prefix[:, :, None], prefix[:, None, :])
        - prefix[:, :, None] * prefix[:, None, :] / total[:, None, None]
    )

    def target(x):
        r = increments(x, end)
        return logsumexp(
            log_mixing
            - 0.5 * ((r[..., None] - centers) ** 2 / variances + np.log(2 * np.pi * variances)),
            axis=-1,
        ).sum(axis=-1)

    model = InnovationModel(left, right, T)
    reference = GaussianBridge(means, marginal_variances, end)
    probes = reference.draw(np.random.default_rng(3901), 17)
    density_error = float(np.max(np.abs(target(probes) - model.target(probes, end))))
    if density_error > 1e-10:
        raise SamplingError(
            "diagnostic_failure",
            "production KDE differs from frozen density",
            {"oracle_production_log_density_error": density_error},
        )
    return reference, target, model, weights, component_means, component_covs, density_error


def reference_case(case, seed, config, budget=None):
    T = case["T"]
    refresh, density_error = None, None
    if case["kind"] == "gaussian":
        means = np.linspace(-0.2, 0.2, T)
        variances = np.linspace(0.5, 2.0, T)
        end = float(means.sum() + case["z"] * np.sqrt(variances.sum()))
        reference = GaussianBridge(means, variances, end)
        oracle_mean, oracle_cov = reference.mean, reference.covariance
        target = reference.logpdf
        probability = 0.5
        component_mean = oracle_mean[None, :]
        component_covs = oracle_cov[None, :, :]
        weights = np.ones(1)
    elif case["kind"] == "kde_mixture":
        (reference, target, model, weights, component_mean, component_covs, density_error) = (
            kde_reference(T, case["z"])
        )
        refresh = model.conditional_refresh
        oracle_mean = weights @ component_mean
        centered = component_mean - oracle_mean
        oracle_cov = np.sum(
            weights[:, None, None] * (component_covs + centered[:, :, None] * centered[:, None, :]),
            axis=0,
        )
        mid = (T - 1) // 2
        probability = float(
            weights
            @ ndtr(
                (oracle_mean[mid] - component_mean[:, mid]) / np.sqrt(component_covs[:, mid, mid])
            )
        )
    else:
        # Frozen target is independent of the fitted production KDE code.
        end = case["z"] * np.sqrt(T * 1.25)
        reference = GaussianBridge(np.zeros(T), np.full(T, 1.25), end)
        component_mean = []
        log_weight = []
        component_cov = 0.25 * (
            np.minimum.outer(np.arange(1, T), np.arange(1, T))
            - np.outer(np.arange(1, T), np.arange(1, T)) / T
        )
        for signs in itertools.product((-1.0, 1.0), repeat=T):
            mu = np.array(signs)
            cm = np.cumsum(mu)[:-1] + np.arange(1, T) / T * (end - mu.sum())
            component_mean.append(cm)
            log_weight.append(-0.5 * (end - mu.sum()) ** 2 / (0.25 * T))
        weights = np.exp(log_weight - logsumexp(log_weight))
        oracle_mean = weights @ np.array(component_mean)
        oracle_cov = sum(
            w * (component_cov + np.outer(mu - oracle_mean, mu - oracle_mean))
            for w, mu in zip(weights, component_mean)
        )
        mid = (T - 1) // 2
        probability = float(
            sum(
                w * ndtr((oracle_mean[mid] - mu[mid]) / np.sqrt(component_cov[mid, mid]))
                for w, mu in zip(weights, component_mean)
            )
        )

        def target(x):
            r = increments(x, end)
            return logsumexp(-0.5 * (r[..., None] - [-1.0, 1.0]) ** 2 / 0.25, axis=-1).sum(axis=-1)

        # Exercise the complete current production transition on the unchanged
        # frozen two-component target, with independently enumerated reference.
        frozen_kernels = GaussianKernelMixture(
            np.array([-1.0, 1.0]), np.full(2, 0.25), np.full((T, 2), 0.5)
        )
        refresh = frozen_kernels.conditional_refresh
        if case.get("transition") == "elliptical_only":
            refresh = None

        component_mean = np.array(component_mean)
        component_covs = np.broadcast_to(component_cov, (len(weights), T - 1, T - 1))

    # Reference precision has its own larger ensemble; scientific competitor
    # ensembles remain matched at the configured count.
    chains, diag = elliptical_sample(
        target, reference, seed, case.get("n_samples", 16000), config, budget, refresh=refresh
    )
    flat = chains.reshape(-1, T - 1)
    mean_error = float(
        np.max(np.abs(flat.mean(axis=0) - oracle_mean) / np.sqrt(np.diag(oracle_cov)))
    )
    cov_error = float(
        np.linalg.norm(np.cov(flat, rowvar=False) - oracle_cov) / np.linalg.norm(oracle_cov)
    )
    mean_mcse = float(np.max(np.array(diag["mean_mcse"]) / np.sqrt(np.diag(oracle_cov))))
    group_cov = np.array([np.cov(group, rowvar=False) for group in chains])
    cov_mcse = float(
        np.sqrt(np.sum(np.var(group_cov, axis=0, ddof=1)) / 4) / np.linalg.norm(oracle_cov)
    )
    midpoint = (T - 1) // 2
    indicator = chains[:, :, midpoint] <= oracle_mean[midpoint]
    discrepancy = float(abs(indicator.mean() - probability))
    probability_mcse = float(indicator.mean(axis=1).std(ddof=1) / 2)
    # Whole-path second moment and exact lower/upper marginal tail quantiles.
    expected_quadratic = float(np.trace(oracle_cov) + oracle_mean @ oracle_mean)
    quadratic = np.sum(chains**2, axis=-1)
    quadratic_error = abs(float(quadratic.mean()) - expected_quadratic) / expected_quadratic
    quadratic_mcse = float(quadratic.mean(axis=1).std(ddof=1) / 2 / expected_quadratic)
    positions = sorted({0, midpoint, T - 2})
    selected = chains[:, :, positions]
    tail_errors, tail_noise, tail_reference = [], [], []
    for p in (0.025, 0.975):
        exact = []
        for position in positions:
            means = component_mean[:, position]
            sd = np.sqrt(component_covs[:, position, position])
            if len(weights) == 1:
                value = means[0] + sd[0] * norm.ppf(p)
            else:
                value = brentq(
                    lambda x, means=means, sd=sd, p=p: float(weights @ ndtr((x - means) / sd)) - p,
                    float(np.min(means - 12 * sd)),
                    float(np.max(means + 12 * sd)),
                )
            exact.append(value)
        scale = np.sqrt(np.diag(oracle_cov)[positions])
        tail_errors.append(np.abs(np.quantile(selected, p, axis=(0, 1)) - exact) / scale)
        tail_noise.append(quantile_mcse(selected, p) / scale)
        tail_reference.append(exact)
    tail_errors, tail_noise = np.asarray(tail_errors), np.asarray(tail_noise)
    budget.check()
    diagnostic = dict(
        diag,
        oracle_mean_error_sd=mean_error,
        oracle_cov_relative_error=cov_error,
        oracle_mean_mcse_sd=mean_mcse,
        oracle_cov_mcse_relative=cov_mcse,
        oracle_midpoint_probability_error=discrepancy,
        oracle_probability_mcse=probability_mcse,
        oracle_path_quadratic_relative_error=quadratic_error,
        oracle_path_quadratic_mcse_relative=quadratic_mcse,
        oracle_tail_quantile_error_sd=float(tail_errors.max()),
        oracle_tail_quantile_mcse_sd=float(tail_noise.max()),
        oracle_tail_positions=positions,
        oracle_tail_exact_quantiles=tail_reference,
        oracle_tail_errors_sd=tail_errors.tolist(),
        oracle_tail_mcse_sd=tail_noise.tolist(),
        oracle_production_log_density_error=density_error,
        oracle_cdf_threshold=float(oracle_mean[midpoint]),
        oracle_cdf_value=probability,
        oracle_precision_method="two-SE screen; covariance/CDF SE from four independent groups",
    )
    errors = np.r_[mean_error, cov_error, discrepancy, quadratic_error, tail_errors.ravel()]
    noise = np.r_[mean_mcse, cov_mcse, probability_mcse, quadratic_mcse, tail_noise.ravel()]
    tolerance = np.r_[0.10, 0.15, 0.05, 0.15, np.full(tail_errors.size, 0.15)]
    passed = bool(np.all(errors + 2 * noise <= tolerance))
    diagnostic["oracle_status"] = (
        "pass" if passed else ("fail" if np.any(errors - 2 * noise > tolerance) else "inconclusive")
    )
    if not passed:
        raise SamplingError(
            "diagnostic_failure",
            "conditional-law oracle " + diagnostic["oracle_status"],
            diagnostic,
        )
    return {"diagnostics": diagnostic}


def validate_bayesian(seed, config, budget=None):
    # Independently integrate a small posterior by prior importance sampling.
    values = np.array([-0.2, 0.0, np.nan, 0.5, 0.8])
    gap = GapData(values, values.copy(), 2, 3, np.array([0.2]), np.array([0.3]), np.arange(1, 4))
    posterior = fit_ar(gap, budget)
    rng = np.random.default_rng(seed)
    n = 300_000
    phi = 2 * rng.beta(2, 2, n) - 1
    v = 1 / rng.gamma(2, size=n)
    mu = values[0] + np.sqrt(v / 0.01) * rng.normal(size=n)
    logw = np.zeros(n)
    for a, b, d in ((-0.2, 0.0, 1), (0.0, 0.5, 2), (0.5, 0.8, 1)):
        mean = mu + phi**d * (a - mu)
        variance = v * (1 + phi * phi if d == 2 else 1)
        logw += -0.5 * (np.log(2 * np.pi * variance) + (b - mean) ** 2 / variance)
    weights = np.exp(logw - logsumexp(logw))
    discrepancy = abs(float(weights @ phi) - posterior.parameter_means[1])
    importance_ess = float(1 / (weights @ weights))
    # The local-level fixture has 40 unit increments plus a four-step displacement.
    data = np.arange(52.0)
    data[24:27] = np.nan
    from bilakde.inputs import prepare

    alpha, beta = local_level_posterior(prepare(data, 20))
    x = ar_paths(np.zeros(20_000), np.zeros(20_000), np.ones(20_000), 1.0, 3.0, 4, rng)
    mean_error = float(np.abs(x[:, 1:-1].mean(axis=0)).max())
    cov_error = float(np.linalg.norm(np.cov(x[:, 1:-1], rowvar=False) - np.eye(3)))
    budget.check()
    if (
        discrepancy > 0.035
        or importance_ess < 1000
        or (alpha, beta) != (22.5, 23.0)
        or mean_error > 0.04
        or cov_error > 0.06
    ):
        raise SamplingError(
            "diagnostic_failure",
            "independent Bayesian reference check failed",
            {
                "phi_error": discrepancy,
                "importance_ess": importance_ess,
                "ar_mean_error": mean_error,
                "ar_cov_error": cov_error,
            },
        )
    return {
        "diagnostics": {
            "phi_reference_error": discrepancy,
            "importance_ess": importance_ess,
            "ar_path_mean_error": mean_error,
            "ar_path_cov_error": cov_error,
            "local_level_alpha": alpha,
            "local_level_beta": beta,
            **budget.evidence(),
        }
    }
