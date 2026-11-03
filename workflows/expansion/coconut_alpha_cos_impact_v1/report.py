"""Render the completed hypothetical source-impact census without filtering."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--actual-review',type=Path,required=True)
    p.add_argument('--diagnostic',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();review_bytes=a.actual_review.read_bytes();review=json.loads(review_bytes)
    raw=a.diagnostic.read_bytes();data=json.loads(raw);ref=review['diagnostic_reference']
    assert len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256']
    assert review['status']=='ACCEPTED_READONLY_IMPACT_DIAGNOSTIC_NOT_EXCLUSION'
    assert review['actual_parent']['State']=='COMPLETED' and review['actual_parent']['ExitCode']=='0:0'
    assert not review['candidate_filtering_performed'] and not data['lower_bounds_or_exclusions_accepted']
    counts=data['counts'];assert counts==review['counts'] and counts['all_rows_accounted']
    assert counts['invalid_or_noncanonical_composition_rows']==0
    combos=[]
    for row in counts['eight_C_O_S_combinations']:
        label='/'.join(k for k in ('C','O','S') if row[k]) or 'none'
        combos.append('| '+label+' | '+format(row['rows'],',')+' |')
    candidate=data['input_candidate_reference'];parent=review['actual_parent']
    text=f'''# COCONUT unspecified-source impact

## Purpose

Quantify the full-pool consequence of the unadopted conservative C/O/S bounds from the cached unresolved source entries. This is a hypothetical diagnostic, not a candidate filter or a source-scope decision.

## Inputs and hashes

- Complete unfiltered minCID candidate Parquet: `{candidate['path']}`, {candidate['bytes']:,} bytes, previously established SHA256 `{candidate['sha256']}`.
- Actual diagnostic: `{ref['path']}`, SHA256 `{ref['sha256']}`.
- Byte-identical actual Root review copy: `{a.actual_review}`, SHA256 `{hashlib.sha256(review_bytes).hexdigest()}`.
- Actual Alpha parent: {parent['JobIDRaw']}, {parent['NodeList']}, {parent['AllocCPUS']} CPUs, COMPLETED 0:0, {parent['ElapsedRaw']} seconds.

## Rules and parameters

The fixed source-derived minimal antichain is C>=1 OR O>=1 OR S>=1. DuckDB {data['duckdb_version']} scanned only the existing non-H composition column of every candidate, parsed each complete integer-pair vector, and checked canonical ordering, unique positive counts and valid non-H atomic numbers. No sampling, chemistry or structural redefinition occurred. Empty non-H vectors remain valid. The out-of-domain Fe source observation remains intact and is not shortened to a weaker vector.

## Script-generated results

| Measure | Candidates |
|---|---:|
| Full candidate census | {counts['total_rows']:,} |
| Hit by hypothetical C/O/S union | {counts['contains_any_C_O_S']:,} |
| Not hit, before any other exclusion | {counts['contains_none_C_O_S']:,} |
| Empty non-H vector | {counts['empty_non_H_vector_rows']:,} |
| Invalid or noncanonical composition | {counts['invalid_or_noncanonical_composition_rows']:,} |
| Fe / outside original X element domain | {counts['Fe_containing_rows']} / {counts['outside_original_X_element_rows']} |

| Present among C/O/S | Candidates |
|---|---:|
'''+ '\n'.join(combos)+f'''

At most {counts['contains_none_C_O_S']:,} candidates would remain under this hypothetical rule, before v1 and other downstream exclusions. This cannot supply the requested {review['target_molecules']:,}-molecule first batch. All {counts['total_rows']:,} unfiltered candidates remain unchanged; no exclusion has been applied.

## Exceptions and handling

The first diagnostic attempt exposed different client-local Gluster device numbers on login and compute nodes. The corrected runtime keeps both device values as observations, checks the current native volume/mount authority, retains the historical inode and mtime/ctime checks, and compares the complete current FD/path frame before and after reading. It does not claim cross-host device-number identity or a fresh 34 GB whole-body SHA. The single SQL boundary fixture passed before the full scan. Earlier failed attempts and all source records remain preserved.

## Known limits

These counts do not resolve graph UNKNOWN735, authorize quarantine, adopt lower bounds, complete all11 decontamination sources, rank candidates or release a dataset. The three exact finite-source recoveries remain separate. The pending user source-scope decision is unchanged. The remaining-count result is an upper bound for this hypothetical veto and is not an accepted eligible pool.
'''
    with a.output.open('x') as f:f.write(text)
    print(json.dumps(dict(report=str(a.output),candidates=counts['total_rows'],hypothetical_remaining=counts['contains_none_C_O_S'],filtering_performed=False)))


if __name__=='__main__':main()
