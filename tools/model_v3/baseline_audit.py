"""Measure baseline model sizes on a compute node without reading real labels."""
from __future__ import annotations

import argparse
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).absolute().parents[2]
sys.path.insert(0, str(ROOT / "current"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    if socket.gethostname().split(".")[0] != "compute-0-20":
        raise RuntimeError("Baseline audit must run on compute-0-20")
    import torch
    from torch_geometric.data import Batch, Data
    from phychem_mfm.factory import build_model

    torch.set_num_threads(16)
    a4 = json.loads((ROOT / "workflows/s_denoise/configs/A4_seed0_v3.json").read_text())["model"]
    previous = json.loads((ROOT / "workflows/sprime_s/formal_s/B1_seed0_v2.json").read_text())["model"]
    candidate = copy.deepcopy(a4)
    candidate["backbone"].update(dim=512, layers=6, heads=8)
    candidate["expert"]["heads"] = 8
    residual = copy.deepcopy(candidate)
    residual["head"] = copy.deepcopy(previous["head"])
    configurations = {"historical_S_384x4": previous, "baseline_512x6_residual": residual,
                      "baseline_512x6_A4": candidate}
    batch = Batch.from_data_list([
        Data(x=torch.tensor([[5], [0], [0]], dtype=torch.long),
             pos=torch.tensor([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]])),
        Data(x=torch.tensor([[7], [0]], dtype=torch.long),
             pos=torch.tensor([[0., 0., 0.], [0., 0., 1.]])),
    ])
    models = {}
    for name, config in configurations.items():
        torch.manual_seed(0)
        model = build_model(config).eval()
        counts = {key: sum(p.numel() for p in module.parameters()) for key, module in model.named_children()}
        detail = {key: {sub: sum(p.numel() for p in module.parameters())
                        for sub, module in group.named_children()}
                  for key, group in model.named_children() if key.endswith("descriptor_heads")}
        total = sum(p.numel() for p in model.parameters())
        if sum(counts.values()) != total:
            raise RuntimeError("Child parameter accounting does not match total")
        with torch.no_grad():
            atom, graph = model.encode_atoms(batch), model.encode_graph(batch)
        models[name] = {"configuration": config, "total_parameters": total,
                        "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
                        "parameters_by_module": counts, "descriptor_heads": detail,
                        "atom_H0_shape": list(atom.shape), "graph_H0_shape": list(graph.shape),
                        "encode_atoms_signature": str(inspect.signature(model.encode_atoms)),
                        "encode_graph_signature": str(inspect.signature(model.encode_graph))}
        del model
    sources = ["current/phychem_mfm/factory.py", "current/phychem_mfm/model/shared.py",
               "current/phychem_mfm/model/backbone.py", "current/phychem_mfm/model/attention.py",
               "current/phychem_mfm/model/heads.py", "current/phychem_mfm/model/routes.py",
               "current/phychem_mfm/phase1/objectives.py", "current/phychem_mfm/training/geometry.py",
               "current/phychem_mfm/training/degrade_molecules.py",
               "current/phychem_mfm/phase1/full_corpus_loader.py",
               "current/phychem_mfm/phase1/downstream_training.py",
               "current/phychem_mfm/phase1/downstream_readout.py",
               "workflows/sprime_s/scripts/s_convergence_runner_v8.py",
               "workflows/sprime_s/scripts/s_training_components_v1.py",
               "workflows/sprime_s/scripts/s_training_components_v2.py",
               "workflows/sprime_s/scripts/s_model_memory_v1.py",
               "workflows/phase1_downstream/stage60_downstream_binding_v3/downstream_binding_data.py",
               "workflows/phase1_downstream/stage60_full_downstream_runner_v1/run_formal_readout.py"]
    payload = {"schema": "model_v3_baseline_audit_v1", "node": socket.gethostname(),
               "job_id": os.environ.get("SLURM_JOB_ID"), "torch_version": str(torch.__version__),
               "code_commit": args.code_commit,
               "models": models,
               "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources},
               "real_data_read": False, "cuda_used": False, "status": "PASS"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({name: info["total_parameters"] for name, info in models.items()}))


if __name__ == "__main__":
    main()
