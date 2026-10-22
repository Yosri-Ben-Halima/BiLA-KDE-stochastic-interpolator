"""Animate saved examples: uv run --group examples python examples/animate_distributions.py."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter

from bilakde.density import InnovationModel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/examples"))
    args = parser.parse_args()
    records = json.loads((args.output / "diagnostics.json").read_text())
    fig, axes = plt.subplots(3, 2, figsize=(12, 10), layout="constrained")
    artists = []
    for row, record in enumerate(records):
        with np.load(args.output / f"example_{row + 1}.npz") as saved:
            start, stop = record["gap_start"], record["gap_stop"]
            values = saved["input_with_gap"]
            model = InnovationModel(
                np.diff(values[:start]), np.diff(values[stop:]), stop - start + 1
            )
            lower = min(
                model.left.data.min() - 4 * model.left.bandwidth,
                model.right.data.min() - 4 * model.right.bandwidth,
            )
            upper = max(
                model.left.data.max() + 4 * model.left.bandwidth,
                model.right.data.max() + 4 * model.right.bandwidth,
            )
            grid = np.linspace(lower, upper, 400)
            left, right = np.exp(model.left.logpdf(grid)), np.exp(model.right.logpdf(grid))
            density = left[:, None] * model.weights + right[:, None] * (1 - model.weights)
            ax = axes[row, 0]
            ax.plot(grid, left, color="#1676ac", alpha=0.35, label="Left KDE")
            ax.plot(grid, right, color="#c05a10", alpha=0.35, label="Right KDE")
            (line,) = ax.plot(grid, density[:, 0], color="#7b3294", lw=2.3, label="Current mixture")
            ax.set(
                xlim=(lower, upper),
                ylim=(0, 1.1 * max(left.max(), right.max())),
                title=f"{record['name']}\nIncrement density before endpoint conditioning",
                xlabel="Increment",
                ylabel="Probability density",
            )
            ax.legend(fontsize=8, frameon=False)
            note = ax.text(0.98, 0.70, "", transform=ax.transAxes, ha="right", fontsize=9)
            ax = axes[row, 1]
            ax.set(
                title="Series-value density after endpoint conditioning",
                xlabel="Series value at the current time step",
                ylabel="Empirical density",
            )
            item = {
                "line": line,
                "density": density,
                "note": note,
                "weights": model.weights,
                "start": start,
            }
            if "chains" in saved:
                chains = saved["chains"]
                samples = chains.reshape(-1, chains.shape[-1])
                bins = np.linspace(samples[:, 1:-1].min(), samples[:, 1:-1].max(), 55)
                hist = np.column_stack(
                    [
                        np.histogram(column, bins=bins, density=True)[0]
                        for column in samples[:, 1:-1].T
                    ]
                )
                centers = (bins[1:] + bins[:-1]) / 2
                path = samples[0]
                (curve,) = ax.plot(centers, hist[:, 0], color="#075f9b", lw=2)
                marker = ax.axvline(path[1], color="#7b3294", lw=1.8, label="First sampled path")
                ax.set(
                    xlim=(min(bins[0], samples[0, -1]), max(bins[-1], samples[0, -1])),
                    ylim=(0, hist.max() * 1.15),
                )
                endpoint = ax.text(0.5, 0.75, "", transform=ax.transAxes, ha="center")
                coverage = record.get("display_interval_coverage", 0.95)
                band_key = f"pointwise_{coverage * 100:.0f}_percent_interval"
                if band_key in saved:
                    band = saved[band_key].copy()
                    shade = ax.axvspan(
                        band[0, 1],
                        band[1, 1],
                        color="#1676ac",
                        alpha=0.14,
                        label=f"{coverage:.0%} pointwise interval",
                    )
                    item.update(band=band, shade=shade)
                ax.legend(fontsize=8, frameon=False)
                item.update(curve=curve, hist=hist, marker=marker, path=path, endpoint=endpoint)
            else:
                ax.text(
                    0.5,
                    0.5,
                    f"Unavailable: {record['status']}\nNo accepted path distribution",
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                )
                ax.set_xticks([])
                ax.set_yticks([])
            for ax in axes[row]:
                ax.grid(alpha=0.15)
                ax.spines[["top", "right"]].set_visible(False)
            artists.append(item)
    heading = fig.suptitle("Distribution evolution", fontsize=17)
    fig.supxlabel(
        "Fixed fitted KDEs; panels have separate scales. Purple marks one sampled path.\n"
        "Shading: labeled pointwise interval, conditional on fitted KDEs; calibration is untested.",
        fontsize=10,
    )

    def update(step):
        heading.set_text(
            f"Distribution evolution | gap increment {step + 1}/11 | time {101 + step}"
        )
        for item in artists:
            item["line"].set_ydata(item["density"][:, step])
            weight = item["weights"][step]
            item["note"].set_text(f"Left weight: {weight:.0%}\nRight weight: {1 - weight:.0%}")
            if "curve" in item:
                final = step == 10
                item["curve"].set_visible(not final)
                point = item["path"][step + 1]
                item["marker"].set_xdata([point, point])
                if "shade" in item:
                    low, high = item["band"][:, step + 1]
                    item["shade"].set_visible(not final)
                    item["shade"].set_x(low)
                    item["shade"].set_width(high - low)
                item["endpoint"].set_text(
                    "Observed right endpoint\nPoint mass (fixed value)" if final else ""
                )
        return []

    animation = FuncAnimation(
        fig, update, frames=[0, 0, *range(11), 10, 10], interval=333, repeat=True, blit=False
    )
    animation.save(args.output / "distribution_evolution.gif", writer=PillowWriter(fps=3), dpi=110)
    plt.close(fig)
    print(f"Saved {args.output / 'distribution_evolution.gif'}")


if __name__ == "__main__":
    main()
