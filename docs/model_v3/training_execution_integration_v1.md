# Training execution integration v1 — source only

This feature is not a scientific acceptance or a runnable standalone branch until Root atomically combines the SA1 performance adapter, SA3 entry/trainer changes and SA4 CP/H0 bridge and completes QA. Base: Root-designated 81948e457c29fbc51687066a4f944ff5bcd5bad5. The author's work is source text only: no Python, AST, Git, tests, CUDA, models, SDK, LMDB, weights, arrays, SSH or Slurm execution. The old A-only loader, original A builder/default twelve options and original logical-batch class bodies remain unchanged. Historical Native checkpoints keep their immutable producer/bridge process; they are not migrated to this source identity.

## One common API and contract

`phase1/v3_training_execution.py` is the single owner of these interfaces:

```python
built = build_training_encoder(model_configuration,
    execution=configuration.get("training_execution"),
    workload_binding=workload, operational_admission=request.get("training_execution_admission"))
# SA3 constructs the original complete two/three-view model and all PD heads.
full_model = original_model_class(built.encoder, pd_heads, registry, structural_binding).to(device)
optimizer = make_training_optimizer(full_model, declared_optimizer, built)
with training_execution_context(built):
    contract = finalize_training_execution(full_model, optimizer, built)
```

`TrainingEncoderExecution` exposes encoder, resolved_options, contract, observer, specification, model_configuration, workload_binding, implementation_sha256, operational_admission and optimizer_dispatch. Finalize returns the sole dict (None without opt-in), once, and attaches `full_model.training_execution_contract`. No full contract is attached recursively to `performance_execution_contract`.

Without opt-in the encoder is the exact original architecture builder; no execution key, observer, policy or new state key is attached. SA3 retains its old direct AdamW path. With opt-in `make_training_optimizer` preserves declared absent/None/False fused/foreach exactly; it uses all complete-model parameters, including PD heads. It does not substitute the A benchmark's omission of fused=False. Master parameters remain FP32; unadmitted fused AdamW and TF32 are explicitly refused.

The exact `model_v3_training_execution_contract_v1` fields are schema, model_configuration, requested_execution, resolved_options, architecture, module_layout, checkpoint_scope_map, optimizer_dispatch, implementation_sha256, workload_sha256, h0_export and execution_state. `execution_state` is the actual existing trainer `_execution_state` projection with its training_execution key removed before attaching the contract. The SA3 CP embeds the identical contract under trainer.contract.training_execution and extra_state.execution.training_execution. `validate_training_execution_state` checks this embedded identity and the exact saved projection; module flags/options, packing/source and the three scope meanings also cross-check. Resume must retain the same mathematical/options/layout contract. New operational rawrefs alone do not rewrite it.

`validate_training_execution_contract(contract, verify_sources=True)` is the unique metadata validator. `validate_h0_export_contract(contract)` additionally rejects unsupported export combinations. Neither reconstructs a model or re-resolves automatic policy. H0 bridge and capability consume these helpers rather than implementing another resolver.

## Explicit policy and workload versions

Configuration has the sole policy at `configuration.training_execution`. `TrainingExecutionSpec` schema is `model_v3_training_execution_v1`; fields: options (the original PerformanceOptions mapping), checkpoint_policy (manual or auto_closed_training_profile_v1), geometry_scope, padding, batch_padded_cost and resident_models=1. Semantic normalization expands defaults without mutating the immutable raw request.

A C1-0 manual starting policy is:

```json
{"options":{"backbone_checkpointing":true,"distance_checkpointing":true,"head_checkpointing":true}}
```

For C1-a/b the policy MUST declare `geometry_scope="c1_shared_pair_v1"` and `options.distance_implementation="dense"`. It does not pretend the shared encoder is a tiled scalar-distance MLP. C1-a/b currently require FP32/dense attention and no outer AMP. Their scope map distinguishes layer checkpointing, the complete shared pair encoder once, and the original S geometry head; PD heads remain their unchanged implementation. Shared pair projection inputs/distances and Gaussian/cutoff/element-affine formulas are unchanged. No new Parameters, initialization or radius is introduced. The original shared backbone and parameter/state keys are reused.

The workload schema is `model_v3_training_workload_v1` with exact top-level keys schema, scope, seed, model_configuration, data, groups, fields, heads, views, view_policy, loss, optimizer, validation. Scope is explicitly engineering_synthetic_fixture, authoritative_proxy, authoritative_full_train or authoritative_grid_cell; a grid CLI may have a distinct mode but must project it explicitly. Data requires registry_sha256, normalization_sha256, data_version, authority_sha256 and selection and preserves every additional actual input projection key. Validation population bindings retain the provider's existing JSON. The stable authority digest is the qualified final-data reference projection, not an operational Root/opaque-provider receipt containing a request SHA. Those original receipts remain in the original trainer/CP/request provenance. No data-line schema or authority is invented here.

SA3 owns the sole `_workload_projection` and `validate_training_workload_request(workload,request,configuration)` in proxy_run. Both producer and consumer call that same metadata function, cross-checking the saved workload against the actual --request configuration/input projection. All relevant heads/views/groups/fields/training-view/precision/schedule/batch/loss/clip/declared optimizer inputs are retained. Raw request/config SHA and capacity refs are not put into the seed-common policy/workload where manual→auto admission would create a circular mismatch. The original recipe identity's hardware routing is not silently removed; SA3 versions any such projection explicitly.

## Same logical batch, including SharedPair

Packing operates only on an already prepared complete logical batch. It never samples, degrades, redraws noise/masks, constructs labels, performs a local loss or updates the optimizer. It sorts complete graphs, executes the native C1-0 or native SharedPair full forward per chunk, then restores original packed atom order before any S/PD head and the original whole-batch loss/count/group reduction. Three-view associations and original source data are untouched. Actual graph counts and executed chunk shapes are recorded separately from consumed base samples.

Zero-dropout/FP32/no outer AMP and no cross-graph BatchNorm are required when packing. Real stochastic modules inserted later still reject before their RNG draw. Auto+compile+packing remains explicitly unsupported; ordinary compiled auto requires its exact observed shapes. Sparse attention cannot silently add a radius to global C1-0; SharedPair sparse/bf16/scalar tiling are refused. No GPU arithmetic gate or adoption follows from these CPU mechanisms. New combinations still need the original output/all-parameter-gradient and500-step gates plus the required GPU speed matrix before performance adoption.

## Training-owned capacity observations

The existing A qualification is unchanged. In particular old/manual R2 A observations, R1 timing and new training profiles are different authorities. This new consumer only accepts schema `model_v3_closed_training_capacity_profiles_v1`, containing at most32 observations with the same six exact refs: configuration, summary, run_status, supervisor, parent_sacct, steps. New training policy auto needs the operational direct dict:

```json
{"schema":"model_v3_training_execution_admission_v1","capacity_profile":{"path":"ACTUAL","bytes":1,"sha256":"ACTUAL"}}
```

That is a shape illustration, not an actual profile. Manual needs no profile, so initial real measurements are possible; there is no OOM retry, changing batch or unmeasured fallback. Automatic consumption requires the same complete training workload/seed, implementation, padding, residency1, compatible checkpoint options, physical GPU/versions/runtime controls and fresh actual capacity/foreign-process checks. It does not grant numerical/scientific acceptance. Different P/SDP/full/grid populations, seeds, roles or architectures cannot borrow the old S/A workload merely because the card name matches.

The shared observer APIs are:

- `forward_context(full_model, role=...)` sets the actual role before every original forward (including a probe), checks live options/flags/precision and restores its previous role. Auto guards compare each role's measured envelope; a larger no-grad VAL cannot authorize TRAIN.
- `capture_forward(full_model, role=...)` snapshots the main TRAIN receipt immediately, before a probe overwrites last_logical_batch_execution; VAL and TRAIN_UNSEEN_CONFORMATION each snapshot their actual batches. It retains metadata, not tensors or inputs.
- `record_completed(snapshot, optimizer=..., optimizer_updates=..., samples_consumed=..., resources=...)` records after the committed step/validation batch. Resources require gpu_observation, peak_allocated_bytes, peak_reserved_bytes, process_rss_sum_bytes, foreign_gpu_risk_observed and output_bytes. Existing runtime_monitor/supervisor sampling is reused. Peaks include probes, full heads and materialized Adam; CPU engineering has explicit None GPU and never qualifies CUDA.
- `set_sink(callable)` streams each row immediately. The observer retains role envelopes/finite shape sets/counts/peaks and an Adam shape/storage summary, not a journal/activation list. Journal is at most16MiB, line at most1MiB; no guard/budget is raised on overflow.
- `begin_validation(role,batch_count=...,population_binding=...)` and `complete_validation(role)` bind each exact provider population. Partial/failed populations remain incomplete; no sampling-only profile masquerades as full validation.
- `configuration(request_reference=actual_ref)` and `summary()` return bounded output metadata after completion. Configuration uses the first actual CUDA-forward environment frame, not a late fresh query after releasing the UUID lock. The actual request source map and invocation join to the original supervisor/kernel frame. CLI output files are training_capacity_configuration.json, training_capacity_summary.json and training_capacity.jsonl.

The native SDK/provider finish outcome stays in the original CHILD_RECEIPT (proxy or explicit WSD schema). Its opt-in training_execution_capacity_artifacts must bind the same configuration/summary/steps refs, job and committed cursors. Parent actual sacct must be C0; supervisor must close its original kernel identity/private/remaining process checks. The producer never writes a fake parent C0. CLI entry qualification accepts the exact run_proxy_experiment or run_wsd_fork source according to the actual request's role, with the original -u/-B argv forms, request SHA and output. Unknown schemas, changed source graph, unclosed/foreign jobs, unknown memory/state or mismatched role/population refuse automatic consumption.

Adam inventory reports actual parameter/state shapes and a conservative remaining tensor-storage allowance for lazy moments/step. It is explicitly NOT a universal optimizer-workspace/future allocator bound. The capacity evidence is sampled, and future actual role/shape guards plus the original85% GPU/RSS/wall/output/private guards remain authoritative. This does not require an invented all-future-shape science gate. Both child metadata JSONs are at most2MiB; original per-job whole/private budgets are not enlarged.

## CP/H0 and WSD

`build_h0_export_encoder(model_configuration,contract)` reuses the same explicit architecture/packing/distance implementation and FP32 master weights; it never reselects training capacity or grants downstream capacity. Candidate/random share this builder through SA4's bridge. `h0_export` explicitly maps training precision→FP32 and records its unique allowed differences. FP32 same-input/eval path can be tested bitwise; bf16→FP32 is not training bit replay. Compiled-source export is refused until it has an admitted mapping, rather than silently disabling compilation and calling it equivalent. H0 remains the original512 API for real training; tiny CPU fixtures are engineering tests only.

`h0_export_context(contract,device_type=...)` is the required explicit eval scope. It saves/restores highest/TF32, deterministic/warn-only and cuDNN controls, applies the map's FP32/highest/two-TF32-off policy, and carries deterministic algorithms from the training contract. Builder/load never silently changes caller globals or RNG. Deterministic CUDA requires the declared CUBLAS_WORKSPACE_CONFIG=:4096:8 already arranged by the fresh worker; no late setter or initialization-history claim is made here. CPU contexts do not constitute hardware qualification.

`rebind_training_execution(full_model,optimizer,parent_execution,workload_binding=...,execution=None,operational_admission=None)` is the only WSD execution hook. It keeps the exact model/optimizer/Parameter/state objects and RNG, permits ONLY view_policy.schedule and view_policy.sample_budget differences already allowed by the original WSD validator, and creates a fresh child observer/contract. Parent COMPLETE/request/terminal/ledger/ref chain stays owned by original WSD logic. Auto needs a closed child-exact workload observation and the same resolved actual flags; no parent profile relabeling. The no-allocation branch uses actual current owned-process bytes for existing R1 residency accounting, preserves fresh foreign/10% reserve/85% tests, and allocates no second model. Manual child measurements remain separate from scientific acceptance. Legacy no-optin WSD is a no-op.

## Verification plan and ownership

SA1 authored seven leaves: this method; phase1/v3_training_execution.py; model/v3_training_capacity.py; model/v3_performance.py; model/v3_logical_batch.py; tests/test_model_v3_training_execution.py; tests/test_model_v3_training_capacity.py. No v3_architecture, trainer/proxy/CLI, WSD or bridge source was edited by SA1. SA3 owns their shared caller/clock/stream/CP hook; SA4 owns bridge/READY/evaluator mapping. Imports of their new helper are intentional atomic-feature dependencies, not a claim this source-only branch is independently executable before integration.

Planned CPU cases cover all C1 defaults/RNG/keys, real all-parameter and positional gradients with/without chunks/checkpoints, true three-view S+D+P masks/counts/source order for C1-a/b, empty/invalid graphs and real stochastic changes, optimizer dispatch, real safe weights_only state roundtrip and same-input H0, changed contract/source refusal, streamed main-before-probe observations, exact populations, unknown Adam layout and CPU-not-CUDA qualification, H0 global restoration and WSD no-reinitialization. They are source plans, not collected/passed results. Tiny encoders are16x2; the four whole-SDP cases use the original512x1 structural fixture. One tiny safe payload is written; no SDK/LMDB/NPZ/real labels or large6x512 checkpoint is created by these tests. The original16CPU/16GiB/RSS12GiB/800s/whole+private2GiB envelope is a bounded first QA proposal, not a measured promise. SA4's real6x512 bridge and SA3 CLI tests need their own output accounting within Root's combined plan.

Root performs static review, atomic integration, targeted/full/checker QA and public preregistration. Actual D3/D4/D5/D6 admission, original GPU20/500/three-card measurements, recipe choice/freeze and final training remain separate uncompleted work. No synthetic receipt or CPU test in this feature substitutes for them.

## Narrow v3 correction after actual CPU4524499

The original atomic CPU run collected2899 cases and retained38 failures. Thirty-four traces reach the existing C1 declaration guard: the new engineering fixture supplied only three of the six canonical ArchitectureOptions fields. The fixture now uses asdict(ArchitectureOptions(...)); production accepts no new partial declaration. Two negative cases retain partial-declaration rejection, configuration identity and constructor RNG checks for both original and opt-in entry paths.

The H0 context also had a production restoration defect for a legal caller using medium matmul precision. In the installed Torch2.10 commit449b1768410104d3ed79d3bcfe4ba1d65c7f22c0, medium sets CUDA TF32 together with MKLDNN BF16. Redundantly setting the legacy CUDA allow_tf32 flag changes the legacy precision enum while leaving the MKLDNN setting, so the precision getter rejects that combination. H0 now applies and restores global matmul policy using only set_float32_matmul_precision; cuDNN remains independently saved/restored. The semantic H0 controls remain FP32/highest/TF32-off with the original deterministic mapping. See the [exact official implementation](https://github.com/pytorch/pytorch/blob/449b1768410104d3ed79d3bcfe4ba1d65c7f22c0/aten/src/ATen/Context.cpp#L303-L361).

The CPU plan adds legal highest/medium caller states across normal and exceptional context exit, retaining complete globals/RNG assertions. The v3 SA1 plan is46 execution cases plus9 capacity cases=55; no v3 collection or pass is claimed. Root retains the original ca1/4499 evidence and all eight v2 source bytes. SA3's next_step fixture and SA4's redundant test setter are separately owned narrow revisions. Model math, thresholds, source/admission semantics and CPU/GPU acceptance boundaries are unchanged.

## Narrow v4 correction after actual CPU4524505

The second atomic CPU run retained15 AttributeError failures at the shared-pair checkpoint wrapper. The original C1-a encoder exposes pair_scale and pair_shift as ordinary None attributes; the shared module-reuse utility copies registered children but omits those attributes. The wrapper now explicitly binds both fields from the original. For C1-b they remain the same Embedding instances, with unchanged registration names, parameters and state. The generic reuse helper and all no-opt-in builders are unchanged.

Four new CPU controls cover C1-a/b with checkpoint off/on: optional attributes and exact object identity, state names/buffers/RNG, unwrapped-versus-wrapped forward and all input/parameter gradients, followed by original-versus-no-opt-in forward/backward in the same process. Existing C1-a/b, whole-SDP, capacity and old default regressions remain enabled. The15 traces include later backward recomputations referring to the earlier missing-attribute C1-a wrapper; source evidence does not establish a separate default-model math defect or authorize changing Torch checkpoint internals. Root retains4505 and will determine the actual post-fix result.

SA1 v4 plans50 execution cases plus9 capacity cases=59, with one tiny safe checkpoint and no SDK runs. The source revision has not been executed by the author and does not claim CPU/GPU acceptance.
