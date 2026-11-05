# COCONUT unspecified-source impact

## Purpose

Quantify the full-pool consequence of the unadopted conservative C/O/S bounds from the cached unresolved source entries. This is a hypothetical diagnostic, not a candidate filter or a source-scope decision.

## Inputs and hashes

- Complete unfiltered minCID candidate Parquet: `/gfshome/alpha/pubchem_expansion_20261103/bulk/original502/unfiltered_pool/attempt_451a57df0a7949f8aef3a9867a35a1c7/candidates.parquet`, 34,325,191,493 bytes, previously established SHA256 `bcaf4726737611c9b534a2aff28d694adb8b4b12ea162693ff0ec1589f7065b1`.
- Actual diagnostic: `/gfshome/alpha/pubchem_expansion_20261103/reports/cos_impact_v3_job_1885163/impact_diagnostic.json`, SHA256 `928a55c00074ea93cc43fe55b03d6c3bc2c4c9a55305598eb6b317ed6f82295f`.
- Byte-identical actual Root review copy: `docs/expansion/coconut_source_scope_impact_20261103_v1.json`, SHA256 `de0d6ffa890e6e6858c49b1863766756c8061c0c066151f11f9bc6e1160e4fb0`.
- Actual Alpha parent: 1885163, compute-0-1, 16 CPUs, COMPLETED 0:0, 32 seconds.

## Rules and parameters

The fixed source-derived minimal antichain is C>=1 OR O>=1 OR S>=1. DuckDB 1.2.2 scanned only the existing non-H composition column of every candidate, parsed each complete integer-pair vector, and checked canonical ordering, unique positive counts and valid non-H atomic numbers. No sampling, chemistry or structural redefinition occurred. Empty non-H vectors remain valid. The out-of-domain Fe source observation remains intact and is not shortened to a weaker vector.

## Script-generated results

| Measure | Candidates |
|---|---:|
| Full candidate census | 109,871,959 |
| Hit by hypothetical C/O/S union | 109,868,692 |
| Not hit, before any other exclusion | 3,267 |
| Empty non-H vector | 8 |
| Invalid or noncanonical composition | 0 |
| Fe / outside original X element domain | 0 / 0 |

| Present among C/O/S | Candidates |
|---|---:|
| none | 3,267 |
| S | 1,489 |
| O | 3,385 |
| O/S | 2,684 |
| C | 9,409,714 |
| C/S | 3,211,746 |
| C/O | 67,982,010 |
| C/O/S | 29,257,664 |

At most 3,267 candidates would remain under this hypothetical rule, before v1 and other downstream exclusions. This cannot supply the requested 2,500,000-molecule first batch. All 109,871,959 unfiltered candidates remain unchanged; no exclusion has been applied.

## Exceptions and handling

The first diagnostic attempt exposed different client-local Gluster device numbers on login and compute nodes. The corrected runtime keeps both device values as observations, checks the current native volume/mount authority, retains the historical inode and mtime/ctime checks, and compares the complete current FD/path frame before and after reading. It does not claim cross-host device-number identity or a fresh 34 GB whole-body SHA. The single SQL boundary fixture passed before the full scan. Earlier failed attempts and all source records remain preserved.

## Known limits

These counts do not resolve graph UNKNOWN735, authorize quarantine, adopt lower bounds, complete all11 decontamination sources, rank candidates or release a dataset. The three exact finite-source recoveries remain separate. The pending user source-scope decision is unchanged. The remaining-count result is an upper bound for this hypothetical veto and is not an accepted eligible pool.
