# Existing Native-S safe-checkpoint future-state audit

Prepared source only. No Python, native payload, SDK, model or job was executed
to prepare it. Root merges this audit into the single supplemental CPU readiness
allocation together with the already-frozen SDK reader and metadata accounting.
Expected inventory tests:4; actual collection/results remain unknown.

Metadata preparation (does not open/hash payload.pt):

```bash
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
SRC=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_s_precision_cp_inventory_v1
$PY -B "$SRC/prepare_inputs.py" --output NEW_INPUT_DIRECTORY
```

This emits fp32_future_inputs.json and bf16_future_inputs.json using the actual
closed v8 jobs4521331/4521332, raw sacct observations, COMPLETE headers, source
refs and original metadata. These manifests use native_S_evidence_inputs_v2,
role future_state, and exact artifacts profile_result/checkpoint. It does not
generate a success receipt or claim science admission.

Inside the owned>=16CPU supplemental allocation, CUDA hidden:

```bash
CUDA_VISIBLE_DEVICES= PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "$PY" -B -m pytest \
  "$SRC/test_inventory.py" -q -p no:cacheprovider \
  -o tmp_path_retention_policy=failed --basetemp=NEW_SHARED_PYTEST_ROOT
CUDA_VISIBLE_DEVICES= "$PY" -B "$SRC/inventory.py" \
  --inputs NEW_INPUT_DIRECTORY/fp32_future_inputs.json --output NEW_FP32_AUDIT
CUDA_VISIBLE_DEVICES= "$PY" -B "$SRC/inventory.py" \
  --inputs NEW_INPUT_DIRECTORY/bf16_future_inputs.json --output NEW_BF16_AUDIT
```

Run these sequentially. Estimate per payload:10–30s CPU wall,<2GiB RSS,<2MiB
output; those are unmeasured estimates, subject to the shared1500s/RSS12GiB/
whole2GiB supervisor. No new independent QA parent is required per output.

The reader validates UID/ordinary-file/nlink1/ancestry/size/hash and inode/time
stability, verifies uncompressed bounded Torch ZIP framing, uses only direct
torch.load(map_location=cpu,weights_only=True), and rehashes the original after
load. There is no unsafe fallback or allowlist extension. Every tensor output
is shape/dtype/numel/byte count only; no tensor values, member IDs, parameter
values or targets are written. The original checkpoint is never copied/changed.

Outputs are shape_report.json (native_S_actual_safe_checkpoint_shape_v2),
future_bound.json (native_S_frozen_state_growth_bound_v2), and RESULT.json.
Unknown schema/state/variant, source drift or a conservative bound exceeding
the unchanged384MiB CP cap causes nonzero exit and FAILED.json. None is treated
as zero. A child audit does not create native_S_future_state_projection_v2 or
its own parent-C0 assertion. After the one actual readiness parent closes,
Root can bind the raw argv/inputs/source/actual terminal to these two refs and
mechanically assemble the existing NativeV2 projection format.

The conservative calculation adds two fp32 moments for every model-state
element again, including buffers/already initialized states, plus all possible
step scalars. It reserves4KiB per future tensor/container, four containers per
model-state entry, plus4MiB fixed serialization reserve. This deliberately
exceeds the pinned Torch2.10 stored-ZIP header/alignment and restricted scalar
pickle metadata framing. Provider growth includes41 scalar curve points capped
at16KiB each,216 saved-update entries with256B each, and another4MiB for scalar
clock/scheduler/RNG/unchanged contract metadata. Source checks bind the actual
Native.save, safe-checkpoint, sampler and AdamW factory implementations. The
current fixed scalar sampler has no serialized corpus-sized permutation/cache
or speculative-prefetch queue. The result remains an upper bound, not a new
training result, numerical gate, D5 authority or permission to alter the plan.

Original20000updates,0:500:20000 validation grid,10000/20000 fixed checkpoints,
seed0/1 and same physical GPU controls remain. This source does not resume the
PROFILE_ONLY u20 weights as a science prefix.
