"""Standalone scientific figure from closed diagnostic artifacts only."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016")


def read_reference(name):
    ref = json.loads((ROOT / "reports" / (name + "_latest.json")).read_text())
    return json.loads(Path(ref["path"]).read_text())


def main():
    d1, d2 = read_reference("D1"), read_reference("D2")
    fig, axes = plt.subplots(2, 2, figsize=(11.7, 8.3), constrained_layout=True)
    tasks = ["element", "distance", "bond_order"]
    colors = ["#4766ab", "#da8b36", "#499d80"]
    axes[0, 0].bar(tasks, [100 * d1["fractions_mean"][k] for k in tasks], color=colors)
    axes[0, 0].set(ylabel="Mean per-batch share of sum of gradient norms (%)", title="D1: all shared-backbone parameters; 200 batches", ylim=(0, 100))
    cosine = np.eye(3)
    for (i, j), key in [((0, 1), "element/distance"), ((0, 2), "element/bond_order"), ((1, 2), "distance/bond_order")]:
        cosine[i, j] = cosine[j, i] = d1["pair_cosines_mean"][key]
    image = axes[0, 1].imshow(cosine, cmap="RdBu_r", vmin=-1, vmax=1)
    axes[0, 1].set(xticks=range(3), yticks=range(3), xticklabels=tasks, yticklabels=tasks, title="D1: mean pairwise gradient cosine")
    for i in range(3):
        for j in range(3):
            axes[0, 1].text(j, i, f"{cosine[i, j]:.3f}", ha="center", va="center", color="white" if i == j else "black")
    fig.colorbar(image, ax=axes[0, 1], shrink=0.8)
    variants = list(d2["aggregate"])
    values = [d2["aggregate"][k]["local_rmse_A"] for k in variants]
    labels = ["0.1 / N\nall pairs", "1 / N\nall pairs", "0.1 / degree\n5 A radius", "1 / degree\n5 A radius"]
    axes[1, 0].bar(labels, values, color=["#da8b36", "#499d80", "#b76b6b", "#4766ab"])
    axes[1, 0].set(yscale="log", ylabel="Achieved local RMSE (A), log scale", title="D2: bounded symmetric free weights; 1,000 molecules")
    for index, value in enumerate(values):
        axes[1, 0].text(index, value * 1.2, f"{value:.3g}", ha="center", fontsize=9)
    axes[1, 0].set_ylim(1e-6, 0.1)
    axes[1, 1].axis("off")
    text = (
        "INTERIM DIAGNOSTICS - NOT THE SMALL-SCALE GATE\n\n"
        "D1 checkpoint: old B3, epoch 3. No optimizer updates.\n"
        f"All-parameter clip threshold 1.0 triggered in {100*d1['clip_trigger_fraction_all_parameters']:.1f}% of batches.\n\n"
        "D2: sigma=0.10 A, 2,000 projected Adam steps per variant.\n"
        "Float64 offline optimization; 70,729 clean-distance<2 A pairs.\n"
        "Errors are achieved feasible solutions, not certified minima.\n\n"
        "The original 0.1/N form can attain 0.00851 A.\n"
        "This refutes a hard error floor near 0.1 A for that form.\n"
        "It does not show the old network can learn the free weights.\n\n"
        "Network features, objective alignment and optimization\n"
        "remain to be assessed by D3 and the refitted lookup baseline.\n"
        "Full training has not started; the small-scale gate is pending."
    )
    axes[1, 1].text(0, 1, text, va="top", fontsize=9.3, linespacing=1.45)
    fig.suptitle("S denoising repair: measured D1 / D2 diagnostics", fontsize=15)
    destination = ROOT / "reports/D1_D2_diagnostics"
    fig.savefig(destination.with_suffix(".pdf"))
    fig.savefig(destination.with_suffix(".png"), dpi=140)
    plt.close(fig)


if __name__ == "__main__":
    main()
