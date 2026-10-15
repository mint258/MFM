#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/share/home/zixiao/PhyChem_MFM_ICLR2027}"
PYTHON_BIN="${PYTHON_BIN:-/share/home/zixiao/.conda/envs/chemprop/bin/python}"
DISCOVERY_POOL_SIZE="${DISCOVERY_POOL_SIZE:?Set the calibrated fixed unique pool size}"
DESCRIPTOR_SCHEDULE_CANONICAL="${DESCRIPTOR_SCHEDULE_CANONICAL:?Set delayed, joint_ramp, or joint_full}"
MANIFEST_ROOT="${MANIFEST_ROOT:-$PROJECT_ROOT/manifests/discovery_v2}"
REGISTRY="${REGISTRY:-$PROJECT_ROOT/registry/discovery_registry.json}"
RUN_ROOT="${RUN_ROOT:-$PROJECT_ROOT/runs/discovery_v2}"
SOURCE_COMMIT="${PHYCHEM_SOURCE_COMMIT:?PHYCHEM_SOURCE_COMMIT must be the deployed clean commit}"
LIGHT_GPU="${LIGHT_GPU:-0}"
EXPERT_GPU="${EXPERT_GPU:-1}"
HYBRID_G_GPU="${HYBRID_G_GPU:-0}"
HYBRID_QG_GPU="${HYBRID_QG_GPU:-1}"

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"
export PHYCHEM_SOURCE_COMMIT="$SOURCE_COMMIT"
export PHYCHEM_SOURCE_DIRTY=0
export WANDB_SILENT=true

run_candidate() {
  local gpu="$1"
  local route="$2"
  export CUDA_VISIBLE_DEVICES="$gpu"
  "$PYTHON_BIN" scripts/train_discovery.py \
    --train-manifest "$MANIFEST_ROOT/train_${DISCOVERY_POOL_SIZE}.json" \
    --validation-manifest "$MANIFEST_ROOT/validation.json" \
    --task-route "$route" \
    --descriptor-schedule "$DESCRIPTOR_SCHEDULE_CANONICAL" \
    --registry "$REGISTRY" \
    --run-root "$RUN_ROOT" \
    --wandb-mode offline
}

# Light-all and Expert-all are exact registry reuses from timing discovery.
# The calls are intentionally retained: the registry makes them no-op reuses.
run_candidate "$LIGHT_GPU" light
run_candidate "$EXPERT_GPU" expert
if [[ "$HYBRID_G_GPU" == "$HYBRID_QG_GPU" ]]; then
  run_candidate "$HYBRID_G_GPU" hybrid_g
  run_candidate "$HYBRID_QG_GPU" hybrid_qg
else
  run_candidate "$HYBRID_G_GPU" hybrid_g &
  g_pid=$!
  run_candidate "$HYBRID_QG_GPU" hybrid_qg &
  qg_pid=$!
  wait "$g_pid"
  wait "$qg_pid"
fi
