#!/bin/bash
#SBATCH --job-name=wp5_verify957_diagnostic_v1
#SBATCH --partition=cpu
#SBATCH --chdir=/share/home/zixiao/descriptor_analysis
#SBATCH --nodelist=compute-0-17
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/wp5_verify957_diagnostic_v1_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/wp5_verify957_diagnostic_v1_%j.err
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT/scripts:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps${PYTHONPATH:+:$PYTHONPATH}"
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
timeout --preserve-status --signal=TERM --kill-after=120s 46h "$PY" -B "$ROOT/scripts/wp5_verify957_readonly_diagnostic_v1.py" --out "$ROOT/acceptance/final_20261016_v1/verify957_diagnostic_$SLURM_JOB_ID"
