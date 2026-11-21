#!/bin/bash
#SBATCH --job-name=benchmark-TDC-report-repair-cap-finalization
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,14,18,20-22]
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_TDC_report_repair_cap_finalization_%j.log
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



# Metadata-only enforcement of the user's two consecutive failed-repair limit.
# No model package, feature payload, prediction, score, fit, or bootstrap is loaded.
b1=root.parent/"benchmark_B1_20261119"
sources=json.loads((b1/"closed_TDC_prerequisite_preparation/job_4537781/proposed_sources.json").read_text())
cpu={};exec(compile(sources["workflows/benchmark_evaluation/cpu_tabpfn_primary.py"],"cpu_tabpfn_primary","exec"),cpu)
auth_path=b1/"closed_TDC_prerequisite_preparation/job_4537781/closed_source_authorization.json"
auth=json.loads(auth_path.read_text())
keys=cpu["validated_closed_reporting_authorization"](auth,4537694)
if len(keys)!=9 or auth["closed_source_manifest"]["tasks_completed"]!=14:raise ValueError("Exactly9 failed tasks and14 preserved successes required")
native_failures="4537765|FAILED|1:0|1278|zixiao|00:00:03\n4537783|FAILED|1:0|1278|zixiao|00:00:02\n"
records=[line.split("|") for line in native_failures.splitlines()]
if {r[0] for r in records}!={"4537765","4537783"} or any(r[1:5]!=["FAILED","1:0","1278","zixiao"] for r in records):raise ValueError("Both actual owned consecutive failed native repairs required")
log_root=root.parent.parent/"control"
logs={4537765:(log_root/"C1_TDC_ASAP_failed_report_GPU7_4537765.log").read_text(),4537783:(log_root/"C1_TDC_ASAP_closed_C0_failed_GPU7_4537783.log").read_text()}
if "returned non-zero exit status 255" not in logs[4537765] or "Only the exact original nine failed contexts may execute" not in logs[4537783]:raise ValueError("The actual two pre-model failures must be retained")
for job in (4537765,4537783):
    for kind in ("C1_Pprime_TABPFN","gpu_runtime","failed_report_GPU7_continuation"):
        if (b1/kind/("job_"+str(job))).exists():raise ValueError("Do not adjudicate a model/admission output as an empty prefit failure")
safe();out=b1/"C1_TDC_report_repair_cap"/("job_"+os.environ["SLURM_JOB_ID"]);out.mkdir(parents=True,exist_ok=False)
reason="USER_TWO_CONSECUTIVE_REPAIR_FAILURE_CAP: native7765 SSH255 before fit; native7783 source-equivalence guard rejected before GPU admission or fit"
failed_sources=[dict(job=int(row[0]),state=row[1],exit_code=row[2],uid=int(row[3]),user=row[4],elapsed=row[5]) for row in records]
failures=[dict(dataset=dataset,task=task,status="UNRESOLVED_AFTER_ALLOWED_REPORT_REPAIR",reason=reason,
    error="No valid closed predictions; no negative model-performance conclusion",
    capped_native_sources=failed_sources,original_source_job=4537694,model_fits_in_repairs=0,
    GPU_contexts_started_in_repairs=0,third_repair_or_fit_authorized=False) for dataset,task in keys]
for job,log in logs.items():
    safe();(out/("native_"+str(job)+".log")).write_text(log)
safe();(out/"native_failed_accounting.txt").write_text(native_failures)
report=dict(status="C1_NATIVE_REPAIR_CAP_UNRESOLVED_FINALIZED",job=os.environ["SLURM_JOB_ID"],
 producer_role="METADATA_ONLY_FAILURE_FINALIZATION_NOT_MODEL_TRAINING",model_or_inference_executed=False,
 tasks_expected=9,tasks_completed=0,failures=failures,coverage=[],
 original_source_job=4537694,original_source_native_evidence=auth["native_accounting"],original_successful_tasks_preserved=14,
 closed_original_reporting_failure_authorization=str(auth_path),failed_native_sources=failed_sources,
 source_model_seed=20261025,completed_valid_repair_predictions=0,third_GPU_repair_submitted=False,
 user_rule="BENCHMARK_PLAN section7: two consecutive failed diagnosis/repairs -> UNRESOLVED; continue other tasks",
 original_successful_predictions_replayed=False,scientific_scores_or_features_read=False,
 unresolved_is_infrastructure_failure_not_negative_scientific_result=True)
safe();(out/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(dict(status=report["status"],job=report["job"],role=report["producer_role"],unresolved_tasks=9,preserved_original_successes=14,new_models_or_contexts=0)),flush=True)

PY
