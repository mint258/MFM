#!/bin/bash
#SBATCH --job-name=native028029_closed_log_audit
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --time=00:20:00
set -euo pipefail
: "${MODEL_V3_EXPECTED_NODE:?Actual CPU node}"
: "${MODEL_V3_LONG_LOG_INPUTS:?Explicit closed batch input}"
: "${MODEL_V3_LONG_LOG_INPUTS_SHA:?Raw closed input SHA}"
: "${MODEL_V3_LONG_LOG_PINS_SHA:?Actual source pins SHA}"
: "${MODEL_V3_LONG_LOG_OUTPUT:?Fresh audit output}"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTEST_ADDOPTS='-o tmp_path_retention_policy=failed'
task_py=/share/home/zixiao/.conda/envs/chemprop/bin/python
task_source=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_closed028029_sdk_audit_v1_source
exec "$task_py" -u -B /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/run_cpu_supervised_v3.py \
  --output-root "$MODEL_V3_LONG_LOG_OUTPUT" --record "$MODEL_V3_LONG_LOG_OUTPUT.supervisor.json" \
  --wall-seconds 900 --rss-limit-bytes 12884901888 -- \
  "$task_py" -u -B "$task_source/audit_closed_segments.py" run \
  --inputs "$MODEL_V3_LONG_LOG_INPUTS" --inputs-sha256 "$MODEL_V3_LONG_LOG_INPUTS_SHA" \
  --pins-sha256 "$MODEL_V3_LONG_LOG_PINS_SHA" --expected-node "$MODEL_V3_EXPECTED_NODE" --output "$MODEL_V3_LONG_LOG_OUTPUT"

