# Fixed full-matrix head numerical attribution

Prepared only; not executed or adopted. Original CPU job4521006 remains
FAILED1:0/48s:57 collected,9PASS/48FAIL,0error/0skip, source bytes unchanged.
The full original aggregation and its source JSON rawSHA references are in
`baseline_aggregate.json` and `BASELINE.md`. The old NPZ files are references
only: neither this aggregate nor this diagnostic reads their bytes.
The full aggregate is2,890,244bytes and remains an immutable external artifact.
Publish `baseline_public_v1.json` (318,147bytes), which retains all1872 stored
observations and all48 original JSON rawSHA refs using documented compact
columns, deduplicated field/transform metadata and the original parameter/
geometry digests. Its full-aggregate bytes/rawSHA reference preserves the
verbose evidence without placing the oversized original in Git. No failure
row or numeric value is removed.

All48 original cases and their three transforms, source builders, initialized
parameter bytes, 3/9/32-atom fixtures, actual masks/noise and raw1e-5/rtol0
oracle remain unchanged. `weight_summary`, all geometry/view digests, registry
and encoder configurations must match the corresponding original case.
Baseline additionally requires every original field/domain/edge/count/argmax/
nonzero measurement to replay exactly. External filenames, wall time and
resource peaks are not scientific replay identities. A mismatch is retained
and makes the diagnostic incomplete; no different seed/fixture is tried.

The frozen Eq source is imported from the explicit `--eq-repository`. It is
not copied or edited. The new request binds the entire original Eq source
inventory, this new source/test/document and the original aggregate/document.
Root publishes the diagnostic rule/source before actual controlled execution.

## Predeclared interventions

Each of seven variants executes the **entire48-case matrix**, with no adaptive
ranking, early model selection or triple intervention:

| Variant | Temporary change |
| --- | --- |
| original_formula_replay | no operator change; exact original control |
| cdist_direct_only | every Euclidean p=2 torch.cdist forces direct mode |
| charge_center_only | both independent dipole heads use centered charges |
| pool_fp64_reference_only | only graph-scalar512-wide H0 pooling accumulates in64 then casts back32 |
| cdist_direct_and_charge_center | first two single interventions together |
| cdist_direct_and_pool_fp64_reference | distance plus scalar pooling reference |
| charge_center_and_pool_fp64_reference | charge centering plus scalar pooling reference |

`torch.cdist` calls with p other than2 retain their original behavior. No
distance, neighbor cutoff, mask, RBF feature, coordinate dtype or view is
changed otherwise. The direct-mode intervention includes original A4 neighbor
construction and C1-0 distances. Existing already-direct C1-a/b calls remain
direct. Counters show actual intercepted calls, not an assumed kernel cause.

The charge intervention computes
`sum_i (q_i-mean(q))*(r_i-mean(r))` using the original **FP32** coordinate
centroid, charge MLP, sum and norm. It equals the original expression over
exact reals because centered positions sum to zero; it changes only floating
evaluation order. No charge parameters are shrunk, changed or fitted. Vector
and magnitude fields have independent charge MLPs, and both are tested.

The pool reference applies only to512-wide latent graph features, including
sum and mean/mixer components. Position centroids (width3), charge centering
(width1), all vector geometry and model parameters retain their original
FP32 calculation. The returned feature is cast back to its original dtype.
**This intervention contains FP64 accumulation and is attribution evidence,
not a claim to satisfy the unchanged full-FP32 acceptance protocol or approval
to adopt FP64.** It cannot silently become a production default.

Each case has its own context manager. Function identities of torch.cdist,
v3_heads._pool and _DipoleHead.forward are restored in finally even on a model
exception. No source file or parameter is monkeypatched. Tests prove actual
cdist p2 behavior/p1 preservation, the centered-charge double-precision
algebra identity, unchanged FP32 head parameters and nonzero outputs, graph
pool-versus-centroid separation, actual FP64 cancellation-reference behavior,
and cleanup on exception. Three digest-drift negatives reject altered
weights/geometry/view identity. Expected small unit collection: **10 cases**.

## Root interfaces

All commands below are interfaces for Root's existing admitted CPU Slurm
workflow; this source does not submit jobs, use GPUs, open native data or train
a model. Root chooses a currently available CPU node2 or8–19, at least16
requested CPUs, all-user memory below85%, actual available memory/quota and
the existing source/identity/storage supervisor. Use the original CPU Python/
Torch environment and explicit empty CUDA visibility. Every model has one
intraop thread as in4521006; the control must replay its actual measurements.

Small meaningful tests, with the original frozen package on PYTHONPATH:

```text
PYTHONPATH=/share/home/zixiao/descriptor_analysis/MFM_model_v3_composed_equivariance/current python -B -m pytest -q -p no:cacheprovider /external/eq_diagnostic_v1/test_diagnostic.py
```

Prepare a new external source-bound request; its command prints actual
path/bytes/rawSHA:

```text
python -B /external/eq_diagnostic_v1/diagnose_aggregation.py prepare-request --eq-repository /share/home/zixiao/descriptor_analysis/MFM_model_v3_composed_equivariance --aggregate /external/eq_diagnostic_v1/baseline_aggregate.json --expected-node <actual-CPU-node> --output /external/eq_diagnostic_request.json
```

After Root's source publication and CPU tests, run only within that allocation:

```text
python -B /external/eq_diagnostic_v1/diagnose_aggregation.py run --request /external/eq_diagnostic_request.json --request-sha256 <actual-request-rawSHA> --output-root /external/new_eq_diagnostic_result
```

The full run is336 actual6x512 case executions (seven times48), not336 training
runs. All original/moved FP32 terminal values are preserved into **new** NPZ
artifacts, including outputs produced before an exception. Raw original
case-JSON refs are retained; no original NPZ is reopened. Per-field
maxabs/argmax/count/nonzero/edge/domain evidence stays in each new case JSON.
Field values are never used to choose a subset or overwrite original failures.

Each variant has the original Eq **32MiB whole-variant output cap**, including
NPZ, JSON, pending files and failures (forecast about11MiB raw terminal values
before compression per variant). The complete job remains under the existing
**2GiB original CPU guard**, including all seven variants, metadata and
failure outputs. Do not run under a silently substituted larger guard. This
adds no default output allowance to any old run. Roots and request files are
external and fresh; old files are not overwritten.

The final status is `DIAGNOSTIC_COMPLETE_NO_ADOPTION` only when the original
control exactly replays all48 cases, every variant has all48 complete numeric
records and source bytes match before/after. Original threshold failures do
not make a completed attribution run look incomplete; a model exception or
replay/source mismatch does. Every record explicitly says
`is_FP32_acceptance_evidence=false`. A raw threshold-pass count for an
intervention is descriptive and cannot upgrade the original failed matrix,
approve an architecture or substitute for a newly preregistered production
fix and its complete FP32 CPU/GPU regression.
