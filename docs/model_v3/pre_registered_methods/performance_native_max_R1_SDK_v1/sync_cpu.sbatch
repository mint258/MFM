#!/bin/bash
#SBATCH --job-name=native_max_single_sync
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=16G
#SBATCH --time=01:00:00
set -euo pipefail
: "${MODEL_V3_MAX_SOURCE_SHA:?Frozen max-log source required}"
: "${MODEL_V3_MAX_MANIFEST:?One certified max SDK manifest required}"
: "${MODEL_V3_MAX_MANIFEST_SHA:?Manifest rawSHA required}"
: "${MODEL_V3_MAX_REQUEST:?Explicit only pnugbb4q required}"
: "${MODEL_V3_MAX_REQUEST_SHA:?Request rawSHA required}"
: "${MODEL_V3_MAX_OUTPUT:?Fresh output required}"
: "${MODEL_V3_EXPECTED_NODE:?Actual CPU allocation required}"
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
p=/share/home/zixiao/descriptor_analysis
s=$p/runs/model_v3_20261026/performance_native_max_R1_SDK_v1_source
py=$p/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
exec "$py" -u -B "$p/runs/model_v3_20261025/run_cpu_supervised_v3.py" \
 --output-root "$MODEL_V3_MAX_OUTPUT" --record "$MODEL_V3_MAX_OUTPUT.supervisor.json" \
 --wall-seconds 3300 --rss-limit-bytes 12884901888 -- \
 "$py" -u -B "$s/sync_max.py" --request "$MODEL_V3_MAX_REQUEST" --request-sha256 "$MODEL_V3_MAX_REQUEST_SHA" \
 --pins-sha256 "$MODEL_V3_MAX_SOURCE_SHA" --output "$MODEL_V3_MAX_OUTPUT"
