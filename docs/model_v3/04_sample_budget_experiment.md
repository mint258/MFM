# Consumed-sample experiment and checkpoint outbox

Prepared opt-in API, based on `bdd03f483b2794124d7394a1364e111324420f46`.
Only two new library modules, one new test module and this document are added.
Existing trainer, B precision controller, sampling, checkpoint implementation,
H0 bridge, data adapters and scientific configurations remain byte-identical.
No scientific training, Slurm submission or WSD fork is started by this API.
Targeted CPU validation4520521 completed C0/204s on compute-0-8: all23
collected cases passed, including real512x6 checkpoint/H0 round-trip. Frozen
implementation/test sources matched before and after. Complete branch and
postmerge regressions are separately required; this is synthetic/API evidence,
not D-dependent training acceptance. External receipt:
`runs/model_v3_20261025/frozen_units_4520521/sample_budget.json`.

The original `V3StepTrainer.run` saves only reached `clock.milestones`; its
default 1/2/4/8/... million list omits a6-million endpoint. The existing test
`test_fixed_budget_splits_milestones_and_never_overruns_or_retains_history`
intentionally confirms a5-draw budget saves only2/4. The new wrapper calls
original `next_step`, `validate`, `save`, `load` and `flush_pending_log`; it adds
checkpoint publication at every original milestone and at the final budget,
including a final point that is not an original milestone.

## Explicit model-side plan

`SampleBudgetPlan` requires the sample budget, panel and validation sample
points, validation roles, recovery interval in base draws, maximum batch draws,
per-segment and total checkpoint counts (partials count), wall and byte caps,
and checkpoint byte/time reserves. Each `run` additionally requires a fresh
segment ID and an explicit advancing sample endpoint. No6M default, platform
threshold, automatic budget extension or architecture decision exists.

The clock is the actual committed `len(choices)` from the existing sampler:
one uniformly sampled molecule/conformer choice is one base draw. Replacement
draws count repeatedly; uniqueness, atoms, two/three physical views, speculative
prefetch and optimizer updates are different quantities. No-label batches
advance sampler/clock/scheduler while leaving optimizer-update count unchanged.
The wrapper checks budget agreement and uses original atom-aware batch packing.
It limits each `next_step` to the nearest declared sample event/endpoint, so it
never skips a milestone or overruns the exact budget.

Recovery/validation boundaries can split batches; consequently their frequency
is part of the immutable experiment contract and must be fixed for comparisons.
Changing plan, budget, schedule, source bytes, registry, normalization, provider
or recipe on resume fails. This is not a scheduler continuation/fork facility.

`input_scope` is either `synthetic_fixture` or `externally_supplied_adapter`.
Neither the plan, manifest, callback nor completed checkpoint grants actual D
authority or scientific acceptance. Production still needs independently
accepted source data, populations, units, atom identities and normalization.
No new physical D schema is generated. Existing validation is reused with its
separate `VAL` and `TRAIN_UNSEEN_CONFORMATION` populations and its original
RNG/provider/mode preservation. No downstream final role is introduced.

Illustrative fixture API (small integers are deliberately synthetic):

```python
from phychem_mfm.phase1.v3_sample_budget_experiment import (
    SampleBudgetPlan, SampleBudgetExperiment,
)

plan = SampleBudgetPlan(
    sample_budget=5, panel_samples=(2, 4, 5),
    validation_samples=(2, 4, 5),
    validation_roles=("VAL", "TRAIN_UNSEEN_CONFORMATION"),
    recovery_interval_samples=2, max_batch_samples=3,
    max_checkpoints_per_segment=2, max_total_checkpoints=16,
    max_segment_seconds=600, checkpoint_reserve_seconds=30,
    checkpoint_reserve_bytes=2 * 1024**2, max_segment_bytes=2 * 1024**3,
)
experiment = SampleBudgetExperiment(
    trainer, plan, output_root=NEW_EXTERNAL_EXPERIMENT_ROOT,
    lineage=EXPLICIT_LINEAGE, input_scope="synthetic_fixture",
    model_configuration=FULL_CONFIGURATION_FILE_REFERENCE,
    panel_binding=FROZEN_PANEL_SOURCE_BINDINGS, panel_required=True,
)
segment = experiment.run(
    segment_id=NEW_SEGMENT_ID, until_samples=5, preflight=ROOT_PREFLIGHT,
)
# A new job reconstructs the same trainer/plan/experiment before:
experiment.resume(EXPLICIT_CHECKPOINT_DIRECTORY)
```

`model_configuration` is an owned ordinary full-file `{path,bytes,sha256}`
reference; its raw SHA must equal the trainer's configuration binding. Panel
bindings contain `panel_sha256`, `training_store_sha256`, per-dataset
`membership_sha256`, published `preregistration_sha` and actual evaluator
`code_sha`. Those identify the existing selected TRAIN panel; they do not
describe training-data authority or become a new data-line format.

## Immutable checkpoint and event publication

Each fresh checkpoint directory first receives a sealed `INTENT.json` containing
the plan/source contract, committed sample/update/history cursors, previous
checkpoint refs and sample-bound validation receipts. Original trainer save
writes `trainer/payload.pt` and its `COMPLETE.json` last, through its existing
weights-only readback and SHA/clock checks. Wrapper state then binds those exact
files. `EXPERIMENT_COMPLETE.json` is published last and fsynced with its directory.
Only then is an immutable outbox event published. File writes are exclusive;
identical republishing is idempotent, while different or malformed partial
metadata is preserved and rejected. No existing checkpoint is overwritten or
deleted, no marker is fabricated, and no parameter namespace is translated.

The event ID binds lineage/plan/panel identity, actual sample/update cursors,
checkpoint bytes, native completion marker and full configuration. A different
event cannot take over an already published sample point: resuming an older
checkpoint into a lineage that already published that future point fails
rather than silently forking or evaluating that point twice. Explicit new
lineage design is outside this API.

At panel points the status is `READY` only for the existing bridge-supported
`ArchitectureStepTrainer` contract with authentic architecture-extension source
hashes, full configuration and512x6 encoder. The publisher checks capability
metadata, not a second model; the isolated evaluator still performs the actual
safe checkpoint load. Bare `V3StepTrainer` and B `PrecisionStepTrainer` records
remain `BLOCKED_UNSUPPORTED_ENCODER`. `panel_required=True` rejects unsupported
input at initialization, before creating outputs. No extension is invented for
them. Non-panel recovery records are `RECOVERY_ONLY` when the encoder supports
the bridge. All original milestones and the final budget must be panel points.

The training process runs one model and the original validation only. It never
loads candidate/reference encoders or executes the downstream panel. Root may
inspect `experiment.controller.pending()` and schedule **only READY** events in
separate approved jobs, using the unchanged request builder/evaluator and the
event's checkpoint/configuration/completion refs. Blocked/recovery-only events
remain explicit records, not executable evaluations.

## Resume and failure semantics

Resume authenticates intent/wrapper/validation/marker/payload contracts before
calling the original trainer load. It restores actual model, optimizer,
scheduler, sampler, provider, RNG, execution flags, validation state and tracking
cursor. An intact original COMPLETE plus intact intent can finish publication
interrupted before wrapper completion; a complete wrapper whose outbox publish
failed republishes the same event ID. Corrupt partial metadata/payload is
retained and fails closed, requiring Root review or the last valid checkpoint.

Only explicit post-commit trainer `pending_log` state with matching
sampler/clock/scheduler cursors permits an emergency recovery save. That record
is not published for panel evaluation. A fresh resume first uses the original
`flush_pending_log`, then saves/publishes a new acknowledged-tracking checkpoint.
An arbitrary optimizer exception may have partially modified parameters before
the base-draw commit; the wrapper never promotes that state to a checkpoint.
It records the failure and leaves the last complete checkpoint authoritative.
Partially completed validation receipt sets can be recomputed on resume using
the original RNG-preserving validator; they are not evaluation ACKs.

ACKs live in a separate append-only ledger, not solely in training checkpoint
state. Loading an older checkpoint therefore cannot roll back a later ACK.
An ACK needs the exact event's candidate/configuration/seed/512 architecture,
same TRAIN membership and candidate/random H0 geometry/packing/runtime/state,
all18 cells and both separate9-cell means, and1,000 defined bootstrap draws.
It additionally requires bound successful Root terminal evidence and an actual
independent SDK certificate for the exact result bytes, run, exit, history count
and clean EOF. A boolean in the core result alone is insufficient. The API does
not generate those receipts. ACK publication has its own final complete marker;
partials are retained, and attempts without a complete marker remain pending.
Repeated identical ACKs are idempotent; changed evidence is rejected.

`controller.curve()` returns aggregate task errors/counts/intervals, separate
18/9/9 means, sample-bound original field validation metrics, and the original
runtime counters captured before that save, sorted by actual consumed draws.
It does not invent an RMSE absent from the supplied original validator. Process
GPU counters retain their since-last-reset scope. Missing, blocked and
pending points stay explicit. No predictions/member IDs, fabricated scores,
platform criterion, seed SD from a single seed, model choice or scientific
acceptance is generated. Core flags and SDK originals are never rewritten.

## Resource limits and remaining operational obligations

Each segment is bounded at no more than2 GiB and7,200 seconds; checkpoint count,
total attempts, endpoint and reserves are explicit. At a count limit the wrapper
returns `SEGMENT_PAUSED` immediately after a safe completed checkpoint. A
cooperative `SegmentPause` from preflight requests a save/pause. Resume uses a
fresh segment/job; old complete and partial files remain. Total checkpoint and
segment attempt caps prevent unlimited accumulation inside this lineage. Root
must reserve project-wide/quota storage across jobs and select adequate caps
before running; the library does not archive/delete old checkpoints or silently
increase a contract that is exhausted.

Before each step, validation and save, the cooperative hook receives actual
elapsed time, segment bytes, sample/update cursors, checkpoint counts and
`payload_capacity_proven=False`. An external adapter requires this hook so Root
can also inspect RSS, GPU/global occupancy and the complete job output forest,
including its W&B SDK/cache/private roots. The wrapper's own census covers its
physical checkpoint/metadata segment, rejects links and does not replace the
validated canonical SDK output census. The actual root supervisor still enforces
the joint2 GiB budget, hard deadline, ownership and descendant cleanup.

Payload size/time for arbitrary future D heads is **not predicted or proven**.
The wrapper temporarily caps the original save's per-file `RLIMIT_FSIZE` to
actual remaining segment bytes minus the caller's metadata reserve, restoring
the original limit afterward. It also checks actual bytes after publication.
An oversized/failed serializer may leave a partial directory; that is evidence,
not a complete checkpoint. Metadata is capped at2 MiB per file. A time reserve
cannot prove an unknown save's duration; Root must supervise the whole operation
and choose safe endpoints/reserves from real measurements. No85% memory or
two-hour success guarantee for unmeasured heads is claimed.

## Prepared CPU verification

Exact new test path: `current/tests/test_model_v3_sample_budget.py`.
Expected collection is23 cases; actual pytest XML determines the result.
Tests cover the original trainer's real numerical recovery (model/optimizer/
provider/scheduler/RNG/validation), final non-milestone save, no-label three-view
base clocks, count/preflight pause, unsupported contracts, original-save
partials, checkpoint-to-event interruption, pending tracking recovery, unsafe
partial optimizer rejection, contract/partial metadata drift, ACK after resume,
alternative-event rejection at an ACKed point, wrong panel/SDK/terminal sources,
partial ACK preservation and explicit frequency/count/wall/byte validation.

One test uses an actual512x6 `ArchitectureStepTrainer`, real safe checkpoint and
the existing generic H0 bridge. It verifies candidate weights, matching random
configuration, exact candidate H0 correspondence and `[3,512]` candidate/random
shape on a three-atom synthetic geometry. It reads zero downstream targets.
Other receipt fixtures are intentionally synthetic and do not prove SDK/job/D
authority. Unit trackers are not persistent tracking evidence.

Root alone runs the prepared tests in an approved development CPU allocation,
at least16 CPUs with adequate memory and a bounded external pytest directory:

```sh
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' \
PYTHONPATH=/share/home/zixiao/descriptor_analysis/MFM_model_v3_sample_budget/current:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps \
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m pytest -q \
 /share/home/zixiao/descriptor_analysis/MFM_model_v3_sample_budget/current/tests/test_model_v3_sample_budget.py \
 --basetemp /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sample_budget_units_NEW_JOB \
 --junitxml=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sample_budget_units_NEW_JOB.xml \
 -o cache_dir=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sample_budget_pytest_cache_NEW_JOB
```

Suggested initial validation allocation:16 CPUs/32 GiB/10 minutes, CUDA hidden;
Root's source snapshots and resource supervisor remain mandatory. No actual
test, data training, capacity validation or scientific plateau has been claimed
by preparing these files.
