#!/bin/bash
#SBATCH --job-name=native_S_SDK_readback
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=16G
#SBATCH --time=00:15:00
set -euo pipefail
: "${MODEL_V3_EXPECTED_NODE:?Root CPU node required}"
: "${MODEL_V3_PROFILE_SDK_PINS_SHA:?Root source pins SHA required}"
: "${MODEL_V3_PROFILE_SDK_FP32_INPUT:?Actual fp32 sdk_verifier call manifest required}"
: "${MODEL_V3_PROFILE_SDK_FP32_SHA:?Actual fp32 call SHA required}"
: "${MODEL_V3_PROFILE_SDK_BF16_INPUT:?Actual bf16 sdk_verifier call manifest required}"
: "${MODEL_V3_PROFILE_SDK_BF16_SHA:?Actual bf16 call SHA required}"
: "${MODEL_V3_PROFILE_SDK_OUTPUT:?Fresh Root output required}"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
task_base=/share/home/zixiao/descriptor_analysis
task_py=/share/home/zixiao/.conda/envs/chemprop/bin/python
task_src=$task_base/runs/model_v3_20261026/native_s_profile_sdk_readback_v4_source
exec "$task_py" -u -B "$task_base/runs/model_v3_20261025/run_cpu_supervised_v3.py" \
  --output-root "$MODEL_V3_PROFILE_SDK_OUTPUT" --record "$MODEL_V3_PROFILE_SDK_OUTPUT.supervisor.json" \
  --wall-seconds 720 --rss-limit-bytes 12884901888 -- \
  "$task_py" -u -B "$task_src/readback_native_profiles.py" \
  --pins-sha256 "$MODEL_V3_PROFILE_SDK_PINS_SHA" --expected-node "$MODEL_V3_EXPECTED_NODE" \
  --input "$MODEL_V3_PROFILE_SDK_FP32_INPUT" --input-sha256 "$MODEL_V3_PROFILE_SDK_FP32_SHA" \
  --input "$MODEL_V3_PROFILE_SDK_BF16_INPUT" --input-sha256 "$MODEL_V3_PROFILE_SDK_BF16_SHA" \
  --output "$MODEL_V3_PROFILE_SDK_OUTPUT"
