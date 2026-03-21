#!/usr/bin/env bash
# Single-GPU smoke test for the current pretrain entrypoint.
#
# Recommended submit example on SCUT HPC:
#   cd /share/home/202264640132/MFM
#   sbatch --export=ALL,REPO_ROOT_OVERRIDE=$PWD,SKIP_CONDA=1,PYTHON_BIN=/share/home/202264640132/.conda/envs/torchgpu/bin/python pretrain/submit/g01n02_pretrain_smoke.sbatch

#SBATCH --job-name=pretrain-single-smoke
#SBATCH --partition=gpuA800
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --gres=gpu:1
#SBATCH --mem=256G
#SBATCH --time=01:00:00
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

RUN_TAG="single_gpu_pretrain_smoke_${SLURM_JOB_ID:-manual}"
RUN_DIR="${REPO_ROOT}/log/slurm_smoke/${RUN_TAG}"
CKPT_DIR="${REPO_ROOT}/test_ckpt/slurm_smoke/${RUN_TAG}"
WANDB_DIR="${REPO_ROOT}/wandb/slurm_smoke/${RUN_TAG}"

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
DATA_ROOT="${DATA_ROOT:-${REPO_ROOT}/test_data/principal_valid_test.lmdb}"
RUN_ENV_SMOKE="${RUN_ENV_SMOKE:-1}"

SINGLE_GPU_TRAIN_START="${SINGLE_GPU_TRAIN_START:-875}"
SINGLE_GPU_TRAIN_END="${SINGLE_GPU_TRAIN_END:-1514}"
SINGLE_GPU_BATCH_SIZE="${SINGLE_GPU_BATCH_SIZE:-32}"
SINGLE_GPU_NUM_WORKERS="${SINGLE_GPU_NUM_WORKERS:-16}"

MODEL_HIDDEN="${MODEL_HIDDEN:-64}"
MODEL_BB_LAYERS="${MODEL_BB_LAYERS:-3}"
MODEL_EXPERT_REAL_LAYERS="${MODEL_EXPERT_REAL_LAYERS:-1}"
MODEL_BB_HEADS="${MODEL_BB_HEADS:-4}"
MODEL_BB_FF_MULT="${MODEL_BB_FF_MULT:-2}"
MODEL_EXPERT_HEADS="${MODEL_EXPERT_HEADS:-4}"
MODEL_EXPERT_FF_MULT="${MODEL_EXPERT_FF_MULT:-2}"

echo "[$(timestamp)] conda_env_name=${CONDA_ENV_NAME}"
echo "[$(timestamp)] python_bin=${PYTHON_BIN}"
echo "[$(timestamp)] module_load_cmd=${MODULE_LOAD_CMD:-<none>}"
echo "[$(timestamp)] conda_activate_cmd=${CONDA_ACTIVATE_CMD:-<none>}"
echo "[$(timestamp)] conda_default_env=${CONDA_DEFAULT_ENV:-<unset>}"
echo "[$(timestamp)] conda_prefix=${CONDA_PREFIX:-<unset>}"
echo "[$(timestamp)] data_root=${DATA_ROOT}"
echo "[$(timestamp)] run_env_smoke=${RUN_ENV_SMOKE}"
echo "[$(timestamp)] single_gpu_train_range=${SINGLE_GPU_TRAIN_START}..${SINGLE_GPU_TRAIN_END}"
echo "[$(timestamp)] single_gpu_batch_size=${SINGLE_GPU_BATCH_SIZE}"
echo "[$(timestamp)] single_gpu_num_workers=${SINGLE_GPU_NUM_WORKERS}"
echo "[$(timestamp)] model_hidden=${MODEL_HIDDEN}"
echo "[$(timestamp)] model_bb_layers=${MODEL_BB_LAYERS}"
echo "[$(timestamp)] model_expert_real_layers=${MODEL_EXPERT_REAL_LAYERS}"

if [[ ! -f "${DATA_ROOT}" ]]; then
  echo "[$(timestamp)] ERROR: DATA_ROOT does not exist: ${DATA_ROOT}"
  exit 1
fi

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
  CUDA_VISIBLE_DEVICES=0 "${PYTHON_BIN}" pretrain/submit/env_smoke_check.py \
    --data-root "${DATA_ROOT}" \
    --train-start "${SINGLE_GPU_TRAIN_START}" \
    --train-end "$((SINGLE_GPU_TRAIN_START + 3))" \
    --batch-size 2 \
    --device auto
fi

section "Phase 2: Single-GPU Pipeline Smoke"
# Intentionally skip val_data_roots here.
# On the current server stack, reopening the same LMDB path for train+val in one process
# raises `lmdb.Error: The environment ... is already open in this process`.
CUDA_VISIBLE_DEVICES=0 "${PYTHON_BIN}" -m pretrain.pipeline \
  --data_roots "${DATA_ROOT}" \
  --starts "${SINGLE_GPU_TRAIN_START}" \
  --ends "${SINGLE_GPU_TRAIN_END}" \
  --epochs 1 \
  --batch_size "${SINGLE_GPU_BATCH_SIZE}" \
  --num_workers "${SINGLE_GPU_NUM_WORKERS}" \
  --hidden_channels "${MODEL_HIDDEN}" \
  --bb_layers "${MODEL_BB_LAYERS}" \
  --bb_heads "${MODEL_BB_HEADS}" \
  --bb_ff_mult "${MODEL_BB_FF_MULT}" \
  --expert_number_E 1 \
  --expert_number_Q 1 \
  --expert_number_Z 1 \
  --expert_number_G 1 \
  --topkE 1 \
  --topkQ 1 \
  --topkZ 1 \
  --topkG 1 \
  --expert_real_layers "${MODEL_EXPERT_REAL_LAYERS}" \
  --expert_int_layers 0 \
  --expert_heads "${MODEL_EXPERT_HEADS}" \
  --expert_ff_mult "${MODEL_EXPERT_FF_MULT}" \
  --lambda_e 1.0 \
  --lambda_e_desc 0.5 \
  --lambda_q 1.0 \
  --lambda_q_desc 0.5 \
  --lambda_z 1.0 \
  --lambda_z_desc 0.5 \
  --lambda_dist 1.0 \
  --lambda_angle 1.0 \
  --lambda_torsion 2.0 \
  --stage1_loss 0.1 \
  --stage1_max_epochs 10 \
  --loss_cutoff 2.0 \
  --perturb_mode both \
  --perturb_level 0.5 \
  --save_path "${CKPT_DIR}/single_gpu_smoke.pt" \
  --use_wandb \
  --wandb_mode offline \
  --wandb_project mfm-pretrain \
  --wandb_group slurm_single_gpu_smoke \
  --wandb_run_name "single_gpu_smoke_${SLURM_JOB_ID}" \
  --wandb_dir "${WANDB_DIR}" \
  --wandb_watch none \
  --wandb_log_batch_every 10

section "Finished"
echo "[$(timestamp)] Completed successfully."
echo "[$(timestamp)] Logs: ${RUN_DIR}"
echo "[$(timestamp)] Checkpoints: ${CKPT_DIR}"
echo "[$(timestamp)] W&B offline dir: ${WANDB_DIR}"
