# D6 full physical identity index — source-only candidate

This is an actual builder and lookup interface. It has not been run, tested, submitted or advertised as an accepted index. Root owns admission/submission. No numerical values, coordinates, masks or physical-QA functions are read or rerun. No QM/UFF is invoked.

## Existing authority reused

The full WP5 `full_logical_owner_plan_v2/build_v1/group_plan.json` already binds the closed canonical record identity (11,231,854 records / 1,220,466 MIDs), the complete 2,208-file source inventory and complete actual footer authority. Their references are reused. Those catalogs contain real file/RG directories and owner identities, but the inspected reader interfaces do not supply full record-to-physical-row lookup; the delivered 55k numeric catalog is a subset and is not substituted.

For Pprime the formal final-delivery completion manifest binds `final_audit_4525885/family_manifest.jsonl` (192,170 actual family files) and the closed coverage analysis. No per-record physical locator catalog is claimed in that interface. The builder reads all official QC identity columns once to establish the independent record/MID/role/native alias/input-view authority; it indexes those QC physical rows in the same pass. It then indexes all other listed families using only scalar identity/native-pointer columns.

The complete source file scope is scanned before a future final Common JOIN. Existing WP5 `classify_owner`/`lookup_batch` apply the original canonical-owner selection, and noncanonical physical rows retain their exact file/RG/row, observed identity and original classification in `shadow_locations`. They are not silently converted into canonical records. The full original canonical table is read-only and never copied or rewritten.

## Exact entry Root can run after actual CPU and storage admission

Set `PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository` and use the established chemprop interpreter on a real Main 16-CPU Slurm allocation:

```bash
/share/home/zixiao/.conda/envs/chemprop/bin/python -B /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/D6_full_physical_index_candidate_20261105_v1/build_index.py --plan /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/D6_full_physical_index_candidate_20261105_v1/source_plan.candidate.json --output /lfshome/zixiao/data_v1_20261025/D6_full_physical_index_20261105_v1
```

Necessary Root parameters: actual CPU node/allocation; fresh actual output directory (update plan and CLI together if occupied); actual Lustre quota and all Lustre future reservations with 100 GB floor. `output_forecast_bytes=16 GiB` is the requested independent budget/forecast, not a measured output size or quota credit. This standalone source candidate does not create or amend a global quota ledger; Root must bind the real quota admission/observer in the submission wrapper. It does not use whole-volume free capacity. No final norm, final Common or Model ACK is required for this identity index.

`build_index.build(plan, output)` is the callable equivalent. It writes one identity SQLite, one QC locator SQLite and sixteen independently written locator SQLite shards, then only on successful close writes `manifest.json`. Failed partial roots have no complete manifest and are retained. No existing source or output is overwritten. Workers use immutable reads only after the identity stage has closed. Existing source SHA values remain inherited; sources are opened with original same-FD/UID/size/frame API and `hash_content=False`, never whole-body rehashed.

## Reader API and physical semantics

Add the candidate directory to module search path and call `read_index.locators_for_mids(manifest_path, mids)`. This streams exact locators for every original canonical/Pprime record of those MIDs. Every result carries source reference, record/MID, actual family, task code, physical row, row group/local row, canonical or original QC identity, observed Pprime job owner where the original row has one, and the original base/native pointer witness.

WP5 input view is the observed base `geometry_status`; native key is its original record ID. Pprime input view is the observed QC `geometry_source`, and native key is its observed `source_record_id`. Original source path/real_index/payload hash/geometry hashes are retained as pointer metadata. No identifier splitting or generated owner is used. Missing original required identity columns stop the source; a missing MID column can only use the actual closed record→MID join, which is counted explicitly. No NULL fields are filled to claim readiness.

Task codes reuse the original `support.TASKS`; base rows use -1 and QC uses -2, strictly index-only tags. Final target IDs, D1 wire format, ordered r73 and scientific masks are untouched. The index deliberately does not claim final Common, normalization or training release.

Only the new index metadata is counted/closed. Existing data files are not rehashed, scientific checks are not repeated, and active SQLite databases are never used. Root may source-check this candidate before actual execution; no additional scientific test matrix is requested.