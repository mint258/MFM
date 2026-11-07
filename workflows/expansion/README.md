# PubChem v2 candidate preparation

This is new CPU-only preparation code. Existing WP5/S′ sources and outputs are
read-only. The source HEAD was checked on compute-0-20; the 1,488,715,010-byte
CID/SMILES file has **not** been downloaded. No candidate pool, UFF conformers,
D labels or decontamination result is claimed by this commit.

The external output root is
`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion`.
Every output uses a fresh path; partial failures remain visible. Data stay out
of Git. Root alone submits Slurm, reviews pilots and updates the shared STATUS.

## Source and screening

`source.py` accesses only the reviewed official HTTPS URL directly. It checks
HEAD length/Last-Modified before and after transfer, enforces range/If-Range
and a real 206 on resume, hashes the completed bytes, and publishes an immutable
receipt. Changed source versions stop rather than append incompatible bytes.
The initial pin is `configs/data_v1/expansion/pubchem_source_pin_v1.json`.

A fresh `expansion_user_quota_receipt_v1` is required for each materialization.
It contains username/uid, `basis=login_node_quota`, actual return code, timestamp,
numeric `quota -v` raw stdout in KiB, its SHA256 and available bytes. Positive
soft/hard limits determine available space; an unlimited zero field is ignored.
The raw row, available bytes and digest are cross-checked. Quota must retain
200 GB after the entire declared output budget, including failure/temporary data.

`screen.py` reads gzip incrementally and queues at most twice the worker count
of 256-row batches. A spawn pool performs real 16-worker chemistry work. Every
accepted CID retains its original row ordinal; duplicate full InChIKeys select
the smallest CID and preserve all CID aliases. SQLite is an external preparation
index, not the permanent family-parquet delivery format.

X01–X05 are the original WP0 definitions: multicomponent, element whitelist,
nonzero net formal charge, radical electrons, and odd total atomic-number sum
including H. Elements are H/B/C/N/O/F/Si/P/S/Cl/Se/Br/I. RDKit is pinned to
2025.09.5 (distribution spelling 2025.9.5 is equivalent). No neutralization,
tautomer normalization, isotope stripping, stereo removal or heavy-atom cutoff
is introduced. The observed v1 maximum of 252 is **not** a selection threshold.

The graph regression compares original-input X flags and reports every mismatch.
It deliberately cannot certify full v1 selection by itself: geometry-derived
X01, original selections and identity/role membership need a complete original
input comparison. Until `full_v1_selection_regression_passed` closes with >=99.9%
agreement and zero unexplained mismatches, production pool release is refused.

## All-source exclusion

`configs/data_v1/decontamination_sources.json` is a pending acquisition and
coverage manifest. URLs, old metadata hashes and upstream Git blob IDs do not
mean current data bytes were acquired or all splits were checked. Each source
must supply raw physical path/bytes/SHA256, identity-only JSONL path/bytes/SHA256,
and a pinned independent full-source coverage proof before status can be READY.

Each identity row contains only `source_id`, `role`, optional `subdataset`,
`inchikeys`, and optional `non_h_composition`. Targets/features are rejected.
The coverage proof uses schema `expansion_all_source_identity_coverage_v1` and
binds dataset, raw_artifacts, identities, expected_identity_records,
covered_roles, covered_subdatasets, all_splits=true, and
unresolved_without_identity_or_composition=0. The identity stream is counted
again, including every required role/subdataset. Unresolved original QM7 graph
identities use the existing conservative non-H composition policy; no graph
identity is invented from a filename or formula.

Matching uses full InChIKey **and** `key[:14]+':'+key[-1]`. The latter is the
WP5 connectivity/protonation key, not a Bemis–Murcko scaffold. It conservatively
excludes matching stereoisomers. Generic Murcko scaffolds are used only for
structural coverage/novelty after exclusion.

The old test-only Phase1 embargo does not close this new gate. Required sources
include v1 TRAIN/VAL/FULL plus embargo, official ExpansionRx train and test,
all SoM and QM9 records, previously used QM7, all 22 TDC ADMET endpoints,
the proposed MoleculeNet union, MARCEL Drugs-75K/Kraken, and COCONUT OOD identities.
The guide does not enumerate MoleculeNet subsets; its manifest explicitly keeps
that scope pending. COCONUT active/inactive coverage also needs verification.

## R/N queues and remaining integration

The frozen seed is 20261025. R is uniform SHA256 order of full identity. N is
ranked within heavy-atom × element-combination strata, with proportional weighted
fair interleaving. Its score uses v1 scaffold/ring-system presence and frequency
plus exact nearest-v1 ECFP4 Tanimoto distance. Downstream data cannot enter the
ranking projection. R and N are disjoint queues of 5M each; the first batch takes
the first 1.25M of each queue. Every later batch takes a longer prefix of these
same frozen queues. No conformers outside the first batch are computed.

`ranking.queues` is a bounded reference implementation (100k rows) for parity;
full-pool exact nearest-neighbor profiling and an external parallel sort are the
next separate implementation stage. Publication additionally requires complete
source screening, full v1 regression, an actually filtered all-source pool and
an exact v1-only fingerprint receipt. An exclusion index alone is insufficient.

The 10k-molecule UFF/D pilot is separate from the 10k-input screening pilot.
UFF must reuse the S′ source/parameters and pass a new no-PM7 input-adapter parity
check. UFF jobs use only nodes 14–19, never GPU or paid school resources. First
measure cost/success; Root reviews >500-core-hour batches and stops at 1.5× cost
overruns. Expansion runs no PM7, xTB or P′ calculations and enters no training.

## Commands (preparation only; not a submission instruction)

From the repository root on a verified compute node:

```bash
python -B -m unittest workflows.expansion.test_preparation -v
python -B -m workflows.expansion.decontamination metadata-status \
  --manifest configs/data_v1/decontamination_sources.json
```

Actual source, screening, exclusion and sorting commands require fresh quota,
external output paths and Root-approved pilots. This repository has no automatic
download, Slurm submission, dependency installation or scientific retry action.
