"""Compact animation: uv run --group examples python examples/animate_styled.py."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Patch

from bilakde.density import InnovationModel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/examples"))
    args = parser.parse_args()
    records = json.loads((args.output / "diagnostics.json").read_text())
    record = records[2]
    coverage = record.get("display_interval_coverage", 0.95)
    with np.load(args.output / "example_3.npz") as saved:
        values = saved["input_with_gap"].copy()
        chains = saved["chains"].copy()
        band = saved[f"pointwise_{coverage * 100:.0f}_percent_interval"].copy()
    samples = chains.reshape(-1, chains.shape[-1])
    start, stop = record["gap_start"], record["gap_stop"]
    model = InnovationModel(np.diff(values[:start]), np.diff(values[stop:]), stop - start + 1)
    grid = np.linspace(
        min(
            model.left.data.min() - 4 * model.left.bandwidth,
            model.right.data.min() - 4 * model.right.bandwidth,
        ),
        max(
            model.left.data.max() + 4 * model.left.bandwidth,
            model.right.data.max() + 4 * model.right.bandwidth,
        ),
        500,
    )
    left, right = np.exp(model.left.logpdf(grid)), np.exp(model.right.logpdf(grid))
    ink, muted, blue, orange, purple = "#172f42", "#697c89", "#007f8b", "#d28c3d", "#8653a3"
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.labelcolor": muted,
            "xtick.color": muted,
            "ytick.color": muted,
            "axes.edgecolor": "#dce5e9",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "text.color": ink,
        }
    )
    fig = plt.figure(figsize=(10, 6.2), facecolor="#f3f6f7")
    fig.text(0.055, 0.927, "BiLA–KDE Bridge", fontsize=25, fontweight="bold", color=ink)
    fig.text(
        0.055,
        0.881,
        "Dérive & volatilité variables  /  Illustration synthétique",
        fontsize=10,
        color=muted,
    )
    fig.text(
        0.945,
        0.929,
        f"{len(samples):,} trajectoires".replace(",", " "),
        ha="right",
        fontsize=10,
        color=blue,
        fontweight="bold",
    )
    fig.text(
        0.945, 0.891, f"Bande ponctuelle à {coverage:.0%}", ha="right", fontsize=9, color=muted
    )
    for x in [0.045, 0.525]:
        card = FancyBboxPatch(
            (x, 0.205),
            0.43,
            0.605,
            boxstyle="round,pad=0.012,rounding_size=0.018",
            facecolor="white",
            edgecolor="#e1e8eb",
            lw=0.8,
            transform=fig.transFigure,
            zorder=-1,
        )
        fig.add_artist(card)
    fig.text(0.065, 0.767, "01   DISTRIBUTION", fontsize=10, fontweight="bold")
    fig.text(0.065, 0.735, "Incréments avant conditionnement", fontsize=9, color=muted)
    fig.text(0.545, 0.767, "02   RECONSTRUCTION", fontsize=10, fontweight="bold")
    fig.text(0.545, 0.735, "Trajectoires contraintes aux deux extrémités", fontsize=9, color=muted)
    density_ax = fig.add_axes([0.091, 0.33, 0.35, 0.35])
    bridge_ax = fig.add_axes([0.572, 0.33, 0.35, 0.35])
    for ax in (density_ax, bridge_ax):
        ax.set_facecolor("white")
        ax.set_axisbelow(True)
        ax.grid(axis="y", color="#eaf0f2", lw=0.8)
        ax.tick_params(labelsize=8, length=0, pad=7)
    density_ax.plot(grid, left, color=blue, alpha=0.35, lw=1.3, ls="--")
    density_ax.plot(grid, right, color=orange, alpha=0.65, lw=1.3, ls="--")
    (line,) = density_ax.plot(grid, left, color=blue, lw=2.6)
    fill = density_ax.fill_between(grid, left, color=blue, alpha=0.10)
    density_ax.set(
        xlim=(grid[0], grid[-1]),
        ylim=(0, max(left.max(), right.max()) * 1.15),
        xlabel="Variation par pas de temps",
        ylabel="Densité",
    )
    density_ax.legend(
        handles=[
            Line2D([], [], color=blue, ls="--", alpha=0.5, label="Gauche"),
            Line2D([], [], color=orange, ls="--", label="Droite"),
        ],
        loc="upper right",
        frameon=False,
        fontsize=8,
    )
    weight_text = fig.text(0.065, 0.235, "", fontsize=9, color=blue)
    gx = np.arange(start - 1, stop + 1)
    selected = np.linspace(0, len(samples) - 1, 24, dtype=int)
    bridge_ax.fill_between(gx, band[0], band[1], color=blue, alpha=0.12, zorder=1)
    bridge_ax.plot(gx, samples[selected].T, color=blue, alpha=0.09, lw=0.7, zorder=2)
    bridge_ax.plot(np.arange(len(values)), values, color="#697c89", lw=1.5, zorder=3)
    bridge_ax.plot(gx, samples.mean(axis=0), color=blue, lw=2.3, zorder=4)
    path = samples[0]
    bridge_ax.plot(gx, path, color=purple, lw=2, alpha=1, zorder=5)
    bridge_ax.scatter(gx[[0, -1]], path[[0, -1]], s=24, color=ink, zorder=6)
    cursor = bridge_ax.axvline(start, color=purple, alpha=0.2, lw=1)
    (dot,) = bridge_ax.plot(
        [start],
        [path[1]],
        "o",
        color=purple,
        ms=7,
        markeredgecolor="white",
        markeredgewidth=1.5,
        zorder=7,
    )
    local = np.r_[
        samples[selected].ravel(), band.ravel(), values[start - 4 : start], values[stop : stop + 4]
    ]
    low, high = local.min(), local.max()
    bridge_ax.set(
        xlim=(start - 3, stop + 3),
        ylim=(low - 0.1 * (high - low), high + 0.1 * (high - low)),
        xlabel="Pas de temps",
        ylabel="Valeur",
    )
    bridge_ax.legend(
        handles=[
            Line2D([], [], color=purple, lw=2, label="Un tirage"),
            Line2D([], [], color=blue, lw=2, label="Moyenne"),
            Patch(facecolor=blue, alpha=0.12, label=f"Bande {coverage:.0%}"),
        ],
        loc="upper left",
        frameon=False,
        fontsize=7.5,
        handlelength=1.5,
    )
    time_text = fig.text(0.545, 0.235, "", fontsize=9, color=purple)
    rail_ax = fig.add_axes([0.055, 0.132, 0.89, 0.025])
    rail_ax.set(xlim=(0, 1), ylim=(-1, 1))
    rail_ax.axis("off")
    rail_ax.plot([0, 1], [0, 0], color="#dce5e9", lw=3, solid_capstyle="round")
    (progress,) = rail_ax.plot([0, 0], [0, 0], color=blue, lw=3, solid_capstyle="round")
    (bead,) = rail_ax.plot([0], [0], "o", ms=5, color=blue, clip_on=False)
    fig.text(0.055, 0.094, "BORD GAUCHE", color=muted, fontsize=7.5)
    fig.text(0.945, 0.094, "BORD DROIT", ha="right", color=muted, fontsize=7.5)
    fig.text(
        0.5,
        0.042,
        "Bande conditionnelle aux KDE ajustées · calibration non établie",
        ha="center",
        fontsize=8,
        color=muted,
    )

    def update(frame):
        fraction = np.clip((frame - 4) / 48, 0, 1)
        arrival = start - 1 + fraction * (stop - start + 1)
        weight = 1 - (arrival - start + 1) / model.T
        density = weight * left + (1 - weight) * right
        line.set_ydata(density)
        vertices = np.column_stack([np.r_[grid[0], grid, grid[-1]], np.r_[0, density, 0]])
        fill.set_verts([vertices])
        weight_text.set_text(f"Mélange   {weight:.0%} gauche  /  {1 - weight:.0%} droite")
        cursor.set_xdata([arrival, arrival])
        dot.set_data([arrival], [np.interp(arrival, gx, path)])
        time_text.set_text(f"Temps   {arrival:.1f}   /   {stop}")
        progress.set_xdata([0, fraction])
        bead.set_xdata([fraction])
        return []

    update(28)
    fig.savefig(args.output / "distribution_evolution_styled.png", dpi=130)
    animation = FuncAnimation(fig, update, frames=60, interval=1000 / 12, blit=False)
    animation.save(
        args.output / "distribution_evolution_styled.gif", writer=PillowWriter(fps=12), dpi=110
    )
    plt.close(fig)
    print(f"Saved {args.output / 'distribution_evolution_styled.gif'}")


if __name__ == "__main__":
    main()
