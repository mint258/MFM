# Opt-in finite long-run storage

This revision is prepared/unrun at delivery. Root owns all actual tests, Slurm,
quota coordination, source snapshots, commits and scientific admission. This
module/CLI **does not create a real quota reservation or start training**.
It verifies/adopts a finite reservation already issued by Root. No model,
labels, losses, numeric update, sampler, optimizer, original safe save/load,
H0 interface or original single-job supervisor has been changed.

Earlier lifetime2GiB was a prototype constraint, not the user's full-condition
limit. The guide requires ordinary recovery checkpoints in addition to seven
milestones; at150 base records/s,64M is118.5h pure training. An illustrative110min
useful segment yields65segments/71CP, not seven retained files. The source audit
and16/80/112GiB planning scenarios remain external at
`runs/model_v3_20261026/long_run_storage_plan_v1/`. Those values are not defaults,
approved reservations, final-D size bounds or measured convergence.

## Default and explicit opt-in

Absent `configuration.long_run_policy`, the original prototype lifetime2GiB,
128 maximum/default16 checkpoint rules and original CLI/ledger behavior remain.
The old frozen Proxy/WSD trees are untouched for exact old-source reproduction.
New shared source bytes are not silently accepted as old scientific checkpoint
provenance. Default regression must still pass on this new branch.

The optional `model_v3_long_run_policy_v1` contains only common seed-independent
finite numbers: `segment_bytes`, `segment_seconds`, `durable_bytes`,
`metadata_bytes`, `metadata_records`, `managed_roots`, `inode_limit`,
`quota_max_age_seconds`, `checkpoint_bytes`, and the independent `counts` object.
Segment output remains<=2GiB, wall<=7200s and matches the original resource
envelope; the original supervisor/RSS/GPU/private-storage checks remain. Durable
capacity is separately explicit and finite. There is no80GiB scientific default.

Independent counts are `launch_attempts`, `successful_segments`,
`failed_attempts`, `checkpoint_attempts` (including partial),
`complete_checkpoints`, `successful_panels`, `failed_panels`, `wsd_children`,
`events` and `ack_attempts`. Zero disables an optional activity. The original
`sample_plan.max_total_checkpoints` now equals the opt-in checkpoint-attempt
allowance, without also becoming the launch/segment cap. Root must preregister
consistent bounded counts for the actual curve, recoveries, failures and forks.

Only `request.long_run` carries seed/run-specific authority:

- `reservation_principal`: `model_v3_Root_durable_reservation_v1`, Root's finite
  UID/FS slot, immutable durable-root identity, cap, historical bytes/counts,
  additional reserved bytes, policy SHA and common configuration identity (or
  a finite predeclared family identity list for WSD). Its raw-bound
  `Root_reservation_record` must agree. No JSON here claims an OS quota API made
  a physical reservation; Root's real shared coordinator is the authority.
- `profile`: `model_v3_Root_long_run_profile_v1`, with actual checkpoint/SDK
  growth, save, combined two-population validation, panel and cleanup costs,
  provider/optimizer future-growth bounds and source/config/data identity.
- `quota_feed_descriptor`: Root-authorized UID/FS/producer-source/live path.
  The worker rereads the actual bounded feed, checks raw stdout, positive native
  user quota limits in KiB, other unspent reservations, headroom, inodes and
  freshness<=90s, then saves the observed bytes as an immutable SHA snapshot.
  The live path is mutable publication, not falsely pinned to its first SHA.
- `lease`, `Root_segment_admission` and `initial_roots`: bounded immutable
  operational records. Each segment admission binds its physical job/canonical
  roots, segment ID, external guard/cache/panel roots and actual allocated job
  ID in science mode. Lease must cover the whole segment at launch.

Root reservation refs/IDs, current quota snapshots and segment receipts are
absent from scientific recipe identity and trainer bindings. A fresh segment
request may update only Root admission, quota descriptor and lease references;
the remaining scientific/configuration/data/source/principal identity is exact.
Every canonical lineage records that stable identity; renewed requests cannot
reset it. WSD family child registration retains its original immutable request
and accepts only the same stable operational identity on renewal.

The explicit capacity-profile projection includes model, selected heads/groups,
optimizer, sampler/geometry, precision/batches, validation, corruption,
execution, input projection and runtime sources. It excludes storage cap-derived
metadata and the budget/schedule/fork provenance, avoiding a profile/cap hash
cycle and allowing a preregistered same-capacity WSD child. It is not arbitrary
recursive seed/hash deletion. Historical data/authority receipts should identify
the immutable release; per-request verification identity remains separate.

## Scientific refusal and measurements

Real mode retains original accepted-final-D adapter/Root admission and registered
scope/budget/validation gates. Long-run science additionally requires actual
final-D profile, successful Root terminal and saved measurements matching the
profile projection, future-state evidence and current real quota/lease. It checks
CP+future growth against payload cap, worst-case registered saves against the
original segment space, SDK against reserved tracking bytes, save/cleanup timing
and total validation overhead. Missing or synthetic/draft evidence rejects before
model/SDK/output creation. Root labels alone do not replace actual final-D proof.

The profile also requires measured base-record throughput, worst-case history
root count and accounting cost. The first implementation performs conservative
full root/index census and can be expensive at a long history. A small fixture
does not prove its64M throughput. Root must measure accounting at the intended
root/metadata scale and include it in the real profile and segment budget before
science admission. No claim of completed6M/64M capacity or performance is made.

The native quota parser follows the proven archive receipt's raw-row/UID/positive
limit approach; its archive-specific34GiB/closed-job rules are not reused.
`df` cannot substitute for actual user quota. Both positive limits zero is
unknown and rejects. Every actual write still consumes the same UID quota;
historical bytes count once in actual quota but stay in durable accounting.
Other outstanding unspent slots and headroom are subtracted. No reservation is
created, renewed or expanded by this implementation.

## Immutable accounting and Root closure

`DurableLedger` registers disjoint old/current training, partial/failed,
SDK/cache, external guard/Slurm logs, panel/H0, source snapshots and management
roots. External roots must be explicitly declared in Root's operational record.
Canonical SDK links use the existing verified census; arbitrary links, external
hardlinks, wrong owner, root overlap or disappearance reject. Persistent roots
remain charged across segments. Original node-local temporary lifecycle remains
the separate private-storage supervisor's responsibility; its persistent caches
and final records must be declared, and final quota planning must include any
shared-FS peak. Registering a scratch root as a historical persistent root and
then deleting it will intentionally fail accounting.

Counters have immutable chained intents written before record materialization.
A crash after intent still consumes its slot; missing materialization cannot
erase an attempt or free a hold. Exact replay can finish the same record; partial
or conflicting bytes reject and remain. Metadata bytes, total JSON files, roots
and inodes also have explicit finite caps. Historical counters are supplied in
Root's principal and never silently initialized to zero for an imported history.

Each launch transaction holds one whole segment allowance before model/SDK.
Concurrent clients cannot spend that same remainder. Current segment capacity
includes its job plus growth of canonical/control/WSD ledgers; historical sizes
are tested separately against durable quota. Checkpoint RLIMIT is the minimum
of original segment allowance, payload cap, durable remainder and quota remainder,
with original cleanup reserves. Every partial remains charged.

Child receipts only record computation and never release the hold or declare
actual Slurm success. `seal` requires Root's actual terminal/owned-process/private
cleanup closure; only then does it classify success/failure and release the
**unused** hold. Actual files and lifetime counters remain. Scientific panel ACK
still delegates to original18cell/1000bootstrap/matched source/random/readout and
independent SDK/Root evidence validation. Long-run ACK has its own finite counter
and consistent lock ordering with training. Parent ACKs are not copied/rolled back.

## CLI and prepared tests

Existing training entry points accept the optional admitted request; no training
is started by this document. Metadata entry point:

```bash
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
TOOL=/share/home/zixiao/descriptor_analysis/MFM_model_v3_long_run_storage/tools/model_v3/storage_control.py
$PY "$TOOL" validate --request ABS_REQUEST_JSON --request-sha256 ACTUAL_RAW_SHA
$PY "$TOOL" census --request ABS_REQUEST_JSON --request-sha256 ACTUAL_RAW_SHA
$PY "$TOOL" allocate --request ABS_REQUEST_JSON --request-sha256 ACTUAL_RAW_SHA \
  --segment-id EXACT_ADMITTED_ID --job-root ABS_JOB_ROOT --lineage-root ABS_CANONICAL_LEDGER
$PY "$TOOL" register-root --request ABS_REQUEST_JSON --request-sha256 ACTUAL_RAW_SHA \
  --root ABS_ADMITTED_EXTERNAL_ROOT --root-kind H0_panel --entry-type directory
$PY "$TOOL" seal --request ABS_REQUEST_JSON --request-sha256 ACTUAL_RAW_SHA \
  --job-root ABS_CLOSED_JOB_ROOT --Root-closure ABS_ACTUAL_ROOT_CLOSURE_JSON
# Long-run ACK uses this tool with --lineage-root/--event/--result/--evidence.
# Explicit engineering metadata additionally requires --input synthetic --engineering-only.
```

`inspect` reports owned roots, actual counts and quota without reading native
data/targets. Metadata allocation is an accounting record under Root's existing
reservation, not a real new quota reservation or Slurm submission. Panel jobs
use Root admission workload `panel` so successful/failed panels remain separate
from training counters. Job result closure and scientific acceptance remain
different. Root controls actual publisher/global slot updates and all job starts.

Prepared command: `python -m pytest -q -s
current/tests/test_model_v3_long_run_storage.py`, expected21cases. It includes a
clearly mocked3GiB/65segment/71CP accounting scenario (not physical>2GiB pytest
output), actual small files/SDK/guards/caches/H0 census, stale/zero/overcommitted
quota and final-D refusal, independent concurrent caps, interrupted counter
materialization, operational renewal, metadata CLI and actual native SDK proxy
fresh-request/resume plus actual model/Adam/provider/RNG resume equality. Quota/profile/Root closures are explicit engineering
fixtures and never scientific proof. Root must run in its actual>=16CPU Slurm
allocation with CUDA hidden, original output guards and before/after source pins.
No new packages. Default regression adds the original proxy20 and WSD18 tests;
Root chooses bounded shards and later full pre/postmerge verification.

At delivery all new tests are unrun. Actual Root quota reservation, final-D
capacity/timing, scientific calibration/architecture/recipe curves and seed SD
remain outstanding. A future cap amendment needs explicit new Root authority
and preserved old accounting; automatic cap growth or cleanup is not implemented.
