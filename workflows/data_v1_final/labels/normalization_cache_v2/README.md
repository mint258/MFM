# Minimal base-metadata binding repair after actual1915

This source is unexecuted at handoff. Failed Main4521915 remains FAILED1/36s,
16CPU15; its six old fixtures actually passed. All v1 source, raw inputs,
outputs and accounting remain immutable. No math, mask, dtype, ordered leaf,
native geometry or numerical tolerance changes.

The actual traceback reaches profile.py:68 base_metadata(template), which
selected the entire provenance and decoded it with an empty F64pool. The actual
prepared owner plan base-file reference contains seconds=1.4602348357439041.
The frozen cache producer copied the whole source reference into provenance;
projection.encode appends a unique pool slot for every float occurrence. Thus
seconds was a legitimate F64reference. This failure is not index reuse or data
corruption, and the old uniqueness/bounds predicate must not be weakened.

Only the base projection changes: it selects exactly
provenance.owner.record_ordinal, original_geometry.atomic_numbers,
native_atom_order_sha256, source_payload_sha256 and geometry_status. These are
the fields actually consumed by the unchanged profile kernel. It does not
select source_reference/seconds/unused owner metadata or positions_A, and still
passes an empty pool to the unchanged v1 projected_decode. Unexpected F64in a
required field still HOLDs. Nothing is replaced by zero and XYZ is never read.
Task-cell recovery, pointer validation, mask regeneration, radix/TSQR math and
comparison remain direct frozen function bindings.

profile.py is byte-identical to v1. The new reader exports v1 function objects
unchanged except base_metadata. run.py changes only scope key and fixture
binding/count/timing label; metadata changes namespace/source binding and adds
explicit historical failure/old-fixture pins. verify_port.py is a Root-only
stdlib inverse-bytes/AST proof; the child does not run it.

Three new pure boundaries run before real body reading in the actual new
allocation, replacing repetition of the already passed old6:

1. Real-shape seconds/unused-owner-float/XYZ tags reproduce v1 failure; v2
   returns only the five needed fields with no pool and mutates no original bits.
2. F64or absent required metadata still HOLDs; there is no fallback into XYZ.
3. The frozen duplicate/out-of-range index rejection and ordered type/bit
   behavior remain unchanged.

Run the Root-installed metadata helper with all original v1 arguments and:

```text
PY -B -m workflows.data_v1_final.labels.normalization_cache_v2.materialize
  --cache-manifest ACTUAL512 --cache-proof ACTUAL --cache-accounting ACTUAL
  --cache-raw ACTUAL --legacy-profile ACTUAL_PROFILE_V2
  --resource-authority CURRENT --metadata-directory NEW --output NEW
  --prior-failed-proof ACTUAL1915_PROOF
  --prior-failed-accounting control/accounting/train_cache512_r0_failed_4521915_v1.json
  --prior-fixture-gate artifacts/labels/source_status_v1/source_train_cache_profile512_r0_v1/fixture_gate.json
  --approve --reason ROOT_NEW_EXECUTION_BINDING_REVIEW
```

CLI values must be actual absolute Main paths. parents.py checks the historical
FAILED1915 raw accounting/request/output binding, old six-fixture PASS and the
exact failure summary. This is historical evidence only. The C0 dependency
remains actual cache4521610; no afterok dependency is assigned to failed1915.
Fresh v2 admission/proof/source pins are still required for the new job.

```text
PY -B -m workflows.data_v1_final.labels.normalization_cache_v2.verify_port --output NEW_PROOF
PY -B -m workflows.data_v1_final.labels.normalization_cache_v2.run
  --config NEW_CONFIG --startup-proof FRESH_CENTRAL_V2_PROOF --output NEW
```

Scope key is source_train_typed_cache_512_profile_v2. Configuration/resource
schemas,16CPU/no_mem/2h/4GiB, immutable48input locators, exact4251records,
512molecules,16groups and all original quality gates remain unchanged. No
normalization or final mask acceptance is authorized. Source TRAIN512statistics
stay provisional; all-source/Common/Pprime/R1 restrictions from v1 still apply.
