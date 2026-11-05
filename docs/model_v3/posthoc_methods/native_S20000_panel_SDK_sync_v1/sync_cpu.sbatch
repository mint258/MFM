#!/bin/bash
#SBATCH --job-name=native20000_panel_selective_sync
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --time=01:00:00
set -euo pipefail
: "${MODEL_V3_PANEL_SOURCE_SHA:?Exact source pins required}"
: "${MODEL_V3_PANEL_MANIFEST:?One explicit certificate manifest required}"
: "${MODEL_V3_PANEL_MANIFEST_SHA:?Manifest rawSHA required}"
: "${MODEL_V3_PANEL_REQUEST:?Exact one-run request required}"
: "${MODEL_V3_PANEL_REQUEST_SHA:?Request rawSHA required}"
: "${MODEL_V3_PANEL_OUTPUT:?Fresh owned output required}"
: "${MODEL_V3_EXPECTED_NODE:?Actual CPU node required}"
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
p=/share/home/zixiao/descriptor_analysis
s=$p/runs/model_v3_20261026/native_S20000_panel_SDK_sync_v1_source
py=$p/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
exec "$py" -u -B "$p/runs/model_v3_20261025/run_cpu_supervised_v3.py" \
 --output-root "$MODEL_V3_PANEL_OUTPUT" --record "$MODEL_V3_PANEL_OUTPUT.supervisor.json" \
 --wall-seconds 3300 --rss-limit-bytes 12884901888 -- \
 "$py" -u -B "$s/sync_panel.py" --request "$MODEL_V3_PANEL_REQUEST" --request-sha256 "$MODEL_V3_PANEL_REQUEST_SHA" \
 --pins-sha256 "$MODEL_V3_PANEL_SOURCE_SHA" --output "$MODEL_V3_PANEL_OUTPUT"
