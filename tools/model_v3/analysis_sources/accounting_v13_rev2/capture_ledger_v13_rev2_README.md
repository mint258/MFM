# Accounting v13 revision2

This revision fixes one statically found historical shape: the top-level
O/A_first_candidates_export_submission_v1.json is an array containing the
already-registered GPU parents4520456/4520457. Version1's dict-only inventory
would refuse it before any scheduler query. Version1 source/pins remain.
No Python, scheduler, SSH or scientific task was executed by this preparer.

Only that exact basename and exact2 parent IDs are accepted as legacy array
metadata. They are explicitly listed with0.job_id/1.job_id field paths and
must already be in the previous exact GPU scope. No new GPU is inferred from
this array. Unknown arrays still refuse; CPU receipt validation, duplicates,
missing-ID rejection, original v12 GPU logic and all previous parents are
unchanged. O/N top-level metadata only; no recursive SDK/data/checkpoint scan.

Use the complete original explanation in capture_ledger_v13_README.md.
Root source/AST reviews these two new modules, then runs:

```bash
P=/share/home/zixiao/descriptor_analysis
N=$P/runs/model_v3_20261026
O=$P/runs/model_v3_20261025
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
"$PY" -B "$N/capture_ledger_v13_rev2.py" \
  --prepare-cpu-registry "$N/cpu_job_registry_v2.json" \
  --inventory-output "$N/cpu_receipt_registry_audit_v1/verified_top_receipt_inventory_v13_rev2.json" \
  --previous-ledger "$O/job_ledger_model_v3_active_v15.json"
"$PY" -B "$N/capture_ledger_v13_rev2.py" --validate-only \
  --gpu-registry "$N/gpu_job_registry_v8.json" \
  --cpu-registry "$N/cpu_job_registry_v2.json" \
  --previous-ledger "$O/job_ledger_model_v3_active_v15.json"
"$PY" -B "$N/capture_ledger_v13_rev2.py" \
  --label job_ledger_model_v3_active_v16 \
  --gpu-registry "$N/gpu_job_registry_v8.json" \
  --cpu-registry "$N/cpu_job_registry_v2.json" \
  --previous-ledger "$O/job_ledger_model_v3_active_v15.json"
```

The first two commands make no scheduler call. The final command performs only
read-only actual sacct/squeue accounting. It never submits/cancels a job.
All output paths must be fresh; older ledgers and registry snapshots remain.
This source revision does not assert any actual cost capture or test PASS.
