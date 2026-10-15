#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

PYTHON_BIN="${PYTHON_BIN:-python}"
GPU_ID="${GPU_ID:-0}"
DATA_ROOT="${DATA_ROOT:-../../../dataset/final_lmdb/principal_valid_test.lmdb}"

TRAIN_START="${TRAIN_START:-875}"
TRAIN_END="${TRAIN_END:-8754}"
VAL_START="${VAL_START:-0}"
VAL_END="${VAL_END:-874}"

NUM_WORKERS="${NUM_WORKERS:-16}"
WANDB_MODE="${WANDB_MODE:-offline}"
WANDB_PROJECT="${WANDB_PROJECT:-mfm-pretrain}"

BASE_ARGS=(
  -m pretrain.pipeline
  --data_roots "${DATA_ROOT}"
  --starts "${TRAIN_START}"
  --ends "${TRAIN_END}"
  --val_data_roots "${DATA_ROOT}"
  --val_starts "${VAL_START}"
  --val_ends "${VAL_END}"
  --num_workers "${NUM_WORKERS}"
  --use_wandb
  --wandb_mode "${WANDB_MODE}"
  --wandb_project "${WANDB_PROJECT}"
  --wandb_watch none
  --wandb_log_batch_every 100
  --bb_heads 4
  --bb_ff_mult 2
  --expert_heads 4
  --expert_ff_mult 2
  --perturb_mode both
  --perturb_level 0.5
  --loss_cutoff 2.0
  --seed 0
)

NODE_KEY="${NODE_KEY:?NODE_KEY is required}"
WANDB_GROUP="${WANDB_GROUP:?WANDB_GROUP is required}"
COMMON_TAGS=("${COMMON_TAGS[@]:-search_smallscale}")

LOG_DIR="${REPO_ROOT}/log/search/${NODE_KEY}"
CKPT_DIR="${REPO_ROOT}/test_ckpt/search/${NODE_KEY}"
WANDB_DIR="${REPO_ROOT}/wandb/search/${NODE_KEY}"
MANIFEST_PATH="${LOG_DIR}/manifest.tsv"

mkdir -p "${LOG_DIR}" "${CKPT_DIR}" "${WANDB_DIR}"

run_exp() {
  local run_name="$1"
  shift

  local save_path="${CKPT_DIR}/${run_name}.pt"
  local log_path="${LOG_DIR}/${run_name}.log"

  {
    if [[ ! -f "${MANIFEST_PATH}" ]]; then
      printf "run_name\tstart_time\tgpu_id\tcommand\n"
    fi
    printf "%s\t%s\t%s\t%s\n" \
      "${run_name}" \
      "$(date '+%Y-%m-%d %H:%M:%S')" \
      "${GPU_ID}" \
      "$*"
  } >> "${MANIFEST_PATH}"

  echo "[$(date '+%Y-%m-%d %H:%M:%S')] START ${run_name}"

  (
    cd "${REPO_ROOT}"
    CUDA_VISIBLE_DEVICES="${GPU_ID}" \
      "${PYTHON_BIN}" "${BASE_ARGS[@]}" \
      --save_path "${save_path}" \
      --wandb_dir "${WANDB_DIR}" \
      --wandb_group "${WANDB_GROUP}" \
      --wandb_run_name "${run_name}" \
      --wandb_tags "${COMMON_TAGS[@]}" "${run_name}" \
      "$@" 2>&1 | tee "${log_path}"
  )

  echo "[$(date '+%Y-%m-%d %H:%M:%S')] END ${run_name}"
}

print_env_banner() {
  echo "repo_root=${REPO_ROOT}"
  echo "python_bin=${PYTHON_BIN}"
  echo "gpu_id=${GPU_ID}"
  echo "data_root=${DATA_ROOT}"
  echo "log_dir=${LOG_DIR}"
  echo "ckpt_dir=${CKPT_DIR}"
  echo "wandb_dir=${WANDB_DIR}"
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi || true
  fi
  "${PYTHON_BIN}" - <<'PY'
import torch
print("torch_version=", torch.__version__)
print("cuda_available=", torch.cuda.is_available())
print("cuda_device_count=", torch.cuda.device_count())
if torch.cuda.is_available():
    print("cuda_device_name=", torch.cuda.get_device_name(0))
PY
}
