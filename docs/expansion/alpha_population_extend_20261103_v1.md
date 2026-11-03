# Population-only statistics: reuse closed1M, add accepted fullCommon

This independent adapter creates a fresh output stage. It never edits the closed
baseline stage, its receipt, or its analysis scope. It does not alter the original
distribution module or its resume/scope guards. It does not require nearest
neighbors and cannot claim task2.1 comparison completion.

`alpha_population_extend_v1.plan` is metadata-only. After actual Common C0 and
Root acceptance, use its exact manifest at
`B/common_actual_close_1885153_v1/common_reference_manifest.json`. Supply a new
adapter deployment manifest (`code_references`, `entry_reference`) and a fresh
metadata output directory. Defaults bind actual baseline acceptance1885167,
the exact original statistics-cache deployment, and v3 node launcher.

The new layer namespace must resolve `distribution_report_v1` to the immutable
`statistics_cache_bc4669c` package, and include the existing accepted Common
consumer plus this adapter and `alpha_common_followup_plans_v1`. The adapter
compares every original distribution Python source pin against the closed1M
receipt. Root handles deployment and submission.

```bash
PY -I -B NEW_LAYER/layer_entry.py \
  workflows.expansion.alpha_population_extend_v1.plan \
  --common-manifest B/common_actual_close_1885153_v1/common_reference_manifest.json \
  --adapter-deployment D/NEW_ADAPTER_actual_deployment.json \
  --output-directory B/population_common_extension_plans_v1
```

The builder retains original baseline manifest, functional-group recipe and
analysis-scope pins. It records the closed DB physical frame without hashing the
large database on the metadata host. The actual allocated producer holds a
SQLite read transaction, rejects WAL/journal activity or frame change, copies
the closed database bytes, and verifies source/copy SHA equality. This is a new
runtime source SHA, not a fabricated historical C0 database hash: the previous
Root acceptance pins the receipt and six population tables, not a database SHA.

The copied DB must contain exactly the completed original one-million population
with exact member/seen anti-join and all11 numeric/bin denominators. A canonical
logical digest binds its population row, required members, seen rows, counts and
moment states. The same digest must remain unchanged after extension. Only
accepted fullCommon1196122 is ingested through unchanged
`distribution_report_v1.__main__.run(stage='population_tables')`, using unchanged
`ingest_population`, `enrich_batch`, and `Moments`. The new version/scope is
written only in the new root; the original scope is copied as lineage. Baseline
sources are not rescanned or reenriched. Common uses original molecule IDs,
including distinct molecules with equal full keys; membership is the complete
strict5 projection and features are the accepted full structural-feature rows.
Missing descriptors or unsupported rows fail, without additive repair/filtering.

The plan initially preserves the actual baseline resources:16CPU,48GiB software
tree,1GiB SQLite cache,24GiB node reserve,shared reports5GB output cap and200GB
account floor, with original future reservation1281736873472B. Root can review
resources before submission; this builder infers no new closed-scope credit.
Both plans and sbatch remain unsubmitted. The adapter emits its own pending-C0
receipt and the unchanged producer's population-only tables. Neither declares
Common NN,1M coverage,2.1 completion, R/N, conformers, D or training released.

Two synthetic stdlib fixtures reject a changed original baseline source/recipe
and missing-C0/non-strict additions. No production data is used by these tests.

The repaired producer has an explicit adapter branch into
`alpha_common_repaired.validate_manifest`. Unknown/unaccepted repaired states
propagate rejection; they never fall back to old authority. The old producer
branch remains unchanged. Invoke the immutable original ten-file
`statistics_cache_bc4669c/distribution_report_v1` package: its original
`io.population` accepts the physical Common manifest's authoritative integer
count, full TRAIN/VAL role/sampling flags and identity-bound sources without
checking/rejecting the authority's producer discriminator. The independent new
adapter validates actual repaired authority before any DATA. This keeps every
original statistics source pin and scientific accumulator unchanged.

Planned baseline DB physical frames retain the metadata host's st_dev as an
observation only. Across Alpha Gluster clients, inode/UID/size/mtime/ctime remain
strict; the mount-local device number may differ. Runtime observes its own full
local frame and checks that exact frame against the same opened source FD and
path under SQLite READ lock before/after copying. Fresh source SHA and independent
destination SHA are mandatory, and destination FD/path frames stay exact. Both
planned and runtime source frames remain in the clone proof; no historical DB
SHA or cross-node device equality is fabricated.

Optional `--future-budget-review B/all_future_storage_budget_v2_20261104.json`
binds the actual matching Root reports budget, preserving its5GB scope cap,
200GB account floor and2TiB authority. It uses the reported other-future
reservation1264483236352B and records original/resolved values plus the review
pin. Omitting this option preserves the original conservative reservation.
The new sbatch explicitly sets `--time=0` and unsets inherited memory-request
variables. The plan carries actual Alpha endpoint/UID from the closed original
runtime rather than inferring them from a hostname.
