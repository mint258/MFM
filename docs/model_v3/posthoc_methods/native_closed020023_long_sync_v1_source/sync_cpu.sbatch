#!/bin/bash
#SBATCH --job-name=native_closed_long_sync
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=01:00:00
set -euo pipefail
: "${MODEL_V3_LONGSYNC_MANIFEST:?Explicit three manifest required}"
: "${MODEL_V3_LONGSYNC_MANIFEST_SHA:?Manifest SHA required}"
: "${MODEL_V3_LONGSYNC_REQUEST:?Explicit request required}"
: "${MODEL_V3_LONGSYNC_REQUEST_SHA:?Request SHA required}"
: "${MODEL_V3_LONGSYNC_SOURCE_SHA:?Frozen source SHA required}"
: "${MODEL_V3_LONGSYNC_OUTPUT:?Fresh output required}"
: "${MODEL_V3_EXPECTED_NODE:?Actual CPU allocation required}"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PYTEST_ADDOPTS='-o tmp_path_retention_policy=failed'
task_project=/share/home/zixiao/descriptor_analysis
task_source=$task_project/runs/model_v3_20261026/native_closed020023_long_sync_v1_source
task_python=$task_project/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
exec "$task_python" -u -B "$task_project/runs/model_v3_20261025/run_cpu_supervised_v3.py" \
  --output-root "$MODEL_V3_LONGSYNC_OUTPUT" --record "$MODEL_V3_LONGSYNC_OUTPUT.supervisor.json" \
  --wall-seconds 3300 --rss-limit-bytes 12884901888 -- \
  "$task_python" -u -B "$task_source/sync_selected_long.py" --request "$MODEL_V3_LONGSYNC_REQUEST" \
  --request-sha256 "$MODEL_V3_LONGSYNC_REQUEST_SHA" --pins-sha256 "$MODEL_V3_LONGSYNC_SOURCE_SHA" \
  --output "$MODEL_V3_LONGSYNC_OUTPUT"
