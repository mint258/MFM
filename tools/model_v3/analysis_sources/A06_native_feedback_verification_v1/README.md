# A06 native-feedback diagnostic: independent offline SDK verification

This is a new external source package. It does not change the original 4521091
diagnostic, its SDK, the diagnostic/launch sources, accepted archive readers,
production trees or existing archives. Root alone submits CPU work and closes
actual jobs. This package has been prepared and statically reviewed; its new
tests and actual SDK readback have **not run** at source freeze.

The known source is the 15-update A06 native-gradient-feedback diagnostic,
job 4521091, offline run `bb3fue46`. Its original summary/status remain
`DIAGNOSTIC_COMPLETED_PENDING_SDK_AND_OUTER_TERMINAL`; this tool writes a
separate certificate and does not rewrite those pending fields. Root reports
the source job C0/106s, but the runner independently requires byte-bound actual
parent sacct and supervisor closure. No success is prefilled into an input
manifest or inferred from a mirror, a child summary, or this README.

The original A06 gate remains **FAILED_UNCHANGED**. This is one seed of
diagnostic evidence, not fixed20/full500 numeric acceptance, two-seed science,
architecture selection, convergence, a speed benchmark or an automatic causal
conclusion. The report records all 15 updates, including the unchanged point
threshold failures at updates14 and15. A gradient-relative maximum can be large
for a near-zero individual parameter; no new parameter-error gate is invented.
The shadow has no model forward in the SHA-fixed producer and uses the same
clipped reference gradient tensors/None entries. Saved before/after/reference
hash equality is checked; reading these receipts does not rerun a model.

## Independent checks

`feedback_schema.py` admits only the declared diagnostic job/run. It checks:

- raw size/SHA/ordinary physical absolute paths, no symlink or `..` input paths;
- the exact fixed producer and producer-pins SHA, complete original source
  inventory, before/after equality, and an actual rehash of that inventory;
- every saved457 scalar/input-receipt field for the first15 updates, using the
  producer's eight `REPLAY_FIELDS`, excluding old timing/peak fields;
- reference/free histories, update ordering/dispatch, borrowed-gradient
  receipts, CPU-vs-CUDA optimizer step representation, consumption increments,
  sampler batches/samples/contract, and all 15 summary point aggregates;
- exact step0 START, steps1..15 update fields, and step16 COMPLETE,
  independently reconstructed from detailed saved aggregates and matched to
  every mirrored field without tolerance; original loss-gap denominator and
  0.001 threshold are unchanged;
- actual parent `COMPLETED/0:0`, >=16 allocated CPUs and a closed successful
  supervisor with no residual recorded processes/private-storage/cleanup error.

`verify_feedback_sdk.py` loads the accepted immutable archive-v7 bounded reader
by exact path and SHA. A separate protobuf tap verifies the full public native
configuration, display name, all public final summary fields and final `_step`.
The native reader requires run ID, explicit steps, every history field/value,
clean EOF and exit0, and rejects uncommitted partial-history requests. It counts
native records independently of committed history rows: ancillary metric/config
records do not consume the history quota and are not silently truncated.
Installed DataStore/protobuf Python source SHA and W&B version are recorded.

Original metadata and SDK are rehashed after scanning. No model, tensor file,
native geometry, labels/targets, corpus store, checkpoint or network API is
opened. Imports are limited to stdlib, installed W&B/protobuf and the SHA-fixed
stdlib-only bounded reader. No `wandb.init`, API client, sync or SDK mutation is
performed. Model-owned config/update metadata can contain parameter names or
selected scalar diagnostics; reports use a fixed aggregate allowlist and do
not export those names, scalar parameter samples, arrays or molecule/member IDs.

## Bounds and output

Source SDK <=128MiB; total native records <=500000; history rows <=100000 and
exactly17 expected; individual native record <=4MiB; each ordinary metadata
file <=4MiB; source inventory total <=32MiB; metadata JSONL line <=128KiB;
new report products combined <=64MiB. Internal CLI wall budget is180s, including
metadata preparation/scan; Root's external supervisor must also bound imports,
output, RSS and the process lifetime. No claim of an actual runtime/peak is made
until Root executes and records it.

The scanner hashes normalized rows to a sink. It does not export a second raw
history or config. A fresh separate output directory contains:

- `verification.json`: bounded native certificate with raw-byte refs, decoder
  sources, counts and hashes; no full config or parameter arrays;
- `summary.csv`: one typed row compatible with the existing repository checker
  at `docs/model_v3/results/A06_native_feedback_4521091.csv`; `status=NOT_ACCEPTED`
  preserves the original science failure even when readback/Slurm succeed;
- `REPORT.md`: all15 loss/gap/count rows, every fixed comparison aggregate
  (three comparisons x parameters/exp_avg/exp_avg_sq/step x relative/global L2),
  and both preclip gradient norms, without invented physical units or CIs;
- `archive_entry.draft.json`: a proposed new index entry for Root review; no
  existing archive/index is edited;
- `report_manifest.json`: hashes of those compact products.

`VERIFIED_DIAGNOSTIC_ONLY` means the source SDK and already closed source job
were checked. It is not the verifier's own Slurm terminal receipt. Root must
observe actual verifier C0 and source-before/after SHA equality before accepting
or publishing the certificate/draft archive entry. An interrupted verifier's
partial output is retained and cannot establish that closure.

## Root-provided closure and input preparation

The existing actual Root frame can be consumed **directly**:
`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/A06_native_feedback_actual_closed_inputs_v1.json`,
raw SHA `d400e494e5892909ab988fac5090cf24d34d56434aba56905a6aaee1e6fa0ed5`.
Its `model_v3_actual_closed_A06_native_feedback_inputs_v1` schema preserves the
headerless actual sacct stdout with exact argv/returncode/stderr, zixiao UID,
source job/node, all top-level file refs, source inventory and launch refs.
The runner checks that exact declared column order, user and parent C0. The
original frame is never rewritten and still explicitly says SDK verification
is pending. `report_feedback.py --inputs` may point to this existing frame;
the preparation command below is optional, not a required replacement receipt.

Use only fresh external output paths and machine-generated raw sizes/SHA.
Root writes a small closure JSON with exactly this meaning (all file refs have
`{path,bytes,sha256}`, with actual absolute Linux paths):

```json
{
  "schema": "model_v3_A06_feedback_root_closure_v1",
  "job_id": "4521091",
  "raw_sacct": {"path":"/absolute/fresh_sacct_4521091.txt","bytes":123,"sha256":"<actual raw SHA>"},
  "supervisor": {"path":"/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/A06_native_feedback_v4_supervisor_4521091.json","bytes":123,"sha256":"<actual raw SHA>"}
}
```

The sacct file is actual `--parsable2` text with headers `JobIDRaw`, `State`,
`ExitCode`, `ElapsedRaw`, `AllocCPUS` (other columns/step rows may exist). The
unique exact parent row is required; batch/extern rows cannot substitute for it.
The source supervisor is checked against the fixed producer command, output,
code/pins arguments, successful cleanup and its source-inventory SHA.

`prepare_feedback_inputs.py` generates the complete role/update manifest and
validates the bounded model-owned metadata. It performs **zero native SDK
record decodes**, only the raw SDK file hash. It does not query Slurm, reserve
resources or manufacture a Root closure.

Set these shell variables to physical absolute paths and machine-read hashes;
the following commands are examples for Root to execute in an admitted CPU job,
not actions already performed:

```sh
task_source=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/a06_native_feedback_verification_v1_source
task_diag=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/A06_native_feedback_v4_4521091
task_request=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/A06_feedback_verification_request_NEW
# task_root_closure, task_root_closure_sha and task_source_pins_sha are fresh,
# actual Root receipt/pin values; do not transcribe hashes from a PTY.
python -B "$task_source/prepare_feedback_inputs.py" \
  --diagnostic-root "$task_diag" \
  --root-closure "$task_root_closure" --root-closure-sha256 "$task_root_closure_sha" \
  --source-pins "$task_source/source_pins_v1.json" --source-pins-sha256 "$task_source_pins_sha" \
  --output "$task_request/inputs.json"
# task_inputs_sha is machine-read from the resulting raw inputs.json.
python -B "$task_source/report_feedback.py" \
  --inputs "$task_request/inputs.json" --inputs-sha256 "$task_inputs_sha" \
  --source-pins "$task_source/source_pins_v1.json" --source-pins-sha256 "$task_source_pins_sha" \
  --output "$task_request/report"
```

The new request parent must already exist; the report directory must not exist.
Neither output may be inside the original diagnostic. Root supplies actual
metadata/quota supervision and new verifier-job terminal evidence. At least16
CPUs, CPU-only, actual available CPU node selected by Root. Follow the current
CPU submission rule: no Slurm memory-size flags; retain measured RSS and the
existing software output/private-storage guards. Source64MiB output is a
software ceiling, not a request to allocate or fill that space.

## Tests for Root

The new suite has **46 expected cases**: pure synthetic metadata/protobuf only.
It constructs a complete real raw-ref metadata bundle on disk, validates the
actual preparer, reconstructs17 rows, compares serialized protobuf records and
checks report allowlists. It includes missing/extra/type/step fields, original457
drift, source/data/consumption/gradient/summary contradictions, late config,
display/run/exit/EOF failures, native-vs-history quotas and byte/wall limits.
Both the direct actual-Root-frame schema and optional manifest preparer are
tested with synthetic on-disk raw-byte refs. The headerless sacct tests reject
command/returncode/rawstdout/user/UID/state/pending/mirror-inference drift.
The output CSV is checked through the actual existing repository checker.
These tests do not claim a genuine SDK-file scan; Root's separate actual command
above supplies that evidence.

```sh
export CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
export SA3_REPOSITORY_CHECKER=/share/home/zixiao/descriptor_analysis/MFM_model_v3/tools/check_repository.py
python -B -m pytest -q -s /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/a06_native_feedback_verification_v1_source/test_feedback_verification.py
```

No new packages: stdlib, existing pytest/W&B/protobuf. There are zero model
checkpoints/embeddings/parameter arrays. Synthetic retained metadata is expected
below4MiB (not yet measured); metadata/protobuf tests are sequential and should
fit the existing2GiB parent/private guards without changing them. Root records
actual wall/RSS/storage peaks and all source-before/after hashes. The accepted
archive-v7 reader and real repository checker are read-only dependencies pinned
in the source manifest; no old source bytes are changed.
