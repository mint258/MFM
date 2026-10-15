#!/usr/bin/env bash
set -euo pipefail

NODE_KEY="node3_depth"
WANDB_GROUP="search_small_depth"
COMMON_TAGS=("search_smallscale" "depth" "scaling")
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

print_env_banner

# Estimated total runtime: about 24-30 hours.
# Goal: separate backbone depth gains from expert depth gains.

run_exp "depth_b2_er1_bs32_ep80" \
  --epochs 80 \
  --batch_size 32 \
  --hidden_channels 64 \
  --bb_layers 2 \
  --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --lambda_dist 1.0 --lambda_angle 2.0 --lambda_torsion 4.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10

run_exp "depth_b3_er1_bs32_ep80" \
  --epochs 80 \
  --batch_size 32 \
  --hidden_channels 64 \
  --bb_layers 3 \
  --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --lambda_dist 1.0 --lambda_angle 2.0 --lambda_torsion 4.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10

run_exp "depth_b4_er1_bs24_ep80" \
  --epochs 80 \
  --batch_size 24 \
  --hidden_channels 64 \
  --bb_layers 4 \
  --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --lambda_dist 1.0 --lambda_angle 2.0 --lambda_torsion 4.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10

run_exp "depth_b3_er2_bs24_ep80" \
  --epochs 80 \
  --batch_size 24 \
  --hidden_channels 64 \
  --bb_layers 3 \
  --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 \
  --expert_real_layers 2 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --lambda_dist 1.0 --lambda_angle 2.0 --lambda_torsion 4.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10
