#!/bin/bash
set -euo pipefail
# Root supplies actual node/partition/CPU/memory/time through submit_job_v2.py.
# Suggested bounded metadata/Parquet job: 16 CPU, 48 GiB, 01:00:00.
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
OUT="$ROOT/wp4_storage_benchmark/job_${SLURM_JOB_ID}"
mkdir -p "$ROOT/wp4_storage_benchmark"
set +e
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/wp4_storage_benchmark.py" --panel-manifest "$ROOT/wp4_native_panel/pilot_panel_manifest.json" --native-root "$ROOT/wp4_native_full_v4" --capacity "$ROOT/reports/wp5_capacity_snapshot.json" --output "$OUT" --workers "$SLURM_CPUS_PER_TASK" --max-output-bytes 4000000000
task_rc=$?
printf '%s\n' "$task_rc" > "$ROOT/logs/wp4_storage_benchmark_${SLURM_JOB_ID}.exitcode"
exit "$task_rc"
