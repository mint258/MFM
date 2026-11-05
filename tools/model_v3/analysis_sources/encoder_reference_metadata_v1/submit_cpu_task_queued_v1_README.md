# Minimal queued CPU helper

Mechanical derivative of O/submit_cpu_task_v2.py. The original helper and its
receipts are unchanged. This source has not executed Python/SSH/Slurm/tests.
Only ordinary source and metadata were read during preparation.

The CPU policy changes the first gate from current idle>=16 to node hardware
capacity>=16. It records both actual CPUAlloc and CPUTot, current free CPUs
(including10), and whether waiting is expected. Slurm still requests exactly
16CPU/16GiB on an allowed CPU node, without oversubscribe/overcommit/exclusive.
This receipt never claims an idle16 admission or actual allocation/success.

All-user declared R/CG memory sum versus AllocMem max and the strict85%
threshold, actual SSH-read MemAvailable minus16GiB/15% reserve, quota64GiB
headroom, CPU node choices, explicit nonsecret MODEL_V3_ bindings and owned
O script/output rules retain the original helper checks. Only16GiB is exposed
here, matching the already authorized ordinary repo-checker and closed-SDK
audit tasks. The helper runs only on Root's actual sonmi/UID1278 login.

`--validate-only` performs the fresh metadata checks and prints the complete
prospective queued-policy observations; it does not create an intent or call
sbatch. A real call repeats current checks, then durably writes a unique
`.QUEUE_INTENT` (JSON content, not an actual receipt) before one sbatch.
Raw sbatch stdout/stderr files and the real queued receipt are preserved.
Failure/timeout/ambiguous submission never automatically retries or cancels;
same-output reentry refuses because the intent persists. Root reconciles it.

Receipt schema reuses the actual standardized model_v3_queued_CPU_submission_v1,
modeQUEUED_ONLY, with actual_sbatch_script/argv/result/raw-stream refs. It is
compatible with the explicit CPU cost registry. Source/base-helper hashes,
admission policy and free-CPU snapshot identify this new implementation; it
does not impersonate the old helper's idle decision. There is no publisher,
dispatcher, monitoring service, allocation claim, auto lease renewal or cancel.
PENDING itself does not run project work; the existing scripts run only after
Slurm allocates their16CPU. Their original budgets/owned-allocation guards stay.

Only submit scripts without an expiring presubmission authority. In particular
the helper explicitly refuses old MODEL_V3_ARCHIVE7_ROOT_RECEIPT bindings:
the7-run archive must use the separately prepared allocation-time JIT wrapper.
The ordinary repo-checker and closed slots5+6 SDK audits have no archive120s
quota input and may use this queued helper immediately after Root's source/AST
review. This helper does not change their code, inputs, tests or evidence.

```bash
P=/share/home/zixiao/descriptor_analysis
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
Q=$P/runs/model_v3_20261026/submit_cpu_task_queued_v1.py
# Use actual already-prepared ordinary script/bindings and a fresh receipt:
"$PY" -B "$Q" --node compute-0-13 --memory-MiB 16384 \
  --script ABSOLUTE_OWNED_O_SCRIPT --bindings EXISTING_BINDINGS \
  --output FRESH_O_SUBMISSION_RECEIPT --validate-only
"$PY" -B "$Q" --node compute-0-13 --memory-MiB 16384 \
  --script ABSOLUTE_OWNED_O_SCRIPT --bindings EXISTING_BINDINGS \
  --output FRESH_O_SUBMISSION_RECEIPT
```

Root is the sole actual submitter. Different authorized tasks use different
explicit output receipts. No existing request/receipt is overwritten and no
old task is automatically resubmitted. Actual job IDs and terminal accounting
must be captured from the new receipts, not prefilled here.
