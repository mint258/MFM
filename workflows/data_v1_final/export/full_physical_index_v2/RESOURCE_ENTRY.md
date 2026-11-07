# D6 real-resource wrapper: Source-only candidate

Use run_index.py, not the copied builder's standalone CLI, after Root fills the real plan/request/proof. Original candidate remains unchanged. No execution, AST/tests, DATA read/hash or submission was done to prepare this candidate.

The new build_index.py differs only in resource IO: a callback at each source/8192-row identity batch; canonical identity commits at8192 for durable partial retention; writer-close finally and a small local writer-handle registry; optional ProcessPool initializer. Owner joins/classification, source mappings, identity/ordinal/native-pointer contents, ordering and original final manifest logic are unchanged. read_index.py is byte-copied without changes. ResourceStop closes every owned write connection/worker context and preserves partial files; no final manifest is written unless original full builder finishes.

resource_runtime.py uses the Root-bound existing frozen day.Client and finite near-clock observation helper for actual Main node18 quota, the original compact-v2 wall_clock/remaining_wall, and the original established D3 quota() parser/code object (only subprocess gets a20s timeout). It checks actual UID1278 and the actual /lfshome user quota limit2TiB, not whole-volume df. No source/numeric/geometry payload is read by the observer. Main V2 future and Lustre future are separately read under shared original locks with exact nonnegative sums/unknown rejection and true job/output entry matching. No ledger is written and no allocation credit is granted.

One parent monitor queries both accounts every30s. Spawn workers validate actual parent PID/start/boot/UID/job/node/argv/cgroup, immutable plan/proof metadata, and a fresh small current-resource state, throttled30s. There are no per-worker quota query storms. Source/batch callbacks raise the same resource-only Stop; all workers drain through their own finally blocks without signals. Known own SQLite/journal metadata is only lstat telemetry; active SQLite bodies are never queried or hashed. The16GiB forecast is a cooperative allocated-metadata bound, never Main quota credit.

## Root fields to bind before execution

Copy source_plan.candidate.json to the actual small plan; all existing scientific input refs/counts stay exactly the original values. Its resource_binding is deliberately UNBOUND and nonexecutable. Root fills:

- status=ROOT_BOUND_REAL_STORAGE_ADMISSION (schema ROOT_BOUND_D6_MAIN_LUSTRE_RESOURCE_V1), node compute-0-18,cpus16.
- wall_seconds: actual finite Slurm wall<=86400 and>900; actual bound publisher expiry must cover the allocation end+300. Existing v5 need not have24h left; choose a real admissible wall or bind a separately launched finite90000s day instance; never extend an old identity.900s drain remains.
- control_directory: a new Main control directory, owning only<=64MiB metadata. It must exist before start; resource_observation child must not exist.
- main_future_entry_key: actual entry in control/root_current_all_future_ledger_v1.json (V2), forecast_bytes67108864,output_root exactlycontrol_directory,job_id actual held parent. Do not add16GiB here.
- lustre_future_entry_key: actual entry in control/root_lustre_all_future_ledger_v1.json, forecast_bytes17179869184,output_root exactlyplan.output_directory,job_id sameactual parent.
- quota_provider_review_reference / quota_provider_identity_reference: actual positive refs for an approved day.Client provider instance (existing v5 or a new distinct finite90000s instance). Both refs must be in the actual request Source closure; no path is falsely substituted.
- quota_floor_policy_reference: actual current100GB user policy ref.

Lustre ledger schema must be ROOT_CURRENT_LUSTRE_ALL_FUTURE_METADATA_POINTER_V1, storage_domain LUSTRE:/lfshome,uid1278,totals_derived_live_from_entries true,entries each{job_id,output_root,forecast_bytes,future_reserved_bytes,status},sum equals known/total_future_reserved_bytes,unknown_future_entries empty. Same-name.lock is read shared. Root proposed40GiB conservative legacy plus16GiB index is supported; no value is preapproved or invented here. Main live V2 uses its own ledger/lock. Both actual free minus their own complete futures must remain>=100000000000.

Root fills source_references with these new sources plus the original imported Source closure/day provider/near-clock/clock/original D3 quota parser sources; the wrapper explicitly checks its principal runtime/reader Source pins. data_references are the original closed full input locators (canonical, owner plan,inventory/footer,Source validation,formal Pprime completion/family list and actual transitive producer references), inherited without login body/hash. Root's generic100 queue actual request must contain exactly the plan DATA list.

## Existing queue/entry

Use already installed workflows.data_v1_final.execution.cpu_account100_queue_v1; no new queue. kind analysis,pilot false,cpus16,node18,no_mem,wall exactlyresource_binding.wall_seconds,estimated_peak_output_bytes67108864 for Main control. scope_key d6_full_original_physical_index_resource_v1; scope_parameters=resource_runtime.parameters(actualPlan). Root review explicitly sees separate16GiB Lustre output. Root performs its normal materialize/held submit/real ledger job binding/activate.

Execution argv (the generic runtime binds its actual Source/fullargv):

    PY -B R/control/D6_full_index_resource_candidate_20261105_v1/run_index.py --plan ACTUAL_SMALL_PLAN --startup-proof ACTUAL_GENERIC100_STARTUP_PROOF

Builder output remains the original /lfshome/zixiao/data_v1_20261025/D6_full_physical_index_20261105_v1, or a Root-selected fresh exact plan path. Original full identity manifest/schema remains unchanged. Wrapper only adds Main resource_result.json; status CLOSED_ORIGINAL_IDENTITY_INDEX_PENDING_ACTUAL_PARENT is not C0 or final Common/D6 release. Resource partial/failure preserves output root and no complete index is accepted. Root terminal accounting/adoption remains external. No QM/UFF, new scientific tests, source-data QA/hash, global registry update or data deletion is performed.
If a new90000s publisher is launched for a24h index allocation, Root separately registers its real64MiB Main provider allowance. The index remains64MiB Main control plus16GiB Lustre; the provider is not hidden in either index forecast. No helper here launches or reserves it.
