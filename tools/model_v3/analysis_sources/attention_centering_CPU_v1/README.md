# One parent / four pytest children: attention-centering full CPU regression

Prepared source only. The candidate's current code/test hashes, request spec,
runtime pins and actual pytest collection are not filled by the preparer.
Root runs this stdlib-only metadata freezer after the actual candidate clean
commit and frozen source receipt exist. No targeted QA parent is added.

Legacy directory:
runs/model_v3_20261026/numeric_full_regression_v1_source.
Identity, process registration, fixture census, worker, supervisor and control
are reused at their exact original paths and bytes. They are not copied,
patched or replaced. CONTROL stays that legacy directory; outputs and plans
stay original runs/model_v3_20261025. The new scheduler script is
O/run_attention_centering_full_regression_v1.sbatch, compatible with the
original submit helper's O-script restriction.

## Root metadata freeze

Root first stdlib-parses this one new Python file, runs bash-n on the one new
wrapper and checks prepared_source_pins_v1.json plus dependency raw SHA.
Then use the actual machine commit/source-freeze refs:

    PY -B NEW/freeze_attention_centering_full_v1.py \
      --prepared-source-pins-sha256 ACTUAL_PREPARED_PIN \
      --code-commit ACTUAL_CLEAN_CANDIDATE_COMMIT \
      --new-test-relative current/tests/test_model_v3_attention_centering.py \
      --candidate-source-pins N/attention_centering_candidate_source_freeze_v1.json \
      --candidate-source-pins-sha256 ACTUAL_SOURCE_FREEZE_SHA \
      --label attention_centering_fullsuite_v1

PY is chemprop/bin/python; NEW is this new prepared source directory, N is
the project runs/model_v3_20261026. Root should expose the existing
O/cpu_git_tools_v1/bin Git2.39.3; the freezer and wrapper do so in their own
process environment. A label is single-use. Partial metadata is retained on
failure; there is no overwrite, cleanup, retry or submission.

The freezer uses the original control.git_clean_snapshot/capture_sources and
full runtime scope: all declared project Python/config/workflow roots,
unchanged explicit external Python refs and original exclusions. The actual
clean HEAD must equal the supplied commit, both before and after source
inventory. All113 prior test names AND raw hashes must remain; the explicit
one new direct test module makes114. Nested/missing/extra test modules reject.
No import/collect-only/pytest/model/data call establishes this set.

Actual candidate source_refs and protected_unchanged_refs are checked against
the supplied source-freeze receipt. The remapped baseline candidate source
list is rehashed in the new tree, so legitimate committed changes to existing
implementation files are recorded with original/actual SHA instead of
mistakenly requiring the new model to have old bytes. Old external frozen
refs remain exact. This receipt is bound as metadata, not promoted to public,
runtime-tested or scientific authority.

Generated files here:
request_spec_v1.json and source_pins_v1.json. Their full code/test inventory is
computed only in that actual Root invocation. planning_only_expected_collection
and new_actual_counts stay null; SA4's planned73 cases or114 modules are not an
actual collected count. All optional tests remain selected; real skips come
from the resulting four JUnit XML files.

The runtime source manifest keeps all original24 legacy refs, plus new
freezer/spec/wrapper/policy/prepared inventory/legacy inventory/candidate
receipt. The original max32-entry validator remains; no cap is relaxed.
The v4 manifest schema is retained because the exact existing supervisor
requires it, while prepared_source_pins has a distinct prepared-only schema.
The contract binds the NEW inventory, original runner/control root, actual
candidate tree and new O-wrapper. No old pins are presented as new pins.

## Actual single Slurm parent

The freezer prints fresh assignment/control/binding/launch paths and a new
submission receipt path. It uses suffix_part0_submission_v4.json because the
unchanged control.validate_artifact_paths explicitly admits that spelling.
The exact path is bound in the new contract.

Root alone submits via original O/submit_cpu_task_v2.py with memory-MiB32768,
new printed scheduler_script, printed launch bindings and printed receipt.
Actual memory85%/MemAvailable/quota/CPU admission remains the original helper.
The wrapper is byte-identical to the old wrapper except job name and an added
new-inventory directory variable/two source-pin references. An exact mechanical
comparison enforces this at metadata freeze.

The wrapper explicitly executes the ORIGINAL supervisor and worker, with
--source-pins NEW/source_pins_v1.json. Dynamic v4 inventory environment flows
from that supervisor to the original worker. Two-stage full-kernel process
registration, fixture/symlink boundaries, fail-only pytest retention, node
whitelist,4threads per each of4pytest, cleanup and original guards remain.

Resources:16CPU32GiB,1h Slurm,3300s supervision,RSS24GiB,whole/private2GiB.
No new runtime/monitor/dispatcher/fixture adapter/test selector exists.

Actual outputs retain original schemas and paths:
O/integration_tests_JOB/{summary.json,sources_before.json,sources_after.json,
shard_00..03.json,shard_00..03.xml,shard_00..03.log};
O/integration_supervisor_JOB.json and identity/journal/storage/fixture metadata.
The summary's real counts and skips, all114 assigned files, disjoint shard
union, complete before/after sources, identities, supervisor cleanup and
independent actual sacct C0 must all close. A freeze or child PASS does not
assert outer Slurm success, public preregistration or C4/scientific adoption.

