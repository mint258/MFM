"""Chunked immutable-source UFF3 runtime; one allocation can process all 2.5M.

Root supplies the frozen R/N source manifest, actual resource plan and fresh
shared quota publisher. This runner has no application wall/repair/failure-count
timeout, no 1024-molecule-parent limit and no scientific retry. Resume adopts
closed per-molecule results and completed family batches only.
"""
from __future__ import annotations
import argparse
import collections
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import random
import socket
import sqlite3
import stat
import time
import uuid
from . import core as C, store as S
from .resources import Budget

WORK=None
LAST_WORKER_GUARD=0.0


def verify(ref):
    from workflows.expansion.portable_sources_v1.transport import verify as check
    return check(ref)


def guard(plan):
    from workflows.expansion.portable_sources_v1.transport import bind_plan
    profile=bind_plan(plan)
    if profile is not None and not plan.get('source_capsule_reference'):
        raise RuntimeError('ALPHA_REQUIRES_REAL_RELOCATED_SOURCE_CAPSULE_BEFORE_ANY_MOLECULE_CLAIM')
    uid=os.getuid();node=socket.gethostname().split('.')[0]
    cpus=int(os.environ.get('SLURM_CPUS_PER_TASK','0'))
    workers=plan['workers']
    if plan['schema']!='PUBCHEM_UFF3_ALLOCATION_PLAN_V1':
        raise RuntimeError('EXACT_UFF3_ALLOCATION_PLAN_SCHEMA')
    policy=S.read_json(verify(plan['user_policy']))
    if (policy['schema']!='pubchem_expansion_completion_user_policy_v1'
            or policy['target_batch_molecules']!=2500000
            or policy['conformers']['max_generated_per_molecule']!=3
            or policy['conformers']['fill'] is not False
            or policy['conformers']['retry'] is not False
            or policy['labels']['Pprime'] is not False
            or policy['labels']['QM'] is not False):
        raise RuntimeError('ACTUAL_CURRENT_USER_MAX3_POLICY_REQUIRED')
    if ((profile is None and (uid!=1278 or node=='sonmi')) or not os.environ.get('SLURM_JOB_ID')
            or type(workers)is not int or workers<16 or cpus<workers
            or node not in plan['allowed_nodes']):
        raise RuntimeError('ACTUAL_MAIN_ALLOCATED_CPU_WORKERS_REQUIRED')
    if plan['maximum_conformers']!=3 or plan['no_fill'] is not True or plan['no_retry'] is not True:
        raise RuntimeError('CURRENT_USER_MAX3_NO_FILL_NO_RETRY_POLICY')
    raw=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    return {'hostname':socket.gethostname(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'start_ticks':int(raw[19]),'uid':uid,'node':node,'endpoint':profile['endpoint'] if profile else '202.38.247.57:22','job_id':os.environ['SLURM_JOB_ID'],
            'allocated_cpus':cpus,'workers':workers,'pid':os.getpid()}


def source_rows(manifest):
    for ref in manifest['source_parts']:
        path=Path(ref['path'])
        count=0
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            before=os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_uid!=os.getuid() or before.st_size!=ref['bytes']:
                raise RuntimeError('OWN_SAME_SIZE_REGULAR_SOURCE_FD_REQUIRED')
            for line in stream:
                digest.update(line)
                row=json.loads(line);C.source_identity(row);count+=1;yield row
            after=os.fstat(stream.fileno());current=path.lstat()
            stamp=lambda value:(value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,value.st_uid)
            if stamp(before)!=stamp(after) or stamp(before)!=stamp(current) or digest.hexdigest()!=ref['sha256']:
                raise RuntimeError('SOURCE_PART_CHANGED_OR_WHOLE_SHA_DIFFERS')
        if count!=ref['rows']:raise RuntimeError('SOURCE_PART_ROW_COUNT_CHANGED')


def ranking_parents(manifest):
    """The source is the actual released batch1, not just 2.5M well-formed rows."""
    rank=S.read_json(verify(manifest['ranking_receipt']))
    filtered=S.read_json(verify(rank['filtered_pool']))
    novelty=S.read_json(verify(rank['novelty_receipt']))
    from workflows.expansion.uff3_alpha_runtime_v1.ordered_contract import complete
    complete(rank,filtered,novelty)
    if (rank['schema']!='expansion_nested_queues_v1' or rank['seed']!=20261025
            or rank['queue_molecules_each']!=5000000 or rank['first_batch_molecules_each']!=1250000
            or rank['downstream_features_used'] is not False):
        raise RuntimeError('TRUE_FROZEN_TEN_MILLION_ORDER_FIRST_2P5M')
    return rank


def open_index(root, manifest, manifest_reference, budget):
    """Validate the full 2.5M source census before the first native call."""
    db=sqlite3.connect(root/'index.sqlite',timeout=120)
    db.executescript('''PRAGMA journal_mode=DELETE;
      CREATE TABLE IF NOT EXISTS source(ordinal INTEGER PRIMARY KEY,mid TEXT UNIQUE,cid INTEGER UNIQUE,
        full_key TEXT UNIQUE,stream TEXT,stream_rank INTEGER,body TEXT,UNIQUE(stream,stream_rank));
      CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
      CREATE TABLE IF NOT EXISTS done(ordinal INTEGER PRIMARY KEY,manifest TEXT,batch_manifest TEXT,status TEXT);
      CREATE TABLE IF NOT EXISTS batches(path TEXT PRIMARY KEY,body TEXT);
    ''')
    pinned=C.sha(C.canonical(manifest_reference))
    old=db.execute("SELECT value FROM meta WHERE key='source_manifest_sha'").fetchone()
    if old and old[0]!=pinned:raise RuntimeError('RESUME_SOURCE_MANIFEST_CHANGED')
    closed=db.execute("SELECT value FROM meta WHERE key='source_census_complete'").fetchone()
    if not closed:
        # This is metadata reconstruction only. No native work can have begun
        # until source_census_complete is committed, so partial census may be
        # rebuilt without retrying any scientific calculation.
        if db.execute('SELECT count(*) FROM done').fetchone()[0]:raise RuntimeError('SCIENCE_WITHOUT_CLOSED_SOURCE_CENSUS')
        db.execute('DELETE FROM source');db.commit()
        counts=collections.Counter()
        for ordinal,row in enumerate(source_rows(manifest)):
            counts[row['stream']]+=1
            db.execute('INSERT INTO source VALUES(?,?,?,?,?,?,?)',(ordinal,C.molecule_id(row),row['cid'],
                row['full_key'],row['stream'],row['stream_rank'],C.canonical(row).decode()))
            if ordinal%10000==9999:db.commit();budget.register(root/'index.sqlite');budget.check()
        expected=manifest['molecules']
        if expected!=2500000 or counts!={'R':1250000,'N':1250000}:raise RuntimeError('TRUE_FULL_2P5M_SOURCE_CENSUS_REQUIRED')
        for stream in ('R','N'):
            n,lo,hi=db.execute('SELECT count(*),min(stream_rank),max(stream_rank) FROM source WHERE stream=?',(stream,)).fetchone()
            if (n,lo,hi)!=(1250000,1,1250000):raise RuntimeError('EXACT_R_N_FROZEN_RANKS_REQUIRED')
        import pyarrow.parquet as pq
        rank=ranking_parents(manifest)
        batch1=verify(rank['batch1'])
        db.execute('CREATE TEMP TABLE ranked(cid INTEGER,full_key TEXT,stream TEXT,stream_rank INTEGER,UNIQUE(stream,stream_rank))')
        for batch in pq.ParquetFile(batch1).iter_batches(batch_size=10000,columns=['cid','full_key','stream','stream_rank']):
            db.executemany('INSERT INTO ranked VALUES(?,?,?,?)',
                ((row['cid'],row['full_key'],row['stream'],row['stream_rank']) for row in batch.to_pylist()))
        expected_rows=db.execute('SELECT count(*) FROM ranked').fetchone()[0]
        missing=db.execute('SELECT count(*) FROM (SELECT cid,full_key,stream,stream_rank FROM ranked EXCEPT SELECT cid,full_key,stream,stream_rank FROM source)').fetchone()[0]
        extra=db.execute('SELECT count(*) FROM (SELECT cid,full_key,stream,stream_rank FROM source EXCEPT SELECT cid,full_key,stream,stream_rank FROM ranked)').fetchone()[0]
        if expected_rows!=2500000 or missing or extra:raise RuntimeError('SOURCE_NOT_EXACT_FROZEN_BATCH1_IDENTITY_AND_RANK')
        db.execute("INSERT OR REPLACE INTO meta VALUES('source_manifest_sha',?)",(pinned,))
        db.execute("INSERT OR REPLACE INTO meta VALUES('source_census_complete','true')");db.commit()
    elif db.execute('SELECT count(*) FROM source').fetchone()[0]!=2500000:
        raise RuntimeError('CLOSED_SOURCE_CENSUS_COUNT_CHANGED')
    return db


def init_worker(plan, output):
    global WORK
    from workflows.expansion.portable_sources_v1.transport import bind_plan
    bind_plan(plan)
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[name]='1'
    if plan.get('source_capsule_reference'):
        from workflows.expansion.portable_sources_v1.kernel import get_capsule
        get_capsule(plan['source_capsule_reference']).load()
    WORK=(plan,Path(output))


def worker_guard():
    """Observe actual RSS/MemAvailable between calls; never kill a native call."""
    global LAST_WORKER_GUARD
    now=time.monotonic()
    if now-LAST_WORKER_GUARD<5:return
    plan,_=WORK
    rss=int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
    available=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    if rss>plan.get('worker_rss_soft_cap_bytes',8<<30) or available<plan.get('minimum_node_available_bytes',4<<30):
        raise RuntimeError('ACTUAL_MEMORY_SAFETY_STOP_RETAIN_PARTIAL_NO_SCIENTIFIC_RETRY')
    LAST_WORKER_GUARD=now


def worker(item):
    ordinal,body=item;plan,root=WORK;source=json.loads(body)
    identity=C.source_identity(source);directory=root/'molecules'/identity[:2]/identity
    manifest_path=directory/'manifest.json'
    if manifest_path.exists():
        manifest=S.read_json(manifest_path)
        if manifest['source_identity_sha256']!=identity or manifest['recipe_sha256']!=C.recipe_sha():
            raise RuntimeError('CLOSED_MOLECULE_SOURCE_OR_RECIPE_CHANGED')
        for name in ('candidate_cache','selected_packet','events'):verify(manifest[name])
        C.validate_cache(S.read_json(manifest['candidate_cache']['path']),source)
        return ordinal,S.reference(manifest_path),os.getpid(),True
    if directory.exists():
        # Crash-interrupted scientific work remains UNKNOWN. Do not erase its
        # intent or reopen its optimizer under the same or a new seed.
        missing={'schema':'PUBCHEM_UFF3_INTERRUPTED_MOLECULE_V1','source':source,
            'state':'INTERRUPTED_NO_AUTOMATIC_SCIENCE_RETRY','source_identity_sha256':identity,
            'output_directory':str(directory),'actual_conformers':None,'training_eligible':False}
        path=root/'interrupted'/(str(ordinal)+'.json')
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():S.write_new(path,missing)
        return ordinal,S.reference(path),os.getpid(),True
    kernel=None
    if plan.get('source_capsule_reference'):
        from .native import NativeKernel
        kernel=NativeKernel(plan['source_capsule_reference'])
    manifest=S.run_one(source,directory,kernel=kernel,checkpoint=worker_guard,
        maximum_molecule_output_bytes=plan.get('maximum_molecule_output_bytes',64<<20))
    if manifest.get('source_contract_hold') or 'ACTUAL_MEMORY_SAFETY_STOP' in (manifest.get('error') or ''):
        raise RuntimeError('CLOSED_PARTIAL_RETAINED_STOP_NEW_DISPATCH:'+str(manifest.get('error')))
    return ordinal,S.reference(directory/'manifest.json'),os.getpid(),False


def load_packet(manifest_reference, job_id):
    m=S.read_json(verify(manifest_reference))
    if m['schema']=='PUBCHEM_UFF3_INTERRUPTED_MOLECULE_V1':
        source=m['source']
        packet={'source':source,'molecule_id':C.molecule_id(source),'producer_job_id':job_id,
            'once_key':C.sha(C.canonical([C.recipe_sha(),C.source_identity(source)])),
            'candidate_cache_sha256':None,'D20':None,'atomic_numbers':[],
            'atom_order_sha256':None,'conformers':[],
            'orders':{'fixed_random':[],'energy':[],'diversity':[]},
            'requested_conformers':3,'generation_count_unknown':True,
            'state':m['state'],'error':'Interrupted original outputs retained; no scientific retry',
            'seed':C.seed_for(C.molecule_id(source))}
        return (manifest_reference,packet),m
    packet=S.read_json(verify(m['selected_packet']))
    source=packet['source']
    cache=S.read_json(verify(m['candidate_cache']));C.validate_cache(cache,source)
    # Runtime provenance is a derived family annotation. The original packet
    # remains immutable; its physical SHA is carried separately in every row.
    packet['producer_job_id']=m.get('producer_job_id',job_id)
    packet['once_key']=C.sha(C.canonical([C.recipe_sha(),C.source_identity(source)]))
    packet['error']=cache.get('error')
    return (m['selected_packet'],packet),m


def register_molecule_outputs(budget,manifest_reference):
    path=Path(manifest_reference['path'])
    budget.register(path.parent if path.name=='manifest.json' else path)
    if path.name!='manifest.json':
        value=S.read_json(path)
        if value.get('schema')=='PUBCHEM_UFF3_INTERRUPTED_MOLECULE_V1':
            budget.register(Path(value['output_directory']))


def progress(root,runtime,mode,completed,initial_closed,expected,closed_now):
    value={'schema':'PUBCHEM_UFF3_MUTABLE_PROGRESS_V1','runtime':runtime,'mode':mode,
        'observed_unix_seconds':time.time(),'new_worker_results':completed,
        'initial_closed_family_molecules':initial_closed,
        'new_closed_family_molecules':closed_now,
        'closed_family_molecules':initial_closed+closed_now,
        'expected_scope_molecules':expected,'final_scientific_acceptance':False}
    temporary=root/('current_progress.pending.'+uuid.uuid4().hex+'.json')
    S.write_new(temporary,value)
    os.replace(temporary,root/'current_progress.json')


def recover_batches(db,root,budget):
    for path in (root/'families').glob('*/manifest.json'):
        if db.execute('SELECT 1 FROM batches WHERE path=?',(str(path),)).fetchone():continue
        value=S.read_json(path)
        for ref in value['family_files']:verify({k:ref[k] for k in ('path','bytes','sha256')})
        for item in value['molecules']:
            verify(item['manifest'])
            register_molecule_outputs(budget,item['manifest'])
            db.execute('INSERT OR IGNORE INTO done VALUES(?,?,?,?)',(item['ordinal'],C.canonical(item['manifest']).decode(),str(path),item['state']))
        budget.register(path.parent)
        db.execute('INSERT INTO batches VALUES(?,?)',(str(path),C.canonical(value).decode()));db.commit()


def write_batch(results,db,root,budget,plan,job_id):
    from . import families
    families.set_capsule(plan.get('source_capsule_reference'))
    folder=root/'families'/('job'+str(job_id)+'_'+uuid.uuid4().hex)
    folder.mkdir(parents=True,exist_ok=False)
    items=[];census=[];cache_refs=[]
    for ordinal,ref,pid,reused in results:
        item,manifest=load_packet(ref,job_id)
        if item is not None:
            items.append(item)
            if manifest.get('candidate_cache'):cache_refs.append(manifest['candidate_cache'])
        census.append({'ordinal':ordinal,'manifest':ref,'state':manifest['state'],'worker_pid':pid,'closed_reused':reused})
        register_molecule_outputs(budget,ref)
    files=families.export_packets(items,folder,budget,job_id) if items else []
    quality=plan.get('quality_reference_review')
    if quality is not None and items:
        review=S.read_json(verify(quality))
        masks=families.export_masks(items,folder,budget,review)
        if masks:files.append(masks)
    value={'schema':'PUBCHEM_UFF3_CLOSED_FAMILY_BATCH_V1','molecules':census,
        'family_files':files,'candidate_cache_references':cache_refs,
        'maximum_delivered_conformers':3,'quality_reference_review':quality,
        'full_population_mask_rate_and_robust_review_complete':False}
    S.write_new(folder/'manifest.json',value);budget.register(folder);budget.check(True)
    for row in census:db.execute('INSERT INTO done VALUES(?,?,?,?)',(row['ordinal'],C.canonical(row['manifest']).decode(),str(folder/'manifest.json'),row['state']))
    db.execute('INSERT INTO batches VALUES(?,?)',(str(folder/'manifest.json'),C.canonical(value).decode()));db.commit()
    return value


def run(plan):
    import fcntl
    runtime=guard(plan)
    manifest_reference=plan['source_manifest'];manifest=S.read_json(verify(manifest_reference))
    if manifest['schema']!='PUBCHEM_UFF3_ORDERED_SOURCE_MANIFEST_V1' or manifest['molecules']!=2500000:
        raise RuntimeError('EXACT_IMMUTABLE_ORDERED_SOURCE_MANIFEST')
    root=Path(plan['output_directory'])
    if runtime['endpoint']=='218.192.171.238:22':
        base=Path('/gfshome/alpha')
        if root!=Path(plan['output_scope_root']):
            raise RuntimeError('ALPHA_UFF_STAGE_MUST_EQUAL_ACTUAL_PRIVATE_ACCOUNTED_SCOPE')
    else:
        base=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion')
    if not root.is_absolute() or base not in root.parents or any(path.is_symlink() for path in (root,*root.parents)):
        raise RuntimeError('OWN_LITERAL_EXTERNAL_EXPANSION_OUTPUT_DIRECTORY_REQUIRED')
    root.mkdir(parents=True,exist_ok=True)
    parent_lock=(root/'parent.lock').open('a+b')
    try:fcntl.flock(parent_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        parent_lock.close()
        raise RuntimeError('OWN_OUTPUT_ALREADY_HAS_LIVE_PARENT_NO_DUPLICATE_DISPATCH')
    budget=Budget(plan,root,parent_lock=parent_lock);db=open_index(root,manifest,manifest_reference,budget)
    recover_batches(db,root,budget)
    shard=plan.get('shard_index',0);shards=plan.get('shard_count',1)
    if not (type(shard)is int and type(shards)is int and 0<=shard<shards):raise RuntimeError('INVALID_EXCLUSIVE_SHARD')
    mode=plan.get('mode','full')
    if mode not in ('pilot','full'):raise RuntimeError('PILOT_OR_FULL_MODE_REQUIRED')
    db.execute('CREATE TEMP TABLE selected(ordinal INTEGER PRIMARY KEY)')
    if mode=='pilot':
        if shards!=1:raise RuntimeError('THE_10K_PILOT_IS_ONE_FROZEN_R_N_SAMPLE')
        rng=random.Random(20261025)
        for stream in ('R','N'):
            for rank in rng.sample(range(1,1250001),5000):
                row=db.execute('SELECT ordinal FROM source WHERE stream=? AND stream_rank=?',(stream,rank)).fetchone()
                if row is None:raise RuntimeError('FROZEN_PILOT_RANK_MISSING')
                db.execute('INSERT INTO selected VALUES(?)',row)
    else:
        db.execute('INSERT INTO selected SELECT ordinal FROM source WHERE ordinal % ?=?',(shards,shard))
    expected=db.execute('SELECT count(*) FROM selected').fetchone()[0]
    initial_closed=db.execute('SELECT count(*) FROM done WHERE ordinal IN(SELECT ordinal FROM selected)').fetchone()[0]
    closed_now=0
    progress(root,runtime,mode,0,initial_closed,expected,closed_now)
    budget.register(root/'current_progress.json')
    start=time.monotonic();pids=set();failure=None;completed=0;batch=[]
    query='SELECT ordinal,body FROM source WHERE ordinal IN(SELECT ordinal FROM selected) AND ordinal NOT IN(SELECT ordinal FROM done) ORDER BY ordinal'
    rows=db.execute(query)
    waiting=collections.deque();limit=2*plan['workers']
    try:
        with ProcessPoolExecutor(max_workers=plan['workers'],mp_context=multiprocessing.get_context('spawn'),
            initializer=init_worker,initargs=(plan,str(root))) as pool:
            for item in rows:
                budget.check()
                budget.require_dispatch_capacity()
                waiting.append(pool.submit(worker,item))
                if len(waiting)>=limit:
                    result=waiting.popleft().result();pids.add(result[2]);register_molecule_outputs(budget,result[1]);batch.append(result);completed+=1
                    if len(batch)>=plan.get('family_batch_molecules',64):
                        write_batch(batch,db,root,budget,plan,runtime['job_id']);closed_now+=len(batch);batch=[]
                        progress(root,runtime,mode,completed,initial_closed,expected,closed_now)
            while waiting:
                result=waiting.popleft().result();pids.add(result[2]);register_molecule_outputs(budget,result[1]);batch.append(result);completed+=1
                if len(batch)>=plan.get('family_batch_molecules',64):
                    write_batch(batch,db,root,budget,plan,runtime['job_id']);closed_now+=len(batch);batch=[]
                    progress(root,runtime,mode,completed,initial_closed,expected,closed_now)
            if batch:
                write_batch(batch,db,root,budget,plan,runtime['job_id']);closed_now+=len(batch);batch=[]
                progress(root,runtime,mode,completed,initial_closed,expected,closed_now)
    except Exception as exc:
        # Workers naturally finish current molecule. Their closed packets are
        # adopted on continuation; no optimizer is forcibly interrupted here.
        failure=type(exc).__name__+': '+str(exc)
    expected=db.execute('SELECT count(*) FROM selected').fetchone()[0]
    actual=db.execute('SELECT count(*) FROM done WHERE ordinal IN(SELECT ordinal FROM selected)').fetchone()[0]
    statuses=dict(db.execute('SELECT status,count(*) FROM done WHERE ordinal IN(SELECT ordinal FROM selected) GROUP BY status'))
    closed_ledger=budget.seal_ledger()
    receipt={'schema':'PUBCHEM_UFF3_ALLOCATION_RECEIPT_V1','runtime':runtime,'source_manifest':manifest_reference,
        'recipe_sha256':C.recipe_sha(),'mode':mode,'shard_index':shard,'shard_count':shards,'expected_molecules':expected,
        'closed_family_export_molecules':actual,'state_counts':statuses,'newly_completed_workers':completed,
        'actual_worker_pids':sorted(pids),'source_total_molecules':2500000,'maximum_conformers':3,
        'status':('COMPLETE_CANDIDATE_PILOT_NOT_TRAINING_RELEASE' if mode=='pilot' else 'COMPLETE_CANDIDATE_SHARD_NOT_TRAINING_RELEASE') if actual==expected and failure is None else 'PARTIAL_RETAINED_NO_SCIENTIFIC_RETRY',
        'failure':failure,'wall_seconds':time.monotonic()-start,'last_resource_observation':budget.latest,
        'quality_reference_review':plan.get('quality_reference_review'),'full_population_1p5_scan_complete':False,
        'output_accounting_rebuild':budget.ledger_rebuild,'closed_ledger':closed_ledger,
        'source_capsule_reference':plan.get('source_capsule_reference'),'parent_transport_manifest':plan.get('parent_transport_manifest'),
        'execution_metadata':{k:plan.get(k)for k in('original_launcher_plan_reference','original_startup_proof_reference','_derived_runtime_plan_reference')},
        'training_eligible':False,'new_QM_calls':0,'batch_manifest_index':'index.sqlite:batches'}
    path=root/('receipt_job'+runtime['job_id']+'_'+uuid.uuid4().hex+'.json');S.write_new(path,receipt)
    db.close();parent_lock.close();return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);args=p.parse_args()
    result=run(S.read_json(args.plan));print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status'].startswith('COMPLETE_CANDIDATE_') else 3


if __name__=='__main__':raise SystemExit(main())
