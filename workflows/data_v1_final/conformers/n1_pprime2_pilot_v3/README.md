# N1 prepare32 v3: exact reviewed count correction, unchanged science

Main job 4521326 actually read the SHA-bound 1,220,466-row per-molecule table and
observed 5,105 rows satisfying `S_conformers=1`, with no role filter. It failed
3:0 after 123 seconds on16 CPUs (1,968 allocated core-seconds): the unproven5040
constant short-circuited every row before physical PM7/baseline validation.
Its eligible0 is not evidence that these molecules lack real usable baselines.
Keep that failed run, artifacts, and cost unchanged.

Root independently approved only this metadata correction in
`configs/data_v1/conformers/n1_pprime2_source_count_correction_v1.json`, 2,857 B,
SHA256 `df97851fdb4a03bcdc11d43b2e27abfc54dca964ceb326e15c1a34e598f70dbc`.
The new catalog pins that actual file, its failed-prepare/source-SHA/population
evidence, and the exact same per-molecule reference. The old proposal, config,
v1/v2 source and results are not edited. Old5040 text remains historical
reference-only provenance, never relabeled an independent source measurement.

## Boundaries and source inheritance

`contract.load_count_correction` verifies the exact Root review, prior actual
parent identity/cost/failure, prepared/SHA/population references and per-molecule
pin. The v3 scopes are fixed to reviewed5105, while preparation gets its expected
value from that actual review. It freshly rehashes the same inputs and recounts
count and distinct molecule_id. A mismatch stays pending; the code cannot adopt
an arbitrary observed count, filter out65, widen a role, or trim rows.

`core.py` and `test_core.py` are complete byte copies of registered v2 files.
Original task/baseline/event/checkpoint/packet scientific payload schemas stay
V2 so their identities and validators do not change. Outer catalog, prepared,
population authority, aggregate and final pilot receipt schemas become V3.
Seed domain, task_key, original PM7 pointer1, retained real baseline1, UFF desired2,
candidate10/cap300, ETKDGv3, graph/atom/stereo checks, fixed-index Kabsch,
0.5A selection/fallback, optimizer2000/E1e-6/F1e-4, and actual candidate-event/
geometry-SHA/readback retention remain unchanged. No PM7 pointer or geometry
is cloned into a second row. No new seed extension or retry is added.

The unmodified test source has absolute **v2** imports. Its ten fixtures run
honestly as inherited scientific/ID boundary tests. Before those tests, v3 checks
complete core/test bytes equal v2 and original pure scientific function/call ASTs
are unchanged. The receipt says these ten tests do not claim coverage of new
count-authority or aggregation metadata. No old module is monkeypatched. Actual
source/SHA/count/conservation checks cover that new path.

New outputs use `artifacts/conformers/n1_pprime2_pilot_v3`. The logical once
ledger remains exactly `artifacts/conformers/n1_pprime2_pilot_v2/once_ledger`.
A metadata version change cannot mint a second attempt. Existing/unknown keys
stop dispatch and are never cleared or automatically retried. Original seed and
task keys remain. All mothers/tasks stay common=false, pilot_membership=false,
production_membership=false, final_common_reference=null.5105 is the observed
source mother, not a final common population or full-generation authorization.
The count record grants no UFF/QM calls; execution still needs its separate exact
Root-reviewed request and fresh proof. Pprime15FAIL/2000/full HOLD is unchanged.

## Actual CPU preparation and small aggregate receipts

The same23 full body inputs are required: per-molecule table,16 role parts,
canonical PM7 pointer index and five complete Sprime baseline parts. Actual CPU
hashes/reads them. Real PM7 LMDB payload validation still occurs across all
metadata-eligible mothers before fixed-hash32 selection; original per-record
payload SHA stays mandatory. Original TRAIN/VAL, FULL/missing, PM7-usable,
unsupported, baseline count/anchor/seed/graph/atom/stereo conditions remain.
Every pending/excluded row remains in the complete mother inventory.

New actual-allocation artifacts:

- `mother_role_status_usable_before_validation.json`, <=1MiB, all observed
  mothers after actual pointer/baseline join and before PM7 payload validation.
- `mother_role_status_usable_audit.json`, <=1MiB, same mothers after physical
  validation and before32 selection, including final status/pending reasons.
- `mother_inventory.jsonl`, neutral name for the full observed mother inventory.

Both aggregates expose the four-way joint
`source_role x effective_role x Sprime_status x Sprime_usable_equals_source_N`.
Here `original_Sprime_usable_count` is original metadata `Sprime_conformers`, and
`Sprime_usable_equals_source_N` compares it with source `S_conformers=1`.
The detailed eleven-way joint also retains `original_Sprime_usable_count`,
`pm7_S_usable_equals1`, `pm7_S_usable_count`, physical original Sprime usable
baseline count, metadata eligibility reason and final status/reason.
`pm7_S_usable_count` is metadata `S_usable_conformers`; it is a separate PM7 S
condition and is never described as Sprime usability. Physical original Sprime
usable count comes from fresh baseline rows with status SUCCESS and converged
is True. None of these counts claims full payload/graph/stereo acceptance.

These definitions are pinned to actual original producer
`s_population_alignment_v4.py` (17,889 B, SHA256
`6d835e763411aca8fa127d45d4ceca0365c8f08cfa3aba0fd885df8cba9e6ae3`):
SM_SQL lines27-32 counts original PM7 geometry with nonempty atomic_numbers;
SPC_SQL lines33-37 counts Sprime SUCCESS and converged IS TRUE. Line184 writes
the bound per-molecule table. Its closed `s_sprime_alignment_v4.json` report
(3,804 B, SHA256
`764b4ccde3e51ed99990084bb4d26fd2972b27d4fb7b0f22ac6ef84e595286fa`)
also states both definitions. The catalog, fresh admission, worker continuation
and both aggregate receipts bind these two actual small references. This adds
provenance only; original eligibility predicates remain unchanged.

Every joint and marginal must sum to all observed mothers. Both receipts retain
the same mother-ID SHA and metadata strata, with fresh source-SHA receipt/current
job/per-molecule/Root-correction references.
No65 membership is invented. A later subset counting5040 alone cannot prove
the old hardcode's historical definition.

`prepared.json` is N1_PPRIME2_PILOT_PREPARED32_V3 and becomes
ACTUAL_INPUT32_READY_NOT_GENERATED only with reviewed distinct mother count,
32 actually validated tasks and no STOP. It binds population authority and both
aggregate references. No future ready output is precreated.

## Exact request-stage interfaces

Root integrates/freezes these nine files and uses existing cpu_auto_memory_queue_v2.
No second queue or submitter is provided. All placeholders below resolve to
literal absolute Main Linux paths.

Preparation argv:

```
PY -B REPO/workflows/data_v1_final/conformers/n1_pprime2_pilot_v3/prepare_cpu.py
  --formal-config REPO/configs/data_v1/conformers/formal_v1.json
  --root-preflight ACTUAL_NEW_FRESH_PROOF
  --output RUN/artifacts/conformers/n1_pprime2_pilot_v3/prepared_v1
```

analysis / pilot=false / key n1_pprime2_prepare32_v3 / exact contract.PREP_SCOPE /
mode BOUNDED_METADATA_PREPARATION /16CPU / no explicit memory / whole cap8GiB.
Wall is finite <=48h; the prior7200s may remain a wall limit, never a forecast.
References: unchanged23 bodies and original small metadata; new nine source
pins; eight original dependencies; six inherited v1 and nine inherited v2 source
pins; Root correction plus its three historical small evidence pins; and the two
original producer/closed-report usability definition pins. The small
`io.prepare_input_references` helper exposes only these metadata/locators and
never opens/hashes a large body. Root adds current policy/scope/central-v2 pins.

After actual prepare closes and Root creates real terminal accounting:

```
PY -B REPO/workflows/data_v1_final/conformers/n1_pprime2_pilot_v3/run32.py
  --prepared ACTUAL_V3_PREPARED_JSON
  --prepare-accounting ACTUAL_STANDARD_PARENT_ACCOUNTING_CLOSURE_JSON
  --root-preflight ACTUAL_NEW_FRESH_PROOF
  --ledger-root RUN/artifacts/conformers/n1_pprime2_pilot_v2/once_ledger
  --output RUN/artifacts/conformers/n1_pprime2_pilot_v3/pilot32_v1
```

conformer / pilot=true / key n1_pprime2_pilot32_v3 / exact contract.SCOPE /
mode BOUNDED_PERFORMANCE_BATCH /16CPU / no explicit memory / whole cap8GiB /
finite wall<=48h. This is prepared32 only. Bind actual prepared/task/baseline/
population/SHA/mother/formal-config references, both actual aggregates, correction
and evidence/source sets, and accounting/raw-sacct refs. Do not substitute future
refs. Runner checks reviewed count/catalog/population/aggregate conservation
before any once claim; original ten tests precede science. At most16 workers,
all real optimizer events/failed prefixes, soft RSS/MemAvailable/quota/wall STOP
and natural drain remain; no forced scientific signal. The 1.5 cost policy is
actual report-and-continue, not estimate STOP. Failed4521326/new prepare/pilot/
cleanup costs all remain in Root's terminal ledger. C0 is not scientific acceptance.

Source-only delivery: no Python/AST/tests, Parquet/JSONL/LMDB body, science,
SSH/Slurm/Git or job submission was executed by this child.
