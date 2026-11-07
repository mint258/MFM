# Counted distribution and exact coverage reports

This is an independent analysis component for taskbook 2.1 and the distribution/
coverage portions of 2.9. It never changes screening or ranking decisions. It
requires complete physical population and exact-nearest producer manifests.
No missing source, sampled Common, partial NN reference, or absent after-coverage
comparison can produce a completed report.

All four populations are required for final reporting: full v1 Common TRAIN/VAL,
one million uniformly sampled same-X internally deduplicated PubChem molecules before v1/downstream decontamination or novelty selection, and complete first-batch
R/N streams of 1.25 million molecules each. Every feature row is matched against
an on-disk, independently pinned molecular membership index. Duplicate identities,
missing members, extra members and changed resume inputs are rejected. Common
identities are original molecule IDs, so distinct Common molecules with the same
InChIKey retain their molecular frequencies. PubChem/R/N use full identity keys.
The independent `baseline_report` stage completes task2.1 from only complete
Common + the one-million PubChem reference + their exact nearest-v1 results.
It does not wait for R/N conformer generation or augmented coverage. The full
`report` stage adds R/N and same-query before/after coverage for task2.9.

The fixed RDKit2025.09.5 functional-group set is recorded with every exact SMARTS,
unique-match setting, original definition CSV and Python source SHA. The same
set is evaluated in all groups. Existing descriptors are preserved; missing
Common descriptors may be additively completed using the original v1 compatibility
dispatcher after checking the exact graph identity and every already present
descriptor/fingerprint. No new screen decision or source molecule is substituted.

Features counted: elements and combinations, heavy atoms, molecular weight,
ring/aromatic-ring counts, generic ring systems, generic Murcko frequencies and
long tail, functional groups, stereocentres, logP, TPSA, HBD/HBA and rotatable
bonds. Disk-backed SQLite counters/member indices avoid loading millions of
scaffolds or the full PubChem pool in RAM. Bounded spawn workers enrich feature
batches; counters, member completion and moments are committed together. Closed
rows are reused on restart. Failed figure attempts remain separate.

Exact NN before/after comparisons must cover exactly the same one million
PubChem query identities, first against complete v1 Common, then against complete
v1 Common + R + N. A physically pinned complete producer must bind these query
and reference population manifests. Exact nearest similarity may not decrease
after adding reference molecules. Optional additional exact comparisons may be
included. Binned ECDF curves use explicit 0.001 Tanimoto bins and are labelled
as binned; the underlying nearest values come from exact search, never ANN.

Outputs include numeric CSV summaries, complete fixed-bin mass/ECDF CSV, complete
categorical Parquet counts, scaffold frequency spectra and long-tail statistics,
functional-group prevalence/match CSV, size/element nearest-coverage strata,
category frequency ratios, source/producer references and JSON summaries.
Headless Matplotlib generates standalone PDF and PNG figures plus a reproducible
Markdown report. Underrepresentation flags (absence or PubChem/v1 frequency ratio
at least two) are descriptive report annotations, not selection rules.

## Physical population manifest

```json
{
  "schema": "EXPANSION_DISTRIBUTION_POPULATION_V1",
  "status": "COMPLETE",
  "population": "v1_common",
  "population_scope": "FULL_DECLARED_POPULATION",
  "expected_molecules": "ACTUAL_INTEGER_NOT_PLACEHOLDER",
  "authority_reference": {"path":"...","bytes":123,"sha256":"..."},
  "authority_count_pointer": "/actual_final_common_count",
  "authority_kind": "FINAL_FULL_COMMON_MEMBERSHIP",
  "is_sample": false,
  "population_roles": ["TRAIN","VAL"],
  "membership": {"identity_column":"molecule_id","artifacts":[{"path":"...","bytes":123,"sha256":"...","format":"parquet","rows":123}]},
  "features": {"identity_column":"molecule_id","artifacts":[{"path":"...","bytes":123,"sha256":"...","format":"parquet","rows":123}]},
  "allow_additive_descriptor_completion": true
}
```

Artifact formats are Parquet or JSONL. `rows` refers to the entire physical file
before optional explicit `equals` and `maximum_stream_rank` source filters.
Membership and feature sources can have different identity column names but
must contain identical identity values. The PubChem sample additionally requires
`sampling={uniform:true,seed:<integer>,source_status:
"X_SCREENED_INTERNAL_FULLKEY_DEDUPLICATED"}` and `is_sample=true`, `baseline_pool_phase="BEFORE_V1_DOWNSTREAM_DECONTAMINATION_AND_NOVELTY"`, and physical `raw_chemical_screen_reference`/`internal_deduplicated_pool_reference` pins. Exact identity/self matches are retained and counted separately from Tanimoto=1 fingerprint matches.
PubChem/R/N use `full_key` as both membership and feature identity columns.
R/N manifests additionally bind their corresponding `stream` and
`selection_status="FINAL_FIRST_BATCH_FROM_RELEASED_DECONTAMINATED_ORDER"`.
Their complete first-batch identities must be disjoint. Common uses original
molecule IDs so that valid repeated molecular structures retain their frequency.

## Exact NN comparison manifest

```json
{
  "schema":"EXPANSION_EXACT_NEAREST_DISTRIBUTION_V1",
  "status":"COMPLETE",
  "comparison":"pubchem_to_v1",
  "query_population":"pubchem_1m",
  "query_population_manifest_reference":{"path":"...","bytes":123,"sha256":"..."},
  "reference_populations":["v1_common"],
  "reference_population_manifest_references":[{"path":"...","bytes":123,"sha256":"..."}],
  "expected_queries":1000000,
  "nearest_similarity_exact":true,
  "fingerprint_recipe":"ECFP4_2048_radius2_chiralityFalse_rdkit2025.09.5",
  "producer_evidence_reference":{"path":"...","bytes":123,"sha256":"..."},
  "results":{"identity_column":"full_key","artifacts":[{"path":"...","bytes":123,"sha256":"...","format":"parquet","rows":1000000}]},
  "value_column":"nearest_v1_tanimoto"
}
```

The producer evidence must contain actual `status=COMPLETE`,
`nearest_similarity_exact=true`, `queries=1000000`, and the identical query and
reference population manifest references. The augmented comparison is named
`pubchem_to_augmented`, with reference populations `[v1_common,R,N]` in that
order. A wrapper cannot turn an incomplete/sampled producer into this evidence.

## Root execution

The plan schema is `EXPANSION_DISTRIBUTION_PLAN_V1`. Supply `analysis_version`,
`output_directory`, actual `workers`, optional `batch_rows` (default1024),
`population_manifests` and `nearest_manifests` lists of pinned references,
plus actual `output_cap_bytes`, `minimum_free_bytes`, and
`other_future_reserved_bytes`. Scheduling and actual parent accounting remain
with Root; no jobs are submitted here, no arbitrary wall/repair limits exist.
Require Root's existing `quota_snapshot` and `quota_authority` for actual
account-quota and pre-query output-credit admission: `kind=lustre` selects
`completion_runtime_v1.lustre_quota.budget_check`, otherwise the original SHARE
quota helper. Whole-filesystem free space cannot substitute for account quota.
Supply reviewed `software_rss_budget_bytes` and `minimum_node_available_bytes`;
the monitor measures actual own process-tree RSS and node memory. CPU21 execution additionally requires the
actual `cpu21_authorization_reference` to the user-approved node21/all policy;
the real partition and parent identity are recorded without relabelling it cpu.

```sh
python -m workflows.expansion.distribution_report_v1 --plan PLAN --stage populations
python -m workflows.expansion.distribution_report_v1 --plan PLAN --stage nearest
python -m workflows.expansion.distribution_report_v1 --plan PLAN --stage baseline_report
python -m workflows.expansion.distribution_report_v1 --plan PLAN --stage report
python -m unittest workflows.expansion.distribution_report_v1.test_distribution
```

Stages can run separately as physical inputs become available. The final report
stage rejects incomplete input populations or exact coverage. Dependencies:
Python3.10+, PyArrow, RDKit2025.09.5, NumPy and Matplotlib. Execute source/data
work on an actual compute allocation, not a Windows interpreter or login node.
