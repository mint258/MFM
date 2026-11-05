# C2 actual603 / independent606 certificate archive v12

Prepared, not tested or executed. This CPU-only increment adds only the one SDK from actual C2 job 4520603. It reuses the independently completed 4520606 verification/report; it does **not** repeat the native scan, evaluate a target, refit a solver or create a history mirror. It preserves all original files and the existing 55 task-index entries, stays offline/unsynced, and changes none of the frozen scientific or previous archive sources.

Actual 603 completed C0 in 127 seconds. It reused the prior TRAIN559 artifact (8192 records/436120 atoms); current TRAIN geometry reads are 0 and current parameter estimation is false. Its fixed first PRETRAIN_VAL population is 1024 records/55650 atoms. This is analysis-only evidence, with no model-selection gate. The independent 606 CPU report completed C0 in 4 seconds after its frozen reporting suite passed 44 tests in job601.

The exact original SDK is `10oej1zg`, 10549 bytes, SHA `7f776fff88dbef23ed8a1868b42a7ac57310f9c07fb9e5d3e1f40caeca1d4528`. The independently verified native stream has **31 native records and 2 committed scientific history rows**, explicit steps 0/1, exit0 and complete EOF, no uncommitted history or decode error. Its public scientific fields, full config and summary matched exactly. The 606 certificate raw SHA is `9cdbce56eeb9c0df9ff58737e83e0570f24281fb833ff9e6b7121f1fc0d35f02`; the safe aggregate report raw SHA is `ee7156f72bfdb4b7bdd52e1ff361386c11ae49572d4d01773aa83e6dd7a9f332`. The certified expectation origin is code-derived saved outputs, with no independent mirrored history file.

v12 checks those exact raw certificate/report bytes, every declared report output SHA, 603/606 supervisor closure, full metadata/source bindings and the original SDK SHA. It also verifies the original fixed producer/logger inventory, the three frozen reporting modules, the bounded-reader source, and the recorded installed decoder Python sources. Installed package-manager hard links are accepted only for the two exact recorded read-only decoder files; no library source is copied or executed. A fresh sonmi receipt must independently confirm both actual jobs C0.

Only safe aggregates are parsed. The original fit_receipt, result and selection_plan are streamed for bounded raw hashes and never parsed or copied. The artifact LOOKUP JSON and NPZ are never opened, even for hashing. Every metadata input reference remains in the certificate/source manifest. Copying metadata has an explicit filename allowlist, so full member-ID documents cannot cross the copy boundary. The safe report retains units and all populations: coordinate vector RMSE is `sqrt(SSE/N)`, component RMSE is `sqrt(SSE/(3N))`, sigma-normalized component MSE is `SSE/(3N*sigma^2)`, and unknown bins use zero correction without exclusions. No threshold or new quality decision is introduced.

The original full SDK/logs, all six certified 606 outputs (native_verification.json, report.json, report.md, summary.csv, metrics.png/pdf), REPORT_COMPLETE, input reference manifest and both supervisors are copied unchanged. An HTML index and `certificate_bound_metrics.csv` expose all 19 scientific scalars across the two certified steps. This new CSV is a **safe aggregate projection** whose canonical two-row digest must equal both the original certificate's expected-row digest and native normalized-history digest (908 bytes). It is not a new scan, reconstructed original journal or fsync mirror; no normalized-history/mirror file is invented. The original training-compatible aggregate `summary.csv` remains unchanged.

The raw C2 first-VAL failure595 supervisor is retained as a hash reference, and the failed482 archive entry remains unchanged. The current index has no595 entry; this package does not add one or reinterpret its outcome/stop code. It only adds actual603, so an index count of 56 is expected if no conflicting identity intervenes. That count is not an execution claim.

Selected sources remain capped at128MiB and each archive case at256MiB. Model-owned JSON hash references are capped at32MiB/file and physically owned single-link regular files, with inode/size/mtime checked while hashing. All originals are rechecked; the fixed SDK symlink allowlist, common task lock, index deduplication, owned fresh pending directory and atomic publication remain unchanged. No credentials, source member identities, coefficients, geometries or predictions are printed.

## Root CPU request (prepared only)

There are **49 expected parameterized tests**. They use only the actual pinned small safe report/certificate/ref/supervisor metadata. They cover two-step/config digest equality, all units/populations, vector/component/sigma confusion, wrong/missing config/EOF/exit/source references, model-selection/old-failure claims, unsafe member arrays and coefficient payload, prevention of LOOKUP/NPZ reads and full fit/result/selection copy, exact CSV field/provenance checks, and absence of any SDK scan or sensitive prepare invocation. These are archive verification tests, not a repeated scientific run or decoder acceptance.

Root chooses a currently available actual CPU node, partition `cpu`, at least16CPUs,4GiB RAM,10minutes, with `CUDA_VISIBLE_DEVICES=''` and `PYTHONDONTWRITEBYTECODE=1`. Use the existing pytest environment; no W&B decoder execution or Torch is required. The source pins distinguish safe `files` from **`hash_only`** metadata. Rehash both groups before/after testing, but **do not copy/snapshot `hash_only` files** into unit evidence. Their references alone are the evidence. The installed decoder refs are recorded separately and verified read-only during actual archive admission.

```bash
python -m pytest -q -p no:cacheprovider \
  runs/model_v3_20261025/archive_closed_v12_source/test_archive_v12.py \
  --basetemp /tmp/mv3n_JOBID/pytest
```

Only after an actual test PASS, Root refreshes CPU/resource admission and creates a SHA-bound sonmi quota/closed-job receipt no older than120seconds. Require exact actual lines `4520603|COMPLETED|0:0` and `4520606|COMPLETED|0:0`, preserving the existing filesystem quota/reserve checks. The root task's archive lock serializes appends and all existing entries are retained.

```bash
python runs/model_v3_20261025/archive_closed_v12_source/archive_closed_runs_v12.py \
  --source-pins runs/model_v3_20261025/archive_closed_v12_source/source_pins_v12.json \
  --source-pins-sha256 PIN_RAW_SHA \
  --quota-closed-receipt FRESH_RECEIPT_JSON \
  --quota-closed-sha256 RECEIPT_RAW_SHA \
  --expected-node ACTUAL_CPU_NODE --expected-partition cpu
```

The only new target is `runs/phase1_full_corpus/wandb_archive/model_v3_20261025/closed_v12/job4520603`. No original or prior archive is moved/deleted/replaced. A failed attempt leaves its pending directory for review. The archive's machine certificate explicitly records zero additional native scans and retains the untouched original606 certificate.
