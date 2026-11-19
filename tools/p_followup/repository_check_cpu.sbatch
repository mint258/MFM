#!/bin/bash
#SBATCH --job-name=p-followup-repository-check
#SBATCH --nodelist=compute-0-17
#SBATCH --partition=cpu
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/p_followup_20261116/repository_check_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/MFM_p_followup_20261117
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
exec /share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B -u tools/check_repository.py --output results/p_followup/REPOSITORY_CHECK.json
