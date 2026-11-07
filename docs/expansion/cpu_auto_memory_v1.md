# SB5 default-memory CPU adapters: draft for Root review

Status: SOURCE_PREPARATION_ONLY_NOT_EXECUTED_NOT_FROZEN. The raw_uniform_cost_v1
draft is paused; its existing __init__/policy/source files are retained.

The new user decision removes requested Slurm memory, exclusivity and the
declared-memory85% admission rule. Analysis remains CPU16 on nodes2/8–19;
formal conformer/QM may use11–19 under the new central authority. This package
only adapts the three existing SB5 analysis stages. It adds no new scientific
scope, filtering, pool repair/release, decontamination, novelty, UFF/QM or
training authority. Old registered files, requests, proofs and results remain
immutable historical evidence.

## Guard and source boundaries

New producers use central cpu_auto_memory_queue_v2.runtime.require_startup,
the actual CPU_AUTO_MEMORY_QUEUED_REQUEST_V1 request and
FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1 proof. Both declare
SLURM_DEFAULT_UNSPECIFIED. The central API checks the actual primary module,
complete argv, node/job/UID/boot identity, CPU16, bound scientific scope and
fresh120-second startup proof, plus actual quota/output200GB reserve. No
missing/zero/default Slurm memory environment value is relabeled64GiB.
Neither old full_queue_v1.startup/RuntimeBudget nor old v1/v3 resource admission
is called by the new producer guard.

Only frozen metadata/file helpers are reused from full_queue_v1: frame,
portable, file_pin, verify_small, fresh_output, owned_bytes, memory_sample and
CooperativeStop. The new monitor samples current own process-tree RSS and
real node MemAvailable every second, stops new work and naturally drains
already running work. It sends no signal. The48GiB RSS softcap is explicitly
an algorithm reference, never scheduler allocation or a submission condition.
The15% node MemAvailable threshold is a runtime STOP, not declared-memory
admission. Current memory observations, missing/zero Slurm memory variables,
output peaks and actual elapsed time remain in the receipt. No memory
reservation or peak-RSS guarantee is claimed.

Identity-profile and inventory keep their original4-hour walls and original
output caps; HEAD keeps15minutes/64MiB. The central48-hour maximum does not
expand these stages. Identity's frozen DuckDB32GB working limit is unchanged
algorithm configuration and is not a claim of granted memory. Data hashes,
portable/current fstat, source counts, scientific authority and quota guards
remain required.

The new identity_profile.py copies frozen identity_v3/export_v2.py and only
changes execution/relative imports and its resource docstring. All original
role, coverage, worker, Parquet and source functions remain AST-identical.
SOURCE_* physical roles remain distinct from effective training roles.
Only the existing profile scope is accepted by the new runtime; the full
identity scope cannot use this adapter without a separate future review.

The new inventory.py copies frozen pubchem_full_v1/inventory_v2.py with only
the execution import changed. The original stream/4KiB index/byte-bound/CRC/
part-SHA algorithms and source parameters remain unchanged. The new
official_head.py changes its resource startup guard/imports and reuses the
frozen catalog/transport and five fixture sources. Normal proxy inheritance,
query redaction, no-signal overrun drain and immediate per-URL persistence
remain unchanged. Original4/5 science fixtures still run inside the new
entries. Central resource tests are separate evidence.

## Actual metadata proof and Root-only CLI

source_equivalence.py reads only small source files. It requires that each
variant equals the original after the enumerated resource-only edits and
that inverse edits recover the complete original bytes. It also compares
each scientific function's normalized AST. HEAD's startup resource guard is
explicitly excluded from that identity claim; its main's sole fixture-import
path is normalized. No wrapper AST is falsely described as the old guard.
The actual proof records original and new file pins and is checked again at
producer startup. The frozen baseline plan remains a separately pinned
historical input, with the new resource authority explicitly superseding its
resource interpretation.

After integration/static review Root may run metadata preparation only:

```bash
PY -B -m workflows.expansion.cpu_auto_memory_v1.materialize \
  --stage identity-profile --baseline-plan ABS_ACTUAL_OLD_READY_PLAN \
  --tag v1 --reviewer root
```

The other exact choices are raw-inventory and official-head. The helper reads
only existing small plan/code/authority files; identity's73 body references
are copied from actual547 metadata, raw's reference from the actual old plan,
and HEAD has no data references. It does not read/hash/stat those data bodies,
read future files, submit jobs or change old plans. The new user authority at
configs/data_v1/user_cpu_auto_memory_20261026_v1.json must physically exist and
be pinned, along with all actual new central sources.

It writes a new plan, actual source-equivalence proof and NOT_REQUEST_READY
base spec under control/cpu_default_memory_specs. The base spec contains no
memory_gib, exclusive_user or memory-fraction admission fields and has no
fabricated future scope-review pin. Root alone creates the new exact scope
review/request with the central materializer and submits/observes it. The
script must omit memory/exclusive directives and the submitter must remove
inherited SBATCH_* overrides as required by the new central contract.

Execution modules are workflows.expansion.cpu_auto_memory_v1.identity_profile,
inventory and official_head, each with --plan ABS_NEW_PLAN --root-preflight
ABS_ACTUAL_NEW_PROOF. All entries, metadata proof/helper and monitor remain
drafts until Root review. This child has not run AST, fixtures, science,
network, SSH, Git or Slurm for this adapter preparation.
