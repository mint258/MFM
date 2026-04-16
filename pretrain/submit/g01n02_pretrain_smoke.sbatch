#!/usr/bin/env bash
# Single-GPU formal pretraining entrypoint.
#
# Recommended submit example on SCUT HPC:
#   cd /share/home/202264640132/MFM
#   sbatch --export=ALL,REPO_ROOT_OVERRIDE=$PWD,SKIP_CONDA=1,PYTHON_BIN=/share/home/202264640132/.conda/envs/torchgpu/bin/python,DATA_ROOTS="./test_data/principal_valid_test.lmdb" pretrain/submit/g01n02_pretrain_smoke.sbatch

#SBATCH --job-name=pretrain-single-formal
#SBATCH --partition=gpuA800
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --gres=gpu:1
#SBATCH --mem=256G
#SBATCH --time=48:00:00
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err

set -euo pipefail

timestamp() {
  date "+%Y-%m-%d %H:%M:%S"
}

section() {
  echo
  echo "========== $* =========="
}

check_required_python_modules() {
  "${PYTHON_BIN}" - <<'PY'
import importlib

mods = ["torch", "torch_geometric", "lmdb", "rdkit", "wandb", "numpy", "sklearn", "tqdm", "periodictable"]
missing = []
for name in mods:
    try:
        importlib.import_module(name)
    except Exception as exc:
        missing.append((name, repr(exc)))

if missing:
    print("required_python_modules_status=missing")
    for name, exc in missing:
        print(f"missing_module={name} error={exc}")
    raise SystemExit(1)

print("required_python_modules_status=ok")
PY
}

run_shell_init_cmd() {
  local cmd="$1"
  local had_errexit=0
  local had_nounset=0
  local status=0

  if [[ "$-" == *e* ]]; then
    had_errexit=1
  fi
  if [[ "$-" == *u* ]]; then
    had_nounset=1
  fi

  set +eu
  eval "${cmd}"
  status=$?

  if [[ ${had_errexit} -eq 1 ]]; then
    set -e
  fi
  if [[ ${had_nounset} -eq 1 ]]; then
    set -u
  fi

  return "${status}"
}

find_repo_root_from() {
  local start_dir="$1"
  local current="${start_dir}"

  while [[ -n "${current}" && "${current}" != "/" ]]; do
    if [[ -d "${current}/pretrain" && -d "${current}/models" && -d "${current}/dataset" ]]; then
      echo "${current}"
      return 0
    fi
    current="$(dirname "${current}")"
  done

  return 1
}

resolve_repo_root() {
  if [[ -n "${REPO_ROOT_OVERRIDE:-}" ]]; then
    echo "${REPO_ROOT_OVERRIDE}"
    return 0
  fi

  if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
    if find_repo_root_from "${SLURM_SUBMIT_DIR}" >/dev/null; then
      find_repo_root_from "${SLURM_SUBMIT_DIR}"
      return 0
    fi
  fi

  if command -v git >/dev/null 2>&1; then
    local git_root
    git_root="$(git -C "${SLURM_SUBMIT_DIR:-$PWD}" rev-parse --show-toplevel 2>/dev/null || true)"
    if [[ -n "${git_root}" ]]; then
      echo "${git_root}"
      return 0
    fi
  fi

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if find_repo_root_from "${script_dir}" >/dev/null; then
    find_repo_root_from "${script_dir}"
    return 0
  fi

  echo "Failed to resolve repo root. Set REPO_ROOT_OVERRIDE=/abs/path/to/MFM_repository when calling sbatch." >&2
  return 1
}

activate_conda_env() {
  if [[ "${SKIP_CONDA:-0}" == "1" ]]; then
    return 0
  fi

  export LANG="${LANG:-C.UTF-8}"
  export LC_ALL="${LC_ALL:-}"

  if [[ -n "${MODULE_LOAD_CMD:-}" ]]; then
    if ! run_shell_init_cmd "${MODULE_LOAD_CMD}"; then
      echo "[$(timestamp)] ERROR: failed to execute MODULE_LOAD_CMD=${MODULE_LOAD_CMD}"
      exit 1
    fi
  fi

  if [[ -n "${CONDA_ACTIVATE_CMD:-}" ]]; then
    if ! run_shell_init_cmd "${CONDA_ACTIVATE_CMD}"; then
      echo "[$(timestamp)] ERROR: failed to execute CONDA_ACTIVATE_CMD=${CONDA_ACTIVATE_CMD}"
      exit 1
    fi
    return 0
  fi

  if command -v conda >/dev/null 2>&1; then
    if ! run_shell_init_cmd "$(conda shell.bash hook)"; then
      echo "[$(timestamp)] ERROR: failed to initialize conda shell hook"
      exit 1
    fi
  elif [[ -f "${HOME}/miniconda3/etc/profile.d/conda.sh" ]]; then
    source "${HOME}/miniconda3/etc/profile.d/conda.sh"
  elif [[ -f "${HOME}/anaconda3/etc/profile.d/conda.sh" ]]; then
    source "${HOME}/anaconda3/etc/profile.d/conda.sh"
  else
    echo "[$(timestamp)] ERROR: conda was not found. Set SKIP_CONDA=1 if PYTHON_BIN is already correct."
    exit 1
  fi

  conda activate "${CONDA_ENV_NAME}"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(resolve_repo_root)"

CONDA_ENV_NAME="${CONDA_ENV_NAME:-torchgpu}"
PYTHON_BIN="${PYTHON_BIN:-python}"
MODULE_LOAD_CMD="${MODULE_LOAD_CMD:-}"
CONDA_ACTIVATE_CMD="${CONDA_ACTIVATE_CMD:-}"

RUN_TAG="${RUN_TAG:-single_gpu_formal_pretrain_${SLURM_JOB_ID:-manual}}"
RUN_DIR="${RUN_DIR:-${REPO_ROOT}/log/formal_pretrain/${RUN_TAG}}"
CKPT_DIR="${CKPT_DIR:-${RUN_DIR}/checkpoints}"
BEST_CKPT="${BEST_CKPT:-${CKPT_DIR}/best.pt}"
WANDB_DIR="${WANDB_DIR:-${RUN_DIR}/wandb}"

mkdir -p "${RUN_DIR}" "${CKPT_DIR}" "${WANDB_DIR}"
exec > >(tee -a "${RUN_DIR}/job.log") 2>&1

section "Job Context"
echo "[$(timestamp)] repo_root=${REPO_ROOT}"
echo "[$(timestamp)] run_dir=${RUN_DIR}"
echo "[$(timestamp)] ckpt_dir=${CKPT_DIR}"
echo "[$(timestamp)] wandb_dir=${WANDB_DIR}"
echo "[$(timestamp)] slurm_job_id=${SLURM_JOB_ID:-N/A}"
echo "[$(timestamp)] hostname=$(hostname)"
echo "[$(timestamp)] submit_dir=${SLURM_SUBMIT_DIR:-N/A}"
echo "[$(timestamp)] workdir_before_cd=$(pwd)"
echo "[$(timestamp)] script_dir=${SCRIPT_DIR}"
echo "[$(timestamp)] repo_root_override=${REPO_ROOT_OVERRIDE:-<none>}"

cd "${REPO_ROOT}"
activate_conda_env

export PYTHONUNBUFFERED=1
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export WANDB_MODE="${WANDB_MODE:-offline}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"

section "User Config"
DATA_DIR="${DATA_DIR:-${REPO_ROOT}/test_data}"
DATA_ROOT="${DATA_ROOT:-}"
DATA_ROOTS="${DATA_ROOTS:-}"
VAL_DATA_ROOTS="${VAL_DATA_ROOTS:-}"
if [[ -z "${DATA_ROOTS}" && -z "${DATA_ROOT}" ]]; then
  DATA_ROOTS="${DATA_DIR}/principal_valid_test.lmdb"
fi
if [[ -z "${DATA_ROOTS}" && -n "${DATA_ROOT}" ]]; then
  DATA_ROOTS="${DATA_ROOT}"
fi
RUN_ENV_SMOKE="${RUN_ENV_SMOKE:-0}"

STARTS_RAW="${STARTS:-}"
ENDS_RAW="${ENDS:-}"
VAL_STARTS_RAW="${VAL_STARTS:-}"
VAL_ENDS_RAW="${VAL_ENDS:-}"

EPOCHS="${EPOCHS:-80}"
LR="${LR:-3e-4}"
WARMUP_PCT="${WARMUP_PCT:-0.06}"
SEED="${SEED:-0}"
BATCH_SIZE="${BATCH_SIZE:-32}"
NUM_WORKERS="${NUM_WORKERS:-16}"

MODEL_HIDDEN="${MODEL_HIDDEN:-128}"
MODEL_BB_LAYERS="${MODEL_BB_LAYERS:-4}"
MODEL_EXPERT_REAL_LAYERS="${MODEL_EXPERT_REAL_LAYERS:-2}"
MODEL_BB_HEADS="${MODEL_BB_HEADS:-4}"
MODEL_BB_FF_MULT="${MODEL_BB_FF_MULT:-4}"
BB_RADIUS="${BB_RADIUS:-8.0}"
MODEL_EXPERT_HEADS="${MODEL_EXPERT_HEADS:-4}"
MODEL_EXPERT_FF_MULT="${MODEL_EXPERT_FF_MULT:-2}"
MODEL_EXPERT_E="${MODEL_EXPERT_E:-1}"
MODEL_EXPERT_Q="${MODEL_EXPERT_Q:-1}"
MODEL_EXPERT_Z="${MODEL_EXPERT_Z:-1}"
MODEL_EXPERT_G="${MODEL_EXPERT_G:-1}"
MODEL_TOPK_E="${MODEL_TOPK_E:-1}"
MODEL_TOPK_Q="${MODEL_TOPK_Q:-1}"
MODEL_TOPK_Z="${MODEL_TOPK_Z:-1}"
MODEL_TOPK_G="${MODEL_TOPK_G:-1}"

LAMBDA_E="${LAMBDA_E:-1.0}"
LAMBDA_E_DESC="${LAMBDA_E_DESC:-0.5}"
LAMBDA_Q="${LAMBDA_Q:-1.0}"
LAMBDA_Q_DESC="${LAMBDA_Q_DESC:-0.5}"
LAMBDA_Z="${LAMBDA_Z:-1.0}"
LAMBDA_Z_DESC="${LAMBDA_Z_DESC:-0.5}"
LAMBDA_COORD="${LAMBDA_COORD:-0.0}"
LAMBDA_DIST="${LAMBDA_DIST:-1.0}"
LAMBDA_ANGLE="${LAMBDA_ANGLE:-1.0}"
LAMBDA_TORSION="${LAMBDA_TORSION:-2.0}"
LAMBDA_PLANAR="${LAMBDA_PLANAR:-0.0}"

STAGE1_LOSS="${STAGE1_LOSS:-0.3}"
STAGE2_LOSS="${STAGE2_LOSS:-0.1}"
STAGE1_MAX_EPOCHS="${STAGE1_MAX_EPOCHS:-10}"
LOSS_CUTOFF="${LOSS_CUTOFF:-2.0}"
MORSE_A="${MORSE_A:-1.0}"
PERTURB_MODE="${PERTURB_MODE:-both}"
PERTURB_LEVEL="${PERTURB_LEVEL:-0.5}"
PERTURB_MIX="${PERTURB_MIX:-none}"
PERTURB_SEED="${PERTURB_SEED:-114}"

SAVE_EVERY_EPOCH="${SAVE_EVERY_EPOCH:-0}"
USE_WANDB="${USE_WANDB:-1}"
WANDB_MODE="${WANDB_MODE:-offline}"
WANDB_PROJECT="${WANDB_PROJECT:-mfm-pretrain}"
WANDB_GROUP="${WANDB_GROUP:-single_gpu_formal}"
WANDB_RUN_NAME="${WANDB_RUN_NAME:-${RUN_TAG}}"
WANDB_WATCH="${WANDB_WATCH:-none}"
WANDB_LOG_BATCH_EVERY="${WANDB_LOG_BATCH_EVERY:-100}"

normalize_lmdb_path() {
  local raw_path="$1"
  if [[ -z "${raw_path}" ]]; then
    return 1
  fi
  if [[ "${raw_path}" == /* || "${raw_path}" == ./* || "${raw_path}" == ../* ]]; then
    printf '%s\n' "${raw_path}"
    return 0
  fi
  printf '%s\n' "${DATA_DIR}/${raw_path}"
}

normalize_root_list() {
  local raw_list="$1"
  local normalized=()
  local raw_root
  if [[ -z "${raw_list}" ]]; then
    printf '\n'
    return 0
  fi
  for raw_root in ${raw_list}; do
    normalized+=("$(normalize_lmdb_path "${raw_root}")")
  done
  printf '%s\n' "${normalized[*]}"
}

DATA_ROOTS="$(normalize_root_list "${DATA_ROOTS}")"
VAL_DATA_ROOTS="$(normalize_root_list "${VAL_DATA_ROOTS}")"

NORMALIZED_DATA_ROOTS=()
if [[ -n "${DATA_ROOTS}" ]]; then
  for raw_root in ${DATA_ROOTS}; do
    normalized_root="$(normalize_lmdb_path "${raw_root}")"
    NORMALIZED_DATA_ROOTS+=("${normalized_root}")
  done
fi

if [[ -n "${DATA_ROOT}" ]]; then
  DATA_ROOT="$(normalize_lmdb_path "${DATA_ROOT}")"
fi

if [[ -z "${DATA_ROOT}" && ${#NORMALIZED_DATA_ROOTS[@]} -gt 0 ]]; then
  DATA_ROOT="${NORMALIZED_DATA_ROOTS[0]}"
fi

if [[ ${#NORMALIZED_DATA_ROOTS[@]} -eq 0 && -n "${DATA_ROOT}" ]]; then
  NORMALIZED_DATA_ROOTS=("${DATA_ROOT}")
fi

if [[ ${#NORMALIZED_DATA_ROOTS[@]} -gt 0 ]]; then
  DATA_ROOTS="${NORMALIZED_DATA_ROOTS[*]}"
fi

VAL_DATA_ROOT_ARR=()
if [[ -n "${VAL_DATA_ROOTS}" ]]; then
  for raw_root in ${VAL_DATA_ROOTS}; do
    VAL_DATA_ROOT_ARR+=("${raw_root}")
  done
fi

read -r -a DATA_ROOT_ARR <<< "${DATA_ROOTS}"

START_ARR=()
if [[ -z "${STARTS_RAW}" ]]; then
  for _ in "${DATA_ROOT_ARR[@]}"; do
    START_ARR+=(0)
  done
else
  read -r -a START_ARR <<< "${STARTS_RAW}"
fi

END_ARR=()
if [[ -z "${ENDS_RAW}" ]]; then
  for _ in "${DATA_ROOT_ARR[@]}"; do
    END_ARR+=(-1)
  done
else
  read -r -a END_ARR <<< "${ENDS_RAW}"
fi

VAL_START_ARR=()
if [[ -z "${VAL_STARTS_RAW}" ]]; then
  for _ in "${VAL_DATA_ROOT_ARR[@]}"; do
    VAL_START_ARR+=(0)
  done
else
  read -r -a VAL_START_ARR <<< "${VAL_STARTS_RAW}"
fi

VAL_END_ARR=()
if [[ -z "${VAL_ENDS_RAW}" ]]; then
  for _ in "${VAL_DATA_ROOT_ARR[@]}"; do
    VAL_END_ARR+=(-1)
  done
else
  read -r -a VAL_END_ARR <<< "${VAL_ENDS_RAW}"
fi

echo "[$(timestamp)] conda_env_name=${CONDA_ENV_NAME}"
echo "[$(timestamp)] python_bin=${PYTHON_BIN}"
echo "[$(timestamp)] module_load_cmd=${MODULE_LOAD_CMD:-<none>}"
echo "[$(timestamp)] conda_activate_cmd=${CONDA_ACTIVATE_CMD:-<none>}"
echo "[$(timestamp)] conda_default_env=${CONDA_DEFAULT_ENV:-<unset>}"
echo "[$(timestamp)] conda_prefix=${CONDA_PREFIX:-<unset>}"
echo "[$(timestamp)] data_root=${DATA_ROOT}"
echo "[$(timestamp)] data_roots=${DATA_ROOTS}"
echo "[$(timestamp)] val_data_roots=${VAL_DATA_ROOTS:-<none>}"
echo "[$(timestamp)] run_env_smoke=${RUN_ENV_SMOKE}"
echo "[$(timestamp)] starts=${START_ARR[*]}"
echo "[$(timestamp)] ends=${END_ARR[*]}"
echo "[$(timestamp)] val_starts=${VAL_START_ARR[*]:-<none>}"
echo "[$(timestamp)] val_ends=${VAL_END_ARR[*]:-<none>}"
echo "[$(timestamp)] epochs=${EPOCHS}"
echo "[$(timestamp)] lr=${LR}"
echo "[$(timestamp)] warmup_pct=${WARMUP_PCT}"
echo "[$(timestamp)] seed=${SEED}"
echo "[$(timestamp)] batch_size=${BATCH_SIZE}"
echo "[$(timestamp)] num_workers=${NUM_WORKERS}"
echo "[$(timestamp)] model_hidden=${MODEL_HIDDEN}"
echo "[$(timestamp)] model_bb_layers=${MODEL_BB_LAYERS}"
echo "[$(timestamp)] bb_radius=${BB_RADIUS}"
echo "[$(timestamp)] model_expert_real_layers=${MODEL_EXPERT_REAL_LAYERS}"
echo "[$(timestamp)] model_experts=${MODEL_EXPERT_E},${MODEL_EXPERT_Q},${MODEL_EXPERT_Z},${MODEL_EXPERT_G}"
echo "[$(timestamp)] model_topk=${MODEL_TOPK_E},${MODEL_TOPK_Q},${MODEL_TOPK_Z},${MODEL_TOPK_G}"
echo "[$(timestamp)] stage1_loss=${STAGE1_LOSS}"
echo "[$(timestamp)] stage2_loss=${STAGE2_LOSS}"
echo "[$(timestamp)] stage1_max_epochs=${STAGE1_MAX_EPOCHS}"
echo "[$(timestamp)] morse_a=${MORSE_A}"
echo "[$(timestamp)] perturb_mode=${PERTURB_MODE}"
echo "[$(timestamp)] perturb_level=${PERTURB_LEVEL}"
echo "[$(timestamp)] perturb_mix=${PERTURB_MIX}"
echo "[$(timestamp)] perturb_seed=${PERTURB_SEED}"
echo "[$(timestamp)] lambda_coord=${LAMBDA_COORD}"
echo "[$(timestamp)] lambda_planar=${LAMBDA_PLANAR}"
echo "[$(timestamp)] save_every_epoch=${SAVE_EVERY_EPOCH}"
echo "[$(timestamp)] best_ckpt=${BEST_CKPT}"
echo "[$(timestamp)] use_wandb=${USE_WANDB}"
echo "[$(timestamp)] wandb_mode=${WANDB_MODE}"
echo "[$(timestamp)] wandb_group=${WANDB_GROUP}"
echo "[$(timestamp)] wandb_run_name=${WANDB_RUN_NAME}"

if [[ -z "${DATA_ROOT}" ]]; then
  echo "[$(timestamp)] ERROR: no LMDB path resolved. Set DATA_ROOTS or DATA_ROOT."
  exit 1
fi

if [[ "${#DATA_ROOT_ARR[@]}" -ne "${#START_ARR[@]}" || "${#DATA_ROOT_ARR[@]}" -ne "${#END_ARR[@]}" ]]; then
  echo "[$(timestamp)] ERROR: DATA_ROOTS, STARTS, and ENDS must have the same number of entries."
  echo "[$(timestamp)] counts data_roots=${#DATA_ROOT_ARR[@]} starts=${#START_ARR[@]} ends=${#END_ARR[@]}"
  exit 1
fi

if [[ "${#VAL_DATA_ROOT_ARR[@]}" -ne "${#VAL_START_ARR[@]}" || "${#VAL_DATA_ROOT_ARR[@]}" -ne "${#VAL_END_ARR[@]}" ]]; then
  echo "[$(timestamp)] ERROR: VAL_DATA_ROOTS, VAL_STARTS, and VAL_ENDS must have the same number of entries."
  echo "[$(timestamp)] counts val_data_roots=${#VAL_DATA_ROOT_ARR[@]} val_starts=${#VAL_START_ARR[@]} val_ends=${#VAL_END_ARR[@]}"
  exit 1
fi

for root in "${NORMALIZED_DATA_ROOTS[@]}"; do
  if [[ ! -f "${root}" ]]; then
    echo "[$(timestamp)] ERROR: LMDB path does not exist or is not a file: ${root}"
    exit 1
  fi
done

for root in "${VAL_DATA_ROOT_ARR[@]}"; do
  if [[ ! -f "${root}" ]]; then
    echo "[$(timestamp)] ERROR: validation LMDB path does not exist or is not a file: ${root}"
    exit 1
  fi
done

for train_root in "${NORMALIZED_DATA_ROOTS[@]}"; do
  for val_root in "${VAL_DATA_ROOT_ARR[@]}"; do
    if [[ "${train_root}" == "${val_root}" ]]; then
      echo "[$(timestamp)] ERROR: train and validation LMDB paths must be different in single-process mode: ${train_root}"
      exit 1
    fi
  done
done

section "Slurm And System"
scontrol show job "${SLURM_JOB_ID}" || true
scontrol show node "${SLURMD_NODENAME:-$(hostname)}" || true
ulimit -a || true

section "GPU Topology"
nvidia-smi -L || true
nvidia-smi topo -m || true
nvidia-smi || true
echo "[$(timestamp)] CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-unset}"

section "Python Environment"
which "${PYTHON_BIN}"
"${PYTHON_BIN}" --version
"${PYTHON_BIN}" - <<'PY'
import importlib
import platform
import sys

mods = ["torch", "torch_geometric", "lmdb", "rdkit", "wandb", "numpy", "sklearn", "tqdm", "periodictable"]
print("python_executable=", sys.executable)
print("python_version=", sys.version.replace("\n", " "))
print("platform=", platform.platform())
for name in mods:
    try:
        module = importlib.import_module(name)
        print(f"{name}_version=", getattr(module, "__version__", "unknown"))
    except Exception as exc:
        print(f"{name}_import_error=", repr(exc))
PY

if ! check_required_python_modules; then
  section "Dependency Failure"
  echo "[$(timestamp)] ERROR: current Python environment is missing required pretraining dependencies."
  exit 1
fi

section "CUDA Sanity"
"${PYTHON_BIN}" - <<'PY'
import torch

print("torch_version=", torch.__version__)
print("cuda_available=", torch.cuda.is_available())
print("cuda_device_count=", torch.cuda.device_count())
for idx in range(torch.cuda.device_count()):
    props = torch.cuda.get_device_properties(idx)
    print(
        f"gpu[{idx}] name={props.name} total_memory_gb={props.total_memory / (1024 ** 3):.2f} "
        f"sm_count={props.multi_processor_count}"
    )
PY

if [[ "${RUN_ENV_SMOKE}" == "1" ]]; then
  section "Phase 1: Repo Env Smoke"
  ENV_SMOKE_START="${ENV_SMOKE_START:-${START_ARR[0]}}"
  ENV_SMOKE_END="${ENV_SMOKE_END:-$(( ENV_SMOKE_START + 3 ))}"
  CUDA_VISIBLE_DEVICES=0 "${PYTHON_BIN}" pretrain/submit/env_smoke_check.py \
    --data-root "${DATA_ROOT}" \
    --train-start "${ENV_SMOKE_START}" \
    --train-end "${ENV_SMOKE_END}" \
    --batch-size 2 \
    --device auto
fi

section "Formal Training"
TRAIN_CMD=(
  "${PYTHON_BIN}"
  -m pretrain.pipeline
  --data_roots "${DATA_ROOT_ARR[@]}"
  --starts "${START_ARR[@]}"
  --ends "${END_ARR[@]}"
  --epochs "${EPOCHS}"
  --batch_size "${BATCH_SIZE}"
  --num_workers "${NUM_WORKERS}"
  --hidden_channels "${MODEL_HIDDEN}"
  --bb_layers "${MODEL_BB_LAYERS}"
  --bb_heads "${MODEL_BB_HEADS}"
  --bb_ff_mult "${MODEL_BB_FF_MULT}"
  --bb_radius "${BB_RADIUS}"
  --expert_number_E "${MODEL_EXPERT_E}"
  --expert_number_Q "${MODEL_EXPERT_Q}"
  --expert_number_Z "${MODEL_EXPERT_Z}"
  --expert_number_G "${MODEL_EXPERT_G}"
  --topkE "${MODEL_TOPK_E}"
  --topkQ "${MODEL_TOPK_Q}"
  --topkZ "${MODEL_TOPK_Z}"
  --topkG "${MODEL_TOPK_G}"
  --expert_real_layers "${MODEL_EXPERT_REAL_LAYERS}"
  --expert_int_layers 0
  --expert_heads "${MODEL_EXPERT_HEADS}"
  --expert_ff_mult "${MODEL_EXPERT_FF_MULT}"
  --lr "${LR}"
  --warmup_pct "${WARMUP_PCT}"
  --seed "${SEED}"
  --lambda_e "${LAMBDA_E}"
  --lambda_e_desc "${LAMBDA_E_DESC}"
  --lambda_q "${LAMBDA_Q}"
  --lambda_q_desc "${LAMBDA_Q_DESC}"
  --lambda_z "${LAMBDA_Z}"
  --lambda_z_desc "${LAMBDA_Z_DESC}"
  --lambda_coord "${LAMBDA_COORD}"
  --lambda_dist "${LAMBDA_DIST}"
  --lambda_angle "${LAMBDA_ANGLE}"
  --lambda_torsion "${LAMBDA_TORSION}"
  --lambda_planar "${LAMBDA_PLANAR}"
  --stage1_loss "${STAGE1_LOSS}"
  --stage2_loss "${STAGE2_LOSS}"
  --stage1_max_epochs "${STAGE1_MAX_EPOCHS}"
  --loss_cutoff "${LOSS_CUTOFF}"
  --morse_a "${MORSE_A}"
  --perturb_mix "${PERTURB_MIX}"
  --perturb_mode "${PERTURB_MODE}"
  --perturb_level "${PERTURB_LEVEL}"
  --perturb_seed "${PERTURB_SEED}"
  --save_path "${BEST_CKPT}"
  --wandb_dir "${WANDB_DIR}"
  --wandb_log_batch_every "${WANDB_LOG_BATCH_EVERY}"
)

if [[ "${#VAL_DATA_ROOT_ARR[@]}" -gt 0 ]]; then
  TRAIN_CMD+=(
    --val_data_roots "${VAL_DATA_ROOT_ARR[@]}"
    --val_starts "${VAL_START_ARR[@]}"
    --val_ends "${VAL_END_ARR[@]}"
  )
fi

if [[ "${SAVE_EVERY_EPOCH}" == "1" ]]; then
  TRAIN_CMD+=(--save_every_epoch)
fi

if [[ "${USE_WANDB}" == "1" ]]; then
  TRAIN_CMD+=(
    --use_wandb
    --wandb_mode "${WANDB_MODE}"
    --wandb_project "${WANDB_PROJECT}"
    --wandb_group "${WANDB_GROUP}"
    --wandb_run_name "${WANDB_RUN_NAME}"
    --wandb_watch "${WANDB_WATCH}"
  )
else
  TRAIN_CMD+=(--wandb_mode disabled)
fi

printf ' %q' "${TRAIN_CMD[@]}"
echo
"${TRAIN_CMD[@]}"

section "Finished"
echo "[$(timestamp)] Completed successfully."
echo "[$(timestamp)] Logs: ${RUN_DIR}"
echo "[$(timestamp)] Checkpoints: ${CKPT_DIR}"
echo "[$(timestamp)] Best checkpoint: ${BEST_CKPT}"
echo "[$(timestamp)] W&B dir: ${WANDB_DIR}"
