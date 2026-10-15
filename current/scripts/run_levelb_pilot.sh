#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-/share/home/zixiao/.conda/envs/chemprop/bin/python}"
PROJECT_ROOT="${PROJECT_ROOT:-/share/home/zixiao/PhyChem_MFM_ICLR2027}"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"
export WANDB_SILENT=true

COMMON_ARGS=(
  --supervision-variant SPD
  --data-root /share/home/zixiao/dataset/lmdb_new
  --train-limit 4096
  --val-limit 512
  --batch-size 48
  --num-workers 6
  --max-steps 20000
  --validate-every 1000
  --max-val-batches 16
  --wandb-mode offline
)

"$PYTHON_BIN" scripts/train.py \
  --task-route light \
  --run-dir runs/levelB2_light_spd_20000 \
  --run-name levelB2-light-spd-20000 \
  "${COMMON_ARGS[@]}"

"$PYTHON_BIN" scripts/train.py \
  --task-route expert \
  --run-dir runs/levelB2_expert_spd_20000 \
  --run-name levelB2-expert-spd-20000 \
  "${COMMON_ARGS[@]}"
