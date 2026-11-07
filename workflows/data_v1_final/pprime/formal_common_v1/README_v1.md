# P-prime common baseline: planning, bounded batches and actual acceptance

New code only; no formal QM has been run or authorized by these files. The
registered pilot15, vector audit, original prepared345, configs and WP5 sources
remain unchanged. Root alone submits. Standard scientific runs require ordinary
16CPU64GiB, node14-19, <=2h, all-user declared-memory85%, pinned source/request
and200GB remaining quota. No336 UFF pilot exception applies. Metadata preparation
and validation run on compute20 with16 CPUs; templates retain64GiB.

## Authorities and identity

Planning needs all three actual frozen manifests, with exact common/order hashes:

- COMMON_POPULATION_V1_FROZEN: unique molecule_id and bool common_population,
  membership_tables pins, TRAIN/ROUTINE-VAL roles and roles_manifest_sha256;
- CONFORMER_ORDER_V1_FROZEN: order_tables (or tables) long parquet, fields
  molecule_id/geometry_source/method/rank/geometry_id. fixed_random uses0-based
  rank; physical integer IDs need not be contiguous;
- CANONICAL_GEOMETRY_MAP_V1_FROZEN: map_tables pins, exact order_manifest pin,
  opaque geometry_id, original int64 sprime_conf_idx and explicit physical
  source_path/SHA/bytes/row/format/member/native_anchor_record_id/atom-order
  mapping. A native trace is never a UFF physical identity.

The order manifest must explicitly declare random_identity_basis. For
canonical_sprime_conf_idx it uses that preserved original/append integer in
SB2 stable_key. For original_physical_conformer_identity the map must explicitly
provide random_order_conformer_id. No guessed rehash is allowed. The complete
fixed-random ordering is checked using seed20261025 and exact SB2 UTF-8 formula
`data-v1-conformer-order:<seed>:<mid>:uff_sprime:<identity>`. Only first2 ranks
are selected. Root/SB2 are preparing a new finalizer retaining old accepted IDs
and stable append IDs; this code does not modify the frozen older finalizer.

Baseline validators and the new formal export require nonnegative int64 UFF IDs.
The frozen pilot's old int32 column is not modified. Opaque/NULL
N1 supplementary IDs cannot be put into that column or make these validators
accept an expanded view. N1 remains common, original_N and S-prime counts stay
unchanged, and pending_two_real_geometries remains in the full denominator.
The plan may describe a BASELINE_READY_COMMON_SUBSET, but ALL_COMMON cannot be
approved or accepted while any common molecule lacks two real accepted views.
No molecule is dropped, no old coordinate is copied to invent a second, and no
P label/zero is used to fill a missing P-prime value.

Future N1 binding must be separately reviewed: a new view/version and explicit
original source idx(nullable trace), supplementary physical namespace, opaque
geometry_id, real candidate/source SHA, new engine integer bridge, stable order
and label mapping. The SB2 n1_pprime2 proposal has no production generator and
is not an accepted binding. This baseline runner intentionally rejects it.

## Pilot, budget, stable raw and once ledger

Before any formal science, pilot_review recomputes the unchanged pilot gates
from a pinned real result, actual raw parent sacct row and actual QC parquet:
2000 unique conformers/timings, all12 outcomes each, >=99.5% all-task success,
parent COMPLETED0,16 exited/joined workers and parent AllocCPUS*ElapsedRaw /2000
<=11.7. The denominator includes failures and all retention/setup/export cost.
It rejects timing/summary/QC disagreement. Root review schema is:

    schema: PPRIME_REAL_PILOT_ROOT_REVIEW_V1
    status: APPROVED
    result: {path,bytes,sha256}
    raw_parent_sacct: {path,bytes,sha256}
    failure_categories_reviewed: true
    all_2000_elapsed_times_reviewed: true

The new `../retention_v1/` execution adapter must run this real pilot with the
Root-accepted stable raw rule, not the old20-only retention. Formal sampling
uses the same physical-key SHA256 threshold100/10000/seed20261010. Its source
stratum is source_shard_id from the original source_plan plus fixed heavy bins;
legacy_engine_file_group is preserved separately for the old engine guard.
Sampling never uses batch/rank/population size or a newly renamed ID. Actual
per-stratum hit rates are reported; this is approximate1%, not an exact draw
or the old WP5 sample identity. The original20 union stable pilot hits retain
all12 raw outputs; original20-only rows are extra reproduction retention.

Accepted original S-prime uses its explicit original_sprime_conf_idx. Generated
fill requires an additional PPRIME_PHYSICAL_AUDIT_IDENTITY_MAP_FROZEN_V1 manifest
binding common_manifest and geometry_manifest, with identity_tables parquet:
geometry_id,molecule_id,physical_identity_json. The identity is
`{"namespace":"data_v1_fill","seed":<real>,"candidate_id":<real>,"task_key":<actual64hex>}`.
Seed/candidate must equal the frozen physical map. A missing map blocks planning;
there is no guessed namespace, native-anchor substitution or N1 default.

import_pilot validates all2000 real base/QC rows, exact coordinates,12 statuses,
stable policy/source audit and durable output bundles. It registers every pilot
scientific input once, including failed outcomes. Reused failures retain their
actual values/statuses/masks; they are not automatically recomputed. Formal
reuse requires the same source atom order, clean coordinates, protocol and
perturbation record_id. Because the old noisy seed includes record_id, equal
clean coordinates alone do not prove reusable scientific input.

Each scientific once_key is SHA256(canonical JSON [domain,molecule,atom-order
SHA,coordinate SHA,protocol SHA,perturb_record_id]). A record owns exactly12
tasks. The exclusive STARTED ledger is written before any task; an existing
STARTED/failed/unknown/closed key forbids automatic retry. Actual outcomes are
stored in separate immutable sidecars. Pilot ledger import also uses exclusive
creation; partial import is an unknown state for Root review, not deletion/retry.

Root's formal review must bind the exact plan/common/order/geometry/pilot review:

    schema: PPRIME_FORMAL_ROOT_REVIEW_V1
    status: APPROVED
    plan/common_manifest/order_manifest/geometry_manifest/pilot_review: pins
    pilot_import: exact closed real-pilot import pin
    approved_scope: ALL_COMMON or BASELINE_READY_COMMON_SUBSET
    approved_total_core_hours_cap: finite number >= plan estimate
    approved_over_500_core_hours: true when estimate >500

No N1 expansion flag enables this baseline implementation. The plan conservatively
estimates all baseline records from the actual pilot allocation rate plus the
already incurred pilot allocation; actual accounting deduplicates pilot reuse.
Every formal batch's actual parent cost must be <=1.5x its pilot-based estimate.
Failure/timeout/cancelled cost is retained. A failed gate means report/stop next
dispatch, not change units or substitute child CPU time.

## Stages and CLI

Use Root-integrated absolute paths, actual SHA values and fresh ordinary
preflight receipts. No CLI below submits another job.

    PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
    REPO=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository
    BASE=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025
    SRC="$REPO/workflows/data_v1_final/pprime/formal_common_v1"
    CFG="$REPO/configs/data_v1/pprime/formal_common_v1.json"

First close the real stable-retention pilot with the original close_pilot.py and
write Root's actual pilot review. Then on compute20:

    "$PY" -B "$SRC/import_pilot_v1.py" --config "$CFG" \
      --pilot-review "$REAL_PILOT_REVIEW" --root-preflight "$IMPORT_INTENT" \
      --output "$BASE/artifacts/pprime_formal_common_v1/pilot_import_v1"
    "$PY" -B "$SRC/prepare_v1.py" plan --config "$CFG" \
      --pilot-review "$REAL_PILOT_REVIEW" --common-manifest "$COMMON" \
      --order-manifest "$ORDERS" --geometry-manifest "$GEOMETRY_MAP" \
      --audit-identity-manifest "$EXPLICIT_FILL_AUDIT_IDENTITIES" \
      --root-preflight "$PLAN_INTENT" --output "$NEW_PLAN_DIR"
    "$PY" -B "$SRC/prepare_v1.py" materialize --config "$CFG" \
      --plan "$NEW_PLAN_DIR/plan.json" --batch-id "$BATCH" \
      --root-preflight "$MATERIALIZE_INTENT" --output "$NEW_PREPARED_BATCH"

Plan tasks are pointer metadata; coordinates are not copied for the entire
population. A materialized batch is <=512 molecules/1024 conformers. It hashes
each selected physical source once, verifies row index, strict SUCCESS&&converged,
anchor and atom-order, and reads parquet row groups through a bounded2-entry
cache. Maximum decoded row-group/JSON packet is512MiB, otherwise explicit
resource rejection. Gzip decoding is bounded; there is no new pickle format or
fallback reader. Actual old LMDB is opened only by the pinned scientific worker.

After Root reviews the actual pilot and plan (including >500h), future ordinary
QM on14-19 would use:

    "$PY" -B "$SRC/run_batch_v1.py" --execute --config "$CFG" \
      --prepared "$NEW_PREPARED_BATCH" --prepared-sha256 "$ACTUAL_PREPARED_SHA" \
      --pilot-import "$PILOT_IMPORT_JSON" --root-review "$FULL_ROOT_REVIEW" \
      --root-preflight "$QM_INTENT" --output "$NEW_BATCH_OUTPUT"

There are16 spawn workers with private node-local scratch and explicit joins.
No process termination or automatic retry is used. Once a wall/cost admission
bound is reached, stop starting records and naturally drain in-flight calls.
Every result preserves all12 outcomes or remains explicitly incomplete. Raw
all12-stable-hit and every failed-call SHA proof is read back independently.
The new formal exporter is a separate derivation of the pinned pilot writer,
using the same WP5 float64 families plus canonical geometry/view/once mapping.
Every written field/value/type is read back against producer rows. Q02 remains
NULL/N/A for cross-geometry source-PM7-HOF subtraction; other QC is unchanged.

    "$PY" -B "$SRC/close_batch_v1.py" --config "$CFG" \
      --result "$NEW_BATCH_OUTPUT/result.json" --raw-sacct "$ACTUAL_PARENT_SACCT" \
      --output "$NEW_BATCH_CLOSURE_JSON"

Prepare a JSON list of all prepared.json pins, and a JSON list of all actual
batch closure pins. A completely imported pilot-only batch needs no QM job.
Final indexing consumes the expected scientific-key set from all prepared
batches plus selected imported pilot outcomes; duplicate keys/parents reject.
It lists all missing/extra rows and all failed actual parents. Family references
to the pilot have an explicit required record-ID filter; they are not copied or
silently treated as the entire formal population.

    "$PY" -B "$SRC/finalize_v1.py" index --config "$CFG" \
      --plan "$PLAN_JSON" --root-review "$FULL_ROOT_REVIEW" \
      --pilot-import "$PILOT_IMPORT_JSON" --prepared-index "$ALL_PREPARED_PINS_JSON" \
      --closures-index "$ALL_ACTUAL_CLOSURE_PINS_JSON" \
      --root-preflight "$INDEX_INTENT" --output "$NEW_INDEX_DIR"

An index is not final acceptance. `finalize_v1.py accept --config ... --data-index
... --validation ... --root-preflight ... --output ...` requires complete common
coverage including N1 and PPRIME_FULL_VALIDATION_CLOSURE_V1 / ALL_VALIDATION_CLOSED
bound to the exact index SHA. Its exact gates are:
wp5_same_audit_passed, float64_family_readback_passed, all_raw_retention_verified,
outlier_scan_1_5_completed, outlier_stop_threshold_resolved,
P_vs_Pprime_distribution_and_correlation_completed,
independent_Pprime_TRAIN_normalization_completed, vector_frame_actual_audit_passed.
Each must be true and have pinned actual reports in sources keys wp5_audit,
float64_readback, raw_retention, outlier_scan, P_vs_Pprime, Pprime_normalization,
vector_frame. This is a handoff schema for actual SB3/Root evidence, not an
implementation or claim that those analyses have occurred. Original1.5 stop
thresholds/user decisions still apply; a JSON boolean alone cannot replace a
missing source report. Source report semantics require Root review.

Known current blockers: no real2000 QM pilot, no frozen final common/orders/map,
no approved/real N1 second-geometry binding, no actual full P-prime data or
post-QM scans/distribution/normalization/frame results. Thus full completion
cannot currently be declared. The8 controlled tests do not claim real-data
validation; run them on compute20 via Root's stable session.
