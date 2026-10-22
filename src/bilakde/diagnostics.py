import warnings

import numpy as np


def _arviz():
    import arviz

    return arviz


def assess(chains, end):
    from .gaussian import increments

    az = _arviz()
    r = increments(chains, end)
    features = np.concatenate(
        [
            chains,
            chains.max(axis=-1, keepdims=True),
            chains.min(axis=-1, keepdims=True),
            (r * r).sum(axis=-1, keepdims=True),
        ],
        axis=-1,
    )
    data = az.from_dict(posterior={"features": features})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        rh = az.rhat(data, method="rank")["features"].values
        bulk = az.ess(data, method="bulk")["features"].values
        tail = az.ess(data, method="tail")["features"].values
        mcse = az.mcse(data, method="mean")["features"].values
    sd = chains.std(axis=(0, 1), ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = mcse[: chains.shape[-1]] / sd
    finite = all(np.isfinite(v).all() for v in (rh, bulk, tail, mcse, ratio))
    passed = bool(
        finite
        and rh.max() <= 1.01
        and bulk.min() >= 400
        and tail.min() >= 400
        and ratio.max() <= 0.05
    )

    def scalar(v):
        return float(v) if np.isfinite(v) else None

    return {
        "diagnostics_pass": passed,
        "rhat_max": scalar(np.max(rh)),
        "ess_bulk_min": scalar(np.min(bulk)),
        "ess_tail_min": scalar(np.min(tail)),
        "mean_mcse_ratio_max": scalar(np.max(ratio)),
        "mean_mcse": [scalar(x) for x in mcse[: chains.shape[-1]]],
        "finite_diagnostics": finite,
    }


def quantile_mcse(chains, probability):
    az = _arviz()
    data = az.from_dict(posterior={"levels": chains})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return az.mcse(data, method="quantile", prob=probability)["levels"].values
