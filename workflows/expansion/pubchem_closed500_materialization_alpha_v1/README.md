# Closed500 -> unfiltered candidates/aliases materialization (Alpha only)

SOURCE ONLY. The author ran no Python, AST/import, test, Slurm, scientific
payload read or data SHA. Root installs/reviews this Source, obtains actual
cost/all-future storage admission and submits one CPU Parent. This package
does not call screen.screen, chemical_task, RDKit, decontamination, ranking
or training. It creates only a fresh SQLite DB and bounded metadata.

## Fixed accepted input

The only accepted input coverage is
AR/control/pubchem_tail_363412_root_20261030_v2/original_finite500_all_source_rows_accounted_v1.json
554554B / SHA40fc128704a7a77a4322c5514f8c1afad78ccef19dcb74474d5cacb83ebfc1b5.

It accounts for500 original descriptors and124857440 physical rows:
110046364 accepted,14764875 chemReject,46201 technicalUnresolved.
It retains two historical FAILED3 Parents and actual1885119 C0 continuation.
It is NOT an all-source exclusion, filtered pool or training release.

Normal498 descriptors supply one features/journal locator pair each. Logical
363/412 supply two pairs each. contract.inputs reads only small metadata and
lifts the two logical manifests' exact fragment ranges/counts. The resulting
502 distinct physical fragments are strictly contiguous, contain no repeated
prefix and preserve the exact original descriptor ranges. The original frozen
manifest/new-tail actual C0/old accepted scientific Source remain bound.

## Existing functions and output SQL

Actual CPU consumption reuses original source.load_inventory/source.record,
kernel.parquet_row, and the already actual-C0 tail-v2 parquet_rows/equal helpers.
The latter retain the legitimate Arrow stored-schema Writer roundtrip and
strict typed binary64 comparison; no new test suite or scientific profile is
introduced. There is no chemical worker initializer or RDKit invocation,
including in the new resource startup check.

Each IO worker pairs every original DISPATCH/COMPLETE journal event with every
original typed Parquet row, checks its category/ordinal/source reference, and
reconstructs the original raw source-row bytes from the durable input fields.
Original source.record checks those bytes' framing/UTF8/rowSHA/SMILES SHA. It
does not reopen or rehash the raw source TSV bodies. Complete source-part
byte-offset/range conservation is checked after both pieces of363/412 join.

Each journal gets one forward SHA while consumed. A private same-FD Parquet
reader maintains one monotone whole-file SHA frontier during Arrow seek reads.
Arrow requires footer/column seeks: gaps advance the digest in bounded chunks,
and already hashed bytes are not hashed again. Decoder seek reads may revisit
those bytes on the same immutable FD. No separate full-body verification pass,
temporary body copy, extra job or trial is created. Both complete SHAs must
match the original locators and both FD frames must remain unchanged before
a fragment is accepted. A malformed/missing/type/field/SHA mismatch stops with
partial new output retained, without inventing values.

A bounded multiprocessing queue sends only accepted original payloads to one
SQLite writer.16 or32 real worker processes perform these IO/F64/source checks;
no new feature values are computed. The parent uses exactly the original
screen.py SQL/selection semantics:

CREATE TABLE candidates(full_key TEXT PRIMARY KEY,cid INTEGER UNIQUE,wp5_key TEXT,features TEXT NOT NULL)
CREATE TABLE aliases(cid INTEGER PRIMARY KEY,full_key TEXT NOT NULL,source_ordinal INTEGER NOT NULL)

For every accepted source row, INSERT aliases(cid,key,ordinal); SELECT current
candidate CID by full_key; INSERT OR REPLACE candidate only if absent or the
new CID is smaller. All accepted aliases remain. Duplicate-CID integrity
errors retain the original refusal behavior; no invented ID or silent drop
is introduced. The exact original full_dispatcher_result_json text is stored
as features, so no float payload rewrite occurs. SQL literals are checked
against the existing accepted frozen screen.py Source; screen.screen itself
is never called.

All124857440 input rows and all three state counts must conserve. Rejects and
UNKNOWN are retained by immutable full input locators/counts; UNKNOWN is never
called a chemical exclusion or placed into the accepted candidate table.
The aliases count must equal110046364, and aliases minus unique candidates
must equal the original full-key duplicate counter. Source membership/counts
and input fragment provenance remain available through input_fragments.json
and the fixed original full coverage reference.

## New package and exact dependencies

Install these eight files into fresh AR/code/pubchem_closed500_materialization_alpha_v1/:
__init__.py, contract.py, metadata.py, resource.py, gate.py, runtime.py, run.py,
README.md. Do not edit an old Alpha package or old input.

AR=/gfshome/alpha/codex_data_v1_20261026, endpoint218.192.171.238:22, UID1264.
PY=AR/chemprop_compatible_v2/bin/python; PYTHONPATH=AR/code.
Dependencies are the already installed secondary_cpu_queue_v1 common/probe,
secondary_pubchem_screening_alpha_v1 source/kernel, pubchem_science_frozen_v1
accepted screen.py, and pubchem_consumed_partial_tail_alpha_v2.run's existing
pure IO/schema/equality helpers plus their existing imports. metadata.draft
inherits the actual accepted tail plan's complete source refs and adds all
eight new files/request/coverage/storage/cost references mechanically.
Python3.11.14/PyArrow17.0.0 are checked; no RDKit API/version call is required.

resource.py/gate.py use the successful tail-v2 narrow Alpha held sbatch -> exact
node waiting PID -> independent fresh proof -> same PID exec chain. Their only
scope change is this fixed read-only502 IO materialization contract; there is
no generic new scheduler. Original Parent C0/FAILED facts are not altered.

## Root request and commands

Root supplies a small JSON with:
schema=ROOT_REQUESTED_CLOSED500_MATERIALIZATION_V1, requested_by=root,
node=actual authorized free CPU node, cpus=16 or32, wall_seconds<=86400
(whole minute, at least3600), output_cap_bytes<=384GiB (at least8GiB),
fresh output_directory under AR/artifacts/pubchem_closed500_materialization_alpha_v1/,
safe job_name, storage_scope_review_reference and cost_gate_reference.
Use a Root-reviewed whole-output allowance that covers the new DB, all indexes,
its DELETE-journal and metadata. Existing inputs do not count as new output.

With the Alpha environment above, Root invokes:

PY -B -m pubchem_closed500_materialization_alpha_v1.metadata draft --request ACTUAL_ROOT_REQUEST --output FRESH_CONTROL_DIRECTORY

Review candidate.json and separately copy review.template.json to root_review.json,
changing only status=APPROVED and reviewer=root.

PY -B -m pubchem_closed500_materialization_alpha_v1.metadata finalize --candidate FRESH_CONTROL_DIRECTORY/candidate.json --root-review FRESH_CONTROL_DIRECTORY/root_review.json
PY -B -m pubchem_closed500_materialization_alpha_v1.resource submit --plan FRESH_CONTROL_DIRECTORY/plan.json
PY -B -m pubchem_closed500_materialization_alpha_v1.resource observe --submission FRESH_CONTROL_DIRECTORY/submission.json --max-seconds 90000

Root alone submits. One real Parent,16/32 CPUs, at most24h, CPU-only. There is
no Slurm mem/exclusive/oversubscribe request; inherited SBATCH_* is removed.
Default memory is not a physical guarantee. Software budget64GiB/current tree
RSS stop56GiB and actual MemAvailable15% remain; effective quota/statvfs minus
all registered current/future outputs plus own remaining cap must retain200GB.
Root must generate a CURRENT materialization cost gate and future-storage
scope, including the whole up-to384GiB output, before this new Parent.

A fixed new O_EXCL IO intent is
AR/control/pubchem_closed500_materialization_alpha_v1/original_closed500_materialization_intent.json.
It does not touch the original500 claim namespace or the successful tail intent.
Existing intent/output/unknown submission blocks automatic re-entry. Resource
STOP closes committed new SQLite prefixes and naturally drains own workers,
with no signals or deletion; it cannot create a successful full receipt.
There is no per-fragment Slurm job or extra preflight/test/pilot.

After actual terminal state:

PY -B -m pubchem_closed500_materialization_alpha_v1.resource account --submission ACTUAL_SUBMISSION
PY -B -m pubchem_closed500_materialization_alpha_v1.metadata close --receipt ACTUAL_CPU_RECEIPT --accounting ACTUAL_C0_ACCOUNT --output FRESH_CLOSURE_JSON

The final CPU job closes SQLite, requires absent-wal/shm/journal, checks the
original alias/candidate counts, and hashes its complete new DB once on CPU.
The formal closure requires actual C0/accounting. Partial new files/failed
Parent costs remain visible; no automatic retry occurs.

## Compatibility and remaining gates

The DB's candidates/aliases tables are directly compatible with the original
screen database contract. The receipt deliberately uses the NEW schema
ALPHA_CLOSED500_UNFILTERED_MATERIALIZATION_RECEIPT_V1 and status
MATERIALIZED_UNFILTERED_NO_RELEASE. It is not spoofed into pubchem_screen_v1
COMPLETE or expansion_filtered_pool_v1. Full raw physical coverage is distinct
from effective unique candidates or final scientific release.

The9/11 decontamination state is unchanged. Later exclusion/filter/nearest-v1/
R-N sorting still require their actual all11/all-split/full-regression/common
population/novelty receipts and separate resource admission. They are not
invoked or bypassed here. Main's old expansion.common has Main UID/quota/output
paths; this Alpha package reuses the accepted Alpha resource helpers instead
of weakening those old guards or monkeypatching shared science.
