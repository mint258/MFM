#!/bin/bash
#SBATCH --job-name=B0-Pprime-standby16
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,20-22]
#SBATCH --cpus-per-task=16
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --no-requeue
#SBATCH --time=24:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B0_pprime_standby_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_data_20261119
data=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119
control=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B -u -m workflows.benchmark_data.pprime_standby \
 --root "$data" --control "$control" --quota-snapshot "$control/benchmark_B0_quota_20261119.json" \
 --previous-job "${B0_PREVIOUS_PPRIME_JOB:-4536581}" --workers "$SLURM_CPUS_PER_TASK"
