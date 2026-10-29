#!/bin/bash
#SBATCH --job-name=Routing7_Av2_R2_two_SDK_audit
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --time=00:20:00
set -euo pipefail
: "${MODEL_V3_PAIRED_SOURCE_SHA:?Frozen paired source required}"
: "${MODEL_V3_PAIRED_INPUTS:?One closed head-off pair/two SDK descriptors required}"
: "${MODEL_V3_PAIRED_INPUTS_SHA:?Actual input rawSHA required}"
: "${MODEL_V3_PAIRED_OUTPUT:?Fresh output required}"
: "${MODEL_V3_EXPECTED_NODE:?Actual CPU allocation required}"
export WANDB_MODE=offline
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
p=/share/home/zixiao/descriptor_analysis
s=$p/runs/model_v3_20261026/performance_routing7_Av2_R2_paired_SDK_v2_source
py=$p/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
exec "$py" -u -B "$p/runs/model_v3_20261025/run_cpu_supervised_v3.py" \
 --output-root "$MODEL_V3_PAIRED_OUTPUT" --record "$MODEL_V3_PAIRED_OUTPUT.supervisor.json" \
 --wall-seconds 900 --rss-limit-bytes 12884901888 -- \
 "$py" -u -B "$s/audit_paired.py" --inputs "$MODEL_V3_PAIRED_INPUTS" --inputs-sha256 "$MODEL_V3_PAIRED_INPUTS_SHA" \
 --pins-sha256 "$MODEL_V3_PAIRED_SOURCE_SHA" --output "$MODEL_V3_PAIRED_OUTPUT"
