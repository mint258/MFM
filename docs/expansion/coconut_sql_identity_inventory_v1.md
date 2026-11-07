# Alpha COCONUT physical SQL identity-field inventory

Source draft only. No Python, AST, fixture, scientific body read, SSH, Git or
Slurm execution was performed to prepare it. The actual1884767 schema metadata
has15 complete public-table definitions, PostgreSQL text COPY, and only the
first citables COPY header within16MiB. SQL1884765 is actual C0 with
37876914074B/SHA256bb61f8e074f876beaaf251b9abe5b4334aebbda28717120ac482db39d58ced29.
That is the exact downloaded2026-10 physical scope. Unpublished hard-deleted
history is not an additional gate.

New source package: `workflows/expansion/secondary_coconut_sql_identity_v1/`
(`__init__.py`, `contracts.py`, `copy_text.py`, `run.py`). Alpha target:
`/gfshome/alpha/codex_data_v1_20261026/code/secondary_coconut_sql_identity_v1/`.
It reuses the registered bounded probe's source/producer helpers and SQL-header
lexer, without editing them or creating a new queue.

```text
AlphaPy -B -m secondary_coconut_sql_identity_v1.run --plan ABS --startup-proof ABS
```

- producer_key/scope_key: `coconut_sql_identity_inventory_alpha_v1`
- plan: `SECONDARY_COCONUT_SQL_IDENTITY_INVENTORY_PLAN_V1`
- proof: `SECONDARY_COCONUT_SQL_IDENTITY_INVENTORY_STARTUP_V1`
- Root review: `EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1`
- mode profile: stage `SQL_IDENTITY_PROJECTION_PROFILE`, pilot true, whole2GiB.
- mode full: stage `SQL_IDENTITY_PROJECTION_FULL`, pilot false, whole64GiB.

Both require actual Alpha UID1264/node/boot/same exec gate PID/current job,
complete main/argv/source pins, CPU16/default-memory/no exclusive, fresh proof,
whole-minute wall<=48h and fresh effective storage with all reserved caps plus
200GB. No memory allocation is invented. Current self-RSS2GiB is an algorithm
reference; MemAvailable15%, invalid metrics, actual output/scratch and remaining
parent wall stop new work. Native SQLite operations drain; no signals or SQL
interrupt are sent. Slow valid memory samples are recorded as lag. Cost is
report-and-continue; actual allocated parent costs remain a later accounting
closure, including startup and failures.

Root fills common exact plan fields as in the tested probe. Additional required
small refs are `format_probe_receipt_reference`,
`format_probe_accounting_reference`, `schema_observations_reference` and the
SQL producer receipt/cost fields from the probe. Parent evidence includes these
actual records. The one data locator is the complete existing SQL file. The
scope_parameters must equal `contracts.parameters(mode, profile_limit_bytes)`.
Use268435456 for an initial256MiB profile; full uses0. No future ref is filled by
this source. The new/old helper source pins are explicitly checked.

The profile stops at the first complete logical COPY record past the selected
limit. At most64MiB record-boundary overshoot is allowed; a larger record fails
with partial evidence rather than being truncated or silently dropped. Read
ahead, consumed bytes and region SHA are separate. Profile never claims whole
EOF/full SHA/all-table coverage. It may cover only citables and project no
identity rows. Such a profile measures skip/width throughput, not unseen-table
output throughput or RDKit cost; actual coverage is reported for Root review.

Full additionally requires `accepted_profile_receipt_reference` and
`accepted_profile_accounting_reference`, a real C0/UID1264 raw sacct parent,
the exact same four kernel source hashes, and Root's
`actual_profile_cost_and_coverage_reviewed=true`. It rehashes the entire SQL,
checks file identity before/after, every COPY row width, block terminator,
known table/column maps, source EOF and dump tail marker. Unknown tables,
data statements, malformed escapes/UTF8, widths or boundaries stop without
dropping source rows. A failure note records table/block/row/byte offsets.

The COPY decoder follows [PostgreSQL's official text-format rules](https://www.postgresql.org/docs/current/sql-copy.html):
it distinguishes NULL before decoding, supports escaped delimiters and physical
line continuations, and handles byte escapes across chunks. Unselected field
bytes are skipped without value decoding. The dump is never imported or run.
SQLite statements are our own fixed schema/queries over selected fields only.

Raw projections retain molecules' canonical SMILES/InChI/key and identity/state
flags; entries' raw/standardized/parent SMILES, status/is_invalid and links;
structures' IDs/links; properties' native molecular_formula for a future
missing-key conservative fallback; collection states and source links. All
physical statuses, NULLs, invalid and unlinked rows remain. No target/property
descriptor, sugar-free fragment, Murcko key, geometry JSON or activity-based
selection enters this stage. Duplicate IDs/orphans are explicit UNKNOWN facts,
not an excuse to remove records. All15 tables have physical row counters.

Outputs include source-byte/row-SHA keyed raw-identity Parquet, a derived
identity-only SQLite database, status counts, progress and an output SHA/footer
manifest in the final receipt. No files are added to Git as data artifacts.
Three new synthetic kernel checks run after startup and before SQL body I/O:
escape/NULL/chunk boundaries, malformed record failure, and physical Parquet
preservation of inactive/invalid original values. No prior fixture suite reruns.

No COCONUT chemical normalization has occurred. StageB must separately profile
and then export all projected identities with the frozen v1 RDKit2025.09.5
SMILES/key functions and fullKey+WP5 rules. No X filtering, neutralization,
tautomer conversion or isotope/stereo edits apply to downstream identities.
This inventory grants no global decontamination, pool, UFF/QM or training release.
