#!/bin/bash
#SBATCH --job-name=wp5_g3_budget_v4
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/g3_budget_v4_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/g3_budget_v4_%j.err
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=""
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
PYTHON=/share/home/zixiao/.conda/envs/chemprop/bin/python
: "${WP5_BENCHMARK_PATH:?Root must set the actual completed rescue benchmark.json path}"
: "${WP5_G6_REPORTS_FILE:?Root must set a text file containing six actual repaired report.json paths}"
: "${WP5_QUOTA_PATH:?Root must publish and supply fresh login quota JSON}"
: "${WP5_REMAINING_TEST_BYTES:?Root must explicitly supply bytes for remaining tests not charged in quota}"
mapfile -t WP5_G6_PATHS < "$WP5_G6_REPORTS_FILE"
if [ "${#WP5_G6_PATHS[@]}" -ne 6 ]; then
  printf '%s\n' 'Expected six completed original-node G6 report paths' >&2
  exit 1
fi
/usr/bin/time -v -o "$WP5_ROOT/logs/g3_budget_v4_${SLURM_JOB_ID}.time.log" "$PYTHON" -B "$WP5_ROOT/scripts/wp5_storage_budget_v4.py" \
  --workers 16 --benchmark "$WP5_BENCHMARK_PATH" --g6-reports "${WP5_G6_PATHS[@]}" \
  --minimum-manifest "$WP5_ROOT/gates/g3/minimum_audit_4513909/manifest.json" \
  --quota "$WP5_QUOTA_PATH" --remaining-tests-not-in-quota-bytes "$WP5_REMAINING_TEST_BYTES" \
  --output "$WP5_ROOT/gates/g3/final_budget_v4_job_${SLURM_JOB_ID}.json"
# Metadata/readback only. Original sources/dictionaries/Parquet remain read-only. Root alone submits.
