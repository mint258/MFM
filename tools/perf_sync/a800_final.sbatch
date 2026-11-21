#!/bin/bash
#SBATCH --job-name=perf-final-A800
#SBATCH --partition=gpuA800
#SBATCH --account=a_xk
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=9
#SBATCH --gres=gpu:1
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --output=/share/home/202264640132/perf_A800_20261120_%j.log
set -euo pipefail
task_root=/share/home/202264640132/perf_A800_20261120
cd "$task_root/source"
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$PWD/current:$PWD/tools/perf_sync"
export TMPDIR="$task_root/tmp" XDG_CACHE_HOME="$task_root/cache"
export TORCHINDUCTOR_CACHE_DIR="$task_root/inductor" TRITON_CACHE_DIR="$task_root/triton"
export NVIDIA_TF32_OVERRIDE=0
unset TORCH_ALLOW_TF32_CUBLAS_OVERRIDE
findmnt -T "$task_root"
df -B1 / "$task_root"
df -Pi / "$task_root"
exec /share/home/202264640132/precision_20261115/env/bin/python -B -u tools/perf_sync/a800_final.py
