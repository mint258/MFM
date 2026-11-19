"""Materialize the published Jonas 2018 train/test membership without resplitting."""
import argparse
from collections import Counter
import json
from pathlib import Path
import tarfile
import pyarrow as pa
import pyarrow.parquet as pq
from .nmr_graph_source import restricted_graph_load
from .pprime_tmpfs_queue import capacity

SCHEMA=pa.schema([('nucleus',pa.string()),('molecule_id',pa.int64()),
    ('official_split',pa.string()),('source_frame_row',pa.int64()),
    ('source_frame_index',pa.string()),('archive_member',pa.string())])

def split_records(nucleus, split, frame, member):
    if nucleus not in ('13C','1H') or split not in ('train','test'):
        raise ValueError('Unrecognized author split')
    if 'molecule_id' not in frame.columns:
        raise ValueError('Author molecule identity missing')
    for pos,(index,mid) in enumerate(frame['molecule_id'].items()):
        yield dict(nucleus=nucleus,molecule_id=int(mid),official_split=split,
            source_frame_row=pos,source_frame_index=str(index),archive_member=member)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--attempt',required=True)
    p.add_argument('--quota-snapshot',type=Path,required=True)
    a=p.parse_args()
    def safe():capacity(a.root,a.quota_snapshot,needed=33554432)
    safe()
    source=a.root/'raw/NMRShiftDB2_Jonas2019/13321_2019_374_MOESM2_ESM.gz'
    out=a.root/'directive19/NMR2018'/a.attempt
    out.mkdir(parents=True,exist_ok=False)
    counts=[];seen=set()
    pa.set_cpu_count(1)
    with pq.ParquetWriter(out/'author_splits.parquet',SCHEMA,compression='zstd') as writer:
        with tarfile.open(source,'r:gz') as archive:
            for member in archive:
                if not member.name.endswith('.pickle'):continue
                if '.13C.' in member.name:nucleus='13C'
                elif '.1H.' in member.name:nucleus='1H'
                else:raise ValueError('Unknown author pickle nucleus')
                if nucleus in seen:raise ValueError('Multiple author files for one nucleus')
                seen.add(nucleus)
                data=restricted_graph_load(archive.extractfile(member).read())
                for split in ('train','test'):
                    frame=data[split+'_df'];ids=set();n=0;buffer=[]
                    for record in split_records(nucleus,split,frame,member.name):
                        ids.add(record['molecule_id']);n+=1;buffer.append(record)
                        if len(buffer)>=8192:
                            safe();writer.write_table(pa.Table.from_pylist(buffer,schema=SCHEMA));buffer=[]
                    if buffer:
                        safe();writer.write_table(pa.Table.from_pylist(buffer,schema=SCHEMA))
                    counts.append(dict(nucleus=nucleus,official_split=split,source_rows=n,
                        unique_molecule_ids=len(ids),columns=list(map(str,frame.columns)),
                        archive_member=member.name))
                    print('AUTHOR_SPLIT_MATERIALIZED',nucleus,split,n,len(ids),flush=True)
                del data
    if seen!={'13C','1H'}:raise ValueError('Both original nuclei required')
    result=dict(status='AUTHOR_SPLITS_MATERIALIZED_PUBLISHED_COUNT_RECONCILIATION_PENDING',
        authority='6d056a41f379b921d31017ecfed9ce84d1a5c71a',source=str(source),
        source_split='nmrshiftdb2-2018; original train_df/test_df',
        reconstructed_split=False,counts=counts,records=str(out/'author_splits.parquet'),
        source_rows_reassigned=False,domain_filter_applied=False,
        published_test_molecule_counts_matched=False,
        target_values_exported=False,UFF_geometry_ready=False,
        independent_numeric_readback=False,new_data_content_hashes=False)
    safe();(out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print('AUTHOR_SPLIT_PREPARATION_CLOSED',out/'manifest.json',flush=True)

if __name__=='__main__':main()
