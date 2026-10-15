#!/bin/bash
#SBATCH --job-name=wp5_g3_storage
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-14
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/g3_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/g3_%j.err
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=""
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
PYTHON=/share/home/zixiao/.conda/envs/chemprop/bin/python
"$PYTHON" -B "$WP5_ROOT/scripts/wp5_storage_gate.py" \
  --workers 16 \
  --population "$WP5_ROOT/population/manifest.json" \
  --quota "$WP5_ROOT/gates/g1_g2_initial.json" \
  --output "$WP5_ROOT/gates/g3/job_${SLURM_JOB_ID}"
# No QM, no LMDB creation, no source deletion; Root alone submits.
# The final quota+temporary/raw-scope projection is a metadata-only --finalize.
