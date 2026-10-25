#!/usr/bin/env python3
"""Prepare a byte-bound panel request and reviewable single-GPU sbatch file.

This tool does not submit jobs. Source metadata, model weights and outputs are
external; no original record, role assignment or label is changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import sys

ROOT = Path(__file__).absolute().parents[2]


def binding(path):
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file():
        raise ValueError("An ordinary, existing source file is required")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""):
            digest.update(block)
    return {"path": str(path), "sha256": digest.hexdigest()}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def make_request(*, panel, training_store, model_configuration, checkpoint,
                 code_sha, preregistration_sha, data_version, pretraining_seed,
                 output_root, cache_root, run_id, source_files=None, state_key="auto",
                 maximum_wall_seconds=3600, wandb_project="phychem-model-v3",
                 reference_kind="primary", h0_packing=None, h0_packing_plan_sha256=None,
                 historical_reference=None, repository_root=ROOT):
    sys.path.insert(0, str(ROOT / "current"))
    from phychem_mfm.phase1.v3_h0_packing import packing_budget, budget_arguments, canonical
    from phychem_mfm.phase1.v3_encoder_bridge import source_model_configuration
    root = Path(repository_root).absolute()
    packing = packing_budget() if h0_packing is None else (
        packing_budget(**budget_arguments(h0_packing)) if "schema" in h0_packing else packing_budget(**h0_packing))
    plans = {} if h0_packing_plan_sha256 is None else dict(h0_packing_plan_sha256)
    if any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in plans.values()):
        raise ValueError("Pinned per-dataset H0 packing plan SHA values are required")
    for value in (code_sha, preregistration_sha):
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            raise ValueError("Full actual code and preregistration commits are required")
    if type(pretraining_seed) is not int or pretraining_seed < 0:
        raise ValueError("The actual checkpoint's pretraining seed is required")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", run_id) or not re.fullmatch(r"[A-Za-z0-9_./:+-]{1,128}", data_version):
        raise ValueError("Bounded run/data identities required")
    if not 60 <= maximum_wall_seconds <= 7200:
        raise ValueError("Evaluation runtime must be bounded at 60-7200 seconds")
    for path in (output_root, cache_root):
        if Path(path).resolve().is_relative_to(root.resolve()):
            raise ValueError("Weights, H0 and evaluation products must stay outside the source tree")
    configuration = json.loads(Path(model_configuration).read_text())
    if "seed" in configuration and configuration["seed"] != pretraining_seed:
        raise ValueError("Declared checkpoint seed differs from its source configuration")
    model = source_model_configuration(configuration)
    if state_key not in {"auto", "model", "model_state"}:
        raise ValueError("Choose a recognized checkpoint schema instead of a permissive arbitrary state key")
    historical = None
    if reference_kind == "historical_sanity_only":
        historical = binding(historical_reference or root / "configs/model_v3/historical_B3_H0_reference_v1.json")
    elif reference_kind != "primary" or historical_reference is not None:
        raise ValueError("Historical metadata belongs only to the explicitly descriptive B3 scope")
    if source_files is None:
        source_files = [path.relative_to(root).as_posix()
                        for path in (root / "current/phychem_mfm").rglob("*.py")]
        source_files += ["tools/model_v3/"+name for name in (
            "evaluate_dev_panel.py", "prepare_dev_evaluation.py", "summarize_experiments.py")]
        if historical is not None:
            source_files.append("workflows/sprime_s/scripts/s_model_memory_v1.py")
    references = []
    for relative in sorted(set(source_files)):
        path = root / relative
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Executed-source inventory escapes the repository")
        references.append({"path": relative, "sha256": binding(path)["sha256"]})
    if not references:
        raise ValueError("Explicit source inventory required")
    return {"schema": "model_v3_dev_evaluation_request_v1", "panel": binding(panel),
        "training_store": binding(training_store), "model_configuration": binding(model_configuration),
        "checkpoint": {**binding(checkpoint), "state_key": state_key},
        "architecture_sha256": hashlib.sha256(encoded(model)).hexdigest(),
        "code_sha": code_sha, "preregistration_sha": preregistration_sha,
        "data_version": data_version, "pretraining_seed": pretraining_seed,
        "output_root": str(Path(output_root).absolute()), "cache_root": str(Path(cache_root).absolute()),
        "run_id": run_id, "source_files": references, "device": "cuda:0",
        "h0_packing": packing, "h0_packing_budget_sha256": canonical(packing),
        "h0_packing_plan_sha256": plans,
        "historical_reference": historical,
        "packing_binding_status": "BOUND" if plans else "METADATA_PLANNING_REQUIRED",
        "maximum_wall_seconds": maximum_wall_seconds, "wandb_project": wandb_project,
        "reference_kind": reference_kind}


def sbatch_text(request_path, request_sha256, *, node, python_entry, gpu_uuid,
                log_path, repository_root=ROOT):
    if not re.fullmatch(r"compute-0-(?:[0-7]|20|21|22)", node):
        raise ValueError("Use the established development cluster's explicitly allowed GPU nodes")
    if not re.fullmatch(r"GPU-[0-9a-fA-F-]{16,64}", gpu_uuid):
        raise ValueError("One measured full GPU UUID is required")
    if not Path(python_entry).is_absolute() or not re.fullmatch(r"[0-9a-f]{64}", request_sha256):
        raise ValueError("Verified logical absolute interpreter and request SHA required")
    log = str(Path(log_path).absolute())
    if any(c in log for c in ("\n", "\r", " ", "\t")):
        raise ValueError("An unambiguous absolute Slurm log path is required")
    root = Path(repository_root).absolute()
    argv = [python_entry, "-B", str(root / "tools/model_v3/evaluate_dev_panel.py"),
            "--request", str(Path(request_path).absolute()), "--request-sha256", request_sha256]
    return "\n".join([
        "#!/bin/bash", "#SBATCH --job-name=model_v3_dev_panel", "#SBATCH --partition=all",
        "#SBATCH --nodelist="+node, "#SBATCH --cpus-per-task=16", "#SBATCH --mem=64G",
        "#SBATCH --time=02:00:00", "#SBATCH --output="+log, "set -euo pipefail",
        "cd "+shlex.quote(str(root)), "export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=16 MKL_NUM_THREADS=16 OPENBLAS_NUM_THREADS=16",
        "export CUDA_VISIBLE_DEVICES="+shlex.quote(gpu_uuid),
        'scratch_dir=$(mktemp -d /tmp/mv3dev_"$SLURM_JOB_ID"_XXXXXX)',
        'chmod 0700 "$scratch_dir"', 'export TMPDIR="$scratch_dir" CUDA_CACHE_PATH="$scratch_dir/cuda_cache"',
        "export PYTHONPATH="+shlex.quote(str(root / "current")),
        "exec "+" ".join(shlex.quote(arg) for arg in argv), ""])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True,
                        help="JSON arguments for make_request; all source files must already exist")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sbatch-output", type=Path, required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--python-entry", required=True)
    parser.add_argument("--gpu-uuid", required=True)
    parser.add_argument("--log-path", required=True)
    args = parser.parse_args()
    request = make_request(**json.loads(args.template.read_text()))
    raw = json.dumps(request, indent=2, sort_keys=True, allow_nan=False)+"\n"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    script = sbatch_text(args.output, digest, node=args.node, python_entry=args.python_entry,
                         gpu_uuid=args.gpu_uuid, log_path=args.log_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.sbatch_output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(raw)
    with args.sbatch_output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(script)
    print(json.dumps({"status": "PREPARED_NOT_SUBMITTED", "request_sha256": digest,
                      "request": str(args.output), "sbatch": str(args.sbatch_output),
                      "packing_plans_bound": bool(request["h0_packing_plan_sha256"])}))


if __name__ == "__main__":
    main()
