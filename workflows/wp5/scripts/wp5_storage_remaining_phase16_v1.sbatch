#!/bin/bash
#SBATCH --job-name=wp5_remaining_storage16_v1
#SBATCH --partition=cpu
#SBATCH --chdir=/share/home/zixiao/descriptor_analysis
#SBATCH --nodes=1
#SBATCH --nodelist=compute-0-17
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/remaining_storage16_v1_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/remaining_storage16_v1_%j.err
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
TASK_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$TASK_ROOT/scripts:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$TASK_ROOT/scripts/wp5_storage_remaining_phase16_v1.py" "$@" --workers 24 --out "$TASK_ROOT/gates/g3/phase16_remaining_storage_job_$SLURM_JOB_ID.json"
