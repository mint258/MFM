# Primary512 short-checkpoint panel launcher v2

V1 and failed CPU preparation4520522 are retained unchanged. That preparation
failed before target decode/model/GPU because the real frozen request builder
uses `{path,sha256}` references (plus checkpoint `state_key`), while READY also
contains measured `bytes`. Direct dictionary equality was incorrect. V2 adds
strict cross-format semantic comparison of absolute path, raw SHA and the
declared primary state key; READY bytes remain mandatory and are independently
stat/hashed against the original physical file. Any optional candidate bytes
must also equal that measurement. No size authority is discarded.

Audit of comparisons: full READY/export refs to full spec refs retain their
exact comparisons. Initial request refs, pre-execution guard request refs,
and result encoder-pair refs now each compare to the full READY/spec authority
through the same measured adapter. No frozen scientific module is changed.
New tests call the actual SHA-pinned9638 `make_request`, assert its real compact
reference shape, pass those references through the adapter and guard, and reject
path/hash/state-key/candidate-bytes/authority-bytes/physical-file/missing-size
drift. They are not equality tests over invented identical dictionaries.

NEW model-owned preparation directory; no edits to the tested B3v2 launcher,
SA3 evaluator tree, A exporter tree, SDK originals or selected data. Prepared
only, **not tested, submitted or run**. Root coordinates compute-node permission,
CPU/GPU admission, source snapshots and Slurm submission.

Purpose: validate the real 512x6 H0/paired-random evaluation toolchain and its
inclusive one-GPU-hour target using the short 500-update A00 diagnostic
checkpoint. It is not an architecture selection, formal-pretraining completion
or claim that this short checkpoint is scientifically superior. A/B3 numerical
gates do not replace full training or two-seed evaluation. D1–D6 are not a
dependency of this existing TRAIN-only panel.

## Immutable sources and inputs

- Evaluate with the existing fully tested SA3 tree, code
  `9638f7c461a6a88b6b2469f2c7e9ec8023d276e5`, and its existing generic standard
  `model_state` bridge. No performance-option or geometry implementation is
  patched into that tree by these tools. Actual generic512 CPU bridge round-trip
  was already tested by Root in 4520439; these new launcher tests do not replace
  a real exported-checkpoint evaluation.
- Primary candidate comes only from
  `/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/A_a00_control_4520486/candidate_h0/READY.json`
  after actual numeric20/500 gates, input/SDK cleanup, bundle verification and
  successful outer-job closure. Expected actual exporter code is
  `8ece64c685fe287d6863fbbe2f6f52006632a5cc`. Its physically visible source tree
  is currently `MFM_model_v3_a_checkpoint`; the original sealed bundle refs are
  authoritative rather than a guessed worktree basename.
- Use the original READY references for `candidate.pt` (standard
  `model_state`), full `model_configuration.json`, `a_run_configuration.json`
  and `provenance.json`. Hash/check those actual bytes. Do not synthesize a
  configuration from dimensions, a kind label, or another checkpoint. The
  preparer passes the original full configuration directly to the existing
  request builder; canonical model semantics must match READY's architecture
  hash. Distinct exporter/evaluator code SHAs and the short diagnostic scope
  remain explicit in the launch spec.
- Reuse the actual complete selected-TRAIN421 source, exactly 17,602 records:
  CYP1,803 / Expansion5,326 / QM910,473. Source geometry availability and native
  masks/IDs/units remain unchanged; encodable H0 inventories can be smaller
  because the sealed source already records unavailable geometry.
- Public panel/rules preregistration remains
  `39cf4929299cd227a3c361183a4b26c8b1405900`; this differs from A's own performance
  preregistration. Existing nine tasks, fixed member/group selection, caps,
  18 cells, random seed, ridge CV, Linear64/ReLU20 epochs/B32 and shared-dataset
  1,000 paired molecular bootstrap draws are unchanged.
- Runtime/accounting comes from the read-only fixed profiler_v2 monitor at
  `/share/home/zixiao/descriptor_analysis/MFM_model_v3_profiler_v2/tools/model_v3/runtime_monitor.py`.
  Its actual SHA is measured into the spec, and the guard imports that exact
  validated `owned_output_bytes` implementation. Canonical SDK links retain
  the established rules. No copy of that accounting algorithm is substituted.

## READY is insufficient without Root terminal admission

The existing READY status is deliberately
`H0_BYTES_VERIFIED_PENDING_OUTER_JOB_TERMINAL`. It must remain that value; the
new adapter never rewrites it or infers that the outer job succeeded.
`export_admission.py` additionally requires Root's fresh successful sacct
terminal receipt and byte-bound outer supervisor, `run_status.json` and
`summary.json`. It rejects RUNNING/failed jobs, incomplete native gates, cleanup
errors, source/schema/seed/RNG/recipe drift, stale admission and changed bundle
bytes. Checkpoint reads here are opaque SHA only; `torch.load` and actual model
execution remain in the already tested frozen bridge.

Root produces a fresh external JSON receipt (actual refs contain absolute
`path`, machine `sha256`, integer `bytes`; placeholders below are not accepted):

```json
{
  "schema": "model_v3_primary512_export_admission_v1",
  "checked_at_utc": "ACTUAL_ISO8601_UTC",
  "expected_export_code_sha": "8ece64c685fe287d6863fbbe2f6f52006632a5cc",
  "ready": {"path": "ACTUAL_ABSOLUTE_READY_PATH", "sha256": "ACTUAL_SHA", "bytes": 0},
  "export_job": {"job_id": "4520486", "state": "COMPLETED", "exit_code": "0:0"},
  "supervisor": {"path": "ACTUAL_ABSOLUTE_SUPERVISOR_PATH", "sha256": "ACTUAL_SHA", "bytes": 0},
  "run_status": {"path": "ACTUAL_ABSOLUTE_RUN_STATUS_PATH", "sha256": "ACTUAL_SHA", "bytes": 0},
  "summary": {"path": "ACTUAL_ABSOLUTE_SUMMARY_PATH", "sha256": "ACTUAL_SHA", "bytes": 0}
}
```

The supervisor must say COMPLETED/exit0, no first failure, no remaining recorded
processes and no private-storage cleanup errors. The run must have no failure
or cleanup errors and must point to the same READY. Summary must confirm full
native A numeric acceptance, fixed and trajectory gates, native_s and no smoke.
The admission observation must be within one hour at CPU preparation and GPU
launch; immutable terminal inputs are rechecked after execution without
requiring a new timestamp during an admitted run. If queued beyond an hour,
Root refreshes terminal evidence and prepares a new launch spec before launch.
Include the underlying actual sacct metadata receipt/command refs as extra audit
fields if available. Never manufacture completion from the READY flag alone.

## Budgets and execution shape

CPU-only tests/preparation: at least 16 CPUs, 16 GiB, 5 minutes, no GPU, only an
approved development node. Actual evaluation: 16 CPUs, **32 GiB allocation /
28 GiB owned-process-group RSS**, one explicitly admitted full GPU UUID, cold
`evaluation/h0_cache`, common evaluation/cache/guard output cap **2 GiB**.
The guard deduplicates nested roots, includes a final output check/reserve, and
uses the original validated canonical SDK accounting. Root's existing outer
supervisor also tracks detached SDK descendants/private storage. It must use
the evaluation root as its persistent output root, not the H0 child alone.

No precision policy is changed: preserve and record FP32/default dtype,
TF32/matmul/cudnn/determinism pre/post; H0 locally disables autocast as in the
tested exporter. No batch/cap/member changes or label-based packing is made.
Packing is exactly the existing metadata-bound atom-count plan; candidate and
matching random512 use the same plan and membership. Its capacity remains a
preset until this real run validates it.

Core cooperative limit3,400s; guard deadline3,500s; TERM20s/KILL10s; total target
3,600s. The new guard's timer starts at main entry, so its READY/source
admission/checksum work is included along with H0, both readouts, bootstrap,
SDK finish and cleanup. The GPU Slurm allocation should remain one hour. Root
must include the guard's own/supervisor startup overhead when reporting actual
allocated time and target attainment. Counter values are process allocator
high-water since last reset, never a device-global GPU-memory peak. Global
GPU85% sampling is an operating guard, not a claim that an exact peak is known.

## CLI and new CPU tests

The new 30 expected tests are synthetic metadata/paired-result/accounting tests,
not real checkpoint/model/target execution. They include stale/failed outer
admission, changed weight bytes, same-shape recipe drift, historical384/incorrect
512 pair rejection, complete18cell/1,000-draw checks, and reuse of fixed
canonical SDK-link/disjoint-root accounting. Root uses actual XML collection
and source before/after hashes; no pass is claimed in this document.

```sh
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' \
  /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python \
  -B -m pytest -q \
  /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_primary512_panel_launch_v2/test_primary512_launch.py \
  --basetemp /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_primary512_panel_launch_v2/pytest_NEW_JOB \
  -o cache_dir=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_primary512_panel_launch_v2/pytest_cache_NEW_JOB
```

CPU metadata preparation (run only after READY plus actual successful terminal
receipts exist). Use full absolute paths; bind all SHA values by machine.
The code SHA refers to the evaluator, not the exporter:

```sh
python -B /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_primary512_panel_launch_v2/prepare_panel_request.py \
  --repository-root /share/home/zixiao/descriptor_analysis/MFM_model_v3_sa3 \
  --materialization-result /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/selected_train_store_4520421/materialization_result.json \
  --materialization-result-sha256 MATERIALIZATION_RAW_SHA \
  --ready /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/A_a00_control_4520486/candidate_h0/READY.json \
  --ready-sha256 READY_RAW_SHA \
  --export-admission /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_primary512_panel_launch_v2/EXPORT_ADMISSION.json \
  --export-admission-sha256 ADMISSION_RAW_SHA \
  --code-sha 9638f7c461a6a88b6b2469f2c7e9ec8023d276e5 \
  --evaluator-sha256 EVALUATOR_ACTUAL_FILE_SHA \
  --python-entry /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python \
  --output-root /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/primary512_request_NEW_JOB \
  --evaluation-output /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/primary512_dev9_NEW_JOB/evaluation
```

This calls the unchanged tested `make_request`/`load_plan` APIs; validates only
TRAIN metadata, original source closure and cohort replay; pins the packing;
writes a fresh bound request/spec; and decodes zero target frames. It does not
submit Slurm or run a model. Root then supervises the following GPU command in
its approved allocation, with the matching source pins/spec hash and physical
GPU UUID already admitted. `python` below is shorthand for the exact verified
logical interpreter above:

```sh
python -u -B /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_primary512_panel_launch_v2/run_panel_guard.py \
  --spec /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/primary512_request_NEW_JOB/launch_spec.json \
  --spec-sha256 SPEC_RAW_SHA --node ROOT_APPROVED_NODE --gpu-uuid ROOT_ADMITTED_FULL_GPU_UUID \
  --guard-output /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/primary512_dev9_NEW_JOB/guard_NEW_JOB
```

The guard checks the standard512 source/configuration/seed and all18/9/9 cells
and 1,000-draw completion, plus both encoders' native target-free cache bindings.
The actual frozen evaluator holds the existing shared UUID lock. No second
lock or scheduler GRES isolation is invented. Persistent SDK originals and
machine receipts remain outside Git. No real primary512 panel result, runtime
or capacity claim exists until Root closes that actual execution and tracking.
