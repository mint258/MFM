# N1 mother count provenance review

2026-10-26. Static source and small-control-receipt review only. No Python,
AST, tests, SSH, Slurm, scientific computation, per-molecule Parquet, mother
JSONL, LMDB or other scientific body was read or executed by this reviewer.
No registered v2 source, original data or historical receipt was changed.

## Confirmed cause

Main preparation4521326 produced mother_count5105, eligible_count0,
selected_count0 and reason_counts={MOTHER_COUNT_NOT5040:5105}. Its prepared
status is PENDING_INPUT32_NOT_READY. new_UFF_calls and new_QM_calls are0.
Root reports actual FAILED/3:0,123s,16CPU,compute-0-13; this review did not
query the scheduler or substitute a producer receipt for terminal accounting.

The count5105 is the actual population selected by prepare_cpu.py:100:

    CREATE TEMP TABLE mother AS SELECT * FROM p WHERE S_conformers=1

The same entry checks the full per-molecule population is1220466 unique
molecules. Mother selection precedes the frozen-role join and every
TRAIN/VAL, PM7-usable, UFF-support, pointer or strict-baseline eligibility
condition. Thus5105 means all source molecules with original S_conformers=1
in this exact pinned per-molecule audit, not a success-only or TRAIN-only
population and not frozen common.

The source audit producer s_population_alignment_v4.py:27–35 defines
S_conformers as count(*) per canonical source molecule. S_usable_conformers
is a separate count requiring ORIGINAL_PM7_GEOMETRY and nonempty native
atomic numbers. Sprime_conformers separately counts rows with status=SUCCESS
and converged=true. These fields cannot be interchanged.

prepare_cpu.py:122 makes count!=(5040,5040) the first per-row reason. With
actual5105, this condition short-circuits all later eligibility reasons for
every mother. No item reaches validate_original. eligible_count0 therefore
does not demonstrate that every source or original baseline is invalid.
The ready condition at:185 independently repeats the same5040 equality.

## What5040 does and does not establish

The earliest5040 reference found within this bounded review is
configs/data_v1/conformers/n1_pprime2_proposal_v1.json:12:
expected_source_pm7_n1_molecules=5040. It has no independently measured N1
count or aggregate-source reference attached to that number. The original
proposal planner at plan.py:80–82 computes the same unfiltered
S_conformers=1 count and compares it to this configured constant; its source
alone is not evidence that the comparison ever passed on real data.
Subsequent generation/pilot contracts, source catalogs and READMEs inherit
the constant. Repeated prose is not independent population evidence.

The following original small closed summaries were inspected without
reopening their scientific tables: s_sprime_alignment_v4.json(3804B),
s_population_closed_summary_independent_review_v1.json(76781B), the Sprime
dataset manifest.json(11430B)/closure.json(6345B),
reports/full_generation_summary.json(8281B), and
training_inputs_v1/manifest.json(4238B). They establish whole-population,
role or strict-usability totals but do not provide an N1 count or a5040
N1-status/role cross-tab. Their source fields do not reconcile the65 difference.
Root reports no other known old readiness-receipt path and ended the search
at this boundary; this is not a claim that no such evidence exists anywhere.

There is consequently no evidence here to identify5040 as the successful
Sprime-baseline subset, a TRAIN/ROUTINE/FULL subset or another physical
population. The65 difference is arithmetic only. Its molecular identities,
status distribution, role distribution and cause remain UNKNOWN. In
particular it must not be labeled65 FAILED,65 FULL or65 ROUTINE, or silently
removed from the real5105 mother. Earlier descriptions calling5040 the
established original PM7 N1 mother should be treated as an unverified legacy
claim, not a source authority. This review does not rewrite frozen history.

## Exact small evidence

Paths below are relative to /share/home/zixiao/descriptor_analysis/.
Only the listed small receipts/source files were hashed by this review.

| Path | Bytes | SHA256 |
| --- | ---: | --- |
| runs/data_v1_20261025/artifacts/conformers/n1_pprime2_pilot_v2/prepared_v1/prepared.json |2670|cc8203a3e5af6d6ac5f8104afc2272ff2d1ce2f5adab587a3278f7d197b6dd2c|
| runs/data_v1_20261025/artifacts/conformers/n1_pprime2_pilot_v2/prepared_v1/source_population_authority.json |8583|b3230f829f1ea3ad8f1cc48c174cf71d148fa285ca0681d8fda873277e25e5e2|
| runs/data_v1_20261025/artifacts/conformers/n1_pprime2_pilot_v2/prepared_v1/source_sha_validation.json |16006|087c3089f1928d086a9e6ec7001bce255f817090bc17d57703186e2e474de4d9|
| runs/data_v1_20261025/repository/configs/data_v1/conformers/n1_pprime2_proposal_v1.json |1302|3e47cbcb2c56baa12ad92c04e1f3eee36b3506607fb1cb2683f8f65c68a60b42|
| runs/data_v1_20261025/repository/workflows/data_v1_final/conformers/n1_pprime2_pilot_v2/prepare_cpu.py |18008|29403314ed3961d610232cfb81f203c1274e7ce630bb9809132cfe9f191f1af1|

The source-SHA receipt reports ALL_ACTUAL_SOURCE_SHA_VERIFIED under actual
job4521326/UID1278/16CPU. The source authority binds the same original
per-molecule audit:
runs/pretraining_readonly_audit_20261023_v1/tables/s_sprime_per_molecule_v4.parquet,
5650950B/SHA9b53e4611c5a3f199f785c8c201aa56ce76f559e3c81ccf10d1819624e03e354.
This last locator/hash is inherited from the real receipt; this review did
not open or hash that Parquet. Likewise the mother JSONL references in the
small receipts are provenance only and were not opened here.

## Minimal new v3 proposal

1. Preserve registered v2 and its failed parent/cost/output. Use a new v3
   namespace, exact scope, job name, output and source pins. Root supplies an
   explicit count-override authority referencing the actual1326 receipts and
   this same source version. Retain5105 as the real unfiltered source mother;
   retain5040 separately as LEGACY_UNRECONCILED_REFERENCE. Do not merely change
   one equality while leaving contracts/catalogs/scope/status claiming5040.
2. On a new admitted CPU preparation, produce small independent cross-tabs
   for all5105 by S_conformers/S_usable_conformers, Sprime_status, declared
   strict usable count, actual accepted baseline count, source/effective role
   and pointer count. Include whole counts/conservation and explicit unknowns.
   This is the next evidence for any proposed5040 subset or65 explanation.
   A global legacy-count mismatch must not overwrite every per-row reason.
3. Keep every original mother in the inventory; apply unchanged TRAIN/VAL,
   unsupported, single original pointer and strict valid-baseline/atom/graph/
   stereo/energy/seed rules. Select the same deterministic32 only after actual
   eligibility validation. Retain all pending reasons and false common/
   production membership. Census5105 is not authorization to generate5105.
4. Preserve the original science, source_N=1,10-candidate budget, original
   baseline,32 pilot, seed domain and shared once-ledger/task identities. A
   source-count correction must not create a new scientific retry domain.
   Root separately integrates/reviews v3, obtains real preparation C0 and
   closes all costs before the existing guarded generation stage.

No v3 code, count override, eligibility cross-tab or actual science is
created by this review. The65 explanation and final common membership remain
unresolved.
