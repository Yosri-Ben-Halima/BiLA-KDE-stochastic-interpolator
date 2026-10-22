import time

import numpy as np
from scipy.interpolate import PchipInterpolator

from bilakde.bridge import _fit
from bilakde.density import InnovationModel
from bilakde.gaussian import GaussianBridge
from bilakde.inputs import prepare
from bilakde.results import BridgeResult

from .bayesian import ar_paths, fit_ar, local_level_posterior
from .scenarios import seed_for
from .scoring import scores

METHODS = (
    "bila",
    "pooled",
    "fixed",
    "left",
    "right",
    "endpoint_corrected",
    "bayesian_local_level",
    "gaussian_bridge",
    "bayesian_ar",
    "plugin_ar",
    "linear",
    "pchip",
)
LEVELS = (0.025, 0.1, 0.25, 0.5, 0.75, 0.9, 0.975)


def predict(method, series, seed, n_samples, config, budget, prior=(2.0, 1.0, 0.01)):
    """Prediction has no access to the withheld truth."""
    gap = prepare(series, 100)
    if method in ("bila", "pooled", "fixed", "left", "right"):
        mode = "linear" if method == "bila" else method
        return _fit(series, (100, 100), seed, n_samples, config, mode, budget=budget)
    if method in ("linear", "pchip"):
        if method == "linear":
            return np.linspace(gap.a, gap.b, gap.T + 1)
        indexes = np.r_[np.arange(gap.start - 101, gap.start), np.arange(gap.stop, gap.stop + 101)]
        return PchipInterpolator(indexes, gap.values[indexes])(
            np.arange(gap.start - 1, gap.stop + 1)
        )
    start = time.perf_counter()
    posterior = None
    if method in ("bayesian_ar", "plugin_ar"):
        posterior = fit_ar(gap, budget, *prior)
    elif method in ("bayesian_local_level", "gaussian_bridge"):
        alpha, beta = local_level_posterior(gap, *prior[:2])
    model = InnovationModel(gap.left, gap.right, gap.T) if method == "endpoint_corrected" else None
    fit_time = time.perf_counter() - start
    groups = []
    streams = np.random.SeedSequence(seed).spawn(4)
    for stream in streams:
        budget.check()
        rng = np.random.default_rng(stream)
        count = n_samples // 4
        if model is not None:
            r = model.draw_increments(rng, count)
            cumulative = np.cumsum(r, axis=1)
            fraction = np.arange(1, gap.T + 1) / gap.T
            interior = (
                gap.a + fraction * (gap.b - gap.a) + cumulative - fraction * cumulative[:, -1, None]
            )
            paths = np.c_[np.full(count, gap.a), interior]
            paths[:, -1] = gap.b
        elif method in ("bayesian_local_level", "gaussian_bridge"):
            v = (
                beta / rng.gamma(alpha, size=count)
                if method == "bayesian_local_level"
                else np.full(count, beta / (alpha - 1))
            )
            standard = GaussianBridge(np.zeros(gap.T), np.ones(gap.T), 0.0).draw(rng, count)
            mean = np.arange(1, gap.T) / gap.T * (gap.b - gap.a)
            paths = np.c_[
                np.full(count, gap.a),
                gap.a + mean + standard * np.sqrt(v[:, None]),
                np.full(count, gap.b),
            ]
        else:
            if method == "bayesian_ar":
                mu, phi, v = posterior.draw(rng, count)
            else:
                mu0, phi0, v0 = posterior.parameter_means
                mu, phi, v = (np.full(count, value) for value in (mu0, phi0, v0))
            paths = ar_paths(mu, phi, v, gap.a, gap.b, gap.T, rng)
        groups.append(paths)
    diagnostic = {
        "inference": "iid numerical-posterior/bridge draws" if posterior else "iid bridge draws",
        "fit_seconds": fit_time,
        "seed": seed,
        "config": {"memory_limit_bytes": config.memory_limit_bytes},
        "chain_streams": [list(s.spawn_key) for s in streams],
    }
    if posterior:
        diagnostic.update(posterior.metadata)
    diagnostic.update(budget.evidence())
    return BridgeResult(gap, np.stack(groups), diagnostic)


def evaluate(method, series, truth, seed, n_samples, config, prior=(2.0, 1.0, 0.01), budget=None):
    begin = time.perf_counter()
    prediction = predict(method, series, seed, n_samples, config, budget, prior)
    budget.check()
    if isinstance(prediction, np.ndarray):
        error = prediction[1:-1] - truth
        metrics = {"rmse": float(np.sqrt(np.mean(error**2))), "mae": float(np.abs(error).mean())}
        return {
            "metrics": metrics,
            "diagnostics": budget.evidence(),
            "chains": None,
            "point": prediction,
        }
    prediction.quantiles(LEVELS)
    budget.check()
    metrics = scores(prediction.chains[:, :, 1:-1], truth, seed_for(seed, "score"))
    budget.check()
    diagnostics = dict(prediction.diagnostics, **budget.evidence())
    diagnostics["standalone_seconds"] = time.perf_counter() - begin
    return {
        "metrics": metrics,
        "diagnostics": diagnostics,
        "chains": prediction.chains,
        "point": prediction.samples.mean(axis=0),
    }
