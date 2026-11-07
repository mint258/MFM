# COCONUT finite molecular source-scope proposal

## Purpose and requested decision

This is an unapplied proposal, supported by actual Alpha audit1885166 COMPLETED0:0. Authorize only the 732 individually listed non-specific supplied entries to be quarantined from the finite-molecule exclusion scope, preserving every raw source record and audit. Retain the three recovered concrete compounds and apply their exact source-bound compositions through the original consumer. All other concrete COCONUT entries and all other downstream sources remain in scope. No source deletion or whole-dataset omission is proposed.

## Inputs and hashes

- Complete735 structural audit DATA: `/gfshome/alpha/pubchem_expansion_20261103/reports/structural735_v1_job_1885166/structural_evidence735.DATA.jsonl`, SHA256 `fe4cf33850282805df1b391ee221fe98997c6f088e085b5e01821d739e118b7a`.
- Actual Root audit review: `/gfshome/alpha/codex_data_v1_20261026/control/pubchem_expansion_runtime_20261103/structural735_1885166_root_actual.json`, SHA256 `511604764bf47f8590ff16f320a20bc408b382df7847ce815bcbc6a8f3139039`.
- Per-row review table: `coconut_molecular_scope_proposal_20261103_v1.csv`, SHA256 `e5eeea7985aae5dc019d83ecb6c139732867f594a32b8d95f5eb65ae41a4b031`.
- Manifest: `coconut_molecular_scope_proposal_20261103_v1.json`; it enumerates every proposed source ID and preserves its source-ID set hash.
- Full-pool hypothetical impact: `/gfshome/alpha/codex_data_v1_20261026/control/pubchem_expansion_runtime_20261103/cos_impact_1885163_root_actual.json`, SHA256 `de0d6ffa890e6e6858c49b1863766756c8061c0c066151f11f9bc6e1160e4fb0`.

## Rules and parameters

The audit rechecked735 physical source records, all8085 cached representation fields and10 primary-source fields. It ran no new chemistry or network work. Missing keys alone never imply an abstract record or a nonexistent real-world molecule. Fixed atom tables take priority over incomplete graph identity; query-bond-only candidates, conflicting compositions and uninterpreted group metadata are exposed separately. The audit found no additional fixed-atom composition candidate beyond the three restored compounds.

The proposed scope excludes entries whose supplied representations do not uniquely specify a finite molecule, plus the three official ontology witnesses. It makes no claim that a named real-world compound does not exist. The proposal requires explicit user confirmation before any index, source manifest, filter or eligibility rule changes.

## Script-generated results

| Evidence partition | Rows | Proposed treatment |
|---|---:|---|
| Source-bound concrete recoveries | 3 | Retain and fully decontaminate by exact composition |
| Official ontology classification witnesses | 3 | Quarantine only if approved |
| Supplied query/dummy/unspecified structures | 729 | Quarantine only if approved |
| Insufficient evidence outside those groups | 0 | None silently omitted |

Without the proposed scope treatment, the tested most-conservative C/O/S veto would exclude 109,868,692 of 109,871,959 candidates, leaving at most 3,267 before other exclusions. That cannot provide the requested2,500,000-molecule batch. This veto has not been applied.

## Exceptions and handling

The restored compounds are Dolastatin13 (707929), Chebulinic acid (174911) and the named Nobiletin component (174178). Source stereo and technical-grade caveats remain attached; no key or stereo is fabricated. The official ChEBI witnesses cover electron, hydrogen-halide class and organohalogen class; no finite representative structure is substituted. The per-row table binds original entry IDs, COPY locators, source-row hashes and exact audit-line hashes, with no raw MOL bodies committed to Git.

## Known limits and current state

Current state is NOT_APPLIED_PENDING_USER_CONFIRMATION. Original graph UNKNOWN735 and all raw source bodies remain unchanged. No quarantine, lower-bound adoption, candidate filtering, ranking or all11 release has occurred. If approved, a new source-scope version and complete provenance ledger must be built and checked before the original concrete-molecule decontamination continues; the old735 producers and old HOLD remain historical evidence.
