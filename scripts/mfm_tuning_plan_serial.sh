#!/usr/bin/env bash
set -euo pipefail

# Serial MFM tuning plan (one experiment finishes before the next starts).
# Keep these fixed as requested:
#   --pretrained_ckpt ckpt/AE_test.pth_epoch_001.pt
#   --data_dir data
#   --folds 1-10
#   --cache_dir mfm_results/cache/train_small/

PYTHON_BIN="${PYTHON_BIN:-python}"
TRAIN_PY="MFM/admet/train.py"

FIXED_ARGS=(
  --pretrained_ckpt ckpt/AE_test.pth_epoch_001.pt
  --data_dir data
  --folds 1-10
  --cache_dir mfm_results/cache/train_small/
)

COMMON_ARGS=(
  --mode mt
  --device cuda
  --embedding_mode backbone
  --epochs 400
  --batch_size 16
  --cache_mode global
  --max_train_rows 0
  --max_val_rows 0
  --max_test_rows 0
)

run_exp() {
  local name="$1"
  shift
  local out_dir="mfm_results/runs/tune_plan/${name}"
  local log_file="logs/${name}.log"

  mkdir -p "${out_dir}" "logs"
  echo "[RUN] ${name}"
  echo "      output: ${out_dir}"
  echo "      log:    ${log_file}"

  "${PYTHON_BIN}" "${TRAIN_PY}" \
    "${FIXED_ARGS[@]}" \
    "${COMMON_ARGS[@]}" \
    --output_dir "${out_dir}" \
    "$@" 2>&1 | tee "${log_file}"
}

# -------------------------------
# Group A: around the best current setting (MFM_hp)
# -------------------------------
run_exp "mfm_a0_ref_hp" \
  --lr 5e-4 --weight_decay 0 --dropout 0 --head_layers 2 --hidden_dim 1024 --patience 30

run_exp "mfm_a1_tiny_wd" \
  --lr 5e-4 --weight_decay 1e-6 --dropout 0 --head_layers 2 --hidden_dim 1024 --patience 30

run_exp "mfm_a2_tiny_dropout" \
  --lr 5e-4 --weight_decay 0 --dropout 0.03 --head_layers 2 --hidden_dim 1024 --patience 30

run_exp "mfm_a3_tiny_wd_dropout" \
  --lr 5e-4 --weight_decay 1e-6 --dropout 0.03 --head_layers 2 --hidden_dim 1024 --patience 30

# -------------------------------
# Group B: optimization schedule to break late plateau
# -------------------------------
run_exp "mfm_b1_cosine_decay" \
  --lr 5e-4 --weight_decay 1e-6 --dropout 0.03 --head_layers 2 --hidden_dim 1024 --patience 40 \
  --warmup_epochs 20 --init_lr 1e-4 --max_lr 8e-4 --final_lr 5e-5

run_exp "mfm_b2_lower_lr" \
  --lr 3e-4 --weight_decay 1e-6 --dropout 0.03 --head_layers 2 --hidden_dim 1024 --patience 40

# -------------------------------
# Group C: capacity and task-weight diagnostics
# -------------------------------
run_exp "mfm_c1_smaller_head" \
  --lr 5e-4 --weight_decay 1e-6 --dropout 0.03 --head_layers 2 --hidden_dim 768 --patience 40

run_exp "mfm_c2_sqrt_task_weights" \
  --lr 5e-4 --weight_decay 1e-6 --dropout 0.03 --head_layers 2 --hidden_dim 1024 --patience 40 \
  --task_weights "1.009,1.000,1.168,1.065,1.542,1.540,1.985,2.293,4.806"

run_exp "mfm_c3_equal_task_weights" \
  --lr 5e-4 --weight_decay 1e-6 --dropout 0.03 --head_layers 2 --hidden_dim 1024 --patience 40 \
  --task_weights "1,1,1,1,1,1,1,1,1"

echo "[DONE] All tuning runs finished."
