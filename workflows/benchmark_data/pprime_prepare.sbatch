#!/bin/bash
#SBATCH --job-name=B0-Pprime-prepare
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-16
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --time=00:30:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B0_pprime_prepare_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_data_20261119
data=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B -u -m workflows.benchmark_data.pprime_queue prepare \
 --root "$data" --source-producer-job "${B0_GEOMETRY_JOB:?Original geometry producer job is required}" \
 --quota-snapshot /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json
