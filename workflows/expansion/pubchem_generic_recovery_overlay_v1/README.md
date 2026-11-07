# Versioned generic recovery, staged source preparation

Population version: `alpha-original502-generic3642-recovery-v1`. Original typed
sources,46,201 UNKNOWN records, old minCID candidates/aliases and old1M remain
immutable. COCONUT/all11 scope is unchanged. No implicit fallback to the old
population is allowed for a later corrected-population query.

## Stage1: candidate delta

```text
<private-python> -B -m workflows.expansion.pubchem_generic_recovery_overlay_v1.delta --plan <actual-plan.json> --startup-proof <actual-startup-proof.json>
```

Plan schema `PUBCHEM_ALPHA_GENERIC_RECOVERY_DELTA_PLAN_V1`, scope
`pubchem_alpha_generic_recovery_delta_v1`, `population_version` as above.
Use the shared current Alpha profile/Guard/node launcher,16CPU workers, UID1264,
endpoint218.192.171.238:22, clean code cwd and current reviewed budgets. Suggested
software process-tree24GiB/reserve24GiB are not Slurm memory reservations. Prefer
a new private stage directory under `/gfshome/alpha/pubchem_expansion_20261103/bulk`
and that same aggregate scope/cap, rather than the old original502 namespace.
Optional `reviewed_storage_budget_reference` requires `storage_budget_scope`
(e.g. `bulk`) and strictly binds that actual V2 budget's cap/future/floor to this
plan; no running resource numbers are built in.

Input reference triples:

| Field | Actual locator; hash native metadata, do not transcribe a future pin |
|---|---|
| `native_diagnostic_receipt_reference` | `/gfshome/alpha/pubchem_expansion_20261103/reports/pubchem_generic3642_diagnostic_v1_job_1885177/receipt.json` |
| `native_diagnostic_actual_reference` | `A/control/pubchem_expansion_runtime_20261103/generic3642_1885177_root_actual_v1.json` |

Here `A=/gfshome/alpha/codex_data_v1_20261026`. The review already binds actual
177C0/accounting/rawsacct and shared-library119 validation. Its
`scientific_population_recovery_accepted=false` is preserved: it accepts diagnostic
facts and authorizes no pre-existing population rewrite. This stage creates only
a fresh candidate delta for actual C0/Root review before overlay construction.

Pin all new package `.py` files, shared runtime, the borrowed original
`pubchem_closed500_bulk_v2/schema.py`, and technical-audit `scan.py`/its common
dependencies in actual startup refs. No chemistry library is imported. All282MB
closed native DATA is freshly streamed/SHA checked on a stable same file; each3642
row's strict status/flags/template/key/FP/non-generic comparison and original
failure/provenance are checked again. There is no native chemistry retry.

Output candidate Parquet uses exactly the old full candidate Arrow schema.
Scientific feature values come from the diagnostic's complete evaluation JSON;
all non-generic fields must still be exactly equal to its independent original
expectation. All three F64 feature fields get complete output readback/bit checks.
New effective candidate fields describe this new version: category `accepted`,
empty technical codes/errors, new full feature payload, and sample_group equal to
the population version. This never edits or relabels the original technical row:
the separate lineage records exact original Parquet/physical row and audit/native
DATA reference/line/offset/SHA. Missing old per-row timings remain null; worker_pid
is explicitly the original177 native diagnostic worker namespace. Actual materializer
worker proofs and per-worker row counts are separate.

`recovery_delta_aliases.parquet` retains all3642 distinct positive source CIDs,
including duplicate full keys. Internal full-key dedup is intentionally deferred
to the overlay stage. `recovery_source_lineage.DATA.jsonl` has3642 rows and exact
binary64 feature hex. Producer schema `PUBCHEM_GENERIC_RECOVERY_DELTA_PRODUCER_V1`,
status `CANDIDATE_DELTA_CLOSED_PENDING_ROOT_ACTUAL_C0`; no minCID population,1M,
all11 index, filter, scientific adoption, or new effective population census is
claimed here. Infrastructure failures preserve private partial output.

## Stage2: exact small overlay and Root completion seal

```text
<private-python> -B -m workflows.expansion.pubchem_generic_recovery_overlay_v1.overlay --plan <actual-plan.json> --startup-proof <actual-startup-proof.json>
```

Plan schema `PUBCHEM_ALPHA_GENERIC_RECOVERY_OVERLAY_PLAN_V1`, scope
`pubchem_alpha_generic_recovery_overlay_v1`, same version/profile/Guard/bulk
aggregate policy as stage1. `duckdb_memory_bytes` is the declared own SQL budget.
Additional reference fields:

- `base_pool_receipt_reference`: existing original502 `unfiltered_pool/receipt.json`.
- `base_pool_actual_reference`: `B/mincid_full502_actual_parent.json`.
- `base_closed_frame_ledger_reference`: `B/bulk_closed_other_future_credit_v1.json`.
- `recovery_delta_receipt_reference`: the actual completed stage1 producer.
- `recovery_delta_actual_reference`: Root's actual stage1 C0 review.

Here `B=A/control/pubchem_expansion_runtime_20261103`. Stage1 review schema is
`ROOT_PUBCHEM_GENERIC_RECOVERY_DELTA_ACTUAL_REVIEW_V1`, status
`APPROVED_CANDIDATE_DELTA_3642`, with reviewer `root`, exact
`producer_receipt_reference`, `actual_parent`, and `actual_accounting_reference`.
The actual parent must occur in the pinned accounting's `actual_parents`, have
Alpha endpoint/UID1264 and COMPLETED0:0, and retain a pinned `raw_sacct_reference`.
This only records the existing required actual-stage review, not user approval.

The original34GB/1.33GB bodies retain their old complete C0/SHA and historical
inode/mtime/ctime witnesses. Native Gluster authority binds the current quota
volume/root. Client-local device numbers are recorded separately, never equated
across nodes; full current before/after frames still include device. No large
fresh full-body hash is claimed. Only key/CID columns participate in the old
population scan. All3642 alias identities/ordinals must equal delta candidates,
and no delta CID may occur in any old alias. Exact SQL computes new fullkeys,
replaced representatives, duplicate aliases, and winning complete delta rows.
Exported winning-delta F64 bits are fully checked. One native fixture compares
the logical result with the complete accepted-row oracle, including lower/higher
CID collisions, duplicate delta keys, all aliases, and a valid H-only empty stratum.

Producer `PUBCHEM_EXACT_MINCID_OVERLAY_PRODUCER_V1` remains
`OVERLAY_CLOSED_PENDING_ROOT_ACTUAL_C0`. Root's subsequent actual overlay review
schema is `ROOT_PUBCHEM_GENERIC_RECOVERY_OVERLAY_ACTUAL_REVIEW_V1`, status
`APPROVED_UNFILTERED_POPULATION_OVERLAY`, reviewer `root`, exact producer reference,
actual parent/accounting and `scientific_population_recovery_accepted=true`.
Only after that existing C0/review can the metadata-only command emit authority:

```text
<private-python> -B -m workflows.expansion.pubchem_generic_recovery_overlay_v1.seal --producer <actual-overlay-receipt.json> --actual-review <actual-root-review.json> --output <fresh-pool-authority.json>
```

This command creates no approval and never rewrites a producer. It requires the
real review/accounting and emits `PUBCHEM_EXACT_MINCID_OVERLAY_POOL_V1`, explicit
version, actual corrected counts, original source lineage and Root C0 pins. The
strict `reader.validate_header(pool)` rejects a pending producer, old pool relabel,
incorrect population/version or mismatched review. `reader.bind(db,pool,check)`
registers exact logical `candidates`/`aliases` views and returns current source
witnesses; `reader.finish(witnesses)` checks them after use. Legacy scalar-Parquet
entry points cannot silently consume this authority; no `.candidates` fake path
is emitted. New explicit baseline/filter adapters will use this reader.

The completed authority describes logical candidates as old canonical rows ANTI JOIN
replacement fullkeys UNION ALL new winning delta rows. Logical aliases are the
old aliases reference UNION ALL all3642 delta aliases. Only an actual complete
overlay stage and Root review may assert corrected accepted110050006/UNKNOWN42559;
new-key/replaced-representative/duplicate counts must be measured in native SQL.
Neither34GB old candidate nor1.33GB alias body is copied to form a new full pool.

An independent new baseline stage will use the same hash domain/seed/rank order.
Since old fullkeys are never removed, the exact new top1M is drawn from the
independently closed old top1M plus new fullkeys; representative-CID replacements
do not change fullkey rank. It must create fresh version-bound membership,
features and query files and report changes. A meaningful synthetic full-population
versus incremental topK parity fixture will precede that stage. Old1M is history,
never relabelled as the corrected baseline. Separate stage C0s remain Root-owned.

## Stage3: fresh exact incremental1M baseline

```text
<private-python> -B -m workflows.expansion.pubchem_generic_recovery_overlay_v1.baseline --plan <actual-plan.json> --startup-proof <actual-startup-proof.json>
```

Plan schema `PUBCHEM_ALPHA_GENERIC_RECOVERY_BASELINE_PLAN_V1`, scope
`pubchem_alpha_generic_recovery_baseline_v1`, same explicit version/resource
fields. Inputs: `source_pool_receipt_reference` is the actual sealed stage2
authority; `previous_baseline_receipt_reference` is the old original502
`baseline_1m/receipt.json`; `previous_baseline_actual_reference` is
`B/baseline1m_actual_root_accounting_v1.json` (actual1885155C0). Old receipt must
bind the original base pool, full predecon phase, exact seed/domain/sample recipe.
Old1M membership and features are freshly SHA checked. Old743MB query is not
needed. The complete old1M identity/ordinal sets in both Parquets must agree.
Actual startup source refs must include the borrowed Alpha handoff
`baseline_core.py`, `projection.py`, `sql.py`, `scientific_contract.py` and its
`original_function_contract.json`. Existing original scientific ASTs are checked;
the fixed domain/seed/sample-size constants are enforced explicitly.

The original hash/domain/tie order ranks the corrected old top1M plus every new
fullkey. Existing key representative CID replacements are applied before ranking.
Every selected feature row is the complete actual minCID winner: old sample
feature rows for replaced keys are removed and winning delta rows supply their
entire new features, not merely an edited CID. This matters even for identical
full InChIKeys whose original source graphs may differ. The original34GB canonical
payload is not scanned/copied. New memberships/features/query are fully emitted.

Before DATA, one native fixture compares the result with an independent complete
corrected-population Python ranking, ensuring insertion above/below the cutoff,
whole-population equality, representative CID replacement and dropped old members.
The production result records actual rank-input size1M+newKeyCount, the exact
insertion-monotonicity proof, removed/added membership and CID changes. It makes no
claim to have rehashed all110M keys or reused a sampled substitute.

Output format remains `EXPANSION_PUBCHEM_PREDECON_BASELINE_V1` because the exact
scientific sample recipe and data format are unchanged. Mandatory
`population_version`, new `source_pool_receipt`, and previous-baseline history
references distinguish this new population and fresh artifacts. Ordinals are
0..999999, query order is `sample_ordinal_ASC`, fingerprint recipe unchanged.
Actual new baseline C0 remains for Root readback. The old baseline is never
overwritten or silently re-labelled; before/after augmentation must pin this
same new baseline membership if using the corrected population.

## Stage4: explicit corrected-population all11 filter and query

```text
<private-python> -B -m workflows.expansion.pubchem_generic_recovery_overlay_v1.filter --plan <actual-plan.json> --startup-proof <actual-startup-proof.json>
<private-python> -B -m workflows.expansion.pubchem_generic_recovery_overlay_v1.query --plan <actual-plan.json> --startup-proof <actual-startup-proof.json>
```

Filter plan schema `PUBCHEM_ALPHA_GENERIC_RECOVERY_FILTER_PLAN_V1`, scope
`pubchem_alpha_generic_recovery_filter_v1`. Add `source_pool_receipt_reference`
(sealed overlay), existing `exclusion_index_receipt`,
`root_index_acceptance_reference`, `regression_reference`, and explicit
`parent_transport_manifest`. All original all11/all-split/physical-source/UNKNOWN,
actual index C0 and selection regression gates remain required; the corrected
pool does not bypass any COCO source-scope authority. The user-approved732 source
dispositions belong to the independent actual all11 authority, not this module.

The original `filter_core` function's code object executes with private globals
and one explicit logical-reader binding. Its scientific/output SQL is unchanged.
The existing declared H-only validation extension is reused, with positive source
constraints unchanged. Original module globals, functions and old entry points
are never monkeypatched. A logical relation token is consumed only by the scoped
binding wrapper; no fictitious Parquet/SQLite path is created. One native fixture
compares logical binding against unchanged direct-Parquet V3/H-only filtering,
covering full-key, exact-composition, positive lower-bound veto and retained H-only.
The synthetic binder is an internal fixture seam, never a plan/runtime fallback.

Pin the borrowed `filter_core.py`, `empty_domain.py`, `science_v3.py`,
`scientific_contract.py` and `original_function_contract.json` in actual startup
sources. Original scientific ASTs are checked before input. Output retains
`expansion_filtered_columnar_pool_v1` format, explicit population version/new pool
reference, one real complete eligible-candidate Parquet, hits and original alias
union references. No old full candidate or alias body is copied merely to build
an unfiltered pool. Original all11 evidence remains independently accepted.

Query plan schema `PUBCHEM_ALPHA_GENERIC_RECOVERY_QUERY_PLAN_V1`, scope
`pubchem_alpha_generic_recovery_query_v1`; add `filtered_pool_receipt_reference`
and pin original handoff `projection.py`/`sql.py`. Use a separate fresh private
stage after actual filter completion. The complete eligible Parquet is SHA
verified and projected using the unchanged exact seven graph fields. Manifest
format `EXPANSION_TYPED_DECONTAMINATED_QUERY_PROJECTION_V1` binds the new population
version/actual filtered receipt, recipe and full row census, with targets/features
from downstream absent. Existing rank/ordered-source SQL can keep reading the
single actual filtered Parquet; its complete-source gate must explicitly recognize
the new sealed pool authority rather than re-label it as originalAlpha502.
