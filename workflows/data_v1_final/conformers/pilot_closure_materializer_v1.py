"""Stdlib-only Root metadata materializer. Never submits, retries, or runs science."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import socket
import time

ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025")
PROJECT=ROOT.parent.parent
PYTHON="/share/home/zixiao/.conda/envs/chemprop/bin/python"
DEPS="/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
MAX_METADATA_BYTES=2*1024*1024
CONTROLLER_SHA="6d1e3f5623bcdf04351d50710ccc81b5ca50f23d3b19051cba29f6fee173ee7f"
COMMON_SHA="ffa4fc9b6ce97be5b62af926c35337168b687f1f80a0fdd3564957dfe169b83b"
FORMAL_V2_FILES=[
 "workflows/data_v1_final/conformers/formal_v2/README.md",
 "workflows/data_v1_final/conformers/formal_v2/finalize_common_v2.py",
 "workflows/data_v1_final/conformers/formal_v2/identity_v2.py",
 "workflows/data_v1_final/conformers/formal_v2/probe_source_schema_v2.py",
 "workflows/data_v1_final/conformers/formal_v2/test_identity_v2.py"]
CLOSURE_FILES=[
 "configs/data_v1/conformers/pilot_closure_v1.json",
 "workflows/data_v1_final/conformers/pilot_closure_v1/README.md",
 "workflows/data_v1_final/conformers/pilot_closure_v1/close_pilot.py",
 "workflows/data_v1_final/conformers/pilot_closure_v1/test_closure.py"]


def reference(path):
    path=Path(path).absolute()
    if path.stat().st_size>MAX_METADATA_BYTES:raise ValueError("METADATA_ONLY_2MIB_FILE_LIMIT:"+str(path))
    raw=path.read_bytes()
    if len(raw)>MAX_METADATA_BYTES:raise ValueError("METADATA_GREW_BEYOND_2MIB")
    return {"path":str(path),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}


def require_reference(ref):
    if reference(ref["path"])!=ref:raise ValueError("PIN_CHANGED:"+ref["path"])
    return Path(ref["path"])


def read_json(path):
    reference(path)
    return json.loads(Path(path).read_text())


def write_new(path,raw):
    with Path(path).open("xb") as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())


def write_json(path,value):
    write_new(path,(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+"\n").encode())


def require_new_bundle(path):
    path=Path(path).absolute()
    if not path.is_absolute() or ".." in path.parts or ROOT/"control" not in path.parents or path.exists() or any(p.is_symlink() for p in path.parents):
        raise ValueError("NEW_NONSYMLINK_ROOT_CONTROL_BUNDLE_REQUIRED")
    return path


def closure_inputs(config,pilot_receipt,sacct_evidence):
    """Only small closed authority/actual query files; never opens data packages."""
    receipt=read_json(pilot_receipt)
    if receipt.get("status")!="PILOT_COMPLETED_REQUIRES_ROOT_REVIEW" or receipt.get("failure") is not None or receipt.get("resource_denial") is not None:
        raise ValueError("FINAL_336_RECEIPT_REQUIRED_BEFORE_ACTUAL_REQUEST")
    if any(receipt.get(k)!=336 for k in ("expected_molecules","submitted_molecules","completed_molecules")) or receipt.get("never_dispatched_molecules")!=0:
        raise ValueError("ACTUAL336_COMPLETE_REQUIRED")
    if str(receipt["runtime"]["job_id"])!=config["expected_job_id"] or receipt["config"]!=config["pilot_config"] or receipt["prepared"]!=config["prepared"]:
        raise ValueError("ORIGINAL_JOB_CONFIG_AND_PREPARED_REQUIRED")
    if receipt.get("parquet_readback",{}).get("status")!="ALL_PILOT_GEOMETRIES_FLOAT64_SHA_READBACK_PASSED":
        raise ValueError("FINAL_PRODUCER_READBACK_PASS_REQUIRED")
    evidence=read_json(sacct_evidence)
    if evidence.get("schema")!="DATA_V1_SACCT_QUERY_EVIDENCE_V1" or evidence.get("query_returncode")!=0:
        raise ValueError("ROOT_SUCCESSFUL_NEW_ACTUAL_SACCT_EVIDENCE_REQUIRED")
    argv=evidence.get("command_argv")
    if not isinstance(argv,list) or not argv or Path(argv[0]).name!="sacct":
        raise ValueError("ACTUAL_SACCT_ARGV_REQUIRED")
    observed=datetime.fromisoformat(evidence["observed_at"])
    if observed.tzinfo is None or not 0<=time.time()-observed.timestamp()<=3600:
        raise ValueError("ROOT_NEW_SACCT_QUERY_WITHIN_ONE_HOUR_REQUIRED")
    raw_ref=evidence["raw_sacct_reference"];raw=require_reference(raw_ref).read_text()
    reader=csv.DictReader(io.StringIO(raw),delimiter="|")
    if not reader.fieldnames or not {"State","ExitCode","ElapsedRaw","AllocCPUS"}<=set(reader.fieldnames):
        raise ValueError("ACTUAL_SACCT_PIPE_HEADER_REQUIRED")
    jid_column="JobIDRaw" if "JobIDRaw" in reader.fieldnames else "JobID"
    parents={}
    for row in reader:
        jid=row.get(jid_column,"")
        if not jid.isdecimal():continue
        state=row["State"].split()[0]
        if jid in parents or state not in {"COMPLETED","FAILED","TIMEOUT","CANCELLED","OUT_OF_MEMORY","NODE_FAIL"}:
            raise ValueError("ALL_REQUESTED_ACTUAL_PARENTS_MUST_BE_UNIQUE_TERMINAL")
        if int(row["ElapsedRaw"])<0 or int(row["AllocCPUS"])<0:raise ValueError("INVALID_ACTUAL_PARENT_COST")
        parents[jid]=row
    requested=list(map(str,evidence["requested_parent_job_ids"]))
    if len(set(requested))!=len(requested) or set(requested)!=set(parents):
        raise ValueError("REQUESTED_PARENT_SET_MUST_MATCH_ACTUAL_RAW_ROWS")
    pilot=parents.get(config["expected_job_id"])
    if pilot is None or pilot["State"].split()[0]!="COMPLETED" or pilot["ExitCode"]!="0:0":
        raise ValueError("ACTUAL_PILOT_PARENT_C0_REQUIRED_BEFORE_REQUEST")
    manifests=[ref for ref in receipt["outputs"] if Path(ref["path"]).name=="reproduction_manifest.json"]
    if len(manifests)!=1:raise ValueError("PRODUCER_ORIGINAL_MANIFEST_REFERENCE_REQUIRED")
    require_reference(manifests[0])
    # Hash small authority files only. Large parquet/packages/tasks are deliberately
    # deferred to the separate node20 analysis job, using these closed references.
    for ref in (config["pilot_config"],config["prepared"]):require_reference(ref)
    return [reference(pilot_receipt),reference(sacct_evidence),raw_ref,manifests[0],
            config["pilot_config"],config["prepared"]]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode",choices=["fixtures","closure"],required=True)
    p.add_argument("--repository",type=Path,required=True);p.add_argument("--job-name",required=True)
    p.add_argument("--bundle-output",type=Path,required=True)
    p.add_argument("--pilot-receipt",type=Path);p.add_argument("--sacct-evidence",type=Path)
    p.add_argument("--application-output",type=Path)
    p.add_argument("--root-review",type=Path,help="Optional actual Root approval of this scope; otherwise output request remains pending and cannot submit")
    a=p.parse_args()
    if os.name!="posix" or os.getuid()!=1278 or socket.gethostname().split(".")[0] not in {"sonmi","compute-0-20"}:
        raise ValueError("ROOT_OWN_METADATA_ON_DEFAULT_SERVER_ONLY")
    repo=a.repository.absolute()
    if repo not in {ROOT/"repository",ROOT/"worktrees"/"sb2"}:raise ValueError("OWN_CANONICAL_OR_SB2_WORKTREE_REQUIRED")
    if not re.fullmatch(r"dv1_[A-Za-z0-9_]+",a.job_name):raise ValueError("REVIEWABLE_DV1_JOB_NAME_REQUIRED")
    bundle=require_new_bundle(a.bundle_output)
    for suffix in (".json",".intent.json",".verification.json"):
        if (ROOT/"control"/"submissions"/(a.job_name+suffix)).exists():
            raise ValueError("EXISTING_JOB_REGISTRATION_NO_MATERIALIZER_RETRY")
    confdir=repo/"workflows/data_v1_final/conformers"
    config_path=repo/"configs/data_v1/conformers/pilot_closure_v1.json";config=read_json(config_path)
    if config["schema"]!="DATA_V1_SPRIME_PILOT_CLOSURE_CONFIG_V1" or config["expected_molecules"]!=336:
        raise ValueError("ORIGINAL_CLOSURE_CONFIG_REQUIRED")
    # The shared Root controller lives in the canonical repository, even when
    # testing the isolated SB2 worktree before its own sources are merged.
    controller=reference(ROOT/"repository/workflows/data_v1_final/execution/submit_reviewed.py")
    common=reference(confdir/"common.py")
    if controller["sha256"]!=CONTROLLER_SHA or common["sha256"]!=COMMON_SHA:
        raise ValueError("REGISTERED_CONTROLLER_OR_COMMON_CHANGED")
    sources=[controller,common,reference(confdir/"formal_v1/full_common.py"),
             reference(confdir/"pilot_closure_v1/close_pilot.py"),
             reference(confdir/"pilot_closure_v1/test_closure.py"),
             reference(config_path),reference(Path(__file__))]
    if a.mode=="fixtures":
        if any((a.pilot_receipt,a.sacct_evidence,a.application_output)):
            raise ValueError("FIXTURES_HAVE_NO_REAL_DATA_ARGUMENTS")
        memory,wall,peak=8,600,64*1024**2
        command=[PYTHON,"-B",str(confdir/"pilot_closure_v1/test_closure.py"),"-v"]
        scope="Only six pure pilot_closure interface fixtures; no scientific runtime or input data reads"
    else:
        if not all((a.pilot_receipt,a.sacct_evidence,a.application_output)):
            raise ValueError("MANUAL_FINAL_RECEIPT_FRESH_ACTUAL_SACCT_AND_OUTPUT_REQUIRED")
        app=a.application_output.absolute();allowed=Path(config["external_output_root"])
        if app.exists() or allowed not in app.parents or ".." in app.parts:
            raise ValueError("NEW_OWN_CLOSURE_APPLICATION_OUTPUT_REQUIRED")
        sources+=closure_inputs(config,a.pilot_receipt,a.sacct_evidence)
        sources.append(reference(confdir/"run_pilot.py"))
        memory,wall,peak=32,3600,config["max_output_bytes"]+(64*1024**2)
        intent=ROOT/"control/submissions"/(a.job_name+".intent.json")
        command=[PYTHON,"-B",str(confdir/"pilot_closure_v1/close_pilot.py"),"--config",str(config_path),
                 "--pilot-receipt",str(a.pilot_receipt.absolute()),"--sacct-evidence",str(a.sacct_evidence.absolute()),
                 "--root-preflight",str(intent),"--output",str(app)]
        scope="Read-only terminal336 pilot closure and actual parent accounting; no UFF/QM/LMDB/Root planning approval"
    root_review={"status":"ROOT_REVIEW_PENDING","reviewer":"root","scope":scope,
                 "note":"Materialization is not submission approval; Root must review a separate explicit approval"}
    if a.root_review:
        review=read_json(a.root_review)
        if review.get("schema")!="DATA_V1_SB2_CLOSURE_REQUEST_ROOT_REVIEW_V1" or review.get("status")!="APPROVED" or review.get("reviewer")!="root" or review.get("mode")!=a.mode or review.get("job_name")!=a.job_name or review.get("repository")!=str(repo):
            raise ValueError("ACTUAL_ROOT_REQUEST_REVIEW_BOUND_TO_MODE_NAME_REPOSITORY_REQUIRED")
        root_review=review;sources.append(reference(a.root_review))
    script="\n".join(["#!/bin/bash",
        "#SBATCH --job-name="+a.job_name,"#SBATCH --partition=all","#SBATCH --nodelist=compute-0-20",
        "#SBATCH --nodes=1","#SBATCH --ntasks=1","#SBATCH --cpus-per-task=16",
        f"#SBATCH --mem={memory}G","#SBATCH --time="+("00:10:00" if a.mode=="fixtures" else "01:00:00"),
        "#SBATCH --output="+str(ROOT/"control"/(a.job_name+"_%j.out")),
        "set -euo pipefail","export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''",
        "export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1",
        "export PYTHONPATH="+shlex.quote(DEPS),"cd "+shlex.quote(str(repo)),
        "exec "+shlex.join(command),""]).encode()
    if b"\r" in script:raise ValueError("SCRIPT_MUST_HAVE_ONLY_LF")
    bundle.mkdir(parents=True)
    script_path=bundle/(a.job_name+".sbatch");write_new(script_path,script)
    # Pin only bounded metadata. Do not import the controller or call subprocess.
    pins={ref["path"]:ref for ref in sources}
    request={"kind":"analysis","node":"compute-0-20","cpus":16,"memory_gib":memory,"wall_seconds":wall,
        "estimated_peak_output_bytes":peak,"pilot":True,"estimated_total_core_hours":16*wall/3600,
        "script_reference":reference(script_path),"source_references":[pins[key] for key in sorted(pins)],
        "root_review":root_review}
    request_path=bundle/"request.proposed.json";write_json(request_path,request)
    write_json(bundle/"materialization.json",{"schema":"SB2_CLOSURE_METADATA_MATERIALIZATION_V1",
        "status":"MATERIALIZED_ONLY_NOT_SUBMITTED","mode":a.mode,"request_reference":reference(request_path),
        "script_reference":reference(script_path),"repository":str(repo),"source_pins":request["source_references"],
        "formal_v2_stage_files":FORMAL_V2_FILES,"pilot_closure_stage_files":CLOSURE_FILES,
        "materializer_stage_files":["workflows/data_v1_final/conformers/pilot_closure_materializer_v1.py",
                                    "workflows/data_v1_final/conformers/pilot_closure_materializer_v1.md"],
        "runtime_environment":{"python_logical_entry":PYTHON,"pythonpath":DEPS,
                               "package_versions":"Not imported by this metadata-only standard-library process"},
        "root_review_attached":bool(a.root_review),"automatic_submission":False,"automatic_retry":False,
        "scientific_calls":0,"new_once_keys":0,"big_data_pages_read":False,
        "next_step":"Root reviews pinned script/request, checks repository/tests, then alone invokes existing submit_reviewed.py after fresh live hardware/quota admission. No submission command is executed or retried here."})
    print(json.dumps({"status":"MATERIALIZED_ONLY_NOT_SUBMITTED","request":str(request_path),
                      "root_review":root_review["status"]}))


if __name__=="__main__":main()
