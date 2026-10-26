# Explicit closed and synced Native long archives

Source only. Nothing submitted or executed by the preparer. Root remains the
only submitter. This tool accepts 1..3 explicit successful Native long segments,
using their strict full-log audit, actual audit C0 and independent Root sync
closure. It creates a fresh append-only archive batch; old56, native7 and all
previous native_long_* indexes are read/bound, never rewritten. A selection
already present in one of those indexes is rejected. More than3 is rejected;
four new segments need two explicitly chosen batches, not a silently expanded cap.

The old v7 CLI cannot directly do this: its allowed jobs are fixed and it
rewrites the old index/offline flag. This thin adapter instead reuses exact
v7.copy_ref/helper.source_manifest, frozen native7 normalize/metrics_csv/latest/
curve_page and literal749. Four existing export regressions run once inline in
the actual archive allocation. There is no SDK decoder, native framing scan,
online API, model, checkpoint load, JIT/RPC/dispatcher/daemon or additional QA
parent. The historical profile/FAILED/A06 cases are excluded from this tool.

## Exact input

Root writes one bounded JSON request:

    {
      "schema": "native_S_explicit_closed_synced_archive_request_v1",
      "archive_name": "native_long_EXPLICIT_UNIQUE_BATCH_NAME",
      "Root_registered_reservations_path": "/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/ACTUAL_ROOT_REGISTRY.json",
      "sync_Root_closure": {"path": "ACTUAL", "bytes": 0, "sha256": "ACTUAL"},
      "entries": [
        {
          "verification": {"path": "ACTUAL", "bytes": 0, "sha256": "ACTUAL"},
          "audit_batch": {"path": "ACTUAL", "bytes": 0, "sha256": "ACTUAL"},
          "audit_supervisor": {"path": "ACTUAL", "bytes": 0, "sha256": "ACTUAL"},
          "actual_audit_C0": {"path": "ACTUAL", "bytes": 0, "sha256": "ACTUAL"}
        }
      ]
    }

Those placeholders are documentation, not valid data or future successes.
The four-key entries are exactly the existing native_closed_long_sync_manifest_v1
entries. Root can reuse the entries from its actual sync-plan
explicit_manifest.json, selecting1..3 and preserving complete raw refs.
The Root registry is explicit current authority; the tool does not guess a newer
reservation feed from a filename/version. No new reservation is made.

Supported existing evidence is fixed by source:
native_S_long_segment_log_audit_batch_v1,
native_S_long_segment_full_log_comparison_v1,
and native_S_explicit_sync_Root_closure_v1 / ROOT_CLOSED_C0_METADATA_VERIFIED.
The already-tested frozen long_common.proof_rows validates the same-job
proof/BATCH/actual-C0/supervisor, source inventory, metadata graph, explicit
steps and clean EOF. The new thin binding requires model/native success and
the exact selected sync record, original SDK raw ref, actual API finished
state/count/first/last, source stability and sync supervisor. It reads the
sync record's actual_remote_metadata fields, not a fabricated old-index schema.
Actual source seed/precision for the family directory comes from the frozen
configuration.contract, not the path spelling.

## Root prepare and immediate CPU submission

Use actual machine SHA references, no manual transcription. Let P be
/share/home/zixiao/descriptor_analysis, N=P/runs/model_v3_20261026,
O=P/runs/model_v3_20261025, PY=/share/home/zixiao/.conda/envs/chemprop/bin/python,
S=N/native_closed_long_archive_v1. After Root's stdlib AST, shell syntax and
raw source-pin checks:

    PY -B S/archive_closed_long.py --source-pins-sha256 PIN prepare \
      --request ACTUAL_REQUEST --request-sha256 ACTUAL_REQUEST_SHA \
      --output N/FRESH_PREPARED_DIRECTORY

This is login metadata only. It does not open/hash SDK or scientific journal.
It revalidates exact proofs and current original indexes, queries actual sacct
for only selected model/audit/sync jobs, then publishes real quota and known
Root holds with the original0..120s age, positive-limit quota parsing,
64GiB headroom plus separate2GiB job allowance. A stale receipt is rejected;
prepare immediately before actual submission through the original helper:

    PY -B O/submit_cpu_task_v2.py --node compute-0-13 --memory-MiB 16384 \
      --script O/run_native_closed_long_archive_v1.sbatch \
      --bindings N/FRESH_PREPARED_DIRECTORY/BINDINGS.json \
      --output O/FRESH_ACTUAL_SUBMISSION.json

Actual idle/capacity, all-user85%, MemAvailable and quota admission are the
unchanged original helper's responsibility. This package adds no queue
mechanism. Pre-SBATCH refusal creates no archive; Root may prepare fresh
metadata later rather than carry an expired quota across a wait. The explicit
archive output is DEST/archive_name and must not exist; failed partials remain.

## CPU export and limits

The actual CPU worker checks16CPU/cpu partition/UID1278/node/job cgroup/noCUDA,
the exact prepared source/request/proofs/cohort/prior indexes and fresh quota.
It runs the original four zero-skip export tests, then for each selected run:

* Hash-checks/copies only the original selected SDK/log directory, materializing
  allowed source links with the exact old source_manifest/copy_ref rules.
* Copies the original independent metadata proofs and the full scientific
  journal. Rechecks original SDK/log/journal raw SHA before/after copying.
* Uses literal749 and the original frozen normalize function, demanding every
  explicit committed global step and the independent normalized-history digest.
* Exports every scientific field to typedCSV (JSON literals, absent cell empty,
  explicit null remains null), complete normalized journal, last values and the
  original unsmoothed interactive curves. Only the breadcrumb label changes
  from "Seven-run archive index" to "Native long archive index"; numeric/CSV/
  curve semantics remain original.

No source artifact moves/changes, no sync is performed and existing online
proof does not make these new local files independently closed. New index,
source manifests and result all state LOG_ONLY/noB/no scientific acceptance.
The worker produces an entry append proposal, not an automatic entry edit.
Root must close actual CPU C0, supervisor/source/cleanup and independently
review the actual pages before appending the proposal to the unified entry.

Budgets remain16CPU16GiB/20min Slurm,900s original CPU supervisor/RSS12GiB,
whole/private2GiB, batch archive256MiB, original archive2GiB and physical forest
104GiB. Per source SDK/log<=128MiB; exact old exporter line/row/normalized caps
remain. The750s worker finalization reserve and original supervisor reserve
remain. Failed attempts, pending copies, SDK copies/CSV/HTML, logs and private
scratch stay in those budgets. No deletion/retry/cancellation or guard expansion.
A child result explicitly waits for actual outer C0; nothing claims future
B20k/scientific acceptance, final D authority, final recipe or guide completion.

