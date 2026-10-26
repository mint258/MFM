# S′ formal CPU v3: finite waves from censored pilot evidence

Source-only implementation of the Root-accepted planning proposal
`docs/data_v1/sprime_formal_cpu_auto_v3_proposal_20261026_v1.md`. No new data,
test, job, parent C0, Root approval or frozen population is claimed here.
Old formal_v1/v2, pilot/recovery results and N1 v4 are untouched.

Actual1321 closure means334 real original packages,102 scientific successes,
232 observed scientific failures,14 exact same-seed QA controls and2 consumed
execution-unknown tasks. Original4520364 and recovery4521110 remain TIMEOUT;
1321 is a separate actual closure C0. Whole336 task metadata are preserved.
Only318 deficit packages+2 unknown tasks enter the original canonical once
ledger;16 enough controls and14 reproduction controls add no attempt/population.

The CPU census must prove99351 deficits=9282 unsupported+320 consumed+89749
never dispatched, and90069 non-unsupported deficits=320+89749. It rehashes and
joins actual source/roles, without trimming or changing TRAIN/ROUTINE VAL/FULL.
The full runtime estimate is null, status RIGHT_CENSORED_NO_VALIDATED_FULL_FORECAST.
Finished-package elapsed values are descriptive. A finite sumCPU×requested wall
is a request ceiling, not a full-runtime forecast or actual-cost guarantee.
Every wave still needs an independent Root review, including the >500-core-hour
decision. No child code self-approves it. Cost1.5 is report-and-continue; actual
failed/TIMEOUT/startup/cleanup costs remain counted. Science thresholds stay.

## Files and unchanged science

`contract.py` handles identities/reviews/accounting. `runtime_io.py` supplies
central-v2 admission, resource-only provider reuse, reservations/durable IO.
`plan.py` supplies draft/freeze/continuation. `prepare_batch.py` materializes
original PM7 pointers and strict original S′ rows. `run_batch.py` executes the
unchanged pinned science.process_task with16 one-thread workers. `close_index.py`
classifies terminal batches and global union; `finalize.py` exposes close/index/
finalize and retains the old v2 physical-mapping body. `identity.py` copies the
original sparse int64/append/order algorithms. `test_contract.py` has8 synthetic
boundaries. `root_review_schemas.json` and the two config examples support Root
review; example status/null references are deliberately non-executable.

Science.py, selection.py, sprime_v6.py, legacy prepare.py and recipe are unchanged
and byte-pinned. seed_for/task_key retain original domains.10N/cap300, UFF,
ETKDGv3, retry1,0.5A, graph/stereo/atom order and optimizer2000/E1e-6/F1e-4 stay.
Old common.py is used only for frozen science/IO pure functions: no old64GiB,
85%, node20/14–19, full336-package or1.5-stop runtime guard is called. No module
globals are monkeypatched. No QM is called. Selected geometries, every failed
case and deterministic1% success candidate archive retain original policy.

Canonical ledger remains exactly
`RUN/artifacts/conformers/formal_v1/attempt_ledger`. All v3 outputs are new children
of `RUN/artifacts/conformers/formal_cpu_auto_v3`. A version/wave/continuation never
creates a new logical seed or clears/changes an existing claim. Import records
are O_EXCL+fsync and may only be reread field-for-field equal. Any old-schema or
different semantic record conflicts and requires Root review; no auto-upgrade.

## Startup and resources

Use frozen `execution/cpu_auto_memory_queue_v2`. Every producer calls its exact
actual-primary/full-argv/source/required-reference/fresh-proof API. All stages
use pilot=false; kind=conformer only for run, otherwise analysis. Initial source
is16CPU/MainUID1278/node13/cpu/no_mem/no exclusive/no GPU, because only node13 has
actual same-storage evidence. Central v2 fixes16CPU; multiple approved16CPU jobs
are bounded by wave maximum_concurrent_jobs. No implicit32CPU guard change.

The existing N1 v4 readonly quota client/publisher is reused with an independent
SPRIME_MAIN_ACCOUNT_QUOTA_REUSE_ROOT_REVIEW_V3. It pins actual provider source,
storage review and optional actual launch receipt, and explicitly says N1 count
authority is not S′ science authority. The separate S′ evidence/wave review grants
science scope. N1 sources/reviews/provider are not edited or restarted by v3.
Its actual node13 XFS/NFS/autofs/DNS/marker checks stay. No compute-local df/quota
fallback is introduced. Root must check the finite provider lease and supply a
new actual reviewed lease if needed; no producer auto-renews it or invents PID.

Parent resource observation checks actual own PID/start identity RSS/MemAvailable,
disk and fresh account quota; a metadata thread observes while CPU analysis is
busy. Provider reads poll60s, freshness<=120s; expiry checked between polls. Quota
reserves every approved wave job's whole8GiB cap, provider64MiB and admin64MiB,
leaving200000000000B. Reuse review reserve must cover the whole wave. Unavailable/
stale/error evidence stops new dispatch and naturally drains existing science.
No scientific signal is sent. Science dispatch cutoff uses explicit config wall
reserve; its requested wall must exceed that reserve. Analysis uses min(600s,
10% request wall) as finite cleanup reserve. Memory and disk limits are software
caps, never a claimed Slurm memory reservation. New ready/plan/frozen manifests
are refused after resource STOP; durable active packets/diagnostics can drain.

Each task reserves its full compressed failure/audit packet before submission.
Cross-process flock serializes reserve/write accounting, includes temp files and
all remaining reservations under8GiB+admin reserve. Parent writes an O_EXCL
canonical dispatch intent before pool.submit. The actual worker separately
fsyncs its true PID/start/boot/task SHA/seed record before calling process_task.
Worker writes+fsyncs a temporary gzip and atomically publishes the immutable
packet before returning its reference. Parent TIMEOUT cannot erase that packet.
Dispatch-only, initializer failure, missing/invalid packet or parent crash keeps
the key consumed and scientific_status=null; no empty synthetic package exists.
At most16 active futures exist, with no queue of unstarted science futures.

## Exact Root interfaces

`PY=/share/home/zixiao/.conda/envs/chemprop/bin/python`.
`REPO=RUN/repository`, `RUN=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025`.
All paths below become literal absolute paths. Options must retain this order.
Every stage also needs actual Root central scope review/registry; source/config
examples are not submission approval. Scope key is
`sprime_formal_cpu_auto_v3_STAGE`, parameters exactly contract.scope(STAGE,configRef).

Metadata-only input locator helper (no data body/hash/LMDB):

```
PY -B -m workflows.data_v1_final.conformers.formal_cpu_auto_v3.runtime_io
  --config CONFIG --quota-reuse-review ACTUAL_RESOURCE_REUSE_REVIEW
  --pilot-review ACTUAL_CENSORED_PILOT_REVIEW
```

This enumerates existing source refs, all16 role parts, original canonical index,
five S′ parts,334 existing package refs, original tasks and real metadata. Root
pins all new namespace files/config, existing frozen deps and transitive inputs.
Source/input lists are disjoint; scientific bodies are data_references. Later
stage actual plans/tasks/accounting refs are added after they actually exist.

```
PY -B REPO/workflows/data_v1_final/conformers/formal_cpu_auto_v3/plan.py draft
  --config CONFIG --root-preflight FRESH_PROOF --quota-reuse-review RESOURCE_REVIEW
  --pilot-review EVIDENCE_REVIEW --output NEW_DRAFT_DIR

PY -B REPO/workflows/data_v1_final/conformers/formal_cpu_auto_v3/plan.py freeze
  --config CONFIG --root-preflight FRESH_PROOF --quota-reuse-review RESOURCE_REVIEW
  --draft ACTUAL_DRAFT --wave-review ACTUAL_ROOT_WAVE_REVIEW --output NEW_PLAN_DIR

PY -B REPO/workflows/data_v1_final/conformers/formal_cpu_auto_v3/prepare_batch.py
  --config CONFIG --plan ACTUAL_FROZEN_PLAN --batch-id EXACT_BATCH_ID
  --root-preflight FRESH_PROOF --quota-reuse-review RESOURCE_REVIEW --output NEW_PREP_DIR

PY -B REPO/workflows/data_v1_final/conformers/formal_cpu_auto_v3/run_batch.py
  --config CONFIG --prepared ACTUAL_PREPARED --root-preflight FRESH_PROOF
  --quota-reuse-review RESOURCE_REVIEW --output EXACT_REVIEWED_RUN_DIR
```

Draft science calls0. Freeze emits a plan only after all320 imports reread equal.
Review lists concrete batch_id/job_name/node/cpus/wall/output/cap and maximum
concurrency. No future JobID, output SHA or completed result is minted. At run,
request/slot/source/full argv/output and fresh actual Slurm wave concurrency are
checked again. Wall is whole-minute<=48h; all original source/seed/once rules hold.

After a real parent terminal, Root creates a small descriptor with actual
plan/prepared/request/submission/accounting references. Source accepts C0,
TIMEOUT or other terminal independently from per-package validity. Raw sacct
must match the declared exact terminal parent set. Close reads only deterministic
packet/start/dispatch/error paths of that exact registered output and task roster.
This is explicit transitive registered-output authority, not guessed future SHAs
or arbitrary directory scanning. It computes actual refs on CPU. Invalid complete
packets are recorded consumed UNKNOWN. No ledger/no durable submission record
and no start/package/error is the only proven-unstarted continuation class.
Existing ledger owned elsewhere is not called unstarted and requires that owner.

```
PY -B REPO/workflows/data_v1_final/conformers/formal_cpu_auto_v3/finalize.py close
  --config CONFIG --root-preflight FRESH_PROOF --quota-reuse-review RESOURCE_REVIEW
  --descriptor ACTUAL_TERMINAL_BATCH_DESCRIPTOR --output NEW_CLOSE_DIR

PY -B REPO/workflows/data_v1_final/conformers/formal_cpu_auto_v3/plan.py continuation
  --config CONFIG --root-preflight FRESH_PROOF --quota-reuse-review RESOURCE_REVIEW
  --closed-batch ACTUAL_CLOSED_BATCH --output NEW_CONTINUATION_DRAFT_DIR
```

Continuation needs a fresh explicit Root wave review/freeze, then preparation.
It never resubmits consumed/uncertain work. Global index catalog fields are
root_draft, batch_closures[], additional_accounting[], related_parent_root_review.
The cost Root review includes actual complete-owned-master/raw evidence and an
explicit classification/reason for every master parent, including unknown-argv
parents. No name-based default-unrelated or same-parent deletion from two lists.
Related terminal set must exactly equal all actual accounting; all encountered
draft/freeze/prepare/science/pilot parents are mandatory. Self/later stage costs
remain explicitly append-pending, never asserted zero or a final pipeline total.

```
PY -B REPO/workflows/data_v1_final/conformers/formal_cpu_auto_v3/finalize.py index
  --config CONFIG --root-preflight FRESH_PROOF --quota-reuse-review RESOURCE_REVIEW
  --catalog ACTUAL_GLOBAL_CLOSE_CATALOG --output NEW_INDEX_DIR

PY -B REPO/workflows/data_v1_final/conformers/formal_cpu_auto_v3/finalize.py finalize
  --config CONFIG --root-preflight FRESH_PROOF --quota-reuse-review RESOURCE_REVIEW
  --completion-index ACTUAL_COMPLETE90069_INDEX --output NEW_FINAL_DIR
```

Index completion requires exact disjoint union packages|UNKNOWN=all90069 original
non-unsupported deficits, no extra/duplicate key, every actual ledger unchanged.
The finalizer rechecks source census/roles/strict old counts, all historical IDs
including failures, old coordinate/anchor/seed conservation and float64 new rows.
Old physical int64 IDs/gaps survive. New provenance identities append after
max(original N,all old attempted max+1), never over old failed ID space. Only the
order rank is dense. UNKNOWN adds0 geometry and stays explicit excluded while
insufficient. Old originals remain even where a new packet failed.

The denominator is unchanged TRAIN+ROUTINE VAL1214218, with FULL audited outside
it. Unsupported, chemical failure, execution UNKNOWN and incomplete PM7 remain
in denominator. Exclusion strictly>2% or non-Se element strictly>20% writes
evidence/distributions/HOLD and emits no frozen manifest. Se34 exception alone
does not remove unsupported. Element/size/scaffold/status changes remain visible.
Success manifests preserve downstream physical/order contracts; orders are not
declared frozen. P′15 covariance FAIL/2000/full HOLD is not released here.

## Verification still required

Eight pure fixtures cover legacy task/seed domain, honest unknown import,
task/seed/N/cohort drift, fake-package failure, sparse append/failed IDs,
duplicate/overflow/type identity boundaries, exact2%/20%/Se gates and UNKNOWN
membership. They do not claim actual CLI/large-data/Slurm/optimizer coverage.
Root runs them on actual authorized CPU before census/initial bounded wave:

```
PY -B -m unittest discover -s REPO/workflows/data_v1_final/conformers/formal_cpu_auto_v3
  -p test_contract.py -t REPO -v
```

This child performed only source/small-metadata reads/writes/hash/static text
comparison. No project Python/AST/tests, scientific body scan, SSH, Slurm, Git or
science execution/submission was performed.
