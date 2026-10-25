"""Measure the preserved failing S-gradient check without changing its source.

Compare repeated autograd of the identical source Tensor, a separately rebuilt
source loss, and the bridge loss on the SAME encoder output graph. Repeat under
8 and 1 intra-op threads. This is a diagnostic, not an acceptance relaxation.
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
sys.path[:0] = [str(ROOT / "current"), str(ROOT / "current/tests")]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tensor_sha(value):
    return hashlib.sha256(value.detach().cpu().contiguous().numpy().tobytes()).hexdigest()


def compare(reference, candidate, torch):
    if reference is None or candidate is None:
        return {"bitwise_equal": reference is None and candidate is None,
                "reference_none": reference is None, "candidate_none": candidate is None}
    ref, other = reference.detach().cpu().double(), candidate.detach().cpu().double()
    finite = torch.isfinite(ref) & torch.isfinite(other)
    delta = other - ref
    result = {"shape": list(ref.shape), "dtype": str(reference.dtype),
              "bitwise_equal": bool(torch.equal(reference, candidate)),
              "reference_sha256": tensor_sha(reference), "candidate_sha256": tensor_sha(candidate),
              "reference_nonfinite": int((~torch.isfinite(ref)).sum()),
              "candidate_nonfinite": int((~torch.isfinite(other)).sum()),
              "different_elements": int((ref != other).sum())}
    if not bool(finite.all()):
        result.update(max_abs=None, relative_l2=None, finite=False)
        return result
    norm = float(torch.linalg.vector_norm(ref))
    result.update(finite=True, reference_l2=norm,
                  candidate_l2=float(torch.linalg.vector_norm(other)),
                  max_abs=float(delta.abs().max()) if delta.numel() else 0.,
                  relative_l2=float(torch.linalg.vector_norm(delta)) / max(norm, 1e-12),
                  max_entry_relative=float((delta.abs() / ref.abs().clamp_min(1e-12)).max()) if delta.numel() else 0.)
    if delta.numel() and not result["bitwise_equal"]:
        flat = delta.abs().reshape(-1)
        take = min(5, int((flat > 0).sum()))
        indices = flat.topk(take).indices.tolist()
        result["largest_differences"] = [{"flat_index": i, "reference": float(ref.reshape(-1)[i]),
                                           "candidate": float(other.reshape(-1)[i]),
                                           "absolute": float(flat[i])} for i in indices]
        if ref.ndim == 2:
            rows = torch.where((delta != 0).any(dim=1))[0]
            result["different_rows"] = rows.tolist()
    return result


def imported_sources():
    paths = {Path(__file__), ROOT / "current/tests/test_model_v3_structural.py"}
    for name, module in tuple(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if name.startswith("phychem_mfm") and path:
            value = Path(path).absolute()
            if value.suffix == ".py" and value.is_relative_to(ROOT):
                paths.add(value)
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(paths)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.output.exists() or not 1 <= args.repeats <= 10:
        raise ValueError("Use a fresh output and bounded repeat count")
    if socket.gethostname().split(".")[0] != "compute-0-20" or not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Use the owned compute-0-20 diagnostic allocation")
    if len(args.code_sha) != 40 or any(c not in "0123456789abcdef" for c in args.code_sha):
        raise ValueError("Actual code commit required")
    import torch
    from test_model_v3_structural import setup_model, legacy_loss
    from phychem_mfm.phase1.v3_structural import build_structural_views
    from phychem_mfm.training.losses import LossWeights
    started = time.perf_counter()
    results = []
    source_before = None
    for threads in (8, 1):
        torch.set_num_threads(threads)
        model, base, registry, binding, norms, targets = setup_model()
        views = build_structural_views(base, ordinals=(10, 11))
        output = model.forward_pretrain(views, enabled_groups=("S",))
        original = legacy_loss(output.source_outputs, views.batch)
        duplicate = legacy_loss(output.source_outputs, views.batch)
        bridge = model.compute_loss(output, views, {}, norms, enabled_groups=("S",), weights=LossWeights())
        if source_before is None:
            source_before = imported_sources()
        parameters = (model.encoder.element_head.weight, model.encoder.bond_head.order.weight,
                      model.encoder.geometry_head.pair_mlp[-1].weight, model.encoder.backbone.atom_emb.weight)
        identities = {id(value): name for name, value in model.encoder.named_parameters()}
        names = ["encoder." + identities[id(value)] for value in parameters]
        summary = {"threads": torch.get_num_threads(), "interop_threads": torch.get_num_interop_threads(),
                   "source_repeat_mismatches": 0, "duplicate_source_mismatches": 0,
                   "bridge_mismatches": 0, "raw_loss_and_count_equal": True, "comparisons": []}
        for field, raw_name in (("s_element", "element"), ("s_noise", "denoise_eps_mse"), ("s_bond", "bond_order")):
            raw_equal = bool(torch.equal(original.raw[raw_name], bridge.fields[field]))
            count_equal = original.counts[raw_name] == bridge.counts[field]
            summary["raw_loss_and_count_equal"] &= raw_equal and count_equal
            gradients_ref = torch.autograd.grad(original.raw[raw_name], parameters, retain_graph=True, allow_unused=True)
            gradients_ref = tuple(None if value is None else value.detach().clone() for value in gradients_ref)
            for repetition in range(args.repeats):
                for condition, tensor in (("source_repeat", original.raw[raw_name]),
                                          ("duplicate_source", duplicate.raw[raw_name]),
                                          ("bridge", bridge.fields[field])):
                    before_rng = tensor_sha(torch.get_rng_state())
                    gradients = torch.autograd.grad(tensor, parameters, retain_graph=True, allow_unused=True)
                    after_rng = tensor_sha(torch.get_rng_state())
                    for name, reference, candidate in zip(names, gradients_ref, gradients):
                        measured = compare(reference, candidate, torch)
                        summary[condition + "_mismatches"] += int(not measured["bitwise_equal"])
                        summary["comparisons"].append({"field": field, "source_raw": raw_name,
                            "parameter": name, "condition": condition, "repetition": repetition,
                            "raw_equal": raw_equal, "count_equal": count_equal,
                            "raw_loss": float(original.raw[raw_name].detach()), "valid_count": int(original.counts[raw_name]),
                            "ambient_rng_unchanged": before_rng == after_rng, **measured})
            if any(value.grad is not None for value in parameters):
                raise RuntimeError("Diagnostic autograd.grad unexpectedly changed leaf parameter.grad")
        results.append(summary)
        print(json.dumps({key: value for key, value in summary.items() if key != "comparisons"}), flush=True)
        del bridge, duplicate, original, output, model
    source_after = imported_sources()
    payload = {"status": "DIAGNOSTIC_COMPLETE", "code_sha": args.code_sha,
               "job_id": os.environ["SLURM_JOB_ID"], "node": socket.gethostname(),
               "torch_version": str(torch.__version__), "cuda_initialized": torch.cuda.is_initialized(),
               "optimizer_updates": 0, "elapsed_seconds": time.perf_counter() - started,
               "source_before": source_before, "source_after": source_after,
               "source_unchanged": source_before == source_after, "results": results,
               "acceptance_rule_changed": False, "original_test_modified": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return 0 if payload["source_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
