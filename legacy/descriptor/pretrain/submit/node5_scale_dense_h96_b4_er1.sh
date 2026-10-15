#!/usr/bin/env bash
set -euo pipefail

NODE_KEY="scale_node5_dense_h96_b4_er1"
WANDB_GROUP="scale_dense_h96_b4_er1"
COMMON_TAGS=("search_smallscale" "scale_law" "dense" "h96" "b4" "er1")

MODEL_KEY="dense_h96_b4_er1"
MODEL_HIDDEN=96
MODEL_BB_LAYERS=4
MODEL_EXPERT_REAL_LAYERS=1
MODEL_BATCH_SIZE="${MODEL_BATCH_SIZE:-24}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"
source "${SCRIPT_DIR}/scaling_common.sh"

print_env_banner
print_scale_model_banner

# Estimated runtime on the 8k anchor is about 20-24 hours total on one node.
run_default_scale_grid
