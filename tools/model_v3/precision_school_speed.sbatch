#!/bin/bash
#SBATCH --job-name=precision-A800
#SBATCH --partition=gpuA800
#SBATCH --account=a_xk
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=9
#SBATCH --gres=gpu:1
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=/share/home/202264640132/precision_A800_%j.log
set -euo pipefail
school_home=/share/home/202264640132
root="$school_home/precision_20261115"
cd "$root/source"
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$PWD/current"
export TMPDIR="$root/tmp"
gpu=${SLURM_JOB_GPUS:-${CUDA_VISIBLE_DEVICES:?Slurm GPU binding missing}}
gpu=${gpu%%,*}
export CUDA_VISIBLE_DEVICES=$(nvidia-smi -i "$gpu" --query-gpu=uuid --format=csv,noheader)
nvidia-smi -i "$CUDA_VISIBLE_DEVICES" --query-gpu=uuid,name,driver_version,memory.total --format=csv
findmnt -T "$root"
df -B1 / "$root"
df -Pi / "$root"
exec "$root/env/bin/python" -B "$school_home/precision_school_guard.py" -- bash tools/model_v3/precision_school_speed.sh
