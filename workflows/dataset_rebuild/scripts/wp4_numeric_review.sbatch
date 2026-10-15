#!/bin/bash
#SBATCH --job-name=p1_rebuild_wp4_numeric_review
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=16G
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/logs/wp4_numeric_review_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/logs/wp4_numeric_review_%j.err
# Root chooses nodelist after actual sinfo/scontrol/declared-memory preflight.
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 BLIS_NUM_THREADS=1
cd "$ROOT"
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/wp4_parsers.py" \
  --review-capability "$ROOT/wp4_capability/job_4512796" \
  --review-capability "$ROOT/wp4_static_polar/job_4512797" \
  --output "$ROOT/reports/wp4_capability_numeric_review_v2.json" --workers 16
