# Alpha far-tail FP-only exact-rescue export

Root alone deploys/submits. This independent producer reads only complete209
candidate Parquet inputs and the small original196 reference manifest. It never
reads active201/232/233 SQL, modifies existing NN code/output or calls RDKit/NN.
The export is a work parcel, never a narrowed replacement for full-pool science.

CLI through the existing isolated native entry:

```text
PY -I -B ENTRY workflows.expansion.main_exact_rescue_queries_v1.run --plan ACTUAL_PLAN --startup-proof ACTUAL_PROOF
```

Plan schema `ALPHA_EXACT_FP_RESCUE_EXPORT_PLAN_V1` adds:

- `expected_parent_job_id="1885232"`; actual numeric SLURM_STEP_ID is required;
- `source_filter_reference`: exact original COMPLETE209 manifest;
- `reference_manifest_reference`: exact original COMPLETE196/full1196122 manifest;
- `md5_hex_text_prefixes=["8","9","a","e","f"]` in that exact order;
- `duckdb_threads=4` or8, `workers=16` for the real overlap allocation;
- `parent_rss_cap_bytes=software_rss_budget_bytes=48GiB`,
  `minimum_node_available_bytes>=24GiB`, positive `sql_memory_bytes<48GiB`,
  spill allowance within `output_cap_bytes<=30e9` including all output/spill;
- optional `rows_per_part<=200000` (default200000), max single file256MiB;
- existing actual Alpha runtime_profile_reference/endpoint/uid, clean cwd,
  startup/source refs, quota authority/current future-budget/resource fields;
- `excluded_active_allocations` includes201/232/233 native runtime/plan/startup
  identities. Only their small plans are read to exclude their output trees.
  Root prepares the ordinary real native-block budget, crediting only actual
  C0 closed209 and the existing v3 baseline; active NN is never credited.

No new approval file/schema is needed. Root's intended execution is an actual
short srun overlap step in232's32CPU allocation,16 requested step CPUs, only4/8
DuckDB threads. The48GiB private own-process budget is a subset of the existing
160GiB parent allowance, not a Slurm memory reservation or a claim that sibling
NN memory is measured by this producer. Actual shared-node reserve/quota checks
remain active. Root controls total allocation concurrency and global exact300GB.

Every original part SHA/footer/rows/FP type is checked. The actual entire
105670833 source rows are counted, including512lowerhex/physical-first-nibble
validation. Only ecfp4_2048_hex is projected into SQL. Selection uses
`substr(md5(ecfp4_2048_hex),1,1)` on the canonical lowercase hex **text**, not raw
bytes. One GROUP BY/sort per physical bucket computes unique selected FPs and
selected original-candidate multiplicities in one MD5 scan. No CID/labels/graph
or downstream information is exported. Original eligible molecule identities
are unaffected; repeated FPs are intentionally one exact-search work item.

Each physical bucket is strictly sorted/unique across bounded200k-row single
string-column Parquet parts. Raw-FP first-character domains are disjoint, proving
global FP uniqueness without an all-data Python set. Each part is whole-SHA/
frame/footer checked and recorded in external `parts_catalog.jsonl` as a flat
`{path,bytes,sha256,rows,physical_fp_bucket}` line, plus the closed-files journal.
Inputs also have an external catalog; no multi-MiB inline source/part list.

Final manifest `ALPHA_EXACT_FP_RESCUE_EXPORT_V1`/COMPLETE contains endpointAlpha/
UID1264, actual parent232 **and numeric step_id**, source_filter_reference209,
reference_manifest_reference196, prefixes, input/selected candidate-row counts,
`distinct_fingerprints`,16-key integer `per_bucket_counts`, `part_count`,
`parts_catalog_reference` and no inline `parts`. Per-bucket source/selected MID
row counts are separate from unique FP counts. Native parent/step C0 is never
self-certified: actual.parent_completion_claimed and step_completion_claimed
are false; Root later binds the real step accounting. Original Alpha paths/
metadata remain original in Main transport; Main UID1278 has separate replicas.

This content manifest is sufficient for the sibling main_exact_rescue_v1 input
contract, not a production adoption or original Alpha parent-C0 claim. Partial
outputs/logs remain on failure. No wall timeout/retry/fill or scientific change.

One tiny real DuckDB/PyArrow fixture uses threads1 and checks MD5 text selection,
duplicates/multiplicity, sorting across parts, single-column output and invalid
FP rejection. It performs no Native NN or full source computation:

```sh
python -m unittest workflows.expansion.main_exact_rescue_queries_v1.test_native_sql -v
```
