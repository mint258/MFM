# Alpha Common reference pack and scientific baseline handoff

This is a proposed source recipe, not an actual plan, admission, job, accounting,
performance measurement or completed analysis. Root owns all submissions. The
reviewed source baseline is Root5caf2ef; the two CLI adaptations in this change
must be in the next immutable capsule before using node_launcher for these modules.
No COCONUT source-scope decision is needed for the independent fixed1M baseline.

## Inputs and work that can proceed independently

Alpha baseline1885155 completed0:0 with the existing receipt at
BULK/original502/baseline_1m/receipt.json (BULK is Root's actual deployment root,
not a literal path to insert into a plan). It freezes exactly1M membership,
feature and QUERY_FIELDS projection rows. Its receipt's
PENDING_ROOT_TERMINAL_ACCOUNTING field is producer-time metadata: retain the
closed receipt and add Root's real terminal accounting separately. Do not rewrite
that receipt or relabel it as a decontaminated/novelty query.

Before Common C0, independently check the actual receipt/three body references,
0..999999 sample ordinal census and membership, compute source-only FP distinct
counts, and count the baseline feature distributions/functional groups. None of
those needs Common, downstream exclusion or UFF. They are independent analyses,
not exact-nearest results or a completed task2.1 comparison.

The existing coverage producer has no pre-ingestion-only CLI. Its QueryCache
scope requires the actual final reference manifest SHA and reference count;
do not create a fake reference or pre-bind a cache to a predicted manifest.
The sample/features are already the frozen baseline; a second sample is not
needed. Existing distribution_report_v1 supports populations-only ingestion,
but its resource dispatcher is still Main-only and cannot currently run an
Alpha resource plan unchanged. Do not launch it on Alpha until an explicit
runtime adaptation is integrated. Final baseline_report also requires full
Common and complete exact1M nearest results.

## Close the actual Common authority before reference packing

Wait for the actual full Alpha Common producer C0, independent Root terminal
accounting and Root review. These are existing consumer contracts, not new gates.
Source-only receipts, partial journals and the stopped Main parent are insufficient.
The expected complete reference is1196122 molecules: TRAIN1188592/VAL7530,
original denominator1214218/excluded18096; graph HOLD0 and all independent
producer census/readbacks must close. See ALPHA_COMMON.md for the exact schema.

Run metadata-only from the approved clean Alpha code cwd:

```
PY -I -B ENTRY workflows.expansion.exact_nn_cached_v1.alpha_common \
  --producer ACTUAL_ALPHA_FULL_PRODUCER_JSON \
  --root-review ACTUAL_ROOT_ACCEPTANCE_JSON --output FRESH_CONSUMER_MANIFEST
```

The finalizer has no --plan or --startup-proof. It produces
expansion_common_v1_structure_projection_v1 with the explicit Alpha producer
marker/status COMPLETE_ALPHA_FULL_COMMON_REFERENCE and pins the unchanged
strict5 and structural-feature journals. Root's acceptance schema is
ROOT_ALPHA_FULL_COMMON_GRAPH_ACTUAL_ACCEPTANCE_V1,
APPROVED_EXACT_FULL_COMMON_REFERENCE, exact producer reference and actual Alpha
COMPLETED0:0 parent in the separately pinned accounting. No Main C0 is invented.

## Freeze the pack plan and launch it using the existing same-node wrapper

Use a fresh Root-pinned plan template with:

- schema PUBCHEM_EXACT_REFERENCE_PACK_PLAN_V1
- reference_role before
- input_manifest: exact path/bytes/SHA triple of the final consumer manifest
- output_scope_root: a dedicated small-file reference-pack aggregate scope
- output_directory: a fresh child directory; node_launcher replaces this with
  output_scope_root/TAG_job_JOBID. Pack intentionally rejects an existing stage.
- workers16 and the actual Alpha profile/endpoint/UID1264/code references,
  parent_rss_cap_bytes, quota/output/future/free-space fields described below.

The raw packed bodies are306207232 FP bytes and33491416 key bytes for1196122
rows, plus exact SQLite ID/identity/scaffold/ring counts and provenance. An8GB
output allowance is a conservative proposed envelope, not a measured requirement
or a new policy. Root may use its reviewed cap. Failed pack stages remain in the
aggregate scope and count against it; restart packing in a fresh stage.

Root's already established same-node wrapper is invoked inside its actual
approved16CPU CPU allocation, from the exact profile clean code cwd:

```
PY -I -B BASE_ENTRY workflows.expansion.alpha_runtime_v1.node_launcher \
  --template PINNED_PACK_TEMPLATE --base-root CLEAN_BASE_ROOT --entry ENTRY \
  --module workflows.expansion.exact_nn_cached_v1.pack_reference \
  --tag exact_common_pack --control-root OWN_CONTROL_ROOT \
  --gluster-rpc-program ACTUAL_ROOT_APPROVED_RPC_PROGRAM
```

Do not pass --action. node_launcher creates the real local publisher, atomically
pins its actual identity into the plan, sets the job-specific output directory,
and supplies --plan plus --startup-proof. Both exact CLIs now accept that
optional startup proof and retain its exact byte reference in their result;
its presence does not authorize scientific inputs or fabricate C0. Keep the
wrapper's actual exit/accounting evidence. The producer writes manifest.json,
schema expansion_exact_ecfp4_reference_v1/status COMPLETE. Freeze its actual
path/bytes/SHA after closing the job.

This pack preserves every Common row, including repeated fingerprints/keys.
Ordinal is zero-based accepted strict5 line order (Common MID ASC), with FP
byte offset256*i and key offset28*i. Equality chooses the earliest ordinal.
Do not require graph-event journal or entire SQLite/manifest bytes to be equal
across attempts; freeze the accepted reference artifact itself.

## Freeze and launch scientific exact1M before coverage

Use schema PUBCHEM_EXACT_SCIENTIFIC_COVERAGE_PLAN_V1 with:

- baseline_receipt: the actual closed1885155 baseline receipt triple
- reference_manifest: the actual closed pack manifest triple
- reference_role before
- output_scope_root: a dedicated small-file coverage scope, separate from UFF
- output_directory: the launcher-assigned child stage
- workers16; query_batch32; cache_commit_queries4096 (both bounded batching and
  checkpoint parameters only; no reference/query sampling or time stop)
- proposed worker_rss_cap_bytes3221225472 and parent_rss_cap_bytes8589934592:
  16*3GiB+8GiB =56GiB software allowances, fitting a reviewed64GiB software tree
  envelope with minimum_node_available_bytes25769803776 (24GiB reserve), only if
  actual MemAvailable and Root admission still satisfy this on the selected node.
- a proposed16GB own-output cap for retained queries.sqlite, journal, attempts,
  metrics and complete1M projection; Root must review with actual usage and all
  future phase reservations. This is not a measured high-water mark.

The complete shared resource fields are runtime_profile_reference, endpoint,
uid, code_references, software_rss_budget_bytes, minimum_node_available_bytes,
quota_snapshot, quota_authority, output_cap_bytes, other_future_reserved_bytes,
minimum_free_bytes. Obtain all real paths/SHA/UID/publisher/resource decisions
from Root's current Alpha deployment, not from old Main plans. The template's
quota authority is replaced with the actual same-node publisher identity by
the launcher; keep maximum_age_seconds120 and the existing freshness predicate.
The Alpha profile and native statfs admission remain authoritative. No finite
Slurm memory reservation is inferred from these software allowances.

Use the same wrapper command with the coverage template and
--module workflows.expansion.exact_nn_cached_v1.coverage --tag baseline_exact_before.
It writes attemptN.coverage.jsonl and attemptN.receipt.json,
schema EXPANSION_EXACT_SCIENTIFIC_COVERAGE_V1/status COMPLETE, queries1000000.
It verifies both membership anti-joins, ingests all1M rows, deduplicates only the
FP computations on disk and replays every source identity. It reports identity
presence, score1 and chosen nearest identity equality separately. Empty FP
self-score remains the pinned RDKit0. No downstream features, approximation,
reference sampling, early publication, molecule deletion or score fitting occurs.

Current exact resource behavior is explicit: worker RSS checks at reference
load and during actual search; parent/quota checks at bounded I/O checkpoints,
force points and result batches, with a30s throttle. This is not the separate
Alpha Guard's5s automatic whole-tree RSS monitor; do not describe it as such.
First full reference-load/worker metrics and actual evaluated/pruned counts are
produced by the job; no pre-run speed claim or total runtime forecast is made.

Cache computations are reference-SHA scoped and checkpointed. For an operational
resume, use the identical actual reference/baseline and same coverage output
stage directly with the accepted CLI (and a fresh Root-admitted current plan),
so queries.sqlite is reused. The generic launcher always creates a new job stage
and therefore does not automatically reuse a previous stage's cache. Do not
rename/copy scientific cache identities or pretend a new empty stage is resumed.

## Later independent dependencies

The before coverage result plus complete Common/baseline population manifests
can complete task2.1 reporting once its Alpha reporting runtime/evidence bridge
is integrated. Its exact receipt currently carries baseline/reference pins,
not distribution_report's population-manifest pin contract; that explicit
metadata bridge remains necessary, without changing scores or membership.

Full candidate novelty/ranking waits for the complete all11 filtered pool and
its Root acceptance (including the unresolved source-scope decision). It must
use the decontaminated-query CLI, not mislabel the baseline. The later after
reference appends exactly2.5M frozen selected fingerprints after the unchanged
Common prefix, and coverage must reuse this identical frozen1M baseline.
No candidate, UFF, D-label, queue, training or after-coverage completion follows
from the before coverage job alone.

Source-only CLI fixtures:
workflows.expansion.exact_nn_cached_v1.test_launcher_cli (2 cases, no science).
Run them in Root's next actual source fixture allocation. No actual execution or
performance result is claimed by this document.

Corrected-population consumers explicitly recognize sealed
PUBCHEM_EXACT_MINCID_OVERLAY_POOL_V1 through the unchanged recovery reader's
actual producer/Root/C0 gate. Legacy V2/Main/Alpha branches retain their original
behavior. A corrected baseline must carry matching population_version, source
pool/size, exact old baseline history, seed/domain and actual corrected183 Root
review. It is not relabelled historical1M. Full coverage and operational profile
plans must add baseline_actual_review_reference (actual1918B,
SHA5217385cfa77f2702e181aa8d97be579b6289ce2a51e60334930ff9f7ae04f69);
baseline_receipt remains the actual183 receipt pin. Old baseline plans need no
new fields. Runtime actual profile.job_id is read instead of legacy SlurmJobID.
No approximate/reference/selection change occurs. Source fixture module
exact_nn_cached_v1.test_overlay_contracts has two metadata cases for sealed
reader delegation and version/history/review absence rejection, no body reads.
