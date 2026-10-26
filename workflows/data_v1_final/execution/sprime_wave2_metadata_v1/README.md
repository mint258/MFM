# Root metadata generator for the remaining 179 Sprime initial batches

This is a source-only handoff. The author did not run Python, AST checks,
tests, scientific body reads, SSH, Slurm or Git. Root reviews/copies these
three sources and runs the generator on Main login as UID1278. This generator
only emits new small metadata. It never queries/submits Slurm, runs a project
scientific entry, starts a publisher, renews a lease, opens a packet or reads
a task/base/Parquet/LMDB body. Each invocation requires an explicit Root stage
decision and reason. Generated scope reviews/specs are concrete manual inputs
to Root's existing central-v2 submission workflow, not submitted jobs.

## Fixed scope and facts

The original actual draft4521457 contains180 initial batches for89749 never
consumed deficits. Batch00000's independent CPU closure4521477 bound the real
SCI4521475 and500valid packages, unknown0, errors0, unstarted0. The generator
requires that real closure, its actual close request/submission and real
terminal accounting for1457/1475/1477. Root separately supplies
`--root-observed-wave1-successes 500` after reviewing terminal outcome
metadata; valid packages and producer C0 are not silently interpreted as
scientific SUCCESS. The generator itself never opens that outcome body.

Wave2 selects exactly original `batch-00001` through `batch-00179`:178×500+
249=89249 molecules. Original task-shard SHA triples are copied from the
frozen draft, without local rehash/parse. Imported320 include the original
318 observed results plus2 consumed UNKNOWN; they remain on the original
once ledger and are not scheduled again. The unchanged kernel, recipe,
task/cohort/seed/graph/stereo/physical baseline rules and final exclusion
thresholds (overall2%, per-element20%, already approved Se exception) remain.
No final quality/common/population release is generated.

The179 science slots each request16CPU oncompute-0-13,8h wall,8GiB whole
output cap, no memory directive; maximum concurrent wave science parents=2.
The code computes179×16×28800=82483200 coreseconds=22912 corehours as the
sum of **requested ceilings**. It is not a runtime forecast, validated full
cost prediction or guarantee of actual billed cost. All actual terminal
costs, including failures, TIMEOUT/cleanup reflected in elapsed and these
auxiliary stages, remain append-required. The1.5 ratio is report-and-continue.

The frozen run guard requires quota reservation at least179×8GiB. The new
independent Root quota-reuse review reserves179 science caps+3 auxiliary
caps=182×8GiB. This is disk output reservation, not requested RAM. The code
computes both byte values rather than relying on prose constants. The old
same-storage node13 map, exact provider source, actual finite launch and
actual publisher identity stay unchanged. Its observed identity expiration
is bound; no lease is extended. The generator rejects an already expired
identity but does **not** claim a fresh current quota observation or that a
future job can finish before expiration. Every actual stage uses the frozen
CPU fresh provider guard, quota minus the entire wave/provider reservation
and200GB headroom,64GiB software RSS/4GiB MemAvailable checks, STOP new
dispatch on stale/expired observation, and natural drain. Root must coordinate
other owned output reservations/concurrency separately. This helper does not
alter them. A later publisher requires an independent Root resource decision
and actual launch/evidence; it is outside this generator.

## Inputs: small metadata versus scientific DATA

Only existing source/config/control files and small `draft.json`, `plan.json`,
`prepared.json` and `closed_batch.json` headers are opened/hashed. The inherited
source template is the actual mapped wave1 prepare stage. All original13
v3 source pins, mapped3 and independent close2 sources, mapping Root review,
4521417 actual CPU source-SHA/physical-stat evidence and node13 same-storage
provider refs are bound, plus the generator's own3 sources. Small source
references are verified exactly before a stage spec is emitted.

Scientific references remain DATA even when tiny: `.parquet`, `.jsonl`,
compressed packets, baseline/task-shard paths, pilot imported outcomes,
terminal outcome JSON and controls. The template's old
`terminal_outcomes336.json` source classification is corrected to DATA by
locator alone; its body is not touched. Original refs are never invented,
replaced with a login hash, or treated as a future produced file. Data/source
sets are disjoint and conflicting SHA triples reject. Main compute performs
the actual scientific body verification under its fresh proof.

All accounting passed to `--accounting` must already exist with schema
`DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1`, endpointMain/UID1278, status
`ACTUAL_PARENT_ACCOUNTING_CLOSED`, return0 and an exact raw sacct reference.
The frozen accounting validator checks all raw/declared parent sets, actual
state/exit/CPUs/elapsed, including terminal failures and cleanup elapsed. The
generator additionally rejects a present foreign raw UID. Root collects this
read-only accounting independently; no planned future parent ID is created.

## Manual sequence

Run `ROOTPY -B ROOTREPO/workflows/data_v1_final/execution/sprime_wave2_metadata_v1/generate.py`.
All paths below are absolute existing Main locators. `CONTROL_NEW` must be a
new descendant of `runs/data_v1_20261025/control`; existing files are never
overwritten. Each invocation writes `scope_review.json` and `stage_spec.json`.
The exact startup-proof placeholder matches the established Root helpers;
Root's normal central-v2 register/submit workflow resolves it and produces a
new real proof. No old proof is reused as current admission.

1. Generate the finite wave review and freeze specification:

   ```text
   generate.py freeze --output CONTROL_NEW --accounting ACTUAL_1457_1475_1477_ACCOUNTING --root-approve-exact-stage --root-approve-wave2 --root-observed-wave1-successes 500 --root-reason ROOT_ACTUAL_EVIDENCE_AND_FINITE_WAVE_DECISION
   ```

   This additionally emits `finite_wave_root_review.json`, independent
   `quota_reuse_review.json` and `wave2_manifest.json`. All179 slots have job
   names and output paths, no job IDs. The manifest holds only an expected
   plan path and `plan_reference:null`; no future plan hash is asserted.
   The compute argv is exactly frozen `plan.py freeze` with original OPTIONS
   order: config,root-preflight,quota-reuse-review,draft,wave-review,output.
   Wall3600s; Root manually reviews/registers/submits. Actual CPU must emit
   `artifacts/conformers/formal_cpu_auto_v3/wave2/frozen_v1/plan.json`.

2. After that actual freeze parent is terminal C0, for one selected batch:

   ```text
   generate.py prepare --output CONTROL_NEW --manifest ACTUAL_WAVE2_MANIFEST --plan ACTUAL_WAVE2_PLAN --batch-id batch-00001 --accounting ACTUAL_FREEZE_ACCOUNTING --root-approve-exact-stage --root-reason ROOT_EXACT_STAGE_DECISION
   ```

   Compute entry is the independent mapped `prepare_batch.py`, with exact
   OPTIONS config,plan,batch-id,root-preflight,quota-reuse-review,
   source-mapping-review,output. Wall14400s. The new Root mapping review and
   actual prior CPU validation/source pins are retained; no device-only
   exception for other fields is introduced. Root submits manually.

3. After the actual prepared header and terminal C0 exist:

   ```text
   generate.py run --output CONTROL_NEW --manifest ACTUAL_WAVE2_MANIFEST --plan ACTUAL_WAVE2_PLAN --batch-id batch-00001 --prepared ACTUAL_PREPARED_HEADER --accounting ACTUAL_PREPARE_ACCOUNTING --root-approve-exact-stage --root-reason ROOT_EXACT_STAGE_DECISION
   ```

   Compute entry is frozen v3 `run_batch.py`, exact OPTIONS config,prepared,
   root-preflight,quota-reuse-review,output, wall28800s. `prepared.tasks`
   JSONL is copied as DATA; the generator never pins/opens it. Exact frozen
   batch/plan/config/kernel/count headers are required. The registered
   central job name must match that batch's approved slot job_name. The
   generator leaves job names to the existing manual central submission
   command; it does not choose another slot or bypass maxconcurrent2.

4. After that actual science parent is terminal (C0, FAILED or TIMEOUT):

   ```text
   generate.py close --output CONTROL_NEW --manifest ACTUAL_WAVE2_MANIFEST --plan ACTUAL_WAVE2_PLAN --batch-id batch-00001 --prepared ACTUAL_PREPARED_HEADER --request ACTUAL_REGISTERED_RUN_REQUEST --submission ACTUAL_RUN_SUBMISSION --accounting ACTUAL_TERMINAL_RUN_ACCOUNTING --root-approve-exact-stage --root-reason ROOT_EXACT_STAGE_DECISION
   ```

   It writes an actual five-reference `descriptor.json` binding plan,
   prepared, request, submission and accounting. Original run job name,
   scope, resources, full primary/options/output chain are checked. C0 is
   deliberately not required for the science parent. Compute entry is the
   independent `formal_cpu_auto_close_index_v1/run.py close`, exact present
   OPTIONS config,root-preflight,quota-reuse-review,descriptor,output;
   absent catalog is omitted. Wall7200s. It preserves original frozen
   terminal classification without importing the unrelated finalizer.

Each batch's fixed compute output leaves are `prepared_mapping_v1`,
`generation_v1` and `closed_v1`. If a leaf already exists or an attempt was
consumed, this helper does not authorize deleting, replacing or retrying it.
A continuation of proven unstarted tasks needs independent Root review;
consumed UNKNOWN attempts never get another attempt here. Do not generate
run or close metadata before its actual prerequisite files/accounting exist.

This helper intentionally does not issue a global completion/finalization or
quality PASS. Root must independently close every parent, reconcile all
90069 original non-unsupported deficit outcomes, classify the complete owned
accounting ledger and retain original scientific failure/UNKNOWN thresholds.
