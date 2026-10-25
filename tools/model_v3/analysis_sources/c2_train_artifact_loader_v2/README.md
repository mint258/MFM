# V2 from completed TRAIN artifact — no TRAIN rebuild, not yet executed

This second package restores the completed TRAIN-only diagnostic's parameters,
then permits the first real PRETRAIN_VAL analysis only after a new public
**ADOPTED artifact-origin protocol**. It does not replay TRAIN, rebuild its CSR,
refit parameters or recompute KKT. Original v1 job 4520482 remains FAILED with
unknown original stop/iteration count. Diagnostic job 4520559 remains a TRAIN
diagnostic, not a retroactively accepted baseline.

The independent full-fit v2 package has already passed its 17 actual CPU tests
in job 4520575. Its four runtime files are copied here byte for byte and are
unchanged. `accepted_train_artifact_v2.py` and its separate tests are new. No
native TRAIN/VAL dataset has been opened by SA-4, no NPZ has been copied into
Git, and no real artifact entrypoint or Slurm submission has been run here.

## Binding and restore rules

The new protocol must bind the same original source-request and frozen
8,192 TRAIN / 1,024 PRETRAIN_VAL **record** selection plus all of:

- TRAIN diagnostic RESULT, DONE, `input_binding.json` and its original bound
  input bundle, including diagnostic public commit
  `cd0c434bb39824cd75c24d7c6de0531946da1de5`.
- An actual C0 TRAIN job closure, raw parent `sacct` row and byte-bound CPU
  supervisor. This is explicit model-owned QA metadata, not a D-line schema.
- The private closed NPZ's original bytes/SHA, recorded array-content schema,
  actual matrix/population/support dimensions and the four executed supervisor
  source hashes. A lone success boolean is insufficient.

559 used **run_cpu_supervised_128m_v1.py**, not the old default-2GiB helper. The
128MiB helper and its three runtime/storage helpers are pinned to the actual
recorded inventory (machine-read from the completed supervisor). The loader
requires that exact four-entry inventory, clean remaining/process/storage
closure, actual input command and matching raw Slurm C0/elapsed; it does not
accept an arbitrary guard or infer equivalent provenance from a similar name.

The model-owned closure schema is `model_v3_C2_TRAIN_artifact_closure_v1`:

```text
source_job: {job_id, state: COMPLETED, exit_code: 0:0, elapsed_seconds}
supervisor: {path, bytes, sha256}
raw_sacct: {argv, stdout, stdout_sha256}
```

For example the machine command can explicitly request
`sacct -n -P -j 4520559 --format=JobIDRaw,State,ExitCode,ElapsedRaw`.
The loader checks the exact parent row rather than `.batch`. The Root-provided
closure must reflect actual files/accounting; the synthetic tests do not supply
authority for a real job.

The accepted original-coordinate parameter file is already a 100,361-byte NPZ
with raw SHA `1e42b97174ca44bf779a4034880f3b12eb1e64431c8c1bbb0cd61ef587d0ef52`.
This hash and its content declaration were read from the closed TRAIN result and
the actual file, without decoding the NPZ or reading any native VAL data. The
five exact fields are:

| Key | Required dtype and shape for 559 |
|---|---|
| active_columns | int64[4116] |
| observed_support | int64[4116] |
| candidate_coefficient | float64[4116] |
| controlled_source_coefficient | float64[4116] |
| jacobi_scale | float64[4116] |

The loader hashes one immutable byte buffer, checks exact unique ZIP members,
bounded expanded sizes/headers, then uses `np.load(..., allow_pickle=False)` with
a closed context manager, as specified by the
[NumPy load API](https://numpy.org/doc/stable/reference/generated/numpy.load.html).
It refuses extra/missing keys, dtype coercion, wrong shape, object arrays,
nonfinite values, unsorted/duplicate/out-of-range columns, nonpositive support
or nonpositive D. All 4,116 codes must lie in the original 708,050-column space,
and support sums must equal the actual TRAIN directed-edge count.

**candidate_coefficient already equals original-coordinate c.** Restoration
assigns it directly into the full zero-initialized coefficient vector. It does
not divide by D again. D is checked as provenance only. The original-source
control coefficient is not the accepted parameter vector. Unknown columns
remain exactly zero and all original validation atoms/pairs stay in denominators.

Source data/method is unchanged: noisy-distance<5 Angstrom neighbors, ordered
element-pair 0.1-Angstrom bins, ridge=1e-4 and the original atom-based objective.
Original 500 failed its new controlled stopping observation while the same-target
augmented solve met the original stop/finite rule. Actual BLAS1/restoration and
same-CSR metadata are checked. Original-coordinate KKT/objective values are copied
from the bound prior diagnostic and clearly marked **not recomputed**. No KKT
threshold, validation selection or additional numerical result gate is added.

## Honest new-job origin and VAL boundary

The new fit receipt and artifact model schema identify
`fit_origin=prior_TRAIN_diagnostic_artifact`, parameter estimation in job 4520559,
`current_job_parameter_estimation_performed=false` and
`current_job_TRAIN_geometry_reads=0`. They retain the full original TRAIN
identity set reconstructed from the closed metadata plan, so the unchanged
original evaluator can check TRAIN/VAL record/molecule separation.

The new model has an artifact-specific serializer/restore schema. The ordinary
v2 or old v1 loader rejects it; its dedicated restore validates both the fixed
base v2 library and the added artifact loader source inventory. No old 500
solver receipt is manufactured, and the new job does not claim to have estimated
these parameters again.

Production opens only the existing source adapter's metadata handles, verifies
zero native reads, and consumes **only**
`source.records('PRETRAIN_VAL', original_plan)`. The original evaluator computes
all fixed vector/component/sigma/local-pair metrics on exactly 1,024 records.
No TRAIN geometry is decoded in the new job. Guard and SDK counters distinguish
prior fitting from current VAL reads; offline W&B step 0 labels prior TRAIN
estimation, step 1 contains all fixed current validation metrics.

Coordinate vector RMSE divides by N atoms, component RMSE by 3N, and the explicit
sigma-normalized component MSE by 3N*sigma² with sigma=0.1 Angstrom. Unknown bins
receive zero correction without dropping denominator entries. The old pair-only
approximately 0.0413 Angstrom result is not comparable to coordinate RMSE.
These remain analysis metrics, not a model/architecture selection threshold.

All new files use `BASELINE_v2_ARTIFACT_*` names and explicitly preserve original
v1 FAILED. A new completion requires full current VAL, source revalidation and
SDK finish; Root's actual outer Slurm/supervisor/native-SDK verification still
precedes any final result report. The old v1 report and failed job are untouched.

## Inputs and publication

Input schema: `model_v3_C2_prior_TRAIN_artifact_v2_inputs_v1`.

```text
source_repository
source_request, selection_plan
TRAIN_diagnostic_result, TRAIN_diagnostic_done, TRAIN_diagnostic_input_binding
TRAIN_closure, TRAIN_artifact
runtime_monitor
protocol_registration: {repository, commit, path, sha256}
```

Every file reference is byte-bound. The new protocol includes the base four-file
source inventory plus the five-file artifact runtime inventory, prior TRAIN job
4520559, original request/plan/diagnostic/DONE/binding/closure SHA values and NPZ
SHA/bytes. The supplied protocol is deliberately
`PREPARED_CONDITIONAL_NOT_ADOPTED`: Root fills/verifies the remaining closure and
explicitly publishes **ADOPTED_AFTER_TRAIN_ONLY_DIAGNOSTIC** before actual VAL.
The full-refit entrypoint refuses this artifact-origin protocol, preventing an
accidental repeat of the 24-minute TRAIN build.

Root alone can run after actual CPU tests and public adoption:

```text
python -B accepted_train_artifact_v2.py --inputs /external/closed_artifact_inputs.json --inputs-sha256 <actual-raw-SHA256> --expected-node <Root-selected-CPU-node> --output-root /external/new_first_VAL_run
```

Caps remain 3,300 seconds / 24 GiB / 128 MiB, with the same stricter internal
work/finalization reserve, fixed CPU-only admission, canonical persistent offline
SDK directories and four-link-aware output census. Neither NPZ nor native
geometries are placed in Git. Current-job data-derived outputs remain external.

## Separate Root CPU test request

```text
PYTHONPATH=/share/home/zixiao/descriptor_analysis/MFM_model_v3_c2/current python -B -m pytest -q -p no:cacheprovider test_accepted_train_artifact_v2.py
```

Expected collection: **31 new synthetic cases**, not a PASS claim. A real small
SciPy TRAIN fit supplies candidate parameters; QA C0/failed-original metadata is
explicitly synthetic and is not a numeric observation of 559/482. Tests compare
restored coefficients and original evaluator outputs to that small fit; detect
double division by D; ensure current source reads VAL only; reject NPZ key/dtype/
shape/range/order/support/object/nonfinite/header/size drift; check raw SHA and
full original-source/DONE/supervisor/actual-C0-command/fixed-128guard chains;
reject old success/candidate failure/thread/matrix/plan drift; require new Git
ADOPTED publication; and reject artifact model origin/source relabeling.
