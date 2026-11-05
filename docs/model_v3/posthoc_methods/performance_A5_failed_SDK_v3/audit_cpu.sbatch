#!/bin/bash
#SBATCH --job-name=A5_failed_pair_SDK0
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=00:20:00
set -euo pipefail
: "${MODEL_V3_A5_FAILED_SOURCE_SHA:?Frozen failed-log source required}"
: "${MODEL_V3_A5_FAILED_INPUTS:?Two actual failed A5 SDKs required}"
: "${MODEL_V3_A5_FAILED_INPUTS_SHA:?Actual input rawSHA required}"
: "${MODEL_V3_A5_FAILED_OUTPUT:?Fresh output required}"
: "${MODEL_V3_EXPECTED_NODE:?Actual CPU allocation required}"
export WANDB_MODE=offline
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
p=/share/home/zixiao/descriptor_analysis
s=$p/runs/model_v3_20261026/performance_A5_failed_SDK_v3_source
py=$p/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
exec "$py" -u -B "$p/runs/model_v3_20261025/run_cpu_supervised_v3.py" \
 --output-root "$MODEL_V3_A5_FAILED_OUTPUT" --record "$MODEL_V3_A5_FAILED_OUTPUT.supervisor.json" \
 --wall-seconds 900 --rss-limit-bytes 12884901888 -- \
 "$py" -u -B "$s/audit_failed.py" --inputs "$MODEL_V3_A5_FAILED_INPUTS" --inputs-sha256 "$MODEL_V3_A5_FAILED_INPUTS_SHA" \
 --pins-sha256 "$MODEL_V3_A5_FAILED_SOURCE_SHA" --output "$MODEL_V3_A5_FAILED_OUTPUT"
