# Per-row structural evidence audit of the original735

This allocated metadata-only diagnostic consumes the complete cached1885150
observations (735 rows, 8085 supplied representation fields), actual primary1885152
observations and ontology witnesses, and Root's already prepared exact3 source
review. It does not run RDKit, make network calls, reread the 38 GB SQL, generate
keys, adopt bounds, filter candidates, quarantine rows or change scientific scope.
The user has not approved a source-scope change. The audit makes the existing
proposal inspectable; it is not another approval layer or an all735/all11 release.

The four mutually exclusive partitions describe supplied evidence:

* `FINITE_EXACT_SOURCE_RECOVERED_PROPOSAL`: the three source-bound exact formula
  proposals, preserving complete-field witnesses and stereo/technical-grade caveats.
* `OFFICIAL_ONTOLOGY_CLASSIFICATION_WITNESS`: the three existing official ChEBI
  classification witnesses, without substituting a finite representative molecule.
* `SUPPLIED_REPRESENTATIONS_UNDERSPECIFIED_QUERY_DUMMY_OR_VARIABLE`: explicit
  query/dummy/query-bond or query/repeat metadata in supplied representations,
  with no fixed-atom composition candidate taking priority.
* `INSUFFICIENT_EVIDENCE`: all other cases, including fixed-atom composition
  candidates awaiting source-association/metadata review. Missing keys alone do
  not imply an abstract class or a nonexistent real-world molecule.

Per-variant records include source field pointer/hash, complete indexed atom-table
checks, actual atomic-number/query/dummy/bond-query flags, query descriptions,
original producer composition observations and diagnostic reasons. A fixed atom
table with only query bonds remains a potential exact **element composition**
candidate; graph/bond/charge/stereo identity remains unknown. Query atoms with
positive `GetAtomicNum` are not assumed fixed elements. Empty non-H vectors from
real H-only atom tables are retained. Conflicting candidate vectors remain visible.

The original native735 JSON is decoded using the unchanged cached extractor.
All eleven cached field hashes/pointers and original physical records are checked
against it. Whole cached MOL text is scanned only for lexical query/repeat/group
metadata. General group annotations alone are not proof of variable composition:
they are reported as requiring interpretation, not automatically promoted to the
underspecified partition. Such metadata blocks an unqualified composition
candidate while retaining the fixed atom-count observation for review. Primary3
raw text is not re-extracted here; its existing exact source review and complete
field pins are retained, and that lexical limitation is explicit in each variant.
Variants are not merged into an identical graph by field names or equal MOL text.

Each output row binds original `entries:<id>:<block>:<ordinal>`, physical locator,
original SQL row hash, opaque body reference, cached DATA line offset/hash, native
record reference, variants, finite/ontology witnesses and its diagnostic partition.
The original opaque bodies are not rehashed again: authority is the closed native
and cached C0 producers. No complete MOL bodies are embedded in this source code
or committed to Git. The new private DATA is a provenance audit, not strict5.

Root supplies the standard Alpha runtime/profile/quota/Guard resource fields and
code references for this package plus **all Python files** in the imported
`coconut_alpha_cached735_v1` package and the current runtime. Root-reviewed worker
count is16; resource budgets come from the current concurrent-stage plan.

Additional plan fields (all references are actual machine `{path,bytes,sha256}`):

```text
schema = COCONUT_ALPHA_STRUCTURAL_AUDIT_PLAN_V1
scope_key = coconut_alpha_structural_audit_v1
cached735_receipt_reference = A/artifacts/pubchem_native735_fields_20261103/cached_job_1885150/receipt.json
cached735_actual_parent_reference = A/control/pubchem_expansion_runtime_20261103/cached735_actual_accounting_for_primary.json
primary3_receipt_reference = A/artifacts/pubchem_native735_fields_20261103/primary3_node_v1_job_1885152/receipt.json
primary3_actual_parent_reference = A/control/pubchem_expansion_runtime_20261103/primary3_root_actual_parent.json
exact3_source_review_reference = A/control/pubchem_expansion_runtime_20261103/primary3_exact_source_review_v1/root_source_review.PROPOSED.json
```

`A` is `/gfshome/alpha/codex_data_v1_20261026`. The original native1885146 receipt,
actual accounting, native DATA and plan are resolved from the closed cached plan.
The primary3 receipt resolves its existing ontology and upstream observation files.
The exact3 review resolves the proposed strict5 rows; none are applied here.

Use the existing node launcher unchanged, in the actual clean base cwd:

```text
PY -I -B NEW_ENTRY workflows.expansion.alpha_runtime_v1.node_launcher --template ACTUAL_TEMPLATE --base-root ACTUAL_CLEAN_BASE --entry NEW_ENTRY --module workflows.expansion.coconut_alpha_structural_audit_v1.run --tag structural735_v1 --control-root A/control/pubchem_expansion_runtime_20261103/node_epochs --gluster-rpc-program ACTUAL_READONLY_RPC
```

The module consumes `--plan PATH --startup-proof PATH`, calls the shared
`profile.admit(plan, minimum_workers=16)` and `Guard`, and runs one meaningful
stdlib classification-boundary fixture before the full audit. That fixture covers
missing keys with fixed atoms/query bonds, dummy atoms, ambiguous query atoms,
uninterpreted group metadata and inconsistent atom tables. It is also directly
runnable as `NEW_ENTRY workflows.expansion.coconut_alpha_structural_audit_v1.test_source -v`.

Private outputs: `source_tests.json`, `structural_evidence735.DATA.jsonl` (735
rows), and producer `receipt.json` with complete partition/variant counters and
the fixed-atom candidate review list. Actual parent C0 remains pending Root's
ordinary accounting readback. No source is dropped and no pending user answer
is inferred from this diagnostic.
