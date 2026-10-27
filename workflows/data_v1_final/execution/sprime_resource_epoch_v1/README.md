# Explicit finite S-prime resource epoch (source only)

This namespace is a small Main-only resource metadata binding. It does not start
or renew a publisher, submit a job, execute Python tests itself, open scientific
bodies on login, alter once keys, or change original scientific code. No actual
new publisher, identity, healthy snapshot, probe C0, executable range or science
result is supplied with the source. All referenced bytes/SHA must already exist.

The actual primaries remain `formal_cpu_auto_prepare_mapping_v1/prepare_batch.py`,
`formal_cpu_auto_v3/run_batch.py`, the original close-index primaries, and the
original `n1_pprime2_pilot_v4/quota_provider.py`. The new controller directly
inherits v4 discover/run and v3 registration/CG/locks/accounting. It changes only
resource metadata generation, future resource argv binding and its own launch.

Original constraints remain: Main UID1278/CPU13/16CPU/no memory or exclusive
requests, scientific8h and7200s dispatch reserve, exact tasks/once/seed/recipe,
SCI2+aux1/owned pending4,182x8GiB reservation plus publisher64MiB/admin64MiB and
200000000000B account headroom. Provider30s refresh/60s poll/120s freshness,
finite <=86400s, unchanged node13 XFS/NFS/autofs/DNS/shared marker evidence.
Old and new publishers have independent directories. An existing Client never
switches identity. No science receives a signal. Failures preserve partial
metadata and require Root review; no cleanup, regeneration or automatic retry.

The old v4 identity expires1793118990.2097795. Old controller300s is a controller
reserve, not an8h scientific lease admission gate. Neither this namespace nor
original Budget adds that gate. Root chooses actual free CPU before starting a
new finite publisher; one lease is not a promise that all179 batches finish.
The original provider stops sampling60s before expiry. A new controller has one
Root-reviewed absolute deadline <=new expiry-300; resume does not shift it.

The old900s conformer probe4522070 could not construct original Budget because
its conformer dispatch reserve is7200s. Root confirmed it was unstarted and
cancelled it: `control/accounting/sprime96_invalid_probe_cancelled_4522070_v1.json`,
1042B SHA4c4ca6786948009ad8f8bbc11ba712d503d4b718b9e5c3da80561bb0d17c964a3,
zero core-seconds. This does not explain old scientific run4521922, whose initial
failure remains UNKNOWN. The new zero-science probe honestly uses analysis900s,
so original Budget uses its unchanged analysis cleanup reserve90s. It calls the
original Budget/Client/quota/memory observation, never `load_science/process_task`.
It is not described as exercising the conformer7200s branch.

## Root metadata CLI and approval boundary

Install the seven files together in Root repository under this same namespace.
Use the existing Main chemprop PY and Root/dependency PYTHONPATH. All following
commands are deployment instructions, not actions already performed. Each output
control directory must be fresh; Root is the only metadata executor/integrator.
Scientific/data references are inherited and never read or rehashed by these
login helpers. They use existing central v2 exact specs; no new queue exists.

### 1. Draft a provider review; Root approves a separate copy

Root request JSON fields: schema `ROOT_REQUEST_SPRIME_PROVIDER_REVIEW_TEMPLATE_V1`,
status `REQUESTED_FOR_REVIEW`, requested_by `root`, publisher_output_directory a
new literal directory under RUN/control. It is a request to draft, not approval.

```sh
"$PY" -B -m workflows.data_v1_final.execution.sprime_resource_epoch_v1.metadata provider-template \
 --root-request ROOT_REQUEST --publisher-output FRESH_PROVIDER_DIR --output FRESH_DRAFT_DIR
```

This writes only `provider_review.template.json`, status
PENDING_INDEPENDENT_ROOT_REVIEW/reviewer null. Root independently copies it to a
new immutable approved review, sets original provider-required status
APPROVED_FOR_EXACT_SAME_STORAGE_PROVIDER/reviewer root, and preserves all policy
and actual evidence pins. It must not rewrite the original v1 review or v4 dir.

Root explicitly starts the original publisher with this approved review only
when ready, using its exact original CLI (no command in this helper starts it):

```sh
"$PY" -B "$REPO/workflows/data_v1_final/conformers/n1_pprime2_pilot_v4/quota_provider.py" \
 --review NEW_APPROVED_PROVIDER_REVIEW --output FRESH_PROVIDER_DIR --max-seconds 86400
```

Root captures actual launch receipt with the existing schema
ROOT_ACTUAL_MAIN_N1_V4_FINITE_QUOTA_PUBLISHER_LAUNCH_V1: endpoint/uid,
review_reference, actual_pid/start_ticks/boot_id/argv/cgroup,
maximum_runtime_seconds, science_jobs_launched_by_publisher=0. Use real process
fields; no invented identity, future hash or old launch receipt. Keep old history.

### 2. Bind actual new publisher facts; no science stage yet

Root writes a small independent approved binding JSON:

| Field | Required actual value |
|---|---|
| schema/status/reviewer | ROOT_EXPLICIT_SPRIME_RESOURCE_EPOCH_BINDING_V1 / APPROVED_NEW_FINITE_RESOURCE_FACTS_ONLY / root |
| endpoint/uid | 202.38.247.57:22 /1278 |
| previous_quota_reuse_review_reference | Original wave2 freeze-stage quota_reuse_review.json pin |
| provider_review_reference | New approved provider review pin |
| publisher_identity_reference | New actual identity.json pin |
| publisher_actual_launch_reference | New actual launch receipt pin |
| first_healthy_snapshot_reference | Actual immutable healthy observation_NNNNNN.json pin, currently fresh |
| whole_wave_output_reserve_bytes |1563368095744 (=182x8GiB) |
| provider_output_reserve_bytes/admin_output_reserve_bytes |67108864 each |
| quota_reserve_bytes |200000000000 |
| scientific_authority_is_separate/publisher_auto_renew |true /false |

```sh
"$PY" -B -m workflows.data_v1_final.execution.sprime_resource_epoch_v1.metadata bind \
 --root-review ACTUAL_APPROVED_BINDING --output FRESH_BIND_DIR \
 --root-approve-exact-stage --root-reason 'Root explicit independent finite resource lease'
```

Bind verifies actual live PID/start/boot/argv/cgroup and original Q snapshot
validation, writes new quota_reuse_review.json plus epoch_manifest.json, and
retains old resource references. No executable science stage or range is emitted.

### 3. New-chain CPU13 probe, then actual C0 accounting closure

```sh
"$PY" -B -m workflows.data_v1_final.execution.sprime_resource_epoch_v1.metadata probe-stage \
 --epoch ACTUAL_EPOCH --probe-output FRESH_RUN_ARTIFACT_PROBE_DIR --output FRESH_PROBE_STAGE_DIR \
 --root-approve-exact-stage --root-reason 'New epoch CPU13 zero-science resource observation'
```

Root submits/activates this analysis900s/16CPU/no_mem/128MiB spec through existing
central v2 with exact CPU13 and fresh proof. Its actual execution is the new
`probe` module. No original scientific bodies, metadata task arrays, UFF/QM or
old2070 are used as a substitute. Startup validates the declared new epoch first;
the original Client then observes actual CPU13 storage and the new publisher.

```sh
"$PY" -B -m workflows.data_v1_final.execution.sprime_resource_epoch_v1.metadata close-probe \
 --epoch ACTUAL_EPOCH --probe-report ACTUAL_RESOURCE_PROBE_JSON --probe-proof ACTUAL_STARTUP_PROOF \
 --accounting ACTUAL_C0_ACCOUNTING --output FRESH_PROBE_CLOSURE_DIR \
 --root-approve-exact-stage --root-reason 'Actual new-chain CPU13 C0 and original healthy Budget closed'
```

Closure requires source/request/full argv/config/output identity, actual new
publisher quota witnesses, no STOP/failure, unchanged reserve and memory samples,
zero science calls, real Main CPU13/16CPU C0 accounting/raw UID. C0 alone or an old
or mixed epoch observation is insufficient. Historical quota validation uses the
actual recorded CPU observation end time, never a substituted snapshot timestamp
or a claim that an old sample is currently fresh. Each new stage still requires
current original120s/expiry validation. Only this closure unlocks science
metadata generation. A new binding without its own CPU probe cannot reuse this.

### 4. One explicit original500 unstarted96 attempt and terminal close

Use the existing recovery96 Root decision and separate single96 wave review
formats. The decision must bind this new probe report/proof/accounting and set
storage_review_reference to the new epoch's root_binding_reference; the separate
wave review binds the same decision/storage. Probe selectors are
`["original_budget_report"]`, `["job_id"]`, `["new_UFF_QM_calls"]`.
Preserve all original500/task pins, recipe/once/seed, original failures/costs,
new name/output, and original CPU13/16CPU/no_mem8h8GiB/concurrency1 limits.

```sh
"$PY" -B -m workflows.data_v1_final.execution.sprime_resource_epoch_v1.metadata run96 \
 --epoch ACTUAL_EPOCH --probe-closure ACTUAL_PROBE_CLOSURE --decision ACTUAL_ROOT96_DECISION \
 --wave-review ACTUAL_NEW_SINGLE96_WAVE_REVIEW --output FRESH_96_RUN_CONTROL \
 --root-approve-exact-stage --root-reason 'Root explicit old500 unstarted continuation using new resource epoch'
```

Original K.derive_plan/derive_prepared supply their reversible metadata lineage;
no CPU freeze/prepare is claimed. New continuation_bundle includes actual epoch
and probe closure pins, consumed later by the original v4 Recovery validator.
The run primary and its five options are original, with new quota review path.
After actual terminal run and accounting, invoke `close96` with the same epoch,
probe-closure, decision, wave-review, plus --continuation-bundle/--request/
--submission/--accounting/--output and Root approval/reason. It uses original
close_index_v2; no retry, outcome upgrade or packet read happens on login.

### 5. Actual96 closure precedes the remaining97..179 controller

Root constructs the existing v4 continuation adoption map after real new96 run
and close: retain old HOLD, old94 closures, actual95 late close, failed96 and zero
close costs, and adopt actual new96 registration/complete500 closure. Both new96
run/close must use this epoch. No future registration or SHA can appear.

```sh
"$PY" -B -m workflows.data_v1_final.execution.sprime_resource_epoch_v1.metadata controller-template \
 --epoch ACTUAL_EPOCH --probe-closure ACTUAL_PROBE_CLOSURE --recovery-map ACTUAL_V4_ADOPTION_MAP \
 --prior-controller-review ACTUAL_ORIGINAL_V3_REVIEW --recovery-tests ACTUAL_V4_THREE_TEST_REPORT \
 --epoch-tests ACTUAL_NEW_THREE_TEST_REPORT --deadline-unix-seconds ROOT_FIXED_ABSOLUTE_DEADLINE \
 --output FRESH_CONTROLLER_DRAFT_DIR --root-approve-exact-stage --root-reason 'Root finite remaining original stages'
```

The template is independently approved by Root in a separate immutable copy;
it is never self-signed by this command. Its explicit delegation covers only
exact original initial stages97..179, SCI2+aux1/pending4, original plan/config/
slots/tasks/headers and new quota CLI path. It requires the actual new probe C0,
actual96 complete closure, original v3/v4 tests, and three new pure tests with
real Main C0 accounting and exact source lists. Future stages cannot be emitted
before those actual facts and Root approval exist.

```sh
"$PY" -B -m workflows.data_v1_final.execution.sprime_resource_epoch_v1.controller \
 --review ACTUAL_APPROVED_EPOCH_CONTROLLER_REVIEW --state-root NEW_STATE_UNDER_OLD_CONTROLLER_BASE \
 --root-run-reviewed-wave2 --reason 'Root explicit finite resource epoch' --observe-only --single-cycle
```

Root then starts the same exact approved controller without observe-only when
its actual metadata observation is satisfactory. It reuses the original global
wave2_single_instance lock and CG outer submission lock. Old exact controller
must no longer be live. Actual old1..95 and old96 prepare use old argv; new96
run/close and future97..179 use new argv. Existing workers do not change resource
identity. Future97..179 retain original plan/prepared bytes: original scientific
validators explicitly permit changing only --quota-reuse-review. No additional
plan/header derivation is needed or claimed for them.

For reviewed direct Root use, `metadata future-stage --stage prepare|run|close
--batch-id batch-NNNNN --epoch ... --probe-closure ... --controller-review ...
--accounting ACTUAL_PARENT --output FRESH_DIR --root-approve-exact-stage
--root-reason ...` generates one exact stage; run/close also need --prepared,
close --request/--submission. It requires the same post96 approved controller
review and actual chain. No helper submits. The thin controller calls this
bounded helper while holding the unchanged CG outer fd, then invokes the
unchanged central submit helper and durable intent protocol.

Resume uses the same absolute deadline and review. A HOLD needs new Root review
pinning previous_epoch_state_reference and supersedes_epoch_review_reference;
it does not silently retry partial generation or consumed tasks. This first
epoch implementation does not hot-adopt another publisher into already-issued
requests or support an automatic sequence of leases. A later independently
reviewed epoch must explicitly retain all new historical registrations too.

## Source-only validation handoff

Three new pure unittest boundaries cover exact quota-argv-only replacement,
unchanged provider policy and absolute finite deadline, and rejection of old,
mixed, stopped or incomplete new-chain probe evidence. They create no files or
processes and have not been run by the source author:

```sh
"$PY" -B -m unittest workflows.data_v1_final.execution.sprime_resource_epoch_v1.test_contract -v
```

Root's actual CPU report for these three tests must have status PASS,
tests_run3/failures0/errors0, source_references=contract.sources(), actual job_id
and accounting_reference. Preserve the separate original v4 three-test report;
do not relabel one as the other. Root performs source/AST/pure checks, deployment,
all real process observations, accounting, central submission and execution.
This source grants no D1 signing, final mask/statistics, Common freeze, scientific
quality release or P-prime exception.
