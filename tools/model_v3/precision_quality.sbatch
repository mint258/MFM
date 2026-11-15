#!/bin/bash
#SBATCH --job-name=precision-quality
#SBATCH --partition=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_precision_20261115/results/precision_20261115/%x_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/MFM_precision_20261115
export PYTHONDONTWRITEBYTECODE=1
exec /share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B -u tools/model_v3/precision_quality.py "${PRECISION_EXECUTION:-standby}" --task "${1:?task}"
