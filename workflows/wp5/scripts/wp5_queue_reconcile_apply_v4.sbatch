#!/bin/bash
#SBATCH --job-name=wp5_terminal_subset_apply_v4
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --nodelist=compute-0-12
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/terminal_subset_apply_v4_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/terminal_subset_apply_v4_%j.err
set -euo pipefail
TASK_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH="$TASK_ROOT/scripts:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps${PYTHONPATH:+:$PYTHONPATH}"
TASK_PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
"$TASK_PY" "$TASK_ROOT/scripts/wp5_queue_reconcile_v4.py" --mode apply --workers 16 --plan "$TASK_ROOT/reports/terminal_subset_dryrun_v4_job_4514264/plan.json" --expected-plan-sha256 7c3ca934f3b9534c9a11721ff487c073297fe2fe91adf5bb1a3158967dbc43a8 --out "$TASK_ROOT/reports/terminal_subset_apply_v4_job_${SLURM_JOB_ID}"
