"""Add uniform UFF scope while referencing every reusable closed geometry in place."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sqlite3
import time
import pyarrow as pa
import pyarrow.parquet as pq
from . import geometry_queue
from .downstream_science import identities
from .pprime_tmpfs_queue import FORECAST
from .admission import protect as quota_protect
from .shared_access import check_access,publish

NEW_PPRIME_FORECAST=80000000000
PEER_ENVIRONMENT_RESERVE=24*1024**3

def joint_capacity(root,snapshot,needed):
    pp=root/'labels/Pprime/shared_v1'
    used=sum(p.stat().st_size for p in pp.glob('*.sqlite'))
    old_remaining=max(67108864,FORECAST-used)
    access=json.loads((root/'geometry/shared_v1/access.json').read_text())
    producer=json.loads(Path(access['source_producer_manifest']).read_text())
    if not source_closed(access,producer,os.getuid()):
        raise ValueError('Original geometry future cannot be retired without native sealed closure')
    quota_protect(root,old_remaining+needed+NEW_PPRIME_FORECAST+PEER_ENVIRONMENT_RESERVE,
                  snapshot,own_concurrent_bytes=1073741824)

def source_closed(access,producer,uid):
    raw=access.get('actual_closure_evidence',{}).get('raw','')
    return bool(access.get('immutable') and access.get('cross_node_read_allowed')
        and access.get('publishing_uid')==uid
        and str(producer.get('job'))==str(access.get('producer_job'))
        and producer.get('status')=='ALL_QUEUED_MOLECULES_TERMINAL'
        and not any(producer.get('states',{}).get(k,0) for k in ('PENDING','INTENT'))
        and 'JobState=COMPLETED' in raw and 'ExitCode=0:0' in raw
        and 'JobId='+str(access['producer_job'])+' ' in raw)

def source_route(source,mid,smiles):
    row=source.execute('SELECT model_smiles,state FROM tasks WHERE mid=?',(mid,)).fetchone()
    if row is None:return None
    if row[0]!=smiles:raise ValueError('Existing ordered graph identity disagrees')
    if row[1] in ('PENDING','INTENT'):raise ValueError('Original geometry task is not closed')
    anchor=source.execute('SELECT dataset,record_id FROM membership WHERE mid=? ORDER BY dataset,record_id LIMIT 1',(mid,)).fetchone()
    if anchor is None:raise ValueError('Existing geometry has no original source membership')
    return anchor,row[1]

def prepare(a):
    root=a.root;folder=root/'directive19/uniform_Sprime/geometry/shared_v1'
    if folder.exists():raise FileExistsError('Preserve existing uniform-scope queue')
    joint_capacity(root,a.quota_snapshot,1073741824)
    progress=json.loads((root/'progress_20261119_03.json').read_text())
    nmr=json.loads((root/'directive19/NMR2018/job_4536887/manifest.json').read_text())
    specs=[(group,json.loads(Path(progress['domains'][group]['manifest']).read_text())['records'])
           for group in ('C7H10O2','PPE1694')]
    specs.append(('NMRShiftDB2_2018',nmr['records']))
    original=root/'geometry/shared_v1/queue.sqlite'
    access=check_access(original)
    if not access or not access.get('immutable'):raise ValueError('Original shared geometry must be sealed')
    source=sqlite3.connect(original.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    folder.mkdir(parents=True)
    path=folder/'queue.sqlite';db=sqlite3.connect(path)
    geometry_queue.schema(db)
    db.execute('INSERT INTO metadata VALUES (?,?)',('ready','false'))
    recipe=source.execute("SELECT value FROM metadata WHERE key='recipe'").fetchone()
    if recipe is None:raise ValueError('Original UFF scientific recipe unavailable')
    db.execute('INSERT INTO metadata VALUES (?,?)',('recipe',recipe[0]))
    binding_path=folder/'geometry_bindings.parquet'
    binding_schema=pa.schema([('dataset',pa.string()),('record_id',pa.string()),('mid',pa.string()),
        ('model_atom_to_source',pa.list_(pa.int64())),('shared_geometry_queue',pa.string()),
        ('shared_geometry_dataset',pa.string()),('shared_geometry_record_id',pa.string()),
        ('reused_closed_source',pa.bool_()),('original_state',pa.string())])
    counts=Counter();per_group={};new_unique=set()
    try:
        with pq.ParquetWriter(binding_path,binding_schema,compression='zstd') as writer:
            for group,records in specs:
                local=Counter()
                for batch in pq.ParquetFile(records).iter_batches(batch_size=2048,
                        columns=['dataset','record_id','model_smiles','model_atom_to_source','domain_eligible']):
                    bindings=[]
                    for row in batch.to_pylist():
                        local['source_rows']+=1
                        if not row['domain_eligible']:
                            local['domain_ineligible_or_unresolved']+=1;continue
                        mid,_=identities(row['model_smiles'])
                        route=source_route(source,mid,row['model_smiles'])
                        if route is not None:
                            (dataset,rid),state=route;queue=str(original)
                            local['records_reusing_closed_source']+=1
                        else:
                            dataset,rid=row['dataset'],row['record_id'];queue=str(path);state='PENDING'
                            db.execute('INSERT OR IGNORE INTO tasks(mid,model_smiles) VALUES (?,?)',(mid,row['model_smiles']))
                            db.execute('INSERT INTO membership VALUES (?,?,?,?)',
                                (dataset,rid,mid,json.dumps(row['model_atom_to_source'])))
                            new_unique.add(mid);local['records_bound_to_new_geometry']+=1
                        bindings.append(dict(dataset=row['dataset'],record_id=row['record_id'],mid=mid,
                            model_atom_to_source=row['model_atom_to_source'],shared_geometry_queue=queue,
                            shared_geometry_dataset=dataset,shared_geometry_record_id=rid,
                            reused_closed_source=route is not None,original_state=state))
                    future=max(2147483648,len(new_unique)*400000+path.stat().st_size)
                    joint_capacity(root,a.quota_snapshot,future)
                    db.commit()
                    if bindings:writer.write_table(pa.Table.from_pylist(bindings,schema=binding_schema))
                per_group[group]=dict(local);counts.update(local)
                print('UNIFORM_SPRIME_SCOPE_GROUP',group,dict(local),flush=True)
        forecast=max(2147483648,len(new_unique)*400000+path.stat().st_size)
        joint_capacity(root,a.quota_snapshot,forecast)
        db.execute('INSERT INTO metadata VALUES (?,?)',('storage_forecast_bytes',str(forecast)))
        db.execute("UPDATE metadata SET value='true' WHERE key='ready'");db.commit()
    finally:db.close();source.close()
    manifest=dict(status='UNIFORM_SPRIME_INPUTS_PREPARED_NEW_GEOMETRY_NOT_COMPUTED',
        queue=str(path),geometry_bindings=str(binding_path),source_groups=per_group,counts=dict(counts),
        unique_new_ordered_model_smiles=len(new_unique),storage_forecast_bytes=forecast,
        future_new_Pprime_forecast_bytes=NEW_PPRIME_FORECAST,peer_environment_reserve_bytes=PEER_ENVIRONMENT_RESERVE,
        reused_source_queue=str(original),source_geometry_copied=False,
        scientific_failures_retried=False,original_reference_coordinates_used_as_UFF=False,
        source_targets_or_historical_reference_outputs_changed=False,
        reader='workflows.benchmark_data.shared_reader.SharedB0Reader',
        binding_contract='Open shared_geometry_queue and get(shared_geometry_dataset,shared_geometry_record_id); apply target row model_atom_to_source',
        UFF_geometry_ready=False,Pprime_ready=False,
        independent_numeric_readback=False,new_data_content_hashes=False)
    (folder/'queue.manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    publish(folder/'access.json',dict(producer_job=os.environ['SLURM_JOB_ID'],
        producer_node=os.uname().nodename.split('.')[0],cross_node_read_allowed=True,
        immutable=False,writers_closed=True,prepared_not_computed=True,database_copy_created=False))
    print('UNIFORM_SPRIME_SCOPE_PREPARED',folder/'queue.manifest.json',len(new_unique),flush=True)

def run(a):
    folder=a.queue.parent
    def protect(path,needed,snapshot,own_concurrent_bytes=1073741824):
        joint_capacity(a.root,snapshot,needed+own_concurrent_bytes)
    geometry_queue.protect=protect
    protect(folder,67108864,a.quota_snapshot)
    publish(folder/'access.json',dict(producer_job=os.environ['SLURM_JOB_ID'],
        producer_node=os.uname().nodename.split('.')[0],cross_node_read_allowed=False,
        immutable=False,writers_closed=False,database_copy_created=False))
    geometry_queue.run(a)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('command',choices=['prepare','run'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--quota-snapshot',type=Path,required=True)
    p.add_argument('--queue',type=Path)
    p.add_argument('--workers',type=int,default=8)
    a=p.parse_args()
    if a.command=='run' and a.queue is None:p.error('--queue required for run')
    (prepare if a.command=='prepare' else run)(a)

if __name__=='__main__':main()
