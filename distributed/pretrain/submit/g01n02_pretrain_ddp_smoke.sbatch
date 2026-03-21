#!/usr/bin/env bash
# 4-GPU DDP smoke test for the distributed pretrain entrypoint.
#
# Recommended submit example on SCUT HPC:
#   cd /share/home/202264640132/MFM
#   sbatch --export=ALL,REPO_ROOT_OVERRIDE=$PWD,SKIP_CONDA=1,PYTHON_BIN=/share/home/202264640132/.conda/envs/torchgpu/bin/python pretrain/submit/g01n02_pretrain_ddp_smoke.sbatch

#SBATCH --job-name=pretrain-ddp-smoke
#SBATCH --partition=gpuA800
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --gres=gpu:4
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
VARIANT_ROOT="${REPO_ROOT}/distributed"
VARIANT_MODULE_PREFIX="distributed."
if [[ ! -f "${VARIANT_ROOT}/pretrain/submit/env_smoke_check.py" ]]; then
  VARIANT_ROOT="${REPO_ROOT}"
  VARIANT_MODULE_PREFIX=""
fi

CONDA_ENV_NAME="${CONDA_ENV_NAME:-torchgpu}"
PYTHON_BIN="${PYTHON_BIN:-python}"
MODULE_LOAD_CMD="${MODULE_LOAD_CMD:-}"
CONDA_ACTIVATE_CMD="${CONDA_ACTIVATE_CMD:-}"

RUN_TAG="ddp_pretrain_smoke_${SLURM_JOB_ID:-manual}"
RUN_DIR="${REPO_ROOT}/log/slurm_smoke/${RUN_TAG}"
CKPT_DIR="${REPO_ROOT}/test_ckpt/slurm_smoke/${RUN_TAG}"
WANDB_DIR="${REPO_ROOT}/wandb/slurm_smoke/${RUN_TAG}"

mkdir -p "${RUN_DIR}" "${CKPT_DIR}" "${WANDB_DIR}"
exec > >(tee -a "${RUN_DIR}/job.log") 2>&1

section "Job Context"
echo "[$(timestamp)] repo_root=${REPO_ROOT}"
echo "[$(timestamp)] variant_root=${VARIANT_ROOT}"
echo "[$(timestamp)] variant_module_prefix=${VARIANT_MODULE_PREFIX}"
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
export NCCL_DEBUG="${NCCL_DEBUG:-WARN}"
export NCCL_ASYNC_ERROR_HANDLING="${NCCL_ASYNC_ERROR_HANDLING:-1}"
export TORCH_DISTRIBUTED_DEBUG="${TORCH_DISTRIBUTED_DEBUG:-INFO}"

section "User Config"
DATA_ROOT="${DATA_ROOT:-${REPO_ROOT}/test_data/principal_valid_test.lmdb}"
RUN_ENV_SMOKE="${RUN_ENV_SMOKE:-1}"
ENV_SMOKE_STRICT_OPTIONAL="${ENV_SMOKE_STRICT_OPTIONAL:-0}"
RUN_ALLREDUCE_SMOKE="${RUN_ALLREDUCE_SMOKE:-1}"
RUN_DDP_PIPELINE_SMOKE="${RUN_DDP_PIPELINE_SMOKE:-1}"
AMP_DTYPE="${AMP_DTYPE:-none}"

DDP_NPROC_PER_NODE="${DDP_NPROC_PER_NODE:-4}"
DIST_TIMEOUT_MINUTES="${DIST_TIMEOUT_MINUTES:-180}"
DDP_TRAIN_START="${DDP_TRAIN_START:-875}"
DDP_TRAIN_END="${DDP_TRAIN_END:-1514}"
DDP_VAL_START="${DDP_VAL_START:-891}"
DDP_VAL_END="${DDP_VAL_END:-894}"
DDP_BATCH_SIZE_PER_GPU="${DDP_BATCH_SIZE_PER_GPU:-8}"
DDP_VAL_BATCH_SIZE="${DDP_VAL_BATCH_SIZE:-0}"
DDP_NUM_WORKERS_PER_GPU="${DDP_NUM_WORKERS_PER_GPU:-6}"
DDP_VAL_NUM_WORKERS="${DDP_VAL_NUM_WORKERS:--1}"
FILTER_MAX_ATOMS="${FILTER_MAX_ATOMS:-128}"
ATOM_BUDGET_PER_BATCH="${ATOM_BUDGET_PER_BATCH:-512}"
VAL_ATOM_BUDGET_PER_BATCH="${VAL_ATOM_BUDGET_PER_BATCH:-0}"
ATOM_COUNT_CACHE_DIR="${ATOM_COUNT_CACHE_DIR:-${REPO_ROOT}/log/atom_count_cache}"
DATALOADER_DEBUG="${DATALOADER_DEBUG:-0}"
DATALOADER_DEBUG_INTERVAL="${DATALOADER_DEBUG_INTERVAL:-30}"
DATALOADER_STALL_THRESHOLD="${DATALOADER_STALL_THRESHOLD:-120}"
DATALOADER_TIMEOUT="${DATALOADER_TIMEOUT:-0}"
DATALOADER_SLOW_FETCH_THRESHOLD="${DATALOADER_SLOW_FETCH_THRESHOLD:-10}"
DATALOADER_DEBUG_DIR="${DATALOADER_DEBUG_DIR:-${RUN_DIR}/dataloader_debug}"
DDP_DEBUG="${DDP_DEBUG:-0}"
DDP_DEBUG_INTERVAL="${DDP_DEBUG_INTERVAL:-15}"
DDP_DEBUG_STALL_THRESHOLD="${DDP_DEBUG_STALL_THRESHOLD:-60}"
DDP_DEBUG_DIR="${DDP_DEBUG_DIR:-${RUN_DIR}/ddp_debug}"
DDP_DEBUG_GRAD_SAMPLE_SIZE="${DDP_DEBUG_GRAD_SAMPLE_SIZE:-12}"

ALLREDUCE_TENSOR_MB="${ALLREDUCE_TENSOR_MB:-256}"
ALLREDUCE_WARMUP_ITERS="${ALLREDUCE_WARMUP_ITERS:-10}"
ALLREDUCE_ITERS="${ALLREDUCE_ITERS:-30}"
ALLREDUCE_DTYPE="${ALLREDUCE_DTYPE:-float32}"

MODEL_HIDDEN="${MODEL_HIDDEN:-64}"
MODEL_BB_LAYERS="${MODEL_BB_LAYERS:-3}"
MODEL_BB_HEADS="${MODEL_BB_HEADS:-4}"
MODEL_BB_FF_MULT="${MODEL_BB_FF_MULT:-2}"
MODEL_EXPERT_E="${MODEL_EXPERT_E:-2}"
MODEL_EXPERT_Q="${MODEL_EXPERT_Q:-2}"
MODEL_EXPERT_Z="${MODEL_EXPERT_Z:-2}"
MODEL_EXPERT_G="${MODEL_EXPERT_G:-2}"
MODEL_TOPK_E="${MODEL_TOPK_E:-1}"
MODEL_TOPK_Q="${MODEL_TOPK_Q:-1}"
MODEL_TOPK_Z="${MODEL_TOPK_Z:-1}"
MODEL_TOPK_G="${MODEL_TOPK_G:-1}"
MODEL_EXPERT_REAL_LAYERS="${MODEL_EXPERT_REAL_LAYERS:-1}"
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
echo "[$(timestamp)] env_smoke_strict_optional=${ENV_SMOKE_STRICT_OPTIONAL}"
echo "[$(timestamp)] run_allreduce_smoke=${RUN_ALLREDUCE_SMOKE}"
echo "[$(timestamp)] run_ddp_pipeline_smoke=${RUN_DDP_PIPELINE_SMOKE}"
echo "[$(timestamp)] ddp_nproc_per_node=${DDP_NPROC_PER_NODE}"
echo "[$(timestamp)] dist_timeout_minutes=${DIST_TIMEOUT_MINUTES}"
echo "[$(timestamp)] ddp_train_range=${DDP_TRAIN_START}..${DDP_TRAIN_END}"
echo "[$(timestamp)] ddp_val_range=${DDP_VAL_START}..${DDP_VAL_END}"
echo "[$(timestamp)] ddp_batch_size_per_gpu=${DDP_BATCH_SIZE_PER_GPU}"
echo "[$(timestamp)] ddp_val_batch_size=${DDP_VAL_BATCH_SIZE}"
echo "[$(timestamp)] ddp_num_workers_per_gpu=${DDP_NUM_WORKERS_PER_GPU}"
echo "[$(timestamp)] ddp_val_num_workers=${DDP_VAL_NUM_WORKERS}"
echo "[$(timestamp)] ddp_num_workers_total=$(( DDP_NUM_WORKERS_PER_GPU * DDP_NPROC_PER_NODE ))"
echo "[$(timestamp)] filter_max_atoms=${FILTER_MAX_ATOMS}"
echo "[$(timestamp)] atom_budget_per_batch=${ATOM_BUDGET_PER_BATCH}"
echo "[$(timestamp)] val_atom_budget_per_batch=${VAL_ATOM_BUDGET_PER_BATCH}"
echo "[$(timestamp)] atom_count_cache_dir=${ATOM_COUNT_CACHE_DIR}"
echo "[$(timestamp)] dataloader_debug=${DATALOADER_DEBUG}"
echo "[$(timestamp)] dataloader_debug_interval=${DATALOADER_DEBUG_INTERVAL}"
echo "[$(timestamp)] dataloader_stall_threshold=${DATALOADER_STALL_THRESHOLD}"
echo "[$(timestamp)] dataloader_timeout=${DATALOADER_TIMEOUT}"
echo "[$(timestamp)] dataloader_slow_fetch_threshold=${DATALOADER_SLOW_FETCH_THRESHOLD}"
echo "[$(timestamp)] dataloader_debug_dir=${DATALOADER_DEBUG_DIR}"
echo "[$(timestamp)] ddp_debug=${DDP_DEBUG}"
echo "[$(timestamp)] ddp_debug_interval=${DDP_DEBUG_INTERVAL}"
echo "[$(timestamp)] ddp_debug_stall_threshold=${DDP_DEBUG_STALL_THRESHOLD}"
echo "[$(timestamp)] ddp_debug_dir=${DDP_DEBUG_DIR}"
echo "[$(timestamp)] ddp_debug_grad_sample_size=${DDP_DEBUG_GRAD_SAMPLE_SIZE}"
echo "[$(timestamp)] allreduce_tensor_mb=${ALLREDUCE_TENSOR_MB}"
echo "[$(timestamp)] allreduce_warmup_iters=${ALLREDUCE_WARMUP_ITERS}"
echo "[$(timestamp)] allreduce_iters=${ALLREDUCE_ITERS}"
echo "[$(timestamp)] allreduce_dtype=${ALLREDUCE_DTYPE}"
echo "[$(timestamp)] model_hidden=${MODEL_HIDDEN}"
echo "[$(timestamp)] model_bb_layers=${MODEL_BB_LAYERS}"
echo "[$(timestamp)] model_experts=${MODEL_EXPERT_E},${MODEL_EXPERT_Q},${MODEL_EXPERT_Z},${MODEL_EXPERT_G}"
echo "[$(timestamp)] model_topk=${MODEL_TOPK_E},${MODEL_TOPK_Q},${MODEL_TOPK_Z},${MODEL_TOPK_G}"
echo "[$(timestamp)] model_expert_real_layers=${MODEL_EXPERT_REAL_LAYERS}"
echo "[$(timestamp)] nccl_debug=${NCCL_DEBUG}"
echo "[$(timestamp)] nccl_async_error_handling=${NCCL_ASYNC_ERROR_HANDLING}"
echo "[$(timestamp)] torch_distributed_debug=${TORCH_DISTRIBUTED_DEBUG}"

if [[ ! -f "${DATA_ROOT}" ]]; then
  echo "[$(timestamp)] ERROR: DATA_ROOT does not exist: ${DATA_ROOT}"
  exit 1
fi

if [[ "${DDP_NPROC_PER_NODE}" != "4" ]]; then
  echo "[$(timestamp)] WARNING: this smoke script is designed for 4 GPUs, but DDP_NPROC_PER_NODE=${DDP_NPROC_PER_NODE}"
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

section "CUDA And Distributed Sanity"
"${PYTHON_BIN}" - <<'PY'
import torch
import torch.distributed as dist

print("torch_version=", torch.__version__)
print("cuda_available=", torch.cuda.is_available())
print("cuda_device_count=", torch.cuda.device_count())
print("distributed_available=", dist.is_available())
print("nccl_available=", dist.is_nccl_available() if dist.is_available() else False)
print("gloo_available=", dist.is_gloo_available() if dist.is_available() else False)
for idx in range(torch.cuda.device_count()):
    props = torch.cuda.get_device_properties(idx)
    print(
        f"gpu[{idx}] name={props.name} total_memory_gb={props.total_memory / (1024 ** 3):.2f} "
        f"sm_count={props.multi_processor_count}"
    )
PY

TORCHRUN_CMD=("${PYTHON_BIN}" -m torch.distributed.run --standalone --nproc_per_node="${DDP_NPROC_PER_NODE}")

if [[ "${RUN_ENV_SMOKE}" == "1" ]]; then
  section "Phase 1: Repo Env Smoke"
  ENV_SMOKE_ARGS=(
    "${VARIANT_ROOT}/pretrain/submit/env_smoke_check.py"
    --data-root "${DATA_ROOT}"
    --train-start "${DDP_TRAIN_START}"
    --train-end "$(( DDP_TRAIN_START + 3 ))"
    --batch-size 2
    --device auto
  )
  if [[ "${ENV_SMOKE_STRICT_OPTIONAL}" == "1" ]]; then
    ENV_SMOKE_ARGS+=(--strict-optional)
  fi
  CUDA_VISIBLE_DEVICES=0 "${PYTHON_BIN}" "${ENV_SMOKE_ARGS[@]}"
fi

if [[ "${RUN_ALLREDUCE_SMOKE}" == "1" ]]; then
  section "Phase 2: 4-GPU NCCL Allreduce Smoke"
  "${TORCHRUN_CMD[@]}" "${VARIANT_ROOT}/pretrain/submit/ddp_allreduce_smoke.py" \
    --backend nccl \
    --tensor-mb "${ALLREDUCE_TENSOR_MB}" \
    --warmup-iters "${ALLREDUCE_WARMUP_ITERS}" \
    --iters "${ALLREDUCE_ITERS}" \
    --dtype "${ALLREDUCE_DTYPE}"
fi

if [[ "${RUN_DDP_PIPELINE_SMOKE}" == "1" ]]; then
  section "Phase 3: 4-GPU Distributed Pipeline Smoke"
  DDP_PIPELINE_CMD=(
    "${TORCHRUN_CMD[@]}"
    -m "${VARIANT_MODULE_PREFIX}pretrain.pipeline"
    --distributed
    --device cuda
    --backend nccl
    --dist_timeout_minutes "${DIST_TIMEOUT_MINUTES}"
    --find_unused_parameters
    --data_roots "${DATA_ROOT}"
    --starts "${DDP_TRAIN_START}"
    --ends "${DDP_TRAIN_END}"
    --val_data_roots "${DATA_ROOT}"
    --val_starts "${DDP_VAL_START}"
    --val_ends "${DDP_VAL_END}"
    --epochs 1
    --batch_size "${DDP_BATCH_SIZE_PER_GPU}"
    --val_batch_size "${DDP_VAL_BATCH_SIZE}"
    --num_workers "${DDP_NUM_WORKERS_PER_GPU}"
    --val_num_workers "${DDP_VAL_NUM_WORKERS}"
    --filter_max_atoms "${FILTER_MAX_ATOMS}"
    --atom_budget_per_batch "${ATOM_BUDGET_PER_BATCH}"
    --val_atom_budget_per_batch "${VAL_ATOM_BUDGET_PER_BATCH}"
    --atom_count_cache_dir "${ATOM_COUNT_CACHE_DIR}"
    --amp_dtype "${AMP_DTYPE}"
    --dataloader_timeout "${DATALOADER_TIMEOUT}"
    --hidden_channels "${MODEL_HIDDEN}"
    --bb_layers "${MODEL_BB_LAYERS}"
    --bb_heads "${MODEL_BB_HEADS}"
    --bb_ff_mult "${MODEL_BB_FF_MULT}"
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
    --lambda_e 1.0
    --lambda_e_desc 0.5
    --lambda_q 1.0
    --lambda_q_desc 0.5
    --lambda_z 1.0
    --lambda_z_desc 0.5
    --lambda_dist 1.0
    --lambda_angle 1.0
    --lambda_torsion 2.0
    --stage1_loss 0.1
    --stage1_max_epochs 10
    --loss_cutoff 2.0
    --perturb_mode both
    --perturb_level 0.5
    --save_path "${CKPT_DIR}/ddp_smoke.pt"
    --use_wandb
    --wandb_mode offline
    --wandb_project mfm-pretrain
    --wandb_group slurm_ddp_smoke
    --wandb_run_name "ddp_smoke_${SLURM_JOB_ID}"
    --wandb_dir "${WANDB_DIR}"
    --wandb_watch none
    --wandb_log_batch_every 10
  )

  if [[ "${DATALOADER_DEBUG}" == "1" ]]; then
    DDP_PIPELINE_CMD+=(
      --dataloader_debug
      --dataloader_debug_interval "${DATALOADER_DEBUG_INTERVAL}"
      --dataloader_stall_threshold "${DATALOADER_STALL_THRESHOLD}"
      --dataloader_slow_fetch_threshold "${DATALOADER_SLOW_FETCH_THRESHOLD}"
      --dataloader_debug_dir "${DATALOADER_DEBUG_DIR}"
    )
  fi

  if [[ "${DDP_DEBUG}" == "1" ]]; then
    DDP_PIPELINE_CMD+=(
      --ddp_debug
      --ddp_debug_interval "${DDP_DEBUG_INTERVAL}"
      --ddp_debug_stall_threshold "${DDP_DEBUG_STALL_THRESHOLD}"
      --ddp_debug_dir "${DDP_DEBUG_DIR}"
      --ddp_debug_grad_sample_size "${DDP_DEBUG_GRAD_SAMPLE_SIZE}"
    )
  fi

  "${DDP_PIPELINE_CMD[@]}"
fi

section "Finished"
echo "[$(timestamp)] Completed successfully."
echo "[$(timestamp)] Logs: ${RUN_DIR}"
echo "[$(timestamp)] Checkpoints: ${CKPT_DIR}"
echo "[$(timestamp)] W&B offline dir: ${WANDB_DIR}"
