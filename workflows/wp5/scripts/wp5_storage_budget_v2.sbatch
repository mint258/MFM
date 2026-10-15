#!/bin/bash
#SBATCH --job-name=wp5_g3_budget_v2
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/g3_budget_v2_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/g3_budget_v2_%j.err
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=""
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
PYTHON=/share/home/zixiao/.conda/envs/chemprop/bin/python
: "${WP5_QUOTA_PATH:?Root must provide the actual freshly refreshed quota JSON}"
: "${WP5_REMAINING_TEST_BYTES:?Root must provide remaining test bytes not already charged in that quota, including explicit 0 when all tests closed}"
"$PYTHON" -B "$WP5_ROOT/scripts/wp5_storage_budget_v2.py" \
  --workers 16 \
  --benchmark "$WP5_ROOT/gates/g3/job_4513894/benchmark.json" \
  --g6-reports \
  "$WP5_ROOT/gates/g6/compute-0-14/job_4513901/report.json" \
  "$WP5_ROOT/gates/g6/compute-0-15/job_4513902/report.json" \
  "$WP5_ROOT/gates/g6/compute-0-16/job_4513903/report.json" \
  "$WP5_ROOT/gates/g6/compute-0-17/job_4513904/report.json" \
  "$WP5_ROOT/gates/g6/compute-0-18/job_4513905/report.json" \
  "$WP5_ROOT/gates/g6/compute-0-19/job_4513906/report.json" \
  --quota "$WP5_QUOTA_PATH" \
  --remaining-tests-not-in-quota-bytes "$WP5_REMAINING_TEST_BYTES" \
  --output "$WP5_ROOT/gates/g3/final_budget_job_${SLURM_JOB_ID}.json"
# Root sole submission after actual G3/G6 closure; metadata/compression only.
# No new scientific serialization/QM/LMDB/source writes or source deletion.
