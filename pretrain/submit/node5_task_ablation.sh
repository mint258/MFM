#!/usr/bin/env bash
set -euo pipefail

NODE_KEY="node5_task_ablation"
WANDB_GROUP="search_small_task_ablation"
COMMON_TAGS=("search_smallscale" "task_ablation" "descriptor")
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

print_env_banner

# Estimated total runtime: about 30-36 hours.
# Goal: determine which descriptor groups matter and what rough loss-weight region is worth carrying to larger data.

run_exp "task_no_desc_bs32_ep100" \
  --epochs 100 \
  --batch_size 32 \
  --hidden_channels 64 \
  --bb_layers 3 \
  --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.0 \
  --lambda_q 1.0 --lambda_q_desc 0.0 \
  --lambda_z 1.0 --lambda_z_desc 0.0 \
  --lambda_dist 1.0 --lambda_angle 2.0 --lambda_torsion 4.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10

run_exp "task_graph_desc_only_bs32_ep100" \
  --epochs 100 \
  --batch_size 32 \
  --hidden_channels 64 \
  --bb_layers 3 \
  --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.0 \
  --lambda_z 1.0 --lambda_z_desc 0.0 \
  --lambda_dist 1.0 --lambda_angle 2.0 --lambda_torsion 4.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10

run_exp "task_node_desc_only_bs32_ep100" \
  --epochs 100 \
  --batch_size 32 \
  --hidden_channels 64 \
  --bb_layers 3 \
  --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 0.0 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --lambda_dist 1.0 --lambda_angle 2.0 --lambda_torsion 4.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10

run_exp "task_full_balanced_bs32_ep100" \
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
  --stage1_loss 0.1 --stage1_max_epochs 10

run_exp "task_full_energy_heavy_bs32_ep100" \
  --epochs 100 \
  --batch_size 32 \
  --hidden_channels 64 \
  --bb_layers 3 \
  --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 \
  --expert_real_layers 1 --expert_int_layers 0 \
  --lambda_e 1.0 --lambda_e_desc 1.0 \
  --lambda_q 1.0 --lambda_q_desc 0.25 \
  --lambda_z 1.0 --lambda_z_desc 0.25 \
  --lambda_dist 1.0 --lambda_angle 2.0 --lambda_torsion 4.0 \
  --stage1_loss 0.1 --stage1_max_epochs 10
