#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/share/home/zixiao/PhyChem_MFM_ICLR2027}"
PYTHON_BIN="${PYTHON_BIN:-/share/home/zixiao/.conda/envs/chemprop/bin/python}"
DISCOVERY_POOL_SIZE="${DISCOVERY_POOL_SIZE:?Set the calibrated fixed unique pool size}"
MANIFEST_ROOT="${MANIFEST_ROOT:-$PROJECT_ROOT/manifests/discovery_v2}"
REGISTRY="${REGISTRY:-$PROJECT_ROOT/registry/discovery_registry.json}"
RUN_ROOT="${RUN_ROOT:-$PROJECT_ROOT/runs/discovery_v2}"
SOURCE_COMMIT="${PHYCHEM_SOURCE_COMMIT:?PHYCHEM_SOURCE_COMMIT must be the deployed clean commit}"
LIGHT_GPU="${LIGHT_GPU:-0}"
EXPERT_GPU="${EXPERT_GPU:-1}"

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"
export PHYCHEM_SOURCE_COMMIT="$SOURCE_COMMIT"
export PHYCHEM_SOURCE_DIRTY=0
export WANDB_SILENT=true

run_route() {
  local gpu="$1"
  local route="$2"
  local schedule
  export CUDA_VISIBLE_DEVICES="$gpu"
  for schedule in delayed joint_ramp joint_full; do
    "$PYTHON_BIN" scripts/train_discovery.py \
      --train-manifest "$MANIFEST_ROOT/train_${DISCOVERY_POOL_SIZE}.json" \
      --validation-manifest "$MANIFEST_ROOT/validation.json" \
      --task-route "$route" \
      --descriptor-schedule "$schedule" \
      --registry "$REGISTRY" \
      --run-root "$RUN_ROOT" \
      --wandb-mode offline
  done
}

if [[ "$LIGHT_GPU" == "$EXPERT_GPU" ]]; then
  # Sequential mode is required when both routes share one GPU; the Expert
  # 200k peak leaves insufficient headroom for a concurrent Light process.
  run_route "$LIGHT_GPU" light
  run_route "$EXPERT_GPU" expert
else
  run_route "$LIGHT_GPU" light &
  light_pid=$!
  run_route "$EXPERT_GPU" expert &
  expert_pid=$!
  wait "$light_pid"
  wait "$expert_pid"
fi
