#!/usr/bin/env bash
set -euo pipefail

NODE_KEY="node4_geom_stage"
WANDB_GROUP="search_small_geom_stage"
COMMON_TAGS=("search_smallscale" "geometry" "stage_schedule")
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

print_env_banner

# Estimated total runtime: about 26-30 hours.
# Goal: baseline run showed a clear validation jump when stage-1 started at epoch 10.
# This node isolates whether the issue comes from stage timing or angle/torsion weight magnitude.

run_exp "geom_s10_a0_t0_bs32_ep100" \
  --epochs 100 \
  --batch_size 32 \
  --hidden_channels 64 \
  --bb_layers 3 \
  --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --lambda_dist 1.0 --lambda_angle 0.0 --lambda_torsion 0.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10

run_exp "geom_s10_a1_t2_bs32_ep100" \
  --epochs 100 \
  --batch_size 32 \
  --hidden_channels 64 \
  --bb_layers 3 \
  --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --lambda_dist 1.0 --lambda_angle 1.0 --lambda_torsion 2.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10

run_exp "geom_s20_a2_t4_bs32_ep100" \
  --epochs 100 \
  --batch_size 32 \
  --hidden_channels 64 \
  --bb_layers 3 \
  --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --lambda_dist 1.0 --lambda_angle 2.0 --lambda_torsion 4.0 \
  --stage1_loss 0.1 --stage1_max_epochs 20

run_exp "geom_s20_a1_t2_bs32_ep100" \
  --epochs 100 \
  --batch_size 32 \
  --hidden_channels 64 \
  --bb_layers 3 \
  --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --lambda_dist 1.0 --lambda_angle 1.0 --lambda_torsion 2.0 \
  --stage1_loss 0.1 --stage1_max_epochs 20
