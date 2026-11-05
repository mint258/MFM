#!/bin/bash
#SBATCH --job-name=model_v3_WandB_selective_sync
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=16G
#SBATCH --time=01:00:00
set -euo pipefail
: "${MODEL_V3_SYNC_SOURCE_PINS:?Frozen source required}"
: "${MODEL_V3_SYNC_SOURCE_PINS_SHA:?Exact source SHA required}"
: "${MODEL_V3_SYNC_REQUEST:?Explicit one-run or bounded batch request required}"
: "${MODEL_V3_SYNC_REQUEST_SHA:?Request SHA required}"
: "${MODEL_V3_SYNC_OUTPUT:?Fresh output required}"
: "${MODEL_V3_EXPECTED_NODE:?Actual CPU allocation required}"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PYTEST_ADDOPTS='-o tmp_path_retention_policy=failed'
task_project=/share/home/zixiao/descriptor_analysis
task_source=$task_project/runs/model_v3_20261026/wandb_selective_sync50_v3
task_python=$task_project/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
exec "$task_python" -u -B "$task_project/runs/model_v3_20261025/run_cpu_supervised_v3.py" \
  --output-root "$MODEL_V3_SYNC_OUTPUT" --record "$MODEL_V3_SYNC_OUTPUT.supervisor.json" \
  --wall-seconds 3300 --rss-limit-bytes 12884901888 -- \
  "$task_python" -u -B "$task_source/sync_selected.py" --request "$MODEL_V3_SYNC_REQUEST" \
  --request-sha256 "$MODEL_V3_SYNC_REQUEST_SHA" --pins-sha256 "$MODEL_V3_SYNC_SOURCE_PINS_SHA" \
  --output "$MODEL_V3_SYNC_OUTPUT"
