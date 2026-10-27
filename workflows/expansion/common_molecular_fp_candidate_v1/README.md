# Common structural-feature producer: source-only candidate

This package fills the missing producer interface for the existing exact ECFP4
reference consumer. **It has no executable science entry point.** The only CLI
reads small metadata and emits `NONEXECUTABLE_CANDIDATE`, including an explicit
list of missing final parents and future CPU-port checks. It never emits a
`COMPLETE` reference/projection manifest, submits a job or accepts a pool.

The existing `screen.py`, compatibility dispatch, exact nearest-neighbour math,
ranking and external-sort sources are unchanged. Nothing here asserts that a
Common population, 1M baseline, NN calculation or figure has actually completed.

## Proven original graph semantics

`source_evidence_v1.json` records actual bytes/SHA and exact line clauses from
Root's Source26 read-only source cache. These are source observations, not
current DATA SHA observations or an execution approval.

The original creator is
`legacy/descriptor/dataset/rdkit_descriptor_generator.py`:

1. Read `data.smiles`; require nonempty text and apply `.strip()`.
2. Parse that string with `Chem.MolFromSmiles` as `template`.
3. Write `canonical_smiles` using `canonical=True, isomericSmiles=False`.
4. Write `isomeric_smiles` from the same template with `isomericSmiles=True`.

The inventory carries all three fields into the rebuild. WP1 separately creates
`reidentified_smiles`/`reidentified_inchikey` from geometry. WP5 retains the source
and geometry identities, full-key variants and accepted-difference QC flags.
It checks the permitted backbone/protonation relation and does **not** require
every full key to equal a single newly derived key. In particular,
`QC_key_reproduction_mismatch_accepted_difference` and
`QC_other_layer_accepted_difference` are explicit retained evidence.

The candidate selector therefore proposes the original creator's
`smiles.strip()` graph entrance, subject to an independent Root semantic review.
It does not select `canonical_smiles` by its name, substitute the geometry graph,
or silently drop stereo. All original fields and accepted differences remain in
the rich source events. A derived key need not equal every historical key.

## Exact input boundary and final parents

The actual finalizer contract is
`formal_cpu_auto_finalize_mapping_v2/finalize.py`:

- A genuinely completed `COMMON_POPULATION_V1_FROZEN` manifest, `pilot_only=false`.
- Its 16 `membership_tables`, whole-file producer triples, and actual final
  `roles` molecular/PM7-record counts for TRAIN and ROUTINE-derived VAL.
- Only rows whose actual `common_population` is true enter this producer.
  Membership comes from the finalizer; this producer never reconstructs it from
  UFF successes or graph availability. Non-Common evidence is retained upstream.
- `formal_population_authority_receipt` closes the original canonical record
  source. The original receipt's one `outputs[name=formal_population].reference`
  identifies `formal_record_index.parquet`; the final manifest must name that
  same receipt, or an independently reviewed relocation port is needed.
- Actual finalizer/accounting/role authority and all canonical source parents
  must be independently validated in the future execution port. Historical
  footer metadata alone does not prove a current whole-file SHA or terminal job.

The known historical footer reports 11,231,854 physical records, 86 row groups
and a 1,242,386,629-byte formal Parquet file. Those numbers are schema evidence,
not this package's actual scan results. Required column names are literal in
`contracts.py`; no `CID`, `full_key` or `WP5_key` alias is invented. CID is null
when the original authority supplies none. Derived full/WP5 keys are additional
fields alongside original stored/reidentified/WP5 values.

Only the identity allowlist is projected from the formal source. Source labels,
energies, descriptors, task payloads and downstream values never enter scoring.
The full canonical parent ref preserves the rest of the original evidence.

## Candidate science and reduction

`worker.load_kernel()` loads the existing
`features_legacy_compatible_v2.features_candidate` function object and its
existing source-scope proof. Successful legacy outputs stay legacy outputs. The
only fallback remains the already isolated exact old ring-Kekulize site; this
package adds no repair, filtering, normalization or feature implementation.

The call uses `cid=None`, the original creator's source text, and a provenance
ordinal. X01–X05 reasons or exceptions become unresolved feature evidence for
the already accepted Common MID. They do not remove it or become a new chemical
exclusion. The rich DATA must retain all physical source records, original graph
spellings, key variants, QC flags, derived graph/keys/features and errors.

`producer.produce_mid` is a library seam, not an admission gate or launcher. It
requires a durable append sink. It appends all source evidence before computing
any variant, appends each result before molecular reduction, and preserves all
variants in the reduction. The future port must provide a real fsync/readback
writer and budget. Reviewed finite per-MID variant-memory limits cause HOLD with
the already written source evidence; they never exclude or truncate a molecule.

`projection.reduce_variants` emits a candidate strict row only if all observed
source variants resolve to **one** canonical isomeric graph/full-key pair and all
derived molecular features agree. Different spellings of the same graph may
coincide. Multiple legitimate graph/key variants, unresolved variants or feature
disagreement preserve all rich results and produce HOLD. There is no first-row
choice, key voting, source-SMILES-to-geometry substitution or bitwise-OR FP.

The old consumer's exact five fields are:

```
molecule_id, full_key, ecfp4_2048_hex, generic_murcko, generic_ring_systems
```

ECFP4 remains radius 2, 2048 bits, `includeChirality=False`, RDKit 2025.09.5,
using the original serialized 256 bytes / 512 hex characters. Chirality-disabled
FP is the existing feature recipe; it does not authorize identity stereo loss.
An acyclic Murcko key stays the original empty string. Native ring-system lists
are preserved, including duplicate entries; unchanged `nearest_exact` counts
`sorted(set(...))` once per MID. Different MIDs sharing one full key remain
separate molecules and therefore each contribute one molecular frequency.

`census.Census` consumes globally sorted unique MIDs with role and expected
native-record counts. It computes a length-prefixed sorted MID/role digest and
both molecular and physical-record counts by role. The future port must compare
the all-16-parts source census, formal join census, rich reduction census and
strict projection census exactly. Count equality alone is insufficient. Any
HOLD prevents the entire strict Common reference from being declared complete;
successful-only subsets cannot masquerade as final Common.

## Small-metadata-only CLI

Root may run this standard-library helper in its approved metadata context:

```
python -m workflows.expansion.common_molecular_fp_candidate_v1.materialize \
  --request /absolute/path/to/actual_candidate_request.json \
  --output-directory /absolute/fresh/path/to/common_fp_candidate
```

Request schema is `COMMON_MOLECULAR_FP_CANDIDATE_REQUEST_V1` and
`requested_scope` must be `FINAL_COMMON_TRAIN_VAL_ONLY`. Required actual source
inputs are `source_evidence_reference` and four `scientific_kernel_references`
in the order `contracts.KERNEL_PATHS`. All are real small triples; the helper
verifies their current small bytes. It does not hash any DATA.

These parent references can explicitly be null while still absent:

```
common_population_manifest_reference
canonical_authority_receipt_reference
graph_selection_review_reference
final_parent_accounting_reference
origin_relocation_review_reference
```

Present small refs are verified and loaded; manifest-supplied membership/formal
DATA refs are structurally validated and copied as locators, never opened. DATA
has a separate positive-integer/64-hex triple validator without the small-file
size cap. The helper never creates or signs a Root review, body SHA, job ID,
PASS, complete source census or anticipated future producer ref.

A supplied graph semantic review must be an actual independent small object
with schema `COMMON_SOURCE_GRAPH_SELECTION_REVIEW_V1`, status
`ROOT_REVIEWED_SOURCE_ONLY`, `selected_source_field="smiles"`, and true fields
`original_creator_strip_then_parse`,
`canonical_smiles_nonisomeric_not_full_graph`,
`accepted_historical_key_differences_preserved`, and
`multiple_graphs_hold_without_representative`. This is a source-semantic review;
it never enables execution in this package.

## Explicit remaining execution work

Only after Root supplies the genuine final Common parents and accepts the graph
semantics should a separate thin executable port be created. It must:

- Apply existing fresh central admission/full argv/source/resource/accounting
  rules in the selected cluster; no historical 64-GiB or Main-UID guard reuse.
- Run the three synthetic methods before opening DATA or creating a monitor.
- Full-SHA/stable-FD verify every closed DATA pin in that allocation; verify the
  complete final-role/canonical-source parent relation and all required columns.
- Stream Arrow/DuckDB identity projections and external MID order, with no
  11M-record Python collection. Use 16 workers and at most 32 pending tasks.
- Provide actual RSS/MemAvailable/current quota+registered-cap observations,
  200-GB effective reserve, finite Root-reviewed wall/output caps and natural
  drain. Actual cost includes failures/startup; overruns report and continue
  without changing quality gates. Science outputs use stable files, avoiding
  disposable SQLite-journal stat races.
- Durably write source and result events before derived Parquet/statistics,
  retain partials/HOLD, then full-SHA/read back every output and exact MID census.
- On Alpha preserve Main UID/endpoint/origin refs intact, pin an explicit
  origin-to-current relocation map, verify same bytes/SHA in the new allocation
  and use Alpha UID1264/current scope7 gates. Never rewrite Main JSON paths and
  call it the same source bytes, or claim Main execution occurred on Alpha.

The existing exact reference writer's IO/quota adapter also needs its own thin
cluster port; its packing/frequency/nearest math must stay unchanged. No new NN
engine is needed. Formal baseline1M must receive a separate actual PubChem
"same screening rules" authority from Root. It is not silently the R/N
decontaminated domain, a sampled Common query or a successful-only partial pool.
Existing exact-query finite comparison caps cannot be silently bypassed for 1M.

After actual complete references, permissible per-MID summaries/figures include
heavy atoms, MW, elements/composition, rings/aromatic rings, rotatable bonds,
HBD/HBA, TPSA, logP, stereo/isotope counts, Murcko/ring coverage and exact nearest
Tanimoto distributions. Unknowns remain denominators/evidence. This package
produces no such statistics or figures and makes no orders/P′/identity/Pool/D4
quality release. The original P′ failures and all scientific HOLDs remain.

## Synthetic verification, not executed by SB4

Exactly three `unittest` methods are provided in `test_boundaries.py`:

1. Creator field selection retains stereo and historical accepted key differences.
2. Legitimate multiple graphs and unresolved variants are retained with HOLD.
3. Exact MID/role census, strict5, acyclic/ring values and large-DATA/small-metadata
   reference separation remain intact.

Root may run these in an actual approved CPU allocation before any science port.
SB4 performed no Python/AST/test execution, DATA read/hash, SSH, Slurm or Git.
