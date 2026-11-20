#!/bin/bash
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/MFM_s_recipe
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
export PYTHONPATH=$PWD/current:$PWD/tools/s_recipe:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
exec /share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B -u tools/s_recipe/scheduled_run.py --task "${1:?S scheduling task}"
