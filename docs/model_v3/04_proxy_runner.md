# Source-bound proxy runner, first revision

This opt-in runner connects the existing update, safe checkpoint and H0 APIs.
It has **not been executed or scientifically accepted** when this document is
written. Root runs the new tests and records actual Slurm, source snapshots and
supervisor closure. No formal pretraining or scientific proxy run is started by
this delivery. WSD branching is a separate subsequent implementation.

The files added are `phase1/v3_proxy_run.py`, `v3_proxy_segments.py`,
`v3_proxy_engineering.py`, `tools/model_v3/run_proxy_experiment.py` and
`current/tests/test_model_v3_proxy_runner.py`. The only existing code edit is an
explicit engineering-marker rejection immediately after bound configuration
loading in `v3_decision_evidence.inspect_run`. The original trainer, sampler,
sample-budget controller, B precision experiment and encoder bridge are unchanged.

## Training and authority boundary

The runner builds the real model and `ArchitectureStepTrainer` subclass, whose
update, gradient clipping, per-500-update group-gradient probes, consumed-draw
clock, sample scheduler, AdamW, save and load remain the original implementation.
The subclass changes only validation context and reporting: fixed seed/epoch
and population hashes for both `VAL` and `TRAIN_UNSEEN_CONFORMATION`, original
field losses/MAE/R²/accuracy, actual raw SSE/RMSE and denominators. Validation
preserves training RNG and committed provider state, including provider batch
construction. The adapter must implement fixed-population validation independent
of its training-prefetch cursor. No label statistics are fitted here.

The first revision accepts explicit FP32, TF32 disabled, highest matmul precision,
and matching two-view or three-view training/validation. BF16 and cross-view
validation reject explicitly; no B registration is silently changed. Scientific
execution requires 6 layers and width512, a fixed physical GPU UUID and full model
name, a matching request, and the original UUID ownership lock. CPU execution is
an engineering fixture with CUDA hidden. Slurm allocation must have at least16
CPUs; requested Torch threads are separately frozen in the configuration.

`model_v3_proxy_request_v1` is **model-owned execution metadata**, not a new D
physical contract. Its raw-bound `configuration` is
`model_v3_proxy_configuration_v1`, with `seed`, full `model`, explicit
`proxy_contract`, immutable scope markers, runtime inventory SHA and input
projection SHA. The contract includes sample plan/milestones, groups/fields,
head forms, optimizer, schedule, conformation selection/geometry source,
training corruption, fixed validation, atom/pair budgets, execution and resources.
There is no automatic 6M budget or plateau threshold.

Real mode is the default and fails before model/SDK/output creation without all
of the following:

- Actual clean committed HEAD/tree and the complete rehashed runtime inventory.
  Root supplies the fixed compute Git2.39.3 in PATH; the CLI uses actual Git,
  not a fabricated clean flag. Actual code SHA differs from public registration
  SHA when appropriate, and both are recorded.
- Explicit preregistered budget/validation and purpose refs. A separately
  registered `calibration` scope allows the first budget curve without requiring
  an already-confirmed platform. `comparison` requires registered selection and
  platform policies; `recipe` also requires a recipe policy. Each policy uses
  `model_v3_proxy_registered_policy_v1`, explicit purposes, configuration identity
  excluding only top-level training seed, and the registered pretraining seeds.
  Budget and validation contents must exactly match. References bind fixed local
  Git blobs and explicit public commit/tree mappings. Commit dates alone do not
  establish public availability; Root admission remains required.
- Raw-bound `model_v3_proxy_Root_admission_v1` with status
  `ROOT_ADMITTED_FINAL_INPUTS`, scope/code/tree/config identity and the canonical
  request identity excluding this admission reference. Its evidence slots refer
  to existing D1–D5 and actual three-GPU SDP integration evidence. These symbolic
  slots do not reinterpret the data-line files. The CLI hashes their raw bytes;
  the separately pinned authority adapter verifies their actual semantics.
- A raw-bound adapter exposing
  `verify_and_bind_model_v3_proxy_inputs(request) -> ProxyInputs`. It must verify
  this exact request, final accepted data-line authority and the actual240000
  molecule TRAIN proxy, then return the existing sampling index, LabelRegistry,
  StructuralFieldBinding, D4 transforms and read-only node-local PreparedV3Batch
  provider. A draft/candidate provider cannot be promoted by a CLI switch. The
  returned opaque receipt and index/registry/normalization/adapter/data-version
  projection must match the frozen request. A/B integration uses this hook;
  this delivery does not copy unmerged A/B implementations.

Engineering requires **both** `--input synthetic --engineering-only` and matching
immutable configuration markers. The analytic fixture supplies no D release or
science acceptance. It records base Git SHA and full raw runtime inventory with
`engineering_raw_inventory_not_claimed_in_base_commit`; dirty new code is never
claimed to be contained by that base commit. Such configurations are rejected by
the scientific selector even if their real checkpoint has a working512 H0.

## Immutable lineage, restoration and independent evaluation

Each job has a fresh outside-Git root with `training/`, SDK and durable history.
A disjoint canonical ledger first registers launch allocations before SDK/model
initialization, so failed initialization roots remain in the global attempt and
storage census. It then retains immutable segment registrations, checkpoint
events and independently completed ACKs. Short metadata locks and a separate
nonblocking training lease allow a separate evaluator to ACK old events while
one training segment runs. No three candidate models coexist in the trainer.

Resume requires a previously registered **complete wrapper checkpoint**. The
original strict loader restores model, AdamW, sampler/provider committed state,
RNG, scheduler, clock, validation and log cursor under the exact parent contract.
Changing budget, sources, optimizer, configuration or execution is not resume.
The fresh SDK run records the parent run; canonical ACKs are neither copied from
nor rolled back to a checkpoint snapshot. Existing partials, failed publication
attempts and unpublished records remain and count against limits. No cleanup
deletes old checkpoints. An incomplete wrapper is not silently repaired; Root
may separately review the existing explicit repair path.

Original milestones, registered panel points, recovery intervals and the exact
final budget all cause original safe saves, including a non-power-of-two final
budget. Checkpoint and segment-attempt caps apply across all registered jobs,
including partial directories. A segment can save and return `SEGMENT_PAUSED`;
it cannot reset its global sample/count/storage budget. Bare/unsupported encoder
contracts cannot emit a false READY event. Engineering1layer events are blocked;
the engineering6layer test must actually load through the existing generic512
bridge before being reported as a tested roundtrip.

`ack` delegates to the existing strict evidence validator: complete18cells,
both9-task readouts,1000 bootstrap draws, matching random512/H0 source/cache/
membership/readout, immutable result bytes, actual successful Root terminal
receipt and independent native SDK certificate. There is no manual “success”
boolean. Synthetic evidence used by a unit test proves only protocol rejection
and persistence. Child receipts say `CHILD_FINISHED_PENDING_ROOT_CLOSURE`, never
scientific COMPLETE or Slurm C0. Root verifies actual sacct/supervisor terminal
state and native SDK independently.

## Capacity and supervision

The **joint lineage cap remains2GiB**, including all prior registered job roots,
the fresh job, SDK/caches/history and canonical ledger, with disjoint-root
deduplication. Fresh segments do not get new storage. The original outer
supervisor must use an output budget no larger than `joint_output_bytes -
ledger_bytes`; its original96MiB reserve remains. The child additionally reserves
SDK/metadata capacity, checks RSS, physical GPU ownership/85% memory, wall time
and proposed checkpoint capacity. A further RLIMIT_FSIZE bounds actual save
bytes by remaining joint capacity, in addition to the original segment save cap.
Wall allowance includes SDK finish and remains <=2h. Outer supervision is still
required; cooperative checks do not certify OS-level closure.

For the historical22,352,859-parameter6x512+A4 model, FP32 parameter storage alone
is89,411,436bytes (85.2694MiB). A hypothetical full AdamW state for every parameter
adds178,822,872bytes:268,234,308bytes (255.8082MiB) before buffers, provider/RNG,
serialization, new PD heads or SDK. Four checkpoints at1/2/4/6M in that hypothetical
scenario use1,072,937,232bytes; seven at1/2/4/8/16/32/64M use1,877,640,156bytes.
These are **planning scenarios, not actual checkpoint-size lower bounds**:
unexecuted legacy heads may have no Adam moments, while new D/P heads increase
storage. An extra retained recovery/segment-end checkpoint costs another full
payload. Final D labels/heads have not been delivered, so64M capacity is not
proved by a small synthetic fixture.

`checkpoint_capacity()` reports actual model tensors, materialized optimizer
tensors, their tensor floor, a hypothetical full-moment scenario and a15%+8MiB
planning reserve explicitly marked unproved. Original `COMPLETE.payload_bytes`
is the actual measurement. The real6x512 engineering bridge test prints both.
The exact final data-line configuration must be measured before registering a
long curve. Available policy is explicit milestone/final retention with a sparse
registered recovery interval, bounded segment endpoints/counts and early safe
pause. Neither extra recovery snapshots nor segment boundaries should be added
without accounting for their full payload. If all required immutable checkpoints
plus SDK do not fit, the runner must stop; no automatic deletion, guard expansion,
checkpoint pruning or altered checkpoint format is implemented here.

## Root execution examples and pending validation

All commands below are prepared examples, **not commands already run**. Root
chooses the actual CPU/GPU allocation, exports the existing dependency overlay,
checks shared resources and supplies the actual interpreter and source receipts.
No package changes are required (existing Torch/PyG/NumPy/W&B/psutil only).

```bash
export PATH=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/cpu_git_tools_v1/bin:$PATH
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/MFM_model_v3_proxy_runner/current:$PYTHONPATH
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
ROOT=/share/home/zixiao/descriptor_analysis
TOOL=$ROOT/MFM_model_v3_proxy_runner/tools/model_v3/run_proxy_experiment.py
# Metadata only; explicit base SHA does not claim these new bytes are in it.
$PY "$TOOL" prepare-engineering --output "$ROOT/runs/NEW/proxy_request" \
  --base-code-sha e47d066e53f000d71c05bf1c772597f2a5c42c30 --layers 1 --sample-budget 3
# Root reads request.json raw SHA from the machine-generated binding above.
# Use the original supervisor;2GiB minus16MiB ledger =2130706432.
# Pass actual owned GPU UUID for CUDA. Existing supervisor CPU testing may need
# Root's validated CPU supervisor rather than the GPU-only run_supervised CLI.
$PY "$TOOL" run --request "$ROOT/runs/NEW/proxy_request/request.json" \
  --request-sha256 ACTUAL_RAW_SHA --input synthetic --engineering-only \
  --output "$ROOT/runs/NEW/job1" --lineage-root "$ROOT/runs/NEW/ledger" \
  --lineage engineering-example --segment-id one --until-samples 2
# Fresh job2 uses the same immutable request/configuration and ledger:
# ... --output .../job2 --segment-id two --until-samples 3 \
#     --resume-complete ACTUAL_JOB1_WRAPPER_EXPERIMENT_COMPLETE_PATH
$PY "$TOOL" status --lineage-root "$ROOT/runs/NEW/ledger" --ledger-bytes 16777216
# Independent evaluator, after actual panel/SDK/Root closure:
# $PY "$TOOL" ack --lineage-root ... --ledger-bytes 16777216 \
#   --event ABS_EVENT_JSON --result ABS_PANEL_RESULT_JSON --evidence ABS_ROOT_EVIDENCE_JSON
```

The `run` example additionally requires the original supervisor child-budget
environment and a real>=16CPU Slurm allocation; invoking it directly without
those bindings rejects. It does not submit anything. All required segment
endpoints, resumes and ACK evidence are explicit. Default real mode omits both
engineering flags and requires the actual admitted request described above.

Prepared targeted test command: `python -m pytest -q -s
current/tests/test_model_v3_proxy_runner.py`. Expected collection is20 cases,
including an actual native offline SDK two-interpreter resume test and one
6x512 original safe-checkpoint/H0 roundtrip. The test requires Root's actual
Slurm allocation, hidden CUDA, adequate job storage and the existing W&B SDK.
It does not fabricate a Slurm job ID or CPU allocation. Root should measure
fixture bytes in its original joint output census and shard if necessary.
Full relevant regression includes the original sample-budget, trainer,
architecture, bridge and decision suites; Root chooses bounded shards.

At this delivery, tests are **prepared/unrun**. Real D3 three-GPU integration,
final D5 authority, registered calibration/proxy curves, pretraining-seed SD,
platform/spike decisions, WSD fork and full plan completion remain outstanding.
