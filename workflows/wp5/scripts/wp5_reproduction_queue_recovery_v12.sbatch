#!/bin/bash
#SBATCH --job-name=wp5_pkg_queue_recovery12
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/wp5_pkg_queue_recovery12_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/wp5_pkg_queue_recovery12_%j.err
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=""
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
WP5_ORIGINAL_PACKAGE=${WP5_ORIGINAL_PACKAGE:-$WP5_ROOT/reproduction_package/queue_recovery_job_4514065/manifest.json}
WP5_ADDITIONAL_SOURCES=${WP5_ADDITIONAL_SOURCES:-$WP5_ROOT/configs/current_code_chain_user_override_v6.json}
/usr/bin/time -v -o "$WP5_ROOT/logs/wp5_pkg_queue_recovery12_${SLURM_JOB_ID}.time.log" \
 /share/home/zixiao/.conda/envs/chemprop/bin/python -B "$WP5_ROOT/scripts/wp5_reproduction_package_supplement_v2.py" \
 --workers 24 --original-manifest "$WP5_ORIGINAL_PACKAGE" --additional-sources "$WP5_ADDITIONAL_SOURCES" \
 --out "$WP5_ROOT/reproduction_package/queue_recovery_v12_job_${SLURM_JOB_ID}"
# Metadata/hash/copy only. Root submission occurs after actual run5 PASS and freeze preparation.
