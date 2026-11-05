# Pprime fill-scope resource seam — Source only

Index remains paused after its two pre-DATA failures. This independent module is for KEY pprime_fill_scope_only_v1, not D6/index. No old index/provider/runtime/active Source was edited. No DATA/DB body, tests/AST, submission or Native work was run.

Caller API:

    budget = resource.start(plan, proof, plan_reference=actualPlanRef, proof_reference=actualProofRef)
    try:
        run(plan, proof, budget)  # existing scope.freeze thin ctx, budget.check per MID
    finally:
        budget.finish()
    resource_summary = budget.report()

The caller first uses installed execution.cpu_account100_queue_v1.runtime.require_startup with its exact current Source/fullargv/scope. Do not use old cpu_auto_memory_queue_v2 (200GB). Import this module through the exact Source-pinned plan.resource_module_path; no inspect.getsourcefile on decorators is required. Generic proof provides the immutable plan/source authority; this module checks actual scope key/UID/job/node18/16CPU/no_mem/argv and finite wall.

resource_fields.template.json contains no approved facts or future positive refs. Root binds plan.control_directory (Main<=64MiB), actual plan.output_directory (Lustre scope root), and resource_binding:

- schema ROOT_BOUND_PPRIME_FILL_SCOPE_RESOURCE_V1; status ROOT_BOUND_REAL_STORAGE_ADMISSION.
- wall_seconds equals actual proof.request.wall_seconds,900<wall<=86400. The actually bound provider must cover allocation end+300s; there is no renewal.
- output_forecast_bytes a positive exact integer<=8589934592. Scope ctx/store enforces this grant with its existing writer/reservation rules; this observer does not walk the tree or treat charged bytes as physical credit.
- main_future_entry_key: actual Main V2 entry with job_id actual parent,output_root exactlyplan.control_directory,forecast_bytes67108864.
- lustre_future_entry_key: actual separate Lustre entry with samejob,output_root exactlyplan.output_directory,forecast_bytes exactlyoutput_forecast_bytes.
- quota_provider_review_reference,quota_provider_identity_reference: actual Root-bound day.Client instance (e.g. current2532992); both must be in the actual generic request Source closure. No provider path is hardcoded or changed.
- quota_floor_policy_reference: the actual current100GB user policy; may legally reside in repository/configs. Only exact Source pin/current pointer is required, no control-only restriction.

Main ledger: R/control/root_current_all_future_ledger_v1.json and .lock; schema ROOT_CURRENT_ALL_FUTURE_METADATA_POINTER_V2. Lustre ledger: R/control/root_lustre_all_future_ledger_v1.json and .lock; schema ROOT_CURRENT_LUSTRE_ALL_FUTURE_METADATA_POINTER_V1,storage_domain LUSTRE:/lfshome,uid1278. Both require totals_derived_live_from_entries true,exact nonnegative integer entry sum=known/total future,unknown empty. They are read shared, never written. Main64MiB and Lustre<=8GiB are separate; no8GiB is put in Main future. Provider64MiB is separately retained by Root, not hidden in either scope estimate.

The observer uses original frozen day.Client plus finite_quota_observation_guard, original compact-v2 wall_clock/remaining_wall, and original established D3 quota parser code object (subprocess timeout20s only). Actual lfs quota for zixiao/UID1278-/lfshome must report hard2TiB. Actual used/free is queried each30s, never copied from a template or whole-volume df. Both real free minus their own live complete future ledger must remain>=100000000000.

One parent-only observer, not16 quota clients. budget.check is30s throttled; actual RSS/DB bodies are not queried here, no global/native state or scientific rules change. Resource shortage/unknown or900s drain raises ResourceStop; caller closes its own writer handles and preserves partial scope. No signals, Native invocation, own/external allocated credit, automatic services/leases, retry, queue framework or fake C0 is introduced. Report is resource metadata, not a completed scope or a scientific acceptance.

Principal Source paths to include explicitly (no decorator inspection): this resource_runtime.py; execution/cpu_analysis_day_v1/quota_provider.py; execution/finite_quota_observation_guard_v1.py; labels/normalization_compact_runtime_v2/runtime.py; export/pilot_family_D3_local_store_v6/queued_quota.py; plus caller's ordinary actual import/source closure and exact plan/proof. Original provider/review validators and parsing rules remain unchanged.