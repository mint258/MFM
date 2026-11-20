#!/bin/bash
#SBATCH --job-name=D-environment-and-new-logic-tests
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,18,20-22]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_d_recipe_data_tests_%j.out
set -euo pipefail
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis/MFM_d_recipe
/share/home/zixiao/.conda/envs/chemprop/bin/python -B tools/d_recipe/run_new_data_tests.py
