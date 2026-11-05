# Closed model-v3 archive v7 — prepared, not executed

Only Root submits or runs this CPU-only metadata tool. No SSH, sbatch, model,
target store, weight deserialization, W&B login/API/sync or original-file deletion
is performed. All implementation lives in this new external directory. The old
v6 archiver, fixed helper, scientific trees and original outputs stay unchanged.

The task archive remains
`runs/phase1_full_corpus/wandb_archive/model_v3_20261025`. v7 takes its existing
`.archive.lock`, reads the index **inside** that lock, preserves all old entry
objects and adds each `(job_id,run_id)` once. A conflicting target is rejected.
Each new case is published from its own fresh `.pending` directory only after
source/copy hashes and bounds pass. Failed pending evidence is retained. All
original SDKs/logs/checkpoints remain at their original paths.

## Exact cases and meanings

| Job | Case | Actual expected terminal | SDKs | Committed HISTORY rows |
|---|---|---|---:|---:|
|4520438|a_native_control_4520438|COMPLETED 0:0|2|500 each|
|4520457|A_a06_fused_4520457|FAILED 1:0|2|500 each|
|4520485|A06_optimizer_diagnostic_4520485|COMPLETED 0:0|1|101|
|4520486|A_a00_control_4520486|COMPLETED 0:0|2|500 each|
|4520513|precision_synthetic_SDK_4520513|COMPLETED 0:0|1|6, explicit steps0–5|
|4520514|precision_synthetic_SDK_4520514|COMPLETED 0:0|1|4, explicit steps6–9|
|4520482|c2_run_4520482|FAILED 1:0|1|0; incomplete native exit may be retained|
|4520525|A_a05_compile_4520525|FAILED 1:0|2|0; incomplete native exit may be retained|
|4520487|existing independent B3 verification|COMPLETED 0:0|1 original|56738, already verified|

4520544 is intentionally absent because it was not closed at preparation time.
Failed457 remains a failed original numerical gate; successful SDK close does
not change that status. 485 is synthetic-gradient optimizer diagnosis with0
model forwards/training steps. 513/514 are synthetic harness/recovery evidence,
not a real D5 proxy. B3 is historical384-dimensional sanity, not primary512.

For525, `primary_cause` binds the original supervisor JSON and stdout hashes:
the supervisor's first failure is MemoryError at the85% physical-capacity cap,
and stdout contains the actual `torch.OutOfMemoryError`. The original
`run_status.failure=null` plus cleanup ConnectionResetError does not imply
success. Both numerical and timing gates remain false in this failure receipt.

## Reader and mirror checks

The fixed `scripts/archive_phase1_wandb_v2.py` is pinned to
`3fbd821e85fe093e037c4b45e6bf666d08533eb07edaabf0435d5b8b1e8f975a`.
Its source manifest, SDK-link allowlist, owner checks and ordinary small-run
CSV/HTML export are reused. v7 first performs independent native/mirror checks.

`bounded_history_v7.py` has distinct limits:500000 total protobuf packets,
100000 committed HISTORY rows,128MiB source SDK,4MiB per packet,64KiB per mirror
line,64MiB normalized history and180s per native scan. Reaching a packet/history/
byte/wall bound raises a budget error, including on a failed source; it never
becomes an EOF or truncation certificate. The reader consumes to clean EOF and
checks run ID and native exit. Failed zero-history sources may instead receive
an explicit incomplete/raw-only certificate; no missing native exit is invented.

Scientific payloads are flattened into unambiguous paths from nested JSON or
native nested_key items. Duplicate/overlapping keys, missing/extra scientific
fields, duplicate/out-of-order steps, unknown internal fields and NaN/Inf are
rejected. Source JSON numeric types are restored exactly, with no numerical
tolerance; bool cannot match integer1. Explicit SDK `_step` must match the mirror.
Precision mirror `commit` must be true, and an uncommitted native partial-history
request cannot certify a successful segment. Optimizer mirrors originally have
no commit member: their native committed HISTORY packets and pinned source
`log(...,commit=True)` are the evidence; v7 does not pretend the mirror had it.

The A mirrors are matched to the native `paired_role` in initial SDK config;
both reference and candidate must be present. The fixed legacy exporter is used
only below its own50000-packet bound; otherwise v7 uses the already verified
normalized stream for compact export. Failed/decode-incomplete sources avoid
the legacy parser. **HISTORY/commit counts are never total SDK packet counts.**

513/514 also get a separate recovery certificate. It binds identical member/
provider/source contracts, native SDK IDs, new-lineage parent ID, original
checkpoint COMPLETE/state/trainer-marker/payload hashes, samples4→8,
updates2→4, log cursor6→10, exact ordinals0…7 and preserved validation0/2 without
replay. The payload file is hashed only, never loaded. The SDK scientific
comparison remains a separate prerequisite; mirror alone is not SDK durability.

## Existing B3 certificate, no target recomputation

487 reuses the actual independent v2 certificate
`a8111a12425d7c4f8421ef645fac222def343727bc93e7ff5b1d446400a8dddf`,
verifier source
`83d322d67184e75d7f11cd55ef597762744bb0b1a3a0137c917b0afe6f120e6b`,
source pins, before/after closure and original reader/source bindings. Its
42,875,881B native SDK,14,296,086B normalized history and compact report are
copied with hashes. The certificate already establishes170299 native packets,
56738 HISTORY rows and clean successful native exit. v7 does not feed this SDK
to the old50000 reader or recompute any target/prediction. The original false
core-verification flag is retained alongside the independent verified certificate.

## Admission, tests and CLI

Every case has<=128MiB selected source/evidence inputs and<=256MiB new archive.
No weight/checkpoint tree is copied to the archive. Quota must leave>34GiB free.
The source manifest, each copied byte and original before/after binding are
checked. Original SDK record source files and all archived paths must be owned
and ordinary; fixed known SDK log-link targets are dereferenced by the helper.

Root supplies a fresh SHA-bound sonmi receipt. The same receipt includes quota
and exact closed-job lines and must be<=120s old at admission/publication:

```json
{"host":"sonmi","uid":1278,"returncode":0,"unix_time":0,
 "stdout":"actual quota -v -u zixiao output",
 "closed_jobs":{"4520438":"4520438|COMPLETED|0:0"}}
```

Supply all selected IDs with their actual expected state/exit. B3 additionally
requires original evaluation4520437 COMPLETED0:0; either precision segment
requires both513/514 closed because the recovery certificate uses both. No
receipt is fetched by this script. If a queued job starts too late or a slow
copy makes the receipt stale, publication stops and pending evidence remains.
Use fresh receipts in separate bounded batches via `--jobs` as necessary.

The CPU task must have>=16 CPUs, CUDA_VISIBLE_DEVICES empty, actual cpu
partition and an exact `--expected-node` binding. GPU nodes20/21/22 are rejected.
Use Root's currently available CPU node and normal CPU partition/account; do
not reuse v6's historical node20 sbatch target. Suggested admission is16CPU/
16GiB/15min, refined by Root's live resource/quota checks.

Tests are **prepared, not run**. The new file contains real offline SDK nested/
typed two-row roundtrip, corrupt/missing/extra scientific values, steps/commit/
runID/exit,>50000 ancillary-packet separation, budget/decode handling, index
preservation/dedup and recovery cursor/ordinal/parent/no-replay cases.

```bash
# CPU Slurm only; existing chemprop Python/deps, no GPU allocation.
SOURCE=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/archive_closed_v7_source
$PY -m pytest -q "$SOURCE/test_archive_v7.py"

# After Root tests/checks and supplies the fresh receipt/source pins:
$PY -u -B "$SOURCE/archive_closed_runs_v7.py" \
  --quota-closed-receipt "$RECEIPT" --quota-closed-sha256 "$RECEIPT_SHA" \
  --source-pins "$SOURCE/source_pins_v7.json" --source-pins-sha256 "$SOURCE_PINS_SHA" \
  --expected-node "$ACTUAL_CPU_NODE" --expected-partition cpu \
  --jobs 4520438 4520457 4520485 4520486 4520513 4520514 4520482 4520525 4520487
```

The tool prints only aggregate archival status/IDs, never SDK scientific data.
Originals remain untouched, all task-index entries are retained, and all output
is explicitly offline/unsynced. No scientific or final evaluation is authorized
by this archive operation.
