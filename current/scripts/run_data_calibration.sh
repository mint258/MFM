#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/share/home/zixiao/PhyChem_MFM_ICLR2027}"
PYTHON_BIN="${PYTHON_BIN:-/share/home/zixiao/.conda/envs/chemprop/bin/python}"
MANIFEST_ROOT="${MANIFEST_ROOT:-$PROJECT_ROOT/manifests/discovery_v2}"
REGISTRY="${REGISTRY:-$PROJECT_ROOT/registry/discovery_registry.json}"
RUN_ROOT="${RUN_ROOT:-$PROJECT_ROOT/runs/discovery_v2}"
SOURCE_COMMIT="${PHYCHEM_SOURCE_COMMIT:?PHYCHEM_SOURCE_COMMIT must be the deployed clean commit}"

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"
export PHYCHEM_SOURCE_COMMIT="$SOURCE_COMMIT"
export PHYCHEM_SOURCE_DIRTY=0
export WANDB_SILENT=true

run_route() {
  local gpu="$1"
  local route="$2"
  local size
  export CUDA_VISIBLE_DEVICES="$gpu"
  "$PYTHON_BIN" -c 'import torch; free,total=torch.cuda.mem_get_info(); print(f"GPU free={free/2**30:.2f} GiB total={total/2**30:.2f} GiB")'
  for size in 50000 100000 200000 400000; do
    "$PYTHON_BIN" scripts/train_discovery.py \
      --train-manifest "$MANIFEST_ROOT/train_${size}.json" \
      --validation-manifest "$MANIFEST_ROOT/validation.json" \
      --task-route "$route" \
      --descriptor-schedule delayed \
      --registry "$REGISTRY" \
      --run-root "$RUN_ROOT" \
      --wandb-mode offline \
      --stop-after-pass 1
  done
}

run_route 0 light &
light_pid=$!
run_route 1 expert &
expert_pid=$!
wait "$light_pid"
wait "$expert_pid"
