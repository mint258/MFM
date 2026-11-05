# Archive v9:559 TRAIN diagnosis and549 A03 — prepared, not executed

Root alone submits CPU tasks. v7/v8 and the44 existing task-index entries remain
unchanged. v7 actual557 passed24 tests/archive562C0; v8 actual568 passed17 tests/
archive569C0. This new source reuses their readonly owner/copy/native/lock/index
primitives. No SSH/sbatch, model fit, target store, validation geometry or NPZ
loading is invoked here. No original artifact is moved/deleted.

##559 expected rows are code-derived saved outputs

Actual559 completedC0/1486s. The original source is pinned to
`7c78234b333dddd87ff5efd0927cf9f25642f455e6c31ca73c9abb936ed1e781`.
Its two direct `run.log(...,step=0/1,commit=True)` calls are checked by AST before
expected values are derived from independent saved outputs:

- controlled_source_solver_return: stop_code7, iterations500,
  solver_wall_seconds34.550494480878115;
- active_jacobi_candidate_return and DIAGNOSTIC_RESULT: candidate iterations74,
  solver_wall_seconds4.711929500102997;
- completed diagnostic status/optional-array metadata: completed_requested_work
  true; every original saved PRETRAIN_VAL count and authorization remains0/false.

DIAGNOSTIC_RESULT, DIAGNOSTIC_DONE, input_binding, input bundle, protocol and
executed-source inventories must cross-bind. Stop/iteration/wall values must
also match the result's independent source/candidate structures. All scientific
types are preserved: counters int, completed bool, wall seconds float.
The actual559 outer helper is `run_cpu_supervised_128m_v1.py`, raw
`23fe5a473918dc420621d98bef49e7e08c7bcd7b43e6f001ae8821bce96b976e`;
its actual four `sources_sha256` are checked, not the older10bb helper. The
command's input path/SHA, C0/exit0/remaining[], GPU-initialization false and
private_storage first_sampling_failure null/budget128MiB are bound as recorded.

There is **no original history.jsonl**. The new comparison is explicitly
`code-derived_saved_outputs`; a new expected.code_derived.jsonl is generated in
the archive only and is never represented as an original fsync mirror. Native
SDKvnfjg196 must independently match every field, explicit step0/1, runID,
exit0 and cleanEOF, with exactly2 committed HISTORY rows. The full normalized
history, all7 scalar CSV values, HTML, SDK bytes and source refs are archived.
The same packet/history/byte/wall limits as the tested v7 reader apply.

The fixed protocol is local
`c65db8b647eb4d39360e31478c4c63368cd84a43`, public
`cd0c434bb39824cd75c24d7c6de0531946da1de5`, same tree
`eecadc77e71a4d290f7a6b00c7d0906e14e58f3f`. These complete references already
exist in the actual input bundle; the current protocol bytes and executed-source
seal are rechecked, without invoking the solver or altering its registration.

559 remains **DIAGNOSTIC_ONLY_COMPLETED_NO_BASELINE_ACCEPTANCE**. Its source
structure named `baseline` contains the new559 controlled solver return, not
the original482 solver stop. Original482 remains FAILED and its stop/iteration
metadata remains unknown/not saved. Stop7 observed in559 is not projected onto
482. Native PRETRAIN_VAL0, no model-selection/KKT/baseline acceptance, and no
online sync are explicit in the archive. Any conflicting scope/count is rejected.

The100361B optional NPZ coefficients/support are hash-only provenance, bounded
by32MiB; the file is not copied or deserialized. Original TRAIN selection/source
metadata refs are verified and retained; no store, CSR or member geometry is read.

##549 is numeric PASS, with speed/adoption still pending

Actual549 completedC0/2196s: native20 batches and500 updates PASS,201216 consumed
base records, no failure/cleanup errors and a complete supervisor. v9 uses an
explicit new case spec and transparent helper parameters, without changing
frozen v7.CASES or other module globals. Both original SDKs must match their
reference/candidate500-row histories, explicit steps/runID/exit0/EOF exactly.
Actual8ece execution/616 prereg and head_checkpointing=false are bound.

This preserves the first genuine A-candidate numerical pass. It does not grant
standalone speed or recipe adoption. Those require the separate ABBA results;
the four upcoming22-history SDKs are intentionally left to a later archive.

## Admission and commands

All files stay in this new external directory. Per-case selected source/evidence
is<=128MiB and final archive<=256MiB. Root supplies a SHA-bound sonmi quota/closed
receipt<=120s old, with actual559/549COMPLETED0:0; it is checked again before
publication. Quota reserve>34GiB, owned>=16CPU allocation, exact expected CPU
node/partition and hidden GPU visibility are required. No CPU-only task belongs
on a GPU node. The task's existing lock and(job_id,run_id) dedup preserve every
old index object. Original482's FAILED entry is checked and retained.

```bash
SOURCE=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/archive_closed_v9_source
# Root CPU-only Slurm: suggest16CPU/16GiB/15min, after live site/quota checks.
$PY -m pytest -q "$SOURCE/test_archive_v9.py"

$PY -u -B "$SOURCE/archive_closed_runs_v9.py" \
  --source-pins "$SOURCE/source_pins_v9.json" --source-pins-sha256 "$SOURCE_PINS_SHA" \
  --quota-closed-receipt "$RECEIPT" --quota-closed-sha256 "$RECEIPT_SHA" \
  --expected-node "$ACTUAL_CPU_NODE" --expected-partition cpu --jobs 4520559 4520549
```

The24 targeted tests are prepared, not executed: fixed logger/field mapping,
typed rows, independent saved-output drift, nonzero/untyped VAL or authorization,
baseline/KKT/model-selection/old482 inference rejection, exact native scientific
rows/step/runID/exit/EOF, and explicit549 wrapper/no frozen-global mutation.
Actual new SDK packet counts are measured, never assumed to equal HISTORY counts.
