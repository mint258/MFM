#!/usr/bin/env bash

# Recommended submit example on SCUT HPC:
#   cd /share/home/202264640132/MFM_distributed
#   sbatch --export=ALL,REPO_ROOT_OVERRIDE=$PWD,SKIP_CONDA=1,PYTHON_BIN=/share/home/202264640132/.conda/envs/torchgpu/bin/python pretrain/submit/g01n02_pretrain_ddp_formal.sbatch

#SBATCH --job-name=pretrain-ddp-formal
#SBATCH --partition=gpuA800
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --gres=gpu:4
#SBATCH --mem=256G
#SBATCH --time=48:00:00
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err

set -Eeuo pipefail

report_failure() {
  local exit_code="$1"
  local line_no="$2"
  local failed_command="$3"
  {
    echo
    echo "========== Failure =========="
    echo "[$(timestamp)] exit_code=${exit_code}"
    echo "[$(timestamp)] failed_line=${line_no}"
    echo "[$(timestamp)] failed_command=${failed_command}"
    echo "[$(timestamp)] pwd=$(pwd)"
    echo "[$(timestamp)] repo_root=${REPO_ROOT:-unset}"
    echo "[$(timestamp)] variant_root=${VARIANT_ROOT:-unset}"
    echo "[$(timestamp)] run_root=${RUN_ROOT:-unset}"
  } >&2
  exit "${exit_code}"
}

trap 'report_failure "$?" "$LINENO" "$BASH_COMMAND"' ERR

timestamp() {
  date "+%Y-%m-%d %H:%M:%S"
}

run_shell_init_cmd() {
  local cmd="$1"
  local had_errexit=0
  local had_nounset=0
  local status=0

  if [[ "$-" == *e* ]]; then had_errexit=1; fi
  if [[ "$-" == *u* ]]; then had_nounset=1; fi

  set +eu
  eval "${cmd}"
  status=$?

  if [[ ${had_errexit} -eq 1 ]]; then set -e; fi
  if [[ ${had_nounset} -eq 1 ]]; then set -u; fi
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
  if [[ -n "${SLURM_SUBMIT_DIR:-}" ]] && find_repo_root_from "${SLURM_SUBMIT_DIR}" >/dev/null; then
    find_repo_root_from "${SLURM_SUBMIT_DIR}"
    return 0
  fi
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if find_repo_root_from "${script_dir}" >/dev/null; then
    find_repo_root_from "${script_dir}"
    return 0
  fi
  echo "Failed to resolve repo root. Set REPO_ROOT_OVERRIDE=/abs/path/to/repo." >&2
  return 1
}

activate_conda_env() {
  if [[ "${SKIP_CONDA:-0}" == "1" ]]; then
    return 0
  fi

  export LANG="${LANG:-C.UTF-8}"
  export LC_ALL="${LC_ALL:-}"

  if [[ -n "${MODULE_LOAD_CMD:-}" ]]; then
    run_shell_init_cmd "${MODULE_LOAD_CMD}"
  fi

  if [[ -n "${CONDA_ACTIVATE_CMD:-}" ]]; then
    run_shell_init_cmd "${CONDA_ACTIVATE_CMD}"
    return 0
  fi

  if command -v conda >/dev/null 2>&1; then
    run_shell_init_cmd "$(conda shell.bash hook)"
  elif [[ -f "${HOME}/miniconda3/etc/profile.d/conda.sh" ]]; then
    source "${HOME}/miniconda3/etc/profile.d/conda.sh"
  elif [[ -f "${HOME}/anaconda3/etc/profile.d/conda.sh" ]]; then
    source "${HOME}/anaconda3/etc/profile.d/conda.sh"
  else
    echo "Conda was not found. Set SKIP_CONDA=1 with PYTHON_BIN to bypass activation." >&2
    exit 1
  fi

  conda activate "${CONDA_ENV_NAME}"
}

REPO_ROOT="$(resolve_repo_root)"
VARIANT_ROOT="${REPO_ROOT}/distributed"
VARIANT_MODULE_PREFIX="distributed."
if [[ ! -f "${VARIANT_ROOT}/pretrain/pipeline.py" ]]; then
  VARIANT_ROOT="${REPO_ROOT}"
  VARIANT_MODULE_PREFIX=""
fi
if [[ ! -f "${VARIANT_ROOT}/pretrain/pipeline.py" ]]; then
  echo "Resolved VARIANT_ROOT does not contain pretrain/pipeline.py: ${VARIANT_ROOT}" >&2
  exit 1
fi
if [[ ! -f "${VARIANT_ROOT}/pretrain/submit/pretrain_preflight.sh" ]]; then
  echo "Resolved VARIANT_ROOT does not contain pretrain_preflight.sh: ${VARIANT_ROOT}" >&2
  exit 1
fi

CONDA_ENV_NAME="${CONDA_ENV_NAME:-torchgpu}"
PYTHON_BIN="${PYTHON_BIN:-python}"
MODULE_LOAD_CMD="${MODULE_LOAD_CMD:-}"
CONDA_ACTIVATE_CMD="${CONDA_ACTIVATE_CMD:-}"

RUN_TAG="${RUN_TAG:-formal_pretrain_${SLURM_JOB_ID:-manual}}"
RUN_ROOT="${RUN_ROOT:-${REPO_ROOT}/log/formal_pretrain/${RUN_TAG}}"
CKPT_DIR="${CKPT_DIR:-${RUN_ROOT}/checkpoints}"
BEST_CKPT="${BEST_CKPT:-${CKPT_DIR}/best.pt}"
WANDB_DIR="${WANDB_DIR:-${RUN_ROOT}/wandb}"

mkdir -p "${RUN_ROOT}" "${CKPT_DIR}" "${WANDB_DIR}"
exec > >(tee -a "${RUN_ROOT}/job.log") 2>&1

cd "${REPO_ROOT}"
activate_conda_env

export PYTHONUNBUFFERED=1
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NCCL_DEBUG="${NCCL_DEBUG:-WARN}"
export NCCL_ASYNC_ERROR_HANDLING="${NCCL_ASYNC_ERROR_HANDLING:-1}"
export TORCH_DISTRIBUTED_DEBUG="${TORCH_DISTRIBUTED_DEBUG:-INFO}"

DATA_DIR="${DATA_DIR:-/share/home/202264640132/dataset}"
DEFAULT_DATA_ROOTS="${DATA_DIR}/principal_00000001_00300000.lmdb ${DATA_DIR}/principal_00300001_00600000.lmdb ${DATA_DIR}/principal_00600001_00900000.lmdb ${DATA_DIR}/principal_00900001_01200000.lmdb ${DATA_DIR}/principal_01200001_01500000.lmdb ${DATA_DIR}/principal_01500001_01800000.lmdb ${DATA_DIR}/unimol_01000001_02000000.lmdb ${DATA_DIR}/unimol_02000001_03000000.lmdb ${DATA_DIR}/unimol_03000001_04000000.lmdb ${DATA_DIR}/unimol_04000001_05000000.lmdb ${DATA_DIR}/unimol_05000001_06000000.lmdb"
DATA_ROOT="${DATA_ROOT:-}"
DATA_ROOTS="${DATA_ROOTS:-}"
if [[ -z "${DATA_ROOTS}" ]]; then
  if [[ -n "${DATA_ROOT}" ]]; then
    DATA_ROOTS="${DATA_ROOT}"
  else
    DATA_ROOTS="${DEFAULT_DATA_ROOTS}"
  fi
fi
read -r -a DATA_ROOT_ARR <<< "${DATA_ROOTS}"

STARTS_RAW="${STARTS:-}"
ENDS_RAW="${ENDS:-}"
if [[ -z "${STARTS_RAW}" ]]; then
  START_ARR=()
  for _ in "${DATA_ROOT_ARR[@]}"; do
    START_ARR+=(0)
  done
else
  read -r -a START_ARR <<< "${STARTS_RAW}"
fi
if [[ -z "${ENDS_RAW}" ]]; then
  END_ARR=()
  for _ in "${DATA_ROOT_ARR[@]}"; do
    END_ARR+=(-1)
  done
else
  read -r -a END_ARR <<< "${ENDS_RAW}"
fi
STARTS="${START_ARR[*]}"
ENDS="${END_ARR[*]}"

if [[ "${#DATA_ROOT_ARR[@]}" -ne "${#START_ARR[@]}" || "${#DATA_ROOT_ARR[@]}" -ne "${#END_ARR[@]}" ]]; then
  echo "DATA_ROOTS, STARTS, and ENDS must have the same number of entries." >&2
  echo "DATA_ROOTS=${#DATA_ROOT_ARR[@]} STARTS=${#START_ARR[@]} ENDS=${#END_ARR[@]}" >&2
  exit 1
fi

missing_data_roots=()
for root_path in "${DATA_ROOT_ARR[@]}"; do
  if [[ ! -e "${root_path}" ]]; then
    missing_data_roots+=("${root_path}")
  fi
done
if [[ "${#missing_data_roots[@]}" -gt 0 ]]; then
  echo "One or more DATA_ROOTS entries do not exist." >&2
  echo "Current DATA_DIR default is: ${DATA_DIR}" >&2
  echo "Set DATA_ROOTS explicitly in sbatch --export, or set DATA_DIR to the directory that contains the LMDB shards." >&2
  for root_path in "${missing_data_roots[@]}"; do
    echo "missing_data_root=${root_path}" >&2
  done
  exit 1
fi

DDP_NPROC_PER_NODE="${DDP_NPROC_PER_NODE:-4}"
DIST_TIMEOUT_MINUTES="${DIST_TIMEOUT_MINUTES:-180}"
BATCH_SIZE_PER_GPU="${BATCH_SIZE_PER_GPU:-16}"
VAL_BATCH_SIZE="${VAL_BATCH_SIZE:-0}"
NUM_WORKERS_PER_GPU="${NUM_WORKERS_PER_GPU:-6}"
VAL_NUM_WORKERS="${VAL_NUM_WORKERS:--1}"
EPOCHS="${EPOCHS:-2}"
LR="${LR:-1e-3}"
WARMUP_PCT="${WARMUP_PCT:-0.02}"
SEED="${SEED:-0}"
PERTURB_MIX="${PERTURB_MIX:-geom:0.2@0.2,geom:0.3@0.1,topo:0.3@0.2,both:0.1@0.1,clean:@1}"
DEFAULT_PERTURB_LMDBS="geom:0.2@0.2=${DATA_DIR}/geom0.2@0.2.lmdb geom:0.3@0.1=${DATA_DIR}/geom0.3@0.1.lmdb topo:0.3@0.2=${DATA_DIR}/topo0.3@0.2.lmdb both:0.1@0.1=${DATA_DIR}/both0.1@0.1.lmdb"
PERTURB_LMDBS="${PERTURB_LMDBS:-${DEFAULT_PERTURB_LMDBS}}"
PERTURB_MODE="${PERTURB_MODE:-both}"
PERTURB_LEVEL="${PERTURB_LEVEL:-0.5}"
VAL_PERTURB_MIX="${VAL_PERTURB_MIX:-clean:@1}"
VAL_PERTURB_LMDBS="${VAL_PERTURB_LMDBS:-}"
VAL_PERTURB_MODE="${VAL_PERTURB_MODE:-clean}"
VAL_PERTURB_LEVEL="${VAL_PERTURB_LEVEL:-0.0}"
VAL_DIAG_PERTURB_MIX="${VAL_DIAG_PERTURB_MIX:-topo:0.3@1}"
VAL_DIAG_PERTURB_LMDBS="${VAL_DIAG_PERTURB_LMDBS:-}"
VAL_DIAG_PERTURB_MODE="${VAL_DIAG_PERTURB_MODE:-topo}"
VAL_DIAG_PERTURB_LEVEL="${VAL_DIAG_PERTURB_LEVEL:-0.3}"
LOSS_CUTOFF="${LOSS_CUTOFF:-2.0}"
MORSE_A="${MORSE_A:-0.6}"
AMP_DTYPE="${AMP_DTYPE:-none}"
DETERMINISTIC_ALGORITHMS="${DETERMINISTIC_ALGORITHMS:-0}"
CUDNN_DETERMINISTIC="${CUDNN_DETERMINISTIC:-0}"
DISABLE_CUDNN_BENCHMARK="${DISABLE_CUDNN_BENCHMARK:-0}"
DISABLE_TF32="${DISABLE_TF32:-0}"
FLOAT32_MATMUL_PRECISION="${FLOAT32_MATMUL_PRECISION:-}"
FIXED_TRAIN_ORDER="${FIXED_TRAIN_ORDER:-0}"
GRAD_CLIP_NORM="${GRAD_CLIP_NORM:-1.0}"
BATCH_ORDER_PREVIEW_BATCHES="${BATCH_ORDER_PREVIEW_BATCHES:-0}"

VAL_SIZE="${VAL_SIZE:-20000}"
SPLIT_SEED="${SPLIT_SEED:-0}"
SPLIT_CACHE_PATH="${SPLIT_CACHE_PATH:-${REPO_ROOT}/log/pretrain_splits/val_seed${SPLIT_SEED}_n${VAL_SIZE}.pt}"
STANDARDIZER_RATIO="${STANDARDIZER_RATIO:-0.01}"
STANDARDIZER_CAP="${STANDARDIZER_CAP:-100000}"
FILTER_MAX_ATOMS="${FILTER_MAX_ATOMS:-128}"
ATOM_BUDGET_PER_BATCH="${ATOM_BUDGET_PER_BATCH:-512}"
VAL_ATOM_BUDGET_PER_BATCH="${VAL_ATOM_BUDGET_PER_BATCH:-0}"
ATOM_COUNT_CACHE_DIR="${ATOM_COUNT_CACHE_DIR:-${REPO_ROOT}/log/atom_count_cache}"
FORCE_RECOMPUTE_ATOM_COUNTS="${FORCE_RECOMPUTE_ATOM_COUNTS:-0}"
OLD_PRETRAINING_STRATEGY="${OLD_PRETRAINING_STRATEGY:-0}"

VALIDATE_EVERY_STEPS="${VALIDATE_EVERY_STEPS:-10000}"
SAVE_LATEST_EVERY_STEPS="${SAVE_LATEST_EVERY_STEPS:-5000}"
SAVE_ARCHIVE_EVERY_STEPS="${SAVE_ARCHIVE_EVERY_STEPS:-40000}"
SAVE_AFTER_STEP="${SAVE_AFTER_STEP:-0}"
SAVE_LAST_K_CHECKPOINTS="${SAVE_LAST_K_CHECKPOINTS:-0}"
STAGE1_MAX_STEPS="${STAGE1_MAX_STEPS:-20000}"
STAGE2_DESCRIPTOR_RAMP_STEPS="${STAGE2_DESCRIPTOR_RAMP_STEPS:-4000}"
STAGE1_SIGNAL_DECAY_STEPS="${STAGE1_SIGNAL_DECAY_STEPS:-${STAGE2_DESCRIPTOR_RAMP_STEPS}}"
STAGE1_SIGNAL_FLOOR="${STAGE1_SIGNAL_FLOOR:-0.35}"
RESUME_FROM="${RESUME_FROM:-}"
MAX_OPTIMIZER_STEPS="${MAX_OPTIMIZER_STEPS:-0}"
DATALOADER_DEBUG="${DATALOADER_DEBUG:-0}"
DATALOADER_DEBUG_INTERVAL="${DATALOADER_DEBUG_INTERVAL:-30}"
DATALOADER_STALL_THRESHOLD="${DATALOADER_STALL_THRESHOLD:-120}"
DATALOADER_TIMEOUT="${DATALOADER_TIMEOUT:-0}"
DATALOADER_SLOW_FETCH_THRESHOLD="${DATALOADER_SLOW_FETCH_THRESHOLD:-10}"
DATALOADER_DEBUG_DIR="${DATALOADER_DEBUG_DIR:-${RUN_ROOT}/dataloader_debug}"
DDP_DEBUG="${DDP_DEBUG:-0}"
DDP_DEBUG_INTERVAL="${DDP_DEBUG_INTERVAL:-15}"
DDP_DEBUG_STALL_THRESHOLD="${DDP_DEBUG_STALL_THRESHOLD:-60}"
DDP_DEBUG_DIR="${DDP_DEBUG_DIR:-${RUN_ROOT}/ddp_debug}"
DDP_DEBUG_GRAD_SAMPLE_SIZE="${DDP_DEBUG_GRAD_SAMPLE_SIZE:-12}"
DDP_STATIC_GRAPH="${DDP_STATIC_GRAPH:-0}"
FIND_UNUSED_PARAMETERS="${FIND_UNUSED_PARAMETERS:-1}"
DDP_FINAL_BARRIER="${DDP_FINAL_BARRIER:-0}"
TIMING_LOG_EVERY="${TIMING_LOG_EVERY:-0}"
TIMING_LOG_DIR="${TIMING_LOG_DIR:-}"
TIMING_SYNC_CUDA="${TIMING_SYNC_CUDA:-0}"
TIMING_COLLECT_RANK_SKEW="${TIMING_COLLECT_RANK_SKEW:-0}"
if [[ "${TIMING_LOG_EVERY}" != "0" && -z "${TIMING_LOG_DIR}" ]]; then
  TIMING_LOG_DIR="${RUN_ROOT}/timing"
fi

MODEL_HIDDEN="${MODEL_HIDDEN:-768}"
MODEL_BB_LAYERS="${MODEL_BB_LAYERS:-6}"
MODEL_BB_HEADS="${MODEL_BB_HEADS:-12}"
MODEL_BB_FF_MULT="${MODEL_BB_FF_MULT:-2}"
BB_RADIUS="${BB_RADIUS:-8.0}"
MODEL_EXPERT_E="${MODEL_EXPERT_E:-1}"
MODEL_EXPERT_Q="${MODEL_EXPERT_Q:-1}"
MODEL_EXPERT_Z="${MODEL_EXPERT_Z:-1}"
MODEL_EXPERT_G="${MODEL_EXPERT_G:-1}"
MODEL_EXPERT_B="${MODEL_EXPERT_B:-1}"
MODEL_TOPK_E="${MODEL_TOPK_E:-1}"
MODEL_TOPK_Q="${MODEL_TOPK_Q:-1}"
MODEL_TOPK_Z="${MODEL_TOPK_Z:-1}"
MODEL_TOPK_G="${MODEL_TOPK_G:-1}"
MODEL_TOPK_B="${MODEL_TOPK_B:-1}"
MODEL_EXPERT_REAL_LAYERS="${MODEL_EXPERT_REAL_LAYERS:-2}"
MODEL_EXPERT_INT_LAYERS="${MODEL_EXPERT_INT_LAYERS:-0}"
MODEL_EXPERT_HEADS="${MODEL_EXPERT_HEADS:-12}"
MODEL_EXPERT_FF_MULT="${MODEL_EXPERT_FF_MULT:-2}"
MODEL_DIRECT_LINEAR_NOEXPERT="${MODEL_DIRECT_LINEAR_NOEXPERT:-0}"
BOND_NEGATIVE_RATIO="${BOND_NEGATIVE_RATIO:-1.0}"

LAMBDA_E="${LAMBDA_E:-1.0}"
LAMBDA_E_DESC="${LAMBDA_E_DESC:-0.25}"
ENERGY_DESC_INCLUDE="${ENERGY_DESC_INCLUDE:-}"
ENERGY_DESC_EXCLUDE="${ENERGY_DESC_EXCLUDE:-}"
LAMBDA_Q="${LAMBDA_Q:-1.0}"
LAMBDA_Q_DESC="${LAMBDA_Q_DESC:-0.5}"
LAMBDA_Z="${LAMBDA_Z:-1.0}"
LAMBDA_Z_DESC="${LAMBDA_Z_DESC:-0.5}"
LAMBDA_BOND_EXIST="${LAMBDA_BOND_EXIST:-1.0}"
LAMBDA_BOND_ORDER="${LAMBDA_BOND_ORDER:-1.0}"
LAMBDA_DIST="${LAMBDA_DIST:-1.0}"
LAMBDA_ANGLE="${LAMBDA_ANGLE:-1.0}"
LAMBDA_TORSION="${LAMBDA_TORSION:-2.0}"

USE_WANDB="${USE_WANDB:-1}"
WANDB_MODE="${WANDB_MODE:-offline}"
WANDB_PROJECT="${WANDB_PROJECT:-mfm-pretrain}"
WANDB_GROUP="${WANDB_GROUP:-formal_ddp}"
WANDB_RUN_NAME="${WANDB_RUN_NAME:-${RUN_TAG}}"
WANDB_WATCH="${WANDB_WATCH:-none}"
WANDB_WATCH_LOG_FREQ="${WANDB_WATCH_LOG_FREQ:-1000}"
WANDB_LOG_BATCH_EVERY="${WANDB_LOG_BATCH_EVERY:-200}"

ENERGY_DESC_INCLUDE_TOKENS="${ENERGY_DESC_INCLUDE//,/ }"
ENERGY_DESC_EXCLUDE_TOKENS="${ENERGY_DESC_EXCLUDE//,/ }"
read -r -a ENERGY_DESC_INCLUDE_ARR <<< "${ENERGY_DESC_INCLUDE_TOKENS}"
read -r -a ENERGY_DESC_EXCLUDE_ARR <<< "${ENERGY_DESC_EXCLUDE_TOKENS}"
read -r -a PERTURB_LMDB_ARR <<< "${PERTURB_LMDBS}"
read -r -a VAL_PERTURB_LMDB_ARR <<< "${VAL_PERTURB_LMDBS}"
read -r -a VAL_DIAG_PERTURB_LMDB_ARR <<< "${VAL_DIAG_PERTURB_LMDBS}"

export REPO_ROOT VARIANT_ROOT VARIANT_MODULE_PREFIX PYTHON_BIN DATA_ROOT DDP_NPROC_PER_NODE
export DATA_ROOTS
export ENV_SMOKE_TRAIN_START="${ENV_SMOKE_TRAIN_START:-0}"
export ENV_SMOKE_TRAIN_END="${ENV_SMOKE_TRAIN_END:-3}"
export RUN_ENV_SMOKE="${RUN_ENV_SMOKE:-1}"
export RUN_ALLREDUCE_PREFLIGHT="${RUN_ALLREDUCE_PREFLIGHT:-1}"
export ALLREDUCE_TENSOR_MB="${ALLREDUCE_TENSOR_MB:-256}"
export ALLREDUCE_WARMUP_ITERS="${ALLREDUCE_WARMUP_ITERS:-10}"
export ALLREDUCE_ITERS="${ALLREDUCE_ITERS:-30}"
export ALLREDUCE_DTYPE="${ALLREDUCE_DTYPE:-bfloat16}"

echo "[$(timestamp)] repo_root=${REPO_ROOT}"
echo "[$(timestamp)] variant_root=${VARIANT_ROOT}"
echo "[$(timestamp)] run_root=${RUN_ROOT}"
echo "[$(timestamp)] checkpoint_dir=${CKPT_DIR}"
echo "[$(timestamp)] best_ckpt=${BEST_CKPT}"
echo "[$(timestamp)] wandb_dir=${WANDB_DIR}"
echo "[$(timestamp)] data_roots=${DATA_ROOTS}"
echo "[$(timestamp)] starts=${STARTS}"
echo "[$(timestamp)] ends=${ENDS}"
echo "[$(timestamp)] effective_global_batch=$(( BATCH_SIZE_PER_GPU * DDP_NPROC_PER_NODE ))"
echo "[$(timestamp)] dist_timeout_minutes=${DIST_TIMEOUT_MINUTES}"
echo "[$(timestamp)] resume_from=${RESUME_FROM:-<none>}"
echo "[$(timestamp)] lr=${LR}"
echo "[$(timestamp)] perturb_mix=${PERTURB_MIX}"
echo "[$(timestamp)] perturb_lmdbs=${PERTURB_LMDBS:-<none>}"
echo "[$(timestamp)] perturb_mode=${PERTURB_MODE}"
echo "[$(timestamp)] perturb_level=${PERTURB_LEVEL}"
echo "[$(timestamp)] val_perturb_mix=${VAL_PERTURB_MIX}"
echo "[$(timestamp)] val_perturb_lmdbs=${VAL_PERTURB_LMDBS:-<none>}"
echo "[$(timestamp)] val_perturb_mode=${VAL_PERTURB_MODE}"
echo "[$(timestamp)] val_perturb_level=${VAL_PERTURB_LEVEL}"
echo "[$(timestamp)] val_diag_perturb_mix=${VAL_DIAG_PERTURB_MIX}"
echo "[$(timestamp)] val_diag_perturb_lmdbs=${VAL_DIAG_PERTURB_LMDBS:-<none>}"
echo "[$(timestamp)] val_diag_perturb_mode=${VAL_DIAG_PERTURB_MODE}"
echo "[$(timestamp)] val_diag_perturb_level=${VAL_DIAG_PERTURB_LEVEL}"
echo "[$(timestamp)] loss_cutoff=${LOSS_CUTOFF}"
echo "[$(timestamp)] morse_a=${MORSE_A}"
echo "[$(timestamp)] amp_dtype=${AMP_DTYPE}"
echo "[$(timestamp)] deterministic_algorithms=${DETERMINISTIC_ALGORITHMS}"
echo "[$(timestamp)] cudnn_deterministic=${CUDNN_DETERMINISTIC}"
echo "[$(timestamp)] disable_cudnn_benchmark=${DISABLE_CUDNN_BENCHMARK}"
echo "[$(timestamp)] disable_tf32=${DISABLE_TF32}"
echo "[$(timestamp)] float32_matmul_precision=${FLOAT32_MATMUL_PRECISION:-<default>}"
echo "[$(timestamp)] fixed_train_order=${FIXED_TRAIN_ORDER}"
echo "[$(timestamp)] grad_clip_norm=${GRAD_CLIP_NORM}"
echo "[$(timestamp)] batch_order_preview_batches=${BATCH_ORDER_PREVIEW_BATCHES}"
echo "[$(timestamp)] bb_radius=${BB_RADIUS}"
echo "[$(timestamp)] stage1_max_steps=${STAGE1_MAX_STEPS}"
echo "[$(timestamp)] stage2_descriptor_ramp_steps=${STAGE2_DESCRIPTOR_RAMP_STEPS}"
echo "[$(timestamp)] stage1_signal_decay_steps=${STAGE1_SIGNAL_DECAY_STEPS}"
echo "[$(timestamp)] stage1_signal_floor=${STAGE1_SIGNAL_FLOOR}"
echo "[$(timestamp)] save_after_step=${SAVE_AFTER_STEP}"
echo "[$(timestamp)] save_last_k_checkpoints=${SAVE_LAST_K_CHECKPOINTS}"
echo "[$(timestamp)] expert_b=${MODEL_EXPERT_B}"
echo "[$(timestamp)] topk_b=${MODEL_TOPK_B}"
echo "[$(timestamp)] expert_real_layers=${MODEL_EXPERT_REAL_LAYERS}"
echo "[$(timestamp)] expert_int_layers=${MODEL_EXPERT_INT_LAYERS}"
echo "[$(timestamp)] direct_linear_noexpert=${MODEL_DIRECT_LINEAR_NOEXPERT}"
echo "[$(timestamp)] bond_negative_ratio=${BOND_NEGATIVE_RATIO}"
echo "[$(timestamp)] lambda_bond_exist=${LAMBDA_BOND_EXIST}"
echo "[$(timestamp)] lambda_bond_order=${LAMBDA_BOND_ORDER}"
echo "[$(timestamp)] energy_desc_include=${ENERGY_DESC_INCLUDE:-<all>}"
echo "[$(timestamp)] energy_desc_exclude=${ENERGY_DESC_EXCLUDE:-<none>}"
echo "[$(timestamp)] lambda_dist=${LAMBDA_DIST}"
echo "[$(timestamp)] filter_max_atoms=${FILTER_MAX_ATOMS}"
echo "[$(timestamp)] atom_budget_per_batch=${ATOM_BUDGET_PER_BATCH}"
echo "[$(timestamp)] old_pretraining_strategy=${OLD_PRETRAINING_STRATEGY}"
echo "[$(timestamp)] val_batch_size=${VAL_BATCH_SIZE}"
echo "[$(timestamp)] val_num_workers=${VAL_NUM_WORKERS}"
echo "[$(timestamp)] val_atom_budget_per_batch=${VAL_ATOM_BUDGET_PER_BATCH}"
echo "[$(timestamp)] atom_count_cache_dir=${ATOM_COUNT_CACHE_DIR}"
echo "[$(timestamp)] force_recompute_atom_counts=${FORCE_RECOMPUTE_ATOM_COUNTS}"
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
echo "[$(timestamp)] ddp_static_graph=${DDP_STATIC_GRAPH}"
echo "[$(timestamp)] find_unused_parameters=${FIND_UNUSED_PARAMETERS}"
echo "[$(timestamp)] ddp_final_barrier=${DDP_FINAL_BARRIER}"
echo "[$(timestamp)] timing_log_every=${TIMING_LOG_EVERY}"
echo "[$(timestamp)] timing_log_dir=${TIMING_LOG_DIR:-<disabled>}"
echo "[$(timestamp)] timing_sync_cuda=${TIMING_SYNC_CUDA}"
echo "[$(timestamp)] timing_collect_rank_skew=${TIMING_COLLECT_RANK_SKEW}"
echo "[$(timestamp)] wandb_watch=${WANDB_WATCH}"
echo "[$(timestamp)] wandb_watch_log_freq=${WANDB_WATCH_LOG_FREQ}"

bash "${VARIANT_ROOT}/pretrain/submit/pretrain_preflight.sh"

TORCHRUN_CMD=("${PYTHON_BIN}" -m torch.distributed.run --standalone --nproc_per_node="${DDP_NPROC_PER_NODE}")
TRAIN_CMD=(
  "${TORCHRUN_CMD[@]}"
  -m "${VARIANT_MODULE_PREFIX}pretrain.pipeline"
  --distributed
  --device cuda
  --backend nccl
  --dist_timeout_minutes "${DIST_TIMEOUT_MINUTES}"
  --data_roots "${DATA_ROOT_ARR[@]}"
  --starts "${START_ARR[@]}"
  --ends "${END_ARR[@]}"
  --random_val_size "${VAL_SIZE}"
  --split_seed "${SPLIT_SEED}"
  --split_cache_path "${SPLIT_CACHE_PATH}"
  --standardizer_ratio "${STANDARDIZER_RATIO}"
  --standardizer_cap "${STANDARDIZER_CAP}"
  --filter_max_atoms "${FILTER_MAX_ATOMS}"
  --atom_budget_per_batch "${ATOM_BUDGET_PER_BATCH}"
  --val_atom_budget_per_batch "${VAL_ATOM_BUDGET_PER_BATCH}"
  --atom_count_cache_dir "${ATOM_COUNT_CACHE_DIR}"
  --epochs "${EPOCHS}"
  --batch_size "${BATCH_SIZE_PER_GPU}"
  --val_batch_size "${VAL_BATCH_SIZE}"
  --num_workers "${NUM_WORKERS_PER_GPU}"
  --val_num_workers "${VAL_NUM_WORKERS}"
  --lr "${LR}"
  --warmup_pct "${WARMUP_PCT}"
  --seed "${SEED}"
  --grad_clip_norm "${GRAD_CLIP_NORM}"
  --batch_order_preview_batches "${BATCH_ORDER_PREVIEW_BATCHES}"
  --perturb_mix "${PERTURB_MIX}"
  --val_perturb_mix "${VAL_PERTURB_MIX}"
  --val_perturb_mode "${VAL_PERTURB_MODE}"
  --val_perturb_level "${VAL_PERTURB_LEVEL}"
  --val_diag_perturb_mix "${VAL_DIAG_PERTURB_MIX}"
  --val_diag_perturb_mode "${VAL_DIAG_PERTURB_MODE}"
  --val_diag_perturb_level "${VAL_DIAG_PERTURB_LEVEL}"
  --loss_cutoff "${LOSS_CUTOFF}"
  --morse_a "${MORSE_A}"
  --amp_dtype "${AMP_DTYPE}"
  --hidden_channels "${MODEL_HIDDEN}"
  --bb_layers "${MODEL_BB_LAYERS}"
  --bb_heads "${MODEL_BB_HEADS}"
  --bb_ff_mult "${MODEL_BB_FF_MULT}"
  --bb_radius "${BB_RADIUS}"
  --expert_number_E "${MODEL_EXPERT_E}"
  --expert_number_Q "${MODEL_EXPERT_Q}"
  --expert_number_Z "${MODEL_EXPERT_Z}"
  --expert_number_G "${MODEL_EXPERT_G}"
  --expert_number_B "${MODEL_EXPERT_B}"
  --topkE "${MODEL_TOPK_E}"
  --topkQ "${MODEL_TOPK_Q}"
  --topkZ "${MODEL_TOPK_Z}"
  --topkG "${MODEL_TOPK_G}"
  --topkB "${MODEL_TOPK_B}"
  --expert_real_layers "${MODEL_EXPERT_REAL_LAYERS}"
  --expert_int_layers "${MODEL_EXPERT_INT_LAYERS}"
  --expert_heads "${MODEL_EXPERT_HEADS}"
  --expert_ff_mult "${MODEL_EXPERT_FF_MULT}"
  --bond_negative_ratio "${BOND_NEGATIVE_RATIO}"
  --lambda_e "${LAMBDA_E}"
  --lambda_e_desc "${LAMBDA_E_DESC}"
  --lambda_q "${LAMBDA_Q}"
  --lambda_q_desc "${LAMBDA_Q_DESC}"
  --lambda_z "${LAMBDA_Z}"
  --lambda_z_desc "${LAMBDA_Z_DESC}"
  --lambda_bond_exist "${LAMBDA_BOND_EXIST}"
  --lambda_bond_order "${LAMBDA_BOND_ORDER}"
  --lambda_dist "${LAMBDA_DIST}"
  --lambda_angle "${LAMBDA_ANGLE}"
  --lambda_torsion "${LAMBDA_TORSION}"
  --validate_every_steps "${VALIDATE_EVERY_STEPS}"
  --save_latest_every_steps "${SAVE_LATEST_EVERY_STEPS}"
  --save_archive_every_steps "${SAVE_ARCHIVE_EVERY_STEPS}"
  --save_after_step "${SAVE_AFTER_STEP}"
  --save_last_k_checkpoints "${SAVE_LAST_K_CHECKPOINTS}"
  --stage1_max_steps "${STAGE1_MAX_STEPS}"
  --stage2_descriptor_ramp_steps "${STAGE2_DESCRIPTOR_RAMP_STEPS}"
  --stage1_signal_decay_steps "${STAGE1_SIGNAL_DECAY_STEPS}"
  --stage1_signal_floor "${STAGE1_SIGNAL_FLOOR}"
  --checkpoint_dir "${CKPT_DIR}"
  --save_path "${BEST_CKPT}"
  --wandb_dir "${WANDB_DIR}"
  --wandb_log_batch_every "${WANDB_LOG_BATCH_EVERY}"
  --dataloader_timeout "${DATALOADER_TIMEOUT}"
)

if [[ "${DETERMINISTIC_ALGORITHMS}" == "1" ]]; then
  TRAIN_CMD+=(--deterministic_algorithms)
fi

if [[ "${CUDNN_DETERMINISTIC}" == "1" ]]; then
  TRAIN_CMD+=(--cudnn_deterministic)
fi

if [[ "${DISABLE_CUDNN_BENCHMARK}" == "1" ]]; then
  TRAIN_CMD+=(--disable_cudnn_benchmark)
fi

if [[ "${DISABLE_TF32}" == "1" ]]; then
  TRAIN_CMD+=(--disable_tf32)
fi

if [[ -n "${FLOAT32_MATMUL_PRECISION}" ]]; then
  TRAIN_CMD+=(--float32_matmul_precision "${FLOAT32_MATMUL_PRECISION}")
fi

if [[ "${FIXED_TRAIN_ORDER}" == "1" ]]; then
  TRAIN_CMD+=(--fixed_train_order)
fi

if [[ "${TIMING_LOG_EVERY}" != "0" ]]; then
  TRAIN_CMD+=(
    --timing_log_every "${TIMING_LOG_EVERY}"
    --timing_log_dir "${TIMING_LOG_DIR}"
  )
  if [[ "${TIMING_SYNC_CUDA}" == "1" ]]; then
    TRAIN_CMD+=(--timing_sync_cuda)
  fi
  if [[ "${TIMING_COLLECT_RANK_SKEW}" == "1" ]]; then
    TRAIN_CMD+=(--timing_collect_rank_skew)
  fi
fi

if [[ "${FORCE_RECOMPUTE_ATOM_COUNTS}" == "1" ]]; then
  TRAIN_CMD+=(--force_recompute_atom_counts)
fi

if [[ "${OLD_PRETRAINING_STRATEGY}" == "1" ]]; then
  TRAIN_CMD+=(--old_pretraining_strategy)
fi

if [[ "${MODEL_DIRECT_LINEAR_NOEXPERT}" == "1" ]]; then
  TRAIN_CMD+=(--direct_linear_noexpert)
fi

if [[ "${#ENERGY_DESC_INCLUDE_ARR[@]}" -gt 0 ]]; then
  TRAIN_CMD+=(--energy_desc_include "${ENERGY_DESC_INCLUDE_ARR[@]}")
fi

if [[ "${#ENERGY_DESC_EXCLUDE_ARR[@]}" -gt 0 ]]; then
  TRAIN_CMD+=(--energy_desc_exclude "${ENERGY_DESC_EXCLUDE_ARR[@]}")
fi

if [[ "${#PERTURB_LMDB_ARR[@]}" -gt 0 ]]; then
  TRAIN_CMD+=(--perturb_lmdbs "${PERTURB_LMDB_ARR[@]}")
fi

if [[ "${#VAL_PERTURB_LMDB_ARR[@]}" -gt 0 ]]; then
  TRAIN_CMD+=(--val_perturb_lmdbs "${VAL_PERTURB_LMDB_ARR[@]}")
fi

if [[ "${#VAL_DIAG_PERTURB_LMDB_ARR[@]}" -gt 0 ]]; then
  TRAIN_CMD+=(--val_diag_perturb_lmdbs "${VAL_DIAG_PERTURB_LMDB_ARR[@]}")
fi

if [[ "${FIND_UNUSED_PARAMETERS}" == "1" ]]; then
  TRAIN_CMD+=(--find_unused_parameters)
else
  TRAIN_CMD+=(--no_find_unused_parameters)
fi

if [[ "${DDP_STATIC_GRAPH}" == "1" ]]; then
  TRAIN_CMD+=(--ddp_static_graph)
else
  TRAIN_CMD+=(--no_ddp_static_graph)
fi

if [[ "${DDP_FINAL_BARRIER}" == "1" ]]; then
  TRAIN_CMD+=(--ddp_final_barrier)
else
  TRAIN_CMD+=(--no_ddp_final_barrier)
fi

if [[ -n "${RESUME_FROM}" ]]; then
  TRAIN_CMD+=(--resume_from "${RESUME_FROM}")
fi

if [[ "${MAX_OPTIMIZER_STEPS}" != "0" ]]; then
  TRAIN_CMD+=(--max_optimizer_steps "${MAX_OPTIMIZER_STEPS}")
fi

if [[ "${DATALOADER_DEBUG}" == "1" ]]; then
  TRAIN_CMD+=(
    --dataloader_debug
    --dataloader_debug_interval "${DATALOADER_DEBUG_INTERVAL}"
    --dataloader_stall_threshold "${DATALOADER_STALL_THRESHOLD}"
    --dataloader_slow_fetch_threshold "${DATALOADER_SLOW_FETCH_THRESHOLD}"
    --dataloader_debug_dir "${DATALOADER_DEBUG_DIR}"
  )
fi

if [[ "${DDP_DEBUG}" == "1" ]]; then
  TRAIN_CMD+=(
    --ddp_debug
    --ddp_debug_interval "${DDP_DEBUG_INTERVAL}"
    --ddp_debug_stall_threshold "${DDP_DEBUG_STALL_THRESHOLD}"
    --ddp_debug_dir "${DDP_DEBUG_DIR}"
    --ddp_debug_grad_sample_size "${DDP_DEBUG_GRAD_SAMPLE_SIZE}"
  )
fi

if [[ "${USE_WANDB}" == "1" ]]; then
  TRAIN_CMD+=(
    --use_wandb
    --wandb_mode "${WANDB_MODE}"
    --wandb_project "${WANDB_PROJECT}"
    --wandb_group "${WANDB_GROUP}"
    --wandb_run_name "${WANDB_RUN_NAME}"
    --wandb_watch "${WANDB_WATCH}"
    --wandb_watch_log_freq "${WANDB_WATCH_LOG_FREQ}"
  )
else
  TRAIN_CMD+=(--wandb_mode disabled)
fi

echo
echo "========== Formal Training =========="
printf ' %q' "${TRAIN_CMD[@]}"
echo
"${TRAIN_CMD[@]}"

echo
echo "========== Finished =========="
echo "[$(timestamp)] run_root=${RUN_ROOT}"
echo "[$(timestamp)] checkpoint_dir=${CKPT_DIR}"
