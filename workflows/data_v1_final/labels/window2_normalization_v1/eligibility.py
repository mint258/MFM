"""Final Common effective TRAIN, with exact D5 native conformer exclusions."""
import collections,sqlite3
from pathlib import Path
from . import io as I
from .reader import need
from ..source_status_cpu_auto_memory_v1.support import sqlite_ro


def eligible(role,common,rid,excluded):
    if role not in ('TRAIN','VAL','FULL','EMBARGO'):raise ValueError('UNKNOWN_FINAL_ROLE')
    if role!='TRAIN':return False,'ROLE_'+role
    if not common:return False,'OUTSIDE_FINAL_COMMON'
    if rid in excluded:return False,'D5_HELDOUT_BASE_AND_ALL_TASK_INPUT_VIEWS'
    return True,'COMMON_TRAIN_NOT_D5'


def build(cfg,root):
    import pyarrow.parquet as pq
    common=I.load_data(cfg['common_reference']);d5=I.load_data(cfg['d5_reference']);members={}
    for ref in common['membership_tables']:
        table=pq.ParquetFile(ref['path'])
        try:
            for batch in table.iter_batches(columns=['molecule_id','effective_role','common_population'],batch_size=8192):
                for row in batch.to_pylist():
                    mid=row['molecule_id'];need(mid not in members,'FINAL_COMMON_DUPLICATE_MOLECULE')
                    members[mid]=(str(row['effective_role']).upper(),bool(row['common_population']))
        finally:table.close()
    excluded=set();diagnostic=I.load_data(cfg['d5_reference'])['diagnostic_base_reference']
    table=pq.ParquetFile(diagnostic['path'])
    try:
        for batch in table.iter_batches(columns=['geometry_source','native_record_id'],batch_size=8192):
            for row in batch.to_pylist():
                if row['geometry_source']=='pm7':
                    rid=row['native_record_id'];need(isinstance(rid,str) and rid,'ORIGINAL_D5_NATIVE_RECORD_ID_REQUIRED');excluded.add(rid)
    finally:table.close()
    need(len(excluded)==d5['heldout_PM7_bases'],'FINAL_D5_PM7_EXCLUSION_COUNT')
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    source=sqlite_ro(cfg['canonical_index']['path']);side=sqlite3.connect(root/'eligibility.sqlite')
    side.execute('PRAGMA journal_mode=DELETE');side.execute('PRAGMA synchronous=FULL')
    side.executescript('CREATE TABLE eligibility(ordinal INTEGER PRIMARY KEY,rid TEXT,mid TEXT,job TEXT,source_role TEXT,effective_role TEXT,common_population INTEGER,geometry_id TEXT,parent_geometry_id TEXT,fit_eligible INTEGER,fit_reason TEXT); CREATE INDEX side_job ON eligibility(job,ordinal);')
    counts=collections.Counter();total=0;fit=0
    try:
        current=source.execute('SELECT record_ordinal,record_id,molecule_id,job_id,new_role FROM records ORDER BY record_ordinal')
        while rows:=current.fetchmany(8192):
            output=[]
            for ordinal,rid,mid,job,original_role in rows:
                need(mid in members,'FINAL_COMMON_ORIGINAL_MOLECULE_UNRESOLVED')
                role,common_member=members[mid];keep,reason=eligible(role,common_member,rid,excluded)
                output.append((ordinal,rid,mid,job,original_role,role,int(common_member),None,None,int(keep),reason))
                counts[reason]+=1;fit+=keep
            side.executemany('INSERT INTO eligibility VALUES(?,?,?,?,?,?,?,?,?,?,?)',output);side.commit();total+=len(rows)
        need(total==cfg['source_records'] and fit>0,'COMPLETE_ORIGINAL_CANONICAL_ELIGIBILITY')
    finally:source.close();side.close()
    return {'eligibility_reference':I.ref(root/'eligibility.sqlite'),'source_records':total,'fit_records':fit,'reason_counts':dict(counts),
            'Common_TRAIN_only':True,'D5_excludes_base_and_all_14_source_tasks':True,'PM7_diagnostic_records':len(excluded)}
