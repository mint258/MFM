#!/bin/bash
#SBATCH --job-name=p-recipe-hybrid
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/p_recipe_20261113/%x_%j.log
set -euo pipefail
root=/share/home/zixiao/descriptor_analysis
cd "$root/MFM_p_recipe"
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
exec /share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B -u tools/p_recipe/scheduled_run.py --task "${1:?task configuration}"
