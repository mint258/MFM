# Explicit shared analysis-day protocol v2

SOURCE ONLY; existing running cpu_analysis_day_v1 R3 is unchanged. Only two scope/module pairs are admitted: common_train_normalization_day_v1 / workflows.data_v1_final.labels.common_train_normalization_day_v1.run and d5_inputs_compound_day_v1 / workflows.data_v1_final.export.d5_inputs_compound_day_v1.run. No arbitrary producer or old scope alias.

Eight source wrappers are based on exact frozen R3, with a separate namespace, request/proof V2, explicit two-item map, and provider import. No new scheduler or resource mathematics. All actual UID1278/node14or18/integer CPUs>=16/86400/no SBATCH mem/exclusive/GPU/same-PID/source/fullargv/process/cgroup/Root exact review/200GB and exact current-future accounting fields remain. Three pure methods are retained with the two new scope constants and no third old scope. Root controls actual submission/review.

Provider and Client are direct imports from frozen cpu_analysis_day_v1.quota_provider. Do not copy/edit them or point their review at v2 source paths. Their new actual finite90000s instance review still pins the original R3 contract.py and quota_provider.py. Identity/review/latest snapshot are real and unique per new parent; running identities are never changed. Original complete quota byte inverse and all R3 source closure are included through ORIGINAL.sources(). The v2 wrapper Source is pinned separately. Original30/60/120/mount/marker/64MiB and actual remaining>=86700 at admission are unchanged.

Root input schema remains ROOT_REQUESTED_ANALYSIS_DAY_V1/status REQUESTED_FOR_REVIEW/requested_by root. Fields and CLI stay compatible: cpus,node,scope_key,scope_parameters,producer_plan_reference,estimated_peak_output_bytes,resource_authority_reference,quota_provider_review_reference,quota_provider_identity_reference,root_carveout_review_reference,source_references,data_references,job_name(dv1_aday_*). Internal request CPU_ANALYSIS_DAY_REQUEST_V2/proof FRESH_CPU_ANALYSIS_DAY_EXECUTION_ADMISSION_V2 live in control/cpu_analysis_day_v2. Producers must not create those objects themselves.

```
PY -B -m workflows.data_v1_final.execution.cpu_analysis_day_v2.materialize draft --request ACTUAL_ROOT_REQUEST
PY -B -m workflows.data_v1_final.execution.cpu_analysis_day_v2.materialize finalize --draft ACTUAL_DRAFT --root-review ACTUAL_SEPARATE_REVIEW
PY -B -m workflows.data_v1_final.execution.cpu_analysis_day_v2.submit --request ACTUAL_REQUEST
PY -B -m workflows.data_v1_final.execution.cpu_analysis_day_v2.observe --submission ACTUAL_SUBMISSION --max-seconds 90000
```

Guard API is runtime.require_startup(proof_path, *,expected_scope_key,expected_scope_parameters,expected_execution_argv,expected_source,expected_kind='analysis',required_references=()). DATA remain positive/nonbool/64hex large locators, never login-read or passed through a small-source hash helper. Actual unavailable Common/cache/D5 population proofs keep producer metadata nonexecutable. The guard never manufactures scientific acceptance. Each future actual parent runs its own new producer boundaries plus these resource3 once before DATA; no extra preflight batch is required.

Canonical node13 device numbers remain historical endpoint-local facts. A producer needing node14/18 must explicitly bind real Root same-storage mapping and actual CPU whole SHA, original inode/size/mtime/uid, path/fstat current-device stability; it cannot pretend device53 or node13. This protocol supplies resources and identity, not such a scientific-file proof.
