#!/bin/bash
#SBATCH --job-name=D-new-loss-tests
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,18,20-22]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_d_recipe_loss_tests_%j.out
set -euo pipefail
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis/MFM_d_recipe
export PYTHONPATH="$PWD:$PWD/current"
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m unittest discover -s tests -p test_d_recipe_loss.py -v
