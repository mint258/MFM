# Recovered label book, source-only candidate

This new namespace never rewrites old book/leases/cache or makes 4521904 C0.
The old parent remains TIMEOUT/0:0, 14412s x16 =230592 core seconds. No new
window may start from a merely guessed cursor. No automatic retry, lease expiry,
unhold, controller, Root approval, masks release, D4 release or normalization is
implemented here.

Prerequisites are actual 4522748 C0 **and** its complete verified inventory,
unchanged old member frames, every committed window/part verified, no inventory
error or original 1% quality HOLD. C0 alone is insufficient. Root must separately
sign exact prefix selection and fresh resource review. Pending inventory creates
no plan, future reference, READY assertion or book. Missing worker04/13 JSON
never proves an unstarted window.

CPU contracts use Main UID1278, node17, 16CPU, no requested memory, central
cpu_auto_memory_queue_v2 fresh actual primary/argv/source proof. Six meaningful
pure boundaries and inverse checks run before DATA. Child has not executed
Python, AST checks, tests, scientific bodies, SSH or Slurm; Root must run them
on a real allocation. The runtime inverse checks compare bytes and AST of the
copied sidecar resolver and full coverage function to frozen originals. Only
historical locator/current SHA provenance and the origin loop/HOLD gate differ.
The science worker, initializer, parser, tree/mask functions, coverage math,
quality denominators and 1% threshold remain the original functions/objects.

Root small review contracts

- Selection: schema ROOT_EXPLICIT_LABELS_SEED_PREFIX_SELECTION_V1, status
  ROOT_APPROVED, reviewer root, reason; inventory_receipt_reference; explicit
  selected_prefixes=[{file_id,end_physical_row},...]. Only complete window
  boundaries inside the actual old committed range are legal. Selecting less
  than any consumed range preserves that source as HOLD; it cannot be redone.
- Resource: original FULL_LABEL_PROJECTION_ROOT_REVIEW_V1 contract plus
  recovery_schema ROOT_LABELS_RECOVERED_BOOK_RESOURCE_REVIEW_V1. It must retain
  the original actual bounded parity/profile/storage/Sprime evidence and master
  pin required by review_contract. Also inventory_receipt_reference,
  seed_selection_reference, retained_old_logical_ceiling_bytes=34359738368,
  approved_whole_cache_cap_bytes>=8GiB for **new** production,
  seed_output_cap_bytes=4..8GiB, new_global_logical_cap_bytes >= old32GiB + seed
  + new production + closure2GiB; budget_basis
  OLD_RETAINED_SEPARATE_FROM_NEWBOOK_PRODUCTION, old_unknown_charge_refunded=false,
  cost_overrun_action=REPORT_AND_CONTINUE, final_masks_authorized=false,
  final_common_D4_authorized=false. Explicit seed_wall_seconds 300..172800 and
  300<=softwall_margin_seconds<production_wall_seconds<=172800 are ceilings,
  not predictions. Approved inode cap and all other unwritten storage upper
  bounds remain explicit. Logical old32GiB is not an actual byte inventory and
  is not reserved again as future output; retained physical space is already
  included in actual shared-account quota used/free.
- Every next/close intent needs a separately signed
  ROOT_LABELS_RECOVERY_FRESH_DISPATCH_QUOTA_REVIEW_V1: ROOT_APPROVED/root/reason,
  UID1278, endpoint202.38.247.57:22, adoption_summary_reference, actual
  quota -v -u zixiao argv/rc0/raw_quota_reference, observed_unix_seconds with
  age0..120s, parsed account_free_bytes, and identical other-storage upper bound.
  Required free >=200GB + remaining new-production reservation + closure2GiB
  + every other outstanding cap. Seed additionally reserves its own output.
  No quota/freshness fallback or publisher renewal is added.

Shortest Root metadata / CPU sequence

Use Linux Main login only for this metadata helper, with ROOT pointing at the
actual repository and PY at the original chemprop Python. These commands are
interfaces, not populated executable approvals or future pins.

    $PY -B -m workflows.data_v1_final.labels.full_recovery_book_v1.metadata seed-candidate \
      --inventory-receipt REAL_RECEIPT --inventory-proof REAL_PROOF \
      --inventory-submission REAL_SUBMISSION --inventory-accounting REAL_ACCOUNT \
      --resource-review ROOT_RESOURCE --selection ROOT_SELECTION \
      --metadata-directory NEW_CONTROL_DIR --output NEW_SEED_ARTIFACT_DIR

Root inspects the unsigned candidate, writes its exact independent central scope
review, then runs `metadata finalize-scope --metadata-directory DIR --scope-review
ACTUAL_ROOT_SCOPE`. This emits stage_spec.json and does not submit. Root uses the
existing central helper on node17; execution primary is:

    $PY -B -m workflows.data_v1_final.labels.full_recovery_book_v1.seed \
      --plan ABS_PLAN --startup-proof ABS_FRESH_PROOF --output ABS_NEW_OUTPUT

After real seed C0/account/raw, `metadata next` requires --seed-receipt,
--seed-proof,--seed-submission,--seed-accounting plus --root-prepare-next --reason,
--quota-review,--metadata-directory,--output,--batch-name,--wall-seconds and
optional --output-cap-bytes (8..32GiB), --max-RGs (1..1024). It writes one immutable
new-book intent and unsigned stage. A failure after claim preserves that intent;
there is no re-claim/reset path. Root separately reviews/finalizes/submits it:

    $PY -B -m workflows.data_v1_final.labels.full_recovery_book_v1.run \
      --config ABS_CONFIG --startup-proof ABS_FRESH_PROOF --output ABS_NEW_OUTPUT

The wrapper calls original full_projection_v1.run.main directly. Its softwall
thread only writes the original latched STOP for new windows and naturally
drains running windows; no signal/kill/cancel is added. The original six full
organization fixtures also remain. Hard TIMEOUT still cannot be accepted, and
successful partial tiles require actual C0, no errors/UNKNOWN tickets/quality
HOLD and exact cursor accounting. `metadata accept` needs the four seed inputs
and --manifest,--proof,--submission,--accounting of the actual new batch. It
never accepts 1904 or a fabricated producer receipt. One batch chain is serial.

Only after all2208 sources are complete and no source HOLD remains, Root may use
`metadata close` with the four seed inputs, --quota-review,--metadata-directory,
--output,--wall-seconds; review/finalize/central submit as above. CPU primary is
`...full_recovery_book_v1.coverage --config ABS --startup-proof ABS --output ABS`.
Closure output cap is2GiB including inventory/coverage files and observer reserve.
Current whole SHA reads of typed parts are CPU work and explicitly counted;
F64 numeric bodies are not redecoded by this final part-inventory pass. Original
inventory/actual writer exact numerical reopen lineage stays attributed.

Coverage seam for D4

`manifest.json` schema LABELS_RECOVERED_FULL_SOURCE_COVERAGE_V1 retains original
FULL_NUMERIC_SOURCE_COVERAGE_OBSERVED_NOT_FINAL_MASKS / quality-HOLD semantics.
It has accepted_origins, origin_counts (units=producer/adoption origins),
actual_parts_inventory_reference (JSONL DATA, max512MiB), actual_part_count,
actual_part_rows, actual_part_whole_SHA_bytes_read, held_source_count,
unresolved_consumed_count, unverified_part_count, quality_hold_fields,
final_mask_release=false, D4_release=false.

Each accepted origin has origin_id/origin_type/authority:

- TIMEOUT_ADOPTED_CLOSED_WINDOWS: old_parent_actual_references, immutable old
  TIMEOUT state, inventory_actual_references, seed_actual_references,
  seed_selection_reference/resource_review_reference, adoption_summary_reference,
  adoption_membership_reference and sidecar_reference. Old producer is never C0.
- ACTUAL_C0_BATCH: actual_parent_chain, producer_manifest_reference,
  closed_window_index_reference, sidecar_reference and actual_parent_C0=true.

Each JSONL part records origin_id/type, file_id/source_reference, physical lo/hi,
range_id/ticket/window_receipt_reference, reference, row_kind/task_code/rows,
typed_stream_sha256, current_frame/current_whole_SHA_verified and honest numeric
readback provenance. Every part path must be its exact old/new registered output
with original ticket-derived basename, current full SHA and stable same FD.
Original interval/role/physical classifications and exact all14tasks+base union
are checked by the unchanged full coverage math. No source/part is silently
omitted. held_source/unresolved_consumed/unverified_part must all be integer0,
quality HOLD empty, plus a separate actual coverage C0 and independent Root
release, before D4 can consume this inventory. A partial report cannot release
masks/Common/normalization.

Limits: source HOLD has no resolution API in this namespace; unresolved old
consumed history blocks full closure. New-book control uses the original bounded
small-metadata limits; a later expansion needs new review, not an automatic cap
increase. Wall and byte ceilings do not forecast full completion or guarantee a
natural drain fits the remaining scheduler wall. All old/new failed costs remain.
