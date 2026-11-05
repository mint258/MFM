# Independent CPU integer popcount prototype — source only, not adopted

This new package implements an alternative exact kernel. It does **not** execute
original CachedReference.nearest and must never be reported as the original
Python/RDKit implementation. Original engine.py/cache.py/workers.py/coverage.py/
run.py and current201 are untouched. No production worker or entry adapter is
provided. No source in this package builds or loads a binary merely on import.
No binary, native test result, complete-reference equivalence, throughput or
speedup has been produced by the source author.

## Mathematical equivalence boundary

`kernel.c` is C11, not C++: it uses CPython C API and libc only, with no RDKit C++,
Boost, NumPy, pybind11, C++ standard-library or OpenMP ABI. It consumes the same
256 raw bytes per fingerprint, copies them privately, and never derives chemistry.
Each nonempty popcount group owns contiguous uint64 fingerprint and ordinal
buffers. Within-group append order is original reference order; duplicate
reference fingerprints remain separate rows. Dynamic capacity can exceed the
used payload: capacity/peak RSS is observed, not described as exactly n*256.
No mmap or externally mutable buffer backs the sealed cache.

For each query the order is min(qpop,rpop)/max(qpop,rpop) descending by exact
integer cross-products, ties ascending rpop; zero/zero upper bound is0/1.
The64-entry LRU only caches that order. The kernel prunes a whole group only when
its upper bound is STRICTLY smaller than the current exact fraction. All selected
group rows are evaluated; the group argmax retains its first original ordinal,
then the global tie chooses the smallest original ordinal. Group-level updates
match the original traversal, so evaluated/pruned and debug searched-group order
can be compared exactly, not just the final nearest score.

Winner intersection/union are **not reduced**. Zero/zero is0/1; zero/nonzero may
remain0/2048 or another actual union. The kernel returns only integer fields and
searched groups. Python constructs the original eight-field dict and performs
one int/int division for score. No native float division/reciprocal/fast-math,
scores list, reference sampling, approximate index or within-group early exit is
used. Bounds/products use uint64; all valid2048-bit products are much smaller.
Distinct feasible rational scores (denominator<=2048) cannot round to the same
binary64 value unless the rational scores are equal; full F64-bit comparison is
still mandatory evidence, not assumed from a smoke-test score match.

## Storage and memory

`CompiledReference(iterable, worker_rss_cap_bytes=..., build_manifest_reference=...)`
allows small oracle fixtures. Append builds private per-group buffers; seal
forbids further append. Before allocation/growth the C helper reads actual Linux
RSS and requires room for old + new buffers simultaneously plus a16MiB workspace
reserve; the cap itself is unchanged. Python also uses original enforce_rss at
load and every4096 records, and the original5s post-query check; native nearest
checks actual headroom before each query. Fixed reserve is allocation headroom,
not permission to exceed the declared cap. Real allocator retention/fragmentation
must be measured. `.close()` drops the capsule and frees all private buffers.

`load_reference(path, expected_frame, fullN, worker_rss_cap_bytes, build_manifest_reference=...)`
retains original same-FD/path dev/inode/size/mtime/UID checks, adds ctime stability,
and verifies fullN and exact n*256 bytes. Parent MUST first verify full reference
artifact SHA, as in the original worker contract. This prototype has no parent
worker/manifest controller. Source truncation/deletion after a successful load
cannot change the private cache; inflight mutation/replacement is rejected.
`reference_records_loaded` deliberately does not claim n RDKit decode calls.

## Future explicit Root build — do not run on login/Windows

Root alone may later build in an admitted CPU-only Linux Slurm allocation with
reviewed output/RSS caps and an actual clean isolated Python. The standalone
recipe does not create a scheduler allocation or quota controller. It requires
Python-I-B and actual Slurm CPU environment. Use an absolute **C compiler**, e.g.
actual `/usr/bin/gcc` after Root confirms it exists; do not pass g++ to C11 source.
The recipe avoids new C++ APIs and should be assessed against actual GCC4.8.5,
CPython3.11.14 headers/ABI; no compilation with that environment is claimed here.

```text
PY -I -B ABS_GUARDED_ENTRY workflows.expansion.exact_nn_popcount_cpp_v1.build --compiler ABS_C_COMPILER --output ABS_FRESH_PRIVATE_BUILD_DIRECTORY
```

Flags are explicit -O3/-std=c11/-fPIC/-shared with no-fast-math,
no-unsafe-math-optimizations/no-reciprocal-math/ffp-contract=off; no -march=native.
On x86 GCC, runtime CPUID selects a target(popcnt) helper only if supported;
otherwise the clearly labelled portable uint64 SWAR function is used. No AVX or
unreviewed CPU threading is introduced. Root must verify the native CPU branch;
current Alpha popcnt observations do not validate fallback performance elsewhere.

A successful build writes source/original-oracle pins, compiler file/version,
exact command/flags and environment paths, CPython version/SOABI/EXT_SUFFIX,
CPU flags/affinity, binary SHA and loaded-executable-library file SHA observations
from a separate Python-I-B metadata probe. Failed attempts/logs remain separate;
they do not get a complete build manifest. Probe/library observations are build
provenance, not full runtime dependency-equivalence or scientific adoption proof.
The loaded manifest status explicitly stays
COMPILED_PROTOTYPE_PENDING_NATIVE_EQUIVALENCE_AND_ROOT_ADOPTION.

`backend.load_kernel` requires an exact build-manifest reference and verifies
binary, current prototype/oracle source bodies and exact CPython version/ABI.
There is no automatic compiler, unpinned import search, native fallback to the old
engine or old-engine fallback to native. One explicit build is allowed per process;
use a fresh process for a different build. Root should pin the immutable manifest
and binary in its actual source/deployment/launcher receipt.

## Pending tests and adoption

After an actual Root build set EXACT_POPCOUNT_BUILD_MANIFEST to its absolute
build_manifest.json path, then within the same admitted immutable source capsule:

```text
ENTRY workflows.expansion.exact_nn_popcount_cpp_v1.test_native -v
```

The8 native fixture methods compare **every result field and score F64 bits** with
the unchanged original oracle: exhaustive6-bit universes/order/duplicates, all2049
q-popcount orderings and LRU eviction, zero fractions, .1 equal-bound case,
strict pruning counts, all2048 single-bit positions/extreme dense fingerprints,
private-copy source deletion, same-FD replacement/cardinality rejection,
empty/width/mutable/seal/RSS guards, source/binary/ABI pin refusal. Missing binary
metadata is a failure, never a skipped successful validation. A2GiB test cap is
only an explicit fixture allowance; Root must admit real process-tree peaks.

Before scientific adoption Root still needs unchanged original math9, actual
complete1,196,122 reference + the SAME real64 query fingerprints versus both
backends, original/native searched-group orders, all integers and F64 bytes,
fresh-spawn/load/steady-state kernel/CPU/RSS measurements, and source/binary/
ABI/CPU/native-C0 independent review. Fixture completion is not full-population
performance representativeness. Build/probe/compile success is not equivalence.

Existing QueryCache mathematically keys recipe/ref SHA/result definition, not
native implementation provenance. No old cache is read/reused by this prototype.
First comparison/performance runs must bypass old cache hits. Production cache
reuse or a worker/entry seam requires a later explicit Root adoption and backend
provenance; it is not implied by equal final scores. Current201 continues unchanged.
