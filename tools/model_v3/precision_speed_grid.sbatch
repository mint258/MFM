#!/bin/bash
#SBATCH --job-name=precision-4090-grid
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-20
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_precision_20261115/results/precision_20261115/grid_4090_%j.log
set -euo pipefail
[[ $(hostname -s) != compute-0-21 ]]
cd /share/home/zixiao/descriptor_analysis/MFM_precision_20261115
export PYTHONDONTWRITEBYTECODE=1
exec python3 -B tools/model_v3/precision_speed_grid.py standby --task "$1"
