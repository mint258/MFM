#!/bin/bash
#SBATCH --job-name=native20000_panel_SDK_audit
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --time=00:10:00
set -euo pipefail
: "${MODEL_V3_PANEL_SOURCE_SHA:?Exact source pins required}"
: "${MODEL_V3_PANEL_INPUTS:?Exact5060 metadata inputs required}"
: "${MODEL_V3_PANEL_INPUTS_SHA:?Input rawSHA required}"
: "${MODEL_V3_PANEL_OUTPUT:?Fresh owned output required}"
: "${MODEL_V3_EXPECTED_NODE:?Actual CPU node required}"
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
p=/share/home/zixiao/descriptor_analysis
s=$p/runs/model_v3_20261026/native_S20000_panel_SDK_sync_v1_source
py=$p/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
exec "$py" -u -B "$p/runs/model_v3_20261025/run_cpu_supervised_v3.py" \
 --output-root "$MODEL_V3_PANEL_OUTPUT" --record "$MODEL_V3_PANEL_OUTPUT.supervisor.json" \
 --wall-seconds 540 --rss-limit-bytes 12884901888 -- \
 "$py" -u -B "$s/audit_panel.py" --inputs "$MODEL_V3_PANEL_INPUTS" --inputs-sha256 "$MODEL_V3_PANEL_INPUTS_SHA" \
 --pins-sha256 "$MODEL_V3_PANEL_SOURCE_SHA" --output "$MODEL_V3_PANEL_OUTPUT"
