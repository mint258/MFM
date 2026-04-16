#!/usr/bin/env bash
set -euo pipefail

NODE_KEY="node2_width"
WANDB_GROUP="search_small_width"
COMMON_TAGS=("search_smallscale" "width" "scaling")
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

print_env_banner

# Estimated total runtime: about 24-30 hours.
# Goal: fit a small-data width scaling curve without stepping beyond likely 24 GB memory limits.

run_exp "width_h48_l3_er1_bs32_ep80" \
  --epochs 80 \
  --batch_size 32 \
  --hidden_channels 48 \
  --bb_layers 3 \
  --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --lambda_dist 1.0 --lambda_angle 2.0 --lambda_torsion 4.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10

run_exp "width_h64_l3_er1_bs32_ep80" \
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

run_exp "width_h96_l3_er1_bs24_ep80" \
  --epochs 80 \
  --batch_size 24 \
  --hidden_channels 96 \
  --bb_layers 3 \
  --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --lambda_dist 1.0 --lambda_angle 2.0 --lambda_torsion 4.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10

run_exp "width_h128_l3_er1_bs16_ep80" \
  --epochs 80 \
  --batch_size 16 \
  --hidden_channels 128 \
  --bb_layers 3 \
  --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --lambda_dist 1.0 --lambda_angle 2.0 --lambda_torsion 4.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10
