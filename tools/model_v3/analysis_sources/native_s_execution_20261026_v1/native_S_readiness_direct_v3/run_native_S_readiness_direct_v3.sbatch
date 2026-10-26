#!/bin/bash
#SBATCH --job-name=native_S_readiness_direct
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/native_S_readiness_direct_%j.log
set -euo pipefail
: "${MODEL_V3_EXPECTED_NODE:?Root helper actual CPU node required}"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
task_py=/share/home/zixiao/.conda/envs/chemprop/bin/python
exec "$task_py" -u -B /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_S_readiness_direct_v3/direct_worker.py
