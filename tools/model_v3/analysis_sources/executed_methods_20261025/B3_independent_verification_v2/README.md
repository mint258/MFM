# B3 independent SDK verification and aggregate report v2

Prepared in a NEW model-owned external directory on 2026-10-25. Existing SA3
source commit `9638f7c461a6a88b6b2469f2c7e9ec8023d276e5` and all SDK originals
remain unchanged. The v2 tools are prepared for Root review and CPU submission;
their new tests and real SDK verification have **not yet run**. The v1 source,
its 21 passing tests from 4520473, and failed 4520474 output remain preserved.
The separately prepared primary512 launcher also passed its 22 CPU tests in
4520473; A06 job 4520457 failed the 500-update gate and produced no export, so
that launcher remains preparation only.

The real historical B3 panel is already closed: Slurm 4520437 COMPLETED/0:0,
543 seconds. Its core evaluation elapsed and all scores/CIs are consumed from
the machine-bound result; this document does not transcribe those intervals.
Both the core result and external guard still explicitly say independent SDK
verification is false. A later separate verification certificate must not
rewrite those historical flags.

Inputs, read-only:

- `../B3_dev9_real_v2/evaluation/result.json`
- `../B3_dev9_real_v2/evaluation/history.jsonl`
- `../B3_dev9_real_v2/evaluation/wandb/offline-run-20261025_165633-xtpvidn4/run-xtpvidn4.wandb`
- `../B3_dev9_real_v2/guard_4520437/guard_result.json`
- `../B3_panel_request_4520434/request.bound.json`
- The frozen panel JSON, byte-bound by that request, and a new Root-produced
  successful terminal-job/quota admission receipt.

No model, H0 tensor, downstream data store, source member list, final targets,
predictions, old evaluation scores, network API, login, upload or sync is used.
W&B native protobuf/DataStore decoding is the independent check, separate from
the evaluator/journal writer. The original SDK stream is scanned in place and
hashed before and after. It is neither copied, modified, pruned nor deleted.
Original inputs and their ancestors must be physical, owned, singly linked
ordinary files; canonical SDK log symlinks are not traversed by this tool.

`verify_native_history.py` checks every native scientific scalar against every
journal payload at the explicit global step; it rejects unknown scientific
keys rather than exporting arbitrary SDK content. It also checks run ID,
initial configuration/source/request/seed bindings, final declared score and
status, successful native exit and clean EOF. It writes normalized safe scalar
history plus a separate certificate with reader version/source/schema hashes.
This verifies persisted tracking; it does not recompute optimizer updates,
predictions, target errors or bootstrap intervals.

The machine-bound original result reports exactly 56,738 history/journal rows.
Those are not the total native SDK records: SDK metric definitions, summaries,
run/config/exit and other ancillary records also occupy the native stream.
The old 50,000-record archiver and v1's 100,000-native-record cap therefore cannot
close this stream. Actual 4520474 failed at the native total cap before EOF;
the total native count remains unknown until a complete successful scan. No
estimated total is reported as an observation.

V2 separates two explicit limits: **500,000 total native SDK records** and
**100,000 scientific history rows/journal lines**. Native ancillary records do
not consume the history quota; all still consume the native total quota. The
SDK history must still match every journal payload/global step and the original
machine-bound result's exact 56,738 rows, with no omitted or extra histories.
Other bounds remain unchanged: 128 MiB SDK input, 32 MiB journal input,
4 MiB per SDK record, 32 KiB per journal line, 64 MiB output, 180 seconds total.
No whole-history list is retained in RAM. Budget exhaustion or truncated/error
streams fail; retained partial new output is not accepted as a certificate.

`make_b3_report.py` requires all 18 cells and both separate nine-cell summaries;
checks every relative improvement and equal-weight mean; requires 1,000 paired
molecular bootstrap draws; and checks 384-dimensional candidate/random state,
configuration, membership, geometry, H0 inventory, packing and runtime matches.
It validates and reports the existing intervals, without recomputing them. It
exports an aggregate Markdown table, compact aggregate JSON, and one typed CSV
row per run. CSV columns follow the unchanged `tools/check_repository.py`
allowlist: all required run/config/code/data/seed/GPU/status/preregistration
columns plus numeric `metric__...` fields. No per-task CSV exemption is added.
The CSV config SHA is the full evaluation request's raw SHA, whose model
configuration and panel refs are separately bound in the report manifest.

The report lists every negative cell, including CYP2D6 ridge and QM9 U0/alpha
ridge, rather than hiding them behind the combined mean. Its SoM inner
validation has 26/35 observed molecular groups; it prints counts read from the
result and explicitly notes the small-population CI/generalization limitation.
This single historical pretraining seed has no two-seed SD. A 384-dimensional
historical sanity check cannot choose or validate the model-v3 512 architecture.
The existing B3 panel's inclusive one-GPU-hour result is specific to this run.

`gpu_peak_allocated_bytes` is reported with its actual PyTorch counter scope:
the evaluator process allocator high-water since the last counter reset. It is
not device-global, driver, process-tree or guaranteed H0-phase memory. Read-only
review found no reset in the actual v3 H0 cache/evaluator/readout/bridge or
historical tiling path, nor bound model modules; the older unrelated dev_probe
and training engines do reset their own counters. No dynamic reset interposer
or device-global peak monitor was added to 4520437. The guard's child counter
has the same scope and value; it is not independent global-memory evidence.
No 85%-capacity claim is inferred.

## CPU test and execution plan (Root only)

Use an approved development compute node in a Root-owned Slurm allocation:
**16 CPUs, 16 GiB, 5 minutes, no GPU**, CUDA hidden, no school-server use.
The target is at most 180 seconds for the bounded real SDK verifier, with an
outer 300-second deadline. Root must finish CPU/node admission first. This
agent neither submits nor starts any job. Tests include one actual tiny offline
SDK run plus synthetic drift/limits/matching tests. Tiny SDK test originals are
retained inside the model-owned pytest basetemp, outside the real run.

Use the actual verified interpreter from the real evaluation, with its installed
W&B SDK and pytest. Example allocation command (Root supplies the NEW basetemp):

```sh
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' \
  /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python \
  -B -m pytest -q \
  /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_b3_verification_v2/test_b3_verification.py \
  --basetemp /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_b3_verification_v2/pytest_NEW_JOB \
  -o cache_dir=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_b3_verification_v2/pytest_cache_NEW_JOB
```

The existing typed-CSV checker test uses the frozen SA3 tree's physical checker;
Root can explicitly bind `SA3_REPOSITORY_CHECKER` to that identical source path.
Expected full collection is 24 tests. Only actual pytest XML/output determines pass
counts. Source pins should be compared before/after the allocation.
The new ancillary-record parameterized test proves two history rows can coexist
with more than two native records and still pass, while the exact same stream
fails if the native total cap is reduced. A separate test still refuses extra
history when ample native budget remains. The original v1 cap-refusal test is
retained with the new total-counter name. For a narrow CPU rerun, select these
six expected cases (plus the installed real-SDK test if Root wants it):

```sh
python -B -m pytest -q \
  /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_b3_verification_v2/test_b3_verification.py::test_native_record_cap_rejects_stream_without_eof \
  /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_b3_verification_v2/test_b3_verification.py::test_native_metric_ancillary_records_do_not_consume_history_quota_but_obey_total_cap \
  /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_b3_verification_v2/test_b3_verification.py::test_history_cap_still_rejects_extra_history_with_room_in_native_budget \
  /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_b3_verification_v2/test_b3_verification.py::test_admission_requires_successful_terminal_receipt_and_quota \
  /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_b3_verification_v2/test_b3_verification.py::test_core_false_flag_needs_separate_successful_matching_certificate
```

Use Root's same verified interpreter, controlled basetemp/cache and allocation
as above. V2 changes only bounds/counter-specific tests and v2 receipt/certificate
identities; no scientific metric, step, membership or completeness rule changes.

Root prepares a NEW receipt with schema below; values come from actual sacct
and fresh login-node metadata quota evidence. Do not substitute an in-progress
job, assumed capacity or stale quota. Hash the exact receipt bytes by machine.
The receipt's optional original command/receipt refs may be included for audit.

```json
{
  "schema": "model_v3_bounded_metadata_admission_v2",
  "evaluation_job": {
    "job_id": "4520437",
    "state": "COMPLETED",
    "exit_code": "0:0"
  },
  "verification_admission": {
    "network_access": false,
    "gpu_requested": false,
    "max_output_bytes": 67108864,
    "max_source_bytes": 134217728,
    "max_native_records": 500000,
    "max_history_rows": 100000,
    "max_wall_seconds": 180,
    "quota": {
      "free_bytes": "REPLACE_WITH_ACTUAL_INTEGER",
      "active_job_reserved_bytes": "REPLACE_WITH_ACTUAL_INTEGER",
      "reserved_headroom_bytes": 34359738368,
      "observed_at_utc": "REPLACE_WITH_ACTUAL_ISO8601_UTC"
    }
  }
}
```

Quota must reserve at least 32 GiB plus active-job reservations and this 64 MiB
new export; the observation must be at most one hour old. These are inputs to a
CPU metadata operation, not an authorization to schedule or change servers.

CLI (Root substitutes machine SHA values and NEW owned output paths; all
input/output paths below are absolute because the safety checks reject `..`):

```sh
python -B /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_b3_verification_v2/verify_native_history.py \
  --result /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/B3_dev9_real_v2/evaluation/result.json --result-sha256 RESULT_RAW_SHA \
  --guard /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/B3_dev9_real_v2/guard_4520437/guard_result.json --guard-sha256 GUARD_RAW_SHA \
  --request /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/B3_panel_request_4520434/request.bound.json --request-sha256 REQUEST_RAW_SHA \
  --admission /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_b3_verification_v2/ADMISSION.json --admission-sha256 ADMISSION_RAW_SHA \
  --output /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_b3_verification_v2/native_sdk_NEW_JOB

python -B /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_b3_verification_v2/make_b3_report.py \
  --result /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/B3_dev9_real_v2/evaluation/result.json --result-sha256 RESULT_RAW_SHA \
  --guard /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/B3_dev9_real_v2/guard_4520437/guard_result.json --guard-sha256 GUARD_RAW_SHA \
  --request /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/B3_panel_request_4520434/request.bound.json --request-sha256 REQUEST_RAW_SHA \
  --verification /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_b3_verification_v2/native_sdk_NEW_JOB/verification.json --verification-sha256 CERTIFICATE_RAW_SHA \
  --output /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_b3_verification_v2/aggregate_report_NEW_JOB
```

Run from this new directory with the same exact verified interpreter; `python`
above is shorthand only. Output directories must be fresh descendants of this
tool directory. The report may omit both verification arguments to explicitly
render PENDING; it cannot claim independent verification without a matching
successful native certificate. A successful certificate does not alter the
original false flags. Reports total at most 128 KiB; aggregate-only CSV may
later be reviewed for the existing approved Git summary path. The full SDK
history, source/member metadata, H0 and predictions do not enter Git.
