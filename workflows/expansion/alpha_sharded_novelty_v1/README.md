# Sharded exact novelty and original R/N queues

This runtime consumes the complete exact-key-only filtered Parquet manifest. It uses the previously validated compiled full Common nearest-neighbor worker and the unchanged original queue function. It does not wait for the independent fixed 1M background job.

Each identical candidate FP is searched once against all 1,196,122 reference molecules. Closed score shards retain the integer scores, reference ordinal and identity, and complete evaluated/pruned counts. Every original candidate identity is joined back to its own structural features. Missing scaffold counts are zero; a missing ring contributes zero, and an empty ring list retains the original full-reference default. A single small SQL check runs in the real allocation before full processing.

Sparse leading FP buckets can be uneven. Large buckets are split by a deterministic MD5 nibble solely for bounded query deduplication; this never changes structure identity, NN math, the reference population, or R/N tie hashes. Small immutable Parquet score/projection shards replace large writable JSON or SQLite outputs. Resume uses only physically verified newline-closed journal entries bound to the same filter and reference; crash tails and orphan partials are preserved.

The NN plan schema is ALPHA_SHARDED_EXACT_NOVELTY_PLAN_V1. The rank plan schema is ALPHA_SHARDED_EXACT_RANK_PLAN_V1. Both run via the existing real Alpha Slurm launcher and accept --plan and --startup-proof. Plans carry actual resource/quota and source pins; there is no new per-job Root approval.

Ranking consumes every projected identity, checks the full candidate membership and original structural fields, and calls original create_queues with seed 20261025 and 5M per stream. Its first batch is 1.25M per stream. It retains the existing H-only input-domain adapter without changing sorting mathematics. Full-pool execution remains uncompleted until the actual producer manifests close; source availability alone makes no dataset-completion claim.
