# C2 baseline-v2 / loader-v3 report and native SDK verification

New external reporting source only. The prior C2 v1 report, scientific source,
B3 and primary512 tools, SDK originals and artifacts remain unchanged. No new
test or real verification has run for this directory at preparation time.
Root alone submits CPU jobs and supplies actual terminal receipts.

The separate frozen `c2_artifact_v2_report_source` passed actual CPU job
4520598: C0/10s, 33 tests, source hashes unchanged. It remains intact. Actual
VAL attempt 4520595 failed before native geometry access because it compared
the executed local diagnostic commit with the distinct public commit. This
directory adapts only provenance to the new loader-v3 runtime, not the C2
baseline-v2 objective, evaluation, metric schema or two-row logger.

SA4 frozen request raw SHA:
`acb401d0d8aa6393680ff718fd0fde0898b7425fadc389dfeb7c68e2bfcab7d2`.
The exact five runtime sources are pinned in `c2_artifact_schema.py`; their
canonical inventory SHA is
`bf5e09abbdea933c0b6576836768106fab87d1f206f930726f28b0a22adc1633`.
Only accepted_train_artifact_v2.py and coordinate_baseline_v2.py differ from
the failed v2 loader. The producer path must be exactly
`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/c2_train_artifact_loader_v3_source/accepted_train_artifact_v2.py`.
Old source SHA values remain rejected even if a supplied protocol/binding
claims a self-consistent old inventory.

The v3 fit receipt's diagnostic_registration_mapping is checked against the
bound prior diagnostic INPUT_BINDING and original diagnostic inputs, both
ordinary model-owned metadata. The full executed local reference must match;
public commit must be cd0c434bb39824cd75c24d7c6de0531946da1de5; the commits must
be distinct; common tree and protocol blob SHA must match the producer's
verified record. The reporter does not rerun Git or interpret metadata equality
as an independent Git tree proof. The pinned v3 producer performs actual
Git/blob/method/source/tree checks. New ADOPTED protocol must explicitly contain
the v3 validation_revision and exact diagnostic_registration_policy.

`c2_artifact_report.py` requires actual current Slurm parent COMPLETED/0:0,
the successful fixed four-source CPU128MiB supervisor, byte-bound current
result/completion/input-binding/fit-receipt, original source request/selection
plan and the public ADOPTED artifact-origin protocol. It independently scans
the native offline SDK before producing a VERIFIED report. A fresh output
directory is required; no evidence is overwritten or removed.

The tool reads bounded (each <=32MiB) **model-owned result/closure/plan metadata**,
which can contain already-authorized TRAIN identities. It checks the closed
8192/1024 record populations, TRAIN/VAL disjointness and receipt membership
hashes without native geometry access. It exports only allowlisted aggregate
metrics/counts/units/source hashes, never identities or weights. The lookup JSON,
TRAIN NPZ, raw native geometries, VAL stores and downstream targets are never
opened. The declared TRAIN artifact binding is compared as metadata, not
rehash-claimed by this reporter.

## Native expectation and bounds

The actual frozen `accepted_train_artifact_v2.py` logger is SHA-bound to
`704f2683fcb9751102712d639b1ffc1a4b8f218d1b9f3257b0fe2b3e4dede12b`.
It writes exactly two committed rows:

- step 0: prior_TRAIN_fit/records=8192, prior_TRAIN_fit/atoms=436120,
  prior_TRAIN_fit/parameter_estimation_job_id="4520559" (string), and
  current_job/TRAIN_geometry_reads=0;
- step 1: `validation/` plus **every** original metric whose exact Python type
  is int or float, with saved metric values and no new rounding/threshold.

No mirrored history file exists. Expected rows are explicitly labeled
**code-derived saved outputs**, not independent measurement duplication. The
SHA-fixed archive_v7 bounded reader performs per-field type/value/step checking,
run-ID/exit0/clean-EOF checking, and partial-request rejection. A separate
read-only protobuf tap checks the complete public config, run display name and
final public summary, including the final summary step. SDK-internal private
keys are separately constrained. All scientific fields must match; missing or
extra fields fail. Installed W&B decoder source bytes/version are recorded.

Limits: SDK 128MiB, total native records 500000, committed history rows 100000
(exactly two expected here), record 4MiB, new export 64MiB, CLI deadline 180s.
Ancillary metric/config/summary records consume the native quota rather than
the history quota. Parent supervision must also enforce the declared inclusive
wall/RSS/output limits, including any import/plot stalls; internal deadline
checks do not replace the external supervisor. No network API or online sync
is called. The original SDK is rehashed before and after scanning.

## Root-provided byte-bound manifest

Every file reference below has exactly `{path,bytes,sha256}` with a physical,
absolute Linux path and machine-computed raw-byte size/SHA. The manifest itself
is passed with its raw SHA. Do not use `../` or manually transcribe PTY hashes.

```json
{
  "schema": "model_v3_C2_artifact_v3_report_inputs_v1",
  "expected_job_id": "<actual successful current VAL-only parent>",
  "root_closure": {"path":"/absolute/root_closure.json","bytes":0,"sha256":"<machine raw SHA>"},
  "source_request": {"path":"/absolute/original_source_request.json","bytes":0,"sha256":"<machine raw SHA>"},
  "selection_plan": {"path":"/absolute/original_selection_plan.json","bytes":0,"sha256":"<machine raw SHA>"},
  "artifact_inputs": {"path":"/absolute/current_artifact_inputs.json","bytes":0,"sha256":"<machine raw SHA>"},
  "input_binding": {"path":"/absolute/current_output/BASELINE_v2_ARTIFACT_INPUT_BINDING.json","bytes":0,"sha256":"<machine raw SHA>"},
  "fit_receipt": {"path":"/absolute/current_output/BASELINE_v2_ARTIFACT_FIT_RECEIPT.json","bytes":0,"sha256":"<machine raw SHA>"},
  "completion": {"path":"/absolute/current_output/BASELINE_v2_ARTIFACT_COMPLETE.json","bytes":0,"sha256":"<machine raw SHA>"},
  "result": {"path":"/absolute/current_output/BASELINE_v2_ARTIFACT_RESULT.json","bytes":0,"sha256":"<machine raw SHA>"},
  "protocol": {"path":"/absolute/public_adopted_protocol_blob.json","bytes":0,"sha256":"<machine raw SHA>"},
  "protocol_registration": {"repository":"/actual/registered/repository","commit":"<actual 40-character ADOPTED commit>","path":"configs/model_v3/c2_prior_TRAIN_artifact_v3_adopted.json","sha256":"<protocol raw SHA>"},
  "SDK_file": {"path":"/absolute/current_output/wandb/offline-.../run-actualID.wandb","bytes":0,"sha256":"<machine raw SHA>"}
}
```

All zero sizes above are placeholders, not an admission receipt. Root closure:
schema `model_v3_C2_artifact_v3_root_closure_v1`; `source_job` contains actual
job_id/state/exit_code/elapsed_seconds; `raw_sacct` contains exact argv/stdout/
stdout_sha256; `supervisor` is a full raw file reference. sacct argv must declare
JobIDRaw,State,ExitCode,ElapsedRaw (AllocCPUS optional) in explicit --format/-o
order, with parsable pipe-separated stdout. Exactly the parent row, not a
.batch/.extern row, proves C0 and elapsed time. Supervisor command must bind
the actual accepted_train_artifact_v2.py inputs path/raw SHA, with no remaining
processes/private sampling failure and no permitted GPU initialization.

The report checks the same actual protocol commit/path/raw SHA through the
Root manifest, executed input/binding and native SDK config. The producer
already verified `git show` before the first VAL; this CPU reporter does not
pretend to republish the protocol or infer a successful current job in advance.

## CPU tests and CLI (Root execution only)

Working directory:
`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/c2_artifact_v3_report_source`.
No new packages: stdlib, installed pytest/W&B/protobuf/numpy/matplotlib only.
No torch, SciPy, native provider, fitter or lookup loader is imported.
Suggested bounded request: 16 CPU, 16GiB, 5 minutes, on a currently admitted CPU
node with Root's normal quota/85%-memory/process supervision. No GPU request.

```text
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m pytest -q -p no:cacheprovider test_c2_artifact_report.py
```

Expected collection: **44 synthetic cases**, not a PASS claim. These include
full-size metadata-only populations, provenance/membership/denominator drift,
19 complete history scalars across two steps, complete config and summary,
native ancillary/history separation, hard caps/deadline, uncommitted request,
real tiny offline SDK roundtrip, real PNG/PDF render and unchanged repository
typed CSV validation. The real tiny SDK test uses synthetic metadata and is
not a claim about a physical C2 job. The pure renderer fixture's certificate
is explicitly synthetic; the real CLI always invokes independent SDK verify.
The 11 added v3 cases reject old/foreign runtime SHA values, the old producer
directory and adoption/report schemas, and altered public/local/tree/blob/
method-verification mapping. Scientific filenames/result schemas remain v2;
only this independent reporting interface/schema and registration path use v3.

Full production reporting (fresh external report directory):

```text
/share/home/zixiao/.conda/envs/chemprop/bin/python -B /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/c2_artifact_v3_report_source/c2_artifact_report.py --inputs /absolute/report_inputs.json --inputs-sha256 <machine raw SHA> --output /absolute/new_C2_artifact_v3_report
```

Optional independent certificate only:

```text
/share/home/zixiao/.conda/envs/chemprop/bin/python -B /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/c2_artifact_v3_report_source/c2_native_sdk.py --inputs /absolute/report_inputs.json --inputs-sha256 <machine raw SHA> --output /absolute/new_native_verification.json
```

## Report semantics and artifacts

Output: report.md, report.json, native_verification.json, one typed summary.csv,
one figure as metrics.png + metrics.pdf, and REPORT_COMPLETE.json written last
with raw output/input/source hashes. No marker appears if SDK, closure,
membership or rendering fails. Intermediate outputs are retained on failure.

All 15 numeric core keys and six original role/flag/membership metadata keys
are displayed. Coordinate vector RMSE uses N atoms, component RMSE 3N,
sigma-normalized component MSE 3N*sigma^2 (sigma=0.1 Angstrom), and local pair
RMSE all unique clean-distance<2 Angstrom pairs. Unknown bins remain in every
denominator with zero correction. The three plot panels separate coordinate
RMSE in Angstrom, normalized MSE without units, and local-pair RMSE in Angstrom.
Zero vector/component RMSE and normalized MSE are explicitly algebraic
derivations of the saved noisy-identity vector MSE. No CI or variance is invented.

The original approximately 0.0413 Angstrom pair-distance baseline is not a
coordinate RMSE comparison. Prior TRAIN solver/KKT scalars and timing are copied
from the bound 4520559 receipt, not estimated in the current VAL-only job. No
KKT quality threshold or model selection rule is added. Current TRAIN reads=0;
current VAL records=1024; original 4520482 remains FAILED and its exact old stop
is not inferred. Only actual C0 plus SDK VERIFIED allows verified report text.

CSV follows existing `tools/check_repository.py` typed one-run summary rules.
Its code_sha and preregistration_sha identify the adopted artifact-runtime
protocol commit; exact runtime source hashes remain separately bound. The
denoise_rmse field means coordinate component RMSE in Angstrom. No metric rows,
member identifiers, coefficients or predictions are placed in Git.
