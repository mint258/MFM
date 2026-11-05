"""Isolated 1,000-synthetic-molecule head capacity diagnostic, not D-3 acceptance.

CPU execution only. H0 is a fixed synthetic 512-dimensional invariant feature
tensor, not the learned full backbone. Every run persists offline W&B history.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import time

ROOT = Path(__file__).absolute().parents[2]
sys.path.insert(0, str(ROOT / "current"))
CASES = ("graph_H1", "graph_H2", "graph_H3", "atom", "pair", "atom_vector",
         "dipole_vector", "dipole_magnitude", "denoise")


def fixture(case, molecules, seed):
    import torch
    from phychem_mfm.model.v3_heads import V3HeadBank
    from phychem_mfm.phase1.v3_contract import FieldSpec, FieldTarget, LabelRegistry, TrainNormalization
    torch.manual_seed(seed)
    h0 = torch.randn(molecules * 3, 512) * .3
    pos = torch.randn(molecules * 3, 3) * .3
    batch = torch.arange(molecules).repeat_interleave(3)
    indices = torch.arange(molecules) * 3
    pair = torch.stack((torch.cat((indices, indices + 1)), torch.cat((indices + 1, indices + 2))))
    source = torch.stack([indices + j for j in range(3) for k in range(3) if j != k], dim=1).reshape(-1)
    dest = torch.stack([indices + k for j in range(3) for k in range(3) if j != k], dim=1).reshape(-1)
    scalar = h0[:, :1] - .2 * h0[:, 1:2]
    if case.startswith("graph"):
        field = FieldSpec("synthetic", "P", "fixture", "graph")
        values = scalar.new_zeros((molecules, 1)).index_add(0, batch, scalar) / 3
    elif case == "atom":
        field, values = FieldSpec("synthetic", "P", "fixture", "atom"), scalar
    elif case == "pair":
        field = FieldSpec("synthetic", "P", "fixture", "pair")
        src, dst = pair
        values = .2 * (h0[src, :1] + h0[dst, :1]) + .1 * (pos[src] - pos[dst]).norm(dim=-1, keepdim=True)
    elif case in ("atom_vector", "denoise"):
        group, kind = ("S", "denoise_eps_mse") if case == "denoise" else ("P", "regression")
        field = FieldSpec("synthetic", group, "fixture", "atom", kind=kind, representation="vector")
        direction = torch.nn.functional.normalize(pos[source] - pos[dest], dim=-1)
        coefficient = .2 + .1 * (h0[source, 0] + h0[dest, 0])
        values = pos.new_zeros(pos.shape).index_add(0, source, coefficient[:, None] * direction)
        if case == "denoise":
            values = values * .1
    else:
        representation = "vector" if case == "dipole_vector" else "magnitude"
        field = FieldSpec("synthetic", "P", "fixture", "graph", representation=representation)
        center = pos.new_zeros((molecules, 3)).index_add(0, batch, pos) / 3
        values = pos.new_zeros((molecules, 3)).index_add(0, batch, .1 * h0[:, :1] * (pos - center[batch]))
        if case == "dipole_magnitude":
            values = values.norm(dim=-1, keepdim=True)
    reg = LabelRegistry((field,), "synthetic-capacity-v1", "a" * 64)
    if field.representation == "vector":
        scale, center = float(values.square().mean().sqrt()), 0.
    else:
        scale, center = float(values.std(unbiased=False)), float(values.mean())
    stats = {"synthetic": TrainNormalization((center,), (max(scale, 1e-6),), "b" * 64, "synthetic-capacity-v1")}
    labels = {"synthetic": FieldTarget(values, torch.ones(len(values), dtype=torch.bool), pair if case == "pair" else None)}
    form = case.split("_")[1] if case.startswith("graph_") else "H1"
    heads = V3HeadBank(reg, dim=512, forms=form, hidden_dim=64)
    return heads, reg, stats, h0, pos, batch, {"synthetic": pair} if case == "pair" else {}, labels


def r_squared(prediction, target):
    import torch
    prediction, target = prediction.detach().double(), target.double()
    denominator = (target - target.mean(dim=0)).square().sum()
    if not bool(denominator > 0):
        raise ValueError("Synthetic capacity fixture unexpectedly has constant labels")
    return float(1 - (prediction - target).square().sum() / denominator)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wandb-dir", type=Path, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--molecules", type=int, default=1000)
    parser.add_argument("--steps", type=int, default=600)
    parser.add_argument("--lr", type=float, default=.01)
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()
    if socket.gethostname().split(".")[0] != "compute-0-20" or not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Use an owned compute-0-20 Slurm allocation")
    cases = args.cases.split(",")
    if not cases or len(cases) != len(set(cases)) or not set(cases) <= set(CASES):
        raise ValueError("Unknown or duplicate synthetic diagnostic case")
    if args.molecules != 1000 or args.steps <= 0 or args.steps > 1000 or args.threads < 1:
        raise ValueError("Require 1,000 synthetic molecules and a bounded declared step budget")
    if len(args.code_sha) != 40 or any(value not in "0123456789abcdef" for value in args.code_sha):
        raise ValueError("Record the actual code commit SHA")
    if args.output.exists():
        raise FileExistsError("Synthetic diagnostic output already exists")
    args.wandb_dir = args.wandb_dir.expanduser().resolve()
    args.wandb_dir.mkdir(parents=True, exist_ok=True)
    wandb_cache_dir = args.wandb_dir / "cache"
    wandb_data_dir = args.wandb_dir / "wandb_data"
    wandb_cache_dir.mkdir(parents=True, exist_ok=True)
    wandb_data_dir.mkdir(parents=True, exist_ok=True)
    # W&B reads these paths during import/init. Give every owned diagnostic
    # directory its own SDK core log/cache and staging area before either.
    os.environ["WANDB_CACHE_DIR"] = str(wandb_cache_dir)
    os.environ["WANDB_DATA_DIR"] = str(wandb_data_dir)
    import torch
    import wandb
    from phychem_mfm.phase1.v3_losses import compute_v3_loss
    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(1)
    # Bind actual package bytes, including imports reached indirectly through
    # package initializers; a declared code SHA alone is not source evidence.
    paths = [Path(__file__), *sorted((ROOT / "current/phychem_mfm").rglob("*.py"))]
    source = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    configuration = {"kind": "SYNTHETIC_HEAD_CAPACITY_ONLY", "code_sha": args.code_sha,
                     "source_sha256": source, "data_version": "synthetic-capacity-v1", "molecules": args.molecules,
                     "H0_dim": 512, "H0_origin": "fixed_synthetic_invariant_features_not_backbone",
                     "step_budget": args.steps, "learning_rate": args.lr, "warmup_steps": 25,
                     "optimizer": "AdamW", "betas": [.9, .95], "weight_decay": 0., "gradient_clip": 1.,
                     "acceptance_R2": .95, "seed_base": 20261025, "cases": cases, "device": "cpu",
                     "vector_loss_mode": "radial_huber_v1",
                     "source_scope": "all_current_phychem_mfm_python_plus_diagnostic_driver",
                     "wandb_cache_dir": str(wandb_cache_dir), "wandb_data_dir": str(wandb_data_dir),
                     "job_id": os.environ["SLURM_JOB_ID"], "node": socket.gethostname(),
                     "torch_version": str(torch.__version__), "python_version": sys.version.split()[0],
                     "threads": torch.get_num_threads(), "CUDA_used": False}
    configuration_sha = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
    results = []
    for case in cases:
        started = time.perf_counter()
        seed = 20261025 + CASES.index(case)
        heads, reg, stats, h0, pos, batch, pairs, labels = fixture(case, args.molecules, seed)
        optimizer = torch.optim.AdamW(heads.parameters(), lr=args.lr, betas=(.9, .95), weight_decay=0., foreach=False)
        tracker = wandb.init(project="model-v3-synthetic-diagnostics", mode="offline", dir=str(args.wandb_dir),
                             name=f"sa2_{case}_{configuration['job_id']}",
                             config={**configuration, "configuration_sha256": configuration_sha, "case": case, "seed": seed})
        result = {"case": case, "seed": seed, "status": "RUNNING", "wandb_run_id": str(tracker.id),
                  "parameters": sum(parameter.numel() for parameter in heads.parameters()),
                  "configuration_sha256": configuration_sha}
        try:
            groups = (reg.fields[0].group,)
            for step in range(1, args.steps + 1):
                optimizer.param_groups[0]["lr"] = args.lr * min(step / 25., 1.)
                optimizer.zero_grad(set_to_none=True)
                predictions = heads(h0, batch, pos, enabled_groups=groups, pair_indices=pairs)
                loss = compute_v3_loss(predictions, labels, reg, stats, enabled_groups=groups,
                                       vector_loss_mode=configuration["vector_loss_mode"])
                loss.total.backward()
                gradient = torch.nn.utils.clip_grad_norm_(heads.parameters(), 1.)
                if not bool(torch.isfinite(gradient)):
                    raise FloatingPointError("Nonfinite synthetic head gradient")
                optimizer.step()
                if step % 25 == 0 or step == args.steps:
                    with torch.no_grad():
                        evaluated = heads(h0, batch, pos, enabled_groups=groups, pair_indices=pairs)["synthetic"]
                        score = r_squared(evaluated, labels["synthetic"].values)
                    row = {"optimizer_updates": step, "base_samples_seen": step * args.molecules,
                           "train/loss": float(loss.total.detach()), "train/R2": score,
                           "valid_labels": loss.counts["synthetic"], "gradient_norm_before_clip": float(gradient)}
                    tracker.log(row, step=step, commit=True)
                    if score >= .95:
                        break
            result.update(status="PASS_SYNTHETIC_ONLY" if score >= .95 else "NOT_PASS_SYNTHETIC_ONLY",
                          R2=score, optimizer_updates=step, elapsed_seconds=time.perf_counter() - started)
            tracker.summary.update(result)
        except Exception as exc:
            result.update(status="FAILED_SYNTHETIC_DIAGNOSTIC", error_type=type(exc).__name__,
                          error=str(exc), elapsed_seconds=time.perf_counter() - started)
            tracker.summary.update(result)
        finally:
            tracker.finish(exit_code=0 if result["status"] == "PASS_SYNTHETIC_ONLY" else 1)
        current_source = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        if current_source != source:
            result.update(status="SOURCE_MUTATED_DURING_SYNTHETIC_DIAGNOSTIC")
        results.append(result)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # The caller supplies a fresh diagnostic output path. It is updated only
        # inside this one bounded run; previous run artifacts are never opened.
        args.output.write_text(json.dumps({"configuration": configuration, "results": results,
                                           "real_D3_acceptance": False}, indent=2) + "\n")
        print(json.dumps(result), flush=True)
    return 0 if all(row["status"] == "PASS_SYNTHETIC_ONLY" for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
