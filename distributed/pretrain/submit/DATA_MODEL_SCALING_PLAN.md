# Data-Model Scaling Plan

## Goal

Before launching expensive full-data pretraining, use nested small-data subsets to answer one focused question:

- as train set size grows, which model size is the most cost-effective choice for this codebase
- does extra capacity pay off more through width or through depth
- when does a larger dense model start to dominate the smaller alternatives

This plan uses the current `principal_valid_test` split as a first anchor and can be extended later to larger subsets from the full LMDB.

## What The Current 8k Anchor Already Says

From the completed `~8k` train runs:

- width helps monotonically: `h48 -> h64 -> h96 -> h128` keeps improving
- depth helps too: `bb_layers=2 -> 3 -> 4` improves clearly
- increasing expert depth from `er1 -> er2` is more parameter-efficient than adding MoE experts
- `2 experts + top1` did not help; `2 experts + top2` helped, but less cleanly than simply widening or deepening

Interpretation:

- for the current architecture, dense scaling should be the main line
- MoE should be treated as a challenger, not as the default scaling path

## Candidate Model Family

Use the same loss recipe across all runs so the scaling curve is not confounded by objective changes.

Recommended frozen training recipe for this batch:

- `lambda_e=1.0`
- `lambda_e_desc=0.5`
- `lambda_q=1.0`
- `lambda_q_desc=0.5`
- `lambda_z=1.0`
- `lambda_z_desc=0.5`
- `lambda_dist=1.0`
- `lambda_angle=1.0`
- `lambda_torsion=2.0`
- `stage1_max_epochs=10`

Core dense candidates:

| name | hidden | bb_layers | expert_real_layers | approx params |
| --- | ---: | ---: | ---: | ---: |
| `dense_h64_b3_er1` | 64 | 3 | 1 | `0.274M` |
| `dense_h64_b4_er1` | 64 | 4 | 1 | `0.308M` |
| `dense_h64_b3_er2` | 64 | 3 | 2 | `0.410M` |
| `dense_h96_b3_er1` | 96 | 3 | 1 | `0.593M` |
| `dense_h96_b4_er1` | 96 | 4 | 1 | `0.668M` |

Optional large ceiling:

| name | hidden | bb_layers | expert_real_layers | approx params |
| --- | ---: | ---: | ---: | ---: |
| `dense_h128_b3_er1` | 128 | 3 | 1 | `1.032M` |

Optional MoE challenger:

| name | hidden | bb_layers | expert_real_layers | experts | approx params |
| --- | ---: | ---: | ---: | --- | ---: |
| `moe2_top2_h64_b3_er1` | 64 | 3 | 1 | `2,2,2,2` | `0.411M` |

You can print the same table directly with:

```bash
py -3 pretrain/submit/estimate_model_params.py --list-presets
```

## Data Sizes

For the current `principal_valid_test` benchmark:

- validation stays fixed at `0..874`
- train subsets are nested:
  - `1k`: `875..1874`
  - `2k`: `875..2874`
  - `4k`: `875..4874`
  - `~8k`: `875..8754`

If you can cheaply sample from the full LMDB before the final large run, add a bridge stage:

- `16k`
- `32k`
- `64k`

That bridge stage is valuable because extrapolating directly from `8k` to `10M` is too long a jump.

## Make Runs Comparable

Do not keep epochs constant across data sizes.

Instead, keep the update budget roughly constant. The easiest practical approximation is:

`epochs(N) = round(80 * 7880 / N)`

That gives:

| train size | epochs | reason |
| --- | ---: | --- |
| `1k` | `640` | about the same number of optimizer updates as `8k x 80 epochs` |
| `2k` | `320` | same update budget |
| `4k` | `160` | same update budget |
| `~8k` | `80` | current anchor |

This keeps wall-clock per run in the same ballpark and avoids the usual fixed-epoch confound.

If memory allows, keep batch size fixed across the core dense family. If one config requires a smaller batch, treat it as an optional ceiling run rather than part of the strict scaling fit.

## Decision Rule

At each data size, compute two frontiers:

1. best absolute model
   - lowest `val/loss_selection`
2. best cost-effective model
   - the smallest parameter model within `3%` of that size's best `val/loss_selection`

Use the second rule for practical model selection.
Use the first rule only as an upper bound on what extra capacity could buy.

## Expected Pattern

Based on the completed `~8k` runs, the most likely trend is:

- very small subsets prefer `0.27M - 0.31M`
- mid-small subsets move toward `0.41M - 0.59M`
- once data size keeps increasing, width should beat MoE and likely continue paying off beyond `0.6M`

So the most likely full-data extrapolation today is:

- efficiency-oriented dense baseline: `h96 / bb4 / er1`
- accuracy-oriented dense baseline: `h128 / bb3 / er1`
- MoE remains a challenger only after the dense baseline is established

## Minimal Two-Phase Run Plan

Phase A: use current benchmark only

- sizes: `1k / 2k / 4k / ~8k`
- models: the 5 dense candidates above

Phase B: bridge toward larger data

- sizes: `16k / 32k / 64k`
- models: only the top 3 from Phase A

That is enough to fit a practical small-data scaling curve without spending large-data training budget too early.
