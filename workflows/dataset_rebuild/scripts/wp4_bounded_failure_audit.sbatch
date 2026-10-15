#!/bin/bash
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
set +e
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/wp4_bounded_failure_audit.py" --pilot-root "$ROOT/wp4_native_bounded_v3_repair/job_4512823" --out "$ROOT/reports/wp4_bounded_failure_audit_job_${SLURM_JOB_ID}.json" --workers "$SLURM_CPUS_PER_TASK"
task_rc=$?
printf '%s\n' "$task_rc" > "$ROOT/logs/wp4_bounded_failure_audit_${SLURM_JOB_ID}.exitcode"
exit "$task_rc"
