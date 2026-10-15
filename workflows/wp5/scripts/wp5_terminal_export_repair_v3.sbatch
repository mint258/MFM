#!/bin/bash
#SBATCH --job-name=wp5_terminal_export_repair_v3
#SBATCH --nodes=1
#SBATCH --nodelist=compute-0-12
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/terminal_export_repair_v3_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/terminal_export_repair_v3_%j.err
set -euo pipefail
TASK_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$TASK_ROOT/scripts:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps${PYTHONPATH:+:$PYTHONPATH}"
TASK_PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
"$TASK_PY" "$TASK_ROOT/scripts/wp5_terminal_export_repair_v3.py" --workers 16 --metadata-hours 46 --out "$TASK_ROOT/reports/terminal_export_repair_v3_job_${SLURM_JOB_ID}"
