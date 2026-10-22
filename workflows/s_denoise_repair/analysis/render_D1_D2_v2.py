"""Standalone scientific figure from closed diagnostic artifacts only."""
import argparse,hashlib,json,os,socket
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from stage3_gate_v4 import query_parents
REFERENCES=[]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def ref(path):return {"path":str(path),"sha256":sha(path)}

ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016")


def read_reference(name):
    pointer_path=ROOT/"reports"/(name+"_latest.json")
    pointer=json.loads(pointer_path.read_text());path=Path(pointer["path"])
    assert path.is_relative_to(ROOT) and sha(path)==pointer["sha256"]
    REFERENCES.extend([ref(pointer_path),ref(path)])
    return json.loads(path.read_text())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--parent-snapshot',type=Path,required=True)
    args=parser.parse_args()
    assert os.getuid()==1278 and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0] in ['compute-0-8','compute-0-9','compute-0-10','compute-0-11']
    parents=query_parents({'4515524','4515525','4515527'},args.parent_snapshot)
    REFERENCES.append(ref(args.parent_snapshot))
    closure_path=ROOT/'configs/lookup_refit_closure_v1.json';closure=json.loads(closure_path.read_text())
    assert closure['status']=='ACTUAL_FULL_TRAIN_LOOKUP_REFIT_CLOSED' and closure['actual_parent']==parents['4515527']
    lookup_ref=closure['result_reference'];assert sha(lookup_ref['path'])==lookup_ref['sha256']
    REFERENCES.extend([ref(closure_path),lookup_ref])
    baseline=closure['metrics']['D3_FULL2000']['lookup_rmse_A']
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
        "COMPLETED D1 / D2 - SEE THE SEPARATE D3 GATE\n\n"
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
        f"New TRAIN-only lookup / D3 FULL2000: {baseline:.8f} A.\n"
        "These completed diagnostics do not determine D3 acceptance."
    )
    axes[1, 1].text(0, 1, text, va="top", fontsize=9.3, linespacing=1.45)
    fig.suptitle("S denoising repair: completed D1 / D2 diagnostics", fontsize=15)
    destination = ROOT / "reports/D1_D2_completed_v2"
    assert not destination.with_suffix('.pdf').exists() and not destination.with_suffix('.png').exists()
    fig.savefig(destination.with_suffix(".pdf"))
    fig.savefig(destination.with_suffix(".png"), dpi=140)
    plt.close(fig)
    report={'status':'D1_D2_CLOSED_DIAGNOSTICS_RENDERED_D3_GATE_SEPARATE','job_id':os.environ['SLURM_JOB_ID'],
       'actual_diagnostic_and_lookup_parents':parents,'source_references':REFERENCES+[ref(Path(__file__))],
       'artifacts':[ref(destination.with_suffix('.pdf')),ref(destination.with_suffix('.png'))],
       'scientific_measurements_recomputed':False,'D3_gate_pass_claimed':False,'full_training_complete_claimed':False}
    with (ROOT/'reports/D1_D2_completed_v2_render.json').open('x') as stream:
        json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
    print(report['status'],flush=True)


if __name__ == "__main__":
    main()
