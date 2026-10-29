# Clean C architecture integration — 2026-10-29

This is an implementation handoff on the isolated clean-integration branch,
based on dbe275e6558c401116159b2e230961d082d07842. Source has been edited and
reviewed as text only. The author did not execute Python, AST, model/tests, Git,
Slurm, SDK, scientific arrays or checkpoint payloads. Actual new QA and scientific
results are unknown and belong to Root's later exact-source validation.

## C-only parameter policy

New C configurations explicitly set backbone.distance_bias_projection_bias=false.
The old registry remains historical and unchanged; the new bias-free registry
declares the new C source identity. architecture_plan includes False in the common
parameters of all 20 initial trials. Missing/True retains the original default.
A/default/runtime options and their old checkpoint identity are not converted to
the C policy.

C1-0 constructs each original Linear, consumes its original initialization RNG
stream, and only then removes the final eight-head distance-MLP bias Parameter.
Six layers remove 48 scalars. All remaining common parameter values and RNG draws
are preserved. C1-a/b's per-head pair_projection was already bias-free, so no
additional parameter is removed there. pair_encoder.project[2].bias is retained.

The replacement helper imports only ordinary Torch/common Linear. It has no
dependency on any stopped numeric, projection, geometry, centering, FFN, residual,
or dipole compensation module. Its guard checks plain strided FP32, AMP disabled,
highest matmul precision, disabled TF32, declared classes/layout, and the actual
bias=None projections. Existing arithmetic, H0 shape512, heads and labels are
unchanged. Compile/Native/performance and explicit training-execution replacements
for bias-free C are rejected, including before install_training_performance can
mutate a model. No unsupported optimized route silently falls back.

Dense/Shared backbone, layer and configuration declarations must agree.
SharedPair extra_state adds False only for the new opt-in; absent/default legacy
keeps the old extra_state. C1-0's missing six state keys distinguish strict state
loading, while full source-model/trainer/bridge configuration binds the explicit
policy. C1-a/b also bind the conditional extra_state even though tensor membership
does not change. Existing default CP/resume and matched-random/H0 interfaces are
reused; no stopped numeric checkpoint contract is imported.

Deleting a common attention-logit constant is an exact real-function identity.
It is not a promise of FP32 bitwise output/gradient identity or a physical PASS.

## Stage5 configuration path

v3_architecture_readiness.compile_trial compiles only the exact 20 initial
architecture_plan trials. It retains6x512x8, A4, PM7/all authorized conformations,
the actual selected sample budget, original240k TRAIN proxy, fixed B0/AdamW/
clip/cosine baseline, and source-bound policy/evidence. C1, views, per-field/common
head forms and pooling become actual model/proxy configuration values.
Unresolved selected-C1/C3 strings, arbitrary trials/overrides/repeats, engineering
templates, unsupported execution, and changed common template identity are refused.

The approved pooling_overrides keyword on V3HeadBank supplies the actual last
H1/P learned-pooling trial. It accepts only ordinary graph-scalar fields and
registry/learned values. The learned override creates the existing sum/mean mixer
without mutating FieldSpec, targets, units, registry hashes or normalization.
Missing/empty overrides preserve old default behavior, tensor keys and extra_state.
Nonempty overrides are explicit extra_state/config semantics and strict restore
must match. Only P graph-scalar fields are overridden by the final registered
pooling trial; vector/tensor/atom fields are not repurposed as scalar labels.

resolve_inputs reuses inspect_run, verify_global_seed_sd, choose_c1 and choose_c3.
It rechecks actual closed panel/checkpoint/execution evidence, the existing
preregistered one-SD/timing/auxiliary rules, and that source runs actually declared
False and the corresponding distance/view/head/condition. Its input document
model_v3_architecture_resolution_inputs_v1 transports policy SHA, panel reference,
panel preregistration commit, global_seed_sd, and optional C1/C3 measurement maps.
Timing references point to closed scalar rows containing
seconds_per_million_samples/gpu_uuid/run_ids; auxiliary rows contain
value/population_sha256/run_ids/scope. Raw hashes supply the original rule
dataclasses' source_sha256. These rows are input transport, not new job or
scientific-acceptance certificates. Missing actual observations are never filled.

prepare_trial requires the actual bound authoritative_proxy base, registered
policy, existing validate_request and bind_inputs checks, and exact240k TRAIN.
For dependent trials it recomputes the supplied selections from their original
sources. It writes only configuration.json, request.UNADMITTED.json and PREPARED:
scope=comparison, empty registrations, Root_admission=None, no inherited durable
reservation. No unresolved planned placeholders are copied into the request.
Existing proxy finalize_training_request remains the only final consumer path.
No new finalization, submission, ACK or resource mechanism is introduced.

The new configurations are not admitted merely because they compile.
D1/D2/D3/D4/D5, selected budget, actual platform/capacity, panel/rules registration,
new FP32 physical acceptance, source/CP/H0 compatibility and fresh Root operational
admission remain mandatory. Current failed FP32-v2 evidence stays failed.
The separate FP64 complete48 mathematics PASS is not an FP32 PASS. Previously
passed old-source C/A/tensor CPU tests do not certify these new combined bytes.

## Files and validation handoff

Owned files:

- current/phychem_mfm/model/v3_distance_bias.py (new ordinary C helper)
- current/phychem_mfm/model/attention.py
- current/phychem_mfm/model/backbone.py
- current/phychem_mfm/model/shared.py
- current/phychem_mfm/model/v3_architecture.py
- current/phychem_mfm/model/v3_performance.py
- current/phychem_mfm/model/v3_heads.py (approved pooling keyword only)
- current/phychem_mfm/phase1/v3_proxy_plan.py (stage5 False only)
- current/phychem_mfm/phase1/v3_architecture_readiness.py (new resolver)
- configs/model_v3/architecture_candidates_bias_free_v1.json
- current/tests/test_model_v3_clean_C_integration.py
- current/tests/test_model_v3_architecture_readiness.py
- docs/model_v3/C_CLEAN_INTEGRATION_20261029.md

factory/config/recipe/proxy runner, original registry, old tests, all old evidence
and stopped candidate worktrees are unchanged. No compensated module was copied.

New tests cover exact common parameter/RNG mapping and removal population,
actual C forwards, ordinary state/config restore/default compatibility, sealer
identity, runtime/type/AMP refusal, actual learned-mixer value/gradient and registry
immutability, default HeadBank extra_state compatibility, all20 configuration
routes, selection/template/scope refusal, real existing gate invocation, selection
recomputation, and explicitly UNADMITTED output. Metadata tests use labeled
synthetic fixtures/stubs; they confer no D/data/platform/FP32 authority.

Root must inspect the actual diff, run normal checking and one appropriate full
combined regression, then bind/publicize exact source before any scientific use.
No C choice, recipe selection, full training, model freeze or adoption is claimed.
Initial-trial compilation does not silently authorize adaptive seed repeats;
those still require the existing separate selected-repeat plan and evidence.
The user's new D1 choices and data adapter/tensor implementation are separate
work owned by Root/other agents and are neither redefined nor granted here.
