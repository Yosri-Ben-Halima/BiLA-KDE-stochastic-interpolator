"""Reproduce cached-density review findings without changing executed source."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from bilakde.density import InnovationModel


def probe(scale, point):
    data = np.tile([-1.0, 1.0], 10) * scale
    model = InnovationModel(data, data, 2)
    increments = np.full((1, 2), point)
    expected = np.logaddexp(
        model.log_left + model.left.logpdf(increments),
        model.log_right + model.right.logpdf(increments),
    ).sum(axis=-1)[0]
    actual = model.log_increments(increments)[0]
    return {
        "window_scale": scale,
        "increment_probe": point,
        "bandwidth": model.left.bandwidth,
        "direct_kde_log_density": float(expected),
        "cached_log_density": float(actual) if np.isfinite(actual) else str(actual),
        "equivalent": bool(np.isclose(actual, expected, rtol=1e-13, atol=1e-12)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    density_source = Path("src/bilakde/density.py")
    result = {
        "density_source_sha256": hashlib.sha256(density_source.read_bytes()).hexdigest(),
        "probes": [probe(1.0, 3.0), probe(1e150, 1e155), probe(3e-162, 0.0)],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
