# Actual N1 source preparation and independent32 UFF pilot v2 (source draft)

This namespace has actual preparation and runner entries. No job or Python test
has been run to produce this source handoff. Root integrates/pins/reviews and
submits through its existing `cpu_auto_memory_queue_v2`; there is no submitter or
second queue here. The six files in `n1_pprime2_generation_v1` remain unchanged,
and their exact references are recorded in this namespace's source catalog.

## The metadata contract change

The original v1 draft required a final-common member. That final authority does
not yet exist, so v2 does not fabricate `final_common_member=true` and does not
patch a validator at runtime. It has its own explicit metadata contract:

- `source_population_authority` means the actual original PM7 N1 mother, frozen
  TRAIN/ROUTINE-VAL roles, verified original PM7 pointer and accepted Sprime
  baseline evidence. It is produced on an actual CPU allocation.
- All prepared tasks, source authority, checkpoints, generated packets and
  receipts have `common=false`, `pilot_membership=false`, production membership
  false and `final_common_reference=null`. Selection into the32 test roster is
  not membership in a released v1 population.
- The mother count5040 is reconciled before role/source-baseline filtering.
  All5040 entries and pending reasons are retained. Remaining FULL, unsupported,
  missing/invalid original baseline, graph/atom/stereo/source/seed problems stay
  explicitly pending/outside this pilot. They are not silently deleted from the
  original population. No new broad exclusion or rigid-molecule exclusion is made.

The numerical science is inherited unchanged: original source reader/graph/
ordered graph/stereo/fixed-index proper Kabsch, original proposal seed domain,
ETKDGv3 parameters, original MinimizeTrajectory2000/E1e-6/F1e-4 and frozen
select_fill/conformer_orders. An actual test-stage AST comparison checks the
unchanged pure functions, embedding helpers and native scientific call ASTs
against the pinned original v1 core. Extra worker admission, metadata, IO and
durability instrumentation are explicit v2 changes, not scientific substitutions.

## Actual inputs already identifiable through small metadata

`--formal-config` is the existing formal_v1.json, used as a read-only collection
of source references, never through its historical64GiB/85% runtime. It binds:

- per-molecule original S/Sprime audit:5650950 bytes, SHA9b53e4611c5a3f199f785c8c201aa56ce76f559e3c81ccf10d1819624e03e354;
- frozen roles authority1314 bytes/a6d47c06... -> actual ROUTINE role manifest
 22642 bytes/16619f25... and16 molecule-role parts;
- actual4520356 source-pin receipt3485 bytes/3b2a91fa... -> canonical original
  formal_record_index1242386629 bytes/ef2d99ae...;
- accepted original Sprime manifest11430 bytes/a67e36e4... -> five original
  conformer Parquet files and their full expected SHA values.

Preparation resolves these small metadata references after actual main startup
admission. The entire bound canonical index, role parts and all five baseline
Parquet files are freshly SHA-verified on that allocation, with stable file
identity before/after hashing. A closed manifest plus a size check is not called
a fresh whole-file SHA. These reads can be substantial; no duration prediction
is claimed. LMDB payloads are read only by legal CPU workers through the exact
frozen read-only reader and per-record payload SHA. No source LMDB is written.

Root's stage spec must explicitly authorize the formal-config reference, its
per_molecule/roles_authority/formal_source_receipt/sprime_manifest refs, the
roles authority's source_role_manifest and actual_closure refs, all16 role parts,
the canonical pointer-index ref and all five original baseline-file refs. These
locators/SHA can be obtained from small metadata without reading science on the
login node. Derived LMDB reads are limited to the pointers and payload SHA in
that bound canonical index. Do not substitute the old read-only proposal's
prospective common boolean for this actual source validation.

For Root's small metadata materialization, the existing JSON files can be
resolved to all exact input locators without opening any large dataset:

```text
PY -B -m workflows.data_v1_final.conformers.n1_pprime2_pilot_v2.io --formal-config ORIGINAL_FORMAL_CONFIG
```

This optional helper prints source/input references only and performs no source
data validation, graph work, LMDB read, generation or submission. Root assigns
the printed inputs to authorized request source/data refs and still performs
the actual large SHA/data work in the admitted preparation job.

## Preparation entry

Canonical argv, in this exact order; `PY` is the central contract interpreter:

```text
PY -B REPO/workflows/data_v1_final/conformers/n1_pprime2_pilot_v2/prepare_cpu.py
  --formal-config ORIGINAL_FORMAL_CONFIG_ABSOLUTE_PATH
  --root-preflight NEW_ACTUAL_STARTUP_PROOF
  --output NEW_ABSOLUTE_PREPARATION_DIRECTORY
```

Use `kind=analysis`, `pilot=false`, mode `BOUNDED_METADATA_PREPARATION`, scope key
`n1_pprime2_prepare32_v2`, and exact `contract.PREP_SCOPE`. All CLI paths must be
literal/absolute. The whole-output request must cover8GiB including temporary
spill and administrative/log reserve, with the normal200GB quota reserve. New
outputs must be a new child of
`runs/data_v1_20261025/artifacts/conformers/n1_pprime2_pilot_v2`.

The parent first consumes central fresh admission with its real `__main__`,
source pin and complete primary argv. It scans the original metadata with
DuckDB16 threads/6GB algorithm memory and bounded6GB node-local spill, preserving
the initial mother roster before baseline extraction. Sixteen spawn workers
validate each candidate source's single original PM7 payload, source graph,
atomic order, finite source energy, accepted original baseline row, baseline
stereo/finite geometry/energy, and the independent seed. No embedding,
forcefield construction, minimization or QM occurs in preparation.

`mother5040.jsonl` records every mother and its actual declared/physical counts,
roles, validation or pending reason. Validation of unknown facts never creates a
READY baseline. Deterministic selection uses unchanged
`stable_key(20261025,mid,'n1_pprime2_pilot',0)`, first32 from the actually validated
eligible roster. An insufficient roster, source-count mismatch or observed STOP
produces `PENDING_INPUT32_NOT_READY` and nonzero return; it does not widen criteria.

Successful preparation creates a source_population_authority.json, all5040
inventory, source-SHA receipt,32 original-baseline packets and32 actual tasks,
then prepared.json containing their real exact references. Original baseline
rows remain unmodified. A baseline geometry locator is explicitly a new opaque
reference to the verified original Parquet row, not a claim that an unknown
production geometry registry was already frozen. The source authority references
the mother/SHA evidence; tasks reference that authority and their baseline
packets. No self-referential or future hashes are manufactured.

The running preparation producer does not claim its own terminal C0. Root must
collect actual terminal sacct, retain failed/timeout attempts too, and form the
existing `DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1` standard accounting JSON. The
runner checks that raw sacct matches every declared parent and the preparation
job is actual COMPLETED0:0/16CPU. This is metadata work after actual termination,
not a second user approval or another science run.

## Generation entry

```text
PY -B REPO/workflows/data_v1_final/conformers/n1_pprime2_pilot_v2/run32.py
  --prepared ACTUAL_PREPARATION_PREPARED_JSON
  --prepare-accounting ACTUAL_STANDARD_PARENT_ACCOUNTING_CLOSURE_JSON
  --root-preflight NEW_ACTUAL_STARTUP_PROOF
  --ledger-root RUN/artifacts/conformers/n1_pprime2_pilot_v2/once_ledger
  --output NEW_ABSOLUTE_GENERATION_DIRECTORY
```

Use `kind=conformer`, `pilot=true`, mode `BOUNDED_PERFORMANCE_BATCH`, scope key
`n1_pprime2_pilot32_v2` and exact `contract.SCOPE`. Root reviews finite wall<=48h,
for example7200 seconds for this pilot, and whole8GiB output. Wall is a requested
limit, not a forecast. No sbatch memory/exclusive directive or historical64GiB/
85% condition is used. The main and worker must be the actual main cluster UID/
CPU allocation; conformer nodes11–19 come from central v2, analysis nodes from
its analysis policy. This is not an Alpha deployment or paid pretraining entry.

Root must authorize every local nine-file source, the catalog's eight original
references and six unchanged v1-source references. Input refs additionally
include the prepared manifest, its source population authority/inventory/SHA
receipt/formal config, all32 tasks and32 baseline packets, actual accounting JSON
and its raw sacct ref. The small prepared manifest provides those locators after
preparation, so none is guessed ahead of an output's existence.

The main consumes fresh central admission before reading task/coordinate bodies.
It then actually runs the ten original pure fixture methods adapted only for the
new false-common metadata contract, including the scientific AST check. The full
actual ten-test receipt is persisted; any failure/skip/unexpected outcome starts
no science. Tests do not use RDKit/torch/LMDB or optimize. The parent then checks
actual preparation C0, exact32 unique roster and baseline packet/full-row hashes.

Workers continue that exact admitted live parent: same PID/start_ticks, boot,
UID/job/node/CPU16 and actual main source/full argv, with the immutable original
startup proof. This is recorded as an active-allocation continuation, not a new
fresh-proof claim or an age waiver. In particular, preparation's full source
hashing may take longer than the120-second entry window. Reusing that old proof
as a supposedly fresh second admission would be wrong; each new main entry still
must pass the ordinary fresh central check before any science data read.

The shared fixed ledger uses the original Root pattern `O_EXCL|O_NOFOLLOW`, one
new generation-domain task key per molecule. Claim happens before dispatch.
Existing, unknown or submit-failed starts are never erased or retried. The same
generation-domain key must be retained for later full planning so accepted pilot
work is reused after review and never recomputed accidentally.

At most16 tasks are active. Each source N remains1 and target UFF records2;
only10 candidates are requested, with the original zero-embedding same-seed
random-coordinate fallback. Native calls are unchanged. Every candidate and
embedding attempt has immutable started/observed checkpoints. A native-call
intent is not a completed optimization claim. A hard timeout can leave an
unknown started call, but completed prior events/checkpoints remain durable;
normal exceptions preserve their complete actual event prefix. All ten actual
optimizer events are retained on success, including convergence/stereo/finite
outcomes, seed/ID, coordinates/SHA and native trajectory snapshot count. Native
snapshot count is not called a guaranteed number of optimizer iterations.

Geometry SHA identical to the baseline cannot create a second row. Repeated
candidate SHA supplies a lowest-energy/stable-ID representative while retaining
all actual events. Different SHA candidates use original0.5 select_fill/maxmin
fallback and original orders. Selected/pool0.5 greedy unique counts and actual
Pprime2 record counts are separate. No new RMSD threshold, seed extension,
candidate duplication or PM7 N2 pointer exists. Rigid/no-second identity stays
pending, not automatically excluded from any eventual population.

Packets are exclusive gzip JSON with exact byte readback and original float64
geometry SHA readback for baseline, finite candidates and supplement. Checkpoints
are retained separately. Actual RSS/MemAvailable, current quota and byte reserves
are observed; storage, pressure, unavailable observation or wall reserve stops
new dispatch and naturally drains active work. The producer sends no explicit
science signal; Slurm terminal cleanup is retained in actual accounting. New
task byte reservations cover their packet/checkpoints; JSON caps are hard IO
limits, not scientific quality exclusions. Parent Slurm/accounting captures
actual elapsed and all failed/cleanup costs. There is no1.5 cost stop; cost is
reported under the latest user's report-and-continue instruction. No calibrated
N1 runtime forecast is invented before this dedicated pilot.

Return0 means32 unique actual packets have durably closed, including pending/
scientific failure packets. It does not mean32 successful supplements, success
rate accepted, two unique geometries, graph/stereo independently accepted,
common released, actual full cost closed or5040 authorized. Receipt statistics
preserve those distinctions. Root must review original success/identity/0.5/
graph-stereo/readback gates and all related actual costs after terminal closure.
This entry has no full5040 mode or automatic release.

## Source handoff checks and limits

The actual CPU test command is:

```text
PY -B -m unittest workflows.data_v1_final.conformers.n1_pprime2_pilot_v2.test_core -v
```

It remains ten test methods, not a new broad repeated suite. Their original
selection/identity/budget/order/embedding logic is retained; only new metadata
boundary fixtures and AST evidence differ. This handoff has not executed them.
Actual environment, schema, large-source reads and whole CLI/once/checkpoint/
durable closure still require the Root-admitted real preparation and32 pilot.
If actual baseline facts are insufficient the prepare output remains pending;
this source does not claim any ready or completed real molecule.
