# COCONUT B: identity-key normalization profile interface draft

Status: `NOT_READY_A_FULL_ACTUAL_AND_ROOT_REVIEW_PENDING`. This is an interface
design, not an executable producer or a READY request. A full has not run or
passed. No normalization, tests, Python/AST, data-body reads, SSH, Git or Slurm
were performed to prepare this document. The A four-source kernel and all
registered sources remain unchanged.

## Dependency on actual A output

B consumes only the identity-only artifacts emitted by A's
`secondary_coconut_sql_identity_v1.run`. It must not reopen the 37 GB SQL, CSV,
coordinates, descriptors, activities or targets. A profile may stop within
`citables`; that cannot establish the identity-row population for B.

Before any READY B plan, require an actual A full receipt with schema
`SECONDARY_COCONUT_SQL_IDENTITY_INVENTORY_RECEIPT_V1`, mode `full`, status
`FULL_SQL_PHYSICAL_IDENTITY_FIELD_INVENTORY_COMPLETE`, actual terminal C0/UID1264
accounting, actual source SHA/EOF/row conservation and stable input frame. Bind
A's exact plan, startup proof, four kernel sources, receipt, accounting and
`physical_output_references`. Do not invent these future pins. CPU verifies each
consumed Parquet body's full SHA, fstat stability, exact A schema and footer row
count; Root login only reads the small authority metadata. A's original table,
status, NULL, duplicate-ID and orphan-link inventories are immutable upstream
facts, retained and referenced as a whole, including rows that lack graph data.

The source scope is the actual downloaded 2026-10 SQL physical release. No extra
requirement to reconstruct unpublished hard-deleted history is introduced.

## Profile selection and identity fields

Use two independent finite samples: at most 10,000 physical `molecules` records
and at most 10,000 physical `entries` records, without replacement, seed
20261026. Domain-separate the table name. Freeze the precise ordinal algorithm
and Python version in the eventual source/plan; materialize the selected ordinal
lists before dispatch. `N` for each table comes from actual A full metadata and
is cross-checked against the ordered Parquet row population. It is unknown now.
Selection uses physical row ordinals only, before examining identity/status.
There is no active/invalid, identity-resolution, duplicate or orphan filter.

Every selected physical record produces one durable result, even if it has no
usable identity. Keep A's `source_table`, `copy_block`, `source_row_ordinal`,
source offset/bytes/SHA and original `identity_fields_json` exactly. Carry the
raw status/active/is_invalid flags, parent/molecule/collection links and source
identifiers. Profiles do not infer whole-table/all-class coverage from their
sample. The remaining five A projection tables and A's full orphan/status audit
remain referenced original inputs; they are not silently relabeled as B
normalized records.

For `molecules`, key derivation uses `canonical_smiles` and retains the original
`standard_inchi_key`. For `entries`, derive independently from each of
`canonical_smiles`, `standardized_canonical_smiles`, `parent_canonical_smiles`.
Retain the original `standard_inchi` string and all absent/invalid field states,
but do not introduce `MolFromInchi`, coordinate perception, sugar-free or Murcko
structure substitutes. Preserve all original/canonical/parent variants; the
profile must not replace the source strings with a preferred variant.

## Frozen functions and key semantics

Call the actual frozen functions, without reimplementation or monkey-patching:

| File | Functions | Current small-source bytes / SHA256 |
| --- | --- | --- |
| `workflows/expansion/identity_v2/projection_v2.py` | `full_keys`, `rdkit_identity_modules`, `source_smiles_keys` | 8616 / `7da54ccb4488950fb567c17cfa161bc339d8a377f2e2fb27362434ce88516d28` |
| `workflows/expansion/common.py` | `wp5_key` / original `KEY_RE` | 4312 / `8c988f617776ad05354deae1cf69933e7ff95210f7a2609f903e4826172ccbad` |

These pins were read from the existing child source files, not from data or a
new actual execution. The eventual deployment must pin its actual Alpha copies
and transitive imports, including `identity_v2/readers_v2.py`, package files and
the exact dependency environment. Actual RDKit must be `2025.09.5`, verified by
the frozen `rdkit_identity_modules` call; import availability is not yet tested.
The `identity_v2` pathname is the existing registered identity implementation;
it does not authorize a new chemistry policy.

Use `full_keys([stored_key], strict=False)`: retain the invalid-key list rather
than dropping the physical record. Pass only present nonempty original strings
to `source_smiles_keys`, with their exact source-field names and bytes; absent
and empty variants are explicit missing-field observations. No trimming,
neutralization, tautomerization, stereochemical or isotopic editing is added.
For field-level attribution, call the frozen helper once per present variant
and retain its returned keys/errors. A usable stored key and an unresolved
SMILES can coexist and must remain distinguishable.

The row's conservative key union is valid source full keys plus all successful
SMILES-derived full keys. Apply frozen `wp5_key` to each valid full key:
`full_key[:14] + ':' + full_key[-1]`. This is not Murcko. Store original keys,
per-variant keys, union keys, WP5 keys, conflicts and exact helper errors
separately. Do not call X01-X05 or the feature/scaffold dispatcher on downstream
identities. Missing/unresolved/discordant identity remains visible and does not
become a chemical exclusion or a successful decontamination claim.

## Proposed execution contract for separate Root review

Proposed producer/scope key: `coconut_identity_norm_profile_alpha_v1`.
Proposed plan/proof schemas:
`SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_PLAN_V1` /
`SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_STARTUP_V1`.
Proposed stage: `IDENTITY_KEY_NORMALIZATION_PROFILE`, kind `analysis`,
`pilot=true`, mode `profile`. No B full mode is implemented or authorized here.

An eventual module invocation may follow the already reviewed Alpha primary
eight-argument contract:

```text
[AlphaPy, -B, -m, secondary_coconut_identity_norm_profile_v1.run,
 --plan, ABS_PLAN, --startup-proof, ABS_PROOF]
```

That module does not exist yet. Root must first approve the concrete source and
add a known protocol to a new thin controller adapter; do not use an A or native
72 scope, do not modify the deployed queue, and do not create another queue.
The new review must bind exact scope parameters, actual endpoint/UID1264/node,
real primary/full argv, actual code and dependency sources, all parents and
actual A-derived data locators. It must require fresh <=120s startup proof and
current Slurm job/boot/exec-gate identity. No Main UID/proof substitution.

Initial ceilings proposed for review: CPU16, no scheduler memory/exclusive
request, wall4h, whole output2GiB including Parquet/ordinal lists/journal/failure
and scratch, at most32 pending records and16 workers. These are ceilings, not a
runtime/output forecast. Measure current owned RSS and MemAvailable; retain
invalid-metric STOP, stop new dispatch and naturally drain, without signals.
Slow sampling is lag metadata, not proof of memory shortage. Keep quota200GB
plus whole outstanding task caps. Preserve the user cost report-and-continue
authority, all failed-parent costs, and actual parent allocation accounting.

## Observable outputs and acceptance limits

Write fresh external Parquet with full per-record/per-variant observations,
selected-ordinal lists, a bounded durable result journal and a compact receipt.
Require selected = written rows = distinct selected source identities; keys can
be empty or multiple and therefore are not a row-conservation denominator.
Report missing fields, helper errors and stored/computed disagreement explicitly.
Bind CPU source hash/read, key derivation, writer, aggregation and total phases;
report separate uniform-table times, current RSS/output and actual parent cost.
Do not infer B throughput from A's COPY prefix or native72 timings.

Future guarded fixtures should check frozen-helper passthrough on a simple
valid key/SMILES, preserved invalid/null field states, per-variant conservative
union and exact WP5 protonation suffix. Those tests are not written or run here.
The profile outcome can only mean identity-key observations for its selected
records. A/B full chemical normalization, whole COCONUT key coverage, global
decontamination, pool release, novelty, UFF, QM and training acceptance remain
pending independent actual evidence and Root review.
