# Next all-source identity inputs after local closure

This is a source/metadata review, not an acquisition or normalization result.
No Python, scientific body read, network request, SSH, Slurm or Git action was
run while preparing it. All large-body hash/projection work remains restricted
to a fresh authorized CPU allocation on the owning cluster.

Guide2.4 requires original all-role v1 plus4900 embargo and every downstream
split. Local closure1192 has11398552 unique(dataset,source_id) records and
preserves original physical roles. It does not release global decontamination.
Its receipt is
`artifacts/expansion/identity/sb5_identity_full_closed_units_coverage_v1_v1/receipt.json`.

## Reuse these existing inputs

Do not redownload or rerun the whole local identity projection for:
v1 original formal11231854 plus4900 embargo, ExpansionRx7608(train5326/test2282),
CYP2003, AZ raw120(including109 fold members plus11 raw extras), QM7 original
Z-only7165, QM9 original133885, and the six local MoleculeNet CSVs:
BACE1513, BBBP2050, ClinTox1484, ESOL1128, FreeSolv642, Lipophilicity4200.
Existing closed unit Parquet references and physical SHA pins are available
through1192. Original source authority remains the76-file547 pins.

The18 missing identity-or-composition rows remain unresolved; do not discard
them or call decontamination complete. Small unit receipts locate them in
graph_identity_000017/18/19/21/22/23/24. These units cover BACE/BBBP/ClinTox/ESOL
boundaries; mixed units do not identify which dataset each missing row belongs
to. A minimal future CPU diagnostic can project only the18 rows selected by
`missing_identity_or_composition` from the existing missing-identity artifact:

```text
/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion/identity/sb5_identity_full_closed_units_coverage_v1_v1/missing_identities.parquet
bytes94968, SHA256 c2aaf5952e45ff70d7cf6d479086a3516f04657178d5d067b515f99098c013ba
```

Only dataset/source_id/SMILES/key/composition/null-reason provenance is needed;
no labels, features or broad renormalization. There is currently no registered
missing18-only CLI. The missing_full_key7183 and unresolved_source_variant8729
counters overlap; QM7 composition-only scope must remain conservative rather
than being converted into coordinate-perceived graphs.

## External sources still needed

- MoleculeNet's proposed17-member union remains intact. Reuse the six local
  CSVs plus complete original QM7/QM9; their exact planned benchmark versions
  and ID-universe mappings still need evidence. Nine other named members have
  no closed local full-source input: HIV, MUV, PCBA, PDBbind, QM7b, QM8, SIDER,
  Tox21 and ToxCast. PDBbind's general2019/refined2019/core2013 locators are
  separate until an explicit union is proved. Do not substitute a core set.
  Official loader-pinned URLs are in `external_all_source_locators_v3.md`.
  Current1094 HEAD results support metadata reachability, not payload SHA,
  row counts, all-split identity or version equivalence.
- TDC ADMET needs the official4426004 archive's22 endpoints x train_val/test,
  hence44 logical CSV members. Main1094's official redirected HEAD returned403;
  a HEAD is not a measured full GET. Any later authorized Alpha attempt uses
  the exact official path and ordinary network configuration.403/429/access
  or login restrictions must be retained, with no proxy/mirror/confirmation
  bypass or repeated evasion. No44-member existence/count proof exists yet.
- MARCEL needs both full Drugs and Kraken sources. Official Drive locators
  timed out under1094's node/environment/budget; neither full archive is pinned.
  Reuse only official locators, report access restrictions, and do not contact
  authors. Do not invoke descriptor/energy sorting or unrestricted pickle.load.
  Kraken still needs a separately reviewed identity-only format boundary.
- COCONUT CSV is already physically acquired and must not be downloaded again.
  Lite is not a replacement for the complete active/inactive universe.

The immutable official metadata versions and exact URL mappings are documented
in [external_all_source_locators_v3.md](external_all_source_locators_v3.md).
Those repository commits identify metadata code, not payload releases.

## COCONUT's next CPU stage

Alpha1884764 is actual COMPLETED0,47s x16CPU=752coresec. Its complete ZIP is
247959854B/SHA25695a0525b11a334389ceebb941d0a8ee9446892fccf4f8ff78d2184efc1c974ea.
The single CSV member is699882314B/SHA256ad4b174454c16dded7cbb40e96dd045b8d4203bc9e96473bb6d0c1c87ea4b46a;
EOF/CRC passed,738794 nonblank rows all have44 fields. Its identity columns are
identifier/canonical_smiles/standard_inchi/standard_inchi_key. No status column
was observed. This is a structural profile, not identity acceptance or proof
of inactive/soft-deleted coverage.

SQL1884765 was still running at the task handoff. The reviewed target is a plain
application/sql file of37876914074 expected bytes. No final SHA, terminal C0,
complete row count or inactive coverage is asserted here. Its existing
producer writes `sql_prefix_profile.json` only after complete GET; that metadata
contains64KiB prefix SHA and PostgreSQL/CREATE markers, not table definitions,
COPY/INSERT grammar or the molecule-to-structure/state mapping. The current
main-side small copies contain no actual SQL prefix profile yet.

Therefore the exact next stage is a bounded `SQL_FORMAT_SCHEMA_PROBE`, whose
NOT_READY contract is
`configs/data_v1/expansion/secondary_coconut_sql_inventory_stage_contract_v1.json`.
It activates only from the actual complete SQL receipt, producer prefix profile
and actual terminal accounting. A fresh Alpha CPU proof must precede every SQL
body read. The probe retains only bounded structural metadata and prefix SHA,
never arbitrary row values, and never imports a database or executes SQL.
Observed dialect/table/identity/state/link columns and data-section grammar
then determine a separately reviewed whole-file inventory parser. If the
bounded region is incomplete or unsupported, remain PENDING rather than guess.

There is no whole-file SQL inventory CLI today. The new bounded probe source
draft is `workflows/expansion/secondary_coconut_sql_inventory_v1/` (three files).
After actual SQL C0/payload/cost pins exist and Root reviews the exact scope,
Alpha's primary argv is:

```text
ALPHA_PY -B -m secondary_coconut_sql_inventory_v1.probe --plan ABS_ACTUAL_READY_PLAN --startup-proof ABS_FRESH_ALPHA_PROOF
```

Plan/proof schemas are SECONDARY_COCONUT_SQL_FORMAT_PROBE_PLAN_V1 and
SECONDARY_COCONUT_SQL_READONLY_STARTUP_V1. The producer/scope key is
coconut_sql_format_schema_probe_v1. Root's actual exact plan supplies
sql_producer_receipt_reference and sql_producer_cost_reference, source pins,
scope parameters, and the one complete SQL data locator. Probe defaults are
not implicit: `scope_parameters` must equal `probe.parameters(rehash_bool)`.
Two synthetic lexical/privacy checks run after fresh startup and before any
SQL body read. A COPY data line and a dollar-quoted function body containing
CREATE TABLE text must not become persisted schema. No current invocation,
test success, completed SQL SHA or ready request is claimed by this draft.

Current
`secondary_source_acquisition_v1/run_v1.py` supports only CSV_ZIP_PROFILE and
PLAIN_SQL_FULL_DOWNLOAD; `profile.py:profile_zip` is a streaming CSV structure
counter, not an identity exporter. `identity_v2/projection_v2.py:identity` and
`:source_smiles_keys` are reusable normalization functions with preserved
isotope/stereo and no chemical exclusions, but no external all-family CLI exists.
They should consume proven projected identity fields later, not raw SQL or
benchmark training loaders.

Reuse Root's existing secondary held queue/probe/gate/resume/accounting machinery.
It needs a new exact readonly producer adapter; do not pass the new stage as if
it were an old acquisition/portable scope, edit registered sources in place, or
create a second queue/observer. The controller's real UID1264/node/boot/current
job/full argv/source/default-memory/storage checks remain mandatory.

After SQL completion, the existing usable accounting CLI is:

```text
ALPHA_PY /gfshome/alpha/codex_data_v1_20261026/workflows/expansion/secondary_source_acquisition_v1/close_actual_v1.py --receipt ACTUAL_SQL_RECEIPT --accounting-evidence ACTUAL_ALPHA_PARENT_EVIDENCE --output NEW_SQL_COST_JSON
```

It records actual terminal costs for either stage. Its field
`successful_profile_and_parent_complete` is intentionally CSV-specific; it is
false for SQL and must not be treated as SQL failure or silently relabeled.
SQL readiness instead binds its actual SQL completion status plus COMPLETED0
parent and full payload pin. Original download and any failure costs remain.

The later complete inventory must rehash the current full payload, scan EOF,
independently count all relevant table rows/IDs/states, conserve molecule and
structure links/orphans/missing identities, and reconcile the CSV universe.
Only that evidence can justify a smaller identity export substituting for SQL.
No step here permits pool repair/release, novelty ranking from benchmark
targets/features, UFF/QM or training.
