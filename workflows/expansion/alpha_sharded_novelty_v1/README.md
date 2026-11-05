# Sharded exact novelty and original R/N queues

This runtime consumes the complete exact-key-only filtered Parquet manifest. It uses the previously validated compiled full Common nearest-neighbor worker and the unchanged original queue function. It does not wait for the independent fixed 1M background job.

Each identical candidate FP is searched once against all 1,196,122 reference molecules. Closed score shards retain the integer scores, reference ordinal and identity, and complete evaluated/pruned counts. Every original candidate identity is joined back to its own structural features. Missing scaffold counts are zero; a missing ring contributes zero, and an empty ring list retains the original full-reference default. A single small SQL check runs in the real allocation before full processing.

Sparse leading FP buckets can be uneven. Large buckets are split by a deterministic MD5 nibble solely for bounded query deduplication; this never changes structure identity, NN math, the reference population, or R/N tie hashes. Small immutable Parquet score/projection shards replace large writable JSON or SQLite outputs. Resume uses only physically verified newline-closed journal entries bound to the same filter and reference; crash tails and orphan partials are preserved.

The NN plan schema is ALPHA_SHARDED_EXACT_NOVELTY_PLAN_V1. The rank plan schema is ALPHA_SHARDED_EXACT_RANK_PLAN_V1. Both run via the existing real Alpha Slurm launcher and accept --plan and --startup-proof. Plans carry actual resource/quota and source pins; there is no new per-job Root approval.

Ranking consumes every projected identity, checks the full candidate membership and original structural fields, and calls original create_queues with seed 20261025 and 5M per stream. Its first batch is 1.25M per stream. It retains the existing H-only input-domain adapter without changing sorting mathematics. Full-pool execution remains uncompleted until the actual producer manifests close; source availability alone makes no dataset-completion claim.
## Two disjoint NN work allocations

Both NN plans still use `ALPHA_SHARDED_EXACT_NOVELTY_PLAN_V1` and the same actual full filtered manifest,
actual196 Common reference and206/207 native exact worker. Add `partition_id` and an explicitly sorted
list `assigned_hash_buckets`. The32-worker plan receives `list('0123456789a')`; the16-worker plan receives
`list('bcdef')`. Partitioning is MD5 of the original canonical512-character FP hex text, first nibble,
not the sparse FP's own leading nibble. Every FP's identities therefore stay in the same work allocation.

Each process verifies the complete physical filtered source and counts full input versus selected rows.
Both query candidates and projection candidates use the same assigned predicate. Existing large physical
FP buckets iterate only assigned MD5 subgroups; small buckets apply the assigned IN predicate once.
Each source_binding also pins scope_key, partition_id and assigned_hash_buckets, so a resume cannot reuse
cache under another assignment. Only complete journalled immutable score parts are reused; old crash
tails and unjournalled orphans remain preserved. Native exact reference search and score/tie rules are unchanged.

NN writes `PUBCHEM_SHARDED_FULL_POOL_NOVELTY_V1` with status `SHARD_COMPLETE` and producer_schema
`PUBCHEM_PARTITIONED_EXACT_NOVELTY_SHARD_V1`. `queries` is only the actual assigned identity count;
whole_filtered_input_rows and unselected_population_rows retain its relation to the entire eligible pool.
No shard claims full population completion.

In the actual rank allocation prepare, call `aggregate.aggregate([ACTUAL_SHARD_REF32,ACTUAL_SHARD_REF16],
NEW_FULL_MANIFEST_PATH)`, or run `workflows.expansion.alpha_sharded_novelty_v1.aggregate
--shard-manifest ACTUAL32/manifest.json --shard-manifest ACTUAL16/manifest.json --output NEW_FULL_MANIFEST`.
The function checks both actual pinned SHARD_COMPLETE bodies/source bindings, disjoint assignment sets
covering0-f, identical source/reference/math, full-input/selected conservation and each closed physical
Parquet footer row count. It writes the original full schema with COMPLETE only when the actual two
selected counts and all physical part rows sum to the complete eligible population. It preserves producer
whole-body SHA references and checks stable frames/footer rows without another full projection-body hash;
the unchanged rank reader performs its normal body verification and full identity/feature anti-joins.
No output data is copied, no job or additional Root acceptance file is created. Original run_rank and
create_queues remain byte-identical. A single standard-library partition fixture covers duplicate-FP
multi-identity allocation, overlap/missing-cover rejection and exact partition declarations; the existing
native SQL preflight additionally checks the real MD5 predicate's disjoint/full union.
