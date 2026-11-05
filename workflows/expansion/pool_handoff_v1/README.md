# Reconstructed PubChem pool handoffs

This independent component consumes the full original124,857,440-row/500-shard
RAW reconstruction. It does not call the old Alpha502 prepare/project entrypoint
or rerun chemistry. `merge` invokes the existing bulk_v2 materialize function;
only its runtime resource callback is adapted. Full positive-CID aliases, exact
minimum-CID/full-InChIKey deduplication and original typed/F64/JSON values remain.

`baseline` selects exactly1,000,000 unique full identities from that complete
screened/internal-deduplicated pool BEFORE any v1/downstream exclusion or novelty.
It orders by existing stable_hash('PubChem-baseline-uniform',20261025,full_key),
then full_key/cid. The fixed sample is distinct from R/N queues and unchanged for
exact before/after coverage. Sample membership and full typed features are saved
as Parquet with sample_ordinal0..999999. Graph-only QUERY_FIELDS JSONL is emitted
in that same sample_ordinal order; no scientific cost-pilot
or decontaminated-query label is assigned to this reference sample.

`filter` uses a native external SQL projection of the unchanged original full-key,
WP5 and exact-composition exclusions plus V3 source-bound positive atom lower
bounds. The original consumer functions remain unchanged; native fixtures compare
every actual hit to coconut735_recovery_v1.consumer.contamination and preserve
exact cutoff behavior. Complete candidate vectors must remain canonical, positive,
unique/sorted and in the frozen X02 domain. No approximate or substructure veto
replaces these rules. All hits and original typed eligible rows are preserved.

Production filtering requires a COMPLETE all11 V3 index and an independent Root
actual-C0 acceptance. MoleculeNet21 acceptance alone and ready9 do not close this
gate; COCONUT735 cannot become READY without accepted source coverage. The required
Root acceptance schema is PUBCHEM_ALL11_EXCLUSION_INDEX_ACTUAL_ACCEPTANCE_V1 with
status APPROVED_COMPLETE_ALL11_INDEX, reviewer=root, exact index_receipt triple,
all_sources_all_splits_verified=true, original_graph_unknowns_retained=true,
actual_parent (JobIDRaw,State=COMPLETED,ExitCode=0:0) and an independently pinned
actual_accounting_reference whose actual_parents list includes that parent. The
index producer_parent_binding.job_id must match it. Its exact source manifest and
closed SQLite database are pinned/read; active SQLite sidecars reject admission.
Root must supply the original full-v1 selection regression acceptance too.

`query_projection` emits schema
EXPANSION_TYPED_DECONTAMINATED_QUERY_PROJECTION_V1 from the complete actual
filtered Parquet, with full QUERY_FIELDS JSONL and exact filtered_pool_receipt
binding. It does not fabricate a legacy SQLite `database` field. The downstream
exact/rank adapter must use the explicit typed schema and physical identity joins.

All stage directories are PRIVATE children of the SAME aggregate scope
/lfshome/zixiao/pubchem_completion_20261103/raw_reconstruction. The shared550GB cap
includes RAW typed output, merge/filter/baseline, spill and every retained partial;
it is not550GB per stage. Other future reservations950GB and minimum free200GB
remain applied. Actual Lustre quota authority, own process-tree RSS and node
MemAvailable are observed by the existing reconstruction RuntimeGuard. SQL is
interrupted only on this process's actual resource stop, without process signals.
Source bodies are whole-SHA admitted once and immutable frames checked at closure.
No arbitrary wall/repair limit or scheduler submission is implemented.

Stage request JSON files explicitly remain PENDING_ACTUAL_CLOSED_INPUTS. Root
prepares a plan only after the listed actual receipts exist:

```sh
python -B -m workflows.expansion.pool_handoff_v1.prepare --request REQUEST \
  --source source_pool_receipt=/actual/closed/minCID/receipt.json --plan PLAN
python -B -m workflows.expansion.pool_handoff_v1 --plan PLAN
python -B -m unittest workflows.expansion.pool_handoff_v1.test_handoff
```

Required source roles: merge(raw_projection_manifest); baseline(source_pool_receipt);
filter(source_pool_receipt,exclusion_index_receipt,root_index_acceptance_reference,
regression_reference); query_projection(filtered_pool_receipt). Preparation reads
small receipt/source metadata only. Actual data admission and all computation run
in a Root-approved compute allocation. No production work is run by these fixtures.
