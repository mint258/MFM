# Local encoder operators — one GPU diagnostic DRAFT

This measurement follows actual1917: on the fixed historical1561 H64, all three head routes stayed below1e-5, so that cohort does not exhibit a final FP32-interface barrier. That does not establish a universal FP32 bound. Actual1838/1842 still has inherited representation drift, and current C4 remains21/48 passed,27 failed. This source does not propose or adopt a model change.

The execution model stays local `cf8ce66d97cd518ebf279b40ee20294919bb95e1`, public `f8417157dc23326d1beca8e19e4725755d9f13c6`, exact tree `2389ab046ee23f2ba92fcb61179d853dfdee8357`, all-six-layer `centered_fp32_v1` plus the existing COMPENSATED stack. Original48 cases/both seeds, parameters, head policies, two/three physical views, three transforms, geometry, domain and1e-5 absolute/0 relative physical thresholds remain fixed. Exactly192 original FP32 encoder forwards are planned. There are zero FP64 encoder forwards, no reference injected into the original path, no training, layer/seed selection, architecture change, quantization or new H0/512 API.

## Actual source boundaries

For each complete original forward, short-lived forward/pre-hooks retain Python references only. They cover both `norm1`/`norm2` in all six layers, `out_norm`, all six coupled attention modules, all six DenseFFN modules, and either the six actual C1-0 TiledDistanceMLP modules or the single shared C1-a/b Gaussian pair encoder. Original1561 StageReferences supplies full physical layout and checks actual layer masks. All own/StageReferences observer handles are removed only after the entire original model call returns, before any local replay/reference work. Bank hooks/forward override are restored using the original capture's finally rules.

The real module signatures are native `LayerNorm(input)`, `DenseFFN(x)`, `DenseGeoSelfAttention(x,pos,mask)->(out,weights)`, `SharedPairAttention(x,pair_features,distances,mask)->out`, and `SharedGaussianPairEncoder(pos,elements,mask)->(features,distances)`. C1-0 TiledDistanceMLP takes the already computed actual F32 squared-distance input. It does not expose a standalone raw distance or compensated-norm module. Gaussian is the complete distance/affine/RBF/projection/envelope block, not an isolated exp kernel. Dense attention exposes a weights port; shared attention does not, and this measurement does not invent that hidden port. Scopes are nested/overlapping, so their errors cannot be summed as exclusive causes.

LayerNorm is still native nn.LayerNorm: COMP only propagates an attribute there. DenseFFN stays Linear/SiLU/Identity(dropout0)/Linear. These facts do not predict which block dominates. The actual fixed matrix has global attention, no radius mask and no Gaussian cutoff; an unused nominal radius/center range is not activated. Unknown module/context, active dropout, non-F32 original input, different masks, unsupported kwargs or topology are rejected explicitly.

## Replay and independent reference

First, every actual original module is replayed with the retained original GPU input objects, strides, storage offsets, original FP32 weights, masks, eval/inference/noAMP and unchanged backend flags. No CPU reconstruction precedes this replay. All raw output leaves, including padding, require bitwise agreement. Shape/dtype/value hashes and actual input/layout/backend controls are saved. Numerical replay failures remain recorded; they do not select or stop the48-case matrix.

Only then an independent strict deepcopy is made, with original state membership/values checked using1561 helpers before metadata changes. Clone-only `numeric_mode` and `attention_aggregation_mode` are explicitly mapped to legacy, parameters/buffers promote to FP64 and cast back to the original raw SHA, and clone/original state remain unchanged by evaluation. The existing tested1561 `gaussian_reference_forward` removes forced .float only in that copy. No initializer or RNG draws are introduced by this copy. Original full-model state, full named-parameter identity and bank state are audited before/after every case.

This reference preserves real formulas but changes numerical algorithms as well as precision: compensated distance/reduction versus direct FP64 operations, centered AV versus direct normalized-softmax AV, native dtype-specific kernels and allocation/layout may differ. It is not an exact current-module instruction sequence with dtype changed. For shared attention, the reference promotes the **actual captured F32** pair_features/distances; it never replaces them with separately recomputed F64 Gaussian values. Every module gets its own actual inputs and no reference output is passed into another original/reference operator. LayerNorm/FFN references operate on the original full B×T dense shapes, not a compact clean44 GEMM.

## Physical population and same-component evidence

Feature statistics use actual valid native physical-view nodes. Pair statistics use the actual mask outer product within each physical graph, including diagonal; attention weights retain the head/channel population separately. Padding remains in raw replay controls but is excluded from numerical maxima/RMS. Norm/FFN validity comes from their owning layer's actual mask, final norm from the verified backbone layout. Physical88/132 nodes and6/9 graphs are retained; clean44 is only the original bank-input gate. Denominators report rows, channels/heads and components explicitly.

For each module/port and each of three transforms, save `D32=Y32_t-Y32_0`, independent-reference drift at those same actual inputs, and `D32-Dref`. Also save original/moved local errors so the signed closure is checked. At each D32, Dref and residual argmax, all five signed terms use that **same component**. Actual input drift is reported too: scalar feature/pair arguments are invariant, coordinate arguments use the original row-vector `x@R+t`. Inherited-input drift remains part of Dref. These records localize a block-level contrast; neither unlike-population maxima nor nested block residuals establish a whole-model, GEMM, softmax or LayerNorm cause.

Planned coverage is5312 scientific FP32 local replays and5312 independent FP64 module calls,4368 module-port/transform observations, all48 cases/all six layers. Existing tiny candidate/head controls run inline with separate scope; no new full regression or QA parent is requested. Actual counts and outcomes are future measurements.

## Whole-forward gates and finite files

All192 actual bank H0 raw-value SHA/dtype/shape/bytes must exactly match the closed1838 typed headers. Those bound headers are reused as existing authority; this task does not reopen the unused BANK_INPUT_STATE files. All52 external terminal arrays for every case are independently read from actual1838's existing terminal NPZ, raw-hash checked and compared bitwise, including the original physics-pass matrix and fixture/config/parameter metadata. The13 unique fields times four forwards must not be confused with52 unique fields. The new captured H0 is a fresh forward gated against1838, not a claim of access to1776 internals.

A numerical local replay, H0 or terminal mismatch retains the complete48 numerical matrix, then returns HOLD/nonzero with explicit flags. No fallback/precision/seed/tolerance change or automatic retry is added. Corrupt source/input/context or resource failure is an execution failure, not a complete scientific matrix. Physical C4 failures themselves remain recorded and do not terminate this diagnostic.

Only per-case scalar/header summaries and the reused complete terminal artifacts are written. Full module activations/operands/weights are never exported; only four roles of masked CPU tensors for the current case are retained in RAM for paired summaries and then released. No duplicate bank NPZ is produced. Both selected source/metadata/old terminal inputs and newly produced artifacts enforce separate128MiB caps; final input fit is not prefilled and assembler/worker reject over-cap scope. Original16CPU32GiB/RSS28GiB/1100s/20min allocation/whole2GiB/private2GiB/child outer-minus96MiB/fd9/public physical UUID lock and85%/quota/foreign-process guards remain unchanged. No new monitor, dispatcher or counterexample-selected cohort is introduced.

## Root-only flow

This is a source-only draft. The author has not run Python/AST/model/arrays/SDK/network/Git/Slurm. Root/SA4 source review, actual metadata assembly/audit, repository checker and public preregistration must precede a GPU submission. No actual future C0/publication/fit is asserted.

```bash
B=/share/home/zixiao/descriptor_analysis
S=$B/runs/model_v3_20261026/encoder_local_op_precision_v1_source
PY=$B/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
"$PY" -B "$S/prepare_metadata.py" --assemble
# Root then publishes the final request/source; obtain PINS_SHA from actual new source_pins_v1.json.
"$PY" -B "$S/launch_local_op_GPU_v1.py" audit --source-pins-sha "$PINS_SHA"
"$PY" -B "$S/launch_local_op_GPU_v1.py" submit --source-pins-sha "$PINS_SHA" \
  --submission-receipt "$B/runs/model_v3_20261025/encoder_local_op_precision_GPU_v1_attempt1.json"
```

The launch/SB are narrow renames of the actual1838 producer's original Root guard integration, on node21 `GPU-c35f2434-9137-9723-1af5-dc69b6295243`. Output is `O/encoder_local_op_precision_GPU_v1_JOB` with original guard/worker closure and new source-bound per-case local JSON. No old attempts, closures, source pins, models or reporting worktrees are altered.