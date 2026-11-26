#!/bin/bash
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --cpus-per-task=16
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/MFM_p_recipe
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/MFM_p_recipe/current:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B -u tools/p_recipe/budget_curve.py --launch-configuration "$1"
