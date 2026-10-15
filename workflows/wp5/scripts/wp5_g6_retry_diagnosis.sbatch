#!/bin/bash
#SBATCH --job-name=wp5_g6_retry_audit
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --nodelist=compute-0-17
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.err
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/docs/deps:/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts:${PYTHONPATH:-}
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
exec /share/home/zixiao/.conda/envs/chemprop/bin/python "$WP5_ROOT/scripts/wp5_g6_retry_diagnosis.py" --workers 24 \
 --source-run "$WP5_ROOT/gates/g6/compute-0-14/job_4513901" \
 --source-run "$WP5_ROOT/gates/g6/compute-0-17/job_4513904" \
 --source-run "$WP5_ROOT/gates/g6/compute-0-18/job_4513905" \
 --source-run "$WP5_ROOT/gates/g6/compute-0-19/job_4513906" \
 --output "$WP5_ROOT/gates/g6_retry_diagnosis/job_${SLURM_JOB_ID}/report.json"
