#!/usr/bin/env bash

# Submit example:
#   sbatch --export=ALL,REPO_ROOT_OVERRIDE=$PWD,SKIP_CONDA=1,PYTHON_BIN=/share/home/202264640132/.conda/envs/torchgpu/bin/python pretrain/submit/g01n02_pretrain_ddp_timing_100steps.sbatch

#SBATCH --job-name=pretrain-ddp-timing-100
#SBATCH --partition=gpuA800
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --gres=gpu:4
#SBATCH --mem=256G
#SBATCH --time=04:00:00
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_DIR="pretrain/submit"
export BATCH_SIZE_PER_GPU="${BATCH_SIZE_PER_GPU:-8}"
export FILTER_MAX_ATOMS="${FILTER_MAX_ATOMS:-196}"
export ATOM_BUDGET_PER_BATCH="${ATOM_BUDGET_PER_BATCH:-1024}"
export NUM_WORKERS_PER_GPU="${NUM_WORKERS_PER_GPU:-8}"
export VALIDATE_EVERY_STEPS="${VALIDATE_EVERY_STEPS:-6000}"
export SAVE_LATEST_EVERY_STEPS="${SAVE_LATEST_EVERY_STEPS:-6000}"
export SAVE_ARCHIVE_EVERY_STEPS="${SAVE_ARCHIVE_EVERY_STEPS:-10000}"
export STAGE1_MAX_STEPS="${STAGE1_MAX_STEPS:-100000000}"
export STAGE2_DESCRIPTOR_RAMP_STEPS="${STAGE2_DESCRIPTOR_RAMP_STEPS:-0}"
export LR="${LR:-1e-4}"
export WARMUP_PCT="${WARMUP_PCT:-0.08}"
export LAMBDA_E="${LAMBDA_E:-4.0}"
export LAMBDA_Q="${LAMBDA_Q:-1.0}"
export LAMBDA_Z="${LAMBDA_Z:-0.1}"
export LAMBDA_BOND_EXIST="${LAMBDA_BOND_EXIST:-0.0}"
export LAMBDA_BOND_ORDER="${LAMBDA_BOND_ORDER:-0.0}"
export LAMBDA_ANGLE="${LAMBDA_ANGLE:-0}"
export LAMBDA_TORSION="${LAMBDA_TORSION:-0}"
export LAMBDA_E_DESC="${LAMBDA_E_DESC:-0.20}"
export LAMBDA_Q_DESC="${LAMBDA_Q_DESC:-0.25}"
export LAMBDA_Z_DESC="${LAMBDA_Z_DESC:-0.25}"
export STAGE1_SIGNAL_FLOOR="${STAGE1_SIGNAL_FLOOR:-0.3}"
export AMP_DTYPE="${AMP_DTYPE:-bf16}"
export MODEL_HIDDEN="${MODEL_HIDDEN:-256}"
export MODEL_BB_LAYERS="${MODEL_BB_LAYERS:-4}"
export MODEL_BB_HEADS="${MODEL_BB_HEADS:-4}"
export MODEL_BB_FF_MULT="${MODEL_BB_FF_MULT:-4}"
export MODEL_EXPERT_REAL_LAYERS="${MODEL_EXPERT_REAL_LAYERS:-2}"
export MODEL_EXPERT_INT_LAYERS="${MODEL_EXPERT_INT_LAYERS:-0}"
export MODEL_EXPERT_HEADS="${MODEL_EXPERT_HEADS:-4}"
export MODEL_EXPERT_FF_MULT="${MODEL_EXPERT_FF_MULT:-2}"
export DATALOADER_DEBUG="${DATALOADER_DEBUG:-0}"
export DDP_DEBUG="${DDP_DEBUG:-0}"
export EPOCHS="${EPOCHS:-1}"
export VAL_PERTURB_MIX="${VAL_PERTURB_MIX:-clean:@1}"
export VAL_DIAG_PERTURB_MIX="${VAL_DIAG_PERTURB_MIX:-topo:0.3@1}"
export WANDB_WATCH="${WANDB_WATCH:-none}"
export WANDB_RUN_NAME="${WANDB_RUN_NAME:-benchmark_with_old_MFM_architecture_timing100}"

export MAX_OPTIMIZER_STEPS="${MAX_OPTIMIZER_STEPS:-100}"
export VAL_SIZE="${VAL_SIZE:-0}"
export USE_WANDB="${USE_WANDB:-0}"
export WANDB_MODE="${WANDB_MODE:-disabled}"
export RUN_ENV_SMOKE="${RUN_ENV_SMOKE:-0}"
export RUN_ALLREDUCE_PREFLIGHT="${RUN_ALLREDUCE_PREFLIGHT:-0}"
export TIMING_LOG_EVERY="${TIMING_LOG_EVERY:-1}"
export TIMING_SYNC_CUDA="${TIMING_SYNC_CUDA:-1}"
export TIMING_COLLECT_RANK_SKEW="${TIMING_COLLECT_RANK_SKEW:-1}"

if [[ -z "${RUN_TAG:-}" ]]; then
  export RUN_TAG="timing100_${SLURM_JOB_ID:-manual}"
fi

if [[ -z "${TIMING_LOG_DIR:-}" ]]; then
  if [[ -n "${RUN_ROOT:-}" ]]; then
    export TIMING_LOG_DIR="${RUN_ROOT}/timing"
  fi
fi

echo "Launching 100-step timing benchmark with MAX_OPTIMIZER_STEPS=${MAX_OPTIMIZER_STEPS}"
echo "Timing logs will be written under TIMING_LOG_DIR=${TIMING_LOG_DIR:-<auto under run_root>}"

exec bash "${SCRIPT_DIR}/g01n02_pretrain_ddp_formal.sbatch"
