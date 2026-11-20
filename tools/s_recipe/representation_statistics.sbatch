#!/bin/bash
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,14,18,20-22]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=04:00:00
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/MFM_s_recipe
export CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK OPENBLAS_NUM_THREADS=$SLURM_CPUS_PER_TASK MKL_NUM_THREADS=$SLURM_CPUS_PER_TASK NUMEXPR_NUM_THREADS=$SLURM_CPUS_PER_TASK
export PYTHONPATH=$PWD/current:$PWD/tools/s_recipe:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
exec /share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B -u tools/s_recipe/representations.py --statistics --configuration "${1:?S endpoint configuration}"
