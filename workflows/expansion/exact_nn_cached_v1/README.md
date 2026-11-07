# Cached exact ECFP4 nearest neighbors

Independent implementation for Part2.1/2.5. Original `nearest_exact.py` remains
unchanged. Every reference molecular row is retained in its original ordinal,
including duplicated fingerprints. RDKit2025.09.5 decodes the complete reference
once per worker. Groups by bit population are visited in descending safe upper
bound `min(q,r)/max(q,r)`. A group is skipped only if an exact integer cross
product proves its upper bound strictly below the current exact rational score.
Equal-bound groups are searched and global ties choose the first original row.
The actual RDKit binary64 result is returned unchanged.

The pinned official implementation returns0 for two empty bit vectors:
https://github.com/rdkit/rdkit/blob/Release_2025_09_5/Code/DataStructs/BitOps.cpp
`upper_bound(0,0)` is therefore0/1. Integer score fractions avoid pruning a
mathematically equal group because a binary64 score rounded upward.

`QueryCache` is a disk SQLite BLOB-key index of exact256-byte fingerprints,
scoped to reference-manifest SHA, recipe and algorithm. Different stereochemical
identities sharing this achiral ECFP4 vector reuse one mathematical query result;
their own identity, scaffold, ring counts and original order are preserved in
the replayed output. Each immutable query source has its own disk membership,
so a cost prefix does not compute pending full-pool queries. Binary64 score
bytes and row digests are checked on lookup. Interrupted complete math results
are reused. Outputs/worker metrics use new attempt names and preserve partials.

`workers.exact_batches(path,n,batches,workers=...,worker_rss_cap_bytes=...)`
is a generic raw-fingerprint API for independent coverage analysis. It does not
assert that coverage samples are a decontaminated expansion pool. Its caller
must pin the complete intended reference manifest and source population. No
reference sample, approximate search, new controller or Slurm submission exists.

Full-pool compatible runner:

```
python -m workflows.expansion.exact_nn_cached_v1.run --plan /absolute/plan.json
```

It accepts the same complete reference and decontaminated query manifests as
`nearest_exact.py`, or the explicit non-releasing v1 structure cost projection.
The receipt retains `expansion_exact_novelty_v1` and the old output fields and
audit; COMPLETE requires all declared rows and a verified filtered-pool receipt.
An explicit prefix is always BOUNDED_COST_PILOT. No default query/comparison/time
cap limits full production. Worker count must fit actual Slurm CPUs, and all
per-worker memory allowances plus parent must fit actual MemAvailable and the
declared node reserve. A finite Slurm memory value, when present, is checked;
absent values remain null and imply no scheduler memory guarantee. Fresh
shared quota is checked at startup and at most30seconds between batch boundaries;
mutable cache/output files earn no quota credit. `kind=lustre` dispatches to the
shared Lustre guard. Only a fixed flat set of output files is polled. Bounded
source/export windows reserve32MiB and NN checkpoint windows64MiB before writes; cache growth also
has a finite SQLite page cap. A native RDKit call is never killed for a clock.
Exact cache transactions close after up to4096 completed unique queries or at
the next completed batch after30seconds; this avoids one Lustre fsync per tiny
worker batch. This is a durability checkpoint, not a computation time limit.

Plan schema `PUBCHEM_EXACT_CACHED_NN_PLAN_V1`, required fields:
`reference_manifest`, `query_manifest` (path/bytes/sha256 triples),
`output_directory`, `workers`, `worker_rss_cap_bytes`, `parent_rss_cap_bytes`,
`query_batch`, and shared quota `quota_snapshot`, `quota_authority`,
`output_cap_bytes`, `other_future_reserved_bytes`, `minimum_free_bytes`.
Optional `max_queries` is an explicit measured prefix only. Use a dedicated
output directory; all cached queries/attempts consume that plan's same cap.

Validation (actual pinned Linux environment, via Root allocation):

```
python -m unittest workflows.expansion.exact_nn_cached_v1.test_exact -v
```

Tests compare exhaustive6-bit-space cases against both an independent integer
oracle and RDKit brute force, including empty vectors, duplicate references,
across-group ties and a rounded-up0.1 equality boundary. Cache tests cover
source-specific pending work, binary64 round trip, result tampering and scope
changes. A full-reference measured profile remains required before estimating
full-pool cost; this module makes no speed claim.

## Optional parent SQLite page-cache allowance

The existing pack_reference, coverage and run CLIs keep --plan PLAN. Their
plan schemas PUBCHEM_EXACT_REFERENCE_PACK_PLAN_V1,
PUBCHEM_EXACT_SCIENTIFIC_COVERAGE_PLAN_V1 and PUBCHEM_EXACT_CACHED_NN_PLAN_V1
all optionally accept sqlite_cache_bytes=1073741824. No extra CLI flag exists.
This sets PRAGMA main.cache_size=-1048576 for each parent SQLite connection;
omission preserves its installed session default. The parameter is per open
main database, not a global pool and not the NN workers' decoded-reference cache.
The integer must be at least1024 bytes; conversion to negative KiB rounds down.
SQLite allocates pages on demand; this suggested cache limit is not preallocated
RSS, a Slurm reservation or an entire-process memory cap. See the official
[SQLite cache_size description](https://www.sqlite.org/pragma.html#pragma_cache_size).

Coverage normally has one query-cache connection (up to1GiB suggested pages).
Full NN adds the read-only reference-count connection during replay, so at most
two connections coexist (up to2GiB), within Root's existing8GiB parent allowance.
Before-pack has one counts writer; after-pack first uses source+destination
backup connections (two), closes them, then opens one counts writer. No caller
sets TEMP cache/store, journal mode, synchronous, cache_spill, page size, schema,
SQL, transaction/checkpoint boundaries, source row order or scientific recipes.
QueryCache retains its exact reference/recipe/algorithm scope; an operational
cache allowance is not inserted into that scope, so a fresh admitted plan may
adjust it while resuming the same scientifically bound DB. Worker NN reference
loading, limits, exact pruning and ties are unchanged.

Each stage writes/logs sqlite_runtime_UUID.json with requested bytes and actual
main cache/page/spill, TEMP cache/store, journal and synchronous PRAGMAs. Its
complete result binds sqlite_runtime_reference. Full NN first records query
cache settings and later writes a second closed readback including the read-only
counts connection; prior attempt/readback files remain retained. These files
record runtime settings, not measured cache hits or speedup. Counts and cache
indices can exceed the default small page cache, making random GFS page I/O a
plausible bottleneck; sequential input, TEMP I/O and fsync may still dominate.

Root's current proposed NN admission is32 workers at1GiB worker RSS each plus
an8GiB parent allowance (40GiB software total), alongside48GiB statistics and a
24GiB node reserve. Root owns the actual CPU/node/quota admission and full packed
reference native memory/cost observation before the1M search. Neither this plan
proposal nor passing small existing engine/bridge/CLI fixtures proves the full
reference fits or supplies a speed claim. No output cap/future reserve or
existing guard is enlarged or bypassed by this option. There is no new time
limit, sampling, release gate, retry or scheduler submission.
