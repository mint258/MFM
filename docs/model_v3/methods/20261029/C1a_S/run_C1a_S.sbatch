#!/bin/bash
#SBATCH --job-name=model_v3_C1a_S_engineering
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-21
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=02:00:00
set -euo pipefail
: "${MODEL_V3_GPU_UUID:?Root fresh UUID admission required}"
: "${MODEL_V3_OUT:?Root fresh independent output required}"
: "${MODEL_V3_RECORD:?Root fresh disjoint supervisor record required}"
[[ "$MODEL_V3_GPU_UUID" == GPU-c35f2434-9137-9723-1af5-dc69b6295243 ]] || exit 2
B=/share/home/zixiao/descriptor_analysis
W=$B/MFM_model_v3_runtime_integration_v1
PY=$B/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
export CUDA_VISIBLE_DEVICES="$MODEL_V3_GPU_UUID"
export CUBLAS_WORKSPACE_CONFIG=:4096:8
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8
export PYTHONPATH="$W/current:$W/tools/model_v3:$W/workflows/sprime_s/scripts:$B/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
cd "$W"
# Root uses existing fresh CPU/RAM85%/MemAvailable/GPU/foreign/quota/2GiB hold admission.
# One UUID lock is acquired inside the worker; no second outer flock.
exec "$PY" -u -B tools/model_v3/run_supervised.py \
  --output-root "$MODEL_V3_OUT" --record "$MODEL_V3_RECORD" \
  --gpu-uuid "$CUDA_VISIBLE_DEVICES" --wall-seconds 6900 \
  --rss-limit-bytes 60129542144 --output-budget-bytes 2147483648 \
  --private-scratch-root "/tmp/mv3n_${SLURM_JOB_ID}" \
  --private-storage-budget-bytes 2147483648 -- \
  "$PY" -u -B "$B/runs/model_v3_20261026/C1a_S_engineering_20261029/benchmark_C1a_S.py" \
  --output "$MODEL_V3_OUT" --seed 0 --workers 8 --warmup 2 --steps 5
