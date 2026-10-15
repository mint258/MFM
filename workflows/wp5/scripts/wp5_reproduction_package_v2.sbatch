#!/bin/bash
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --job-name=wp5_reproduction_package_v2
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/reproduction_package_v2_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/reproduction_package_v2_%j.err
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
PYTHON=/share/home/zixiao/.conda/envs/chemprop/bin/python
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=""
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:$WP5_ROOT/scripts:${PYTHONPATH:-}
: "${WP5_CURRENT_CODE_CHAIN:?Root final current source inventory required}"
WP5_AUDIT_MEMBERSHIP="${WP5_AUDIT_MEMBERSHIP:-$WP5_ROOT/audit_membership/job_4513945/manifest.json}"
/usr/bin/time -v -o "$WP5_ROOT/logs/reproduction_package_v2_${SLURM_JOB_ID}.time.log" \
 timeout --signal=TERM --kill-after=120s 46h "$PYTHON" -B "$WP5_ROOT/scripts/wp5_reproduction_package_v2.py" \
 --workers 24 --chain "$WP5_CURRENT_CODE_CHAIN" --audit-membership "$WP5_AUDIT_MEMBERSHIP" \
 --out "$WP5_ROOT/reproduction_package/job_${SLURM_JOB_ID}"
