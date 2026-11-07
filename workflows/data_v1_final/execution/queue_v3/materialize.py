"""Materialize exact honest nonpilot analysis stages; never submit or run data work."""
import argparse
import copy
import json
import pathlib
import re
from ..queue_v1.shared import (ROOT, REPO, PROJECT, PY, load, need, on_login,
                               pin, read_small, write_new)
from ..queue_v1.queue_contract import CPU_NODES, validate_request, _pin
from .contract import validate_scope_spec

CONTROLLED = {"schema", "kind", "pilot", "cpus", "memory_gib", "wall_seconds",
              "estimated_peak_output_bytes", "execution_argv", "source_references",
              "data_references", "deferred_authority_references"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=pathlib.Path, required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--afterok", action="append", default=[])
    args = parser.parse_args(); on_login()
    need(args.node in CPU_NODES, "ACTUAL_CPU_PARTITION_NODE_REQUIRED")
    spec = load(args.spec); reviewed = validate_scope_spec(spec, read_small=read_small)
    name = args.job_name
    need(re.fullmatch(r"dv1_q_[A-Za-z0-9_]+", name), "NEW_QUEUED_JOB_NAME_REQUIRED")
    proof = ROOT / "control/queue_startup" / (name + ".json")
    reqpath = ROOT / "control/requests" / (name + ".json")
    script = ROOT / "control/scripts" / (name + ".sbatch")
    destinations = (script, reqpath, proof, proof.with_suffix(".ready.json"),
                    ROOT / "control/submissions" / (name + ".json"),
                    ROOT / "control/submissions" / (name + ".queue_intent.json"),
                    ROOT / "control/queue_started" / (name + ".json"),
                    ROOT / "control/queue_finished" / (name + ".json"))
    for path in destinations:
        need(not path.exists() and not path.is_symlink(), "NEW_DESTINATION_REQUIRED:" + str(path))
    authority = REPO / "configs/data_v1/queued_execution_decision_20261026_v1.json"
    refs = {}
    for ref in spec["source_references"]:
        _pin(ref, small=True)
        need(ref["path"] not in refs, "UNIQUE_STAGE_SOURCE_REFERENCES_REQUIRED")
        need(pin(ref["path"]) == ref, "EXACT_CURRENT_STAGE_SOURCE_PIN_REQUIRED")
        refs[ref["path"]] = ref
    v1 = REPO / "workflows/data_v1_final/execution/queue_v1"
    v3 = REPO / "workflows/data_v1_final/execution/queue_v3"
    need(pathlib.Path(__file__).absolute().parent == v3, "ROOT_INTEGRATED_EXECUTION_SOURCE_REQUIRED")
    extra = [args.spec, authority, *v1.glob("*.py"), *v3.glob("*.py"),
             REPO / "workflows/data_v1_final/execution/cpu_prefix_replay_v1/probe_memory.py"]
    extra += [pathlib.Path(spec["scope"]["review"]["path"])]
    extra += [pathlib.Path(ref["path"]) for ref in reviewed["parent_evidence_references"]]
    for path in extra:
        actual = pin(path)
        need(str(path) not in refs or refs[str(path)] == actual, "CONFLICTING_IMMUTABLE_SOURCE_PIN")
        refs[str(path)] = actual
    argv = [value.replace("__ROOT_STARTUP_PROOF__", str(proof)) for value in spec["execution_argv"]]
    wall = spec["wall_seconds"]
    text = f'''#!/bin/bash
#SBATCH --job-name={name}
#SBATCH --partition=cpu
#SBATCH --nodelist={args.node}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --exclusive=user
#SBATCH --time={wall//3600:02d}:{wall%3600//60:02d}:{wall%60:02d}
#SBATCH --output={ROOT}/control/{name}_%j.out
set -euo pipefail
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH={REPO}:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
cd {PROJECT}
exec {PY} -B -m workflows.data_v1_final.execution.queue_v1.launch --request {reqpath}
'''
    script.parent.mkdir(parents=True, exist_ok=True)
    with script.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
    request = {"schema": "DATA_V1_QUEUED_REQUEST_V1", "kind": "analysis", "partition": "cpu",
        "job_name": name, "node": args.node, "cpus": 16, "memory_gib": 64,
        "wall_seconds": wall, "estimated_peak_output_bytes": spec["estimated_peak_output_bytes"],
        "pilot": spec["pilot"], "estimated_total_core_hours": wall * 16 / 3600,
        "estimate_is_allocation_ceiling_not_runtime_forecast": True,
        "workdir": str(PROJECT), "exclusive_user": True,
        "startup_proof_path": str(proof), "startup_wait_seconds": 120,
        "queue_authority_reference": pin(authority), "script_reference": pin(script),
        "source_references": list(refs.values()), "data_references": spec.get("data_references", []),
        "deferred_authority_references": spec.get("deferred_authority_references", []),
        "execution_argv": argv, "dependencies": args.afterok,
        "root_review": {"status": "APPROVED", "reviewer": "root", "stage_spec_reference": pin(args.spec),
            "scope": "Exact separately reviewed analysis stage; no scientific acceptance or follow-on grant.",
            "resource_policy": "Strict16CPU64GiB/all-user-declared85/live-memory/quota; no exemptions."}}
    # Preserve every domain field, including explicit False flags; do not silently
    # drop source_status_stage/source_status_manifest/scope or future producer keys.
    for key, value in spec.items():
        if key in CONTROLLED:
            continue
        need(key not in request, "STAGE_SPEC_CANNOT_OVERRIDE_QUEUE_CONTROL:" + key)
        request[key] = copy.deepcopy(value)
    validate_request(request, read_small=read_small, script_text=text)
    write_new(reqpath, request)
    print(json.dumps({"status": "EXACT_ANALYSIS_QUEUED_REQUEST_PREPARED_NOT_SUBMITTED",
                      "request": pin(reqpath), "scope_mode": reviewed["mode"],
                      "pilot": spec["pilot"], "data_bodies_read_or_stat": False}))


if __name__ == "__main__":
    main()
