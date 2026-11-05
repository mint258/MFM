# Minimal Pprime fill scope-only entry — source candidate

Source-only: no execution, tests, submission, deployment or changes to existing modules. The separate index issue stays paused. This entry freezes reusable actual fill scope files directly on Lustre; it does not initialize Native, run NoInvoke/input hashing, write production once claims, use a shared publication pool, or call Base.bootstrap.

Deploy `run.py`/`__init__.py` as `repository/workflows/data_v1_final/pprime/fill_scope_only_v1/`, and copy the finalized sibling resource module as `resource_runtime.py` there. Root pins the actual installed file in `plan.resource_module_reference`; the entry does not hardcode its control path or inspect a decorated function's principal module.

## Actual entry and resource API

```bash
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.data_v1_final.pprime.fill_scope_only_v1.run --plan <actual-plan.json> --startup-proof <actual-generic100-proof.json>
```

KEY is `pprime_fill_scope_only_v1`. The entry first calls the installed `cpu_account100_queue_v1.runtime.require_startup` with actual source/full argv/scope/16CPU/node18/data references. It then calls `resource.start(plan,proof,plan_reference=...,proof_reference=...)`, passes that monitor to `run(plan,proof,budget)`, and always calls `.finish()`. Existing observation `.check()`/`.report()` methods are used. No old200GB authority/provider is substituted.

Root fills `control_directory`, `source_references`, `resource_module_reference` and `resource_binding` in `plan.candidate.json`. The 49 metadata refs and closed source DATA refs are already concrete actual identities; no Parquet/JSONL body was read to prepare this template. Source pins must include the actual installed entry/resource, the two extracted original source references, original selection/identity/common-component APIs and their actual transitive runtime source closure. Runtime metadata/data references must remain identical to the generic request.

Resource binding uses the sibling's exact schema/status `ROOT_BOUND_PPRIME_FILL_SCOPE_RESOURCE_V1` / `ROOT_BOUND_REAL_STORAGE_ADMISSION`, real node18/16CPU/wall<=86400, output_forecast_bytes<=8GiB, Main64MiB and Lustre future keys, real current provider review/identity and100GB policy references. Actual Main/Lustre quotas and all future reservations remain that monitor's responsibility; the thin code never creates credit, alters global ledgers or reports whole-volume free space as quota.

## Unchanged source scope and minimal context

The original `scope.freeze` and `references` function definitions are taken from the exact pinned previous candidate source. Only their function AST definitions are compiled, with original filename/line numbers; their original module imports and Native/preparation bootstrap are not executed. Their function bodies, SQL, source selection, complete ordinary order and first2 selection are unchanged.

Private globals supply only: declared small-JSON metadata reader, closed same-FD source holder, original `fixed_random_ids` and `common_component`, original output `stamp/pin` functions, SQL quoting and metadata store. The original common component keeps5659's real FAILED1:0 and its closed-function lineage; the whole parent is never promoted to C0.

The thin legacy b interface contains only actual formal_record_index and molecule_index refs: `data=[native_ref]`, `pilot.record_index=native_ref.path`, and `population={1:molecule_ref}`. The latter is explicitly only the old ABI's key1; there is no fake per-population roster, NULL authority, Native source context or ready prefix. Original record→MID/source/role metadata remains original data.

Original-ready1,110,751 MIDs are actually reconstructed from all registered disjoint ready shards and original main190/pilot1000 domains. The scope actually anti-joins them against closed5659 fill SUCCESS/common=true/N>=2, verifies its existing ordinary pointer count and fill identity witness, sorts every ordinary physical ID with seed20261025 before selecting rank0/1, and retains original physical IDs/role/native pointer/audit provenance. No energy/diversity D7 or N1 publication is required. The observed80740 is source provenance; actual chosen MID/record counts come from the real join, never from aggregate subtraction.

## Storage and closure

Persistent output root is exactly `/lfshome/zixiao/data_v1_20261025/Pprime_fill_scope_20261105_v1`; successful data and its real SHA references are in `closed_scope/`. The thin store returns original output pin semantics and exact real Lustre paths. It enforces a separate8GiB logical output cap by statting only explicit owned output files/registered JSON, including the active DuckDB's file length and WAL; it never opens or queries an active database to monitor progress and never traverses the output tree. Logical bytes are never quota credit.

Private DuckDB connect IO directs spill files to a new actual-job directory `/dev/shm/pp_fill_scope_v1_<actual-job-id>`, records a real UID/PID/start/boot/job owner marker, and sets temp_directory plus max_temp_directory_size=8GiB. This changes only resource IO, not the original scope function. Only that exact owned spill directory's bounded file metadata is counted separately; local temporary bytes are not Main/Lustre credit. No recursive cleanup is added; the small scratch/marker may remain for the existing safe cleanup route.

Main receives only `<control_directory>/scope_only_receipt.json` plus the existing monitor metadata, within the reserved64MiB. The receipt explicitly says Native/input hashes/QM/once were not performed; it records actual scope counts, component refs, persistent manifest ref and the actual resource report. The scope is reusable for the next separately admitted pairs/input-hash preparation. It is not a prepared-pairs acceptance, full Common, D6 or training release.