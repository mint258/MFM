"""Render task2.2 from completed acquisition/EOF evidence; no data-body replay."""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path


def read(path):
    raw=path.read_bytes()
    return json.loads(raw),dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('download','inventory','pin','accounting','output_directory'):
        parser.add_argument('--'+name.replace('_','-'),required=True,type=Path)
    args=parser.parse_args()
    download,dref=read(args.download);inventory,iref=read(args.inventory)
    pin,pref=read(args.pin);account,aref=read(args.accounting)
    assert download['schema']=='pubchem_download_complete_v1' and download['status']=='RAW_ACQUIRED_NO_CHEMICAL_SCREENING'
    assert inventory['schema']=='SB5_PUBCHEM_RAW_INVENTORY_RECEIPT_V2' and inventory['status']=='RAW_FULL_EOF_INVENTORY_COMPLETE_NO_CHEMICAL_SCREENING'
    assert account['endpoint']=='202.38.247.57:22' and account['uid']==1278
    parents={row['JobIDRaw']:row for row in csv.DictReader(io.StringIO(account['raw_sacct']),delimiter='|') if row['JobIDRaw'] in ('4520348','4521093')}
    assert set(parents)=={'4520348','4521093'}
    assert all(row['State']=='COMPLETED' and row['ExitCode']=='0:0' and row['UID']=='1278' for row in parents.values())
    raw=download['file'];assert raw==inventory['raw_source']
    assert download['gzip']['gzip_read_to_eof_crc_validated'] and inventory['gzip_EOF_CRC_revalidated'] and inventory['raw_complete_SHA_verified']
    counts=inventory['counts'];assert counts['records']==counts['cid_records']==124857440 and counts['global_unique_cids_proven'] and counts['strictly_increasing_cids']
    assert inventory['source_index']['part_count']==500
    assert pin['content_length']==raw['bytes'] and pin['last_modified']==download['source_version']
    first=min(row['started_unix_seconds'] for row in download['parts'])
    snapshot=dict(schema='PUBCHEM_ACQUIRED_SOURCE_SNAPSHOT_V1',status='ACQUISITION_AND_FULL_EOF_CID_INVENTORY_COMPLETE',
        official_source_url=pin['url'],snapshot_observed_on=pin['observed_on'],download_started_UTC=dt.datetime.fromtimestamp(first,dt.timezone.utc).isoformat(),
        source_version_basis='OFFICIAL_HTTP_LAST_MODIFIED_SNAPSHOT_NOT_DATABASE_RELEASE_NUMBER',source_last_modified=download['source_version'],
        compressed_source=raw,uncompressed_bytes=counts['uncompressed_bytes'],source_records=counts['records'],unique_positive_CIDs=counts['cid_records'],
        source_index=inventory['source_index'],metadata_inputs=dict(download=dref,inventory=iref,initial_HEAD_pin=pref,actual_accounting=aref),actual_parents=parents,
        historical_full_SHA_and_gzip_EOF_validated=True,new_data_body_rehash_performed=False,chemical_screening_or_candidate_release_claimed=False)
    out=args.output_directory;out.mkdir(parents=True,exist_ok=False)
    (out/'pubchem_acquired_snapshot.json').write_text(json.dumps(snapshot,sort_keys=True,indent=2)+'\n')
    text=f'''# PubChem acquisition (task 2.2)

## Purpose

Preserve the complete official CID-SMILES snapshot and CID provenance for expansion. This report is generated from completed acquisition and EOF receipts; it performs no new network download or chemical screening.

## Inputs and hashes

- Official URL: {pin['url']}
- Snapshot observed: {pin['observed_on']}; first download byte-range start (UTC): {snapshot['download_started_UTC']}.
- Official Last-Modified: {download['source_version']}. This HTTP snapshot identifier is not an invented PubChem database release number.
- Compressed bytes: {raw['bytes']:,}; SHA256: `{raw['sha256']}`.
- Download receipt: `{dref['path']}`; SHA256 `{dref['sha256']}`.
- EOF receipt: `{iref['path']}`; SHA256 `{iref['sha256']}`.
- Current terminal-accounting evidence: `{aref['path']}`; SHA256 `{aref['sha256']}`.

The machine snapshot preserves every metadata input pin, original raw-source reference and all 500 source-part index pins.

## Rules and parameters

The original downloader used sixteen exact HTTP byte ranges, two simultaneous network transfers, streamed assembly, full compressed SHA256 and gzip EOF/CRC validation. The independent inventory read every source row, preserved CID-SMILES records without chemistry changes, and established globally unique positive CIDs by strict increasing order. No proxy or network bypass was used.

## Script-generated results

| Measure | Result |
|---|---:|
| Source records / unique CIDs | {counts['records']:,} |
| Uncompressed source bytes | {counts['uncompressed_bytes']:,} |
| Indexed source parts | {inventory['source_index']['part_count']} |
| Maximum source line bytes | {counts['maximum_source_line_bytes']} |
| Acquisition job | 4520348 COMPLETED 0:0 |
| Independent full-EOF job | 4521093 COMPLETED 0:0 |

## Exceptions and handling

The initial HEAD pin intentionally has no body SHA; the completed download and independent full-EOF receipts provide the authoritative body hash. Historical source paths and partials remain provenance. No existing file is deleted or rewritten by this report, and no historical receipt is promoted or changed.

## Known limits

This metadata report reuses the two actual completed data jobs and freshly checked terminal accounting. It does not claim a new full-body rehash, current availability at every historical path, chemical screening, decontamination, novelty ranking, UFF generation or a completed expansion dataset. The raw snapshot is versioned by URL/date/Last-Modified/content hash; later upstream changes require a new snapshot.
'''
    (out/'pubchem_acquisition.md').write_text(text)
    print(json.dumps(dict(report=str(out/'pubchem_acquisition.md'),snapshot=str(out/'pubchem_acquired_snapshot.json'),source_records=counts['records'])))


if __name__=='__main__':main()
