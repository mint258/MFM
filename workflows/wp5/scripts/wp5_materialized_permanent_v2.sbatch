#!/bin/bash
#SBATCH --job-name=wp5_permanent_bytes_v2
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --nodelist=compute-0-13
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=4G
#SBATCH --time=00:15:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/permanent_bytes_v2_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/permanent_bytes_v2_%j.err
set -euo pipefail
TASK_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$TASK_ROOT/scripts/wp5_collect_materialized_permanent_v2.py" --workers 16 --output "$TASK_ROOT/reports/formal_materialized_permanent_bytes_v2_job_${SLURM_JOB_ID}.json"
