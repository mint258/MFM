#!/usr/bin/env bash
set -euo pipefail

NODE_KEY="scale_node3_dense_h64_b3_er2"
WANDB_GROUP="scale_dense_h64_b3_er2"
COMMON_TAGS=("search_smallscale" "scale_law" "dense" "h64" "b3" "er2")

MODEL_KEY="dense_h64_b3_er2"
MODEL_HIDDEN=64
MODEL_BB_LAYERS=3
MODEL_EXPERT_REAL_LAYERS=2
MODEL_BATCH_SIZE="${MODEL_BATCH_SIZE:-24}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"
source "${SCRIPT_DIR}/scaling_common.sh"

print_env_banner
print_scale_model_banner

# Estimated runtime on the 8k anchor is about 20-24 hours total on one node.
run_default_scale_grid
