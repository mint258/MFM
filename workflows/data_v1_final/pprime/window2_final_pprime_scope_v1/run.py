"""General final-scope P-prime producer, sharing the unchanged twelve-task engine.

Closed QC is reused. A durable Native intent is never automatically retried.
The running historical window2_fill_v1 module is imported without modification.
"""
from __future__ import annotations
import argparse,collections,concurrent.futures as cf,json,multiprocessing as mp,os,sqlite3,sys,types
from pathlib import Path
from .prepare import read,save,info,need,key,record_id
O=None

def initialize(plan):
    global O
    from ..window2_fill_v1 import run as original
    O=original;O.initialize(plan)
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)

def checked_conformer(row,native):
    """Use existing order witness or compare the actual source ordered Z.

    The latter reuses the native reader's original witness after equality; it
    never computes a new atom-order digest or infers correspondence by geometry.
    """
    raw=json.loads(row['physical_geometry_json'])
    need(raw.get('source_record_id')==row['native_anchor_record_id'],'PHYSICAL_NATIVE_ANCHOR_CHANGED')
    need(raw.get('molecule_id',row['molecule_id'])==row['molecule_id'],'PHYSICAL_MID_CHANGED')
    need(raw.get('sprime_conf_idx')==row['original_sprime_conf_idx'],'ACTUAL_SOURCE_PHYSICAL_ID_CHANGED')
    need(raw['status']=='SUCCESS' and raw['converged'] is True,'ACTUAL_GEOMETRY_NOT_USABLE')
    numbers=raw.get('atomic_numbers',raw.get('z'))
    if numbers is not None:
        need([int(v) for v in numbers]==[int(v) for v in native['z']],'ACTUAL_GEOMETRY_NATIVE_ORDERED_Z_DIFFERS')
        need(len(numbers)==len(raw['coordinates']),'ATOM_COORDINATE_COUNT_DIFFERS')
    witness=raw.get('atom_order_sha256')
    if witness:need(witness==native['native_atom_order_sha256'],'EXISTING_ATOM_ORDER_WITNESS_DIFFERS')
    else:
        need(numbers is not None,'NO_EXISTING_WITNESS_OR_ACTUAL_Z')
        raw['atom_order_sha256']=native['native_atom_order_sha256']
    return dict(raw,sprime_conf_idx=int(row['sprime_conf_idx']))

def compute(row,sink,context):
    """Cache the one original native read for compute_pair's normal read seam."""
    import hashlib,struct
    source=json.loads(row['native_source_json'])
    source.update(effective_role=row['effective_role'],source_role=row['source_role'],
        file_group=int(row['file_group']),size_stratum=row['size_stratum'])
    need(source['molecule_id']==row['molecule_id'] and source['record_id']==row['native_anchor_record_id'],'NATIVE_SOURCE_PHYSICAL_ALIGNMENT')
    native=O.ENGINE.NATIVE.read_native(source);conformer=checked_conformer(row,native)
    # Same coordinate digest used by the original adapter at its geometry
    # boundary. This is not a new source-file/content-hash delivery pass.
    xyz=conformer['coordinates'];flat=[float(v) for point in xyz for v in point]
    coordinate=hashlib.sha256(struct.pack('<'+'d'*len(flat),*flat)).hexdigest()
    pair={'record_id':row['record_id'],'molecule_id':row['molecule_id'],
        'random_order_rank':int(row['random_order_rank']),'geometry_source':'uff_sprime',
        'canonical_geometry_id':row['geometry_id'],'source':source,'conformer':conformer,
        'uff_coordinate_sha256':coordinate}
    if conformer.get('geometry_sha256'):pair['uff_geometry_sha256']=conformer['geometry_sha256']
    reader=O.ENGINE.NATIVE.read_native
    def cached(value):
        need(value==source,'ORIGINAL_NATIVE_READ_SOURCE_CHANGED');return native
    O.ENGINE.NATIVE.read_native=cached
    try:return O.COMPUTE(O.ENGINE,pair,sink,context)
    finally:O.ENGINE.NATIVE.read_native=reader

def batch_work(task):
    number,rows,output=task;folder=Path(output)/('batch_%06d'%number);folder.mkdir(exist_ok=False)
    sink=O.RawSink(folder/'raw_outputs.sqlite',O.ENGINE.OUTPUT_ARCHIVE,sys.maxsize)
    records=[];outcomes=[];success=0
    try:
        for row in rows:
            outcome={'record_id':row['record_id'],'molecule_id':row['molecule_id'],'sprime_conf_idx':row['sprime_conf_idx']}
            try:
                record=compute(row,sink,{'job_id':int(os.environ['SLURM_JOB_ID']),'lane':number,'pprime_reproduction_manifest_sha256':O.ENGINE.PACKAGE_SHA})
                need(len(record['tasks'])==12 and len({x['task'] for x in record['tasks']})==12,'TWELVE_ORIGINAL_TASK_ALIGNMENT')
                record['lane']=number;records.append(record)
                success+=int(all(x['scope_status']=='SUCCESS' for x in record['tasks']))
                outcome['status']='CLOSED_TWELVE_OUTCOMES'
            except Exception as exc:
                outcome.update(status='UNKNOWN_OR_UNRESOLVED_NO_AUTOMATIC_NATIVE_RETRY',error=repr(exc))
            outcomes.append(outcome)
    finally:sink.close()
    files=[]
    if records:files,_=O.producer_export(O.ENGINE,records,folder/'families')
    outcome_path=folder/'record_outcomes.json';save(outcome_path,outcomes)
    result={'batch':number,'assigned':len(rows),'completed':len(records),'all12_success':success,
        'record_outcomes':info(outcome_path,len(outcomes)),'files':files,'raw_outputs':info(folder/'raw_outputs.sqlite')}
    save(folder/'checkpoint.json',result)
    print(json.dumps({'batch':number,'closed_outcomes':len(records),'unresolved':len(rows)-len(records)}),flush=True)
    return result

def recover(db,out):
    """Only durable completed publication checkpoints may close an intent."""
    for filename in sorted(out.glob('batch_*/checkpoint.json')):
        batch=read(filename)
        for row in read(batch['record_outcomes']):
            db.execute('UPDATE claims SET status=? WHERE molecule_id=? AND sprime_conf_idx=?',
                (row['status'],row['molecule_id'],row['sprime_conf_idx']))
    db.commit()

def run(plan):
    import pyarrow.parquet as pq
    need(os.getuid()==1278 and bool(os.environ.get('SLURM_JOB_ID')),'MAIN_REAL_SLURM_ALLOCATION_REQUIRED')
    scope=read(plan['scope']);need(scope['schema']=='PPRIME_FINAL_PHYSICAL_FIRST2_CONTINUATION_SCOPE_V1','FINAL_GENERAL_PHYSICAL_SCOPE_REQUIRED')
    out=Path(plan['output']);out.mkdir(parents=True,exist_ok=True)
    lock=os.open(out/'producer.lock',os.O_RDWR|os.O_CREAT,0o600)
    import fcntl
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    db=sqlite3.connect(out/'claims.sqlite')
    db.execute('''CREATE TABLE IF NOT EXISTS claims(record_id TEXT UNIQUE,molecule_id TEXT,
        sprime_conf_idx INTEGER,batch INTEGER,status TEXT,PRIMARY KEY(molecule_id,sprime_conf_idx))''');db.commit()
    recover(db,out)
    db.execute("UPDATE claims SET status='UNKNOWN_NATIVE_INTENT_WITHOUT_CLOSED_QC' WHERE status='NATIVE_INTENT'")
    db.commit();cpus=int(os.environ.get('SLURM_CPUS_PER_TASK','16'))
    number=max([int(folder.name.split('_')[1]) for folder in out.glob('batch_*') if folder.is_dir()]+[-1])+1
    pending={};buffer=[];seen=set();assigned=0
    try:
        with cf.ProcessPoolExecutor(cpus,mp_context=mp.get_context('spawn'),initializer=initialize,initargs=(plan,)) as pool:
            def settle(wait=False):
                if not pending:return
                done,_=cf.wait(pending,return_when=cf.FIRST_COMPLETED if wait else cf.ALL_COMPLETED,timeout=None if wait else 0)
                for future in done:
                    pending.pop(future);result=future.result()
                    for row in read(result['record_outcomes']):
                        db.execute('UPDATE claims SET status=? WHERE molecule_id=? AND sprime_conf_idx=?',(row['status'],row['molecule_id'],row['sprime_conf_idx']))
                    db.commit()
            def dispatch(rows,batch_number):
                nonlocal assigned
                selected=[]
                for row in rows:
                    try:db.execute('INSERT INTO claims VALUES(?,?,?,?,?)',(row['record_id'],row['molecule_id'],row['sprime_conf_idx'],batch_number,'NATIVE_INTENT'))
                    except sqlite3.IntegrityError:continue
                    selected.append(row)
                db.commit()
                if selected:
                    assigned+=len(selected);pending[pool.submit(batch_work,(batch_number,selected,str(out)))]=batch_number
            for batch in pq.ParquetFile(scope['tables']['tasks']['path']).iter_batches(batch_size=1024):
                for row in batch.to_pylist():
                    k=key(row);need(k not in seen,'DUPLICATE_FINAL_TASK_PHYSICAL_KEY');seen.add(k)
                    need(row['random_order_rank'] in (0,1),'RANK_GE_2_FORBIDDEN')
                    need(row['record_id']==record_id(k),'RECORD_KEY_PHYSICAL_ALIGNMENT')
                    if db.execute('SELECT 1 FROM claims WHERE molecule_id=? AND sprime_conf_idx=?',k).fetchone():continue
                    buffer.append(row)
                    if len(buffer)>=int(plan.get('batch_records',128)):
                        while len(pending)>=cpus:settle(True)
                        dispatch(buffer,number);number+=1;buffer=[]
                settle(False)
            if buffer:dispatch(buffer,number)
            while pending:settle(True)
        need(len(seen)==scope['needed_records'],'FINAL_SCOPE_TASK_COUNT_DIFFERS')
        batches=[read(filename) for filename in sorted(out.glob('batch_*/checkpoint.json'))]
        counts=dict(db.execute('SELECT status,count(*) FROM claims GROUP BY status'))
        unresolved=sum(count for status,count in counts.items() if status!='CLOSED_TWELVE_OUTCOMES')
        manifest={'schema':'PPRIME_FINAL_PHYSICAL_FIRST2_PRODUCER_V1',
            'status':'CLOSED_WITH_EXPLICIT_UNRESOLVED' if unresolved or scope['unknown_native_intents'] else 'COMPLETED_ALL_MISSING_PHYSICAL_RECORDS',
            'scope':plan['scope'],'records_assigned':sum(counts.values()),
            'records_completed':sum(batch['completed'] for batch in batches),'all12_success':sum(batch['all12_success'] for batch in batches),
            'claim_status_counts':counts,'prior_scope_unknown_native_intents':scope['unknown_native_intents'],
            'batches':batches,'original_native_recipe_900s_unchanged':True,'no_Pprime_rank_ge_2':True,
            'no_new_N1_generation':True,'no_automatic_native_retry':True,'independent_readback':False,
            'additional_source_or_delivery_hash_jobs':False,'actual_job_id':os.environ['SLURM_JOB_ID']}
        save(out/'manifest.json',manifest);return manifest
    finally:
        db.close();fcntl.flock(lock,fcntl.LOCK_UN);os.close(lock)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True);args=parser.parse_args()
    print(json.dumps(run(read(args.plan)),ensure_ascii=False))
