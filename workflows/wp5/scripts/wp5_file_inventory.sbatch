#!/bin/bash
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
set -euo pipefail
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export CUDA_VISIBLE_DEVICES=""
cd /share/home/zixiao/descriptor_analysis
/share/home/zixiao/.conda/envs/chemprop/bin/python runs/phase1_wp5_20261011/scripts/wp5_file_inventory.py --workers 24 --output runs/phase1_wp5_20261011/reports/account_top_level_inventory.json
