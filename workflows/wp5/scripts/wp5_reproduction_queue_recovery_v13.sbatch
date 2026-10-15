#!/bin/bash
#SBATCH --job-name=wp5_R13_package
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/wp5_package13_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/wp5_package13_%j.err
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/wp5_prepare_runtime_freeze_v13.py" --mode package --workers 24 "$@"
