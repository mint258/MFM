#!/bin/bash
#SBATCH --job-name=C1-TDC-ASAP-TabPFN-failed-report-only
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,14,18,20-22]
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=04:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_TDC_ASAP_failed_report_only_%j.log
set -euo pipefail
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
cd /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/environments/gpu_cu118_job_4536985_step_24/tabpfn/bin/python -B - <<'PY'

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
    protect(root,16*1024**2+forecast,quota,own_concurrent_bytes=40*1024**3)
    return forecast



import ast,subprocess
b1=root.parent/"benchmark_B1_20261119"
cache=Path(os.environ["BENCHMARK_SOURCE_CACHE"])
if not cache.resolve().is_relative_to(b1.resolve()):raise ValueError("Owned shared source cache required")
sources=json.loads(cache.read_text())
cpu={}
exec(compile(sources["workflows/benchmark_evaluation/cpu_tabpfn_primary.py"],"cpu_tabpfn_primary","exec"),cpu)
original_manifest=b1/"C1_Pprime_TABPFN/job_4537694/manifest.json"
closed=json.loads(original_manifest.read_text())
accounting=subprocess.run(["ssh","-n","-o","BatchMode=yes","-o","ConnectTimeout=10","sonmi",
 "sacct","-X","-n","-P","-j","4537694","-o","JobIDRaw,State,ExitCode"],text=True,capture_output=True,check=True,timeout=25).stdout
raw=sources["workflows/benchmark_evaluation/c1_pprime_tdc_asap_tabpfn.sbatch"]
original=raw.split("<<'PY'\n",1)[1].rsplit("\nPY",1)[0]
program,failed_keys=cpu["prepare_failed_reporting_source"](original,closed,accounting,4537694)
safe();continuation_source_root=b1/"failed_report_native_continuation"/("job_"+os.environ["SLURM_JOB_ID"]);continuation_source_root.mkdir(parents=True,exist_ok=False)
safe();program_path=continuation_source_root/"failed_only_original_CPU_model.py";program_path.write_text(program)
declaration=dict(status="ACTUAL_CLOSED_FAILED_TASKS_AUTHORIZED",job=os.environ["SLURM_JOB_ID"],source_job=4537694,
 source_manifest=str(original_manifest),native_accounting=accounting,failed_tasks=failed_keys,
 first_attempt_completed_tasks=closed["tasks_completed"],original_successful_predictions_copied_or_refitted=False,
 fixed_weight_context_inference=True,training_rollback=False,model_seed=20261025,
 max_additional_context_inference_attempts_per_failed_task=1,second_failed_attempt_status="UNRESOLVED_AFTER_ALLOWED_REPORT_REPAIR",
 source_cache=str(cache),model_program=str(program_path))
safe();(continuation_source_root/"declaration.json").write_text(json.dumps(declaration,indent=2)+"\n")
print("FAILED_REPORT_ONLY_CONTEXT_INFERENCE_START",len(failed_keys),"source",4537694,flush=True)
exec(compile(program,str(program_path),"exec"),globals())
safe();(continuation_source_root/"native_model_body_closed.json").write_text(json.dumps(dict(status="FAILED_ONLY_MODEL_BODY_CLOSED",job=os.environ["SLURM_JOB_ID"],source_job=4537694,source_manifest=str(original_manifest),original_successful_models_replayed=False),indent=2)+"\n")

PY
