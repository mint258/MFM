#!/bin/bash
#SBATCH --job-name=wp5_g3_rescue
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/g3_rescue_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/g3_rescue_%j.err
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=""
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
PYTHON=/share/home/zixiao/.conda/envs/chemprop/bin/python
/usr/bin/time -v -o "$WP5_ROOT/logs/g3_rescue_${SLURM_JOB_ID}.time.log" "$PYTHON" -B "$WP5_ROOT/scripts/wp5_storage_rescue.py" \
  --workers 16 --source-root "$WP5_ROOT/gates/g3/job_4513894" \
  --output "$WP5_ROOT/gates/g3/rescue_${SLURM_JOB_ID}"
# Read original science/dictionaries only. No QM, LMDB, science Parquet rewrite, or deletion.
