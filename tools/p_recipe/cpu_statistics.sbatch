#!/bin/bash
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --nodes=1
#SBATCH --exclude=compute-0-[0-7,14,18,20-22]
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/MFM_p_recipe
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/MFM_p_recipe/current:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository
/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B tools/p_recipe/cpu_statistics.py --finalize-configuration "$1"
