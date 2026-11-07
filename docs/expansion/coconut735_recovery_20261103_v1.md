# COCONUT original735 recovery and all-source exclusion

This module is part of taskbook section2.4. It preserves the exact2026-10
COCONUT source and all original unknown identities. It does not replace that
source by a newer download or treat an invalid parser result as a chemical
exclusion. Source-only authoring is not a completed dataset.

The existing actual Alpha1885088 output accounts for2,939,137 physical rows
(1,140,133 molecules and1,799,004 entries), exporting2,938,431 strict5 rows.
It retains735 NULL-molecule-FK entries without full keys or complete atom
composition. Actual1885095's exact735 replay completed and preserved these
UNKNOWN identities. Its immutable diagnosis pin is:

- Alpha `artifacts/coconut735_readonly_diagnosis_v1/day01_sonmi1/diagnosis735.DATA.jsonl`
-3,621,006 bytes; SHA256 `2c3f2be645f0b3e6ed708b6f0fbc09fcfb10fb5931aa8872c3b26189ca19a80cd`.

Main holds the copied pureQA evidence under
`control/alpha_coconut735_1885095_closed_pureQA_origin_v1/`. The scientific
DATA is not present in that metadata copy. Alpha transport must be restored
or these frozen scientific inputs copied with their exact hashes before the
recovery can be executed. No current scientific result is implied by this doc.

## Recovery rule

Use the exact original whole-string unsanitized parser parameters from the
old strict5 kernel and RDKit2025.09.5. Do not trim, repair charge, substitute
dummy atoms, infer missing atoms, sanitize, or generate a key. Fixed explicit
non-H atoms survive every completion of an original wildcard atom. Their
positive element counts therefore form a mathematically conservative
lower-bound veto. An original fixed element outside the unchanged X02 domain
proves disjointness. Original invalid syntax, non-ASCII/name suffixes, empty
strings and dummy-only strings remain HOLD, without being called nonmolecules.

Every present original canonical/standardized/parent variant must be covered.
All raw variants and exact physical table/block/ordinal/SHA remain in the
output ledger. A proposed atom bound is not automatically adopted: measure its
impact on the complete actual candidate pool, preserve possible over-exclusion
counts, and reject any degenerate universal exclusion. Any remaining HOLD must
be resolved from the same original source or exact official version-bound
identity evidence. Neither a newer CSV nor a plausible name match can resolve
an original physical source row.

`run.py` uses all735 original rows and an actual16CPU Slurm allocation. It has
no wall timeout, STOP2, fixed retry limit, or automatic READY transition. The
scheduler's real resource bounds still apply. Root supplies actual disk/quota
admission and current source pins before submission. Output is new immutable
JSONL and receipt under a fresh artifact directory. No old DATA is overwritten.

Example runtime (Root supplies exact existing absolute paths):

```
PY -B -m workflows.expansion.coconut735_recovery_v1.run --diagnosis DIAGNOSIS --expected-sha256 2c3f2be645f0b3e6ed708b6f0fbc09fcfb10fb5931aa8872c3b26189ca19a80cd --expected-bytes 3621006 --workers 16 --output FRESH_DIRECTORY
```

Tests cover original fixed atoms plus wildcard/fragments, dummy-only/syntax
HOLD, forbidden fixed elements, actual SQLite exact/typed veto behavior and
rejection of incomplete source indexes. Execute these within Root's existing
allocated scientific validation parent; source author has performed AST only.

## MoleculeNet and all11 sources

MoleculeNet does not need another21-source graph calculation. The actual
Root acceptance already exists at
`control/molnet21_4524733_actual_conservative_coverage_root_acceptance_v1.json`,
with a matching `...actual_root_adoption_readback_v1.json`:4524733 C0,35s,
16CPU, all21 physical dispositions retained,6 composition overlay rows and2
typed lower bounds. Original graph UNKNOWN stays unchanged.

The top-level READY9 manifest is stale for that adopted conservative evidence.
`manifest.py` composes those original9 sources, existing MolNet adoption, and
an independently accepted complete735 COCONUT coverage package into the new
`expansion_decontamination_sources_with_constraints_v3` schema. It refuses
partial735, unmeasured or universal vetoes and does not pretend metadata
composition is actual index/filter completion.

`consumer.py` keeps direct original `decontamination.identity_keys` and
`decontamination.contamination` function objects. Its independent V3 index
primitives allow both MoleculeNet and COCONUT source-bound positive atom rules,
validate every candidate against the original X02 domain and preserve
full-key/WP5/exact-composition exclusions. Old V2 hardcodes exactly2 MolNet
rules and cannot represent COCONUT constraints; old files remain unchanged.
Root's actual full-pool pipeline must use V3 explicitly and establish the
complete physical all11 index/filter evidence. No downstream descriptors,
activity values, task labels or similarity scores enter exclusion decisions.

Status at source handoff: code and this report are prepared; actual735 DATA,
remaining HOLD disposition, full-pool veto impact and complete all11 filter
remain pending. No scientific READY or pool release is claimed.
