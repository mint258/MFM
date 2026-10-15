#!/bin/bash
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010
SHARD=${1:?source shard ID required}
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
set +e
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/wp1_geometry.py" --input "$ROOT/record_index.parquet" --output "$ROOT/wp1_geometry_full/shard_${SHARD}_job_${SLURM_JOB_ID}" --workers "$SLURM_CPUS_PER_TASK" --shards "$SHARD" --timeout 30
task_rc=$?
printf '%s\n' "$task_rc" > "$ROOT/logs/wp1_geometry_full_${SLURM_JOB_ID}.exitcode"
exit "$task_rc"
