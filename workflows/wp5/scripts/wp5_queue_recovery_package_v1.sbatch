#!/bin/bash
#SBATCH --job-name=wp5_queue_recovery_package
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.err
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
WP5_PACKAGE_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
export PYTHONPATH="$WP5_PACKAGE_ROOT/scripts:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps${PYTHONPATH:+:$PYTHONPATH}"
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B "$WP5_PACKAGE_ROOT/scripts/wp5_reproduction_package_supplement_v2.py" \
  --original-manifest "$WP5_PACKAGE_ROOT/reproduction_package/supplement_job_4513971/manifest.json" \
  --additional-sources "$WP5_PACKAGE_ROOT/configs/current_code_chain_user_override_v5.json" \
  --out "$WP5_PACKAGE_ROOT/reproduction_package/queue_recovery_job_${SLURM_JOB_ID}" --workers 24