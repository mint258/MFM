#!/bin/bash
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --job-name=wp5_hb_storage_delta
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/hb_storage_delta_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/hb_storage_delta_%j.err
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=""
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:$WP5_ROOT/scripts:${PYTHONPATH:-}
: "${WP5_QUOTA_PATH:?Root must publish fresh login quota JSON}"
/usr/bin/time -v -o "$WP5_ROOT/logs/hb_storage_delta_${SLURM_JOB_ID}.time.log" \
 /share/home/zixiao/.conda/envs/chemprop/bin/python -B "$WP5_ROOT/scripts/wp5_hb_storage_delta_v1.py" \
 --workers 16 --quota "$WP5_QUOTA_PATH" \
 --output "$WP5_ROOT/gates/g3/HB_delta_job_${SLURM_JOB_ID}.json"
# Same actual50 rows only; paired in-memory Parquet buffers, no QM or raw writes.
