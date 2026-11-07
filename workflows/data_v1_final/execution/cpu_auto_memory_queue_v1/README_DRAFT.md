# CPU auto-memory central queue — new-authority draft

This draft implements the latest user instruction: use available CPU cores,
request no Slurm memory and no exclusivity, and allow scientific CPU nodes11–19.
The old registered queue_v1/queue_v3 sources, requests, proofs, observations and
claims remain untouched. This author ran no Python, tests, SSH, Git or Slurm.
Root must review these sources, integrate them and obtain actual new-policy
fixture/startup evidence before treating any computation as accepted.

## Public producer API

    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v1 import runtime
    proof = runtime.require_startup(
        startup_proof_path,
        expected_scope_key=EXACT_KEY,
        expected_scope_parameters=EXACT_PARAMETERS,
        expected_execution_argv=EXACT_FULL_ARGV,
        expected_source=Path(__file__),
        expected_kind='analysis',  # or conformer / qm
        required_references=(PLAN_PIN, OTHER_REQUIRED_PINS),
    )

expected_source is a Path/str for the actual main producer or its exact
{path,bytes,sha256} pin. Main __file__, current source bytes, primary Python
file/module and all sys.argv options must match the request; a producer path
passed as an ordinary wrapper argument is rejected. required_references are
exact triples already in source or data references. Small sources are hashed;
large data remain authorized locators only until the scientific producer reads
them after startup. Old 64GiB/85% proofs cannot masquerade as the new schema.

The returned proof has job_id, uid, node, boot_id, request, request_reference,
job_metadata (actual full scontrol text including RunTime), node_metadata,
account_free_bytes, quota_raw, source_references, script_reference,
queue_authority_reference, existing_jobs_all_users and memory_observation.
It explicitly declares memory_policy=SLURM_DEFAULT_UNSPECIFIED,
memory_admission_evaluated=false and memory_limits_requested=false. Scheduler
MinMemoryNode/MinMemoryCPU/TRES and actual memory environment are observations;
they are not invented requests or assumed allocation sizes. Zero, missing or
large memory declarations are recorded without an85% rejection. Target memory
observation failure is recorded; it does not become a zero-memory assertion.

The public contract module also exports validate_request(request,read_small=,
script_text=), validate_bound_request(request,read_small=), and
validate_fresh_startup_proof(proof,request,now_unix=,uid=,boot_id=,
max_age_seconds=120). Freshness remains target-clock120s; it applies at startup,
not repeatedly during a long running scientific stage.

No central RuntimeBudget or signal sender is provided. Each new scientific
adapter owns its output caps, stable owned-process identity, RSS/MemAvailable
observations, optional algorithm soft limits and STOP/new-dispatch behavior.
A soft limit must not be called the Slurm allocation. Stop dispatching and
naturally drain in-flight work; no Root process-kill policy is introduced.
The historical scientific plan may still describe its original64GiB run as
lineage, but the new request and explicit resource binding must be truthful.

## Resource and authority schema

Request schema: CPU_AUTO_MEMORY_QUEUED_REQUEST_V1.
Proof schema: FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1.
Stage spec schema: ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1.
Root scope review schema: EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1.

The authority passed through --authority must have:

    schema: USER_AUTHORIZED_CPU_AUTO_MEMORY_DECISION_V1
    status: USER_AUTHORIZED
    user_statements: [the actual no-memory instruction, actual11–13 instruction]
    memory_policy: SLURM_DEFAULT_UNSPECIFIED
    partition: cpu
    cpus_per_task: 16
    allowed_nodes:
      analysis: [2,8,9,10,11,12,13,14,15,16,17,18,19]
      conformer: [11,12,13,14,15,16,17,18,19]
      qm: [11,12,13,14,15,16,17,18,19]
    max_wall_seconds: 172800
    quota_reserve_bytes: 200000000000
    memory_directives_allowed: false
    exclusive_requested: false
    declared_memory_fraction_admission: false
    record_actual_memory: true
    no_forced_signals: true
    old_scientific_gates_unchanged: true

Actual script/task CPU count is exactly16. max48h is an authorization ceiling,
not a claim that the cpu partition accepts48h; Root must retain actual site time
limits and the smaller original stage bounds. The materialized sbatch script
contains no --mem, --mem-per-*, --exclusive, GPU or overcommit directive. Submit
also removes inherited SBATCH_* environment variables, records only their names,
uses --no-requeue, and checks a real chosen cpu-partition node has>=16 free CPUs.
There is no declaration-percentage admission or memory environment assertion.

## Exact scope review, with no circular hash

A spec contains kind, pilot, wall_seconds, estimated_peak_output_bytes,
execution_argv, source/data refs, scope_key, scope_parameters and
scope={mode,review:<small pin>,parent_profile:<exact parent pin or null>}.
review contains schema/status=APPROVED_FOR_EXACT_STAGE/reviewer=root,
resource_authority_reference=<new authority pin>, kind, scope_key,
scope_parameters, scope_mode, pilot, wall_seconds, estimated_peak_output_bytes,
execution_argv before __ROOT_STARTUP_PROOF__ replacement,
source_status_stage (null if absent), stage_output_cap_bytes and actual
parent_evidence_references. First write the review, then pin it into the NEW
spec; review never references the spec's own hash. Both become request sources.

FIXTURE_ONLY requires pilot=true and may have no parent evidence.
BOUNDED_PERFORMANCE_BATCH permits honest true or false, exactly matching review,
and requires bounded_batch_limits_reviewed=true. Other modes require false:
BOUNDED_METADATA_PREPARATION describes an allocation-side preparation stage;
it does not permit scientific indexing on the login node. FULL_SOURCE_AFTER_PROFILE
requires the actual parent_profile, profile_reviewed=true and matching
approved_profile_reference. FULL_SOURCE_INVENTORY_PRIOR_CRC permits a first
whole-gzip EOF inventory with prior pinned real CRC evidence, no circular full
profile; review requires inventory_only=true, candidate_release_authorized=false,
crc_full_eof_actual_passed=true and crc_receipt_reference equal a parent pin,
with inventory stage cap<=10GiB. Root must review the evidence itself.

Scientific plans, seeds, once ledgers, raw retention, all success/cost/mask gates,
Se-only exception, ROUTINE VAL and quota200GB remain in force. New resource
permission is not scientific acceptance or an automatic next-stage dispatch.
Stage and whole-phase storage caps remain distinct; e.g.24GiB prepare and60GiB
whole-phase declaration stay separately recorded. Producers cannot overwrite
reserved queue fields including root_review; explicitly rename old producer
reviews as producer_root_review in a new wrapper and pin the original spec.

## Root queue workflow

    python -B -m workflows.data_v1_final.execution.cpu_auto_memory_queue_v1.materialize \
      --spec NEW_SPEC --authority ACTUAL_NEW_AUTHORITY \
      --node compute-0-12 --job-name dv1_q_NEW_NAME
    python -B -m workflows.data_v1_final.execution.cpu_auto_memory_queue_v1.submit \
      --request R/control/requests/dv1_q_NEW_NAME.json --keep-held
    python -B -m workflows.data_v1_final.execution.cpu_auto_memory_queue_v1.activate \
      --job-name dv1_q_NEW_NAME \
      --registry R/control/cpu_auto_memory_registries/new_phase.json \
      --observer-output R/control/cpu_auto_memory_observers/new_lease

Submit always leaves jobs held, even if --keep-held is omitted. It records the
actual held metadata and cannot release jobs itself. Activation checks own UID,
job ID/name/script/CPU16/partition/node/time/no-requeue, starts and verifies a
new live observer, then releases only those own held IDs. Held NumNodes1 or1-1
is accepted; actual RUNNING must be one node. No memory or USER exclusivity
condition is tested. There is no cancel, signal, automatic retry or resubmission.
Root separately manages only previously authorized PENDING-job replacement.

New persistent job/request/proof claims and per-phase observer locks live under
cpu_auto_memory_claims / cpu_auto_memory_phase_locks. New registries are disjoint
from all legacy queued_phase*.json and queue_v2/queue_v3 registries by job ID,
job name, request and proof paths. Old monitors and registries are not stopped
or rewritten. New activation evidence is outside registry folders. Partial
claims remain for Root reconciliation; deleting claims is not a retry method.
The finite observer lease can be renewed for the same registered jobs after
its old lock is free, without submitting another physical job.

## Verification boundary

Eight new fixtures cover: new source/authority/scope and no data-body callback;
science nodes11–13 and exact CPUs; forbidden memory0/memory/exclusive/GPU options;
zero/unbounded declarations and high memory pressure recorded without rejection;
old/stale/future/wrong-boot proofs; actual>=16 idle CPU; complete primary/argv
binding; and old/new registry disjointness. No scientific data or scheduler is
used by those fixtures. Pure check command is -m unittest
workflows.data_v1_final.execution.cpu_auto_memory_queue_v1.test_contract -v.

A new reviewed fixture stage may run -m
workflows.data_v1_final.execution.cpu_auto_memory_queue_v1.run_checks
--startup-proof __ROOT_STARTUP_PROOF__. The runner requires a genuine new-policy
startup proof and discovers exactly8 tests, rejects SKIP and records actual
results in control/cpu_auto_memory_checks/<jobid>.json. No previous22 fixtures
are rerun by this runner. These sources and8 fixtures are unexecuted by this
author and do not prove the full guide objective or any scientific gate complete.
