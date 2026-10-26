# Finite Root metadata controller for reviewed Sprime wave2

Source-only delivery: the author did not run Python/AST/tests, SSH, Slurm,
Git or scientific data reads. The eight pure state tests have not run.
Root must integrate/review these five files, run the eight tests on a legal
CPU allocation, pin their real C0/accounting evidence, and explicitly launch.
No controller was started and no new job was submitted by this delivery.

## Fixed authority and existing adoption

This controller is only Main UID1278/loginsonmi, endpoint202.38.247.57:22,
for the actual179-slot/89249-molecule wave frozen by4521486. The manifest
5821B SHA4320aa98c09684e7bd4fbc2392a4c73df9f991d9fa998ba40fc56844436ddf40
and actual124998B plan
SHAd2f592f2dcb0bd8a3d2d62e368da998adec4901ae11126149906f1f268a83827
are fixed in source. All science slot job names come from this actual plan.
The frozen generator3 bytes and existing Root central helper are separately
fixed. Current controller/central source pins are explicitly Root-reviewed
and verified; controller/generator sources are rechecked before transitions.
No frozen generator, queue, producer, mapping, model or other user's source
is changed.

Root's explicit adoption file must include at least these four actual jobs:

| Batch | Stage | Actual job | Actual job name / phase |
|---|---|---|---|
| batch-00001 | prepare |4521489|`dv1_q_sprime_v3_w2_b00001_prepare_20261027_v1` / name without `dv1_q_`|
| batch-00002 | prepare |4521490|same with b00002|
| batch-00001 | run |4521493|`dv1_q_sprime_v3_wave2_b00001_20261027_v1` / name without `dv1_q_`|
| batch-00002 | run |4521494|same with b00002|

The first two prepares were actually C0/68s and65s when Root supplied this
adoption; run terminal status is queried, never assumed. Stage specs exist
under `control/sprime_v3_wave2_stages_v1/batch-0000N/{prepare,run}_v1/stage_spec.json`.
Actual request/submission are `control/{requests,submissions}/JOB_NAME.json`.
Actual activation/registry are
`control/cpu_auto_memory_{activations,registries}/PHASE.json`.
The controller never reconstructs an auxiliary manual job name by guessing.
Missing one of these four adoption keys or a different actual submitted job
ID rejects startup. Any further manual stage must be added to Root's adoption
before launch/resume. Root must stop independent manual stage submissions
while the controller owns the chain, or update/review the adoption first.

Adoption is small Root metadata with schema
`ROOT_SPRIME_WAVE2_CONTROLLER_ADOPTION_V1`, reviewerroot, endpointMain,
uid1278, exact `manifest_reference` and `plan_reference`,
`all_manual_known_registrations_included:true`, and `entries` array. Each
entry has `batch_id`, `stage` and five **existing actual** SHA triples:
`stage_spec_reference`, `request_reference`, `submission_reference`,
`activation_reference`, `registry_reference`. No future job IDs or hashes.

## Root startup review and pure tests

The exact primary is `PY -B ROOTREPO/workflows/data_v1_final/execution/sprime_wave2_controller_v1/controller.py`.
Actual `/proc` primary/fullargv/UID/boot/start ticks/source/launch identity
are recorded; using a different module invocation is rejected. Single
instance uses the own flock
`control/sprime_wave2_controller_v1/wave2_single_instance.lock`.

After Root copies all five files, the following prints **unapproved locator
metadata only**, without Slurm or scientific body calls:

```text
controller.py --adoption ACTUAL_ADOPTION_JSON --print-review-inputs
```

Root uses those actual pins to author a new review with schema
`ROOT_FINITE_SPRIME_WAVE2_CONTROLLER_REVIEW_V1`, status
`APPROVED_FINITE_METADATA_CONTROLLER`, reviewerroot, endpointMain, uid1278,
the printed manifest/plan/adoption/source/publisher identity refs,
`maximum_seconds` at most86400, `maximum_nonterminal_science:2`,
`maximum_nonterminal_aux:1`, `maximum_owned_data_run_pending:4`,
`stop_before_publisher_expiry_seconds:300`, and
`pure_state_cpu_test_reference` below. This is a Root decision after actual
review, not a self-issued controller approval. The exact source array/order
returned by the locator mode is the expected source array.

Root runs on a legal CPU allocation:

```text
PY -B -m unittest workflows.data_v1_final.execution.sprime_wave2_controller_v1.test_state
```

After real execution Root supplies a small PASS receipt with `status:PASS`,
`tests_run:8`, `failures:0`, `errors:0`, `source_references` equal to this
namespace's five actual source refs in `controller.FILES` order,
`job_id` the actual numeric test parent and `accounting_reference` its real
standard `DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1`/raw source. The controller
validates real terminal C0/16CPU, not an unexecuted future test result. This
small receipt is Root's accurate translation of the actual test/Slurm
evidence; it must never claim a fabricated PASS. Eight pure tests cover
TIMEOUT-to-close, prepare-C0, closure conflicts/zero valids, no invented
scientific SUCCESS, UNKNOWN/unstarted HOLD, resource bounds, uncertain
submission no-reissue, and closer priority. They do not establish real
queue integration, full scientific quality or final population release.

Then Root may first perform one metadata observation without any new stage:

```text
controller.py --adoption ACTUAL_ADOPTION_JSON --review ACTUAL_REVIEW_JSON --state-root CONTROL_NEW_STATE_ROOT --root-run-reviewed-wave2 --reason ROOT_EXPLICIT_REASON --max-seconds 3600 --poll-seconds 15 --single-cycle --observe-only
```

State roots must be new literal descendants of
`control/sprime_wave2_controller_v1`. For live advancement omit
`--observe-only`; `--single-cycle` can generate and submit at most **one**
stage, then returns, so it is not a dry run without `--observe-only`.
For a bounded polling foreground/background launch omit `--single-cycle`.
Root owns SSH/background presentation; the controller does not open SSH.
It sleeps15s by default, accepted5..30s, and stops no later than the lesser
of requested `--max-seconds`, Root maximum and the actual existing publisher
identity's expiration minus300s. It never creates or renews that publisher.
Deadline ending sends no signal or cancellation and leaves current Slurm
jobs/observers to their already-authorized guards and natural drain.

## Transition and resource semantics

Every cycle reads only its actual registered request/submission/activation/
registry/spec metadata, real sacct and owned data-run pending registrations.
It never scans task/packet/baseline/LMDB/Parquet bodies or the population.
Fixed headers `prepared.json` and `closed_batch.json` are small metadata.
The frozen generator retains scientific refs as DATA and does not login
hash/parse them. The central helper performs its unchanged materialize,
held queued submission and live observer/activation; project science only
runs on its actual CPU16/node13/no_mem allocation under fresh proof.

Prepare→run requires actual prepare C0 plus the existing actual prepared
header. Run→close requires the actual science parent to be terminal; FAILED
and TIMEOUT are retained and allowed into independent close. Close→DONE
requires actual close C0 and its original metadata chain. Close is preferred
over any ready run, and a ready run over a new prepare. All actual terminal
parents, including failed prepare/close and cleanup seconds observed by
Slurm, are saved as standard accounting plus unmodified raw sacct. Multiple
point-in-time records of one job are not additive: Root's final owned master
deduplicates each parent by actual job ID and appends later cost changes.

At most2 nonterminal wave science parents and1 nonterminal auxiliary parent
are admitted; counting includes PENDING/configuring/completing, which is more
conservative than RUNNING only. The two already manually submitted prepares
are adopted as observed facts even if both still nonterminal, with no new
aux until that count drains. Pending<=4 counts only successful owned
registrations from this data-run's `ROOT/control/requests` and submissions.
Same-UID unrelated/model work is not assigned to this task or modified.
All-user actual free CPUs are still checked by the unchanged central held
queue/startup guard. This controller cannot bypass a live node CPU condition.

Every stage still applies the Root-approved8h science ceiling/8GiB cap,
182×8GiB whole-wave disk reservation and200GB live account reserve. The
requested22912corehours are not a forecast or actual-cost guarantee. Cost
1.5 report-and-continue, final scientific thresholds and Se exception remain.
No new seed, retry, geometry, graph/stereo/order/float64 interpretation or
QM operation is introduced. Max science concurrency is also rechecked by
the unchanged original runner against the exact179 slot names.

Controller state/event/command/account/spec files under its state root are
bounded by8GiB with64MiB output headroom. Central global requests,
submissions/activation/observer metadata remain owned by the unchanged
central helper; their physical usage still contributes to actual shared
quota and the reviewed wave reservation, but is not falsely claimed to be
inside the controller tree cap. Query/helper outputs are bounded2MiB per
metadata read. Current immutable registration frames are cached after exact
pin validation, avoiding repeated full source validation on every poll;
frame/source mutation HOLDs before a new transition.

## Durable submission and HOLD/resume

Each command/transition has immutable event, actual child PID/identity/full
argv, stdout/stderr references and an immutable state snapshot, with fsync.
Only `latest.json` is an atomic pointer to immutable snapshots. A durable
O_EXCL submission intent is written **before** invoking the central helper.
No existing destination is overwritten or deleted. Failed metadata
generation preserves its partial directory and HOLDs instead of regenerating.

An existing exact successful request/submission/activation/registry can be
read and adopted after restart. The complete primary/options/plan/config/
prepared/source/UID/job/resources/spec and actual central activation chain
must match. A request, intent or ambiguous receipt without a complete
successful registration never triggers another helper/sbatch call. Missing
activation requires Root to recover the existing held job through the
established central workflow and provide actual adoption/activation refs;
the controller never resubmits or guesses its state.

Metadata helper/query processes are allowed bounded wait. A process still
live past that limit/deadline is recorded as unresolved with its real PID;
no signal is sent and the controller HOLDs. This can leave a metadata-only
child finishing naturally. Root must inspect its actual outcome/central
registration before resuming. Merely waiting is never approval to retry.

Closure errors, invalid metadata chain, valid_packets0, consumed UNKNOWN,
external conflicting consumption or unstarted tasks produce a persistent
HOLD and no new dispatch. Legal scientific failure packets with valid real
readback are not relabelled SUCCESS. UNKNOWN is not a chemical result or
unstarted task; consumed attempts cannot retry. Unstarted continuation and
whether unrelated untouched keys may proceed need an independent Root
decision; this controller does not infer permission. A failed prepare or
close likewise HOLDs, with its real parent accounting retained.

To resume a normal single-cycle or lease-ended run use the same state root
and `--resume`; existing actual registrations are reconciled. A HOLD may
only resume under a **new** Root review binding
`supersedes_review_reference` to the prior review and
`resume_from_state_reference` to the exact current immutable state, with
updated complete adoption and identical frozen population/source pins.
Unresolved intents still HOLD unless actual matching successful registration
and activation now exist. New review or elapsed time never authorizes another
submission of that stage/attempt. Root may need a separate manual bounded
repair/continuation protocol; the controller never deletes old evidence.

All179 initial batch closures yield only
`ALL179_INITIAL_BATCHES_CLOSED_NOT_GLOBAL_QUALITY_RELEASE`. Original320
imports (including two historical UNKNOWN), full90069 outcome/index,
complete owned-parent cost classification, original exclusion gates,
common/int64 mapping and production quality release remain independent.
