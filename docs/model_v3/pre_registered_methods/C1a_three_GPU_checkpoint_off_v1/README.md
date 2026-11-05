# C1-a: one checkpoint-off production batch on each GPU family

This is the user-amendment-v3 engineering measurement: one3090, one4090 and one5090, each exactly one C1-a window with2warmup+5measured complete optimizer updates. No C1-0 window, ABBA, small batch, batch trimming, architecture decision, A-equivalence rerun or scientific recipe adoption is scheduled. CUDA OOM/85% resource stop is a truthful failed measurement; there is no automatic retry or smaller batch. Original4731 and all negative evidence remain unchanged.

The runner reuses4731's production SInputStream call unchanged: original B1 reference, native_s, seed0,8workers, max_padded_cost8000000 and the original snapshot d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f. It stages the first epoch0 production batch once and re-clones it for every update. batch_identity.json records the mature corpus_receipt including original logical indices/record keys/native atom counts and exact encoder-tensor digest. Root compares the three actual receipt_sha256 values and shapes before reporting a cross-card same-batch result. Different receipts are reported as mismatched, never called the same batch. No dataset version D5 is invented.

The e92b validated runtime is the functional base. Root creates the detached immutable engineering runtime MFM_model_v3_C1a_three_GPU_checkpoint_off_runtime_v1 from canonical committed866b2d4a42b36e62abda730585b66c52a011fde1; all three cards use that same root and actual commit, even while canonical receives later A/50-step integration. This is an engineering snapshot, not a numeric candidate branch. The current C-only six-layer512x8/global-attention bias=False model is used; C1-a shared pair features/per-layer projections are unchanged. Only backbone recomputation is setFalse and the existing ConfigurableDenoisingHead recomputation flag isFalse. The original non-checkpointed SharedGaussianPairEncoder remains its exact plain type; no RuntimeDense attention, performance packing, compiled path or compensated arithmetic is installed. The pair hook requires exactly one shared encoding per full optimizer step, including backward. This engineering execution does not claim that A qualification transferred to the C mathematical candidate.

Timing matches4731: CUDA-synchronized zero_grad/forward/loss/backward/clip/Adam, excluding loader,H2D,SDK and monitoring. FP32/highest/TF32off/deterministic/AdamW/original S losses/clip1 remain. Peaks include warmup and first Adam state as well as all measured updates. Tracker failures are recorded and do not turn a completed measurement into a scientific failure. They do not weaken the original physical guards.

Root alone submits. The original shared automatic-memory policy cbb3d620f90768272abb2e135a11e928a861a896e9c51c80b5bea82ec6eca245 is the sole RAM policy: ordinary64GiBsoftware/RSS56GiB, registered own concurrent budgets plus other finite declarations<85%, actual MemAvailable64GiB+node15%, unknown-own budgets reject. No fixed Slurm mem, mem0, exclusive or overcommit. Fresh worker assess repeats the same policy against actual scontrol/squeue/meminfo and requires the exact SUBMITTED registration/job/node/UUID. Existing original GPU supervisor remains6900s, whole output2GiB and independent private2GiB. Benchmark alone holds the public full-UUID lock; original foreign-process/85%VRAM/UID/kernel/quota protections remain.

Use the established Root PRE_SUBMISSION registration→assess→registry-lock/sbatch/actual binding/SUBMITTED sequence. Registration Root_source/source_pins bind this actual submission source/package; software_budget_bytes=64<<30,rss_limit_bytes=56<<30; no fake future job ID. Root retains the independent2GiB storage hold, all future storage budget/quota admission and job log budget. Do not use Native storage counters as this experiment's hold. start_C1a_S.py performs no submission, retry, registration mutation, queue wait or public/source audit. Root's chosen logical interpreter remains the original installed environment.

Required environment:

```
MODEL_V3_GPU_UUID=Root's actual full UUID
MODEL_V3_EXPECTED_NODE=Root's actual selected node
MODEL_V3_EXPECTED_GPU=3090 or4090 or5090
MODEL_V3_AUTO_REGISTRATION_ID=Root's actual one-use shared map registration
MODEL_V3_SOURCE_ROOT=/share/home/zixiao/descriptor_analysis/MFM_model_v3_C1a_three_GPU_checkpoint_off_runtime_v1
MODEL_V3_CODE_SHA=866b2d4a42b36e62abda730585b66c52a011fde1
MODEL_V3_OUT=fresh independent family/child
MODEL_V3_RECORD=fresh independent family/supervisor.json
MODEL_V3_STARTUP_JSON=fresh independent family/control/startup.json
```

After Root's fresh resource and quota admission, its existing submission code uses:

```python
env = {k:v for k,v in os.environ.items() if not k.startswith('SBATCH_')}
# Add the exact environment above, then hold the original registry mutex
# across this one sbatch and the actual immutable receipt/SUBMITTED update.
argv = ['sbatch','--parsable','--nodelist',actual_node,
        '--output',str(fresh_family/'slurm-%j.log'),
        '/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/C1a_three_GPU_checkpoint_off_v1_source/run_C1a_S.sbatch']
```

The worker runs the original supervisor with benchmark_C1a_S.py --source-root ACTUAL_ROOT --expected-gpu FAMILY --gpu-uuid ACTUAL_UUID --expected-node ACTUAL_NODE --code-sha ACTUAL_COMMIT --output FRESH_CHILD. Do not launch the child directly outside the admitted original supervisor.4090 can run first; the other two remain unsubmitted until actual resources are free. No timepoint availability is hardcoded. No original controller, running training, checkpoint, data file or frozen source is changed.

Author validation is source-only bounded reads/edits and machine SHA. No Python/AST/bash/project/test/Slurm/Git/network/SDK execution was performed by the source author. Root reviews and runs the new source. source_pins/handoff freeze no actual jobs or throughput/peak results.
