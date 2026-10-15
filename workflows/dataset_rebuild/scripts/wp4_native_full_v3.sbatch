#!/bin/bash
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010
BUCKET=${1:?molecule bucket required}
COUNT=${2:-16}
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
OUT="$ROOT/wp4_native_full_v3/bucket_${BUCKET}"
RESUME=()
if [[ -f "$OUT/metadata.json" ]]; then RESUME=(--resume); fi
set +e
/usr/bin/time -v -o "$ROOT/logs/wp4_native_${SLURM_JOB_ID}.time.log" /share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/wp4_native_pilot_v3.py" --panel "$ROOT/wp4_native_panel/pilot_panel.parquet" --panel-manifest "$ROOT/wp4_native_panel/pilot_panel_manifest.json" --record-index "$ROOT/record_index.parquet" --output "$OUT" --workers "$SLURM_CPUS_PER_TASK" --bucket-count "$COUNT" --bucket "$BUCKET" --wall-seconds 84600 "${RESUME[@]}"
task_rc=$?
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/record_job_resources.py" --time-log "$ROOT/logs/wp4_native_${SLURM_JOB_ID}.time.log" --output "$OUT/job_${SLURM_JOB_ID}_resources.json"
printf '%s\n' "$task_rc" > "$ROOT/logs/wp4_native_full_v3_${SLURM_JOB_ID}.exitcode"
exit "$task_rc"
