#!/bin/bash
#SBATCH --job-name=R2_paired_selective_sync
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=16G
#SBATCH --time=01:00:00
set -euo pipefail
: "${MODEL_V3_PAIRED_SOURCE_SHA:?Frozen paired source required}"
: "${MODEL_V3_PAIRED_MANIFEST:?Both certified head-off SDK manifest required}"
: "${MODEL_V3_PAIRED_MANIFEST_SHA:?Manifest rawSHA required}"
: "${MODEL_V3_PAIRED_REQUEST:?Explicit max3 selected IDs required}"
: "${MODEL_V3_PAIRED_REQUEST_SHA:?Request rawSHA required}"
: "${MODEL_V3_PAIRED_OUTPUT:?Fresh output required}"
: "${MODEL_V3_EXPECTED_NODE:?Actual CPU allocation required}"
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
p=/share/home/zixiao/descriptor_analysis
s=$p/runs/model_v3_20261026/performance_head_off_R2_SDK_v1_source
py=$p/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
exec "$py" -u -B "$p/runs/model_v3_20261025/run_cpu_supervised_v3.py" \
 --output-root "$MODEL_V3_PAIRED_OUTPUT" --record "$MODEL_V3_PAIRED_OUTPUT.supervisor.json" \
 --wall-seconds 3300 --rss-limit-bytes 12884901888 -- \
 "$py" -u -B "$s/sync_paired.py" --request "$MODEL_V3_PAIRED_REQUEST" --request-sha256 "$MODEL_V3_PAIRED_REQUEST_SHA" \
 --pins-sha256 "$MODEL_V3_PAIRED_SOURCE_SHA" --output "$MODEL_V3_PAIRED_OUTPUT"
