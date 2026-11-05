# One uniform centered-FP32 candidate: original complete48

**Actual candidate CPU/publication ready; final request/source pins not yet written.**
Candidate cf8ce66/tree2389ab has actual CPU4521707 C0:2712 collected,2709 passed,
3 unchanged optional skips; new73 and oldnumeric47 passed without skips. The
independent experiment is published/read back at f8417157dc23326d1beca8e19e4725755d9f13c6.
Root final_binding.py --write-final consumes exact actual evidence and generates
the final metadata; author has not invoked it, Python, AST, a model, SSH or Slurm.
The historical DRAFT inventory remains unchanged. This directory edits neither
the candidate/frozen baseline nor source fixture/reporting tree/prior failures.

## Execution boundary

Execution package: MFM_model_v3_attention_centering_v1, experiment branch
model-v3-attention-centering-20261027-v1. Base local4068623cc455915a34a4aacae4f0df5c56f691b7;
parent public5cdb2772dfa51e1cc72098c659fb741440219772. Root will bind the actual NEW
local/public/tree after commit and CPU QA. The reporting model-v3/v12 branch only
receives reports/prereg/source snapshots and links this independent experiment;
its current code is not this execution runtime.

The ordinary/default aggregation path remains legacy in candidate code. This one
experiment explicitly constructs **all six layers** with
backbone.attention_aggregation_mode=centered_fp32_v1. Existing encoder/heads/
distance/reducers remain numeric_mode=compensated_fp32_v1. No case/layer/seed
selection, new initializer, parameter, architecture,512 H0/API change, AMP, bf16,
FP64 production or NativeRuntimeDense migration is authorized.

## Minimal reuse

- centered_adapter.py loads the exact old v3_composed_equivariance.py
  rawSHA0c49debe901ee5db79a71fcbc8541d426231c5090eb9740b84649e867d8df0e8.
  It patches only fixture builder bindings in a finally-restored local context,
  injects the explicit aggregation key plus oldCOMPENSATED option, and builds
  every original PD head policy unchanged. No cohort/physics/transform formula
  is copied. Each constructed complete parameter SHA must equal the actual1492
  same-seed capture; clean/noisy views are not rebuilt or resampled by this adapter.
- test_centered_matrix.py follows the original1435 scientific test. All52 terminal
  arrays and complete measured JSON are fsynced before the unchanged original
  assert_case_passed. All13 fields, all3 transforms, raw invariants/nonzero/domain/
  edge/orthogonal-R controls, absolute1e-5/relative0 stay in the frozen source.
- run_centered_matrix.py is derived from the original1435 runner: same pytest48,
  no fail-fast, ordinary numbered=False case directories, source before/after,
  XML counts and complete output coverage. Numerical failures do not terminate
  remaining cases. Structural exceptions receive per-case exception records;
  incomplete measurement coverage cannot become a successful subset or physics
  PASS. No final model acceptance/adoption is implied even if all48 pass.
- tiny_candidate_controls.py invokes the ACTUAL new candidate helper
  centered_attention_value(p,V,mask,attention_dropout=None) on same-GPU tiny
  softmax/dyadic and constant-V inputs, checks actual logits/V gradients against
  old direct AV on the exactly representable dyadic case, and refuses all-masked,
  empty,bf16,active-dropout inputs without CUDA RNG consumption. This is separate
  from the scientific48 and repeats no192 FP64 encoders. The actual helper
  signature must be rechecked after SA4 commits; this is not an executed claim.

Existing original48 failures1435/other attempts and1641 local evidence remain.
There is only ONE centered candidate and no legacy fallback if its option or
guards are unsupported. Passing tiny/CPU controls is not full48 acceptance.

## Source/publication binding to finish after actual QA

execution_request_DRAFT.json contains the fixed48 IDs, original tolerance and
capture metadata but deliberately EMPTY candidate rawrefs/public files/QA refs
and null actual commit/tree/public receipt. DRAFT cannot bootstrap. Finalization
must create fresh execution_request_v1.json and source_pins_v1.json after Root:

1. Receives the actual candidate commit/tree and source inventory plus actual
   CPU results/outerC0/source-stability proof. Preserve raw QA evidence; do not
   manufacture an expected-count receipt or reinterpret an old QA as new pass.
2. Publishes the candidate experiment branch, verifies its actual public/local
   same tree and raw Git blobs, preserving the original parent branch. Use the
   existing model_v3_numeric_candidate_publication_actual_v1 receipt schema
   (public/local/tree/files); bind this actual new receipt, not5cdb as if it were
   the new candidate. Reporting/root is never used for execution imports.
3. Builds required_public_paths from actual required/changed source files,
   including all eight CRITICAL paths declared in centered_publication.py,
   and all changed candidate scientific code/tests/config. public_files must
   equal this explicit set; each must also appear in raw runtime source_refs.
   Source refs must cover the complete actual runtime closure and unchanged
   fixture/capture metadata. Relocate only the old numeric candidate-root paths
   to the new execution tree, then rehash ACTUAL bytes; never reuse an old SHA
   under a guessed new path or substitute reporting sources.
4. Source-only request fields become status=FINAL_BOUND_PUBLIC_EXPERIMENT_REQUEST,
   actual local_commit/public_commit/exact_shared_tree/publication_receipt,
   candidate_QA_evidence (actual small JSON certificates),public_files,
   required_public_paths,source_refs. Add the final raw test/helper/source refs.
   Verify all48 IDs exactly equal original1435 and fixture order. Source pins
   use schema model_v3_centered_attention_complete48_GPU_launch_source_pins_v1
   with files/protected_dependencies/execution_request rawref. No weights/data
   are copied into these source inventories.
5. Runs ordinary checker, publishes the new runner/protocol/source snapshot and
   scientific rules before Root invokes the fresh Root resource admission. The
   final request is bound by exact source-pins SHA; no stale source is admitted.

centered_publication.py uses exact raw Git blobs by default. Only the two already
registered inherited numeric metadata filenames may use complete CRLF-to-LF
projection, and an already-LF checkout matches directly. No code normalization
or arbitrary new metadata exception exists. Source graph/current raw SHA stays
strict regardless of Git text representation. No invented16-file count is
imposed on the new candidate; all declared required/changed files must be bound.

## Root launch, only after finalization/publication

launch_centered_matrix_GPU_v1.py and run_centered_matrix_GPU_v1.sbatch are thin
derivatives of the proven1641/1561 Root launcher. They retain the original
gpu_runtime_retry_v4 guard d3cba6...,c35/node21,shared fd9 lock,16CPU/32GiB,
RSS28GiB,1100s supervisor,20min allocation,whole output2GiB/private2GiB,actual
quota/max(queue,AllocMem)85%/MemAvailable/NVML guards. No dispatcher, monitor,
automatic retry or new admission parent is introduced. The final request SHA
comes from final source pins; no original d5ed capture request is mislabelled as
the new candidate request. Distinct output/attempt prefix:
attention_centered_e2e_GPU_v1.

```bash
P=/share/home/zixiao/descriptor_analysis
S=$P/runs/model_v3_20261026/attention_centered_e2e_v1_source
PY=$P/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
PIN=$(sha256sum "$S/source_pins_v1.json" | cut -d' ' -f1)
"$PY" -B "$S/launch_centered_matrix_GPU_v1.py" audit --source-pins-sha "$PIN"
"$PY" -B "$S/launch_centered_matrix_GPU_v1.py" submit --source-pins-sha "$PIN" \
  --submission-receipt "$P/runs/model_v3_20261025/attention_centered_e2e_GPU_v1_attempt1.json"
```

These commands currently must refuse because final request/pins are absent.
Root alone submits after actual evidence is bound. All48 remain in the declared
experiment, including numerical failures; original tolerances and losses are not
changed in response to results. A failed GPU job is retained with actual scope.
