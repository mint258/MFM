#!/bin/bash
#SBATCH --job-name=model_v3_equivariance_v2_rejudge
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/equivariance_v2_rejudge_%j.log
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/equivariance_v2_rejudge_%j.log
set -euo pipefail
: "${MODEL_V3_EXPECTED_NODE:?Root actual CPU node}"
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
py=/share/home/zixiao/.conda/envs/chemprop/bin/python
out=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/equivariance_v2_rejudge_actual_v1
exec "$py" -u -B /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/run_cpu_supervised_v3.py --output-root "$out" --record "$out.supervisor.json" --wall-seconds 900 --rss-limit-bytes 12884901888 -- "$py" -u -B /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/equivariance_v2_rejudge_20261029/rejudge.py --request /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/equivariance_v2_rejudge_20261029/request.json --output "$out"