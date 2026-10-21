import hashlib

import numpy as np

PRIMARY = ("gaussian", "skew", "scale", "shape")
STRESS = ("ar_gaussian", "ar_skew", "garch", "switching_ar")


def primary_cases(replicates):
    for replicate in range(replicates):
        for scenario in PRIMARY:
            for missing in (10, 30, 100):
                yield {
                    "id": f"{scenario}-gap{missing}-r{replicate}",
                    "scenario": scenario,
                    "missing": missing,
                    "replicate": replicate,
                    "partition": "primary",
                }


def seed_for(seed, *parts):
    text = "|".join(map(str, (seed, *parts)))
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "little")


def skew(rng, n):
    component = rng.random(n) < 0.75
    return np.where(component, rng.normal(-0.5, 0.5, n), rng.normal(1.5, 0.75, n)) / np.sqrt(
        1.078125
    )


def generate(case, seed, window=100):
    rng = np.random.default_rng(
        seed_for(seed, case["partition"], case["scenario"], case["missing"], case["replicate"])
    )
    m = case["missing"]
    T = m + 1
    n = 2 * window + T
    time = np.arange(1, n + 1) - window
    u = np.clip(time / T, 0, 1)
    name = case["scenario"]
    if name in PRIMARY:
        if name == "gaussian":
            r = rng.normal(size=n)
        else:
            r = skew(rng, n)
            if name == "scale":
                r *= 0.7 + 0.8 * u
            if name == "shape":
                r *= np.where(rng.random(n) < u, -1, 1)
        full = np.r_[0.0, np.cumsum(r)]
    elif name == "garch":
        previous = 0.0
        h = 1.0
        r = np.empty(n + 1000)
        for i in range(len(r)):
            h = 0.05 + 0.10 * previous**2 + 0.85 * h
            previous = np.sqrt(h) * rng.normal()
            r[i] = previous
        full = np.r_[0.0, np.cumsum(r[-n:])]
    else:
        epsilon = skew(rng, n + 1001) if name == "ar_skew" else rng.normal(size=n + 1001)
        full = np.zeros(n + 1001)
        for i in range(1, len(full)):
            mu = 2.0 if name == "switching_ar" and i - 1000 >= window + T // 2 else 0.0
            full[i] = mu + 0.6 * (full[i - 1] - mu) + epsilon[i]
        full = full[-(n + 1) :]
    start = window + 1
    truth = full[start : start + m].copy()
    masked = full.copy()
    masked[start : start + m] = np.nan
    return masked, truth
