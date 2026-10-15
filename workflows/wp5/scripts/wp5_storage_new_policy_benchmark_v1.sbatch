#!/bin/bash
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --job-name=wp5_g3_new_policy_proto
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/g3_new_policy_proto_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/g3_new_policy_proto_%j.err
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=""
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
PYTHON=/share/home/zixiao/.conda/envs/chemprop/bin/python
: "${WP5_G6_REPORTS_FILE:?Root must supply actual closed full-output G6 report list}"
WP5_AUDIT_MANIFEST="${WP5_AUDIT_MANIFEST:-$WP5_ROOT/audit_membership/job_4513945/manifest.json}"
mapfile -t WP5_G6_PATHS < "$WP5_G6_REPORTS_FILE"
/usr/bin/time -v -o "$WP5_ROOT/logs/g3_new_policy_proto_${SLURM_JOB_ID}.time.log" \
 "$PYTHON" -B "$WP5_ROOT/scripts/wp5_storage_new_policy_benchmark_v1.py" \
 --workers 16 --reports "${WP5_G6_PATHS[@]}" --audit-manifest "$WP5_AUDIT_MANIFEST" \
 --output "$WP5_ROOT/gates/g3/new_policy_benchmark_job_${SLURM_JOB_ID}"
# Only new TEST prototypes are written. Original full outputs/science remain read-only.
