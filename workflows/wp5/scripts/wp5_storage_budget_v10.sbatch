#!/bin/bash
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --job-name=wp5_g3_new_policy_budget
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/g3_budget_v10_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/g3_budget_v10_%j.err
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=""
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
PYTHON=/share/home/zixiao/.conda/envs/chemprop/bin/python
: "${WP5_BENCHMARK_PATH:?Root must supply actual completed rescue benchmark.json}"
: "${WP5_NEW_POLICY_PROTOTYPE:?Root must supply actual new policy prototype report}"
: "${WP5_QUOTA_PATH:?Root must publish fresh login quota JSON}"
: "${WP5_REMAINING_TEST_BYTES:?Explicit remaining50-double/final200/new-six test bytes not yet charged}"
: "${WP5_REPRODUCTION_PACKAGE:?Root must supply actual closed reproduction package manifest}"
WP5_AUDIT_MANIFEST="${WP5_AUDIT_MANIFEST:-$WP5_ROOT/audit_membership/job_4513945/manifest.json}"
/usr/bin/time -v -o "$WP5_ROOT/logs/g3_budget_v10_${SLURM_JOB_ID}.time.log" \
 "$PYTHON" -B "$WP5_ROOT/scripts/wp5_storage_budget_v10.py" \
 --workers 16 --benchmark "$WP5_BENCHMARK_PATH" --prototype "$WP5_NEW_POLICY_PROTOTYPE" \
 --quota "$WP5_QUOTA_PATH" --remaining-tests-not-in-quota-bytes "$WP5_REMAINING_TEST_BYTES" \
 --audit-manifest "$WP5_AUDIT_MANIFEST" --reproduction-package "$WP5_REPRODUCTION_PACKAGE" \
 --output "$WP5_ROOT/gates/g3/new_policy_budget_v10_job_${SLURM_JOB_ID}.json"
# Metadata only. Old ALL/min policies are superseded; no cache filtering is assumed.
