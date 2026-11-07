# Exact-key full-pool driver

Run the new allocated module `workflows.expansion.alpha_exact_key_filter_v1.run --plan PLAN --startup-proof PROOF`
through the existing Alpha node launcher and actual private Python `-I -B`, from the clean code cwd.
No deployment or Slurm submission is performed by this package. It never changes old index205, pool180,
old/new 1M samples, background201, ranking functions or scientific normalization.

This is the user's replacement rule, not the old V3 composition contract. Full InChIKey and the original
v1 WP5 key (`key[:14]+':'+key[-1]`, connectivity14 plus protonation) alone veto candidates. The eleven
source families and every original strict5 part/role remain physically counted. All MoleculeNet rows
whose original `subdataset == 'PDBbind'` are removed from the downstream plan. Source keys are freshly
inserted from retained rows; a key shared with HIV or another source survives. No composition of any
kind, lower bound, wildcard, name match, guessed graph or 1slg/1pts correspondence is consulted.

Empty-key identity rows and explicitly supplied audited unresolved IDs produce no veto and are listed
in `eval_exclusions.jsonl` with dataset, role, subdataset, source ID, exact original/ref replica, ordinal,
byte offset, bytes and original line SHA. Optional audited physical records absent from strict5 can also
be retained here. Audit entries are disposition records, never representative molecules or new keys.
All input strict5 rows have exactly one disposition, including PDBbind. The historical manifests/audits
are preserved; obsolete `unresolved_without_identity_or_composition == 0` does not block this policy.

The index deduplicates the unchanged (kind,key,dataset) PK in memory (actual SQLite pages below2GB),
then performs one native backup into the small durable index file and closes the in-memory database.
This avoids millions of Gluster random index writes; original source EOF/SHA/disposition checks remain.
The index and filter run sequentially in one allocation. No huge JSONL candidate export or persistent
DuckDB is written. DuckDB is in-memory with explicit <=4GB spill. The streaming output preserves all
original Arrow columns/types and partitions by the actual `ecfp4_2048_hex` string's first lowerhex nibble.
All16 buckets retain all identities, including duplicate fingerprints. Each bucket closes small Parquet
shards at about128MiB or <=1M rows; each active shard is hard-bounded below192MiB (also below256MiB).
Sixteen active shards plus4GB spill remain below8GB. The active SQLite index is bounded below2GB in
the earlier nonconcurrent index phase. Actual active
files plus spill must remain below8GB, checked during input batches/SQL/output, while the original Alpha
quota/RSS Guard retains real directory/volume/CPU/memory protections. A resource failure preserves
partials. It is not a chemistry rejection or a successful reduced pool.

The original sealed overlay reader binds old34GB candidates plus the small recovered delta, retaining
its historical source SHA and current full-frame checks without redundant whole-old-pool hashing.
Actual SQL validates all109875599 input rows, unique CID/FullKey and exact full/WP5 serialization.
Two anti joins cannot duplicate the validated input identities. Physical closed-shard rows are counted
at EOF and sum to eligible; excluded is complete input minus eligible. All original fields survive.
`closed_files.jsonl` immediately records whole SHA, real immutable inode/mtime/ctime/blocks for every
closed shard/index/audit file. Root's existing shared quota publisher can credit those closed files;
the journal itself stays open until completion and must not be credited early. New code never edits
the quota assumptions of running201. Only one final `manifest.json` is written, with actual job/resources,
source consumption and dispositions, aliases by reference, all part references and complete counts.
There is no new per-job Root acceptance-file requirement.

Plan schema is `ALPHA_EXACT_KEY_FULL_POOL_FILTER_PLAN_V1`, scope `alpha_exact_key_full_pool_filter_v1`.
Use existing runtime profile/quota fields, actual code_references/startup request, exact execution_argv,
output_scope_root, fresh output_directory, workers16; software_rss_budget_bytes<=88GiB,
minimum_node_available_bytes>=24GiB, duckdb_memory_bytes<=64GiB, spill_limit_bytes<=4_000_000_000,
active_output_limit_bytes<=8_000_000_000. `policy` must equal core.POLICY. Optional shard_target_bytes
defaults128MiB (cannot exceed128MiB) and shard_max_rows defaults1M. Root supplies actual resource budget values, not a new
scientific approval. `data_references` must declare the manifest, every strict5 part and optional audit
projection; the existing transport must map imported Main references exactly to verified Alpha copies.

Required actual small inputs (pin them from existing machine receipts):

- source_manifest_reference: `/gfshome/alpha/pubchem_expansion_20261103/reports/all11_actual_source_manifest_v3_job_1885186/all11_source_manifest.json`.
- source_pool_receipt_reference: `/gfshome/alpha/pubchem_expansion_20261103/bulk/generic_mincid_overlay_v1_job_1885180/corrected_pool_authority.json`.
- parent_transport_manifest: `/gfshome/alpha/pubchem_expansion_20261103/reports/all10_source_replicas_v1_job_1885168/parent_transport_manifest.json`.
- policy_authority_reference: Root's actual user instruction archive
  `/gfshome/alpha/codex_data_v1_20261026/control/pubchem_expansion_runtime_20261103/user_exact_structure_policy_20261104.json`.
  This is preserved instruction provenance, not a per-job Root acceptance gate.
- audited_structure_exclusion_references: optional closed JSONL projections of already audited unresolved
  physical records, each row retaining dataset/source_id/role/subdataset/source_reference/
  row_ordinal_1based/source_record_sha256 and existing evidence. Exact source ID membership only.
  No prefix or wildcard matches. All such rows are copied into eval exclusions even if no strict5 row
  had been emitted. Already supplied strict5 empty-key rows require no extra projection.

The original186 manifest supplies all eleven family's identity paths and row counts. Read all parts,
including historical formula-only overlays, for disposition conservation; overlays contribute no keys.
Do not supply old lower-bound files as active veto inputs. All old audits remain historical evidence.
The overlay reader also needs the actual180 receipt's embedded existing base/delta/ledger/proof sources;
the existing deployed reader resolves them without scientific recomputation.

`test_core` contains three standard-library boundary fixtures. `test_native` adds one actual DuckDB/Arrow
fixture proving full/WP5 veto, H-only survival, composition non-veto, all-field typed preservation and
physical closed-shard row counts. The driver runs these four before full DATA within its actual Alpha
allocation, logging real results; not Windows/login or a separate approval job.
