"""Array/pandas demonstration; the main guard is required for worker spawning."""

import numpy as np
import pandas as pd

from bilakde import BiLAKDEBridge, BridgeError


def main():
    values = np.r_[0.0, np.cumsum(np.random.default_rng(8).normal(size=211))]
    values[101:111] = np.nan
    series = pd.Series(
        values,
        index=pd.date_range("2026-01-01", periods=len(values), freq="h", tz="UTC"),
        name="sensor",
    )
    try:
        result = BiLAKDEBridge(random_state=42).fit_transform(series, n_samples=4000)
        print("Completed:", result.imputed_series.iloc[100:112].to_string())
        print("Samples:", result.samples.shape)
        print(
            "Diagnostics:",
            {
                k: result.diagnostics[k]
                for k in ("rhat_max", "ess_bulk_min", "ess_tail_min", "elapsed_seconds")
            },
        )
        summary = result.quantiles([0.025, 0.5, 0.975])
        print("Pointwise quantiles:", summary.values)
    except BridgeError as exc:
        print("Unsuccessful:", exc.status, exc.reason, exc.diagnostics)
        raise


if __name__ == "__main__":
    main()
