#!/usr/bin/env bash
set -euo pipefail

: "${MODEL_KEY:?MODEL_KEY is required}"
: "${MODEL_HIDDEN:?MODEL_HIDDEN is required}"
: "${MODEL_BB_LAYERS:?MODEL_BB_LAYERS is required}"
: "${MODEL_EXPERT_REAL_LAYERS:?MODEL_EXPERT_REAL_LAYERS is required}"

MODEL_BATCH_SIZE="${MODEL_BATCH_SIZE:-32}"
MODEL_EXPERT_E="${MODEL_EXPERT_E:-1}"
MODEL_EXPERT_Q="${MODEL_EXPERT_Q:-1}"
MODEL_EXPERT_Z="${MODEL_EXPERT_Z:-1}"
MODEL_EXPERT_G="${MODEL_EXPERT_G:-1}"
MODEL_TOPK_E="${MODEL_TOPK_E:-1}"
MODEL_TOPK_Q="${MODEL_TOPK_Q:-1}"
MODEL_TOPK_Z="${MODEL_TOPK_Z:-1}"
MODEL_TOPK_G="${MODEL_TOPK_G:-1}"

print_scale_model_banner() {
  echo "model_key=${MODEL_KEY}"
  echo "model_hidden=${MODEL_HIDDEN}"
  echo "model_bb_layers=${MODEL_BB_LAYERS}"
  echo "model_expert_real_layers=${MODEL_EXPERT_REAL_LAYERS}"
  echo "model_batch_size=${MODEL_BATCH_SIZE}"
  echo "model_experts=${MODEL_EXPERT_E},${MODEL_EXPERT_Q},${MODEL_EXPERT_Z},${MODEL_EXPERT_G}"
  echo "model_topk=${MODEL_TOPK_E},${MODEL_TOPK_Q},${MODEL_TOPK_Z},${MODEL_TOPK_G}"
}

run_scale_subset() {
  local subset_tag="$1"
  local train_start="$2"
  local train_end="$3"
  local epochs="$4"
  shift 4

  run_exp "${MODEL_KEY}_${subset_tag}_ep${epochs}" \
    --starts "${train_start}" \
    --ends "${train_end}" \
    --val_starts 0 \
    --val_ends 874 \
    --epochs "${epochs}" \
    --batch_size "${MODEL_BATCH_SIZE}" \
    --hidden_channels "${MODEL_HIDDEN}" \
    --bb_layers "${MODEL_BB_LAYERS}" \
    --expert_number_E "${MODEL_EXPERT_E}" \
    --expert_number_Q "${MODEL_EXPERT_Q}" \
    --expert_number_Z "${MODEL_EXPERT_Z}" \
    --expert_number_G "${MODEL_EXPERT_G}" \
    --topkE "${MODEL_TOPK_E}" \
    --topkQ "${MODEL_TOPK_Q}" \
    --topkZ "${MODEL_TOPK_Z}" \
    --topkG "${MODEL_TOPK_G}" \
    --expert_real_layers "${MODEL_EXPERT_REAL_LAYERS}" \
    --expert_int_layers 0 \
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
    "$@"
}

run_default_scale_grid() {
  run_scale_subset "n1k" 875 1874 640 "$@"
  run_scale_subset "n2k" 875 2874 320 "$@"
  run_scale_subset "n4k" 875 4874 160 "$@"
  run_scale_subset "n8k" 875 8754 80 "$@"
}
