#!/bin/bash
#SBATCH --job-name=sconv_inventory21
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-21
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/logs/gpu_inventory21_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export PYTHONDONTWRITEBYTECODE=1
/share/home/zixiao/.conda/envs/chemprop/bin/python -B runs/sprime_s_convergence_20261013/scripts/gpu_inventory.py
