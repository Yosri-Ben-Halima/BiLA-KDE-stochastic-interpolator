"""Plot fitted density evolution and saved bridge marginals without rerunning sampling."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from bilakde.density import InnovationModel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/examples"))
    args = parser.parse_args()
    records = json.loads((args.output / "diagnostics.json").read_text())
    fig, axes = plt.subplots(3, 3, figsize=(16, 11), layout="constrained")
    for row, record in enumerate(records):
        with np.load(args.output / f"example_{row + 1}.npz") as saved:
            values = saved["input_with_gap"]
            start, stop = record["gap_start"], record["gap_stop"]
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
            grid = np.linspace(lower, upper, 500)
            left, right = np.exp(model.left.logpdf(grid)), np.exp(model.right.logpdf(grid))
            density = left[:, None] * model.weights + right[:, None] * (1 - model.weights)
            ax = axes[row, 0]
            ax.plot(grid, left, color="#1676ac", label="Left observed KDE")
            ax.plot(grid, right, color="#c05a10", label="Right observed KDE")
            middle = model.T // 2
            ax.plot(
                grid, density[:, middle], "--", color="#7b3294", label=f"Gap increment {middle + 1}"
            )
            ax.set(
                title=f"{record['name']}\nFitted increment densities",
                xlabel="Increment (change per time step)",
                ylabel="Probability density",
            )
            ax.legend(fontsize=8, frameon=False)
            ax.grid(alpha=0.15)
            ax = axes[row, 1]
            times = np.arange(start, stop + 1)
            mesh = ax.pcolormesh(times, grid, density, shading="nearest", cmap="Blues", vmin=0)
            ax.plot(times, model.means, color="#7b3294", lw=1.8, label="Mixture mean")
            ax.set(
                title="Increment distribution across the gap\nBefore endpoint conditioning",
                xlabel="Time step of increment arrival",
                ylabel="Increment",
            )
            ax.legend(fontsize=8, frameon=False)
            fig.colorbar(mesh, ax=ax, label="Probability density", shrink=0.8)
            ax = axes[row, 2]
            ax.set(
                title="Series-value distribution inside the gap\nAfter endpoint conditioning",
                xlabel="Missing time step",
                ylabel="Series value",
            )
            if "chains" in saved:
                chains = saved["chains"]
                samples = chains.reshape(-1, chains.shape[-1])[:, 1:-1]
                bins = np.linspace(samples.min(), samples.max(), 65)
                counts = np.column_stack(
                    [np.histogram(column, bins=bins, density=True)[0] for column in samples.T]
                )
                mesh = ax.pcolormesh(
                    np.arange(start, stop + 1) - 0.5, bins, counts, cmap="Blues", vmin=0
                )
                x = np.arange(start, stop)
                ax.plot(x, samples.mean(axis=0), color="#075f9b", lw=2, label="Ensemble mean")
                ax.plot(x, samples[0], color="#7b3294", lw=1.8, label="First sampled path")
                ax.legend(fontsize=8, frameon=False)
                fig.colorbar(mesh, ax=ax, label="Empirical density", shrink=0.8)
            else:
                ax.set_facecolor("#f3f4f6")
                ax.text(
                    0.5,
                    0.5,
                    f"Unavailable: {record['status']}\nNo accepted bridge ensemble",
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    color="#555555",
                )
                ax.set_xticks([])
                ax.set_yticks([])
    fig.suptitle("Distribution evolution | BiLA-KDE Bridge", fontsize=18)
    fig.supxlabel(
        "Each panel has its own density scale. Bridge heatmaps are empirical marginals, "
        "not validated quantiles or a joint path density.",
        fontsize=10,
    )
    for extension in ("png", "svg"):
        fig.savefig(args.output / f"distribution_evolution.{extension}", dpi=170)
    plt.close(fig)
    print(f"Saved {args.output / 'distribution_evolution.png'}")


if __name__ == "__main__":
    main()
