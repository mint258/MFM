#!/usr/bin/env bash
set -euo pipefail

NODE_KEY="node1_moe"
WANDB_GROUP="search_small_moe"
COMMON_TAGS=("search_smallscale" "moe" "routing")
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

print_env_banner

# Estimated total runtime: about 24-32 hours on a 24 GB GPU.
# Goal: determine whether multi-expert routing helps beyond the single-expert baseline.

run_exp "moe_e1q1z1g1_k1111_h64_l3_bs32_ep80" \
  --epochs 80 \
  --batch_size 32 \
  --hidden_channels 64 \
  --bb_layers 3 \
  --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 \
  --topkE 1 --topkQ 1 --topkZ 1 --topkG 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --lambda_dist 1.0 --lambda_angle 2.0 --lambda_torsion 4.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10

run_exp "moe_e2q2z2g2_k1111_h64_l3_bs24_ep80" \
  --epochs 80 \
  --batch_size 24 \
  --hidden_channels 64 \
  --bb_layers 3 \
  --expert_number_E 2 --expert_number_Q 2 --expert_number_Z 2 --expert_number_G 2 \
  --topkE 1 --topkQ 1 --topkZ 1 --topkG 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --lambda_dist 1.0 --lambda_angle 2.0 --lambda_torsion 4.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10

run_exp "moe_e2q2z2g2_k2222_h64_l3_bs24_ep80" \
  --epochs 80 \
  --batch_size 24 \
  --hidden_channels 64 \
  --bb_layers 3 \
  --expert_number_E 2 --expert_number_Q 2 --expert_number_Z 2 --expert_number_G 2 \
  --topkE 2 --topkQ 2 --topkZ 2 --topkG 2 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --lambda_dist 1.0 --lambda_angle 2.0 --lambda_torsion 4.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10

run_exp "moe_e2q2z1g2_k1111_h64_l3_bs24_ep80" \
  --epochs 80 \
  --batch_size 24 \
  --hidden_channels 64 \
  --bb_layers 3 \
  --expert_number_E 2 --expert_number_Q 2 --expert_number_Z 1 --expert_number_G 2 \
  --topkE 1 --topkQ 1 --topkZ 1 --topkG 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --lambda_dist 1.0 --lambda_angle 2.0 --lambda_torsion 4.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10
