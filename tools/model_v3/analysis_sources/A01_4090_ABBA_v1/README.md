# A01 actual RTX4090 standalone A/B/B/A preparation

New external sources only. Nothing in the original4520456 run, original8ece
tree, original SDKs or old A03 helpers is changed. No Python/test/SSH/GPU job or
submission was executed by the preparing agent. New metadata tests, public
registration and GPU observations remain pending Root execution.

The earlier3090 label was an operational misclassification, corrected before
writing this package. Original configuration and supervisor both identify
**NVIDIA GeForce RTX4090**, UUID
`GPU-ec788ed1-7da1-8f93-bb23-b4fdb2018b02`, node`compute-0-20`, Python
`/share/home/zixiao/.conda/envs/chemprop/bin/python`. The original machine NVML
capacity/driver and Torch-visible capacity are separately copied from the
original configuration, without assuming a commercial card's capacity. No3090
protocol or numeric qualification is implied.

## What is preregistered

`protocol.json` fixes sequential **reference, candidate, candidate, reference**.
Each member starts a fresh process, seed0 model and optimizer; one model is
resident, no torch.profiler, original native-S data/loader/capacity, original
FP32/TF32/determinism and A01 candidate options. It invokes the unchanged
`tools/model_v3/single_a_benchmark.py` in the frozen8ece tree: **2warmup updates
plus20 measured updates**, not500 timing updates. Original20-batch/500-update
numeric acceptance is a prerequisite only. The paired run's3043s allocation
cannot predict the short standalone window, and does not establish speedup.

Per-member sbatch remains the accepted A03 timing envelope: **20minutes**, outer
supervisor1100s,16CPUs,64GiB Slurm memory request,56GiB software RSS limit,
2GiB persistent output and2GiB node-private storage. The previous provisional
45minute idea was removed before freeze. Four members have an explicit maximum
4800 allocated GPU seconds; failed allocations are retained in actual cost.
No formal pretraining or school-server work is started.

The whole per-member output root is created before sbatch and contains the
Slurm log, prelaunch/worker observations, supervisor record/journal, benchmark,
SDK/cache and final source closure. The supervisor counts this single common
root with its existing2GiB census. No nested root is double-counted. The final
closure uses the same fixed original census and must also fit2GiB. Up to four
such roots are retained, plus a separately declared64MiB finite management
envelope (12 admission attempts); all count toward the real filesystem quota.
There is no deletion, automatic retry, count reset or hidden output move.

## Numeric/source admission before every member

The original4520456 summary/status/configuration, all20 fixed-batch results,
all500 trajectory results and actual parent C0 are required. The original
supervisor must have no remaining recorded processes, cleanup errors, foreign
GPU signalling or failed private-storage samples.

There is no standalone`source_closure.json` in that original run. Admission
instead explicitly checks the saved `candidate_h0/provenance.json` source map,
the original configuration source map, READY inventory digest and bound raw
gate/config/history files. The original exporter actually called
`verify_source_inventory` before constructing that provenance. The new helper
rehashes every original source file on the server CPU and checks clean Git HEAD
`8ece64c685fe287d6863fbbe2f6f52006632a5cc`. It also rehashes original native-S
metadata/histories and both source offline SDKs (`v37vklr4`, `6r67khz4`) as opaque
files. It never opens the checkpoint weights, native geometries or labels, and
does not infer native-SDK readback success from a mirror or file hash.

The original candidate-options raw SHA is
`d3bb101a8e5417fcbe998c39f97698e6902a9b06851a343aa0a0e4830ef0e8d4`;
the original A prerequisite commit remains
`61658a4c1f472de035601dbedc17809315774784`. Complete original numeric acceptance
qualifies this actual options/source/data/4090 combination; it is not standalone
timing or a cross-GPU result.

The new source protocol must be publicly registered before any GPU submission.
`admit_abba.py` validates an explicit Root exact-tree publication receipt,
actual local tree and byte-identical Git blobs for all new source files and
source pins. Publish `protocol.json` as
`configs/model_v3/a01_4090_abba_v1.json`; other files and source pins go under
`tools/model_v3/analysis_sources/A01_4090_ABBA_v1/`. The new launcher/publication
commit and original model execution commit are recorded separately.

Actual CPU QA is also required before submission. Root supplies a small
`model_v3_A01_4090_ABBA_QA_closure_v1` JSON containing `job_id` and a raw
`unit_result` reference `{path,bytes,sha256}`. The actual unit result must have
returncode0, counts`{tests:52,failures:0,errors:0,skipped:0}`, unchanged before/
after source maps including all six files plus source pins. The helper checks
the actual QA parent C0 itself. No prepared manifest counts as actual QA.

## Resource and process checks

- All users' queue memory declarations are summed, including per-CPU scaling
  and pending declarations; unknown/duplicate rows fail. Admission takes
  `max(all_user_declared, controller_AllocMem)+new64GiB`, strictly below85% of
  controller RealMemory, with actual16CPU headroom. The active worker does not
  double-add its own allocation.
- Actual `/proc/meminfo` must retain15% of measured MemTotal after deducting a
  planned64GiB working set from MemAvailable. The explicit64GiB Slurm request
  is retained; no lower memory claim is made from unmeasured RSS.
- Fresh successful real user quota must still have64GiB after reserving the
  next2GiB output. No `df` replacement or old quota snapshot is accepted.
- Exact physical UUID/name/driver/NVML total capacity must match original
  machine metadata, and that UUID must have no compute process. Both login and
  worker check current hardware. The public UUID lock is probed; the unchanged
  benchmark takes the actual lifetime nonblocking lock. A probe is not a GRES
  reservation or a claim that other users cannot race.
- Actual worker Slurm job/env, cgroup and CPU affinity must match the immutable
  Root submission/nonce/position/output. Literal AllocTRES/ReqTRES/MinMemoryNode
  are checked if available. Only an explicit Slurm transport outage can reuse
  an exact matching successful Root controller/C0 observation <=90s old, adding
  the full new64GiB request to pre-job memory. Actual local physical-memory,
  GPU and lock checks are never replaced. Semantic failures never fall back;
  unavailable allocated-memory TRES is not falsely reported as observed.

Root serializes submission under a series lock, writes a non-replayable
position intent before sbatch, and retains ambiguous stdout/failures. Position2
requires position1 actual C0 plus closed child/SDK/input/supervisor/source
evidence; likewise positions3 and4. A failed or ambiguous submitted position
cannot be retried by this protocol; preserve it for Root review. Resource-only
preflight rejection can be attempted again with a fresh receipt within12 total
admission attempts, without deleting prior evidence.

## Root-only commands

Use physical absolute paths and machine-computed raw hashes. Root must provide
an existing strict compute20 known-hosts file, actual publication receipt, and
actual QA receipt. The helper records the exact raw commands/returncodes,
timestamps, all-user memory, quota and source bindings before calling sbatch.
It never uses an online W&B client or touches another user's process.

```sh
task_source=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/A01_4090_ABBA_v1
task_output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/A01_4090_ABBA_outputs_v1
# Invoke only after actual CPU QA and byte-identical public registration.
python -B "$task_source/admit_abba.py" submit --position 1 \
  --source-pins-sha256 "$task_source_pins_sha" \
  --record "$task_output/position1_attempt1.json" \
  --publication "$task_publication" --publication-sha256 "$task_publication_sha" \
  --qa "$task_QA_closure" --qa-sha256 "$task_QA_sha" \
  --known-hosts "$task_existing_strict_compute20_known_hosts"
# Later positions use the same registered sources and add exactly the previous
# actual SUBMITTED receipt (freshly hashed), after its actual C0 and cleanup.
# --previous-submission /absolute/previous.json --previous-sha256 "$task_previous_sha"
```

The actual worker is launched by the new sbatch template. It uses the fixed
Git2.39.3 tools path, chemprop Python and the same known source/runtime settings.
Its final source/child success record explicitly does not assert outer Slurm C0;
Root captures that separately before admitting the next position.

## Reporting after all four actual completions

Use the unchanged original `tools/model_v3/a_speed_report.py`. Pass the four
`benchmark` subdirectories in A/B/B/A order and their corresponding per-member
`supervisor.json`, with original `--numeric-gate`4520456. The original report
requires matching complete model/optimizer/loss/reference/source/data/control
configuration, exact measured input-receipt digest, no grouping/foreign GPU,
2warmup+20 full native-S measured updates and matched20/500 numeric gates.

Pooling sums consumed base records/native atoms and divides by summed measured
wall time per role. No new threshold, median substitution, causal percentage,
seed SD, stable speedup or recipe adoption is invented. Keep all four raw short
windows and cold-start/cleanup/failure/allocation costs visible. Torch memory
counters are measured-window counters after reset, not whole-job/device-global
peaks. SDK archives/readback are independent evidence; hashing the originals
does not replace their eventual independent SDK verification.

## CPU metadata tests for Root

Expected **52 cases**, stdlib+existing pytest only, zero model/SDK/geometry/
target access and no subprocess/SSH/sbatch invoked. Tests cover actual complete
20/500 proof shape,4090-vs3090/capacity/source rejection, max(queue,AllocMem),
physical reserve/quota/freshness, exact process/controller/sbatch identity,
transport-only Root reuse, sequential20-update completion, immutable receipts
and template caps. Synthetic hardware numbers are fixture values, not a new
measurement. Test retained metadata is estimated below1MiB, with zero model
checkpoints or embedding files; Root records actual peaks.

```sh
export CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
python -B -m pytest -q -s /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/A01_4090_ABBA_v1/test_abba_admission.py
```

Model CPU QA remains >=16CPUs with explicit finite memory (Root may use16GiB),
85%/MemAvailable/quota and existing2GiB software storage guards. The separate
`A06_verifier_resource_scope_corrigendum_v1.md` corrects an earlier frozen A06
README's accidental application of a data-line-only no-memory-flag rule; those
frozen six A06 sources and original evidence are untouched.
