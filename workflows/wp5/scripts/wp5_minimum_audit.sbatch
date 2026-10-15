#!/bin/bash
#SBATCH --job-name=wp5_minimum_audit
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/minimum_audit_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/minimum_audit_%j.err
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=""
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$WP5_ROOT/scripts/wp5_minimum_audit.py" \
  --threads 24 --memory-gb 20 \
  --output "$WP5_ROOT/gates/g3/minimum_audit_${SLURM_JOB_ID}"
# Original formal/packing/raw untouched, no new QM/LMDB. Root alone submits.
