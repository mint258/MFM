#!/bin/bash
set -euo pipefail
# Root supplies actual node/partition/resources through submit_job_v2.py.
# Suggested read-only metadata job: 16 CPU, 32 GiB, 00:30:00.
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
mkdir -p "$ROOT/wp4_archive_scope_projection"
set +e
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/wp4_archive_scope_projection.py" --output "$ROOT/wp4_archive_scope_projection/job_${SLURM_JOB_ID}" --workers "$SLURM_CPUS_PER_TASK"
task_rc=$?
printf '%s\n' "$task_rc" > "$ROOT/logs/wp4_archive_scope_projection_${SLURM_JOB_ID}.exitcode"
exit "$task_rc"
