# Conditional coordinate baseline v2 — prepared, not adopted or executed

This independent source is only preparation. No actual TRAIN/VAL data or running
diagnostic output was read while preparing it. Original v1 job 4520482 remains
FAILED, with its original stop/iteration count unknown and no validation result.
The original C2 source, runner, request, snapshot, selection and old report tools
are unchanged. Root alone owns CPU testing, public preregistration and execution.

The method is **not automatically chosen**. If the controlled original 500 solve
satisfies the original stop/finite rule, Root may retry original v1 with BLAS1;
this v2 production gate rejects that case. V2 may be considered only when the
TRAIN-only diagnostic's original solve fails that rule and the same-target
active/Jacobi solve meets it. Even then, a new explicit **ADOPTED** public v2
protocol must precede the real v2 fit and native PRETRAIN_VAL access. Merely
publishing this conditional code/template does not activate it.

## Implementation and unchanged quantities

`solver_math.py`, `core_capture.py` and `diagnose_coordinate_lookup.py` are exact
byte copies of the support code already covered by the 20 actual diagnostic
tests in job 4520551, publicly preregistered at
`cd0c434bb39824cd75c24d7c6de0531946da1de5`. Their raw SHA values are checked by
the v2 fitter and included in the new executed-source inventory. The diagnostic
main/old original runner are never called by the v2 program. Only tested common
metadata, CPU admission, SDK layout, census, BLAS control and sparse math helpers
are reused; a new guard logs honest live TRAIN/VAL counters rather than a copied
TRAIN-only zero-VAL message.

The independent v2 builder calls the original frozen `design_matrix` and
`_record_receipt`, in the same record/stack/target order. A synthetic integration
test compares the new CSR buffers, normalized RHS and support **byte for byte**
against the actual old fitter captured by the tested `CoreCapture`. Production
does not monkeypatch the old LSQR, run old 500 LSQR, or forge an old receipt from
augmented statistics.

Actual input remains the same original closed 8,192 TRAIN / 1,024 PRETRAIN_VAL
**record** selection; it is not molecule-uniform and is not D-5. No candidate
selection is rerun, no input request or snapshot JSON is rewritten, no records
are dropped, and no downstream final targets/scores are consulted. Prediction
features remain input elements and noisy-distance<5 Angstrom neighbors in
0.1-Angstrom ordered-pair bins. Epsilon=y-x is an Angstrom displacement, with
the original source-noise seed/epoch policy and sigma=0.1 Angstrom.

The target remains exactly

```text
J(c) = ||A*c-b||² / N_TRAIN_atoms + 1e-4*||c||².
```

Support-zero columns have exact zero norm and optimal coefficient zero. The
active variable change uses
`D[k]=sqrt(column_squared_norm[k]/N_TRAIN_atoms + 1e-4)`, and LSQR solves

```text
[ A_active/(sqrt(N_TRAIN_atoms)*D) ] z = [ b/sqrt(N_TRAIN_atoms) ]
[ sqrt(1e-4)/D                   ]     [ 0                    ]
```

with `damp=0`, zero initial point, actual BLAS1, atol=btol=1e-8, conlim=1e8 and
maximum 2,000 iterations. The old accepted stopping codes (0,1,2,4,5) and finite
full-space coefficients are still required before validation. Unknown columns
are expanded to exact zeros. Original-coordinate KKT residual and objective are
reported with **no additional KKT threshold**. Native VALIDATION never selects
ridge, bins, tolerance, iteration budget or result fields.

Limits remain 3,300 seconds / 24 GiB process RSS / 128 MiB total owned output,
with the already stricter work/finalization reservation used by the diagnostic
support. Original sparse build bounds and the 8-GiB preconditioning numeric bound
apply; no dense coefficient Gram or CSR is saved. Exceeding a budget fails the
new attempt, rather than changing a budget or accepting an incomplete population.

## Honest v2 model, receipts and results

`V2Lookup` owns its v2 serializer/restore method. It delegates prediction to the
original frozen coordinate lookup's prediction implementation and evaluation to
the original `evaluate_coordinate_lookup`. New model schema is
`model_v3_C2_coordinate_lookup_v2`; the old v1 loader must reject it.

The model/fit receipt explicitly separates:

- `source_feature_resource_configuration_v1`: the untouched source adapter
  defaults, including legacy `maximum_iterations=500`. These are provenance,
  **not** the actual v2 solver's iteration limit.
- `actual_solver_configuration_v2`: active/Jacobi, explicit augmentation,
  damp0, BLAS1, zero initial point and maximum 2,000 iterations.
- `augmented_operator_statistics`: actual LSQR stop, iterations and norm/
  condition estimates for the **augmented operator**.
- `original_coordinate_KKT_and_objective`: measurements transformed back to the
  original full coefficient space; no scientific acceptance threshold is added.

Full-space finite/unknown-zero checks precede model return. A failed fit cannot
enter `source.records('PRETRAIN_VAL', ...)`. Only after successful fit are the
entire original 1,024 validation records passed to the original evaluator.
Its complete fixed vector/component/epsilon/local-pair metric dictionary is
retained, with original all-atom/unknown-bin denominators. The old approximately
0.0413 Angstrom pair-distance result is not a coordinate comparison and is not
substituted into any new result. V2 remains analysis only and adds no architecture
or final-pretraining selection threshold.

Every newly written JSON artifact carries the actual v2 method and
`original_v1_job_4520482_remains_FAILED=true`. Names are:

```text
BASELINE_v2_INPUT_BINDING.json
BASELINE_v2_solver_return.json
BASELINE_v2_thread_control.json
BASELINE_v2_FIT_RECEIPT.json
BASELINE_v2_LOOKUP.json
BASELINE_v2_RESULT.json
BASELINE_v2_COMPLETE.json  (only after full fit/eval/SDK finish/source verification)
BASELINE_v2_FAILED.json    (on failure; old v1 is never rewritten)
```

The original/augmented norm meanings are not mixed in an old `solver` record.
Model restore validates the old feature configuration's full semantic hash,
all four executed source SHA values, unique supported codes, finite values,
positive support and the honest v2 solver configuration/accepted stop. Same-shape
radius changes and relabeling the solver as old 500 are rejected.

Output model/fit artifacts contain private coefficient/identity metadata needed
by the original evaluator, stay outside Git, and are not publication reports.
Root's real Slurm/supervisor/native-SDK QA is still required after a real run.
The already tested/frozen v1 reporting tool is not silently reused for v2.

## Future production activation inputs

The bound input manifest has schema
`model_v3_C2_coordinate_baseline_v2_inputs_v1` and these fields:

- `source_repository`: unchanged original C2 worktree.
- `source_request`, `selection_plan`: original `{path,bytes,sha256}` references.
- `TRAIN_diagnostic_result`, `TRAIN_diagnostic_done`,
  `TRAIN_diagnostic_input_binding`: actual completed TRAIN-only diagnostic
  references. The last is that run's `input_binding.json`, not a v2 file.
  Its original input bundle is also rehashed. All must bind the same old request
  and plan and the published diagnostic commit `cd0c434...`; no stop is inferred
  from file names, original job 482 or a missing diagnostic result.
- `runtime_monitor`: the same fixed four-link-aware census source reference.
- `protocol_registration`: `{repository,commit,path,sha256}` for the **new**
  public v2 protocol, distinct from both the original v1 and diagnostic commits.

The shipped `coordinate_baseline_v2_protocol.json` deliberately says
`PREPARED_CONDITIONAL_NOT_ADOPTED` and has no guessed real input/result hashes.
After Root examines the actual diagnostic and decides that the v2 route applies,
it must separately populate the real original request/plan and completed
diagnostic raw SHA fields, set `ADOPTED_AFTER_TRAIN_ONLY_DIAGNOSTIC`, and publicly
commit that concrete protocol before any real v2 run. The source bytes and
mathematical rules do not change in that metadata step. If original 500 succeeds,
this activation is refused and v2 remains unused.

After activation only, on Root's actual CPU allocation:

```text
python -B coordinate_baseline_v2.py --inputs /external/closed_v2_inputs.json --inputs-sha256 <actual-raw-SHA256> --expected-node <Root-selected-CPU-node> --output-root /external/new_v2_run
```

No job submission, actual fit or actual VAL access has been performed by SA-4.
Canonical persistent offline SDK paths are bound before import/init, all original
sources/inputs and new source files are reverified, and two committed fit/VAL
history points are emitted. Online synchronization is never claimed.

## Root CPU validation request

From this independent source directory:

```text
PYTHONPATH=/share/home/zixiao/descriptor_analysis/MFM_model_v3_c2/current python -B -m pytest -q -p no:cacheprovider test_coordinate_baseline_v2.py
```

Expected collection: **17 new synthetic cases**, not a PASS claim. The three
reused support files are byte-identical to the previously tested diagnostic
source; original 20-case proof is preserved. New cases cover original-core CSR/
RHS/support equivalence; small dense ridge oracle; no old-solver invocation;
honest v2 save/restore; source and same-shape semantic drift; unknown-zero and
vector/component/sigma denominator preservation through the original evaluator;
only fitting before synthetic validation; failed-stop/nonfinite fit preventing
VAL; original role/population/sparse-budget refusal; actual temporary Git
preregistration; prepared-only and successful-original-500 rejection; wrong-plan
rejection and an eligible synthetic activation. No native dataset handles are
opened by these tests, and synthetic stop values do not describe job 559 or 482.
