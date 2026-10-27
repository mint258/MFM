# Full physical native inventory from closed source context

This independent wrapper completes the original native-key attempt inventory,
without changing any old source, worker, parser kwargs, result, boundary flag,
scientific gate or composition policy. It is not graph/identity/decontamination
or pool acceptance. No source download, QM, UFF, graph repair, neutralization,
tautomer, isotope, charge or stereo edit is added.

The exact SDF population is39633 physical records: QM821786,core195,
general12800,refined4852. The earlier3195 profile results, including all
UNKNOWNs and technical fields, are reused unchanged, never recomputed.
At most36438 new original key_work tasks are claimed: QM820786,core0,
general11800,refined3852. Entity union counts must never substitute for these
physical counts; records sharing an ID or graph remain separate records.

Actual856 source metadata also records17847 MOL2 records and44510 index rows.
Core has195 native SDF/195 MOL2 but193 index rows, with2 native IDs outside
the component index. General has12800/12800 but17679 index rows, with4879
index IDs outside that component's native population. These are original
component-level gaps, not proved global-source gaps. Cross-component literal
ID relationships are observed by CPU, not guessed; all original index rows,
IDs, conformers, native variants and unresolved states remain represented.
MOL2 keeps the old original-atom-table composition and graph/charge/stereo
UNKNOWN, with no use of partial charges as formal charges or new MOL2 parser.

The protocol key is
`moleculenet_native4_closed_source_full_inventory_alpha_v1`; module
`secondary_moleculenet_native4_full_v1.run`; schemas
`SECONDARY_MOLECULENET_NATIVE4_CLOSED_SOURCE_FULL_{PLAN,STARTUP}_V1`.
It is analysis,mode full,pilot=false,performance_profile=false,16CPU,
SLURM_DEFAULT_UNSPECIFIED/no memory or exclusive request,14400s,4GiB whole
output,scope7. The original CSV6 Budget is used with a declared science
subcap whole4GiB minus8MiB, retaining its original1GiB+128MiB drain reserve;
at most8MiB is separately reserved inside that wholecap for the single control
once registration. The original Writer is used without source changes.
Actual RSS/MemAvailable/current free and all registered caps plus200GB are
observed, new work stops on pressure and pending work drains without explicit
signals. No default Slurm memory value is called a hard physical guarantee.

Only five scientific DATA inputs are used, all producer-pinned by856:

| Input | Bytes |
| --- | ---: |
| native_records.raw |229671020|
| source_rows.jsonl |119341284|
| native_relationships.sqlite |141537280|
| key_events.jsonl |13613492|
| actual_population_and_selected_ordinals.json |16331|

Total504179407B. Paths/bytes/SHA come directly from the accepted receipt;
the metadata helper never hashes or reads these bodies on login. In
particular the small selection file is still DATA. The full source blobs,
source logs and DB are reused in place, not copied into the4GiB output.
No TAR, gzip, original SDF/MOL2 file or active SQLite is reopened. The bound
closed source producer already checked all original TAR members, gzip EOF/CRC
and raw source hashes; the new task independently verifies the five current
closed output hashes and complete physical census before dispatch.

The three new pure methods run before DATA and before Budget construction.
They check full physical-vs-entity census/conformer conservation; success and
UNKNOWN reuse with claimed-record no-retry; and unresolved/native/source/MOL2
union boundaries. They use synthetic metadata/results only. Old B3, old
native3 and old audit3 tests are referenced by actual receipts, not rerun.

For every input, the process holds an owned UID1264 regular non-symlink FD
while verifying its whole SHA and dev/ino/size/mtime/ctime/UID frame. All five
must pass before body decoding. The closed index must have no WAL/SHM/journal;
SQLite integrity/schema is checked through a read-only immutable connection
to the held FD via/proc/self/fd. Immutable is not evidence of closure: manual
frame checks and the actual C0 producer/whole hashes are required because
[SQLite skips change detection for immutable files](https://sqlite.org/uri.html).
The input index is never written. All output SQLite work uses MEMORY journal
and memory temp state, avoiding transient output-journal deletion races in
the unchanged Budget's output-tree observer.

Every native source row is matched literally against records.body and its
blob offset/bytes/SHA; all segments are checked on the held blob FD and must
cover the whole blob contiguously, without overlap/gaps/unjournaled records.
Every original index event is matched with its exact ids.value/details.
All record/ID counts must equal the actual four-source closed census, and
every native physical record must have its original entity_members relation.
Neither ID-only rows nor native-only rows are dropped because mapping is
unresolved. The complete original relationship report is retained as context.

The original selection list is checked for the actual39633 population,
seed20261026,Python3.11.14 and3195 exact selected ordinals, without resampling.
The actual858 zero-parse reducer is reused to validate the entire old journal:
6390 events/3195 pairs/max32 pending/no duplicate, orphan or changed source.
Every old source/result must equal the closed record index, old results
unknown flag and old keys/WP5 index. The exact result object and its original
event offset/bytes/SHA are retained for PROFILE_REUSE, including old worker
PID/CPU/error fields. These old fields are never presented as new workers or
new scientific successes. Profile UNKNOWNs do not enter the new work pool.

Only after five-input readback, census and old-result binding does a global
population once registry get atomically created with O_EXCL. Its fingerprint
uses the five original input triples, physical census, original native worker
SHA and frozen identity sources, not the new wrapper SHA. Changing a wrapper
cannot reset a scientific attempt. Any prior registry yields HOLD; no automatic
resume, registry removal, claim reset or retry is implemented. The single
control registration is within the admin reserve. Per-record new claims are
durable under the new science output before pool submission. A claim without
a durable result remains unresolved/HOLD after failure or timeout.

Original initialize/load/key_work and frozen identity functions are imported
from their exact original source files. A thin worker I/O wrapper captures
stable per-worker stdout/stderr and fsyncs call-intent/return observations;
it directly calls the unchanged key_work object. Original worker results are
not altered. QM8 uses sanitize=True/removeHs=False/strictParsing=False; PDB
uses sanitize=True/removeHs=False/strictParsing=True. Present source variants
are the original projected allowlist and are processed by the old function;
other source properties are not newly inferred as SMILES. Full raw bytes and
original property-name/context evidence remain available through parent refs.
No special EOF seam or fallback sanitization is introduced.

The pool has at most16 processes/32 pending records. Results are fsynced before
any result/key index or union update. Future/initialization/return-validation
errors create explicit technical UNKNOWN results, never chemical rejections;
the actual native return axis stays UNKNOWN for those errors. Claimed tasks,
observed native returns and original worker results are counted separately;
dispatch is not claimed to prove a native invocation. Missing futures or
resource drain cannot claim full closure, reset once or fabricate successes.

The authoritative new outputs are native_key_results.jsonl, the new record
key/result index, full entity-key unions and all original index-ID relation
rows. Existing entity_members provides the original literal/ordinal grouping;
all native keys, source-variant keys and unresolved composition candidates
are unioned without selecting a representative or implying same graph from
same ID. Original metadata mapping gaps and cross-component membership stay
visible, while ID-only rows without any matched native context stay UNKNOWN.

The unchanged CSV6 Writer is also used as a compatibility view. Its Parquet
full_keys/WP5/missing_full_key fields retain source-SMILES-only semantics.
Native SDF keys are never renamed as SMILES-derived keys. Every view row
contains the exact native result and all-union in key_observation_json, plus
the authoritative native-result segment. Native union/missing state is
separate. Consumers needing native/full union must read the authoritative
native journal/index/entity unions, not reinterpret the compatibility columns.
This distinction is declared in the plan, result observations and receipt.

Full C0 means all39633 SDF physical records have original/reused or new attempt
results, all57480 native and44510 index contexts are retained, and declared
scope/cap/resource checks closed. It does not mean every native graph/key is
resolved, graph unavailable was established, all source IDs are accepted,
composition policy was accepted, or global decontamination/pool/training/QM
is released. Every old and new UNKNOWN remains available for later policy
review. No exclusion threshold, mask, tolerance, method, keyword, version,
source seed or whole-source population is changed.

Actual856 parent cost677s/10832coresec includes whole physical projection and
input hashing; it is not pure key timing. Its scale677×36438/3195≈7721s is
only a descriptive planning reference, not a worst-case bound or spent cost.
The profile's journal-size ratio is likewise descriptive, with new native
logs, compatibility output, indexes/unions and fixed I/O extra. The4h/4GiB
task may stop with a retained partial prefix if tails exceed those limits.
Original856 and858 costs and failures elsewhere remain in Root's ledger;
the new task's actual allocated cost is pending terminal accounting. Cost
overrun reports continue while all quality gates stay unchanged.

Root-only metadata flow uses thin package
`secondary_cpu_readonly_native4_full_v1`, whose controller is byte-identical
to v13 and whose adapter allows only this protocol. No queue algorithm or
arbitrary module runner is introduced.

```bash
python -B -m secondary_cpu_readonly_native4_full_v1.materialize source-template --source-manifest ACTUAL_INSTALLED_MANIFEST --output NEW_SOURCE_TEMPLATE
```

Root independently creates a distinct source approval by changing only
status to APPROVED_FOR_EXACT_METADATA_ADAPTER and reviewer to root.
The request schema ROOT_REQUESTED_ALPHA_NATIVE4_FULL_PHYSICAL_INVENTORY_V1
requires status REQUESTED_FOR_REVIEW/requested_by root, actual references
adapter_source_review_reference,base_controller_review_reference,
resource_authority_reference,cost_decision_reference,storage_review_reference,
native_profile_receipt_reference,native_profile_accounting_reference,
accepted_audit_receipt_reference,accepted_audit_accounting_reference, plus
actual Alpha python/node/new output_directory/startup_proof_path.

```bash
python -B -m secondary_cpu_readonly_native4_full_v1.materialize draft --request ACTUAL_ROOT_REQUEST --output NEW_SPEC_DIRECTORY
```

The helper derives the five DATA locators/census/old source pins from actual
small receipts, not from a new database/journal read. Root independently
reviews a separate scope-template copy, changing only status to
APPROVED_FOR_EXACT_STAGE and reviewer root. It explicitly acknowledges old
UNKNOWNs/ID gaps and the bounded physical inventory; scientific release stays
false. No child creates an approval or future job/result/body SHA.

```bash
python -B -m secondary_cpu_readonly_native4_full_v1.materialize finalize --draft ACTUAL_DRAFT_RECEIPT --root-review ROOT_SCOPE_APPROVAL
```

Then Root uses the inherited controller submit/observe/account with readonly
producer,no deployment,wall14400 and actual base review/resource/scope7. Source
development executed no Python, AST, tests, scientific body, SSH, Slurm or Git.
Root must run the new3 fixtures in the real CPU allocation before DATA.
