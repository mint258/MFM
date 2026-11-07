"""Formal authorization, actual accounting, task identity and one-attempt journals."""
from __future__ import annotations
import hashlib
import csv
import importlib.util
import json
import math
import os
from pathlib import Path
import socket
import sys
import time

sys.dont_write_bytecode=True
PARENT=Path(__file__).parent.parent
sys.path.insert(0,str(PARENT))
if hashlib.sha256((PARENT/"common.py").read_bytes()).hexdigest()!="ffa4fc9b6ce97be5b62af926c35337168b687f1f80a0fdd3564957dfe169b83b":
    raise ValueError("REGISTERED_IO_HELPER_CHANGED")
import common as IO
if Path(IO.__file__).absolute()!=PARENT/"common.py":raise ValueError("WRONG_COMMON_MODULE_IMPORTED")

KERNEL_SHA="2476767636d97b2a334dcf1f8b8e789e137a268acc6404ade61b7162690d211f"


def q(value):return "'" + str(value).replace("'","''") + "'"


def config(path):
    value=json.loads(Path(path).read_text())
    if value["schema"]!="DATA_V1_SPRIME_FORMAL_V1":
        raise ValueError("FORMAL_CONFIG_REQUIRED")
    if value["formal_cpus"]!=16 or value["formal_memory_gib"]!=64 or not 0<value["wall_seconds"]<=48*3600:
        raise ValueError("ORIGINAL_FORMAL_16CPU64G_AND_MAX48H_REQUIRED")
    if value["max_output_bytes"]!=8*1024**3:
        raise ValueError("FORMAL_8GIB_BATCH_CAP_REQUIRED")
    if value["exclusion_policy"]!={"overall_max":0.02,"element_max":0.2,"approved_element_exceptions":[34]}:
        raise ValueError("ORIGINAL_STOP_THRESHOLDS_AND_SE_ONLY_EXCEPTION_REQUIRED")
    for key in ("recipe_config","roles_authority","per_molecule","formal_source_receipt","sprime_manifest"):
        IO.require_pin(value[key])
    if IO.digest(PARENT/"science.py")!=KERNEL_SHA:
        raise ValueError("REGISTERED_KERNEL_CHANGED")
    return value


def task_key(mid,cohort):
    return hashlib.sha256(("sprime-fill-once-v1:"+KERNEL_SHA+":"+mid+":"+cohort).encode()).hexdigest()


def require_budget_review(estimate,decision):
    cap=decision["approved_total_core_hours_cap"]
    if not math.isfinite(estimate) or not math.isfinite(cap) or estimate<0 or cap<estimate:
        raise ValueError("FINITE_ADEQUATE_ROOT_CORE_HOUR_CAP_REQUIRED")
    if estimate>500 and decision.get("approved_over_500_core_hours") is not True:
        raise ValueError("OVER500_CORE_HOURS_REQUIRES_EXPLICIT_ROOT_REVIEW")


def require_actual_accounting(path,pilot_job_id=None):
    value=json.loads(Path(path).read_text())
    if value.get("schema")!="DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1" or value.get("status")!="ACTUAL_PARENT_ACCOUNTING_CLOSED":
        raise ValueError("ACTUAL_TERMINAL_PARENT_ACCOUNTING_REQUIRED")
    if value.get("query_returncode")!=0:
        raise ValueError("SUCCESSFUL_ACTUAL_SACCT_QUERY_REQUIRED")
    raw=IO.require_pin(value["raw_sacct_reference"]).read_text().splitlines()
    reader=csv.DictReader(raw,delimiter="|")
    if not reader.fieldnames or not {"State","ExitCode","ElapsedRaw","AllocCPUS"}<=set(reader.fieldnames):
        raise ValueError("PARSABLE_SACCT_HEADER_REQUIRED")
    jid_field="JobIDRaw" if "JobIDRaw" in reader.fieldnames else "JobID"
    actual={}
    for observed in reader:
        jid=observed.get(jid_field,"")
        if not jid.isdecimal():continue
        if jid in actual:raise ValueError("DUPLICATE_RAW_PARENT_ACCOUNTING")
        actual[jid]=observed
    ids=set();total=0
    for row in value["parents"]:
        jid=str(row["job_id"])
        if not jid.isdecimal() or jid in ids or row["state"] not in {"COMPLETED","FAILED","TIMEOUT","CANCELLED","OUT_OF_MEMORY","NODE_FAIL"}:
            raise ValueError("UNIQUE_TERMINAL_PARENT_ROWS_ONLY")
        ids.add(jid)
        cpus,seconds=int(row["alloc_cpus"]),int(row["elapsed_raw_seconds"])
        if cpus<0 or seconds<0:
            raise ValueError("INVALID_ACTUAL_PARENT_COST")
        observed=actual.get(jid)
        if observed is None or int(observed["AllocCPUS"])!=cpus or int(observed["ElapsedRaw"])!=seconds or observed["State"].split()[0]!=row["state"] or observed["ExitCode"]!=row["exit_code"]:
            raise ValueError("DECLARED_ACCOUNTING_DIFFERS_FROM_RAW_SACCT")
        total+=cpus*seconds
        if jid==str(pilot_job_id) and (row["state"]!="COMPLETED" or row["exit_code"]!="0:0"):
            raise ValueError("PILOT_PARENT_NOT_SUCCESSFULLY_CLOSED")
    if pilot_job_id is not None and str(pilot_job_id) not in ids:
        raise ValueError("PILOT_JOB_NOT_IN_ACTUAL_ACCOUNTING")
    if ids!=set(actual):raise ValueError("ACCOUNTING_PARENT_SET_DIFFERS_FROM_RAW_SACCT")
    return value,total


def formal_source(value):
    receipt=json.loads(IO.require_pin(value["formal_source_receipt"]).read_text())
    if receipt["status"]!="ALL_BOUND_INPUTS_SHA_VERIFIED":raise ValueError("CLOSED_FORMAL_SOURCE_PIN_REQUIRED")
    rows=[r for r in receipt["outputs"] if r["name"]=="formal_population"]
    if len(rows)!=1:raise ValueError("FORMAL_SOURCE_NOT_UNIQUE")
    row=rows[0];st=Path(row["reference"]["path"]).stat();after=row["after"]
    if (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_uid)!=(after["device"],after["inode"],after["size"],after["mtime_ns"],after["uid"]):
        raise ValueError("FORMAL_SOURCE_IDENTITY_CHANGED")
    return row["reference"]


def review(path,for_planning=False):
    decision=json.loads(Path(path).read_text())
    allowed={"APPROVED","PILOT_ACCEPTED_FOR_PLANNING"} if for_planning else {"APPROVED"}
    if decision.get("schema")!="DATA_V1_SPRIME_FULL_ROOT_REVIEW_V1" or decision.get("status") not in allowed:
        raise ValueError("EXPLICIT_ROOT_FULL_REVIEW_REQUIRED")
    for key in ("pilot_receipt","pilot_accounting","pilot_reproduction_manifest","pilot_tasks"):
        IO.require_pin(decision[key])
    pilot=json.loads(Path(decision["pilot_receipt"]["path"]).read_text())
    if pilot["status"]!="PILOT_COMPLETED_REQUIRES_ROOT_REVIEW" or pilot["expected_molecules"]!=336 or pilot["completed_molecules"]!=336 or pilot.get("resource_denial"):
        raise ValueError("REAL_COMPLETE_PILOT_REQUIRED_BEFORE_FULL")
    if pilot.get("parquet_readback",{}).get("status")!="ALL_PILOT_GEOMETRIES_FLOAT64_SHA_READBACK_PASSED":
        raise ValueError("REAL_PILOT_FLOAT64_READBACK_REQUIRED")
    _,actual=require_actual_accounting(decision["pilot_accounting"]["path"],pilot["runtime"]["job_id"])
    if decision.get("accept_scientific_failure_disclosure") is not True:
        raise ValueError("ROOT_MUST_REVIEW_REAL_FAILURE_CATEGORIES")
    return decision,pilot,actual


def authority_roles(value):
    authority=json.loads(IO.require_pin(value["roles_authority"]).read_text())
    manifest_ref=authority["source_role_manifest"]
    manifest=json.loads(IO.require_pin(manifest_ref).read_text())
    if manifest["status"]!="ROUTINE_MOLECULE_VAL_ROLES_FROZEN" or authority["validation_source"]!="ROUTINE":
        raise ValueError("FROZEN_ROUTINE_MOLECULAR_ROLES_REQUIRED")
    refs=[ref for ref in manifest["outputs"] if "/molecule_roles/" in ref["path"]]
    if len(refs)!=16:
        raise ValueError("ALL16_FROZEN_MOLECULE_ROLE_PARTS_REQUIRED")
    for ref in refs:IO.require_pin(ref)
    return manifest_ref,refs


def runtime(value,intent_path,config_path,science=False):
    node=socket.gethostname().split(".")[0]
    expected={f"compute-0-{i}" for i in range(14,20)} if science else {"compute-0-20"}
    if node not in expected or not os.environ.get("SLURM_JOB_ID") or int(os.environ.get("SLURM_CPUS_PER_TASK",0))<16:
        raise ValueError("FORMAL_STAGE_REQUIRES_OWN_16CPU_SLURM_ON_CORRECT_NODE")
    record=json.loads(Path(intent_path).read_text());request=record["request"]
    if science and (request.get("pilot") is not False or request["memory_gib"]!=64 or request["cpus"]!=16 or request.get("memory_basis")):
        raise ValueError("NO_SMALL_PILOT_MEMORY_POLICY_FOR_FORMAL_RUNS")
    IO.require_preflight(intent_path,config_path,value) # original all-user declaration85%, quota and pins
    return {"job_id":os.environ["SLURM_JOB_ID"],"node":node,"cpus":int(os.environ["SLURM_CPUS_PER_TASK"])}


def ledger_path(value,key):
    if len(key)!=64 or any(c not in "0123456789abcdef" for c in key):
        raise ValueError("INVALID_TASK_KEY")
    root=Path(value["attempt_ledger_root"])
    allowed=Path(value["external_output_root"])
    if not root.is_absolute() or allowed not in root.parents or any(p.is_symlink() for p in (root,*root.parents)):
        raise ValueError("LEDGER_OUTSIDE_OWN_FORMAL_ROOT")
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    return root/(key+".json")


def exclusive_json(path,value):
    raw=(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n").encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())


def begin_attempt(value,task):
    key=task["meta"]["task_key"]
    expected=task_key(task["meta"]["molecule_id"],task["meta"]["cohort"])
    if key!=expected:raise ValueError("TASK_KEY_MISMATCH")
    frame=Path("/proc/self/stat").read_text();start_ticks=int(frame[frame.rfind(")")+2:].split()[19])
    row={"schema":"SPRIME_ONCE_ATTEMPT_STARTED_V1","task_key":key,"molecule_id":task["meta"]["molecule_id"],
         "cohort":task["meta"]["cohort"],"kernel_sha256":KERNEL_SHA,"uid":os.getuid(),"pid":os.getpid(),
         "pid_start_ticks":start_ticks,
         "job_id":os.environ["SLURM_JOB_ID"],"node":socket.gethostname(),"observed_epoch":time.time()}
    exclusive_json(ledger_path(value,key),row) # exists means consumed/unknown; never delete or retry
    return row
