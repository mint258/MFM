# Full original PubChem raw reconstruction fallback

Use this fallback only after Root has checked the known Main backups and cannot
adopt the complete Alpha502 scientific Parquet bodies. It reconstructs the
entire original snapshot (124,857,440 rows in 500 original raw descriptors),
never a smaller/easier pool. It performs no PM7/xTB/UFF, downstream evaluation
or training. It is a source implementation, not evidence that reconstruction
has executed or that any final candidate release is complete.

## Existing physical source on Main

On 2026-11-03, the scoped Main inventory found all500 original raw TSV files,
8,880,849,781 bytes total. Their index was rehashed and its exact SHA matched.
The complete compressed CID-SMILES snapshot is also physically present.

* Inventory receipt:
  `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion/raw/sb5_pubchem_raw_inventory_v2_cpu_default_memory_v1/receipt.json`
* Original acquisition receipt:
  `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion/raw/pubchem_20261025_v1/attempt_4520348/receipt.json`
* Actual source index, derived from `inventory.source_index.reference`:
  `.../sb5_pubchem_raw_inventory_v2_cpu_default_memory_v1/source_index.jsonl`,
  358,880 bytes, SHA256
  `046406af00c171396ff51be480d6adff09e7122e5640e1ca69da7c40d7ad3eea2`.
* Raw gzip, derived from `inventory.raw_source` and `acquisition.file`:
  `.../raw/pubchem_20261025_v1/CID-SMILES.gz`, 1,488,715,010 bytes, SHA256
  `2504bc00da1b0587ae208d8a5fb2a4fe6043c215436150f2023d59c57c5cd2b7`.

These are observed existing locators, not invented future output pins. `prepare`
reads the actual receipts/index, conserves every original part/ordinal/byte,
and freezes its real references. Allocated `run` then checks the actual raw gzip
and index SHA before data computation. All source parts receive their own
same-FD streaming SHA, byte/CID/ordinal/row conservation checks during use.

The checked `source_artifacts` directories contained only code/metadata ZIPs,
JSON and Python files. Main cost-profile and prefix scientific bodies are
10,000/16-row or bounded-prefix pilots. They are not substituted for Alpha's
complete scientific bodies. This is a bounded backup search result, not a claim
that no unknown backup exists anywhere on the server.

## Scientific identity

`science/` contains byte-identical frozen source copies from the verified
read-only Source26 snapshot. `kernel.py` copies the original Main
`raw_uniform_cost_v1.run` functions `funnel`, `chemical_task`, `output_schema`,
and `parquet_row`. Their only normalized change is the import path to the
isolated byte-identical feature package. Scientific field constants and all
four function ASTs are checked against `scientific_origin_contract.json`.

The original Alpha `cid_summary`, `row_fact`, and `record` functions are copied
without changing their ASTs. Source facts retain CID text (including any leading
zero bytes), full raw/source-SMILES SHA, original source ordinal and part,
byte offset/length, and source terminator. The observed3786-byte maximum belongs
to this exact pinned snapshot; it is a framing invariant, not a chemical-size
filter. Source isotopes, stereo, X01-X05 and exact compatibility fallback remain
unchanged. RDKit2025.09.5 is required.

The copied `science/common.py` retains unused legacy resource helpers to preserve
its original bytes. Reconstruction never calls its old wall/freshness guards.
The actual call path uses the new cooperative resource monitor. Chemistry tasks
have no arbitrary future timeout, repair counter or application wall deadline.

## Durable execution and storage

Each original descriptor owns a nonblocking **live flock**, rather than an
unrecoverable intent-file existence gate. Root can allocate disjoint descriptor
indices across actual parents. Each parent reuses a bounded spawn pool. Resource
stops halt new work and naturally drain submitted work; no process is signalled
and no infrastructure failure becomes a molecular chemical rejection.

Every completed descriptor stores:

1. `all_results.parquet`, the original complete typed Arrow layout including
   full original feature JSON and error evidence, with unchanged binary64 fields;
2. `source_facts.parquet`, exact row byte/CID provenance;
3. `accepted.parquet`, every accepted original row plus its integer CID and
   fragment locator, directly consumable by bulk_v2 exact minimum-CID SQL;
4. an atomic hashed `complete.json`, actual source/output frames, worker counts,
   reason counts and real parent identity.

There is no second huge full-JSON journal. Original scientific values/errors
survive in the typed output and exact raw provenance survives separately.
Interrupted attempts remain under unique attempt paths. Only closed units are
reused. A closed output is hashed once; an unchanged physical frame reuses that
proof. Changed/restored files must match the original full SHA before adoption.

`assemble` requires **all500** exact original units and conserves all124,857,440
source rows. It emits `projection_manifest.json` using the
`PUBCHEM_ALL_CLOSED_PROJECTIONS_V2` consumer schema, with explicit reconstruction
lineage. It never impersonates the old Alpha502 closure. The manifest can then
feed `pubchem_closed500_bulk_v2.merge.materialize` under Root's fresh complete
storage/memory/account-quota admission. Dedup/filter/ranking/generation remain
subsequent explicit pipeline stages.

## Honest baseline comparison

The old Alpha counts are110,046,364 accepted,14,764,875 chemical rejects and46,201
technical UNKNOWN. New observed counts are reported beside these with signed
differences. They are **not forced equal**. Removing old operational timeouts can
resolve some technical outcomes, but a count difference alone does not establish
that cause. Per-row attribution remains unavailable unless old bodies are
recovered; known reasons are recorded where evidenced, otherwise left unknown.
Technical UNKNOWN never becomes an invented chemical exclusion or zero-filled
accepted feature.

## Root preparation and execution

Root supplies actual resource JSON fields: `output_cap_bytes` (entire shared
reconstruction output including retained partials), `other_future_reserved_bytes`,
`minimum_free_bytes`, `software_rss_budget_bytes`,
`minimum_node_available_bytes`, `quota_feed_path` and `quota_device`.
No guessed Main input paths/hashes are used and no ready data admission is implied
by an offline draft. The live quota publisher samples existing output allocation
**before** querying real user quota, preventing newly written bytes from being
credited against an older quota sample. Whole-filesystem free space is checked
separately and never replaces account quota. Quota observation freshness is a
real capacity-observation requirement, not an application computation deadline.

For the current completion goal, prefer Root's already-live shared
`quota_snapshot` + `quota_authority`, reusing
`completion_runtime_v1.quota.budget_check`; the optional package-local publisher
is unnecessary in that mode. Root's explicit user-approved CPU21 policy can be
bound as `cpu21_authorization_reference` from the actual
`configs/data_v1/expansion/user_cpu21_authorization_20261103.json` file. A run on
compute-0-21 must observe its real `all` partition and this approval; it never
claims to have run in the `cpu` partition. Root prefers newly available CPU
partition nodes for subsequent jobs and records the actual resource decision.

```sh
PY -m workflows.expansion.pubchem_raw_reconstruction_v1 prepare \
  --inventory-receipt ACTUAL_INVENTORY_JSON \
  --acquisition-receipt ACTUAL_ACQUISITION_JSON \
  --output NEW_OUTPUT_ROOT --plan NEW_PLAN_JSON \
  --resources ROOT_ACTUAL_RESOURCES_JSON --workers ACTUAL_CPUS

# Login metadata service only, managed/identified by Root; no scientific data work.
PY -m workflows.expansion.pubchem_raw_reconstruction_v1.quota_feed \
  --plan NEW_PLAN_JSON --output EXACT_QUOTA_FEED

# Run only inside actual Main Slurm allocations. No submission occurs here.
PY -m workflows.expansion.pubchem_raw_reconstruction_v1 run \
  --plan NEW_PLAN_JSON --indices ROOT_ASSIGNED_ORIGINAL_INDICES

# After all actual parents/units are accounted for:
PY -m workflows.expansion.pubchem_raw_reconstruction_v1 assemble --plan NEW_PLAN_JSON
```

Root runs the Linux fixture suite before formal reconstruction:

```sh
PY -m unittest workflows.expansion.pubchem_raw_reconstruction_v1.test_reconstruction
```

The tests check frozen scientific/provenance ASTs, exact CID/CRLF facts, actual
three-state tiny reconstruction with Parquet readback/resume, Main-original vs
isolated-science parity, honest changed technical counts, and rejection of a
narrowed fake full scope. Fixture success is not full-population completion.
Root records actual parent terminal states, total costs and subsequent all-source
decontamination/novelty release. This package never fabricates those facts.
