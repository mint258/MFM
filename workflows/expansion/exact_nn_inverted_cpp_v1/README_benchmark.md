# Isolated full-reference paired prefix64 benchmark

Source-only driver; Root alone deploys/submits it. It neither changes NN APIs,
the active201 job, source ordinals/math nor production adoption. Do not interpret
64 historical query identities as a representative full-pool speed or ETA.

Use an actual Main UID1278, compute-0-20 Slurm16CPU CPU-only allocation and the
matching chemprop Python3.11.14/RDKit2025.09.5 environment, Python `-I -B`. An
explicit full source import root is required (the directory containing
`workflows`). Root's isolated entry should invoke:

```text
workflows.expansion.exact_nn_inverted_cpp_v1.benchmark --config ACTUAL_CONFIG --output FRESH_ABSOLUTE_OUTPUT
```

Config schema `MAIN_FULL_COMMON_INVERTED_BENCHMARK_CONFIG_V1` has `compiler` equal
to the actual `/usr/bin/cc`, `import_root`, `repeats`1 or3, and
`ordered_query_identity_sha256` equal to
`f61f6a5f8f5effece3dfa24dc6d48172d77e072e165e5652103d2b68204e4854`.
`inputs` contains actual path/bytes/sha256 refs named `fingerprints`, `queries`
and `historical206`. Required existing inputs are:

| Input | Actual path / bytes / SHA256 |
|---|---|
| fingerprints | `/tmp/zixiao_pubchem_inverted_benchmark_20261104/fingerprints.bin`;306207232;`4973bd1cdf9cc3ea5a601ddff3d54ac1063858e8aed2114b1c0cffe0a37f1d57` |
| queries | MainR/control/pubchem_alpha_return_20261103/inverted_reference_benchmark_prefix64_20261104.jsonl;49016;`1df7de435b7f131f3a2eb816919f33b3dfed10804cd86c04f850c06a278e4021` |
| historical206 | Same control/original_206_popcount_measurements_for_inverted_benchmark.json;125067;`6f20621f629cd23ba029aa25a04af9cb3cc05148e2cc15883dee6be6f78a054a` |

MainR is `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025`.
The full inputs are freshly SHA/frame checked; the fingerprint file must contain
all1196122 references in original order,256 bytes each. Query identity digest
updates SHA256 for each i=0..63 with compact JSON
`[i,cid,full_key,bytes.fromhex(ecfp4_2048_hex).hex()]` plus newline. Every query FP
also binds the exact historical206 fingerprint hash/native+RDKit results/F64 bits.

Both actual `build.build` functions compile their unchanged source with the
selected actual compiler in fresh private directories. Their emitted source,
ABI/compiler/binary pins are consumed directly. Then a separate `-I -B` process
runs exactly10 actual new-package native tests, including the original RDKit
oracle and old backend, with `EXACT_INVERTED_BUILD_MANIFEST` and
`EXACT_POPCOUNT_BUILD_MANIFEST` set to those actual manifests. No skip is accepted.
Compilation/test stdout/stderr and partial failures are preserved. There is no
new approval layer or production adoption claim.

Exactly16 explicitly spawned processes each load both full references into
private native storage. Load order alternates by worker; a barrier ensures all
16 full-cache workers exist before query timing. Each owns four of the exact64
query identities, with repeats1 or3. Per-query/per-repeat order alternates old
first/new first. All8 result fields, unreduced integer fractions, searched group
order and binary64 score bits match both the historical206 native/RDKit witness
and the paired current old backend. A separately timed new profile call per query
records posting visits/counter work; it is excluded from paired-call timing totals.
There is no QueryCache or FP identity deduplication/subset of the reference.

Initial/rechecked actual MemAvailable must be at least80GiB:16×3GiB process caps,
8GiB parent and24GiB reserve. Actual RSS and node available memory are observed
while workers run, with a56GiB aggregate process RSS cap. These are software
budgets, not Slurm memory reservations. Partial files remain on any failure;
peers stop between calls and abort their load barrier cooperatively. No external
process/job is signalled. No arbitrary benchmark wall timeout is introduced.

Perworker load wall/processCPU/RSS/high-water/retained native storage statistics,
percall result/timing rows and posting-work observations remain actual output
files. Final COMPLETE requires all tests,16 successful workers,64×repeat exact
comparisons and stable original source/ref frames. Result pins actual physical
source bodies; a base Git commit is not claimed to contain uncommitted new code.
Even a faster measured prefix does not establish full-pool throughput or ETA;
loading, test/profiling overhead and parent CPU are reported separately.
