#!/usr/bin/env python3
"""Prepare a byte-bound panel request and reviewable single-GPU sbatch file.

This tool does not submit jobs. Source metadata, model weights and outputs are
external; no original record, role assignment or label is changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
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


H0_POLICY_RELATIVE = "current/phychem_mfm/phase1/v3_training_execution_policy.py"


def _preinit_json(reference):
    path = Path(reference["path"])
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 2 * 1024**2:
        raise ValueError("Ordinary bounded H0 preinitialization metadata required")
    raw = path.read_bytes()
    if (hashlib.sha256(raw).hexdigest() != reference["sha256"]
            or ("bytes" in reference and len(raw) != reference["bytes"])):
        raise ValueError("H0 preinitialization metadata bytes differ")
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("Duplicate preinitialization metadata key")
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError("Nonfinite preinitialization metadata")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def _shared_preinit_policy(root, expected=None):
    # One fixed, source-bound, stdlib-only SA1 leaf. Configuration cannot select
    # executable paths. Compile the same raw bytes that were hashed, not a pyc
    # or a file reopened by a general namespace/plugin loader.
    source = Path(root) / H0_POLICY_RELATIVE
    if source.is_symlink() or not source.is_file() or not 0 < source.stat().st_size <= 64 * 1024:
        raise ValueError("The shared bounded H0 metadata policy leaf is required")
    raw = source.read_bytes()
    ref = {"path": str(source.absolute()), "sha256": hashlib.sha256(raw).hexdigest()}
    if expected is not None and ref != expected:
        raise ValueError("The preinitialization policy source differs")
    namespace = {"__name__": "model_v3_fixed_H0_metadata_policy", "__file__": str(source)}
    exec(compile(raw, str(source), "exec"), namespace)
    return namespace["h0_runtime_controls_from_deterministic"], ref


def h0_preinit_declaration(configuration_ref, *, repository_root=ROOT, expected_policy=None):
    """Source configuration -> the canonical adapter's pre-CUDA declaration."""
    configuration = _preinit_json(configuration_ref)
    if type(configuration) is not dict or type(configuration.get("training_execution")) is not dict:
        raise ValueError("Explicit training execution required for H0 preinitialization")
    try:
        deterministic = configuration["proxy_contract"]["execution"]["deterministic"]
    except (KeyError, TypeError) as exc:
        raise ValueError("The source configuration must declare its actual deterministic policy") from exc
    policy, policy_ref = _shared_preinit_policy(repository_root, expected_policy)
    controls = policy(deterministic)  # The one shared policy validates bool/type.
    return {"configuration": dict(configuration_ref), "policy_source": policy_ref,
            "runtime_controls": controls}


def validate_h0_preinit_request(request_path, request_sha256, *, repository_root=ROOT,
                               apply_environment=True):
    """Bind/apply only opt-in environment policy before any model CUDA call.

    This is not GPU admission or a certificate. The original complete CP/H0 map
    is independently validated later. No Torch or phychem package is imported.
    """
    if type(apply_environment) is not bool:
        raise ValueError("Explicit metadata/environment mode required")
    request = _preinit_json({"path": str(request_path), "sha256": request_sha256})
    enabled = request.get("enable_training_execution", False)
    if type(enabled) is not bool:
        raise ValueError("Explicit boolean H0 execution opt-in required")
    if not enabled:
        if "h0_preinit" in request:
            raise ValueError("H0 preinitialization belongs only to the explicit new path")
        return None
    declaration = request.get("h0_preinit")
    if type(declaration) is not dict or set(declaration) != {"configuration", "policy_source", "runtime_controls"}:
        raise ValueError("The bound H0 preinitialization declaration is missing/incomplete")
    if declaration["configuration"] != request["model_configuration"]:
        raise ValueError("H0 preinitialization/source configuration differs")
    source_map = {row["path"]: row["sha256"] for row in request["source_files"]}
    for relative in (H0_POLICY_RELATIVE, "tools/model_v3/prepare_dev_evaluation.py",
                     "tools/model_v3/evaluate_dev_panel.py"):
        ref = binding(Path(repository_root) / relative)
        if source_map.get(relative) != ref["sha256"]:
            raise ValueError("Pre-CUDA H0 source inventory differs: " + relative)
    expected = h0_preinit_declaration(request["model_configuration"],
        repository_root=repository_root, expected_policy=declaration["policy_source"])
    if declaration != expected:
        raise ValueError("Declared pre-CUDA H0 controls differ from the shared policy")
    if not apply_environment:
        return declaration  # metadata planning only; never runtime admission
    torch_module = sys.modules.get("torch")
    if torch_module is not None and torch_module.cuda.is_initialized():
        raise ValueError("The H0 environment gate must precede CUDA initialization")
    desired = declaration["runtime_controls"]["cublas_workspace_config_for_cuda"]
    if desired is not None:
        inherited = os.environ.get("CUBLAS_WORKSPACE_CONFIG")
        if inherited is not None and inherited != desired:
            raise ValueError("Inherited CUBLAS policy contradicts the declared H0 map")
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = desired
    return declaration


def make_request(*, panel, training_store, model_configuration, checkpoint,
                 code_sha, preregistration_sha, data_version, pretraining_seed,
                 output_root, cache_root, run_id, source_files=None, state_key="auto",
                 maximum_wall_seconds=3600, wandb_project="phychem-model-v3",
                 reference_kind="primary", h0_packing=None, h0_packing_plan_sha256=None,
                 historical_reference=None, repository_root=ROOT,
                 enable_architecture_candidates=False, training_completion=None,
                 enable_training_execution=False):
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
    if type(enable_training_execution) is not bool:
        raise ValueError("Training-execution export opt-in must be boolean")
    if "training_execution" in configuration and not enable_training_execution:
        raise ValueError("New training execution requires explicit evaluation opt-in")
    if enable_training_execution and (reference_kind != "primary" or training_completion is None
            or type(configuration.get("training_execution")) is not dict):
        raise ValueError("Execution H0 requires its primary sample-checkpoint configuration and COMPLETE")
    if type(enable_architecture_candidates) is not bool:
        raise ValueError("Architecture-candidate opt-in must be boolean")
    if any(key in model["backbone"] for key in ("v3_architecture", "v3_legacy_memory")) and not enable_architecture_candidates:
        raise ValueError("C1 candidates require explicit evaluation opt-in")
    if reference_kind != "primary" and (enable_architecture_candidates or training_completion is not None):
        raise ValueError("New architecture/sample checkpoints belong to primary evaluations only")
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
        if "v3_legacy_memory" in model["backbone"]:
            source_files.append("workflows/sprime_s/scripts/s_model_memory_v1.py")
    if enable_training_execution:
        required_execution_sources = {
            "current/phychem_mfm/phase1/v3_execution_checkpoint_bridge.py",
            "current/phychem_mfm/phase1/v3_training_execution.py", H0_POLICY_RELATIVE,
            "current/phychem_mfm/phase1/v3_encoder_bridge.py",
            "tools/model_v3/evaluate_dev_panel.py", "tools/model_v3/prepare_dev_evaluation.py"}
        if not required_execution_sources <= set(source_files):
            raise ValueError("Execution H0 requires its actual adapter/bridge/evaluator source inventory")
    references = []
    for relative in sorted(set(source_files)):
        path = root / relative
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Executed-source inventory escapes the repository")
        references.append({"path": relative, "sha256": binding(path)["sha256"]})
    if not references:
        raise ValueError("Explicit source inventory required")
    request = {"schema": "model_v3_dev_evaluation_request_v1", "panel": binding(panel),
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
    if enable_architecture_candidates:
        request["enable_architecture_candidates"] = True
    if enable_training_execution:
        request["enable_training_execution"] = True
        request["h0_preinit"] = h0_preinit_declaration(request["model_configuration"], repository_root=root)
    if training_completion is not None:
        request["training_completion"] = binding(training_completion)
    return request


def sbatch_text(request_path, request_sha256, *, node, python_entry, gpu_uuid,
                log_path, repository_root=ROOT, h0_preinit=None):
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
    preinit_lines = []
    if h0_preinit is not None:
        expected = h0_preinit_declaration(h0_preinit["configuration"],
            repository_root=root, expected_policy=h0_preinit["policy_source"])
        if expected != h0_preinit:
            raise ValueError("Sbatch H0 controls differ from the one shared policy")
        desired = h0_preinit["runtime_controls"]["cublas_workspace_config_for_cuda"]
        if desired is not None:
            quoted = shlex.quote(desired)
            preinit_lines = [
                'if [[ -n "${CUBLAS_WORKSPACE_CONFIG+x}" && "$CUBLAS_WORKSPACE_CONFIG" != '+quoted+' ]]; then',
                '  echo "Inherited CUBLAS policy contradicts the bound H0 map" >&2; exit 1',
                'fi', "export CUBLAS_WORKSPACE_CONFIG="+quoted]
    return "\n".join([
        "#!/bin/bash", "#SBATCH --job-name=model_v3_dev_panel", "#SBATCH --partition=all",
        "#SBATCH --nodelist="+node, "#SBATCH --cpus-per-task=16", "#SBATCH --mem=64G",
        "#SBATCH --time=02:00:00", "#SBATCH --output="+log, "set -euo pipefail",
        "cd "+shlex.quote(str(root)), "export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=16 MKL_NUM_THREADS=16 OPENBLAS_NUM_THREADS=16",
        "export CUDA_VISIBLE_DEVICES="+shlex.quote(gpu_uuid),
        'scratch_dir=$(mktemp -d /tmp/mv3dev_"$SLURM_JOB_ID"_XXXXXX)',
        'chmod 0700 "$scratch_dir"', 'export TMPDIR="$scratch_dir" CUDA_CACHE_PATH="$scratch_dir/cuda_cache"',
        "export PYTHONPATH="+shlex.quote(str(root / "current")),
        *preinit_lines, "exec "+" ".join(shlex.quote(arg) for arg in argv), ""])


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
    parser.add_argument("--enable-training-execution", action="store_true",
                        help="Explicit opt-in to the bound training-execution FP32 H0 map")
    args = parser.parse_args()
    arguments = json.loads(args.template.read_text())
    if args.enable_training_execution:
        if "enable_training_execution" in arguments and arguments["enable_training_execution"] is not True:
            raise ValueError("CLI and template execution opt-ins differ")
        arguments["enable_training_execution"] = True
    request = make_request(**arguments)
    raw = json.dumps(request, indent=2, sort_keys=True, allow_nan=False)+"\n"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    script = sbatch_text(args.output, digest, node=args.node, python_entry=args.python_entry,
                         gpu_uuid=args.gpu_uuid, log_path=args.log_path,
                         h0_preinit=request.get("h0_preinit"))
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
