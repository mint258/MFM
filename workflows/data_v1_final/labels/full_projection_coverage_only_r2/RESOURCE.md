# Full-projection coverage-only resource seam — Source only

New KEY full_projection_coverage_only_v1; no Pprime/D6/index scope is borrowed. Running Pprime scope and every existing Source/provider/ledger remain unchanged. No Python/AST/tests, DATA body/hash, submission or computation was run preparing these files.

API after the logical entry's actual cpu_account100_queue_v1.require_startup:

    budget = resource.start(plan, proof, plan_ref, proof_ref)
    # Keyword plan_reference=... / proof_reference=... is also supported.
    try:
        # original coverage logic; budget.check can be called at stop probes
        # and SQLite VACUUM progress callbacks (caller retains original policy)
        run_original_coverage(plan, proof, budget)
    finally:
        close_all_local_DB_handles()
        budget.finish()
        budget.cleanup_local_workspace()
    summary = budget.report()

The resource module does not repeat startup/admit or implement any coverage/schema/owner/numeric/ID logic. It checks the actual generic request KEY/UID/node18/16CPU/no_mem/argv and finite wall, uses the original day.Client/near-clock helper, original canonical wall-clock helper and original actual Lustre quota parser code. No principal-module inspection, control-only policy restriction, credit service or new queue is added.

Plan uses inline resource_binding. Root must actually bind:

- schema ROOT_BOUND_FULL_PROJECTION_COVERAGE_RESOURCE_V1,status ROOT_BOUND_REAL_STORAGE_ADMISSION.
- wall_seconds: actual allocation wall,900<wall<=86400. Bound day identity must cover actual end+300s; Root may start a new true instance, never renew/swap the old identity.
- output_forecast_bytes positive integer<=34359738368 (Root's revised32GiB Lustre grant; not the earlier8GiB proposal).
- local_workspace_cap_bytes positive integer<=34359738368.
- main_future_entry_key: Main V2 entry actualjob/output_root=plan.control_directory/forecast_bytes67108864.
- lustre_future_entry_key: Lustre entry actualjob/output_root=plan.output_directory/forecast_bytes exactlyoutput_forecast_bytes.
- actual quota_provider_review_reference,quota_provider_identity_reference,quota_floor_policy_reference in the request Source closure.

Top-level plan.control_directory is an already prepared Main metadata directory; runtime only creates its fresh coverage_resource_observation child. Runtime never creates the Lustre plan.output_directory; original logical entry owns that fresh root and final32GiB output.

Top-level plan.local_workspace_directory is a Root-reviewed fresh literal direct child of /dev/shm (fixed unique date name or actually known job name). Resource runtime is its only creator, with actual UID1278/job/PID/plan/proof marker. Entry must not mkdir it again; use budget.local_workspace_directory. Actual tmpfs mount, initial local free>=cap+4GiB and MemAvailable>=cap+4GiB are sampled. Every30s only this own local SQLite/spill tree is metadata-censused; finite whole recensus on FileNotFound, persistent unknown stillStop. Real st_size is constrained<=local cap; local free keeps4GiB. No DB query/hash or local-byte Main quota credit. Scope/packets/shared-source trees are not traversed.

cleanup_local_workspace is explicit and only after the entry closes local DBs. It stops the observer first, verifies the same fresh directory inode/UID and actual parent marker, rejects symlinks/nonregular/other-UID files, and removes only that pure-derived local tree. It never deletes Lustre partial/final output or any source. No local DB may be an authoritative final ref; VACUUM INTO the approved Lustre.partial/final file remains the logical entry's storage-only operation. finish alone only stops the observer; repeated finish is safe.

Main root_current_all_future_ledger_v1.json/.lock (V2) and separate root_lustre_all_future_ledger_v1.json/.lock (ROOT_CURRENT_LUSTRE_ALL_FUTURE_METADATA_POINTER_V1/storage_domain LUSTRE:/lfshome/uid1278) are shared-lock read, exact known integer sums, unknown rejection and actualjob/output ownership. Both actual free minus all own-domain future must remain>=100000000000. Main only64MiB; no32GiB is added to Main. Provider's independent64MiB stays Root-accounted. Real lfs quota must bind UID1278 and2TiB user hard limit; whole-volume free is never used.

ResourceStop/unknown and900s drain stop new work through callback, never signals. The original entry closes/preserves its published or partial Lustre output and controls storage/schema acceptance; this module does not claim coverage complete/C0 or change scientific criteria. Forecasts are not physical inventories or free credit. No future/approved/free/SourceQA value is fabricated in the template.

Explicit Source paths: this file; frozen execution/cpu_analysis_day_v1/quota_provider.py; execution/finite_quota_observation_guard_v1.py; labels/normalization_compact_runtime_v2/runtime.py; export/pilot_family_D3_local_store_v6/queued_quota.py; plus the logical entry's full source closure. Pass the resource module's exact actual Source pin; no inspect on contextlib-decorated functions.