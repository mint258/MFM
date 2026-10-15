# Small-Data Search Plan

## Baseline facts from `run-9i2x9171`

- Baseline config:
  - `hidden_channels=64`
  - `bb_layers=3`
  - `expert_number_E/Q/Z/G=1/1/1/1`
  - `lambda_e_desc=lambda_q_desc=lambda_z_desc=0.5`
  - `lambda_dist/lambda_angle/lambda_torsion=1/2/4`
  - `stage1_max_epochs=10`
- The recorded run stayed healthy on CUDA and did not show overfitting in the observed window.
- Validation selection loss improved from about `10.81` at epoch 1 to `4.31` at epoch 19.
- Stage transition happened at epoch `10` because of `stage1_max_epochs`, not because geometry reached `stage1_loss`.
- Validation selection loss jumped upward at epoch `11` right after angle/torsion were enabled, then kept improving again.
- Easy tasks:
  - charge base task
  - element base task
  - most node-level descriptor heads except `estate_type` and `min_ring_size`
- Hard tasks:
  - energy
  - geometry
  - several graph descriptors such as `ExactMolWt`, `BertzCT`, `LabuteASA`, `MolMR`, `NumValenceElectrons`

## First-Batch Priority

1. `MoE` effectiveness must be tested first because the current baseline is effectively a non-MoE control.
2. Width and depth scaling are the right place to fit a rough small-data scaling curve.
3. Stage timing and geometry loss weights are high priority because the baseline showed a clear stage-transition shock.
4. Descriptor ablation is needed before large-data runs so you do not carry unnecessary auxiliary tasks into the expensive phase.
5. Optimizer fine-tuning is intentionally deferred to the next batch because the baseline run is already stable and monotonic.

## Output Layout

Each submission script writes to:

- `log/search/<node_key>/`
- `test_ckpt/search/<node_key>/`
- `wandb/search/<node_key>/`

Each node keeps one scientific question family, so later analysis stays clean.

## Suggested Launch

From repo root or any working directory:

```bash
GPU_ID=0 PYTHON_BIN=python bash pretrain/submit/node1_moe_effectiveness.sh
GPU_ID=0 PYTHON_BIN=python bash pretrain/submit/node2_width_scaling.sh
GPU_ID=0 PYTHON_BIN=python bash pretrain/submit/node3_depth_scaling.sh
GPU_ID=0 PYTHON_BIN=python bash pretrain/submit/node4_geom_stage_search.sh
GPU_ID=0 PYTHON_BIN=python bash pretrain/submit/node5_task_ablation.sh
```

If your `python` is not already the `chemprop` environment interpreter, set `PYTHON_BIN` explicitly.
