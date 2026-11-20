#!/bin/bash
#SBATCH --job-name=D-stage0-environment
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,18,20-22]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120_environment_%j.out
set -euo pipefail
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120
export PYTHONPATH="$PWD:$PWD/current"
/share/home/zixiao/.conda/envs/chemprop/bin/python -B workflows/data_d_descriptors/environment.py
