# Passive F32 geometry and scalar-stage trace (DRAFT v3)

Revision v1 was not executed or published: Root AST4/Bash1 passed, but SA4 found that the frozen StageReferences.close clears pending references before take. Its eight leaves, original inventory and Root/SA4 BLOCKED evidence are preserved verbatim in N/projection_passive_stage_trace_v1_source_snapshot/SNAPSHOT.json. Revision v2 fixed the normal capture path but did not explicitly close if the original full forward raised. Root AST4/Bash1 and the SA4 v2 boundary report are preserved as v2-only source evidence. Revision v3 adds only an outer finally around the original forward/disarm/take path, so an original-forward exception propagates after explicit full observer cleanup. The original forward is still called exactly once and its original object is returned normally. Final cleanup is checked in that same GPU call path. No extra encoder, new test framework or mathematical change. Other changes are package/publication/output-path revision and this explanation.

This is one observation of the already tested and published f4652e940823141ac376eba5b6b1195f700fa692 / b2c4c6772d751ba08ac611cbe563ee2e1b40e709 candidate, exact tree411ebc59652f8aecf2d06938842aeca4782a184d. It proposes no new model, policy, tolerance or adoption. Root reviews and publishes this method before any GPU execution. These source files have not been parsed, executed or tested by the author. Final request/pins do not yet exist.

The actual4550 result is12 physical passes/36 failures,48 complete cases/192 original FP32 encoder forwards. Actual4554 CPU reproduced all1872 field/transform scalars, with0 mismatches and0 nearest-F32 unattainable components/records, without any model call/CUDA initialization. Thus neither a comparator error nor a representability barrier for those saved terminals is established. The separate closure interface is N/projection4554_Root_closure_interface_v1.json; it is a checklist, not an executed Root closure.

## Exact observation and transparency gates

Use the original CASE_SPECS (C1-0/a/b, two/three views, four H policies, both original seeds), original1492 parameter identity, unchanged fixture/three R64,t64 transforms and original absolute1e-5/rtol0 terminal criterion. The old projection_composition sets the same three already tested arithmetic modes and observes the same twelve projection ports. The new wrapper only registers short-lived reference-retaining hooks and calls each original full forward once, returning its exact original object.

For each of192 original full forwards, after the entire model returns, first remove every new hook; only then copy:
- actual scalar node embedding, each of the six scalar layer outputs, out_norm and active packed H0, all FP32;
- C1-0: each actual TiledDistanceMLP input dist-squared, six observations; C1-a/b: actual SharedGaussianPairEncoder returned distance, one observation;
- actual full physical-view positions, elements, batch, native row indices, clean44 row indices and dense native mask.

Reuse StageReferences and LocalModules.arm/disarm from the fixed1561/local-op sources. The LocalModules observer registry is filtered to distance ports before arming. Never call LocalModules.process, local replay, strict_fp64_encoder_copy, Gaussian reference forward, analysis forward installers, geometry setters or any FP64 model. geometry_policy is only the old assertion of actual six global-attention flags/cutoffNone. No pair-feature512, attention matrix, norm-internal or generic-operator tensors are saved.

Each stage is selected by the original native mask into full physical88/132 rows, not just clean44. Ordered distance pairs use the mask outer product and retain diagonal entries; denominator is sum of squared actual native graph counts. Padding contributes neither a geometry max nor a node statistic. Pair row order is graph ascending, native query then key ascending; exact batch/native-row arrays bind that reconstruction. No deduplication/mirroring. Layer masks and StageReferences packed/out_norm equality must match. Original R/t, fixture/native view identities and vector/bond edge metadata are retained through the unmodified measured-case document.

All52 new terminals/case must be bitwise equal to the actual4550 saved terminal arrays, with exact case/config/parameter/fixture identities and the same original physical pass flag. All48 are attempted before refusing downstream interpretation; a mismatch retains artifacts and produces HOLD. A new trace's hidden H0 is fresh:4550 saved terminal arrays do not contain or prove old hidden H0. Parameter/full-state identity is checked before/after each case by the reused typed state audit. Post-forward trace processing checks CPU/CUDA RNG state unchanged; it never sets RNG/global arithmetic policies.

A successful trace means transparent capture and complete ports, not physical acceptance: the original12/36 physical result is preserved separately. CPU/NativeRuntimeDense/bf16/training stochastic-dropout coverage is not claimed.

## Budget fixed before execution

There are48cases×4roles. Full physical nodes are24cases×88 plus24cases×132, each with4roles. Nine [N,512] F32 stage matrices total389,283,840B. Actual C1-0 six dist-squared and C1-a/b one distance valid-pair scalar arrays total5,703,680B. F32 position payload is253,440B. Integer/bool row and mask payload is below1MiB; no full ordered-pair index matrix is saved. Raw numerical payload is below400MiB.

Hard bounds are4MiB per uncompressed typed role NPZ and512MiB for all new trace-owned files (metadata included). One role is serialized in bounded host memory and written immediately; records retain only refs/headers. No48-model/activation cache. Original terminals remain at most512KiB/case. The unchanged original supervisor owns whole persistent2GiB, separate private2GiB, RSS28GiB, wall1100s, node21/C35 and fd9 UUID lock; worker/resource/quota admission is fresh per attempt. Extra reference lifetimes may affect allocation/kernel selection, hence the mandatory external bit gate. Do not claim that source transparency alone proves numerical transparency.

The selected old sources, control/case JSON and4550 terminal inputs remain bounded by128MiB, counted by actual physical file identity. Assembly only stats NPZ; the actual GPU worker verifies and opens the52-terminal controls, never weights/native data/SDK. The new trace payload can exceed128MiB; a future CPU analysis must declare its own explicit finite trace-input bound (at most512MiB), rather than silently reusing an old128MiB capture reader.

## Root-only minimal sequence

1. Preserve this DRAFT inventory. Root performs source/AST review and SA4 scientific review. Stage the exact eight static leaves in one preregistration directory and publish through the existing reporting/checker workflow. This is source publication, not a new QA parent or scientific pass.
2. Root runs stdlib metadata assembly (no Torch/model/NPZ reads):
   GPU_python -B N/projection_passive_stage_trace_v3_source/prepare_metadata.py --method-publication ACTUAL_ROOT_PUBLICATION.json --method-publication-sha256 ACTUAL_SHA
   The default published prefix is docs/model_v3/pre_registered_methods/projection_passive_stage_trace_v3/. The exact eight files must be in the actual receipt files map. Original candidate/full-CPU/publication validation is reused from the exact original request. Unknown actual schemas refuse.
3. Root audits the new final pins/request and uses the unchanged guard-backed submit pattern:
   GPU_python -u -B N/projection_passive_stage_trace_v3_source/launch_passive_trace_GPU_v1.py audit --source-pins-sha ACTUAL_FINAL_PINS_SHA
   GPU_python -u -B N/projection_passive_stage_trace_v3_source/launch_passive_trace_GPU_v1.py submit --source-pins-sha ACTUAL_FINAL_PINS_SHA --submission-receipt O/NEW_ATTEMPT.json
   Root alone submits after fresh quota/RAM85%/NVML no-foreign/UUID-lock/independent reservation checks. No live job or hold is modified. SB binds the original source environment and inherited supervisor child ceiling; no second UUID lock is added.

The launcher is a path/schema/output-name mechanical derivative of the original4550 launcher and SB; original guard, identity/admission, sampled85%, output/private and runtime budgets are reused. Root must confirm the exact derivative and actual publication/input schemas before use. No dispatcher, retry loop, monitor or new CPU QA parent.

## Later CPU scope (not implemented or executed here)

Use all48×four roles from these files. Compare invariant scalar geometry/node stages under the recorded transforms, with the same saved physical row/pair populations. For distance only, an optional offline F64 oracle may promote these actual saved F32 positions to distinguish input-geometry drift from distance arithmetic residual at the same component. That does not rerun an encoder and is not a whole-model/head causal attribution. No raw maximum ranking across nested stages; no layer/seed selection; no production repair, universal FP32 floor or architecture conclusion follows from this observation.
