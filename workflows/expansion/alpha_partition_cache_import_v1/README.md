# Same-Alpha exact score-cache import

This imports closed complete rescue6/7 results into the original low11 cache.
It does not change the original exact NN runtime, mathematical kernel, full
1,196,122 references, source209 pool or the final low11/high5 aggregate.

The production plan schema is `PUBCHEM_ALPHA_PARTITION_CACHE_IMPORT_PLAN_V1`.
It pins the actual original NN deployment, reference/filter, one `target` and
exactly two `sources`. Each actual upstream object has `runtime`,
`plan_reference`, `startup_proof_reference`, `accounting_reference`, `root`;
sources additionally pin `manifest_reference`. Sources must be native C0 and
SHARD_COMPLETE; the target and any explicitly declared additional import
writers must have all recorded native steps terminal. Original source/target
locks are held throughout the import. No new Root approval record is used.

Every source part is whole-SHA/footer/schema checked. Per-source MD5 scope,
unique FP mass, full-reference integer counters, original unreduced fraction,
F64 bits and the complete original ordinal/key map are validated. Incoming FP
membership is independently joined against original209 candidates. Overlap
must match all9 original fields and exact binary64 bits; matching old rows are
kept once, and only the anti-join is physically copied. Old bindings/journals/
Parquet are not rewritten; global exact300GB/all-future200GB protections remain.

Plan/startup/native metadata, original/derived five-field bindings, all source
and old journals, closed part files, the full key map and candidate files remain
frame checked. Failed imports can leave valid new closed parts; they are retained
and must be included in a subsequent terminal-writer audit and exact overlap
check. A completed low11 manifest is never modified. Rescues are never supplied
as third/fourth final aggregate manifests.

`test_checks.py` exercises corruption, duplicate/scope/key rejection, float32
rejection and equal-value/different-unreduced-counter rejection. The bounded
Main20 `native_fixture.py` consumes explicit byte-identical copies of4096 actual
Alpha267 score rows and the complete original1,196,122 key map. It verifies a
controlled1024-row overlap, retains3072 new rows and rejects a changed native
counter even when the reference sum remains valid. It neither recalculates NN
nor certifies a full rescue/import. Actual production import still requires all
terminal provenance and complete DATA checks above.

Production is invoked through the ordinary immutable Alpha entry and launcher:

```sh
python -I -B ENTRY workflows.expansion.alpha_partition_cache_import_v1.run \
  --plan ACTUAL_PLAN.json --startup-proof ACTUAL_STARTUP.json
```

The coordinator must prepare the held importer/new-low allocations and retarget
only unstarted rank/consumer dependencies before stopping the old low writer.
After actual import C0, resume the original low scope from its retained cache,
with this import manifest and all original Main245 lineage pinned. No running
writer is changed merely by deploying this module.