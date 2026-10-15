#!/bin/bash
#SBATCH --job-name=bq_prepare
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=01:00:00
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
exec /share/home/zixiao/.conda/envs/chemprop/bin/python runs/phase1_screening_20261011/scripts/b_quantum_prepare.py --workers 16 --out runs/phase1_screening_20261011/b_quantum/plan
