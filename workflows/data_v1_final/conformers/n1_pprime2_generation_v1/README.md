# N1 Pprime second real UFF kernel (draft)

This is a new six-file source draft, not an executed/registered science stage.
It contains a real single-molecule ETKDG/UFF kernel, a pure contract/selection
boundary layer and ten synthetic test methods. It has no submitter, queue,
standalone generation CLI, actual32 pilot result, full-batch authority or cost
forecast. Original proposal, original UFF sources/configuration/data and existing
Sprime packages are unchanged. Root reviews and pins this draft before building
one central-v2 runner around its API. No Python, UFF, QM or source LMDB was run or
read to create this draft.

## Counts and physical identities

The PM7 N1 mother population is5040, to be reconciled against the actual pinned
per-molecule authority on a legal CPU allocation.5040 is not a common count.
Remaining FULL, unsupported, unusable baseline and non-common cases stay outside
the eligible roster, with their counts and reasons reported separately. Only a
frozen final common TRAIN/ROUTINE-VAL member with exactly one valid accepted UFF
baseline and one original PM7 pointer is eligible. A membership boolean alone
cannot establish that authority; Root's CPU preparation must prove the join.

`PM7_source_count=1`, `source_N=1`, `accepted_baseline_count=1` and
`UFF_desired_count=2` are separate required fields. The original PM7 record is
only the original graph/stereo/atom-order anchor and RMSD diagnostic reference.
It is never relabeled as UFF, copied to PM7 N2 or used to fabricate a second
parent row. The full original baseline row and coordinates are preserved with
their canonical full-row SHA; computed identity metadata is a sidecar. Legacy
accepted rows without a stored geometry SHA get a computed sidecar SHA without
altering the original row.

The selected supplement must be an actual independently embedded/optimized
candidate from this task's native optimizer events. It has native ID
`n1p2:<seed>:<candidate_id>` under its molecule, a new opaque geometry ID in
`uff_sprime_n1_pprime2:`, atom/source/stereo/SHA provenance, and the explicit
`pprime_n1_second` supplement role. Original Sprime N/count and common membership
do not change. An expanded Pprime view references the existing baseline and this
new supplement. Its orders use source `uff_sprime`, seed20261025, old ID0 and
the new stable string ID, following the original proposal.

Exact atomic-number plus float64 coordinate geometry SHA duplicates of the
baseline cannot add a second geometry row. Duplicate candidate geometry SHA
retains all real optimizer events but supplies one representative by frozen
energy/candidate-key ordering. This identity boundary is independently reviewed
by Root and does not introduce another RMSD tolerance. Different SHA candidates
use the exact original `select_fill(existing=[baseline],target=2,threshold=0.5)`:
lowest-energy sufficiently distant candidate first, otherwise real maxmin
fallback with `below_dedup_threshold=true`. No geometry or candidate row is
manufactured when selection cannot produce a second identity.

`Pprime_actual_records`, `selected_unique_at_0p5_A` and
`candidate_pool_unique_at_0p5_A` are reported separately. Two independently
optimized geometry identities below0.5 can produce two actual Pprime records
and only one0.5-unique selected geometry. Those counts must never be conflated.
Unique counts follow the frozen baseline-first greedy threshold admission; no
global cluster maximum is claimed.
A rigid molecule with no second eligible geometry stays
`PPRIME2_PENDING_NO_SECOND_REAL_GEOMETRY`; technical/input failure stays pending
with its actual event prefix. Pending does not silently become excluded from
common, an accepted one-parent Pprime case, a copied row, or an automatic retry.

## Exact reused science and candidate budget

`frozen_sources.json` pins the original fill common/selection/science reference,
the original `sprime_v6.py` and its `prepare.py` import, recipe and N1 proposal
source/config. The original fill's `process_task(target=2)` is never called: its
PM7 record-count invariant correctly requires original N1, so such a call would
be invalid. The new kernel directly reuses the frozen `read`, `plain`, `field`,
`graph`, `ordered_graph`, `fix_stereo`, `check_geometry_stereo` and `rmsd`
functions. Source payload SHA is verified by the original read-only LMDB reader.
The baseline is rechecked against actual source atom order, anchor, stereo,
geometry, finite UFF energy and successful/converged status before generation.
Every generated candidate rechecks ordered graph and atomic numbers. RMSD remains
fixed source heavy-atom indices plus proper-rotation Kabsch, no atom permutation.
Original `select_fill` and `conformer_orders` are imported unchanged and pinned.

The independent seed is exactly the original proposal's SHA256 first4-byte,
31-bit nonzero rule with domain `sprime-ETKDGv3-v1-n1-pprime2:`. A collision with
the old baseline seed safely rejects the task; it does not invent another seed.
Candidate budget is `min(10*original_source_N,300)=10`, never `10*UFF_target=20`.
ETKDGv3 uses this seed, one thread, chirality enforcement, prune=-1 and max200
embedding iterations. Only zero/failed ordinary embedding takes the original
same-seed random-coordinate fallback. Nonempty partial embedding gets no added
candidates. Both attempted calls, returned IDs/errors and elapsed times are
retained. Two calls of numConfs10 are not reported as20 optimization calls.

Each returned candidate invokes native `MinimizeTrajectory(snapshotFreq=1,
maxIts=2000,energyTol=1e-6,forceTol=1e-4)` and native `CalcEnergy`. The native
optimizer return code, actual trajectory snapshot count, coordinates/SHA,
finite/stereo outcomes, source/seed/candidate identity and actual elapsed time
are retained for every actual event, including successful molecules. Snapshot
count is native trajectory evidence; it is not a fabricated2000 iteration count.
Nonfinite, nonconverged or stereo-invalid candidates cannot supply the second
row. An exception retains its complete traceback and any completed event prefix;
missing geometry/SHA after a failed native call is explicitly null, never guessed.
There is no automatic retry, seed expansion, changed threshold or QM call.

## Minimal preparation and runner interface

Root's legal CPU preparation should perform the following once, writing new
exclusive-created outputs and retaining all source/authority pins:

1. Reconcile full PM7 `S_conformers=1` count with5040 before any role/common join.
   Report all mother/role/common/baseline/unsupported eligibility counts.
2. Intersect the frozen common table and frozen TRAIN/ROUTINE-VAL roles. Read the
   actual PM7 pointer and accepted baseline evidence on that allocation; verify
   exactly one each and freeze the unchanged full baseline row SHA/geometry ID.
   A prospective proposal roster alone is not a common or baseline authority.
3. Create `N1_PPRIME2_PREPARED_TASK_V1` envelopes with new generation `task_key`,
   required meta counts/role/common fields, one `records` pointer, one
   `existing_conformers` row, `baseline_row_sha256`, `baseline_geometry_id`, and
   exact authority triples: `frozen_common`, `source_pointer_manifest`,
   `accepted_baseline_evidence`, `roles_manifest`. `contract.validate_task` checks
   metadata bindings; scientific graph/stereo checks occur in the actual core.
4. Apply `contract.pilot32(eligible_tasks,frozen_selection)` after validation. It
   uses original proposal stable ordering `(stable_key(20261025,mid,
   'n1_pprime2_pilot',0),mid)`. Fewer than32 eligible unique molecules produces
   an explicit count report and no widened pilot. Freeze the32 task references
   in a manifest distinct from the task bodies, avoiding self-referential hashes.

No preparation/runner script is invented here. Root can add one small entry to
its existing central-v2 stage workflow using these concrete APIs:

```python
from workflows.data_v1_final.conformers.n1_pprime2_generation_v1 import contract, core

# Actual main-entry admission is validated by Root's runner before this pool.
# All values below come from actual pinned sources/preparation, not this draft.
initializer = core.worker_init
initargs = (catalog_reference, frozen_common_reference, prepared_manifest_reference,
            {"proof_path": actual_fresh_proof_path,
             "runner_source": actual_primary_runner_reference,
             "execution_argv": exact_primary_argv})
# ProcessPoolExecutor(max_workers=16, mp_context=spawn,
#                     initializer=initializer, initargs=initargs)
# Submit core.process_task(task) only after an exclusive Root once-ledger claim.
```

The initializer consumes existing `cpu_auto_memory_queue_v2.runtime.require_startup`
with exact primary source/full argv, `kind=conformer`, scope key
`n1_pprime2_generation32_v1` and exact `contract.SCOPE`. It requires `pilot=true`
and `BOUNDED_PERFORMANCE_BATCH`; it cannot start a fixture-only or formal run.
The actual worker checks its fresh admission before importing RDKit/science.
Its proof must still be within the central120-second startup window, so Root
should start the pool promptly after fresh admission and keep heavy preparation
in its separately admitted preparation stage. All six local sources, eight
frozen references, common and prepared manifest must be authorized explicitly.
The central layer binds main UID/job/boot/node, CPU16, nodes11–19, CPU-only,
quota200GB reserve and new unspecified-memory policy. Original historical
proposal64GiB/85%/14–19 fields remain provenance only and are never copied into
a new request. Torch is used for original tensor decoding/thread control, not
an alternative optimizer or RMSD numerical kernel.

Root's runner must enforce exactly32 unique manifest molecules and one attempt
per generation task key, bound active dispatch to16, monitor actual RSS/
MemAvailable, stop new dispatch and naturally drain on pressure/wall/storage
limits, precheck the complete packet/log/temp output budget, and durably write
then read back/verify each packet. The core returns Python data and never writes
files itself. No caller boolean or return dict substitutes for durable outputs,
actual C0, source/coordinate acceptance, source authority or accounting closure.
Keep all actual optimizer events, packet SHA and original baseline references.
An interrupted task is not automatically resubmitted; Root audits ownership and
once state. The dedicated pilot's successful packets may only be reused later
through Root acceptance, preventing a formal batch from recomputing its32 tasks.

Full generation remains a separate Root decision after actual32 distribution,
success/identity/RMSD fallback, RSS/storage and real allocated-cost evidence.
This initializer deliberately admits only the32 pilot scope. No formal-batch
mode, >500-molecule queue, new cost estimate or invented common release exists
in this draft. The latest user policy makes1.5 cost overruns report-and-continue;
this kernel has no1.5 stop gate. Actual parent costs, failed/timeout/cleanup jobs,
per-candidate times and pending reasons still must be reported. A request wall
or maximum candidate count is neither an actual cost nor a runtime forecast.

## Synthetic validation available for an admitted CPU test stage

From integrated Root repo, on an actual admitted16CPU allocation:

```text
PY -B -m unittest workflows.data_v1_final.conformers.n1_pprime2_generation_v1.test_core -v
```

The ten methods cover a separately calculated seed golden value; source N1 vs
UFF target2 and pointer/baseline counts; common/roles/full-row preservation;
0.5 boundary priority; real below-threshold fallback with separate counts;
baseline/candidate SHA identity duplicates and unresolved rigid boundary;
quality/actual-call/seed/ID/budget rejection; unchanged expanded ordering;
deterministic32 vs short roster; and bounded same-seed embedding fallback plus
missing-admission refusal. The embedding fixture uses an explicit fake API and
does not claim a scientific optimization. Tests import only standard library,
this draft and the frozen pure selection module. They have not been run here.
They do not replace actual RDKit2025.09.5, atom/stereo/RMSD, environment,
durable-output or central primary-chain validation in the real32 pilot.
