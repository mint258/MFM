# v2 Parquet stored-schema compatibility

Only the expected schema is round-tripped through the original ParquetWriter
options before strict comparison. This accounts for compliant nested list
child names (item -> element); field names, types, nullability, metadata and
all original row/binary64 checks remain. No chemical function changes.

The original v1 Parent1885116 ended FAILED1:0/15s/64CPU before a tail intent
or new chemistry. Its code, outputs and cost remain. v2 uses the SAME fixed
v1 intent path, not a new once namespace:
AR/control/pubchem_consumed_partial_tail_alpha_v1/original363_412_unread_tail_intent.json.
Only this bounded format repair is attempted; another failed attempt stops
this issue under the user's two-failure/four-hour limit. No new QM or tests.
# Exact consumed PubChem363/412 tail continuation

SOURCE ONLY. The author has run no Python/import/AST/fixtures/scientific DATA,
data SHA, Slurm job, commit or submission for this package. Root performs actual
CPU checks and remains the only submitter. This is an isolated, fixed two-tail
I/O continuation of the original finite500, not a new screening epoch or retry
of processed molecules. Nothing releases the global pool, filtered/dedup1M,
novelty, UFF/QM or training.

## Existing facts and exact scope

| Original descriptor | Old failed Parent | Verified prefix ordinals | Exact unread suffix | Prefix/tail rows |
|---|---|---|---|---|
|363|1885075 / FAILED3:0 /32CPU compute-0-1|90750001..90866289|90866290..91000000|116289 /133711|
|412|1885076 / FAILED3:0 /32CPU compute-0-6|103000001..103233073|103233074..103250000|233073 /16927|

The exact existing checkpoint triples are fixed in contract.TAILS. Both say
completed=dispatched=actual_input_rows_dispatched, last_completed=last_dispatched,
expected250000, journal_precedes_parquet=true. Prefix category counts are
363:(103364 accepted,12912 chemReject,13 technicalUnresolved) and
412:(225838,7233,2). All349362 old rows, including15 UNKNOWN, remain read-only.
The old original claim references/plan references/full journal+Parquet locators
come from these checkpoint headers. Their old files and statuses never change.

Old account input:
AR/control/pubchem_packed_day32_alpha_v1/actual_day01_terminal_accounting_v1.json
(1168B, d067702af2fc9b37cd32576f048e656472b70ec0b949bb046c411a54824d1443).
It records old elapsed85513/85517 seconds at32CPU, failed3:0 and5472960coresec.
Root's own new Parent account is separate; no fake child C0 is created.

## Eight-file transfer and actual dependencies

Transfer these exact eight files from the new Git worktree directory to the
same new flat Alpha package AR/code/pubchem_consumed_partial_tail_alpha_v2/:

__init__.py, contract.py, metadata.py, resource.py, gate.py, runtime.py, run.py,
README.md.

AR=/gfshome/alpha/codex_data_v1_20261026, endpoint218.192.171.238:22 UID1264.
PY=AR/chemprop_compatible_v2/bin/python. PYTHONPATH=AR/code. The pre-existing
Alpha packages secondary_cpu_queue_v1 (common/probe), secondary_pubchem_screening_alpha_v1,
secondary_pubchem_packed_day_alpha_v1 and pubchem_science_frozen_v1 must retain
their accepted exact source pins. No shared file is patched or copied over.
Metadata drafts mechanically build the complete existing+new small source list
and validate old plans with the original DAY contract; Root should compare the
eight transferred source bytes to this worktree. No scientific DATA is transferred.

The Main checkout is only a Source authoring location. These modules intentionally
import Alpha's established top-level namespaces and hard-code the exact Alpha
root/UID. Do not run them using a local Windows interpreter or Main UID1278.

## Root metadata preparation and submit

The request is a small explicit Root JSON. Example fields (the storage reference
must be Root's actual new current all-future review and actual cost_gate.json, never an invented SHA):

{
  "schema": "ROOT_REQUESTED_PUBCHEM_CONSUMED_TAIL_V1",
  "requested_by": "root",
  "node": "compute-0-1",
  "cpus": 64,
  "wall_seconds": 86400,
  "output_cap_bytes": 8589934592,
  "output_directory": "AR/artifacts/pubchem_consumed_partial_tail_alpha_v2/ROOT_FRESH_TAG",
  "job_name": "dv1_pc_tail363412_v1",
  "old_accounting_reference": {"path": "ACTUAL_PATH", "bytes": 1168, "sha256": "ACTUAL_SHA"},
  "storage_scope_review_reference": {"path": "ACTUAL_CURRENT_SCOPE", "bytes": "ACTUAL_INTEGER", "sha256": "ACTUAL_SHA"},
  "cost_gate_reference": {"path": "ACTUAL_ROOT_COST_GATE", "bytes": "ACTUAL_INTEGER", "sha256": "ACTUAL_SHA"}
}

Replace AR in every JSON path with the absolute root. cpus is exactly16,32 or64;
wall is a whole minute1800..86400 seconds, output cap4..16GiB. Default Slurm memory
is unspecified; software budget64GiB, current tree RSS stop56GiB, actual node
MemAvailable15%, whole output+all other current/future caps+200GB remain.
No mem/exclusive/oversubscribe/GPU request or SBATCH_* memory environment exists.

On Alpha login, with the environment above:

PY -B -m pubchem_consumed_partial_tail_alpha_v2.metadata draft --request ACTUAL_ROOT_REQUEST --output AR/control/ROOT_FRESH_DIRECTORY

Root reviews candidate.json and copies review.template.json to a separate
root_review.json, changing only status to APPROVED and reviewer to root.

PY -B -m pubchem_consumed_partial_tail_alpha_v2.metadata finalize --candidate AR/control/ROOT_FRESH_DIRECTORY/candidate.json --root-review AR/control/ROOT_FRESH_DIRECTORY/root_review.json

PY -B -m pubchem_consumed_partial_tail_alpha_v2.resource submit --plan AR/control/ROOT_FRESH_DIRECTORY/plan.json
PY -B -m pubchem_consumed_partial_tail_alpha_v2.resource observe --submission AR/control/ROOT_FRESH_DIRECTORY/submission.json --max-seconds 90000

This is the existing Alpha held sbatch -> real node PID probe -> independent
fresh120s proof -> same PID exec sequence, narrowly parameterized16/32/64.
The gate waits180 seconds. One Parent only, no arrays, auto-submit, new epoch,
automatic retry, signals or alteration to other jobs. Root rechecks current CPU
and storage. If observe returns its finite timeout, observe the SAME submission;
never call submit again. It normally returns immediately once proof is published.
resource account is terminal-only and never resubmits.

## Actual CPU execution

1. Fresh target proof validates real endpoint/UID/node/job/PID/boot/start/cgroup/
   complete argv/source pins, CPU allocation, Python3.11.14, PyArrow17.0.0 and
   RDKit2025.09.5. Existing kernel.verify_source and direct object assertions are
   the necessary existing science/source checks. No new scientific test suite,
   chemistry profile, whole500 regression or QM is added.
2. Original source.load_inventory/iter_part load the accepted source-index and
   only two source parts. Their original complete SHA/frame/ordinal/byte checks
   execute on CPU. For both prefix journals and Parquets, full expected SHA and
   stable FD/frame are checked; all dispatch/result pairs are matched against
   exact original raw source records and every Parquet row is compared through
   original kernel.parquet_row and ORIGINAL.differences (typed binary64).
   Pending work must be empty at each exact prefix boundary. No prefix value is
   recomputed by chemical_task. A mismatch stops before any new intent/chemistry.
3. Only after both old prefixes close, exclusively create
   AR/control/pubchem_consumed_partial_tail_alpha_v1/original363_412_unread_tail_intent.json.
   Its path is fixed across new control/output tags. Existing/partial intent
   blocks re-entry. Original materialize_shards.claim is never invoked, released
   or modified. The old source iterators stay positioned after their verified
   prefixes, so only exact unread ordinals reach chemistry.
4. One persistent spawn pool uses the actual16/32/64 CPUs. Original kernel
   initialize/chemical_task, journal.Writer, output_schema/parquet_row and frozen
   filter/descriptor source objects are reused directly. Only pending width is
   resource-sized16/32/64 (each original bounded result remains<=32MiB, at most
   2GiB pending at64; runtime drain reserve scales from1GiB to2GiB plus128MiB), and resource STOP drains existing futures without setting
   the original kernel stop event. Both tails retain original sample_group
   full_shard in fresh separate fragment files.
5. Each new fragment is SHA-closed by the original Writer, then read back against
   the raw source and original typed serialization. Prefix file frames are
   checked unchanged. Two formal logical descriptor manifests reference old
   prefix + new tail without copying/mutating/concatenating old Parquet files.
   Each union has exactly250000 ordered rows, no holes/overlap, original three
   categories preserved and both old/new Parent provenance. New Parent C0 and
   actual allocation cost remain pending until actual terminal accounting.

An output/resource/worker/IO failure preserves old data, the new partial files,
the consumed intent and actual failure. No automatic second attempt occurs.
Root must inspect that retained state under the user's two-failure/four-hour
repair limit; changing output tag does not reopen these tails.

## Actual closure and costs

PY -B -m pubchem_consumed_partial_tail_alpha_v2.resource account --submission ACTUAL_SUBMISSION

After actual C0 only:

PY -B -m pubchem_consumed_partial_tail_alpha_v2.metadata close --receipt ACTUAL_NEW_CPU_RECEIPT --accounting ACTUAL_NEW_ACCOUNT_JSON --output ACTUAL_NEW_FORMAL_CLOSURE_JSON

Logical manifests and the CPU receipt retain old failed3 and new Parent account
as distinct facts. No old descriptor becomes an invented single-parent C0.
Physical-row completion is separate from whole-pool scientific acceptance.

The old uniform10000 profile is
AR/artifacts/pubchem_uniform10000_alpha_v1/v1/receipt.json, job1884795,
uniform phase87.86179045494646 seconds at16workers. Root's actual freeze approval
AR/control/secondary_cpu_queue/pubchem_C_metadata_freeze_root_approval_v1.json
uses UNIFORM_PHASE_WALL_ROW_SCALED_REFERENCE, factor4, IO900s and drain120s;
8GiB/28800s per descriptor were protective ceilings, not measured costs.
Comparable un-margined full500 reference is17552317coresec. The260 related
production/failed Parents observed by Root total15878560coresec; that subtotal
excludes some environment/fixture costs and is NOT a whole-line global ledger.
This new finite64CPU x86400 maximum adds5529600, giving21408160 below
2x17552317=35104634; actual expected duration is minutes/hours and it exits early.
Tail reference alone is about21177coresec before new prefix I/O/initialization.
No new molecules or repeated old chemistry are added to consume the day.

Only after actual new Parent C0 and this logical continuation closure can Root
reconcile the original finite500 physical coverage. Decontamination/unique
molecules/novelty/final candidate pool acceptance remain separate.
