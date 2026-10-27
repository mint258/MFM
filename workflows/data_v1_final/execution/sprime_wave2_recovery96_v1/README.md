# Exact batch96 never-dispatched continuation

This namespace produces small Root-reviewed metadata only. It does not submit,
generate conformers, read task/Parquet/LMDB/packet bodies, alter an attempt ledger,
clear a seed/key, or infer why the historical first Budget observation stopped.
The original `formal_cpu_auto_v3.run_batch.py` and existing
`formal_cpu_auto_close_index_v2.run.py` remain the actual execution primaries.
Their scientific functions, `SCIENCE.process_task` object, recipe, task key,
seed, packet IO and terminal classification are not copied or changed.

The actual old run4521922 FAILED and old close4521923 C0 remain history and cost.
The close must report all500 unstarted, zero consumed/valid/unresolved, and no
errors/external consumption. The original prepared header is the actual
4521921 C0 lineage, with its exact original500 tasks reference. A new header
changes only its plan pointer and adds explicit metadata-derivation provenance;
it does not claim another CPU preparation. A new plan inherits the original
4521486 runtime/import/root-draft lineage and original179-batch context, but
authorizes **one** new96 job with new name/output, max concurrency1 and the
matching460800 allocation-core-second ceiling. It does not claim a new CPU
freeze. It retains explicit references to the original plan and Root decision.
The original run independently verifies the actual320 imports, original500 task
bytes/unique keys and absence of every canonical once key before any dispatch.

Root must independently review storage, the original182-slot8GiB reserve,
the old failed writer's closed future-cap treatment and200GB account reserve.
The current fresh probe is not an explanation or retroactive repair of4521922.
The original run still performs its own Budget observation at actual startup;
if it fails again, no automatic retry or key cleanup is authorized.

## Actual decision and source-only interface

Root writes a new small decision JSON with schema
`ROOT_EXPLICIT_SPRIME96_UNSTARTED_CONTINUATION_DECISION_V1`, status
`APPROVED_EXACT_OLD500_UNSTARTED_NEW_ATTEMPT`, reviewer `root`, batch_id
`batch-00096`, and these booleans:

- `automatic_retry=false`
- `once_ledger_keys_removed_or_changed=false`
- `original_scientific_recipe_taskkeys_seeds_unchanged=true`

Its actual reference fields are:

- `original_HOLD_reference`: exact pinned old327 state; old run4521922 and
  close4521923 must be present and the close-report pin must match.
- `original_closed_reference`: actual old96 `closed_batch.json`.
- `original_close_accounting_reference`: raw-backed actual4521923 C0 account.
- `original_prepare_accounting_reference`: raw-backed actual4521921 C0 account.
- `probe_report_reference`, `probe_startup_proof_reference`,
  `probe_accounting_reference`: actual fresh CPU13 zero-science probe and C0
  account. No future SHA is accepted or generated.
- `storage_review_reference`: actual independent Root storage review.

The decision also supplies explicit arrays of string dictionary keys:
`probe_budget_report_selector`, `probe_job_id_selector` and
`probe_new_science_calls_selector`. These locate the original Budget.report,
string actualjob ID and zero new-science-call counter in Root's actual small
probe report. An empty selector selects the top-level object. There is no
automatic schema guess, alternative-field fallback or payload-value traversal.
The selected report must have stop/failure None, actual quota and memory
observations, the unchanged182-slot reserve/provider64MiB reserve and natural
drain/no signals. A C0 diagnostic with a STOP remains ineligible for new science.

`replacement_closed_directory_name` is a fresh literal `[a-z][a-z0-9_]{1,127}`
directory under the original96 batch parent. Keep old `closed_v1` and generation
output untouched. The helper accepts only Main Root integrated paths and runs
under the existing login metadata policy. Root must coordinate the actual CG
outer serialization lock; this source does not submit or acquire science keys.

Root then writes a separate actual `SPRIME_FORMAL_CPU_ROOT_REVIEW_V3`. Preserve
all original resource/science/cost authority fields and original draft/config
pins; its jobs list is only a copy of old96 slot with **only** `job_name` and
`output_root` changed. It retains16CPU13/no_mem/8h/8GiB, maximum_concurrent_jobs1,
and requested_allocation_core_seconds_ceiling460800. Explicitly bind
`unstarted_continuation_decision_reference` to the decision pin and
`storage_review_reference` to the same actual storage review. The decision does
not contain this later wave-review pin: that would create a circular hash.
All original wave-review fields required by frozen `C.approve_wave` still apply.

```sh
PYTHONPATH="$REPO:$DEPS" "$PY" -B -m workflows.data_v1_final.execution.sprime_wave2_recovery96_v1.metadata run \
  --decision ACTUAL_DECISION --wave-review ACTUAL_NEW_SINGLE96_WAVE_REVIEW \
  --output FRESH_ROOT_CONTROL_DIRECTORY \
  --root-approve-exact-stage --root-reason 'Root actual independent review'
```

This writes `derived_plan.json`, `derived_prepared.json`,
`continuation_bundle.json`, `scope_review.json`, `stage_spec.json`. The produced
stage uses the **original** run path, scope and all five original options. Data
locators are inherited unchanged and never opened/hashed by this helper. All
scientific references, original failure/close/preparation/probe costs and small
authority pins remain in the source/data sets. Only Root's existing central
materializer/submission/observer can execute it after review.

After that new actual run becomes terminal, Root captures its real request,
submission, accounting/raw and invokes:

```sh
PYTHONPATH="$REPO:$DEPS" "$PY" -B -m workflows.data_v1_final.execution.sprime_wave2_recovery96_v1.metadata close \
  --decision ACTUAL_DECISION --wave-review ACTUAL_NEW_SINGLE96_WAVE_REVIEW \
  --continuation-bundle ACTUAL_RUN_METADATA_BUNDLE \
  --request ACTUAL_NEW_RUN_REQUEST --submission ACTUAL_NEW_RUN_SUBMISSION \
  --accounting ACTUAL_NEW_RUN_ACCOUNTING --output FRESH_CLOSE_METADATA_DIRECTORY \
  --root-approve-exact-stage --root-reason 'Root actual terminal close review'
```

This creates a new descriptor and original close_index_v2 stage. Any real
terminal failure is classified honestly; C0 alone does not imply500 valid
packets. Original failed96 and zero-consumed close are never replaced in history.
Fresh names/directories and metadata-only body classifiers are required; a
partial directory is preserved and cannot be regenerated over automatically.

## Validation and controller handoff

Three new pure metadata tests are provided, not executed by the source author:

```sh
"$PY" -B -m unittest workflows.data_v1_final.execution.sprime_wave2_recovery96_v1.test_contract -v
```

They test single96/resource preservation, inverse metadata/source-locator/runtime
lineage preservation without mutating originals, and rejection of any consumed,
unknown or incomplete unstarted mass. Old scientific suites are not repeated.
This source has not executed Python/AST/tests/SSH/Slurm or read scientific bodies.

The old v3 controller cannot directly adopt new96: it hard-codes the original
prepared/output/name and global plan equality. A later explicit v4 adoption map
must retain the old HOLD/review/failed96/zero-close cost, adopt actual95 late-close
and actual new96 run+close registrations, and allow only96's reviewed derived
plan/prepared/output. It must require actual complete no-unknown96 closure before
continuing97..179. This metadata helper does not grant that controller approval,
publish Common/Sprime membership, freeze masks, or finalize a scientific release.
