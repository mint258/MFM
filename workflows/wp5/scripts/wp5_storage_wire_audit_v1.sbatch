#!/bin/bash
#SBATCH --job-name=wp5_wire_audit
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --nodelist=compute-0-17
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.err
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts:${PYTHONPATH:-}
R=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
exec /share/home/zixiao/.conda/envs/chemprop/bin/python "$R/scripts/wp5_storage_wire_audit_v1.py" --workers 24 --output "$R/gates/g3/storage_wire_audit_job_${SLURM_JOB_ID}" --report "$R/gates/g6_recovery/compute-0-14/job_4513918/report.json" --report "$R/gates/g6_recovery/compute-0-17/job_4513921/report.json" --report "$R/gates/g6_recovery/compute-0-18/job_4513922/report.json" --report "$R/gates/g6_recovery/compute-0-19/job_4513923/report.json"
