# B normalization profile source draft

Status: `SOURCE_DRAFT_NOT_READY_A_FULL_ACTUAL_PENDING`. The earlier interface
design is now implemented by four new draft files in
`workflows/expansion/secondary_coconut_identity_norm_profile_v1/`:
`__init__.py`, `contracts.py`, `runtime.py`, `run.py`. None has been executed,
AST-checked, tested or submitted. Existing A/identity/feature/queue sources
are unchanged. A profile1884770's actual C0 and318s do not satisfy A full
acceptance; its projected identity scope exercised only collection_molecule.
A full1884772 was running at this source handoff. No future result is assumed.

## Exact input/startup contract

Alpha deploys the new package as `Alpha/code/secondary_coconut_identity_norm_profile_v1`.
The proposed separate exact adapter must use:

```text
ALPHA_PY -B -m secondary_coconut_identity_norm_profile_v1.run --plan ABS_PLAN --startup-proof ABS_PROOF
```

Producer/scope key `coconut_identity_norm_profile_alpha_v1`; plan/proof schemas
`SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_PLAN_V1` /
`SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_STARTUP_V1`; stage
`IDENTITY_KEY_NORMALIZATION_PROFILE`; modeprofile/kindanalysis/pilottrue only.
`scope_parameters=contracts.parameters(actual_python_version)` exactly, and
`sampler_python_version` must equal the real full Python version. CPU16,
no requested memory/exclusive/GPU, wall<=4h whole minutes, output2GiB including
all partials, Parquet, journal and metadata; those are ceilings, not forecasts.
Root must add/review an exact known protocol in its thin adapter. There is no
READY materializer, new queue, implicit scope reuse or B full mode here.

The independent fresh<=120s Alpha UID1264/current job/node/boot/actual primary/
full argv/exec-gate PID identity is mandatory. Source set equals the exact Root
review's approved sources, with all actual imported files pinned. The proof
requires `bounded_readonly_scope_only=true`; acquisition scope is false.
The exact stage review uses `EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1` /
`APPROVED_FOR_EXACT_STAGE` / reviewerroot, and additionally
`actual_A_full_cost_and_identity_projection_reviewed=true`.

Required small parent fields, all real existing Alpha triples, are:

- `a_full_receipt_reference`: actual full receipt with complete EOF, current
  SQL SHA,15 DDL tables, raw/projected row conservation and no status filter;
- `a_full_accounting_reference`: actual Alpha C0 UID1264 CPU16 parent and exact
  raw sacct/cost; that document's `raw_sacct_reference` is also a parent pin;
- `a_full_plan_reference`, `a_full_startup_proof_reference`: exact refs stored
  inside that actual receipt, not rewritten Main paths;
- unchanged A four kernel sources in source_references, plus actual Alpha base
  common/gate/probe/adapter, B sources, source-dependency package files,
  `resource_authority_reference`, `cost_decision_reference` and exact environment.

`data_references` is exactly the two actual A `physical_output_references`
named `molecules.raw_identity.parquet` then `entries.raw_identity.parquet`.
No SQL/CSV/SQLite/coordinates/properties body is opened by B. N comes from
actual A full `inventory.reconciliation.projected_rows_by_table` and is checked
against each actual Parquet footer/schema. Root login only binds these large
locators. CPU independently hashes both files, requires UID1264/regular/no
symlink, and verifies current frame before/after hashing and selected reads.

## Unchanged normalization helpers

Deploy original files at `Alpha/code/workflows/expansion/...`, preserving their
module layout and direct function objects. Exact immutable references:

| Relative source | Bytes | SHA256 |
| --- | ---: | --- |
| identity_v2/projection_v2.py | 8616 | `7da54ccb4488950fb567c17cfa161bc339d8a377f2e2fb27362434ce88516d28` |
| common.py | 4312 | `8c988f617776ad05354deae1cf69933e7ff95210f7a2609f903e4826172ccbad` |

Plan `frozen_identity_source_references={projection:TRIPLE,common:TRIPLE}` must
point to those actual Alpha copies. All transitive imported package files and
`identity_v2/readers_v2.py` also belong to approved small source pins. Main and
each worker verify actual module locations/full bytes and call the original
`full_keys(strict=False)`, `source_smiles_keys`, `rdkit_identity_modules` and
`wp5_key`. This is a direct-file/function-object proof, not a false claim that
the new coordinator AST equals the old identity functions. RDKit must report
exactly2025.09.5. No old helper file is edited or monkey-patched.

For molecules, derive from canonical_smiles and retain standard_inchi_key and
raw InChI. For entries, independently derive from all original canonical,
standardized_canonical and parent_canonical SMILES. Preserve raw JSON and all
IDs/state/invalid/active/links. Missing or invalid variants remain separate
observations; a usable stored key and unresolved SMILES may coexist. Compute
the conservative union of valid source and derived full keys and original
`full_key[:14]+':'+full_key[-1]` WP5 keys. No X exclusions, scaffold/features,
MolFromInchi, neutralization, tautomer/stereo/isotope editing or status filtering.
No descriptor/target is read or used for ordering.

## Sampling, boundaries and observations

Two independent uniform samples, each min(10000,N), use zero-based Parquet
physical ordinals without replacement. Table-domain seed is integer SHA256 of
`20261026|TABLE`, then the frozen Python `random.Random(seed).sample` algorithm;
the exact selected ordinal lists are saved before dispatch. At most32 pending
tasks,16 worker processes. Completion requires16 distinct nonempty worker PIDs
and exact selected/written/physical-key/Parquet row conservation; process count
is measured rather than inferred from allocated CPUs.

Read only selected rowgroups, after full source SHA. Rowgroup uncompressed
metadata must be<=256MiB. A selected raw JSON is<=2MiB and result<=8MiB; these
are container/IPC budgets, not RDKit heap proofs. A too-wide record stops the
profile with its original locator retained; it is not truncated, resampled,
chemically excluded or omitted from a claimed complete sample.

Completed result JSONL is flushed/fsynced before aggregation, alongside fresh
Parquet containing complete per-row/per-variant observations. Current actual
parent+owned worker RSS, MemAvailable, whole output, source SHA/frames and hard
wall remain guarded; first current sample precedes source body reads. Runtime
STOP prevents new dispatch and drains active work without signals. A sample
latency>2s is lag metadata, not evidence of memory shortage. Invalid readings
remain STOP. Reserve768MiB+32MiB for pending32 plus buffered16 bounded results;
include actual scratch/metadata in output cap. Quota retains all caps+200GB.
User-authorized cost overruns report and continue; no quality threshold changes.

Three new guarded fixtures test valid/invalid source keys and WP5 suffix,
inactive/invalid/orphan/null preservation, and direct-helper conservative union
of multiple SMILES variants. They have not run. Receipt schema
`SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_RECEIPT_V1`, complete status
`SAMPLED_FROZEN_IDENTITY_KEY_OBSERVATIONS_COMPLETE`; otherwise
`INCOMPLETE_IDENTITY_PROFILE_UNKNOWNS_PRESERVED`. Preserve source-hash/footer
phase CPU/time, each table's read/dispatch/write elapsed, summed worker key
CPU/wall, initialization proofs, actual current RSS/output and later actual
parent allocated cost. Sum of worker wall is not parent wall.

A's complete table/status/orphan facts and all other original output refs are
retained unchanged in the receipt. Profile sample missing/conflicting identities
are reported, not repaired or converted to exclusions. Even C0 would not prove
B full/all-COCONUT identity acceptance, global all-source decontamination,
released pool, novelty, UFF/QM or training. A/B full authorization requires
independent actual evidence and Root review.
