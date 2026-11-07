# Full source recipes and pending actual parents

The new adapters are independent consumers of the original scientific objects.
No producer submits a job. Root owns Slurm admission and source publication.
All production actions below run on approved Main CPU allocations, with pinned
plans, fresh Lustre quota and the declared whole-output/future-output reserves.
`memory` fields below are software allowances, not fabricated Slurm reservations.
No finite memory allocation is inferred when Slurm memory environment fields are
absent; all software allowances must fit measured MemAvailable plus the reserve.

1. **Reference before.** Wait for the actual full true Common molecular graph
   projection and independent final Root graph review. Use
   `pack_reference --plan ...` with schema `PUBCHEM_EXACT_REFERENCE_PACK_PLAN_V1`,
   `reference_role=before`, `input_manifest` pinned to that closed
   `expansion_common_v1_structure_projection_v1` manifest. This preserves every
   Common molecular row, duplicate reference fingerprints and original ordinals;
   it writes the complete binary fingerprints, ASCII full keys and exact
   scaffold/ring/identity counts. No representative or sampled reference exists.

2. **Scientific baseline.** Pool's closed
   `EXPANSION_PUBCHEM_PREDECON_BASELINE_V1` receipt selects1M unique full keys from
   the entire original internal-minimum-CID pool before v1/downstream exclusion.
   Seed20261025/domain `PubChem-baseline-uniform`, original hash order, zero-based
   sample ordinals are frozen once. Invoke `coverage --plan ...`, schema
   `PUBCHEM_EXACT_SCIENTIFIC_COVERAGE_PLAN_V1`, `baseline_receipt`,
   `reference_manifest`, `reference_role=before`. Exact bidirectional sample
   membership checks precede NN work. Its explicit
   `EXPANSION_EXACT_SCIENTIFIC_COVERAGE_V1` COMPLETE receipt releases no candidate
   pool. It is neither a cost pilot nor falsely decontaminated.

3. **Actual full novel candidate queries.** Wait for complete all11 all-split
   filtering and Root's actual accepted index/producer/accounting chain. Pool
   emits `EXPANSION_TYPED_DECONTAMINATED_QUERY_PROJECTION_V1` with exact7-field
   JSONL, all eligible rows and pinned typed filtered receipt. Invoke
   `run --plan ...`, schema `PUBCHEM_EXACT_CACHED_NN_PLAN_V1`; omit max_queries for
   the entire pool. The output remains the original
   `expansion_exact_novelty_v1`; COMPLETE requires all original eligible rows.
   An explicit cost prefix cannot authorize ranking. Query BLOB deduplication
   changes only repeated mathematical work; source identities are all replayed.

4. **Unchanged scientific queue math.** Invoke `typed_rank --plan ...`, schema
   `PUBCHEM_TYPED_EXACT_RANK_PLAN_V1`, pinned `novelty_receipt`. It proves full
   typed candidate/novelty identities by both anti-joins and checks every
   structural ranking feature against the original typed source. The unchanged
   `external_sort.create_queues` object creates R5M and N5M, disjoint, seed20261025,
   same original R-uniform/N-tie domains, exact rational proportional order;
   first batch is exactly1.25M from each queue. No population narrowing exists.

5. **Frozen UFF source and augmentation fingerprints.** Root supplies a real
   `ROOT_EXPANSION_PUBCHEM_GRAPH_SOURCE_REVIEW_V1`, APPROVED_FROZEN_SOURCE_GRAPH,
   binding actual ranking receipt, typed filtered candidates, raw projection,
   source PubChem version and isomeric graph semantics. Invoke `ordered_source`
   with schema `PUBCHEM_TYPED_ORDERED_UFF_SOURCE_PLAN_V1`, `ranking_receipt`,
   `graph_source_review`. All2.5M selected identities join their immutable source
   graphs. It writes the existing UFF3 source-manifest contract, bounded JSONL
   parts and `EXPANSION_ORDERED_RN_REFERENCE_PROJECTION_V1`. The latter reuses the
   exact original precomputed ECFP4, with no new perception or downstream labels.

6. **Reference after.** Invoke `pack_reference`, role after,
   `base_reference_manifest` pinned to exactly step1, `input_manifest` pinned to
   step5's augmentation manifest. Every base fingerprint/key byte is copied
   unchanged as the prefix; exactly2.5M new disjoint source identities follow.
   The resulting `EXPANSION_EXACT_AUGMENTED_REFERENCE_V1` reports source-space
   membership; it does not claim UFF/QM/training completion.

7. **Scientific coverage after.** Invoke `coverage` role after with the exact
   same baseline receipt as step2 and complete augmented reference from step6.
   It independently hashes the full old reference prefix, uses all old/new
   reference rows and original-ordinal ties. Report identity membership,
   fingerprint score1 and equality of the nearest chosen full identity
   separately: fingerprint collision/stereoduplicates are not identity proof.

8. **Comparison.** Invoke `compare_coverage`, schema
   `PUBCHEM_EXACT_COVERAGE_COMPARISON_PLAN_V1`, pinned `before_receipt` and
   `after_receipt`. Same1M identity/order and reference-parent bindings are
   mandatory. No score may decrease; an equal score must retain the original
   earliest reference ordinal. Counts, exact descriptive quantiles, histograms
   and gains retain the full sample; a second summary explicitly excludes
   identities present in either reference. Self matches are reported openly.

All reference/coverage/NN plans need `output_directory`, `workers`,
`worker_rss_cap_bytes`, `parent_rss_cap_bytes`, `query_batch` as applicable and
the shared quota fields `quota_snapshot`, `quota_authority`, `output_cap_bytes`,
`other_future_reserved_bytes`, `minimum_free_bytes`. SQL plans additionally
require `sql_memory_bytes`, `spill_cap_bytes`, `minimum_node_available_bytes`.
Every plan's output allowance must include retained failed attempts and spill.
Dedicated attempt directories preserve partial SQL outputs. Generation uses the
separate UFF3 plan and its existing closed-inode ledger, not the SQL poller.

Pending dependencies remain actual dependencies: no future Common, RAW merge,
all11 index, baseline, exact novelty, queue, source, accounting or Root review
hash is fabricated here. These recipes and source checks are not performance
measurements. Profile the complete true Common reference before projecting
full-pool CPU/storage cost.

Validation additions: `python -m unittest
workflows.expansion.exact_nn_cached_v1.test_bridge -v` runs5 small native SQL
seam tests (membership/features, fixed-sample membership, self-match reports and
equal-score original ordinals), plus2 memory-metadata cases verifying that an
absent Slurm memory value is not fabricated and real memory guards remain.
The9 engine/cache/spawn tests passed in Root's
actual4525647; new adapter tests remain pending their own actual allocation.
