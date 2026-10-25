# Exact analysis queue v3 and disjoint observers

Source only; no Python, tests, source scan, Slurm, activation or release was run
by this author. Root must integrate, inspect, run check_repository and execute
the 14 new queue fixtures plus 8 source-status fixtures in a reviewed allocation.
Existing queue_v1 files, original four jobs959–962, registry and live observer
are never modified or terminated. This module has no submission command.

This v3 source replaces an unexecuted child-only v2 draft. Root review found two
real blockers: site held NumNodes=1-1 was rejected, and true performance profiles
were incorrectly rejected by the fixture/pilot equivalence. The old v2 files
remain untouched as negative evidence; only v3 is intended for Root integration.
The new14 checks retain the old12 cases and add these two explicit boundaries.
No v2 source has been executed or integrated by this author.
## Scope and resources

v3 adds honest pilot=false analysis stages to the old pilot-only materializer.
The request still uses DATA_V1_QUEUED_REQUEST_V1 and the frozen queue_v1.launch,
validate_request, startup/job/memory/freshness validators. It requests exactly
16CPU/64GiB, cpu partition, exclusive=user, <=4h, and old submit --no-requeue.
Zero or missing foreign memory remains unbounded. No small-test exemption,
paid server, GPU, new QM/UFF role or scientific acceptance is granted.

The BOUNDED_METADATA_PREPARATION name describes the stage's place in a pipeline,
not a claim that its runtime only reads small metadata. For example source-status
prepare builds a real all-record canonical SQLite index in the allocated CPU
job. Only materialization, activation and observing small scheduler/source
metadata belong on login. Raw/Parquet/LMDB/gzip scientific inventory always runs
inside the actual allocation after the fresh frozen startup proof.

A new spec may use ROOT_REVIEWED_QUEUED_STAGE_SPEC_V1 or V3. It must declare
scope_key, scope_parameters, pilot, wall_seconds, estimated_peak_output_bytes,
execution_argv, and scope={mode, review: small pin, parent_profile: small pin|null}.
All non-resource producer fields are copied exactly into the request, including
source_status_stage, source_status_manifest=False and stage_output_cap_bytes.
A producer field cannot overwrite a queue control field. A bound-request check
reopens the pinned original spec, compares every domain field and substitutes
only __ROOT_STARTUP_PROOF__ in argv. All original/supplementary source pins stay.

The separate scope.review JSON has schema EXACT_ANALYSIS_QUEUE_SCOPE_ROOT_REVIEW_V3,
status APPROVED_FOR_EXACT_STAGE, reviewer root; it exactly binds scope_key,
scope_parameters, scope_mode, pilot, wall_seconds, estimated_peak_output_bytes,
execution_argv before token replacement, source_status_stage when present,
and stage_output_cap_bytes. parent_evidence_references is an explicit list of
small physical pins. parent_profile must be null or equal an exact parent pin.
The review does not reference the spec's own hash, avoiding a circular hash.
Root's real review must evaluate the parent evidence; a copied boolean alone
is not a real performance result or a global scientific release.

Modes:

- FIXTURE_ONLY: pilot=true; no real source processing.
- BOUNDED_METADATA_PREPARATION: pilot=false; exact source-index preparation,
  performed in the real allocation, with explicit stage/output bounds.
- BOUNDED_PERFORMANCE_BATCH: honest pilot=true or false, exactly matching the Root review; first finite shard/profile scope,
  requiring bounded_batch_limits_reviewed=true, no implicit later shards.
- FULL_SOURCE_AFTER_PROFILE: pilot=false; requires non-null parent_profile,
  profile_reviewed=true and approved_profile_reference equal that exact pin.
  Each new full stage requires its own Root review and actual profile.
- FULL_SOURCE_INVENTORY_PRIOR_CRC: pilot=false for a first complete gzip EOF
  inventory, not screening or candidate release. It requires pinned prior CRC
  evidence such as actual4520348, crc_full_eof_actual_passed=true,
  inventory_only=true, candidate_release_authorized=false and stage cap<=10GiB.
  It does not circularly demand a previous full-inventory runtime profile.

Stage output cap and whole-phase quota declaration are distinct: a prepare may
write at most24GiB while its request/review conservatively reserves60GiB for the
whole phase. cap must be positive and <=whole-phase budget; it is never silently
changed into the larger budget. Every proof retains>=200GB after the request's
full conservative declaration. Inventory's10GiB rule applies to its own stage cap.

Materialization pins every queue_v1/*.py, every new queue_v3/*.py, original
probe_memory.py, queue decision, spec, scope review and parents, plus all explicit
producer source refs. Data references are locators only and are not stat/hashed
or opened on login. Materializer itself must run from Root's integrated repo.

## Registration, claims and coexistence

New registry paths are exclusively R/control/queue_v3_registries/<phase>.json;
observer outputs are R/control/queue_v3_observers/<lease_name>. v3 reads every
legacy R/control/queued_phase_*.json registry and every new canonical registry.
It requires globally disjoint jobIDs, request paths, startup proof paths and job
names, including within one registry. Any existing control/queue_v2_registries/*.json rows are also read for disjointness. Legacy activation files are ignored by
schema; new activation evidence goes in control/queue_v3_activations, outside the
registry directory. Unknown JSON schemas in the new registry directory reject.

A short queue_v3_registration.lock serializes new registrations only. Persistent
queue_v3_claims/jobs/<jobid>/claim.json and independently hashed request/proof
claim directories are created exclusively before the registry. They bind the
literal registry path and exact request/receipt pins. Existing claims reject a
new activation, even if its registry was lost. Partial registration stays as
unknown evidence for Root reconciliation; no cleanup, retry or resubmission is
automatic. Do not delete claims to get a job admitted.

Each observer uses a per-registry SHA lock under queue_v3_phase_locks. It never
opens the old root_queue_observer.lock, never observes or proves old jobs, and
checks claims before proof creation for its exact registered row. An expired
observer may be replaced by a new finite observer/output for the SAME registry
and same jobs once its per-phase lock is free; existing claims are verified,
not recreated. Expiry never means submit another physical job.

proof_v3.py is an exact function copy of frozen create_proof except for the
single redundant top-level memory_basis=admission['memory_basis'] tag required
by new producers. The tag is set before the unchanged original proof/ready writes;
there is no modification after ready publication. verify_proof_delta.py compares
the exact inverse function text and normalized AST. All old math and validators,
120s target-clock freshness and proof/ready ordering remain unchanged.

Activation verifies every own job is actually PENDING/JobHeldUser/Priority0,
UID1278, exact ID/name/cpu partition/node/16CPU/64G/USER/Requeue0/script/workdir/
wall. It registers claims, starts an observer and requires a live /proc identity
and fresh same-boot heartbeat before releasing its own still-exact held IDs.
Identity binds PID/UID/boot/start_ticks/PGID/SID/full argv hash/cgroup and physical
source/registry pins. There is no signal, cancel, requeue or change to another job.
Held NumNodes accepts only literal 1 or the observed site range 1-1, and TRES must explicitly contain node=1/cpu=16/mem=64G without GPU resources. The frozen RUNNING startup still requires NumNodes=1. No broader range is admitted.
Failure leaves jobs held or partially released with immutable evidence for Root;
there is no automatic repeat activation or resubmission.

## Root commands after integration and review

    python -B -m workflows.data_v1_final.execution.queue_v3.materialize \
      --spec NEW_EXACT_SPEC --node ACTUAL_CPU_NODE --job-name dv1_q_NEW_NAME
    python -B -m workflows.data_v1_final.execution.queue_v1.submit \
      --request R/control/requests/dv1_q_NEW_NAME.json --keep-held
    python -B -m workflows.data_v1_final.execution.queue_v3.activate \
      --job-name dv1_q_NEW_NAME \
      --registry R/control/queue_v3_registries/NEW_PHASE.json \
      --observer-output R/control/queue_v3_observers/NEW_LEASE

Names must satisfy lowercase [a-z0-9_]+ for phase/lease and dv1_q_[A-Za-z0-9_]+
for jobs; replace R with its absolute run root. Dependencies are exact --afterok
IDs and remain subject to frozen actual-C0 evidence at startup. A new fixture
job execution_argv may run -m workflows.data_v1_final.execution.queue_v3.run_checks;
it discovers exactly14 new v3 and8 source-status fixtures, rejects skips and
writes control/queue_v3_checks/<actual_jobid>.json. It does not rerun the previous
12 queue_v1 tests or execute a scientific stage.

All sources are prepared but untested by this author. Queued/terminal/fixture
states never certify a complete status audit, identity coverage, filtered pool,
benchmark, D1–D7 release or the user's complete guide objective.

## Exact v3 scope-review template and reservation rules

The review schema is EXACT_ANALYSIS_QUEUE_SCOPE_ROOT_REVIEW_V3. A new spec uses
ROOT_REVIEWED_QUEUED_STAGE_SPEC_V3 (V1 is accepted only with all new explicit
scope fields). Copy the following fields from the concrete spec into the review:

    schema = EXACT_ANALYSIS_QUEUE_SCOPE_ROOT_REVIEW_V3
    status = APPROVED_FOR_EXACT_STAGE
    reviewer = root
    scope_key = spec.scope_key
    scope_parameters = deep copy of spec.scope_parameters
    scope_mode = spec.scope.mode
    pilot = spec.pilot
    wall_seconds = spec.wall_seconds
    estimated_peak_output_bytes = spec.estimated_peak_output_bytes
    execution_argv = spec.execution_argv before startup-proof replacement
    source_status_stage = spec.get(source_status_stage), null if absent
    stage_output_cap_bytes = spec.get(stage_output_cap_bytes, estimated_peak_output_bytes)
    parent_evidence_references = actual small physical parent pins

Write this review first and obtain its physical pin, then set the NEW spec's
scope={mode,review:<that pin>,parent_profile:null|an exact parent pin}. There is
no review reference to the spec's own hash, so no circular hash. The materializer
then pins both immutable files. FIXTURE_ONLY allows [] parents; all other modes
require at least one real parent pin. Profile-only review adds
bounded_batch_limits_reviewed=true. A full-after-profile review adds
profile_reviewed=true and approved_profile_reference=scope.parent_profile.
Inventory-only review adds inventory_only=true, candidate_release_authorized=false,
crc_full_eof_actual_passed=true and crc_receipt_reference equal an actual parent
pin; stage output cap must be<=10GiB while a larger whole-phase reservation may
be retained. These flags never replace Root's actual evidence review.

For canonical status prepare the concrete scope_key may be
source_status_v1_canonical_index_prepare, source_status_stage=prepare,
mode=BOUNDED_METADATA_PREPARATION, pilot=false, stage cap25769803776 and whole
phase64424509440 bytes. For the22-fixture job: mode=FIXTURE_ONLY, pilot=true,
wall600, stage/whole16777216 bytes; spec may omit source_status_stage while its
review explicitly records null. These are schema examples, not approvals or
precomputed future pins.

Queue-reserved fields cannot be overwritten by producer metadata: schema,
kind/partition/node/job_name/resources/wall/budget, workdir/exclusive flag,
startup proof/wait, authority/script/source/data refs, execution argv/dependencies,
and root_review. Explicit spec resources are consumed and validated rather than
copied over request controls. In particular an existing producer root_review
must be deliberately renamed producer_root_review in a NEW wrapper spec, with
the original producer spec pinned for provenance; do not loosen the collision
check or silently discard the producer's opinion. Other producer domain fields,
including false flags, remain exact copies and are checked against that wrapper.
