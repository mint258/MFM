# Independent full identity export after actual4521092: source draft

Status: SOURCE_PREPARATION_ONLY_NOT_EXECUTED_NOT_FROZEN. Old registered profile,
runtime, requests, receipts and input bodies are unchanged. This is a separate
full scientific scope, not a resource-only migration of the profile.

## Exact scope and acceptance

The proposed scope is sb5_identity_full_source_roles_after_profile_v1,
FULL_SOURCE_AFTER_PROFILE, pilot=false. It reuses the original export_v2 full
branch: all86 actual formal rowgroups /11231854 records, all4900 embargo rows,
and the same complete local cohorts. Expected total is11398552 original
records, unique on(dataset,source_id), including later common exclusions.
Chemical-key deduplication cannot replace physical-record coverage. Original
SOURCE_TRAIN/SOURCE_FULL/SOURCE_ROUTINE/SOURCE_EMBARGO roles and raw booleans
are preserved; effective training roles are not applied.

The existing full-scope source assertions are retained: v1 original record
unique count11236754; historical physical roles11104772/115760/11322/4900;
raw member_train/full/routine counts11104772/127082/11322; embargo4100 known
full-key plus800 unresolved-graph composition records; every local source
and fold retained. These are full-run checks, not claims that the profile
or pin547 measured all such counts. All18 profile rows lacking identity or
composition and all other unresolved variants remain in scope. This full
export does not accept global decontamination or release a pool, UFF/QM,
novelty order or training inputs. External TDC/MoleculeNet/MARCEL/COCONUT
coverage remains PENDING.

Only original identity columns are projected. The same76 input references
are bound:3 small metadata sources and73 data bodies, with complete current
SHA, portable/current fstat and source counts reverified in the allocation.
No target/feature materialization, common filtering or geometric graph
fabrication is introduced. Quantum source targets are not used for selection
or sorting. The raw PubChem inventory is independent of this local export.

## Source proof and resource authority

The new run.py is a copy of the frozen original identity_v3/export_v2.py.
Only declared execution/identity-library imports, its module docstring and
the SCOPES constant change. SCOPES now accepts full only under the new key.
provenance.py requires inverse complete bytes and identical ASTs for every
original function, and also compares the scientific functions of the actual
accepted profile producer. It explicitly records scope_expansion_from_profile
to_full=true and resource_only_change_claimed=false. An unchanged function
AST does not mean the profile's population automatically covered full mode.
The original profile-only adapter remains unchanged and still rejects full.

Startup uses the actual cpu_auto_memory_queue_v2 API, exact new full scope,
actual accepted profile, actual parent accounting and current source pins.
The central scope review must explicitly use FULL_SOURCE_AFTER_PROFILE and
bind parent_profile to the real4521092 receipt. No old request/proof or copied
UID/node observation may masquerade as a fresh full-job proof. These sources
use the main development-cluster authority; Alpha needs its own real context.

CPU16, no requested Slurm memory/exclusivity,4-hour wall ceiling and16GiB whole
output ceiling are retained. DuckDB's32GB working limit and the monitor's
48GiB RSS reference are algorithm settings, not granted memory. The accepted
current-RSS/MemAvailable monitor is reused without calling the profile scope
startup. It stops new work, preserves output/200GB quota checks and drains
naturally. No signal, process termination or SQL interrupt is sent.

## Estimate, soft deadline and actual costs

Actual4521092 has232234 source records, internal total138.507879seconds and
hash phase102.065922seconds. Its nonhash residual36.441957seconds includes
cohorts, worker/output, startup within the producer and global checks. It is
not an independently measured full aggregation phase. The full/profile row
ratio is approximately49.08. The coarse model is102.065922 +36.441957*49.08,
approximately31.5minutes. Twice this estimate is rounded up to64minutes as a
conservative planning allowance. This is an extrapolation from a structured
profile, not a confidence interval or measured full runtime. Global distinct/
grouped checks, spill, I/O and full RSS are still unmeasured.

The new budget adds a separate monotonic cost timer. At96minutes=1.5*64 it
sets STOP and writes a bounded cost_soft_deadline_notice.json once, blocking
new stage/task/record dispatch. Already running hashes, workers and SQL calls
drain naturally. A query may exceed the soft deadline before returning; no
absolute96-minute wall guarantee is claimed. The existing4-hour Slurm ceiling
remains. The timer starts after fresh startup at producer-budget construction,
matching the internal profile timing basis. Startup wait/validation and drain
are not omitted from actual parent allocation cost and are separately disclosed.
No timezone assumption reconstructs a false exact Slurm StartTime.

The source profile's real allocated cost comes from its bound sacct parent
ElapsedRaw*AllocCPUS. Worker-time sums, dispatch timings,64/96-minute planning
values and4-hour allocation ceiling are not actual cost. The full job's
allocated cost remains pending its own real terminal parent accounting.
Soft STOP or resource failure retains closed units/partials and does not
create an accepted full receipt. The new receipt inherits all original
scientific metrics plus the separate planning/soft-stop memory-budget evidence.

Storage planning uses twice formal-byte extrapolation plus twice profile
other snapshot/final-receipt bytes,6GiB bounded spill and256MiB reserve,
approximately6.60GiB. This allowance is not a mathematical compression bound;
the16GiB whole-output STOP stays active and no old file is overwritten/deleted.

## Root-only preparation and checks

After source review/integration, Root can run the small-metadata helper:

```bash
PY -B -m workflows.expansion.identity_full_after_profile_v1.materialize \
  --profile-receipt ABS_ACTUAL_4521092_RECEIPT \
  --accounting ABS_CURRENT_ACTUAL_ACCOUNTING --tag v1 --reviewer root
```

It refuses missing/changed profile/accounting/source authorities. It reads
no data body and creates a new source-bound READY plan, actual source proof
and NOT_REQUEST_READY base spec. It does not fabricate scope.review, future
job/request/parent references, script, quota or a submission. Root must review
the actual source/accounting/forecast, create its exact full scope review with
profile_reviewed and approved_profile_reference, then use the central builder
and observer. The old four science fixtures were already accepted in092 and
are not automatically rerun during full export. Three new incremental fixture
sources test planning definitions, no-signal96-minute STOP and rejection of
profile/common-filter/shortened-full population.

```bash
PY -B -m unittest workflows.expansion.identity_full_after_profile_v1.test_full_policy -v
PY -B -m workflows.expansion.identity_full_after_profile_v1.run \
  --plan ABS_NEW_FULL_PLAN --root-preflight ABS_ACTUAL_NEW_PROOF
```

This child has only prepared new source and small metadata. No Python, AST,
tests, data body, SSH, Git, Slurm or network execution was performed here.

Root review clarification: global_coverage is one in-flight aggregation stage. A soft STOP may be observed only after its sequence of SQL statements finishes; it is not a promise to interrupt or stop between individual SQL statements.
