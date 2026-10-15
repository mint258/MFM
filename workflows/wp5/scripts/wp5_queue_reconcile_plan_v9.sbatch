#!/bin/bash
#SBATCH --job-name=wp5_actual385_mirror_dryrun_v9
#SBATCH --partition=cpu
#SBATCH --chdir=/share/home/zixiao/descriptor_analysis
#SBATCH --nodes=1
#SBATCH --nodelist=compute-0-17
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/actual385_mirror_dryrun_v9_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/actual385_mirror_dryrun_v9_%j.err
set -euo pipefail
TASK_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
cd /share/home/zixiao/descriptor_analysis
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$TASK_ROOT/scripts:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps${PYTHONPATH:+:$PYTHONPATH}"
TASK_PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
# Root supplies actual copy manifest and SHA; mirror exists only on this same node.
"$TASK_PY" "$TASK_ROOT/scripts/wp5_queue_reconcile_v9.py" --mode dry-run --workers 24 "$@" --out "$TASK_ROOT/reports/actual385_mirror_dryrun_v9_job_${SLURM_JOB_ID}"
