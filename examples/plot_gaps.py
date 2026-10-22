"""Before/after gallery: uv run --group examples python examples/plot_gaps.py."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from bilakde import BiLAKDEBridge, BridgeError, SummaryPrecisionError
from bilakde.inputs import prepare
from bilakde.results import BridgeResult


def make_examples():
    """Fixed seeds and settings; no selection of favorable reconstructions."""
    for name, seed in [
        ("Gaussian increments", 8),
        ("Skewed increments", 12),
        ("Changing drift and volatility", 21),
    ]:
        rng = np.random.default_rng(seed)
        if seed == 8:
            increments = rng.normal(size=211)
        else:
            increments = rng.exponential(size=211) - 1
            if seed == 21:
                transition = np.clip((np.arange(211) - 85) / 40, 0, 1)
                increments = (0.6 + transition) * increments + 0.4 * transition
        truth = np.r_[0.0, np.cumsum(increments)]
        masked = truth.copy()
        masked[101:111] = np.nan
        yield name, seed, truth, masked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/examples"))
    parser.add_argument("--samples", type=int, default=8000, help="Requested paths per example")
    parser.add_argument(
        "--fallback-90",
        action="store_true",
        help="Check a labeled 90%% interval when the 95%% interval fails",
    )
    parser.add_argument(
        "--reuse", action="store_true", help="Replot saved outputs without inference"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
        }
    )
    fig, axes = plt.subplots(3, 3, figsize=(16, 11), layout="constrained")
    records = []
    for row, (name, seed, truth, masked) in enumerate(make_examples()):
        print(f"Example {row + 1}/3: {name}", flush=True)
        x = np.arange(len(truth))
        gx = np.arange(100, 112)
        record = {
            "name": name,
            "data_seed": seed,
            "sampler_seed": 42,
            "n_samples": args.samples,
            "gap_start": 101,
            "gap_stop": 111,
        }
        result, band = None, None
        try:
            if args.reuse:
                saved_records = json.loads((args.output / "diagnostics.json").read_text())
                record = saved_records[row]
                with np.load(args.output / f"example_{row + 1}.npz") as saved:
                    if not np.array_equal(saved["truth"], truth):
                        raise ValueError("Saved examples do not match the declared data")
                    if "chains" in saved:
                        chains = saved["chains"].copy()
                        result = BridgeResult(
                            prepare(masked, (100, 100)), chains, record["diagnostics"]
                        )
                    if "pointwise_95_percent_interval" in saved:
                        band = saved["pointwise_95_percent_interval"].copy()
                    if "pointwise_90_percent_interval" in saved:
                        band = saved["pointwise_90_percent_interval"].copy()
            else:
                result = BiLAKDEBridge(random_state=42).fit_transform(
                    masked, n_samples=args.samples
                )
                record.update(status="success", diagnostics=result.diagnostics)
                try:
                    band = result.quantiles([0.025, 0.975]).values
                    record["interval_status"] = "success"
                except SummaryPrecisionError as exc:
                    record["interval_status"] = exc.status
                    record["interval_diagnostics"] = exc.diagnostics
        except BridgeError as exc:
            record.update(status=exc.status, reason=exc.reason, diagnostics=exc.diagnostics)
        if result is not None and band is None and args.fallback_90:
            try:
                band = result.quantiles([0.05, 0.95]).values
                record["display_interval_coverage"] = 0.90
                record["fallback_interval_status"] = "success"
            except SummaryPrecisionError as exc:
                record["fallback_interval_status"] = exc.status
                record["fallback_interval_diagnostics"] = exc.diagnostics
        records.append(record)
        for col, ax in enumerate(axes[row]):
            ax.axvspan(100.5, 110.5, color="#f4be52", alpha=0.15)
            ax.plot(x, masked, color="#364152", lw=1.5, zorder=3)
            ax.scatter([100, 111], truth[[100, 111]], s=26, color="#364152", zorder=5)
            ax.set_xlabel("Time step")
            ax.set_ylabel("Series value (arbitrary units)")
            ax.grid(alpha=0.15)
            if col == 0:
                ax.set_title(f"{name}\nBefore: 10 missing values", loc="left")
            else:
                ax.plot(gx, truth[gx], "--", color="#c05a10", lw=1.8, zorder=4)
                if result is not None:
                    if band is not None:
                        ax.fill_between(gx, band[0], band[1], color="#1676ac", alpha=0.18)
                    # Spread the displayed draws across all four retained chains.
                    selected = np.linspace(0, len(result.samples) - 1, 24, dtype=int)
                    ax.plot(gx, result.samples[selected].T, color="#1676ac", alpha=0.12, lw=0.7)
                    ax.plot(
                        gx, result.samples[selected[0]], color="#7b3294", alpha=1, lw=1.8, zorder=4
                    )
                    ax.plot(gx, result.samples.mean(axis=0), color="#075f9b", lw=2.4, zorder=5)
                    title = "After: ensemble mean" if col == 1 else "Gap close-up"
                    if band is None:
                        title += " (band unavailable)"
                    else:
                        coverage = record.get("display_interval_coverage", 0.95)
                        title += f" ({coverage:.0%} pointwise band)"
                else:
                    title = f"No reconstruction: {record['status']}"
                ax.set_title(title, loc="left")
            if col == 2:
                ax.set_xlim(93, 118)
                local = [truth[93:119]]
                if result is not None:
                    local.append(result.samples[selected].ravel())
                if band is not None:
                    local.append(band.ravel())
                low, high = np.concatenate(local).min(), np.concatenate(local).max()
                pad = max((high - low) * 0.12, 0.1)
                ax.set_ylim(low - pad, high + pad)
            else:
                ax.set_xlim(0, len(truth) - 1)
        # Same scale in the full-series before/after comparison.
        low = min(axes[row, 0].get_ylim()[0], axes[row, 1].get_ylim()[0])
        high = max(axes[row, 0].get_ylim()[1], axes[row, 1].get_ylim()[1])
        axes[row, 0].set_ylim(low, high)
        axes[row, 1].set_ylim(low, high)
        arrays = {"truth": truth, "input_with_gap": masked}
        if result is not None:
            arrays.update(imputed=result.imputed_series, chains=result.chains)
        if band is not None:
            coverage = record.get("display_interval_coverage", 0.95)
            arrays[f"pointwise_{coverage * 100:.0f}_percent_interval"] = band
        np.savez_compressed(args.output / f"example_{row + 1}.npz", **arrays)
        print(
            f"  {record['status']}; 95% interval: {record.get('interval_status', 'unavailable')}; "
            f"90% fallback: {record.get('fallback_interval_status', 'not requested')}",
            flush=True,
        )
    legend = [
        Line2D([], [], color="#364152", label="Observed"),
        Patch(color="#f4be52", alpha=0.25, label="Missing interval"),
        Line2D([], [], color="#075f9b", lw=2.4, label="Imputed ensemble mean"),
        Line2D([], [], color="#1676ac", alpha=0.4, label="24 sampled paths"),
        Line2D([], [], color="#7b3294", lw=1.8, label="One sampled path (first draw)"),
        Patch(color="#1676ac", alpha=0.18, label="Pointwise interval (coverage in panel title)"),
        Line2D([], [], color="#c05a10", ls="--", label="Hidden truth (synthetic)"),
    ]
    fig.legend(handles=legend, loc="outside lower center", ncol=3, frameon=False)
    sample_counts = ", ".join(f"{record['n_samples']:,}" for record in records)
    fig.suptitle(
        "BiLA-KDE Bridge | time series before and after gap imputation\n"
        f"Paths requested by row: {sample_counts}; close-ups use their own vertical scale",
        fontsize=16,
    )
    fig.savefig(args.output / "before_after.png", dpi=170)
    fig.savefig(args.output / "before_after.svg")
    plt.close(fig)
    (args.output / "diagnostics.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    (args.output / "README.md").write_text(
        "# Before and after gap imputation\n\n"
        "Open before_after.png or before_after.svg. Each row has one internal ten-value gap. "
        "The original complete series is retained only to show hidden truth; the imputer "
        "receives the masked array. Fixed seeds are declared in examples/plot_gaps.py.\n\n"
        "The blue band is a pointwise interval at the coverage stated in its panel title, "
        "conditional on fitted KDEs, not a "
        "simultaneous whole-path band or an interval for density-estimation uncertainty. "
        "These three illustrations do not measure predictive calibration or superiority. "
        "Diagnostics and any failures are in diagnostics.json; NPZ files retain truth, "
        "masked inputs and successful chain output. Failed quantile checks suppress bands.\n",
        encoding="utf-8",
    )
    print(f"Saved gallery to {args.output / 'before_after.png'}", flush=True)


if __name__ == "__main__":
    main()
