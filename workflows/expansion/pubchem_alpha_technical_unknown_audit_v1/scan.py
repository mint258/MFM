"""Column-pruned original typed evidence; historical body SHA is never relabelled fresh."""
import collections
import hashlib
import json
import os
from pathlib import Path
import stat
from ..alpha_runtime_v1.common import canonical, load, need, reference, verify, write
from .core import FIELDS, add_counts, category_counts, classify


def frame(s):
    need(stat.S_ISREG(s.st_mode) and s.st_uid == 1264 and s.st_nlink == 1, 'Own single-link closed source file')
    return {k:getattr(s,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_uid','st_nlink')}


def scan(spec, closed_ref, directory):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from ..pubchem_closed500_bulk_v2.schema import original_schema
    source = spec['Parquet_reference']; path = Path(source['path'])
    historical=load(verify(closed_ref))
    need(historical['source_fragment']==spec,'Same exact prior fragment receipt')
    unit = Path(directory)/spec['fragment_id'];unit.mkdir(exist_ok=False)
    output = unit/'technical_observations.DATA.jsonl'
    before = frame(path.lstat());need(before['st_size'] == source['bytes'], 'Original declared bytes')
    counts = collections.Counter(); observed = []; selected_groups = 0
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream, output.open('xb') as target:
        need(frame(os.fstat(stream.fileno())) == before, 'Exact current opened source')
        parquet = pq.ParquetFile(stream)
        need(parquet.schema_arrow.equals(original_schema(),check_metadata=True), 'Exact original full typed schema')
        need(parquet.metadata.num_rows == spec['rows'], 'Original complete physical row count')
        # Read only the category column over the whole source. Every error/source text
        # column is fetched only for row groups containing a recorded UNKNOWN.
        categories = parquet.read(columns=['category'],use_threads=False)['category'].to_pylist()
        all_counts = category_counts(categories);need(all_counts == spec['counts'], 'Original three-way source census')
        offset = 0
        for group in range(parquet.metadata.num_row_groups):
            n = parquet.metadata.row_group(group).num_rows
            indices = [i for i in range(n) if categories[offset+i] == 'technicalUnresolved']
            if indices:
                selected_groups += 1
                table = parquet.read_row_group(group,columns=list(FIELDS),use_threads=False)
                for local,row in zip(indices,table.take(pa.array(indices,type=pa.int64())).to_pylist()):
                    physical = offset+local
                    need(row['category'] == 'technicalUnresolved' and row['ordinal'] == spec['first_ordinal']+physical,
                         'Original physical row/ordinal binding')
                    need(row['cid_source_ascii'].isascii() and row['cid_source_ascii'].isdigit()
                         and int(row['cid_source_ascii'])>0, 'Exact original positive CID text')
                    need(hashlib.sha256(row['source_smiles'].encode('utf-8')).hexdigest() == row['source_smiles_sha256'],
                         'Exact original whole source SMILES hash')
                    part = json.loads(row['source_part_reference_json'])
                    need(set(part) == {'path','bytes','sha256'} and len(part['sha256']) == 64, 'Original source part pin')
                    observation = classify(row);add_counts(counts,row,observation)
                    value = dict(schema='PUBCHEM_ORIGINAL_TECHNICAL_UNKNOWN_OBSERVATION_V1',
                        source_fragment_id=spec['fragment_id'],source_reference=source,
                        prior_full_SHA_closure_receipt_reference=closed_ref,
                        physical_parquet_row_0based=physical,row_group_0based=group,row_in_group_0based=local,
                        original_typed_fields=row,recorded_exception_observation=observation,
                        source_raw_byte_offset=None,source_raw_byte_offset_not_retained_in_typed_schema=True,
                        raw_source_or_journal_replayed=False,scientific_acceptance=False)
                    target.write(canonical(value)+b'\n');observed.append(row['ordinal'])
            offset += n
        need(offset == spec['rows'] and len(observed) == spec['counts']['technicalUnresolved'], 'Full fragment UNKNOWN conservation')
        target.flush();os.fsync(target.fileno())
        after = frame(os.fstat(stream.fileno()))
        need(before == after == frame(path.lstat()), 'Full current same-file frame stable including device/ctime')
        parquet.close()
    result = dict(schema='PUBCHEM_TECHNICAL_UNKNOWN_FRAGMENT_AUDIT_V1',source_fragment=spec,
        prior_full_SHA_closure_receipt_reference=closed_ref,all_source_counts=all_counts,
        DATA=dict(reference(output),rows=len(observed)),counts=dict(counts),
        source_current_frame_before=before,source_current_frame_after=after,
        source_body_fresh_full_SHA_verified=False,historical_full_SHA_reused=True,
        historical_inode_or_same_device_claimed=False,selected_evidence_row_groups=selected_groups,
        full_category_column_scanned=True,chemistry_calls=0,pool_or_baseline_modified=False)
    technical={k[len('technical_code/'):]:v for k,v in counts.items() if k.startswith('technical_code/')}
    need(technical==historical['technical_reason_counts'],'Exact original closed technical-code frequency conservation')
    result['original_technical_reason_counts']=technical
    write(unit/'receipt.json',result)
    return result
