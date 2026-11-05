# Two failed A5 SDKs: source-only bounded audit and selective sync

This adapter is restricted to original GPU job `4524601` and SDK IDs `89mp3smr` / `9j1swwgi`. `scope.json` binds the actual Root negative closure. The parent was FAILED 1:0; the scientific child returned 2 after the fixed-20 gate. All twenty forward comparisons passed, but 120 near-zero-bias relative-gradient comparisons failed the unchanged original gate. There was no 500-update trajectory, R1 timing, model adoption or retry. This package does not change that result or the pending user policy question.

## Exact failure-path expectations

The bound original `paired_a_acceptance.py` initializes both W&B trackers before fixed20, with the complete saved `configuration.json` plus native `paired_role`. Only the later trajectory loop calls `tracker.log`; this run returned before that loop. Finally, both trackers are asked to finish with native exit 1 because `final_status` is `FIXED_BATCH_GATE_FAILED`. That is the source-derived expectation. Actual native exit, record counts, configuration and EOF remain independently unverified until the CPU audit runs.

Expected committed history is exactly zero, with no first/last explicit step. It is not 20, 500, or zero native packets. No role is inferred from directory order, timestamps or SDK sizes: the CPU decoder must discover one `reference` and one `candidate` from the two actual RunRecord configs and check the matching `A_{role}_4524601` name/project/ID. The project is `mfm_model_v3_development`. Every initial RunRecord config and config update must preserve the complete typed expected config and native role.

This source path has no user `summary.update`, `summary.json`, `SDK_expected_summary.json`, trajectory gate or role history journal. The adapter does not create an expected-summary artifact or invented last step. It reuses original tap2's config/summary update and private-field classification. Its narrow zero-history finalizer checks the complete typed config/header, verifies no history began, and requires **zero public scientific summary leaves**. SDK automatic private summary fields are accepted only by the unchanged tap2 allowlist; unrecognized private or any public summary field is HOLD. Actual allowed private key names and a summary digest are recorded without exporting their values. Original tap2.finish's nonempty mirror[-1] assumption is not applied to an empty population.

## Reuse and limits

Literal749, tap2, the reviewed rb/CRC/fragment-chain scanner, original v7 protocol, installed0.28.1 source snapshots and original v3 one-file transport are raw-source bound. The transport body changes only its eligibility import. No decoder, monitor, scheduler or QA framework is introduced. Four inline functional metadata checks exercise the existing empty plain-row parser, header/role binding, original private-summary allowlist and full typed config rejection; they run within the same actual audit allocation, not a new QA parent.

Root login preparation reads only source/small JSON and stats these two SDKs and the known fixed-gate metadata. It does not open SDK, journals, credentials or W&B API. The CPU audit alone hashes/decodes both SDKs, and checks each separately to exact native exit 1, clean full-fragment EOF/CRC, no uncommitted requests, no history, full typed config and the summary rule above. Any history, role repetition/absence, exit mismatch, unexplained field, truncation or source drift fails. It also raw-hashes the exact pre-existing 2,489,057-byte fixed gate under a narrow 4MiB allowance without decoding/recomputing its numerical content; this reuses the original negative Root authority rather than re-evaluating the model.

The two original SDKs are only 101,923 and 101,871 bytes. Each SDK remains bounded by 128MiB; explicit admitted input metadata plus SDK envelope by 256MiB. Existing scanner bounds remain 180 seconds per SDK, 500,000 native records, 100,000 history rows, 4MiB per record and 64MiB normalized-export accounting. Expected history remains exactly zero within those upper limits. Source and ordinary JSON limits remain 2MiB; no large scientific gate is copied into a certificate.

Audit resources remain CPU16/16GiB, RSS12GiB, original supervisor 900s, Slurm20min, original whole-output/private 2GiB. Sync retains the original supervisor3300s/Slurm1h, CPU16/16GiB/RSS12GiB and both2GiB caps; original per-batch/CLI/API bounds are3000/600/180s with at most3 sequential runs. This request selects exactly2. Failures and original SDKs remain intact.

## Root preparation and submission

After Root's source/AST/bash review, metadata-only audit preparation is:

```sh
P=/share/home/zixiao/descriptor_analysis
N=$P/runs/model_v3_20261026
O=$P/runs/model_v3_20261025
S=$N/performance_A5_failed_SDK_v1_source
PY=$P/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
PIN=$(sha256sum "$S/source_pins.json" | cut -d' ' -f1)
"$PY" -B "$S/prepare.py" --mode audit --pins-sha256 "$PIN" \
  --plan-output "$N/performance_A5_failed_SDK_audit_request_v1" \
  --job-output "$N/performance_A5_failed_SDK_audit_actual_v1"
```

Root copies `audit_cpu.sbatch` raw bytes to a fresh `O/run_performance_A5_failed_SDK_audit_v1.sbatch`, checks its source SHA, then uses the existing fresh-admission helper:

```sh
"$PY" -B "$O/submit_cpu_task_v2.py" --node compute-0-13 --memory-MiB 16384 \
  --script "$O/run_performance_A5_failed_SDK_audit_v1.sbatch" \
  --bindings "$N/performance_A5_failed_SDK_audit_request_v1/bindings.json" \
  --output "$O/performance_A5_failed_SDK_audit_submission_v1.json"
```

The CPU node is Root's explicit fresh resource choice; the helper retains idle16CPU/all-user memory85%/live MemAvailable/quota checks and supplies the expected-node environment. Submission ambiguity must not trigger automatic retry.

Only after genuine audit CPU C0, exact supervisor/argv/source binding and two separate complete certificates may Root prepare synchronization:

```sh
"$PY" -B "$S/prepare.py" --mode sync --pins-sha256 "$PIN" \
  --audit-result "$N/performance_A5_failed_SDK_audit_actual_v1/RESULT.json" \
  --audit-supervisor "$N/performance_A5_failed_SDK_audit_actual_v1.supervisor.json" \
  --plan-output "$N/performance_A5_failed_selective_sync_request_v1" \
  --job-output "$N/performance_A5_failed_selective_sync_actual_v1"
```

Root may then raw-copy `sync_cpu.sbatch` to `O/run_performance_A5_failed_selective_sync_v1.sbatch` and submit with that new plan's bindings and a fresh submission receipt, using the same CPU16/16GiB helper. Actual job IDs/C0/role mapping are never prefilled by this source package.

## Exact online scope

The original actual failed-exit v3 pilot is reused as method evidence, without re-piloting or crediting its result to A5. An empty native entity is resolved only from the actual authenticated account/default entity inside the CPU transport; project is retained from each native record. Only the two independently certified SDKs may be exact-copied and replayed. The original source, marker and failed exit remain unchanged. There is no sync-all, repair/append, summary/config/state mutation API, deletion or finish call on the original runs.

Success requires actual sync CPU C0 and the original remote route/runID/**failed**/history0/first-stepNone/last-stepNone readback for both runs. Remote metric-value re-comparison is not claimed. Safe failure output contains only stage/type/traceback-frame metadata; credentials and exception messages stay out of public output. An audit C0 or successful log sync never changes the original GPU FAILED result or grants A5 acceptance, R1, auto capacity, final training or D5 authority.

Author work is source/stat/small-metadata only. Python, AST, tests, SDK/journal reads, W&B/API/SSH/Slurm operations have not been executed by the author.
