#!/usr/bin/env bash
# Single-GPU sbatch entrypoint for MFM_version1/pretrain_multitask.py.
#
# Recommended submit example on SCUT HPC:
#   cd /share/home/202264640132/MFM_repository
#   sbatch --export=ALL,REPO_ROOT_OVERRIDE=$PWD,SKIP_CONDA=1,PYTHON_BIN=/share/home/202264640132/.conda/envs/torchgpu/bin/python MFM_version1/g01n02_pretrain_multitask.sbatch

#SBATCH --job-name=mfm-v1-pretrain
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

mods = [
    "torch",
    "torch_geometric",
    "torch_cluster",
    "lmdb",
    "rdkit",
    "numpy",
    "sklearn",
    "tqdm",
    "periodictable",
]
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
    if [[ -d "${current}/MFM_version1" ]]; then
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
    if [[ -n "${git_root}" && -d "${git_root}/MFM_version1" ]]; then
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
VERSION_ROOT="${MFM_VERSION1_ROOT_OVERRIDE:-${REPO_ROOT}/MFM_version1}"

if [[ ! -f "${VERSION_ROOT}/pretrain_multitask.py" ]]; then
  echo "Resolved VERSION_ROOT does not contain pretrain_multitask.py: ${VERSION_ROOT}" >&2
  exit 1
fi

CONDA_ENV_NAME="${CONDA_ENV_NAME:-torchgpu}"
PYTHON_BIN="${PYTHON_BIN:-python}"
MODULE_LOAD_CMD="${MODULE_LOAD_CMD:-}"
CONDA_ACTIVATE_CMD="${CONDA_ACTIVATE_CMD:-}"

LOG_PATH="${LOG_PATH:-${VERSION_ROOT}/train_real_only_dim128.log}"
mkdir -p "$(dirname "${LOG_PATH}")"
exec > >(tee -a "${LOG_PATH}") 2>&1

section "Job Context"
echo "[$(timestamp)] repo_root=${REPO_ROOT}"
echo "[$(timestamp)] version_root=${VERSION_ROOT}"
echo "[$(timestamp)] log_path=${LOG_PATH}"
echo "[$(timestamp)] slurm_job_id=${SLURM_JOB_ID:-N/A}"
echo "[$(timestamp)] hostname=$(hostname)"
echo "[$(timestamp)] submit_dir=${SLURM_SUBMIT_DIR:-N/A}"
echo "[$(timestamp)] workdir_before_cd=$(pwd)"
echo "[$(timestamp)] script_dir=${SCRIPT_DIR}"
echo "[$(timestamp)] repo_root_override=${REPO_ROOT_OVERRIDE:-<none>}"
echo "[$(timestamp)] version_root_override=${MFM_VERSION1_ROOT_OVERRIDE:-<none>}"

cd "${VERSION_ROOT}"
activate_conda_env

export PYTHONUNBUFFERED=1
export PYTHONPATH="${VERSION_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"

section "User Config"
DATA_ROOTS="${DATA_ROOTS:-../../../dataset/lmdb_new/unimol_01000001_02000000.augmented.lmdb ../../../dataset/lmdb_new/principal_00000001_00300000.augmented.lmdb}"
VAL_DATA_ROOTS="${VAL_DATA_ROOTS:-}"
STARTS_RAW="${STARTS:-}"
ENDS_RAW="${ENDS:-}"
VAL_STARTS_RAW="${VAL_STARTS:-}"
VAL_ENDS_RAW="${VAL_ENDS:-}"

BATCH_SIZE="${BATCH_SIZE:-4}"
STAGE1_MAX_EPOCHS="${STAGE1_MAX_EPOCHS:-2}"
STAGE2_LOSS="${STAGE2_LOSS:-0.01}"
MORSE_A="${MORSE_A:-0.6}"
LAMBDA_DIST="${LAMBDA_DIST:-1}"
LAMBDA_COORD="${LAMBDA_COORD:-0}"
LAMBDA_ANGLE="${LAMBDA_ANGLE:-2}"
LAMBDA_TORSION="${LAMBDA_TORSION:-4}"
LAMBDA_PLANAR="${LAMBDA_PLANAR:-0}"
LAMBDA_E="${LAMBDA_E:-5}"
LAMBDA_Q="${LAMBDA_Q:-1}"
LAMBDA_Z="${LAMBDA_Z:-0.01}"
LOSS_CUTOFF="${LOSS_CUTOFF:-2}"
MODEL_EXPERT_E="${MODEL_EXPERT_E:-1}"
MODEL_EXPERT_Q="${MODEL_EXPERT_Q:-1}"
MODEL_EXPERT_Z="${MODEL_EXPERT_Z:-1}"
MODEL_EXPERT_G="${MODEL_EXPERT_G:-1}"
MODEL_HIDDEN="${MODEL_HIDDEN:-128}"
MODEL_BB_LAYERS="${MODEL_BB_LAYERS:-4}"
MODEL_BB_HEADS="${MODEL_BB_HEADS:-4}"
MODEL_BB_FF_MULT="${MODEL_BB_FF_MULT:-4}"
BB_RADIUS="${BB_RADIUS:-8.0}"
MODEL_EXPERT_REAL_LAYERS="${MODEL_EXPERT_REAL_LAYERS:-2}"
MODEL_EXPERT_INT_LAYERS="${MODEL_EXPERT_INT_LAYERS:-0}"
MODEL_EXPERT_HEADS="${MODEL_EXPERT_HEADS:-4}"
MODEL_EXPERT_FF_MULT="${MODEL_EXPERT_FF_MULT:-2}"
SAVE_PATH="${SAVE_PATH:-test_ckpt/real_only_dim128/AE_test.pth}"
EPOCHS="${EPOCHS:-10}"
SAVE_EVERY_EPOCH="${SAVE_EVERY_EPOCH:-1}"
NUM_WORKERS="${NUM_WORKERS:-0}"
LR="${LR:-5e-4}"
PERTURB_MIX="${PERTURB_MIX:-geom:0.2@1,geom:0.3@0.4,topo:0.3@0.5,both:0.1@0.3,geom:0@1}"
PERTURB_SEED="${PERTURB_SEED:-114}"

read -r -a DATA_ROOT_ARR <<< "${DATA_ROOTS}"
read -r -a VAL_DATA_ROOT_ARR <<< "${VAL_DATA_ROOTS}"

START_ARR=()
if [[ -n "${STARTS_RAW}" ]]; then
  read -r -a START_ARR <<< "${STARTS_RAW}"
fi

END_ARR=()
if [[ -n "${ENDS_RAW}" ]]; then
  read -r -a END_ARR <<< "${ENDS_RAW}"
fi

VAL_START_ARR=()
if [[ -n "${VAL_STARTS_RAW}" ]]; then
  read -r -a VAL_START_ARR <<< "${VAL_STARTS_RAW}"
fi

VAL_END_ARR=()
if [[ -n "${VAL_ENDS_RAW}" ]]; then
  read -r -a VAL_END_ARR <<< "${VAL_ENDS_RAW}"
fi

echo "[$(timestamp)] conda_env_name=${CONDA_ENV_NAME}"
echo "[$(timestamp)] python_bin=${PYTHON_BIN}"
echo "[$(timestamp)] module_load_cmd=${MODULE_LOAD_CMD:-<none>}"
echo "[$(timestamp)] conda_activate_cmd=${CONDA_ACTIVATE_CMD:-<none>}"
echo "[$(timestamp)] conda_default_env=${CONDA_DEFAULT_ENV:-<unset>}"
echo "[$(timestamp)] conda_prefix=${CONDA_PREFIX:-<unset>}"
echo "[$(timestamp)] data_roots=${DATA_ROOTS}"
echo "[$(timestamp)] val_data_roots=${VAL_DATA_ROOTS:-<none>}"
echo "[$(timestamp)] starts=${STARTS_RAW:-<default>}"
echo "[$(timestamp)] ends=${ENDS_RAW:-<default>}"
echo "[$(timestamp)] val_starts=${VAL_STARTS_RAW:-<none>}"
echo "[$(timestamp)] val_ends=${VAL_ENDS_RAW:-<none>}"
echo "[$(timestamp)] batch_size=${BATCH_SIZE}"
echo "[$(timestamp)] stage1_max_epochs=${STAGE1_MAX_EPOCHS}"
echo "[$(timestamp)] stage2_loss=${STAGE2_LOSS}"
echo "[$(timestamp)] morse_a=${MORSE_A}"
echo "[$(timestamp)] lambda_dist=${LAMBDA_DIST}"
echo "[$(timestamp)] lambda_coord=${LAMBDA_COORD}"
echo "[$(timestamp)] lambda_angle=${LAMBDA_ANGLE}"
echo "[$(timestamp)] lambda_torsion=${LAMBDA_TORSION}"
echo "[$(timestamp)] lambda_planar=${LAMBDA_PLANAR}"
echo "[$(timestamp)] lambda_e=${LAMBDA_E}"
echo "[$(timestamp)] lambda_q=${LAMBDA_Q}"
echo "[$(timestamp)] lambda_z=${LAMBDA_Z}"
echo "[$(timestamp)] loss_cutoff=${LOSS_CUTOFF}"
echo "[$(timestamp)] model_experts=${MODEL_EXPERT_E},${MODEL_EXPERT_Q},${MODEL_EXPERT_Z},${MODEL_EXPERT_G}"
echo "[$(timestamp)] model_hidden=${MODEL_HIDDEN}"
echo "[$(timestamp)] model_bb_layers=${MODEL_BB_LAYERS}"
echo "[$(timestamp)] model_bb_heads=${MODEL_BB_HEADS}"
echo "[$(timestamp)] model_bb_ff_mult=${MODEL_BB_FF_MULT}"
echo "[$(timestamp)] bb_radius=${BB_RADIUS}"
echo "[$(timestamp)] model_expert_real_layers=${MODEL_EXPERT_REAL_LAYERS}"
echo "[$(timestamp)] model_expert_int_layers=${MODEL_EXPERT_INT_LAYERS}"
echo "[$(timestamp)] model_expert_heads=${MODEL_EXPERT_HEADS}"
echo "[$(timestamp)] model_expert_ff_mult=${MODEL_EXPERT_FF_MULT}"
echo "[$(timestamp)] save_path=${SAVE_PATH}"
echo "[$(timestamp)] epochs=${EPOCHS}"
echo "[$(timestamp)] save_every_epoch=${SAVE_EVERY_EPOCH}"
echo "[$(timestamp)] num_workers=${NUM_WORKERS}"
echo "[$(timestamp)] lr=${LR}"
echo "[$(timestamp)] perturb_mix=${PERTURB_MIX}"
echo "[$(timestamp)] perturb_seed=${PERTURB_SEED}"

if [[ "${#DATA_ROOT_ARR[@]}" -eq 0 ]]; then
  echo "[$(timestamp)] ERROR: DATA_ROOTS is empty."
  exit 1
fi

if [[ "${#START_ARR[@]}" -gt 0 && "${#START_ARR[@]}" -ne "${#DATA_ROOT_ARR[@]}" ]]; then
  echo "[$(timestamp)] ERROR: STARTS must match DATA_ROOTS entry count."
  exit 1
fi

if [[ "${#END_ARR[@]}" -gt 0 && "${#END_ARR[@]}" -ne "${#DATA_ROOT_ARR[@]}" ]]; then
  echo "[$(timestamp)] ERROR: ENDS must match DATA_ROOTS entry count."
  exit 1
fi

if [[ "${#VAL_START_ARR[@]}" -gt 0 && "${#VAL_START_ARR[@]}" -ne "${#VAL_DATA_ROOT_ARR[@]}" ]]; then
  echo "[$(timestamp)] ERROR: VAL_STARTS must match VAL_DATA_ROOTS entry count."
  exit 1
fi

if [[ "${#VAL_END_ARR[@]}" -gt 0 && "${#VAL_END_ARR[@]}" -ne "${#VAL_DATA_ROOT_ARR[@]}" ]]; then
  echo "[$(timestamp)] ERROR: VAL_ENDS must match VAL_DATA_ROOTS entry count."
  exit 1
fi

for root in "${DATA_ROOT_ARR[@]}"; do
  if [[ ! -e "${root}" ]]; then
    echo "[$(timestamp)] ERROR: training data path does not exist: ${root}"
    exit 1
  fi
done

for root in "${VAL_DATA_ROOT_ARR[@]}"; do
  if [[ ! -e "${root}" ]]; then
    echo "[$(timestamp)] ERROR: validation data path does not exist: ${root}"
    exit 1
  fi
done

mkdir -p "$(dirname "${SAVE_PATH}")"

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

mods = ["torch", "torch_geometric", "torch_cluster", "lmdb", "rdkit", "numpy", "sklearn", "tqdm", "periodictable"]
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
  echo "[$(timestamp)] ERROR: current Python environment is missing required MFM_version1 dependencies."
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

section "Training"
TRAIN_CMD=(
  "${PYTHON_BIN}"
  pretrain_multitask.py
  --data_roots "${DATA_ROOT_ARR[@]}"
  --batch_size "${BATCH_SIZE}"
  --stage1_max_epochs "${STAGE1_MAX_EPOCHS}"
  --stage2_loss "${STAGE2_LOSS}"
  --morse_a "${MORSE_A}"
  --lambda_dist "${LAMBDA_DIST}"
  --lambda_coord "${LAMBDA_COORD}"
  --lambda_angle "${LAMBDA_ANGLE}"
  --lambda_torsion "${LAMBDA_TORSION}"
  --lambda_planar "${LAMBDA_PLANAR}"
  --lambda_e "${LAMBDA_E}"
  --lambda_q "${LAMBDA_Q}"
  --lambda_z "${LAMBDA_Z}"
  --loss_cutoff "${LOSS_CUTOFF}"
  --expert_number_E "${MODEL_EXPERT_E}"
  --expert_number_Q "${MODEL_EXPERT_Q}"
  --expert_number_Z "${MODEL_EXPERT_Z}"
  --expert_number_G "${MODEL_EXPERT_G}"
  --hidden_channels "${MODEL_HIDDEN}"
  --bb_layers "${MODEL_BB_LAYERS}"
  --bb_heads "${MODEL_BB_HEADS}"
  --bb_ff_mult "${MODEL_BB_FF_MULT}"
  --bb_radius "${BB_RADIUS}"
  --expert_real_layers "${MODEL_EXPERT_REAL_LAYERS}"
  --expert_int_layers "${MODEL_EXPERT_INT_LAYERS}"
  --expert_heads "${MODEL_EXPERT_HEADS}"
  --expert_ff_mult "${MODEL_EXPERT_FF_MULT}"
  --save_path "${SAVE_PATH}"
  --epochs "${EPOCHS}"
  --num_workers "${NUM_WORKERS}"
  --lr "${LR}"
  --perturb_mix "${PERTURB_MIX}"
  --perturb_seed "${PERTURB_SEED}"
)

if [[ "${SAVE_EVERY_EPOCH}" == "1" ]]; then
  TRAIN_CMD+=(--save_every_epoch)
fi

if [[ "${#START_ARR[@]}" -gt 0 ]]; then
  TRAIN_CMD+=(--starts "${START_ARR[@]}")
fi

if [[ "${#END_ARR[@]}" -gt 0 ]]; then
  TRAIN_CMD+=(--ends "${END_ARR[@]}")
fi

if [[ "${#VAL_DATA_ROOT_ARR[@]}" -gt 0 ]]; then
  TRAIN_CMD+=(--val_data_roots "${VAL_DATA_ROOT_ARR[@]}")
fi

if [[ "${#VAL_START_ARR[@]}" -gt 0 ]]; then
  TRAIN_CMD+=(--val_starts "${VAL_START_ARR[@]}")
fi

if [[ "${#VAL_END_ARR[@]}" -gt 0 ]]; then
  TRAIN_CMD+=(--val_ends "${VAL_END_ARR[@]}")
fi

printf ' %q' "${TRAIN_CMD[@]}"
echo
"${TRAIN_CMD[@]}"

section "Finished"
echo "[$(timestamp)] Completed successfully."
echo "[$(timestamp)] Log file: ${LOG_PATH}"
echo "[$(timestamp)] Save path: ${SAVE_PATH}"
