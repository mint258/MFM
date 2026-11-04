# Current-parent closed prepared component — Source-only

New unique EXECUTE scope pprime_current_closed_component_execute_v1,
module workflows.data_v1_final.pprime.current_prepared_component_v1.run.
7Source, same generic16/no_mem/86400s/v3RSS56/software64 resource mechanism.
Original v3 main/execution and v2 worker/once/12calls/900s/QC/publication execute
by identical code objects; only private C/resource admission bindings differ.
No original/live Source, prep jobs or metadata operator is edited here.
Source3 is original3 methods with component boundaries added inside method3;
no extra Slurm/QM diagnostic suite. Author executed no Python/AST/test/SCI/SSH.

## Proven closure, and what is NOT claimed

Prep v3 P.build exhausts shard hash_map, checks hashesNULL=0, checkpoints and
closes its DuckDB; original main engine is closed. Persistent hash workers live
across shards until Parent finally closes, and original input Body FDs remain
cached read-only. They do NOT retain or write published destination files.
U.publish verifies closed local bytes, copies fullSHA/fsync, samefilesystem
atomicrename, fsyncs pooldir and marks token COMMITTED_BYTE_VERIFIED.
Header Store writes/fsyncs a fresh temp, atomically hardlinks final, unlinks temp,
then fsyncs directory. Stable singlelink header has no later writer in Source.
Nothing here asserts ParentC0 or hashworkers closed. Native starts ONLY after
new actualCPU wholeSHA/readback of this exact committed bundle/index/sidecars.
No active prep DB/WAL or node-local hash scratch is opened by the adopter.

## Root component approval (all small actual refs, no future IDs)

Use standard request fields of original v3 EXECUTE, but request schema
ROOT_REQUESTED_CURRENT_PREPARED_COMPONENT_EXECUTION_V1. Keep mode EXECUTE and
original prepared_shard_header_reference. Existing field
shared_preparation_root_acceptance_reference now points to this NEW schema:
ROOT_APPROVED_CURRENT_PARENT_PREPARED_COMPONENT_V1 /
APPROVED_CPU_VERIFY_CLOSED_COMPONENT_NOT_PARENT_C0 / reviewer=root.
parent_C0_claimed=false; hash_workers_closed_claimed=false.
prepare_parent_registration={request_reference,submission_reference,
proof_reference,plan_reference}; all actual original v3 SHARED_PREPARE.
actual_source3_reference is actual Parent source3.json with3PASS.
prepare_parent_observation_reference is pure actual metadata:
job_id:string,uid1278,node,state:'RUNNING',request_reference,proof_reference,
query_returncode:0,raw_reference. Raw is actual sacct parsable2 with fields
JobIDRaw,State,AllocCPUS,NodeList,UID (others preserved). It proves RUNNING at
review snapshot, not perpetual liveness or C0. An eventual terminal does not
invalidate immutable published bytes; its accounting remains separate.
external_assignment_reference points to handoff below.

Header remains PPRIME_CPU_CLOSED_ASSIGNED_PAIRS_HEADER_V2. Index remains
DuckDB pairs(rid VARCHAR,mid VARCHAR,rank BIGINT,pair BLOB,hashes BLOB), closed
and immutable in shared PREP bundle. Pair JSON and hashes record are original.
verify_component(plan,proof,budget,allowed_owner='EARLY_MAIN') checks all bundle
files with original stable-FD fullSHA, CAS COMMITTED under pool lock, exact index
schema/record/MID/rank/pairSHA/geometrySHA/12 ordered original input-file hashes.
It never initializes the engine or invokes/render inputs. Original execution
rehashes/revalidates actual native inputs as before, then same physical_once.
For Alpha exporter, shared functions are authority.metadata_bind and
verify_component; explicitly allowed_owner='ALPHA'. Main only accepts EARLY_MAIN.

## Root-exclusive slot handoff: before any new submit

Root alone safely retires its metadata operator; no Slurm process is signalled.
No concurrent modification of live state. Hold BOTH existing native lock and
central serial lock:
 ROOT/control/pprime_dual_parallel_20261030/single_root_native_autowire.lock
 ROOT/control/root_data_v1_sequential_submit.lock
Original state: ROOT/control/pprime_full_start_user_20261030_v1/
full38_resource_v3_rollout/state.json; ownlock same dir/operator.lock.
Actual key = original generation_shard_header.shard_id, NOT header ordinal.
Only ABSENT or status RESOURCE_WAIT_NO_NATIVE_INTENT slot may be reassigned;
any prior actualsubmission/UNKNOWN/native-intent is HOLD, never retry.
Write state.shards[shard_id] with status
EXTERNALLY_ASSIGNED_CURRENT_CLOSED_COMPONENT, header_reference=exactpreparedref,
assignment_owner='EARLY_MAIN' or 'ALPHA'. Original operator skips every existing
status except RESOURCE_WAIT_NO_NATIVE_INTENT (Source lines164–165).
Save immutable before/after snapshots and explicit Root handoff JSON:
 schema ROOT_EXCLUSIVE_PREPARED_COMPONENT_SLOT_HANDOFF_V1
 status EXCLUSIVE_COMPONENT_SLOT_ASSIGNED_WITHOUT_NATIVE_RETRY
 reviewer root; owner; shard_id; prepared_shard_header_reference;
 generation_shard_header_reference; operator_state_path; operator_native_lock;
 central_serialization_lock; old_operator_not_live_during_state_edit=true;
 state_status EXTERNALLY_ASSIGNED_CURRENT_CLOSED_COMPONENT;
 physical_once_ledger=original C.ledger(plan); no_whole_shard_physical_preclaim=true;
 immutable_state_after_snapshot_reference=actualpure copied state reference.
No preclaim of physical records, no invented submission or childC0.

Root registers/submits new Main only under same serial lock and same physical
once root. Before resuming oldoperator, replace transferred Main entry with
actual newMain registration/result fields (submission_reference/job_id/node)
so original live_exec_counts includes it in16Parent limit. Preserve an external
handoff reference/history. Alpha entries MUST use external_submission_reference
namespaced fields, never fake Main Slurm IDs; Root counts Alpha capacity in its
independent endpoint resource policy. If Root pauses after handoff before actual
submit, retain reservedslot/noNativeintent evidence and explicitly resolve it;
do not silently reset status or let original C0 operator create another Parent.
Restore the SAME old Source/input/state directory only after atomic state save;
no reset of state.preparations/holds/costs/other shards.

## Actual CLI (Root only)

PY -B -m workflows.data_v1_final.pprime.current_prepared_component_v1.metadata draft --request ROOT_REQUEST --output FRESH_CONTROL
Root signs separate exact root_review.template.json.
...metadata finalize --draft draft_receipt.json --root-review ACTUAL_ROOT_REVIEW
Original central materialize/submit/activate once, new scope/module, real16CPU.
Same Parent Source3→independentcomponentQA→originalNativeexecution.
Sourcefinal is not component acceptance, ParentC0 or actual new Native output.

### Export caller compatibility
The same verify_component accepts the actual Main EXPORT analysis proof and
its independently guarded budget (allowed_owner='ALPHA'). It does not assume
that caller scope is QM/MainNative or require unrelated cp resource fields.
It requires actualUID1278/16CPU, component3 DATA refs in actualcaller DATA, and
header/review refs in actualcaller SOURCE. The native entry separately retains
original full exact data declaration. Root/N1 uses metadata_bind(cp), original
Formal.bootstrap(cp), then verify_component(cp,actualExportProof,actualBudget).


Root pre-production resource correction: source PREP authority comes from the exact header-bound original preparation plan and is explicitly declared in caller SOURCE. A new executor may publish to a different fixed32GiB EXEC epoch without changing its immutable source bundle, input bytes, science, or original CAS protocol. Parent cap8GiB and four-parent publication epochs fit the original supported resource range; shared PREP is counted once globally by physical pool root.
