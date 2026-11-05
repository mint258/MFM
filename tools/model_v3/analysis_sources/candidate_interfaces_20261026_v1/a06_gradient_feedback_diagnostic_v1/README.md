# A06 native-gradient feedback diagnostic — prepared, not executed

Only this new external directory is edited. Original A/export/model sources,
job457/job485 outputs, raw LMDBs and the previous gates remain unchanged.
Root alone performs CPU tests, GPU admission, submission and archive closure.
This package does not authorize or adopt fused AdamW.

## Evidence and limited question

Job4520457 used actual code `8ece64c685fe287d6863fbbe2f6f52006632a5cc`
and public preregistration `61658a4c1f472de035601dbedc17809315774784`.
It ran native S at seed0, original8M padded-cost batches/8workers,
6layers×512/8heads/ff_mult2, A4 head, tiled65536-row distance MLP and all
original checkpoint paths. FP32, TF32 off and strict deterministic controls
were active. AdamW was3e-4, betas(.9,.95), weight_decay.01, clip_norm1.
The reference uses the original automatic foreach dispatch; the only effective
candidate change is fused=True. The candidate's explicit backbone checkpoint
True matches the reference model configuration's True (option None).

457 passed20 fixed batches and completed500 updates/201216 base records,
but failed its registered trajectory test. First failure: update14,
relative loss difference0.0029128788627426007; update15:0.003909828508023756;
maximum: update379,0.18546434093044833. Child exit2, outer supervisor FAILED;
the recorded Slurm failure remains a failure. Its run_status.failure=null
means the harness completed with a failed numerical gate. It does not mean
the experiment passed. No accepted checkpoint was exported.

Job4520485 completed a separate optimizer-only synthetic-gradient diagnostic:
99 comparisons, actual `_multi_tensor_adam` versus `_fused_adam`,101 HISTORY
commits, zero native model forwards. Those results establish kernel rounding
under its synthetic inputs. They do not replay457 gradients or establish
training feedback causality. Pins retain both original evidence sets.

## Three paths and replay condition

`diagnose_native_feedback.py` implements exactly15 native updates, covering
the first failed point14. It does not rerun the20 unchanged-weight batches or
provide a500-update/complete A acceptance mode, checkpoint export or resume.

1. Reference: the unchanged memory-bounded source model and default AdamW.
2. Free fused: the unchanged performance source model and fused AdamW.
3. Shadow fused: clones the already-created reference Parameters only, with
   independent optimizer moments and parameters. It never constructs a model,
   executes forward/backward, draws random numbers or supplies model gradients.

Both real models retain457's alternating execution order: reference/free on
odd updates, free/reference on even updates. The shadow executes afterward.
Before clipping, both native gradient maps are cloned on CUDA for compact
comparison; those clones are discarded every update. The shadow aliases the
reference's **same clipped gradient Tensor objects and None entries** online.
No additional clipping or re-scaling occurs. Gradient SHA256 covers ordered
names, dtypes, shapes, None markers and every raw byte. Hashes before/after
shadow.step must match for both borrowed and reference gradients. One tensor
at a time temporarily reaches CPU memory for hashing; none is written to disk.
Actual Python Adam dispatch counters must show one original foreach and two
fused dispatches per update. Wrappers call the original functions unchanged
and restore them in finally. A CPU optimizer is never a substitute for the
diagnostic's actual CUDA fused kernel.

At every step, BOTH real-model loss, preclip gradient norm, input receipt,
sample/atom counts, valid-label counts and committed sample count must equal
the original457 saved row exactly, including scalar types. Stream bindings
also match the original manifest/loader/sampler/transport contract and snapshot
SHA. A mismatch stops with `REPLAY_MISMATCH`, preserves partial evidence and
prevents causal interpretation. Matching recorded loss/norm is a reproduction
condition; original full gradient tensors were not saved and cannot be claimed
bitwise replayed. If all15 rows match, first registered point failure must14.

Each update saves loss, gradient/parameter/moment error summaries, worst5
parameter names, all6 distance-bias summaries and fixed bias scalar values.
Every parameter and None entry is included. FP64 L2 reductions retain the
original per-parameter max(reference_norm,1e-12) denominator. Raw-gradient
1e-4 annotations do not replace the original same-weight20-batch test.
Parameter/moment errors have **no invented pass threshold**; they are
diagnostic summaries. The original loss-point threshold remains1e-3.
Global errors are explicitly diagnostic and cannot overrule a parameter gate.

Shadow-minus-reference describes optimizer evolution under an identical,
exogenous native reference-gradient sequence. Free-minus-shadow includes
gradient feedback and its interactions with parameter-dependent weight decay.
Norm differences are not an additive causal decomposition, and the tool does
not assign percentages or automatically declare the failed run's root cause.

## Bounds, provenance and expected outputs

Requires the same original5090 UUID `GPU-22e21021-e572-4562-fc51-cd8c83e74141`,
compute-0-21, Python3.11.14 original executable, Torch2.10.0+cu128/CUDA12.8,
cuDNN91002 and driver590.44.01. Actual Adam Python source hashes must also
match485's saved environment. Strict CUBLAS `:4096:8` binds before importing
Torch; original helper then enables deterministic algorithms/warn_only=False,
cuDNN deterministic/benchmarkFalse and TF32False for BOTH model paths.

Pins verify every457 repository source before/after, all selected original
evidence/configuration files, this new source/tests/README/review and the
source manifest's externally supplied raw SHA. The original manifest, frozen
protocol and shard snapshot are additionally bound by the existing native
stream. Original source files are referenced, never edited or copied into a
new scientific implementation. Python bytecode writes must be disabled.

All three paths and native loading remain subject to physical GPU85%, child
RSS28GiB, Root's declared allocation, foreign-process observations, private
scratch/cache accounting, original2GiB output cap and at most2h allocation.
There is no torch.profiler or compiled candidate. The added shadow Parameters
cost89,411,436B; its two lazily materialized Adam moments cost up to178,822,872B.
Two raw-gradient snapshots cost up to178,822,872B together. Shadow gradients
share reference storage, adding0B for gradient arrays. These are conservative
array bounds over all22,352,859 parameters; inactive parameters have no Adam
state. CUDA temporaries, hash host buffers, allocator reservation and framework
overhead are extra and are measured by the original supervisor/guards. Observed
allocator peaks and sampled RSS/private-storage maxima retain their actual
semantics. Additional storage does not justify raising85% or2GiB.

Output is fresh and external. No weights, moments or full gradients are saved.
Expected compact products: configuration/data binding,15 update JSON files,
reference/candidate histories, committed consumption/resources JSONL, summary,
run_status, before/after source closure, and one persistent offline SDK.
The standard SDK layout is root/cache plus root/wandb_data and init dir=root.
START at explicit step0, updates1..15 and COMPLETE at16 yield **17 expected
HISTORY/commit rows**, not17 native protobuf packets. Each acknowledged row is
also fsynced to history.jsonl. Native runID/config/scientific payload/explicit
step/exit0/cleanEOF must be independently verified after finish, using a full
native reader with a separate packet budget. This script leaves that readback
pending and never infers it from the mirror. SDK failures/partial files remain;
no online sync is attempted. A new archive certificate is Root's later work.

## CPU request — expected23 cases, not executed here

Run on a freshly admitted CPU node, >=16CPUs; proposed16GiB/15min, GPU hidden,
normal source pre/post hashes, closed-job/fresh quota receipt and existing
bounded CPU supervisor. Use original/current or the merged current on
PYTHONPATH for the unchanged acceptance helper, and the established deps
overlay. All tests use small CPU tensors/own pytest files. They test strict
source/history budgets, replay typing/field drift, null-gradient floor,
None semantics, parameter-only RNG-free cloning, real CPU gradient borrowing
and mutation detection. No test mocks CUDA acceptance or verifies fused CUDA.

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' \
  "$CPU_PY" -B -m pytest -q -p no:cacheprovider \
  /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/a06_gradient_feedback_diagnostic_v1/test_native_feedback.py \
  --basetemp "$SHARED_UNIT_PYTEST_ROOT"
```

## GPU request — proposal only, Root must admit and submit

After CPU results and source review, use Root's existing GPU partition/account,
same node21/physical UUID,16CPUs/32GiB. Suggested15min initial allocation,
child840s/outer880s; extend only within the original2h ceiling if Root's live
resource/I/O audit warrants it. This is one GPU training diagnostic, not a CPU
task on a GPU node. Root owns the UUID lock, quota120s receipt, exact expected
node, real memory/process census and supervisor source binding. The child takes
the standard nonblocking physical UUID lock. No self-SSH/sbatch is implemented.

```bash
PY=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
REPO=/share/home/zixiao/descriptor_analysis/MFM_model_v3_a_checkpoint
SRC=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/a06_gradient_feedback_diagnostic_v1
# PINS_RAW_SHA256 is the machine-produced frozen source_pins_v1.json SHA.
# OUT/SUPERVISOR_RECORD are fresh paths, using a single standard child root.
export CUDA_VISIBLE_DEVICES=GPU-22e21021-e572-4562-fc51-cd8c83e74141
export PYTHONDONTWRITEBYTECODE=1
"$PY" -B "$REPO/tools/model_v3/run_supervised.py" \
  --output-root "$OUT" --record "$SUPERVISOR_RECORD" \
  --gpu-uuid "$CUDA_VISIBLE_DEVICES" --wall-seconds 880 \
  --rss-limit-bytes 30064771072 --output-budget-bytes 2147483648 \
  --private-scratch-root "/tmp/mv3n_${SLURM_JOB_ID}" \
  --private-storage-budget-bytes 2147483648 -- \
  "$PY" -B "$SRC/diagnose_native_feedback.py" --repo "$REPO" \
  --code-sha 8ece64c685fe287d6863fbbe2f6f52006632a5cc \
  --source-pins "$SRC/source_pins_v1.json" --pins-sha256 "$PINS_RAW_SHA256" \
  --expected-gpu 5090 --updates 15 --wall-seconds 840 --output "$OUT"
```

The total outcome remains pending independent SDK/source/resource closure and
the actual outer Slurm terminal state. Successful execution is a15-step
diagnostic only. The failed A06 numerical acceptance and unfrozen recipe remain.
