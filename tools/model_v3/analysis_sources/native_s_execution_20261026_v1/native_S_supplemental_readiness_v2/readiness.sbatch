#!/bin/bash
#SBATCH --job-name=native_S_readiness
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=16G
#SBATCH --time=00:30:00
set -euo pipefail
: "${MODEL_V3_READINESS_SOURCE_PINS:?Root source pins required}"
: "${MODEL_V3_READINESS_SOURCE_PINS_SHA:?Root raw source SHA required}"
: "${MODEL_V3_READINESS_REQUEST:?Root actual request required}"
: "${MODEL_V3_READINESS_REQUEST_SHA:?Root actual request SHA required}"
: "${MODEL_V3_EXPECTED_NODE:?Actual CPU node required}"
: "${MODEL_V3_READINESS_OUTPUT:?Fresh output required}"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTEST_ADDOPTS='-o tmp_path_retention_policy=failed'
task_py=/share/home/zixiao/.conda/envs/chemprop/bin/python
task_src=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_S_supplemental_readiness_v2
exec "$task_py" -u -B /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/run_cpu_supervised_v3.py \
  --output-root "$MODEL_V3_READINESS_OUTPUT" --record "$MODEL_V3_READINESS_OUTPUT.supervisor.json" \
  --wall-seconds 1500 --rss-limit-bytes 12884901888 -- \
  "$task_py" -u -B "$task_src/run_readiness.py" \
  --source-pins "$MODEL_V3_READINESS_SOURCE_PINS" --source-pins-sha256 "$MODEL_V3_READINESS_SOURCE_PINS_SHA" \
  --request "$MODEL_V3_READINESS_REQUEST" --request-sha256 "$MODEL_V3_READINESS_REQUEST_SHA" \
  --expected-node "$MODEL_V3_EXPECTED_NODE" --output "$MODEL_V3_READINESS_OUTPUT"
