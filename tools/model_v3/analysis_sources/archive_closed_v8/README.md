# Archive v8: minimal546/primary512 additions — prepared, not executed

v7 is unchanged: actual CPU557 passed24 tests and archive562 completed with41
task-index entries. v8 imports that exact implementation and reader by SHA,
reuses its source/copy/owner/index/receipt checks and the same task archive lock.
No Slurm/SSH is submitted by this tool, no frozen scientific tree is edited,
and no original artifact is moved/deleted. Root owns all tests and submission.

## New cases

- **546:** `A_a01_backbone_off_4520546`, actualFAILED1:0. Its run_status reports
  MemoryError `A diagnostic exceeded85% of physical GPU capacity`; the actual
  supervisor reports child_exit1. This is a soft-cap refusal, so stdout CUDA
  OOM is **not** required. Two original SDKs are copied and scanned to actual
  EOF/decode status. Committed HISTORY count is measured, not predeclared zero.
  No independent mirror check is claimed where none exists. Native/incomplete
  closure is explicit, and both numeric/timing gate flags remain false.
- **544:** `primary512_a00_dev9_v1/evaluation`, actualCOMPLETED0:0. Independent
  verifier565 passed37 CPU tests; actual566 completed0:0. v8 requires a fresh
  receipt proving544/566C0 and byte-checks the566 outer supervisor too. The
  original `VERIFIED_AND_REPORTED_PENDING_OUTER_TERMINAL` closure text remains
  unchanged; the actual outer success is separately bound.

549 is not included because it was still running when this source was prepared.

## Complete primary history and provenance

The actual primary certificate is22949B, SHA
`7b2dfeb176351b0a3076519f3afcfa2c0a3b716f7be9daf352950274541677eb`.
It establishes170295 native protobuf packets,56738 committed HISTORY rows,
cleanEOF/exit0, reference_kindprimary, H0_dimension512 and6 layers. The original
42,838,754B SDK SHA is
`5b644cbd12031ef7f4984a9c18e86d169358ec1d07f8ee71ab419d525c2f90c8`.
Original result/guard/request/launch_spec, export/source/admission chain, all
certificate refs, compact report refs and reader/schema/version are rechecked.

The tested primary verifier/scope/export-admission code is imported read-only,
with full source pins. Its exact native comparison is rerun across **all** rows,
every metric, explicit step, initial config, final summary, run ID/name and
exit/clean EOF. The resulting packet types/counts, history count, canonical
stream bytes/SHA and every series statistic must equal the actual566 certificate.
The old50000-packet exporter is never used for primary512.

Because566 kept only a canonical hash/series report, v8 now writes the entire
canonical normalized history and complete long-form `step,key,value_json` CSV.
The CSV scalar count must equal the sum of all certificate-series counts. No
subsampling or last-point-only export is permitted. A readable HTML links the
full CSV/history and fresh verification. The complete original journal and raw
SDK, source metadata, original certificate and compact report remain available
inside the task archive; original source paths stay unchanged.

The198,753,232B A00 checkpoint is a **hash-only reference**: Root explicitly
authorized streaming rehash under the existing512MiB checkpoint bound, with
inode/size/mtime checks. It is never deserialized or copied into the archive.
Other refs use the original128MiB bound. The tested readonly export admission
also rechecks the same unique checkpoint; a metadata-aware cache avoids extra
rehashes by this wrapper when physical identity has not changed. All selected
archive source bytes remain<=128MiB, full generated exports<=96MiB, and the
complete new case<=256MiB. There is no target-store/model/prediction access.

This is the primary512 **short500 A00 development panel**. It does not establish
formal-pretraining completion, convergence, architecture selection or a final
downstream result. Those scope flags remain false in manifests and HTML.

## CPU tests and bounded archival command

New targeted tests are prepared, not run: every scalar/CSV value and canonical
stream, all original-certificate comparisons, summary/all-metric mismatch,
>50000 ancillary-packet behavior, duplicate/missing step and byte limits,
failed546 dynamic0/1/3-history observations, missing native exit, packet bounds
and changed hash-only provenance identity. The real v7 SDK24 tests and primary
verifier37 tests are reused rather than rewritten.

```bash
SOURCE=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/archive_closed_v8_source
# Root: actual available CPU node only,>=16CPUs; CUDA_VISIBLE_DEVICES empty.
$PY -m pytest -q "$SOURCE/test_archive_v8.py"

# After CPU checks, Root supplies a <=120s fresh sonmi quota/closed-job receipt.
$PY -u -B "$SOURCE/archive_closed_runs_v8.py" \
  --source-pins "$SOURCE/source_pins_v8.json" --source-pins-sha256 "$SOURCE_PINS_SHA" \
  --quota-closed-receipt "$RECEIPT" --quota-closed-sha256 "$RECEIPT_SHA" \
  --expected-node "$ACTUAL_CPU_NODE" --expected-partition cpu --jobs 4520546 4520544
```

Use the same receipt shape as v7. Required exact closed lines:546 FAILED1:0,
544 COMPLETED0:0 and566 COMPLETED0:0. Every new case repeats the120-second
freshness/quota checks before publication; `--jobs` permits separate fresh
batches if needed. Suggest16CPU/16GiB/15min, subject to Root's live site/quota
checks. CPU-only tasks must use CPU nodes, not GPU nodes. The existing lock and
`(job_id,run_id)` dedup preserve all41 old entries. Expected new index entries
are two546 SDKs plus one544 SDK, with actual counts checked during execution.

All SDK artifacts remain offline/unsynced. The tool prints aggregate archival
status only and does not print native scientific payloads.
