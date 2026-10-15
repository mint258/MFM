#!/bin/bash
#SBATCH --job-name=wp5_g3_budget_v5
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/g3_budget_v5_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/g3_budget_v5_%j.err
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=""
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
PYTHON=/share/home/zixiao/.conda/envs/chemprop/bin/python
: "${WP5_BENCHMARK_PATH:?Root must set the actual completed rescue benchmark.json path}"
: "${WP5_G6_REPORTS_FILE:?Root must set a text file containing actual closed G6 report paths}"
: "${WP5_QUOTA_PATH:?Root must publish and supply fresh login quota JSON}"
: "${WP5_REMAINING_TEST_BYTES:?Root must explicitly supply bytes for remaining tests not charged in quota}"
mapfile -t WP5_G6_PATHS < "$WP5_G6_REPORTS_FILE"
WP5_PROJECTION_ARGS=()
WP5_EXPECTED_REPORTS=6
WP5_OUTPUT_NAME=final_budget_v5_job
if [ "${WP5_PROVISIONAL:-0}" = 1 ]; then
  WP5_PROJECTION_ARGS+=(--provisional)
  WP5_EXPECTED_REPORTS=4
  WP5_OUTPUT_NAME=provisional_budget_v5_job
fi
if [ "${#WP5_G6_PATHS[@]}" -ne "$WP5_EXPECTED_REPORTS" ]; then
  printf '%s\n' 'Expected actual4 provisional14/17/18/19 or actual6 formal closed G6 report paths' >&2
  exit 1
fi
/usr/bin/time -v -o "$WP5_ROOT/logs/g3_budget_v5_${SLURM_JOB_ID}.time.log" "$PYTHON" -B "$WP5_ROOT/scripts/wp5_storage_budget_v5.py" \
  --workers 16 "${WP5_PROJECTION_ARGS[@]}" --benchmark "$WP5_BENCHMARK_PATH" --g6-reports "${WP5_G6_PATHS[@]}" \
  --minimum-manifest "$WP5_ROOT/gates/g3/minimum_audit_4513909/manifest.json" \
  --quota "$WP5_QUOTA_PATH" --remaining-tests-not-in-quota-bytes "$WP5_REMAINING_TEST_BYTES" \
  --output "$WP5_ROOT/gates/g3/${WP5_OUTPUT_NAME}_${SLURM_JOB_ID}.json"
# Metadata/readback only. Original sources/dictionaries/Parquet remain read-only. Root alone submits.
