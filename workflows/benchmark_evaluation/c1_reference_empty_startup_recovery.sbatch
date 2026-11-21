#!/bin/bash
#SBATCH --job-name=benchmark-reference-empty-startup-recovery
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,14,18,20-22]
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_reference_empty_startup_recovery_%j.log
set -euo pipefail
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
cd /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'

import fcntl,json,os,socket,time
from pathlib import Path
from workflows.benchmark_data.admission import protect
from workflows.benchmark_data.storage_reservations import current_concurrent
root=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119")
quota=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json")
def safe():
    forecast=0
    for folder in (root/"labels/Pprime/shared_v1",root/"directive19/uniform_Sprime/labels/Pprime/shared_v1"):
        access=json.loads((folder/"access.json").read_text())
        if not (access.get("immutable") and access.get("cross_node_read_allowed")):
            forecast+=max(0,80000000000-sum(p.stat().st_size for p in folder.glob("*.sqlite")))
    protect(root,64*1024**2+forecast,quota,own_concurrent_bytes=40*1024**3)
    return forecast



import re,subprocess
b1=root.parent/"benchmark_B1_20261119"
cache=Path(os.environ["BENCHMARK_SOURCE_CACHE"])
if not cache.resolve().is_relative_to(b1.resolve()):raise ValueError("Owned immutable source capsule required")
sources=json.loads(cache.read_text())
h={};exec(compile(sources["workflows/benchmark_evaluation/infrastructure_handover.py"],"handover","exec"),h)
recovery={};exec(compile(sources["workflows/benchmark_evaluation/feature_startup_recovery.py"],"feature_startup_recovery","exec"),recovery)
safe();out=b1/"reference_empty_startup_recovery"/("job_"+os.environ["SLURM_JOB_ID"]);out.mkdir(parents=True,exist_ok=False)
ledger=dict(status="INSPECTING_ACTUAL_TERMINAL_FEATURE_SOURCE",job=os.environ["SLURM_JOB_ID"],original_feature_job=4537149,downstream_model_IDs_changed=False,model_sources_changed=False,new_feature_job=None,released=[],updated_dependencies=[],held=[],scientific_outputs_read_for_QA=False)
def save():
    safe();(out/"manifest.json").write_text(json.dumps(ledger,indent=2)+"\n")
def run(*args):return subprocess.run(args,text=True,capture_output=True,check=True,timeout=45).stdout.strip()
def detail(job):
    raw=run("scontrol","show","job",str(job),"-o");value=h["require_owned_pending"](raw)
    safe();(out/("job_"+str(job)+".native.txt")).write_text(raw+"\n");return value
save()
native=subprocess.run(["ssh","-n","-oBatchMode=yes","-oConnectTimeout=10","sonmi","sacct -X -n -P -j 4537149 -o JobID,User,State,ExitCode"],text=True,capture_output=True,check=True,timeout=25).stdout
rows=[r.strip().split("|") for r in native.splitlines() if r.strip().split("|")[0]=="4537149"]
if len(rows)!=1 or rows[0][1]!="zixiao":raise ValueError("Actual registered native source ownership required")
actual=rows[0];delivery=b1/"C1_Pprime_reference_features/job_4537149"
if not delivery.resolve().is_relative_to(b1.resolve()):raise ValueError("The original namespace escaped its owned artifact root")
action=recovery["continuation_decision"](actual[2],actual[3],delivery.exists() or delivery.is_symlink())
ledger.update(native_original_accounting=native,decision=action,original_namespace=str(delivery),original_feature_state=actual[2]);save()
if action=="NO_OP_SUCCESS":
    manifest=json.loads((delivery/"manifest.json").read_text())
    if manifest.get("status")!="C1_PPRIME_REFERENCE_OPTICAL_AND_ATOMIC_FEATURES_CLOSED" or str(manifest.get("job"))!="4537149":
        raise ValueError("Native successful source needs its actual closed feature contract")
    ledger["status"]="NO_RECOVERY_NEEDED_ORIGINAL_FEATURE_CLOSED";save();print(json.dumps(ledger),flush=True);raise SystemExit(0)
if action!="RETRY_EMPTY_FAILED_OUTPUT":
    ledger["status"]="PARTIAL_FEATURE_OUTPUT_REQUIRES_SCOPED_RECOVERY_NO_WHOLE_REPLAY";save();print(json.dumps(ledger),flush=True);raise SystemExit(3)
capture=json.loads((b1/"reference_pending_native_capture/job_4537760/manifest.json").read_text())
jobs=[int(r["job"]) for r in capture["sources"]]
if len(set(jobs))!=45 or not capture["all_pending_zero_runtime"]:raise ValueError("Exactly45 registered original pending model identities required")
before={job:detail(job) for job in jobs}
if delivery.exists() or delivery.is_symlink():raise ValueError("Do not replay any original scientific output")
claim=root.parent.parent/"control/benchmark_C1_reference_empty_startup_4537149.json"
safe()
with claim.open("x") as stream:stream.write(json.dumps(dict(controller_job=os.environ["SLURM_JOB_ID"],original_feature_job=4537149,original_native_accounting=native,original_output_absent=True,output_namespace=str(delivery),attempt=1),indent=2)+"\n")
ledger["one_attempt_claim"]=str(claim);save()
for job in jobs:
    detail(job);run("scontrol","hold",str(job));ledger["held"].append(job);save()
script=sources["workflows/benchmark_evaluation/c1_reference_features_startup_continuation.sbatch"]
subprocess.run(["bash","-n"],input=script,text=True,capture_output=True,check=True)
safe();script_path=out/"native_feature_continuation.sbatch";script_path.write_text(script)
response=run("sbatch","--parsable","--hold","--exclude=compute-0-[0-7,14,18,20-22]","--export=ALL,BENCHMARK_FEATURE_RECOVERY_DECLARATION="+str(claim),str(script_path))
if not re.fullmatch(r"[0-9]+(?:;[A-Za-z0-9_-]+)?",response):raise ValueError("An exact held native feature ID is required")
new=int(response.split(";")[0]);ledger["new_feature_job"]=new;ledger["new_feature_script"]=str(script_path);save()
if detail(new)["Reason"]!="JobHeldUser":raise ValueError("New feature source must remain held")
for job in jobs:
    current=detail(job)
    dep=h["remap_dependency"](current.get("Dependency"),{4537149:new})
    parts=[] if not dep else dep.split(",")
    if "afterok:"+str(new) not in parts:parts.append("afterok:"+str(new))
    updated=",".join(parts)
    run("scontrol","update","JobId="+str(job),"Dependency="+updated)
    ledger["updated_dependencies"].append(dict(job=job,dependency=updated));save()
ledger["status"]="ONE_EMPTY_FEATURE_CONTINUATION_AND_ALL45_ORIGINAL_MODELS_RECORDED_BEFORE_RELEASE";save()
if detail(new)["Reason"]!="JobHeldUser":raise ValueError("Feature producer was released before recording")
run("scontrol","release",str(new));ledger["released"].append(new);save()
for job in jobs:
    if before[job].get("Reason")=="JobHeldUser":continue
    if detail(job)["Reason"]!="JobHeldUser":raise ValueError("Only a recorded original held model may be released")
    run("scontrol","release",str(job));ledger["released"].append(job);save()
ledger["status"]="EMPTY_FAILED_FEATURE_CONTINUATION_RELEASED_ORIGINAL45_MODEL_IDS_PRESERVED";save()
print(json.dumps({k:ledger[k] for k in ("status","job","original_feature_job","new_feature_job","original_namespace","released","model_sources_changed","downstream_model_IDs_changed")}),flush=True)

PY
