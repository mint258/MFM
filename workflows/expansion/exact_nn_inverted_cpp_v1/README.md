# Independent exact inverted posting prototype — not adopted

This new C11/CPython package is an alternative implementation, not execution of
the original RDKit engine or the adopted popcount kernel. No existing module is
modified. Active201/213/214, caches, worker entries and scientific artifacts stay
untouched. The source author has not compiled, run native tests, loaded scientific
DATA or measured this backend. There is no production integration or speed claim.

## Private representation and exact result

Append privately copies each original256-byte ECFP4 fingerprint and original
ordinal into the same popcount groups as the old prototype. Every identity,
including duplicate fingerprints, remains a separate original ordinal. Seal builds
CSR offsets for all2048 bits and a uint32 posting for each reference/bit incidence.
Posting lists contain original ordinals, not an approximation or a chosen subset;
list order has no effect on integer counts. References up to UINT32_MAX are
explicitly supported; append refuses larger inputs before truncation. This is
well above the intended full1,196,122 reference. Offsets/allocations have overflow
checks. Posting allocation coexists with raw builder buffers until fully built;
only then are raw words freed. Group ordinal buffers and CSR stay private and
immutable. No mmap or mutable external buffer backs a sealed cache. Empty
fingerprints contribute a reference ordinal but no posting, and remain searchable.

Each query gets a private uint16[N] array, zeros every slot, then visits all query
set-bit posting lists. Every intersecting reference/bit increments its counter;
maximum intersection2048 fits uint16. Group order remains exact
min(qpop,rpop)/max(qpop,rpop), descending rational bound, ties ascending rpop,
zero/zero bound0/1, the same64-entry LRU. The winner scan visits groups in that
order and skips only strict-lower bounds, retaining equality groups. Within-group
ties retain first original ordinal; cross-group ties choose earliest original
ordinal. Intersection/union are unreduced; zero/zero is0/1. The native result has
exactly the old seven fields, including logical evaluated/pruned counts and group
sequence. Python adds score with exactly one integer division, producing the same
eight-field API/F64 bit pattern subject to required native parity validation.

`CompiledReference`, `load_reference`, `order`, `nearest`, `close` keep the old
prototype API shape. It is a NEW implementation and must not reuse an old binary,
old build proof, adoption or cache namespace merely because the shape matches.

## Honest work diagnostics and resource boundaries

`nearest_with_work(raw)` returns `(same_eight_field_result, work)`; the ordinary
nearest result stays unchanged. Work separately reports query set bits/posting
lists, posting entries/increments, all N zeroed counters, winner scan rows and
checked bounds. **Logical pruning is not zero physical work:** a reference whose
group is later pruned may already have contributed posting increments. This
simple global-posting version deliberately precomputes all reference intersections
before logical bound scanning. It may do more physical work than popcount for
some queries, especially dense queries or strong early winners. Group-wise
postings are a possible later alternative, not implemented or assumed faster.

The C cap checks actual Linux process RSS plus requested peak buffer bytes and
16MiB reserve. It includes old+new growth buffers and CSR build peak. Query
workspace reservations are module-wide/GIL protected, including lazy allocated
pages; resident reserved bytes may be counted twice conservatively. Each query
owns/frees its workspace; posting/group data are read-only outside the GIL. The
LRU is updated under GIL then copied before release. Concurrent queries do not
share counters. RSS/allocator retention, source-load peaks and multi-backend
benchmark memory must be measured; the3GiB fixture allowance is not a fixed
production admission. Native statistics distinguish posting bytes, retained raw
bytes, group buffer capacity and per-query workspace. None claim RDKit decoding.

Same-FD/path dev/inode/size/mtime/ctime/UID/fullN guards from the old private loader
are retained. Parent must first verify the full reference artifact SHA. Source
mutation/replacement during load fails; deletion after successful load cannot
alter the private CSR. No sampling, chemistry recomputation, score array, float
native division, fast-math or worker threads are introduced by the kernel.

## Explicit new build and native verification — Root only

Build in a separately admitted CPU-only Linux allocation using actual CPython
headers and an absolute C compiler. This recipe never submits or builds on import:

```
PY -I -B GUARDED_ENTRY workflows.expansion.exact_nn_inverted_cpp_v1.build --compiler /usr/bin/cc --output ABS_FRESH_BUILD
```

C11/libc/CPython only; no C++/RDKit/NumPy/Boost ABI. Explicit -O3 with no-fast-math,
no reciprocal/unsafe FP optimizations, fp-contract=off, no march=native. Runtime
CPUID selects popcnt for loading/query-popcounts only; intersection search uses
postings. Portable SWAR fallback is labeled. Build pins this package's five core
sources, original mathematical engine, compiler/version/flags, CPU/affinity,
CPython SOABI/version/extension suffix, binary SHA and observed loaded libraries.
One new build may load per process; import is lazy. Status remains
COMPILED_PROTOTYPE_PENDING_NATIVE_EQUIVALENCE_AND_ROOT_ADOPTION. The old popcount
binary/manifest cannot satisfy this implementation/module/schema identity.

After separately building both backends, set `EXACT_INVERTED_BUILD_MANIFEST` and
`EXACT_POPCOUNT_BUILD_MANIFEST` to their actual build manifests and run:

```
ENTRY workflows.expansion.exact_nn_inverted_cpp_v1.test_native -v
```

Ten native unittest cases compare ALL original result fields/F64 bits against
both unchanged Python/RDKit oracle and the old popcount kernel: exhaustive6-bit
references/queries, duplicates/earliest ties/equal bound .1, zero/unreduced
fractions, all2048 bit positions, dense2048 intersections, all2049 orderings/LRU,
strict pruning and honest posting work, shared-cache concurrent private counters,
source deletion/replacement/cardinality and cap/ABI/source/binary refusal. A
missing actual build is an error, not a skipped successful validation. Fixtures
are prepared but not run by the source author.

Actual full reference1196122 plus the exact same64 historical206 fingerprints,
per-query SHA/order digest, all result fields/F64, native source/binary/ABI,
load+steady wall/CPU/RSS and posting workload remain required benchmark evidence.
The64 prefix is not a full-pool workload or ETA. Scientific adoption and production
resource caps require those actual measurements; this package adds no Root gate
or controller and does not affect running Alpha jobs.
## Coordinator native evidence — 2026-11-04

Main Slurm4525827 completed0:0 in15seconds with16CPU; Alpha actualstep1885213.0 completed0:0 in22seconds with16CPU inside the existing32CPU allocation. Parent1885213 remainedRUNNING and is not relabeled completed. Each site passed10native tests, then16workers each loaded all1,196,122 references and made192paired comparisons of the same64historical queries. All eight fields and binary64 score bits matched.

Main paired old/new call-wall totals were8.930364188s/3.671120866s (ratio2.4326); Alpha20.625004780s/11.269353767s (ratio1.8302). Alpha coexecuted with the active NN workers. These are prefix64 kernel observations, not whole-pool throughput or an ETA. Both sites built separately against their actual Python/ABI: Main3.11.14GCC11.2 and Alpha3.11.14conda-forgeGCC14.3. Production integration/cache continuation is still pending; active201/213/214 were not replaced by the benchmark.

Actual producer results, native accounting and the ordinary native-equivalence input descriptor are archived under docs/expansion/results/20261104/inverted_*.json and native_sacct.txt. No new per-job Root approval schema is introduced. The descriptor binds actual Main parentC0 and Alpha stepC0, preserving Main metadata origins and the RUNNING Alpha parent.
