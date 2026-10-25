"""Stdlib-only CPU request preparation; no submission, retry, or science import."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex

ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025")
CANON=ROOT/"repository"
CPU=CANON/"workflows/data_v1_final/execution/cpu_analysis_v1"
PY="/share/home/zixiao/.conda/envs/chemprop/bin/python"
DEPS="/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"


def metadata_helper():
    path=Path(__file__).parent.parent/"pilot_closure_materializer_v1.py"
    spec=importlib.util.spec_from_file_location("_sb2_prior_stdlib_metadata_only",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--mode",choices=["fixtures","closure"],required=True)
    p.add_argument("--repository",type=Path,required=True);p.add_argument("--node",required=True)
    p.add_argument("--job-name",required=True);p.add_argument("--bundle-output",type=Path,required=True)
    p.add_argument("--pilot-receipt",type=Path);p.add_argument("--sacct-evidence",type=Path)
    p.add_argument("--application-output",type=Path);p.add_argument("--root-review",type=Path)
    a=p.parse_args()
    if os.name!="posix" or os.getuid()!=1278:raise ValueError("ROOT_OWN_DEFAULT_SERVER_METADATA_ONLY")
    if a.node not in {f"compute-0-{n}" for n in (2,*range(8,20))}:raise ValueError("REVIEWED_CPU_PARTITION_NODES_ONLY")
    repo=a.repository.absolute()
    if repo not in {CANON,ROOT/"worktrees/sb2"}:raise ValueError("OWN_CANONICAL_OR_SB2_SOURCES_ONLY")
    if not re.fullmatch(r"dv1_[A-Za-z0-9_]+",a.job_name):raise ValueError("DV1_JOB_NAME_REQUIRED")
    old=metadata_helper();bundle=old.require_new_bundle(a.bundle_output)
    for suffix in (".json",".intent.json",".verification.json"):
        if (ROOT/"control/submissions"/(a.job_name+suffix)).exists():raise ValueError("OWN_JOB_ALREADY_REGISTERED_NO_RETRY")
    cfg_path=CANON/"configs/data_v1/conformers/pilot_closure_v1.json"
    run_path=repo/"configs/data_v1/conformers/pilot_closure_cpu_v1.json"
    cfg=old.read_json(cfg_path);run=old.read_json(run_path);expected=run[a.mode]
    if old.reference(cfg_path)!=run["closure_config"]:raise ValueError("ORIGINAL_UNMODIFIED_CLOSURE_CONFIG_REQUIRED")
    policy_path=CANON/"configs/data_v1/cpu_analysis_small_scopes_v1.json"
    decision_path=CANON/"configs/data_v1/run_decisions_v4.json"
    central=old.read_json(policy_path);scope=central["scopes"][expected["scope_key"]]
    if scope["memory_gib"]!=expected["memory_gib"] or expected["wall_seconds"]>scope["wall_seconds"] or expected["cap_bytes"]>scope["output_cap_bytes"]:
        raise ValueError("NEW_ENTRY_DIFFERS_FROM_ACTUAL_CENTRAL_FINITE_SCOPE")
    files=[CPU/name for name in ("__init__.py","policy.py","runtime.py","probe_memory.py","launch.py","submit_cpu_pilot_v1.py")]
    directory=repo/"workflows/data_v1_final/conformers/pilot_closure_cpu_v1"
    source_paths=[*files,policy_path,decision_path,cfg_path,run_path,
        CANON/"workflows/data_v1_final/execution/submit_reviewed.py",
        directory/"runtime_adapter.py",directory/"close_pilot_cpu.py",directory/"test_cpu_entry.py",
        directory/"materialize.py",repo/"workflows/data_v1_final/conformers/common.py",
        repo/"workflows/data_v1_final/conformers/formal_v1/full_common.py",
        repo/"workflows/data_v1_final/conformers/pilot_closure_v1/test_closure.py",
        repo/"workflows/data_v1_final/conformers/pilot_closure_v1/close_pilot.py",
        repo/"workflows/data_v1_final/conformers/pilot_closure_materializer_v1.py"]
    refs=[old.reference(path) for path in source_paths]
    for ref in [scope["base_request_reference"],*scope.get("authority_references",[])]:
        old.require_reference(ref);refs.append(ref)
    base=old.read_json(scope["base_request_reference"]["path"])
    for ref in [base["script_reference"],*base["source_references"]]:
        old.require_reference(ref);refs.append(ref)
    intent=ROOT/"control/submissions"/(a.job_name+".intent.json")
    common_args=["--config",str(cfg_path),"--cpu-runconfig",str(run_path),"--root-preflight",str(intent)]
    if a.mode=="fixtures":
        if any((a.pilot_receipt,a.sacct_evidence,a.application_output)):raise ValueError("FIXTURE_MODE_HAS_NO_ACTUAL_DATA_ARGUMENTS")
        child=[PY,"-B",str(directory/"test_cpu_entry.py"),*common_args]
    else:
        if not all((a.pilot_receipt,a.sacct_evidence,a.application_output)):raise ValueError("MANUAL_FINAL336_C0_AND_FRESH_SACCT_INPUTS_REQUIRED")
        output=a.application_output.absolute()
        if output.exists() or Path(cfg["external_output_root"]) not in output.parents or ".." in output.parts:
            raise ValueError("NEW_CHILD_OF_ORIGINAL_CLOSURE_OUTPUT_ROOT_REQUIRED")
        refs+=old.closure_inputs(cfg,a.pilot_receipt,a.sacct_evidence)
        refs.append(old.reference(repo/"workflows/data_v1_final/conformers/run_pilot.py"))
        child=[PY,"-B",str(directory/"close_pilot_cpu.py"),*common_args,
            "--pilot-receipt",str(a.pilot_receipt.absolute()),"--sacct-evidence",str(a.sacct_evidence.absolute()),
            "--output",str(output)]
    root_review={"status":"ROOT_REVIEW_PENDING","reviewer":"root","mode":a.mode,
        "scope":"Only current bounded CPU analysis; materializer never submits or approves itself"}
    if a.root_review:
        root_review=old.read_json(a.root_review)
        if root_review.get("status")!="APPROVED" or root_review.get("reviewer")!="root" or root_review.get("mode")!=a.mode or root_review.get("job_name")!=a.job_name or root_review.get("repository")!=str(repo):
            raise ValueError("ACTUAL_ROOT_CPU_ANALYSIS_REVIEW_REQUIRED")
        refs.append(old.reference(a.root_review))
    wall=expected["wall_seconds"];h,remainder=divmod(wall,3600);m,s=divmod(remainder,60)
    launch=[PY,"-B","-m","workflows.data_v1_final.execution.cpu_analysis_v1.launch",
            "--intent",str(intent),"--",*child]
    script="\n".join(["#!/bin/bash","#SBATCH --job-name="+a.job_name,"#SBATCH --partition=cpu",
        "#SBATCH --nodelist="+a.node,"#SBATCH --nodes=1","#SBATCH --ntasks=1","#SBATCH --cpus-per-task=16",
        f"#SBATCH --mem={expected['memory_gib']}G",f"#SBATCH --time={h:02d}:{m:02d}:{s:02d}",
        "#SBATCH --output="+str(ROOT/"control"/(a.job_name+"_%j.out")),"set -euo pipefail",
        "export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''",
        "export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1",
        "export PYTHONPATH="+shlex.quote(str(CANON)+":"+DEPS),"cd "+shlex.quote(str(CANON)),
        "exec "+shlex.join(launch),""]).encode()
    if b"\r" in script:raise ValueError("LF_ONLY_SCRIPT_REQUIRED")
    bundle.mkdir(parents=True);script_path=bundle/(a.job_name+".sbatch");old.write_new(script_path,script)
    pins={ref["path"]:ref for ref in refs}
    request={"kind":"analysis","partition":"cpu","pilot":True,"resource_policy":"CPU_BOUNDED_TEST_LIVE_MEMORY_V1",
        "scope_key":expected["scope_key"],"scope_parameters":scope["parameters"],"node":a.node,
        "cpus":16,"memory_gib":expected["memory_gib"],"wall_seconds":wall,
        "estimated_peak_output_bytes":scope["output_cap_bytes"]+32*1024**2,
        "estimated_total_core_hours":16*wall/3600,"formal_generation_authorized":False,
        "decision_reference":old.reference(decision_path),"scope_policy_reference":old.reference(policy_path),
        "base_request_reference":scope["base_request_reference"],"root_review":root_review,
        "script_reference":old.reference(script_path),"source_references":[pins[key] for key in sorted(pins)]}
    old.write_json(bundle/"request.proposed.json",request)
    old.write_json(bundle/"materialization.json",{"schema":"SB2_CPU_CLOSURE_METADATA_ONLY_V1",
        "status":"MATERIALIZED_NOT_SUBMITTED","mode":a.mode,"request":old.reference(bundle/"request.proposed.json"),
        "central_runtime":old.reference(CPU/"runtime.py"),"old_closure_config":old.reference(cfg_path),
        "source_pins":request["source_references"],"source_delta":"Visible complete CPU entry; guard/checkpoint/bounded IO pool only; no AST runtime execution",
        "root_review_attached":bool(a.root_review),"automatic_submission":False,"automatic_retry":False,
        "scientific_calls":0,"big_data_pages_read":False,"new_once_keys_created":0})
    print(json.dumps({"status":"MATERIALIZED_NOT_SUBMITTED","request":str(bundle/"request.proposed.json")}))


if __name__=="__main__":main()
