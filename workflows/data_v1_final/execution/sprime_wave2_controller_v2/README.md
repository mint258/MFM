# Finite wave2 controller v2: one explicitly adopted batch33 metadata repair

Source-only replacement. Original v1 five files, generator, central helper,
provider, science kernel and completed outputs stay frozen. Root integrates,
runs the original8 plus new4 pure tests on actual16CPU, then supplies a new
independent review. No child Python/AST/tests/SSH/Slurm execution occurred.

v2 inherits the v1 controller's exact179 slots/89249 original keys,16CPU13,
maxSCI2/maxaux1/owned-pending<=4, finite publisher expiry−300,15s polling,
O_EXCL intent/registration/event/state and shared single-instance lock.
Only Root's independently completed **batch-00033 close** may replace the
failed metadata job4521632. No prepare/UFF/task/seed/once retry is created.
SCI33 remains actual4521623; SCI34 actual4521633 is rediscovered/accounted
normally. Failed4521632/diagnostic4521637/new repair/test costs remain in the
complete Root ledger; the repair event also preserves actual old/new parent
accounting. Current diagnostic8 Client PASS does not identify old failure.

Use the **same actual old state root** `control/sprime_wave2_controller_v1/live_v1`
with explicit --resume. This preserves deterministic registration/spec paths
for every old known stage and the same global lock. Using a new state root
would make existing requests point to absent spec paths and is not recovery.
All old state/event files remain immutable; new states and launches are added.
The actual primary/HERE/source pins identify v2, never falsely v1.

```text
PY -B ROOTREPO/workflows/data_v1_final/execution/sprime_wave2_controller_v2/controller.py --adoption ACTUAL_ALL_MANUAL_ADOPTION --repair-map ACTUAL_ROOT_REPAIR_MAP --print-review-inputs
PY -B ROOTREPO/workflows/data_v1_final/execution/sprime_wave2_controller_v2/controller.py --adoption ACTUAL_ALL_MANUAL_ADOPTION --repair-map ACTUAL_ROOT_REPAIR_MAP --review ACTUAL_NEW_V2_REVIEW --state-root OLD_LIVE_STATE_ROOT --resume --root-run-reviewed-wave2 --reason ROOT_REASON --max-seconds FINITE --poll-seconds 15 --single-cycle --observe-only
```

Only after Root reviews this actual metadata observation, a finite launch can
omit single-cycle/observe-only with the same approved scope. No automatic
publisher renewal or Slurm signal/cancel is added. All unknown, invalid chain,
empty close, failed producer or ambiguous submit still HOLD, never retry.

The new review schema is ROOT_FINITE_SPRIME_WAVE2_CONTROLLER_REVIEW_V2, status
APPROVED_FINITE_METADATA_CONTROLLER/reviewer root. All original review fields
remain, with actual12-test receipt/accounting and complete new `sources()`
(seven own + original five + unchanged generator/helper/central refs).
It adds `repair_map_reference` and `repair_original_hold_reference`; the
ordinary `supersedes_review_reference`/`resume_from_state_reference` still
bind the exact current latest state for a new review. The repair's original
HOLD reference remains distinct from later resumed state snapshots.

Root repair-map schema ROOT_SPRIME_SINGLE_CLOSE_REPAIR_MAP_V2, status
APPROVED_SINGLE_METADATA_CLOSE_REPLACEMENT, reviewer root, endpoint Main,
UID1278. Required fields:

* exact manifest_reference/plan_reference; batch_id=batch-00033, stage=close,
  failed_job_id=4521632, science_job_id=4521623, no_science_retry=true;
* resume_state_reference = immutable original actual HOLD/cycle322 state;
  its close actual_registered_references must equal failed_registration;
* failed_registration and replacement_registration each contain actual
  stage_spec/request/submission/activation/registry reference fields;
* failed_accounting_reference: real standard/raw FAILED1:0 parent4521632;
* replacement_accounting_reference: real standard/raw C0 replacement parent,
 16CPUs. The new job ID is read from its actual submission, never predicted;
* replacement_output_root = exact wave2/batch-00033/closed_root_repair_v1;
  replacement_primary_reference = actual new close_index_v2/run.py;
  replacement_source_references = actual five new closer files in its FILES
  order (`__init__`,admission,run,test_admission,README).

No map is READY until the replacement close and all real registrations/C0
exist. Root creates it after that observation; this source generates no
future refs/approval. On construction the map validates original failed
registration/state/cost, new actual C0/pins and strict single-stage literals.
Only then it installs this existing actual registration in the in-memory
adoption set. It is not a new submission or a science-success assertion.

Both required integration points change together: expected close argv uses
the new primary/output only for33, and discover reads only its new
closed_batch.json. Its report must still match science parent4521623/plan and
the unchanged `close_hold` gates. All other stages retain the frozen default
generator paths, names, args and source requirements. There is no automatic
resubmit of the old failed close or any other stage. Final global completion
must consume the actual new33 closure ref and keep both closure costs in the
complete owned accounting; this controller does not publish Common/quality.
