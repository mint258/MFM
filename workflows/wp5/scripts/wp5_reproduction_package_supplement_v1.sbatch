#!/bin/bash
#SBATCH --job-name=wp5_pkg_runtime_supplement
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/wp5_pkg_supplement_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/wp5_pkg_supplement_%j.err
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=""
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
WP5_ADDITIONAL_ARGS=()
if [ -n "${WP5_ADDITIONAL_SOURCES:-}" ]; then
  WP5_ADDITIONAL_ARGS+=(--additional-sources "$WP5_ADDITIONAL_SOURCES")
fi
/usr/bin/time -v -o "$WP5_ROOT/logs/wp5_pkg_supplement_${SLURM_JOB_ID}.time.log" \
 /share/home/zixiao/.conda/envs/chemprop/bin/python -B "$WP5_ROOT/scripts/wp5_reproduction_package_supplement_v1.py" \
 --workers 24 --original-manifest "${WP5_ORIGINAL_PACKAGE:-$WP5_ROOT/reproduction_package/job_4513947/manifest.json}" \
 "${WP5_ADDITIONAL_ARGS[@]}" --out "$WP5_ROOT/reproduction_package/supplement_job_${SLURM_JOB_ID}"
# Metadata/hash/copy only. No scientific calculation, environment installation or original mutation.
