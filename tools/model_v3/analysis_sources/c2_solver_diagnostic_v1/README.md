# C2 TRAIN-only solver diagnosis — new protocol, not baseline acceptance

Original C2 v1 job 4520482 failed with Slurm `FAILED/1:0` after 1,648 seconds.
Its failure record says that sparse LSQR did not satisfy the original stopping
condition, with 8,192 native TRAIN records decoded and zero VAL records. The old
stop code and iteration count were not persisted. **Do not infer stop 7 or an
exhausted 500 iterations.** Original v1 remains failed, with no coordinate result
or validation acceptance. The separate C2 report tool is still frozen and is
not being used to manufacture a result.

This new independent source directory implements a numerical/performance
diagnostic only. It neither changes the active ecdb C2 source, old request,
selection, features, ridge or old caps, nor invokes the old runner/main or
evaluation function. Root must test and commit the new source and diagnostic
rules to Git and publish their registration **before any real replay**.

## Exact mathematics

Let A be the raw CSR captured from the original fitter, b the original TRAIN
displacement target, n the number of TRAIN atoms and lambda=1e-4. The objective is

```text
J(c) = ||A c - b||² / n + lambda ||c||².
```

The original core passes a custom LinearOperator for A/sqrt(n), RHS b/sqrt(n),
and damp=sqrt(lambda) to LSQR. For support-zero columns, A is exactly zero;
positive ridge uniquely minimizes their coefficient at zero. On observed columns
define D_kk=sqrt(||A[:,k]||²/n + lambda) and z=D*c_active. Then

```text
B = [ A_active / (sqrt(n) D) ]       q = [ b/sqrt(n) ]
    [ sqrt(lambda) / D       ]           [ 0         ]

||B z - q||² = J(c),  c_inactive=0, c_active=D^-1 z.
```

The diagonal of B.T*B is one, including any observed zero-norm column. Only
column norms and sparse arrays are used; production code never constructs a
dense coefficient Gram matrix. The new solve uses this explicit sparse augmented
operator, `damp=0`, a zero initial point, the original atol=btol=1e-8 and
condition_limit=1e8, with an upper bound of 2,000 iterations. It does not use
the original solution as an x0 warm start. Positive `damp` with a nonzero x0
would put the ridge center at x0 in SciPy; that changes this objective. The
official [SciPy LSQR description](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.lsqr.html)
documents that distinction. Root also inspected the actual installed SciPy
source, rather than assuming the current online version is the installed one.

Each finite returned coefficient is diagnosed in original coordinates:

```text
g = A.T*(A*c-b)/n + lambda*c
relative normal residual = ||g|| / ||A.T*b/n||.
```

A zero RHS-gradient norm gives an explicit undefined relative value, not an
arbitrary epsilon denominator. The absolute norm, data term, ridge penalty and
objective are retained. These are TRAIN numerical diagnostics; **no new KKT
acceptance threshold**, validation criterion, model-selection rule or baseline
acceptance is created.

## Execution boundary

`CoreCapture` temporarily wraps the original module's LinearOperator constructor
and LSQR binding, restoring both in `finally`. It reads only the fixed
matvec/rmatvec closures `check,matrix,root_atoms` and the original fit frame's
`support,atoms,edges`. Both directions must reference the same matrix/root and
normalization. The actual original SciPy operator and original LSQR result tuple
are passed through. Original CSR buffers are fingerprinted and must remain
byte-identical; scaling occurs only in newly allocated sparse matrices.

The controlled original algorithm still has the original 500-iteration limit.
Its actual stop, iterations, rnorm, damped rnorm, arnorm, anorm, acond, xnorm,
matrix dimensions/nnz, observed support count and solver wall time are committed
to a durable JSON file **before the old require can raise**. Nonfinite estimates
are explicitly null with a named nonfinite field list. The core may reject its
new return or return a TRAIN model; in either case, that model is discarded and
no validation is called. Neither outcome changes what happened in old job 482.

Both solvers share the exact constructed TRAIN CSR/RHS and use BLAS=1. Real
`threadpool_info` snapshots are recorded before, inside and after each controlled
section; detected BLAS libraries must actually report one thread and restore
their previous settings. This uses the documented scoped API in
[threadpoolctl](https://github.com/joblib/threadpoolctl). No thread-count scan is
performed. This is a new controlled-thread observation, not a bitwise replay of
482, whose original BLAS state and stop fields were unmeasured.

Only `source.records('TRAIN', original_closed_plan)` is consumed. The existing
adapter may open already-bound role metadata; it must not decode any native
PRETRAIN_VAL geometry. The exact old request and selection raw SHA values,
original failure, old implementation inventory, metadata role proof and source
snapshot are preserved/verified. The request is never rewritten on disk. A
private control-only copy adds the already-bound selection raw SHA for the new
wrapper; this is not a new scientific request or a changed selection.

The new workflow uses the same total caps: **3,300 seconds, 24 GiB process RSS,
128 MiB total owned job output**. The Root supervisor covers its child tree,
logs/private storage and actual CPU allocation. The new child stops numerical
work at 3,240 seconds, leaving 30 seconds for its own source/SDK finalization
before the supervisor's 3,270-second finalization boundary; this is a stricter
work allowance, not an increase to any old cap. A 2,000-iteration limit is only
an upper bound. Work interrupted by the declared deadline is explicitly censored;
any solver stop/iteration field not actually returned stays unknown. Already
returned source/candidate receipts survive later KKT/finalization failures.

The captured CSR is never saved. Preconditioning has a declared conservative
8-GiB phase-local numeric upper bound within the 24-GiB process cap. Optional
active-column-only coefficients, support, column indices and D are saved as one
private numeric NPZ only if their uncompressed upper bound fits 32 MiB and the
remaining job budget. Array refusal is recorded; it never increases a budget.
No member IDs, raw coordinates, prediction records, target vectors or dense Gram
are exported. Actual data-derived arrays/receipts stay outside Git.

W&B is persistent offline with canonical `cache/wandb_data/wandb_config` paths
bound before SDK import/init. The fixed four-link-aware runtime_monitor source
SHA is verified. Root's existing CPU-only supervisor, not a GPU node, owns job
submission, identity, output/private storage and resource enforcement.

## Inputs, preregistration and command

`diagnostic_protocol.json` is prepared method metadata, not a D schema or a
claim that a new baseline has passed. Its `source_inventory_sha256` binds the
three executed source files. Root can copy this directory to
`tools/model_v3/analysis_sources/c2_solver_diagnostic_v1` without changing file
bytes, run the tests, and commit/publish the protocol plus source. The later
registration commit/path and independent raw protocol SHA must be supplied in
the actual input manifest. The executed source is rehashed before/after the run.

The input manifest has schema
`model_v3_C2_train_solver_diagnostic_inputs_v1` and fields:

- `source_repository`: the unchanged original C2 worktree path.
- `source_request`, `selection_plan`, `original_failure`: exact original
  `{path,bytes,sha256}` references, provided by Root.
- `runtime_monitor`: fixed ordinary source `{path,sha256}` reference whose SHA
  is `dbe875ab7ceec7e5002c5b70bff0608e3506f7451bdacd38e5f5bfc0700663fe`.
- `protocol_registration`: `{repository,commit,path,sha256}` for the **committed**
  new diagnostic protocol blob. Reading a working-tree-only file is insufficient.

No real source-request/plan binding is guessed in this directory. Root supplies
those original references and the actual new registration after publication.

```text
python -B diagnose_coordinate_lookup.py --inputs /external/closed_diagnostic_inputs.json --inputs-sha256 <actual-raw-SHA256> --expected-node <Root-selected-CPU-node> --output-root /external/new_diagnostic_run
```

The source adapter still requires its owned 16-CPU Slurm allocation. The new
admission check requires the actual CPU host and Slurm node to match the explicit
CPU node and CUDA devices to be hidden. The tool never submits a job. All source
and method rules must be published before Root uses this command on real TRAIN.

Final files use `DIAGNOSTIC_*` names, never the original C2 COMPLETE/model format.
Even a normal diagnostic completion has `baseline_accepted=false`; a changed
baseline solver needs a separate future public protocol. Old failed evidence is
not overwritten, relabeled or deleted. Any new failure/partial output is kept.

## Root-controlled validation request

No code or scientific data fit has been executed here by SA-4. Proposed command
from this source directory on an available CPU node:

```text
PYTHONPATH=/share/home/zixiao/descriptor_analysis/MFM_model_v3_c2/current python -B -m pytest -q -p no:cacheprovider test_solver_math.py test_core_capture.py test_train_only_runtime.py
```

Expected source collection: **20 synthetic cases**, not a PASS claim. Tests use
small dense ridge oracles only in tests; full sparse production never forms the
Gram. Coverage includes equal objective for arbitrary z; exact zero unknown
columns; original atom/component/ridge denominators; nonzero-x0 center trap;
zero-gradient residual semantics; sparse/budget boundaries; original core closure
and actual LSQR return capture; restoration on failure; source drift; forbidden
non-TRAIN roles; same-matrix candidate integration; original fit returning or
rejecting without any VAL call; candidate censor preserving source stop; actual
temporary Git preregistration; CPU host admission; and bounded private NPZ output.
Synthetic test stop codes/iteration limits are never observations of job 482.
