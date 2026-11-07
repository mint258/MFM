# Main original12 portable exporter and dispatch claim relay

This namespace has two entry points. `run` is a new actual Main analysis16CPU
Parent that exports original inputs from one independently closed published
component. `relay` is a bounded Root **login metadata coordinator**, with no
standby Slurm allocation and no scientific DATA reads or scientific key/hash
computation. Neither changes any existing producer or model Source.

The legacy243 seven files remain unchanged. A still-running PREP Parent and
its live input-hash workers are never declared C0. The shared
`current_prepared_component_v1.authority` must validate its actual component:
`metadata_bind(component_plan, allowed_owner='ALPHA')` in metadata, then
`verify_component(component_plan, export_proof, export_budget, allowed_owner='ALPHA')` in the real CPU
Parent. Export accepts the unchanged
`PPRIME_CPU_CLOSED_ASSIGNED_PAIRS_HEADER_V2` and closed DuckDB
`pairs(rid,mid,rank,pair BLOB,hashes BLOB)`.

Root must first perform its serial operator external assignment. Alpha's
component must have **no Main native MID overlap**, including job4525253 and
future Main EXECs. Global O_EXCL alone does not eliminate the old Main
`exists -> claim_create` race. Export and relay never retire another process,
change another job, stop Main, preclaim a batch, or acquire a whole-shard claim.

## Export metadata and CPU entry

```bash
PY -B -m workflows.data_v1_final.pprime.portable_alpha_original12_main_v1.metadata draft --request REQUEST --output SPEC
PY -B -m workflows.data_v1_final.pprime.portable_alpha_original12_main_v1.metadata finalize --draft SPEC/draft_receipt.json --root-review REVIEW
PY -B -m workflows.data_v1_final.pprime.portable_alpha_original12_main_v1.run --plan SPEC/plan.json --startup-proof ACTUAL_CPU_PROOF
# Root only, after actual export Parent C0/raw accounting:
PY -B -m workflows.data_v1_final.pprime.portable_alpha_original12_main_v1.metadata close --parent-registration SEVEN_REF_JSON --output ACTUAL_EXPORT_CLOSURE
```

Root request schema is `ROOT_REQUESTED_PPRIME_ALPHA_PORTABLE_MAIN_EXPORT_V1`,
status `REQUESTED_FOR_REVIEW`, `requested_by=root`. Required fields:

* `component_plan_reference`: exact small plan accepted by the shared component
  adopter. Its original pilot, generation, retention, protocol, context,
  partition, original prepared header and actual publication chain are retained.
* `external_assignment_reference`: Root's actual serial transition authority
  described below.
* `additional_runtime_source_inventory_reference`: Root's explicit original
  Python Source inventory. Its `source_references` become
  `additional_runtime_source_references` in the frozen plan. The current supplied
  inventory is `control/alpha_original12_runtime_source_20261030_v1/original_runtime_python_source_inventory.json`,
  84 original `.py` files under
  `/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime/phychem_mfm`.
* The original five named resource/cost/quota/carveout references, with a fresh
  Root allocation for this export. `node` must be2 or8–19; `maximum_molecules`
  is an integer1–5000; `output_cap_bytes` is Root's explicit finite cap, at most
 64GiB. `output_directory` is a fresh child of this namespace's artifact root.

Scope key is `pprime_alpha_original12_portable_main_export_v1`, kind `analysis`,
16CPU, one86400-second Parent, unspecified Slurm memory. The existing private
v3 observer enforces RSS56GiB/software64GiB plus actual MemAvailable, output,
quota, future reservations and natural drain. It is not a memory request.

External assignment small schema:

```text
schema: ROOT_EXCLUSIVE_PREPARED_COMPONENT_SLOT_HANDOFF_V1
status: EXCLUSIVE_COMPONENT_SLOT_ASSIGNED_WITHOUT_NATIVE_RETRY
reviewer: root
owner: ALPHA
prepared_shard_header_reference: exact component positive triple
generation_shard_header_reference: exact original MID-shard triple
shard_id: exact original generation shard ID
state_status: EXTERNALLY_ASSIGNED_CURRENT_CLOSED_COMPONENT
physical_once_ledger: exact original C.ledger(component_plan)
no_whole_shard_physical_preclaim: true
operator_state_path, operator_native_lock, central_serialization_lock: exact existing paths
old_operator_not_live_during_state_edit: true
immutable_state_after_snapshot_reference: exact actual handoff snapshot
```

Root should retain its actual operator serial-lock/state transition evidence
inside this authority. A template with these words is not evidence of that
transition. The shared component authority has its own complete original
publication/proof/COMMITTED-chain checks.

## Byte-preserving output interface

Export examines only the actual closed component. It walks MIDs descending,
preserves original rank0/1/source role/seed, excludes already consumed global
claims, and selects at most5000 actual MIDs/10000 actual records. If preparation
already omitted a consumed original rank, no missing rank is regenerated.
A newly appearing claim during packing fails closed; packets do not reserve
anything. The later relay still uses O_EXCL at actual dispatch time.

Each packet has schema `PPRIME_ALPHA_ORIGINAL12_PACKET_V1`:

```text
record_id, molecule_id, physical_key, original_pair_sha256
prepared_header_reference, original_protocol_reference
pair_reference, hashes_reference, native_payload_reference
atomic_numbers_i64_reference
native_coordinates_f64_reference, uff_coordinates_f64_reference
preflight_reference
```

`pair.bin` and `hashes.bin` are the **original DuckDB BLOB bytes**. The native
payload is the original LMDB entry's pickle bytes; it is never decoded and
reserialized for transfer. Original read_native, ordered graph, geometry adapter
and atom order are checked under the original NoInvoke guard. All twelve original
input hashes are inherited unchanged from the independently verified component.
Main does not render the batch again; Alpha must render and verify them before
claim and Native. Arrays are original little-endian int64/F64 bytes.
No QM, UFF, embedding, seed, threshold, parser, task or retention rule is added.

LMDB whole-file SHA is inherited from the original closed Source authority.
Only each actual exported full payload SHA and the actual source's original
stable frame are checked now; no enormous LMDB is rehashed or copied for this
transport. The inventory says this explicitly. Alpha's private PacketHandle can
serve the original bytes through the original reader without changing the
eleven Main-origin source paths or claiming to own whole LMDB replicas.

The small header `PPRIME_ALPHA_ORIGINAL12_PORTABLE_INPUTS_V1` contains:

```text
records, MIDs                         # actual integers, not planned counts
record_index_reference                # DATA JSONL
dispatch_authorization_inventory_reference
prepared_header_reference, external_assignment_reference, component_plan_reference
component_cpu_qa_reference
original_protocol_reference, source_context_reference, retention_policy_reference
original_audit_membership_reference, portable_audit_membership_reference
source_audit_reference, source_inventory_reference
runtime_asset_locator_reference
reproduction_package_reference, original_reproduction_package_reference
origin_export_root
packets_are_not_claims=true, whole_LMDB_files_copied=false
native_invokes=0, global_once_claims_created=0, PREP_parent_C0_claimed=false
scientific_PASS=false, final_Common_or_training_admission=false
```

Each record-index row is
`{record_id,molecule_id,physical_key,random_order_rank,packet_reference,dispatch_authorization_reference}`.
Authorization is not embedded back into packet, avoiding a circular SHA.

`source_inventory.json` retains `sources` with all eleven original entries,
`portable_source_entries_reference` (auxiliary DATA JSONL), and
`selected_source_current_frames`. `runtime_asset_locators.json` has
`schema=PPRIME_ALPHA_RUNTIME_ASSET_LOCATORS_V1` and
`rows=[{origin_reference,portable_reference,mode,source_kind}]`.
Non-LMDB original execution assets, original software whitelist14+22, required
pprime scientific Source and the explicit runtime84 Python Source files are
copied in this same CPU Parent with whole-file SHA/current-frame checks.
The layout preserves the entire original absolute path tree below
`runtime_assets/`, including neighbouring engine/parser files. Original executable
mode is retained; no package download or user authentication file is copied.

The portable audit changes only its selected-record path to the actual exported
Parquet copy; original bytes/SHA/rows/seed/policy remain identical. Original
source-audit DATA and reproduction-package bytes are copied intact. All inner
Main-origin pointers require the explicit origin-to-portable/Alpha resolver.

Root's post-C0 wrapper schema is
`ROOT_ACTUAL_PPRIME_ALPHA_PORTABLE_EXPORT_CLOSURE_V1`, status
`ACTUAL_CPU_C0_PORTABLE_PACKET_SOURCE_ONLY`, reviewer `root`, with
`portable_manifest_reference` and `parent` containing the seven exact
`receipt_reference,plan_reference,proof_reference,request_reference,submission_reference,accounting_reference,raw_sacct_reference`.
The original `root_metadata.closed_parent` checks the actual Main export C0,
UID1278,16CPU and raw sacct. The producer never signs its own C0.

## Metadata-only claim relay

```bash
PY -B -m workflows.data_v1_final.pprime.portable_alpha_original12_main_v1.relay --binding ROOT_BINDING --output FRESH_CONTROL_DIR
```

Root binding schema is `ROOT_APPROVED_PPRIME_ALPHA_DISPATCH_RELAY_V1`, status
`APPROVED_BOUNDED_METADATA_ONLY_RELAY`, reviewer `root`, UID1278/Main endpoint.
It requires `portable_export_closure_reference`, `portable_manifest_reference`,
`external_assignment_reference`, all eight Source pins in `source_references`,
`alpha_startup_proof_reference` and exact `alpha_parent`:

```text
endpoint=218.192.171.238:22, uid=1264, job_id, node, boot_id
parent_pid=actual_gate_process.pid, parent_ticks=str(actual_gate_process.start_ticks)
```

The actual Alpha proof is `SECONDARY_PPRIME_ORIGINAL12_DAY_STARTUP_V1`, formal
original12 scope, actual admitted16CPU/86400s/unspecified memory, plus its actual
portable origin reference. Source3/software compatibility/admission belong to
Alpha's actual CPU guard; the login relay does not invent these outcomes.

Other binding fields are `alpha_mailbox_root`, `alpha_output_root`,
`Main_to_Alpha_key_path`, `known_hosts_path`, `serial_lock_path`, `relay_seconds`
(<=86400), `poll_seconds` (1–30), `heartbeat_max_age_seconds` (10–300),
`maximum_transport_calls` (<=100000), and `maximum_control_bytes` (4MiB–1GiB).
Only private-key **paths** are passed to sftp; key bodies are not read, copied or
printed. Root supplies the actual finite control reservation.

The CPU exports one small `PPRIME_ALPHA_DISPATCH_AUTHORIZATION_V1` per physical
key and small inventory pages of at most128 refs. Relay reads only these pure
control files, the actual export/Alpha proof, and slot messages. It never opens
DATA index, pair, payload, scientific DB, F64 or raw/native result bodies and
never computes a physical key from scientific values on login.

Alpha atomically writes `requests/slot_XX_seq_XXXXXX.json`; at most sixteen
slots are in flight. Requests use `PPRIME_ALPHA_DISPATCH_CLAIM_REQUEST_V1`,
including request/slot/sequence, subset manifest, CPU authorization and packet
refs, original key/RID/pairSHA/protocol/header, `alpha_execution`, and action
`CLAIM` or `SETTLE`. SETTLE retains all original fields and adds the original
Main `claim_reference` and `outcome=CLOSED|UNKNOWN`.

The relay invokes the **original** `claim_create` O_EXCL only for an authorized
actual imminent dispatch. Existing claims return ALREADY_CONSUMED. New claims
retain Main UID1278 as the control writer, actual Alpha job/boot/endpoint and
native UID1264, exact `foreign_execution`, and explicit
`ROOT_LOGIN_METADATA_RELAY_NOT_NATIVE_PARENT` writer identity. It creates no
Main native job. Replies use `PPRIME_ALPHA_DISPATCH_CLAIM_RESPONSE_V1`, status
CLAIMED/ALREADY_CONSUMED/SETTLED/UNKNOWN_RETAINED/STOP, with original Main claim
ref and Alpha copy locator retaining identical bytes/SHA.

Heartbeat uses `PPRIME_ALPHA_CLAIM_SESSION_HEARTBEAT_V1`, exact alpha_parent,
strictly increasing `heartbeat_sequence`, stop_new and actual worker slot/pid/
ticks list. Liveness uses **Main local monotonic time since a sequence increase**,
not cross-cluster wall-clock subtraction. First observation is only a baseline;
requests wait for a genuine increase and their registered worker identity.

Lost transport/heartbeat stops new claims. A claimed UNKNOWN is never retried,
upgraded, released or erased; its slot remains held. CLOSED settlement frees a
dispatch slot, never the permanent global claim. The relay terminates after all
authorized keys settle or its finite Root lease, keeping all unclosed claims
UNKNOWN. It sends no signals and does not alter Main operator or Slurm jobs.

Only Root performs Source checking, metadata freeze, deployment, actual CPU
execution, Alpha submission, actual accounting and commit. This implementation
adds no test suite or extra QM diagnostic Parent.
