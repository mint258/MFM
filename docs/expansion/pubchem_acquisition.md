# PubChem acquisition (task 2.2)

## Purpose

Preserve the complete official CID-SMILES snapshot and CID provenance for expansion. This report is generated from completed acquisition and EOF receipts; it performs no new network download or chemical screening.

## Inputs and hashes

- Official URL: https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/CID-SMILES.gz
- Snapshot observed: 2026-10-25; first download byte-range start (UTC): 2026-10-25T05:33:55.695161+00:00.
- Official Last-Modified: Sat, 24 Oct 2026 18:17:31 GMT. This HTTP snapshot identifier is not an invented PubChem database release number.
- Compressed bytes: 1,488,715,010; SHA256: `2504bc00da1b0587ae208d8a5fb2a4fe6043c215436150f2023d59c57c5cd2b7`.
- Download receipt: `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion/raw/pubchem_20261025_v1/attempt_4520348/receipt.json`; SHA256 `2a945e3bfa378b1f958d0214e6a2448cf97d22f81ec2455f359077e3887ad478`.
- EOF receipt: `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion/raw/sb5_pubchem_raw_inventory_v2_cpu_default_memory_v1/receipt.json`; SHA256 `048dda8b56cc1ba91cf95e488c94f5bc88ecae1e71269db9e29b809a844cd9b2`.
- Current terminal-accounting evidence: `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/pubchem_alpha_return_20261103/acquisition_source_actual_accounting_20261103.json`; SHA256 `e05138a9d3c8b8b18349cb1e64bcd13355d781fb264d5eef8239240d994ae8bc`.

The machine snapshot preserves every metadata input pin, original raw-source reference and all 500 source-part index pins.

## Rules and parameters

The original downloader used sixteen exact HTTP byte ranges, two simultaneous network transfers, streamed assembly, full compressed SHA256 and gzip EOF/CRC validation. The independent inventory read every source row, preserved CID-SMILES records without chemistry changes, and established globally unique positive CIDs by strict increasing order. No proxy or network bypass was used.

## Script-generated results

| Measure | Result |
|---|---:|
| Source records / unique CIDs | 124,857,440 |
| Uncompressed source bytes | 8,880,849,781 |
| Indexed source parts | 500 |
| Maximum source line bytes | 3786 |
| Acquisition job | 4520348 COMPLETED 0:0 |
| Independent full-EOF job | 4521093 COMPLETED 0:0 |

## Exceptions and handling

The initial HEAD pin intentionally has no body SHA; the completed download and independent full-EOF receipts provide the authoritative body hash. Historical source paths and partials remain provenance. No existing file is deleted or rewritten by this report, and no historical receipt is promoted or changed.

## Known limits

This metadata report reuses the two actual completed data jobs and freshly checked terminal accounting. It does not claim a new full-body rehash, current availability at every historical path, chemical screening, decontamination, novelty ranking, UFF generation or a completed expansion dataset. The raw snapshot is versioned by URL/date/Last-Modified/content hash; later upstream changes require a new snapshot.
