"""Terminal-only WP5 metadata reconciliation: plan first, Root-only explicit apply.
No QM/LMDB, no partial molecule splicing, no historical file deletion/rewrite.
"""
from __future__ import annotations
import argparse,concurrent.futures,hashlib,json,multiprocessing,os,socket,sqlite3,time,traceback
from collections import Counter
from pathlib import Path
from urllib.parse import quote
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
CALCS=('pm7_B','pm7_cation','pm7_anion','pm7_water','pm7_octanol','xtb_singlepoint','xtb_vipea','xtb_vfukui','xtb_ALPB_water','xtb_ALPB_octanol','xtb_fod','xtb_perturbed_gradient')
TERMINAL={'COMPLETED','FAILED','CANCELLED','NODE_FAIL','OUT_OF_MEMORY','TIMEOUT','BOOT_FAIL','DEADLINE','PREEMPTED'}
POLICY='FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT'
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def write_json(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(x,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def readonly(p):
    db=sqlite3.connect('file:'+quote(str(Path(p).resolve()))+'?mode=ro',uri=True,timeout=3,isolation_level=None)
    db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON');db.execute('PRAGMA busy_timeout=3000');return db
def row_sha(r):return sha(canonical(dict(r))) if r is not None else None
def stop_guard():
    if not (ROOT/'STOP_NEW_MOLECULES.json').exists() and not (ROOT/'control/STOP.json').exists():raise ValueError('ROOT_STOP_REQUIRED')
def node_guard():
    if os.getuid()!=1278 or not socket.gethostname().split('.')[0].startswith('compute-0-'):raise ValueError('UID1278_COMPUTE_REQUIRED')
    for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):
        if os.environ.get(k)!='1':raise ValueError('THREADS_ONE_REQUIRED:'+k)
def registered_jobs(submitted):
    d=load(submitted);rows=d.get('main',[])+d.get('cleanup',[])
    if d.get('status')!='ALL_MAIN_AND_SIX_CLEANUP_SUBMITTED' or len(rows)!=78:raise ValueError('ORIGINAL_72_PLUS_6_SUBMISSION_REQUIRED')
    jobs=[str(x['job_id']) for x in rows]
    if len(set(jobs))!=78:raise ValueError('FORMAL_IDS_NOT_UNIQUE')
    for r in rows:
        actual=load(r['receipt'])
        if str(actual['job_id'])!=str(r['job_id']) or actual['node']!=r['node']:raise ValueError('SUBMISSION_RECEIPT_BINDING_DIFFERS')
    return jobs
def terminal_proof(jobs,out):
    from wp5_accounting_v2 import run_sacct
    r=run_sacct(['-X','-n','-P','-j',','.join(sorted(jobs)),'--format=JobID,User,State'],evidence_path=Path(out)/('accounting_'+str(time.time_ns())+'.json'),wait_seconds=120)
    if r.returncode!=0:raise ValueError('ACTUAL_ACCOUNTING_UNAVAILABLE:'+r.evidence_path)
    states={}
    for line in r.stdout.splitlines():
        f=line.strip().split('|')
        if len(f)<3 or f[1]!='zixiao':raise ValueError('ACCOUNTING_USER_FORMAT_DIFFERS')
        states[f[0]]=f[2].split()[0]
    if set(states)!=set(jobs):raise ValueError('ACCOUNTING_EXACT_IDS_DIFFERS')
    return {'path':r.evidence_path,'sha256':digest(r.evidence_path),'states':states,'all_terminal':all(x in TERMINAL for x in states.values())}

def validate_payload(item,complete,options,db):
    mid=item['molecule_id'];n=item['record_count'];p=item['payload'];rec=complete['receipt'];ctx=p['context']
    if complete['wire_sha256']!=item['wire_sha256'] or complete['record_count']!=n:raise ValueError('SCI_RECEIPT_WIRE_COUNT_DIFFERS')
    if rec['molecule_id']!=mid or rec['records']!=n or rec['requested_outcomes']!=12*n or rec.get('raw_policy')!=POLICY:raise ValueError('SCI_RECEIPT_POPULATION_POLICY_DIFFERS')
    for k in ('attempt_id','job_id','task_id','lane','execution_id','reproduction_package_sha256','audit_membership_sha256'):
        if ctx.get(k)!=rec['context'].get(k):raise ValueError('SCI_CONTEXT_DIFFERS:'+k)
    if str(ctx['job_id'])!=str(options['job_id']):raise ValueError('SCI_JOB_DIFFERS')
    if options['mode']=='main' and str(ctx['task_id'])!=str(options['task_id']):raise ValueError('SCI_TASK_DIFFERS')
    if not ctx['execution_id'].startswith(options['session']+':'):raise ValueError('SCI_SESSION_DIFFERS')
    if ctx['reproduction_package_sha256']!=options['reproduction_package_sha256'] or ctx['audit_membership_sha256']!=options['audit_membership_sha256']:raise ValueError('SCI_AUTHORITY_DIFFERS')
    rows=p['population_rows'];records=p['result']['record_results'];rid=[r['record_id'] for r in rows]
    if len(rows)!=n or len(set(rid))!=n or len(records)!=n or {r['record_id'] for r in records}!=set(rid):raise ValueError('SCI_COMPLETE_RECORD_SET_DIFFERS')
    if any(r['molecule_id']!=mid for r in rows+records):raise ValueError('SCI_MOLECULE_ID_DIFFERS')
    counts={c:{'success':0,'total':0} for c in CALCS};retained=0;audited=0
    for record in records:
        tasks=record['tasks'];names=[d.get('task',d.get('name')) for d in tasks]
        if len(tasks)!=12 or sorted(names)!=sorted(CALCS):raise ValueError('SCI_TWELVE_TASKS_DIFFERS')
        audited+=bool(record.get('audit_selected'))
        for d in tasks:
            calc=d.get('task',d.get('name'));status=d['scope_status'];ref=d['raw_ref']
            if status not in {'SUCCESS','CALCULATION_FAILED','PROPERTY_FAILED','TIMEOUT'}:raise ValueError('SCI_STATUS_DIFFERS')
            counts[calc]['total']+=1;counts[calc]['success']+=status=='SUCCESS'
            wanted=bool(record.get('audit_selected')) or status in {'CALCULATION_FAILED','PROPERTY_FAILED','TIMEOUT'}
            if ref['execution_id']!=ctx['execution_id'] or bool(ref['output_retained'])!=wanted:raise ValueError('SCI_RAW_ATTEMPT_POLICY_DIFFERS')
            raw=db.execute('SELECT molecule_id,scope_status,hex(raw_sha256) AS raw_sha FROM records WHERE record_id=? AND calc_type=? AND execution_id=?',(record['record_id'],calc,ctx['execution_id'])).fetchone()
            if wanted:
                retained+=1
                if raw is None or raw['molecule_id']!=mid or raw['scope_status']!=status:raise ValueError('SCI_RETAINED_RAW_METADATA_MISSING')
                if ref.get('raw_sha256') and raw['raw_sha'].lower()!=ref['raw_sha256'].lower():raise ValueError('SCI_RAW_SHA_REFERENCE_DIFFERS')
            elif raw is not None:raise ValueError('ORDINARY_SUCCESS_HAS_RAW_ROW')
    rawcount=db.execute('SELECT count(*) FROM records WHERE molecule_id=? AND execution_id=?',(mid,ctx['execution_id'])).fetchone()[0]
    if counts!=rec['counts'] or retained!=complete['raw_calls'] or rawcount!=retained or audited!=rec['audited_records']:raise ValueError('SCI_COUNTS_RETENTION_DIFFERS')
    return {'evidence':'SHA_VERIFIED_COMPLETE_SCI_STAGE','wire_sha256':item['wire_sha256'],'context':ctx,'receipt':rec,'receipt_sha256':sha(canonical(rec)),'record_count':n,'raw_calls':retained,'pipeline_failure':rec.get('pipeline_failure')}

def emit(mid,evidence,source,options,q,stream,report):
    current=q.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone()
    if current is None:raise ValueError('SCI_MOLECULE_NOT_IN_QUEUE:'+mid)
    row=dict(current);rec=evidence['receipt'];ctx=evidence['context'];attempt=int(ctx['attempt_id'])
    if int(row['record_count'])!=evidence['record_count'] or str(row['task_id'])!=str(ctx['task_id']):raise ValueError('QUEUE_SCI_POPULATION_TASK_DIFFERS:'+mid)
    report['records']+=evidence['record_count'];desired='RETRY_PENDING' if rec['retryable'] and attempt==0 else 'COMPLETE'
    old=json.loads(row['receipt_json']) if row['receipt_json'] else None;action='NOOP_DURABLE_ALREADY_PUBLISHED'
    if int(row['attempt'])>attempt:action='PRESERVE_OLDER_COMPLETED_ATTEMPT_NOT_LATEST'
    elif int(row['attempt'])<attempt:action='CONFLICT_QUEUE_ATTEMPT_BEHIND_SCI'
    elif old is not None:
        if old.get('context',{}).get('execution_id')!=ctx['execution_id'] or old.get('counts')!=rec['counts']:action='CONFLICT_SAME_ATTEMPT_RECEIPT_DIFFERS'
        elif row['state']!=desired:action='RESTORE_DURABLE_COMPLETION'
    else:action='RESTORE_DURABLE_COMPLETION'
    if action.startswith('CONFLICT_'):report['conflicts'].append({'molecule_id':mid,'classification':action,'source':str(source)})
    stream.write(json.dumps({'molecule_id':mid,'run_root':options['run_root'],'source':str(source),'source_run_sha256':report['run_json_sha256'],'session':options['session'],'action':action,'desired_state':desired,'before':row,'before_sha256':row_sha(row),**evidence},separators=(',',':'),allow_nan=False)+'\n')
    report.setdefault('actions',{})[action]=report.setdefault('actions',{}).get(action,0)+1

def worker_init(barrier):barrier.wait(timeout=180)
def inspect_run(arg):
    run_path,queue_path,out=arg
    from wp5_archive_v5 import ArchiveReader
    run=load(run_path);opt=run['options'];root=Path(opt['run_root'])
    report={'run_root':str(root),'run_json_sha256':digest(run_path),'session':opt['session'],'job_id':str(opt['job_id']),'task_id':str(opt['task_id']),'node':run['node'],'worker_pid':os.getpid(),'staged_molecules':0,'retired_molecules':0,'records':0,'errors':[],'conflicts':[]}
    output=Path(out)/('run_'+opt['session']+'.jsonl');seen={};q=readonly(queue_path)
    try:
        if Path(opt['queue']).resolve()!=Path(queue_path).resolve():raise ValueError('RUN_QUEUE_DIFFERS')
        for field in ('dictionaries','protocol','registry','production_contract','audit_membership','reproduction_package'):
            refs=[x for x in opt['source_bindings'] if x['path']==opt[field]]
            if len(refs)!=1 or digest(opt[field])!=refs[0]['sha256']:raise ValueError('SOURCE_BINDING_DIFFERS:'+field)
        lanes=sorted((root/'temporary_lanes').glob('lane_*.sqlite'));sources=lanes+([root/'raw_archive.sqlite'] if (root/'raw_archive.sqlite').exists() else [])
        refs=load(root/'family_exports.json')['references'] if (root/'family_exports.json').exists() else None
        exported=load(root/'export_completion.json') if (root/'export_completion.json').exists() else None
        retired_cache={}
        def retired(mid,c,db):
            export_id=c.get('export_id')
            saved=db.execute('SELECT references_json FROM parquet_exports WHERE export_id=?',(export_id,)).fetchone()
            if saved is None:raise ValueError('RETIRED_SCI_WITHOUT_DURABLE_PARQUET_EXPORT_BINDING')
            permanent=json.loads(saved[0])
            if sha(canonical(permanent))!=export_id:raise ValueError('RETIRED_EXPORT_BINDING_SHA_DIFFERS')
            canon=[r for r in permanent if r['family']=='canonical_record_attempts']
            if len(canon)!=1:raise ValueError('RETIRED_CANONICAL_REFERENCE_MISSING')
            import pyarrow.parquet as pq
            if export_id not in retired_cache:
                for ref in permanent:
                    path=Path(ref['path'])
                    if path.stat().st_size!=ref['bytes'] or digest(path)!=ref['sha256']:raise ValueError('PERMANENT_EXPORT_SHA_DIFFERS')
                cache={}
                for b in pq.ParquetFile(canon[0]['path']).iter_batches(batch_size=8192):
                    for row in b.to_pylist():cache.setdefault(row['molecule_id'],[]).append(row)
                retired_cache[export_id]=cache
            rec=c['receipt'];ctx=rec['context'];ids={}
            for row in retired_cache[export_id].get(mid,[]):
                if any(str(row[k])!=str(ctx[k]) for k in ('attempt_id','job_id','task_id','lane')) or row['raw_execution_id']!=ctx['execution_id']:raise ValueError('RETIRED_CANONICAL_CONTEXT_DIFFERS')
                ids.setdefault(row['record_id'],[]).append(row['calc_type'])
            if len(ids)!=c['record_count'] or any(sorted(x)!=sorted(CALCS) for x in ids.values()):raise ValueError('RETIRED_CANONICAL_TWELVE_TASK_RECORD_SET_DIFFERS')
            if rec['requested_outcomes']!=12*c['record_count'] or any(rec['counts'][x]['total']!=c['record_count'] for x in CALCS):raise ValueError('RETIRED_COUNTS_DIFFERS')
            return {'evidence':'PREVIOUS_EXACT_EXPORT_CLOSURE_SHA_REVERIFIED_STAGE_RETIRED','wire_sha256':c['wire_sha256'],'context':ctx,'receipt':rec,'receipt_sha256':sha(canonical(rec)),'record_count':c['record_count'],'raw_calls':c['raw_calls'],'pipeline_failure':rec.get('pipeline_failure'),'retirement_export_id':export_id}
        with output.open('x') as stream:
            for source in sources:
                reader=ArchiveReader(source,opt['dictionaries'])
                try:
                    ids=set()
                    for item in reader.iter_staged():
                        mid=item['molecule_id'];ids.add(mid);c=reader.completion(mid)
                        if c is None:raise ValueError('STAGE_WITHOUT_ATOMIC_RECEIPT:'+mid)
                        evidence=validate_payload(item,c,opt,reader.db);key=(mid,evidence['context']['execution_id'])
                        if key in seen:
                            if seen[key]!=evidence['wire_sha256']:raise ValueError('DUPLICATE_EXECUTION_WIRE_DIFFERS')
                            continue
                        seen[key]=evidence['wire_sha256'];report['staged_molecules']+=1;emit(mid,evidence,source,opt,q,stream,report)
                    for row in reader.db.execute('SELECT molecule_id FROM completion_receipts ORDER BY molecule_id'):
                        mid=row[0];c=reader.completion(mid);key=(mid,c['receipt']['context']['execution_id'])
                        if mid in ids or key in seen:continue
                        evidence=retired(mid,c,reader.db);seen[key]=evidence['wire_sha256'];report['retired_molecules']+=1;emit(mid,evidence,source,opt,q,stream,report)
                finally:reader.close()
            stream.flush();os.fsync(stream.fileno())
    except BaseException:report['errors'].append(traceback.format_exc(limit=8))
    finally:q.close()
    if not output.exists():output.touch()
    report['evidence_file']={'path':str(output),'sha256':digest(output),'bytes':output.stat().st_size};return report

def queue_snapshot(path):
    db=readonly(path)
    try:
        return {'meta':dict(db.execute('SELECT key,value FROM meta')),
                'states':[dict(r) for r in db.execute('SELECT state,count(*) AS molecules,sum(record_count) AS records,sum(predicted_seconds) AS predicted_seconds FROM molecules GROUP BY state')],
                'tasks':[dict(r) for r in db.execute('SELECT * FROM tasks ORDER BY task_id')],
                'sessions':[dict(r) for r in db.execute('SELECT * FROM sessions ORDER BY session_id')],
                'export_repairs':[dict(r) for r in db.execute('SELECT * FROM export_repairs ORDER BY run_root')],
                'by_task':[dict(r) for r in db.execute('SELECT task_id,state,count(*) AS molecules,sum(record_count) AS records,sum(predicted_seconds) AS predicted_seconds FROM molecules GROUP BY task_id,state')],
                'running_rows':[dict(r) for r in db.execute("SELECT * FROM molecules WHERE state='RUNNING' ORDER BY molecule_id")]}
    finally:db.close()

def plan(args):
    node_guard();stop_guard();out=Path(args.out)
    if Path(args.queue).resolve()!=ROOT/'queue/pending.sqlite' or not out.resolve().is_relative_to(ROOT):raise ValueError('CURRENT_FORMAL_QUEUE_AND_NEW_ROOT_OUTPUT_REQUIRED')
    out.mkdir(parents=True,exist_ok=False)
    jobs=registered_jobs(args.submitted);proof=terminal_proof(jobs,out)
    base={'schema':'WP5_TERMINAL_QUEUE_RECONCILIATION_PLAN_V1','created_epoch':time.time(),'source_sha256':digest(__file__),'queue':str(args.queue),
          'submitted':{'path':str(args.submitted),'sha256':digest(args.submitted)},'accounting':proof,'QM_started':False,'original_LMDB_opened':False,'queue_modified':False,'historical_files_modified':False}
    if not proof['all_terminal']:
        base.update(status='WAITING_FOR_ALL_ORIGINAL_78_TERMINAL',active_jobs={k:v for k,v in proof['states'].items() if v not in TERMINAL})
        write_json(out/'plan.json',base);print(json.dumps(base));return 75
    snapshot=queue_snapshot(args.queue);write_json(out/'queue_snapshot.json',snapshot)
    selected=[p for p in sorted((ROOT/'runtime').glob('task_*/job_*/run.json')) if str(load(p)['options']['job_id']) in set(jobs)]
    count=min(args.workers,len(selected));runs=[]
    if selected:
        ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(count)
        with concurrent.futures.ProcessPoolExecutor(max_workers=count,mp_context=ctx,initializer=worker_init,initargs=(barrier,)) as pool:
            runs=list(pool.map(inspect_run,[(str(p),str(args.queue),str(out)) for p in selected],chunksize=1))
    conflicts=[{'run_root':r['run_root'],'error':e} for r in runs for e in r['errors']]+[c for r in runs for c in r['conflicts']]
    latest={};restores={};seen_mid=set();current_complete=set()
    for r in runs:
        for line in Path(r['evidence_file']['path']).open():
            e=json.loads(line);key=(e['molecule_id'],int(e['context']['attempt_id']));seen_mid.add(e['molecule_id'])
            if key in latest and latest[key]!=e['wire_sha256']:conflicts.append({'molecule_id':key[0],'attempt':key[1],'classification':'CROSS_RUN_SAME_ATTEMPT_DIFFERENT_COMPLETE_SCI'})
            latest[key]=e['wire_sha256']
            if int(e['before']['attempt'])==int(e['context']['attempt_id']):current_complete.add(e['molecule_id'])
            if e['action']=='RESTORE_DURABLE_COMPLETION':restores.setdefault(e['molecule_id'],e)
    actions=[{'kind':'RESTORE_DURABLE_COMPLETION','molecule_id':m,'evidence':e} for m,e in sorted(restores.items())]
    for row in snapshot['running_rows']:
        if row['molecule_id'] not in restores:
            if row['molecule_id'] not in current_complete:
                actions.append({'kind':'RELEASE_TERMINAL_INCOMPLETE','before':row,'before_sha256':row_sha(row),'desired_state':'RETRY_PENDING' if row['attempt']==0 else 'FINAL_FAILURE',
                                'explanation':'No complete SCI for CURRENT attempt in exhaustive terminal lanes; prior completed attempts remain history, never splice or promote them to current attempt'})
            else:conflicts.append({'molecule_id':row['molecule_id'],'classification':'RUNNING_NONRECONCILABLE_DURABLE_HISTORY'})
    for row in snapshot['export_repairs']:
        if row['state']=='RUNNING':
            if str(row['job_id']) not in proof['states']:conflicts.append({'classification':'EXPORT_REPAIR_OWNER_NOT_ORIGINAL_JOB','row':row})
            else:actions.append({'kind':'RESET_TERMINAL_EXPORT_CLAIM','before':row,'before_sha256':row_sha(row)})
    for row in snapshot['tasks']:
        if row['state']=='RUNNING':
            if str(row['job_id']) not in proof['states']:conflicts.append({'classification':'TASK_OWNER_NOT_ORIGINAL_JOB','row':row})
            else:actions.append({'kind':'MARK_TERMINAL_TASK_DEAD','before':row,'before_sha256':row_sha(row)})
    export_roots=[{'run_root':r['run_root'],'run_json_sha256':r['run_json_sha256'],'session':r['session'],'job_id':r['job_id'],
                   'complete_molecules':r['staged_molecules']+r['retired_molecules'],'records':r['records'],
                   'export_completion_exists':(Path(r['run_root'])/'export_completion.json').exists(),'repair_only_no_QM':True}
                  for r in runs if r['staged_molecules']+r['retired_molecules']]
    if selected and len({r['worker_pid'] for r in runs})<16:conflicts.append({'classification':'FEWER_THAN16_ACTUAL_SCI_WORKERS'})
    write_json(out/'actions.json',actions);write_json(out/'run_reports.json',runs);write_json(out/'export_roots.json',export_roots)
    base.update(status='REVIEWABLE_PLAN_NO_QUEUE_WRITE' if not conflicts else 'PLAN_HAS_EXPLICIT_CONFLICTS_NO_APPLY',
                queue_snapshot={'path':str(out/'queue_snapshot.json'),'sha256':digest(out/'queue_snapshot.json')},
                queue_plan_sha256=snapshot['meta']['plan_sha256'],queue_population=snapshot['meta'],
                actions={'path':str(out/'actions.json'),'sha256':digest(out/'actions.json'),'count':len(actions),'by_kind':dict(Counter(x['kind'] for x in actions))},
                run_reports={'path':str(out/'run_reports.json'),'sha256':digest(out/'run_reports.json')},export_roots={'path':str(out/'export_roots.json'),'sha256':digest(out/'export_roots.json')},
                conflicts=conflicts,workers_requested=args.workers,actual_worker_pids=sorted({r['worker_pid'] for r in runs}),
                complete_SCI_examined=sum(r['staged_molecules']+r['retired_molecules'] for r in runs),records_in_examined_attempts=sum(r['records'] for r in runs),
                scientific_retry_rule='receipt.retryable AND attempt==0; never inferred from queue RETRY alone',
                export_before_new_QM='Apply reviewed reconciliation, separately repair-only every export_roots using runner11, verify permanent SHAs before new claims',
                recovery_submission='Same original72 task IDs/node mapping may resume pending rows only; new submissions require Root/user direction after original6 cleanup per guide3.5')
    write_json(out/'plan.json',base);print(json.dumps({k:base[k] for k in ('status','actions','complete_SCI_examined','actual_worker_pids','conflicts')}));return 0 if not conflicts else 2

def retry_transaction(db,callback,seconds=120):
    limit=time.monotonic()+seconds
    while True:
        try:db.execute('BEGIN IMMEDIATE');value=callback();db.execute('COMMIT');return value
        except sqlite3.OperationalError as exc:
            if db.in_transaction:db.execute('ROLLBACK')
            code=getattr(exc,'sqlite_errorcode',None)
            busy=((code & 255) in (sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED)) if isinstance(code,int) else str(exc).lower() in {'database is locked','database table is locked','database is busy'}
            if not busy:raise
            if time.monotonic()>=limit:raise
            time.sleep(min(.25,limit-time.monotonic()))
        except BaseException:
            if db.in_transaction:db.execute('ROLLBACK')
            raise

def action_apply(db,a):
    kind=a['kind'];now=time.time()
    if kind=='RESTORE_DURABLE_COMPLETION':
        e=a['evidence'];mid=e['molecule_id'];row=db.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone();rec=e['receipt'];ctx=e['context']
        old=json.loads(row['receipt_json']) if row['receipt_json'] else None
        if old and old.get('context',{}).get('execution_id')==ctx['execution_id'] and old.get('counts')==rec['counts'] and row['state']==e['desired_state']:return 'ALREADY_APPLIED'
        if row_sha(row)!=e['before_sha256']:raise ValueError('QUEUE_ROW_CHANGED_SINCE_REVIEW:'+mid)
        rank=row['completion_rank']
        if rank is None:
            rank=int(db.execute("SELECT value FROM meta WHERE key='completion_sequence'").fetchone()[0])+1
            db.execute("UPDATE meta SET value=? WHERE key='completion_sequence'",(str(rank),))
        path=row['archive_path'] if row['export_json'] and row['receipt_json'] else e['source']
        db.execute('UPDATE molecules SET state=?,owner=?,lane=?,archive_path=?,receipt_json=?,counts_json=?,completion_rank=?,updated=? WHERE molecule_id=?',
                   (e['desired_state'],e['session'],ctx['lane'],path,json.dumps(rec),json.dumps(rec['counts']),rank,now,mid))
    elif kind=='RELEASE_TERMINAL_INCOMPLETE':
        b=a['before'];row=db.execute('SELECT * FROM molecules WHERE molecule_id=?',(b['molecule_id'],)).fetchone()
        if row['state']==a['desired_state'] and row['owner'] is None:return 'ALREADY_APPLIED'
        if row_sha(row)!=a['before_sha256']:raise ValueError('INCOMPLETE_ROW_CHANGED_SINCE_REVIEW')
        db.execute('UPDATE molecules SET state=?,owner=NULL,updated=? WHERE molecule_id=?',(a['desired_state'],now,b['molecule_id']))
    elif kind=='RESET_TERMINAL_EXPORT_CLAIM':
        b=a['before'];row=db.execute('SELECT * FROM export_repairs WHERE run_root=?',(b['run_root'],)).fetchone()
        if row['state']=='ERROR' and row['error']=='TERMINAL_METADATA_RECONCILIATION_RETRYABLE_NO_QM':return 'ALREADY_APPLIED'
        if row_sha(row)!=a['before_sha256']:raise ValueError('EXPORT_CLAIM_CHANGED_SINCE_REVIEW')
        db.execute("UPDATE export_repairs SET state='ERROR',updated=?,error=? WHERE run_root=?",(now,'TERMINAL_METADATA_RECONCILIATION_RETRYABLE_NO_QM',b['run_root']))
    elif kind=='MARK_TERMINAL_TASK_DEAD':
        b=a['before'];row=db.execute('SELECT * FROM tasks WHERE task_id=?',(b['task_id'],)).fetchone()
        if row['state']=='DEAD':return 'ALREADY_APPLIED'
        if row_sha(row)!=a['before_sha256']:raise ValueError('TASK_CHANGED_SINCE_REVIEW')
        if db.execute("SELECT 1 FROM molecules WHERE task_id=? AND state='RUNNING' LIMIT 1",(b['task_id'],)).fetchone():raise ValueError('TASK_HAS_UNRECONCILED_RUNNING_MOLECULE')
        db.execute("UPDATE tasks SET state='DEAD',heartbeat=? WHERE task_id=?",(now,b['task_id']))
    else:raise ValueError('UNKNOWN_ACTION:'+kind)
    return 'APPLIED'

def apply(args):
    node_guard();stop_guard();path=Path(args.plan)
    if digest(path)!=args.expected_plan_sha256:raise ValueError('EXACT_REVIEWED_PLAN_SHA_REQUIRED')
    p=load(path)
    if p['status']!='REVIEWABLE_PLAN_NO_QUEUE_WRITE' or p['conflicts']:raise ValueError('CONFLICT_FREE_REVIEWABLE_PLAN_REQUIRED')
    if digest(__file__)!=p['source_sha256']:raise ValueError('RECONCILIATION_SOURCE_CHANGED')
    out=Path(args.out)
    if Path(p['queue']).resolve()!=ROOT/'queue/pending.sqlite' or not out.resolve().is_relative_to(ROOT):raise ValueError('CURRENT_FORMAL_QUEUE_AND_NEW_ROOT_OUTPUT_REQUIRED')
    out.mkdir(parents=True,exist_ok=False)
    if digest(p['submitted']['path'])!=p['submitted']['sha256']:raise ValueError('SUBMISSION_CHANGED')
    proof=terminal_proof(registered_jobs(p['submitted']['path']),out)
    if not proof['all_terminal']:raise ValueError('ALL78_TERMINAL_REQUIRED_APPLY_BLOCKED')
    for ref in (p['actions'],p['run_reports'],p['queue_snapshot'],p['export_roots']):
        if digest(ref['path'])!=ref['sha256']:raise ValueError('REVIEWED_PLAN_LEAF_CHANGED')
    for r in load(p['run_reports']['path']):
        if digest(Path(r['run_root'])/'run.json')!=r['run_json_sha256'] or digest(r['evidence_file']['path'])!=r['evidence_file']['sha256']:raise ValueError('SCI_EVIDENCE_BINDING_CHANGED')
    from wp5_archive_v5 import ArchiveReader
    actions=load(p['actions']['path'])
    for a in actions:
        if a['kind']!='RESTORE_DURABLE_COMPLETION':continue
        e=a['evidence'];opt=load(Path(e['run_root'])/'run.json')['options'];reader=ArchiveReader(e['source'],opt['dictionaries'])
        try:
            c=reader.completion(e['molecule_id'])
            if c is None or c['wire_sha256']!=e['wire_sha256'] or sha(canonical(c['receipt']))!=e['receipt_sha256']:raise ValueError('DURABLE_RECEIPT_CHANGED')
            row=reader.db.execute('SELECT uncompressed_bytes,dict_id,wire_frame FROM parsed_molecules WHERE molecule_id=?',(e['molecule_id'],)).fetchone()
            if row is not None:
                d=reader.dicts['pm7_B'];wire=reader.zstd.decompress(row['wire_frame'],d['data'],row['uncompressed_bytes'])
                if row['dict_id']!=d['dict_id'] or sha(wire)!=e['wire_sha256']:raise ValueError('DURABLE_WIRE_CHANGED')
            elif e.get('retirement_export_id'):
                saved=reader.db.execute('SELECT references_json FROM parquet_exports WHERE export_id=?',(e['retirement_export_id'],)).fetchone()
                if saved is None or sha(canonical(json.loads(saved[0])))!=e['retirement_export_id']:raise ValueError('RETIRED_EXPORT_BINDING_CHANGED')
                for ref in json.loads(saved[0]):
                    if Path(ref['path']).stat().st_size!=ref['bytes'] or digest(ref['path'])!=ref['sha256']:raise ValueError('RETIRED_PERMANENT_EXPORT_CHANGED')
            else:raise ValueError('CANDIDATE_SCI_WIRE_DISAPPEARED')
        finally:reader.close()
    db=sqlite3.connect(p['queue'],timeout=1,isolation_level=None);db.row_factory=sqlite3.Row;db.execute('PRAGMA busy_timeout=1000');db.execute('PRAGMA synchronous=FULL');results=[]
    try:
        if dict(db.execute('SELECT key,value FROM meta')).get('plan_sha256')!=p['queue_plan_sha256']:raise ValueError('QUEUE_FROZEN_PLAN_CHANGED')
        with (out/'mutation_journal.jsonl').open('x') as journal:
            for i,a in enumerate(actions):
                journal.write(json.dumps({'event':'BEFORE','index':i,'action':a},separators=(',',':'),allow_nan=False)+'\n');journal.flush();os.fsync(journal.fileno())
                value=retry_transaction(db,lambda:action_apply(db,a));r={'index':i,'kind':a['kind'],'status':value};results.append(r)
                journal.write(json.dumps({'event':'AFTER',**r})+'\n');journal.flush();os.fsync(journal.fileno())
    finally:db.close()
    report={'schema':'WP5_TERMINAL_QUEUE_RECONCILIATION_APPLY_V1','status':'METADATA_ONLY_RECONCILIATION_COMPLETE','plan':{'path':str(path),'sha256':args.expected_plan_sha256},
            'accounting':proof,'results':results,'queue_modified':True,'QM_started':False,'original_LMDB_opened':False,'historical_files_modified':False,'scientific_attempts_reset':False,
            'export_repair_pending_separate_no_QM_step':p['export_roots']}
    write_json(out/'report.json',report);print(json.dumps({'status':report['status'],'actions':len(results)}));return 0

def check():
    import ast
    ast.parse(Path(__file__).read_text())
    db=sqlite3.connect(':memory:',isolation_level=None);db.row_factory=sqlite3.Row
    db.executescript("CREATE TABLE meta(key TEXT PRIMARY KEY,value);INSERT INTO meta VALUES('completion_sequence','0');CREATE TABLE molecules(molecule_id TEXT PRIMARY KEY,task_id,record_count,state,attempt,owner,lane,archive_path,receipt_json,counts_json,completion_rank,export_json,updated);")
    db.execute("INSERT INTO molecules VALUES('m','t',2,'RETRY_PENDING',0,NULL,0,'old',NULL,NULL,NULL,NULL,1)")
    before=dict(db.execute('SELECT * FROM molecules').fetchone());ctx={'execution_id':'session:0:0:test','attempt_id':0,'lane':0}
    rec={'molecule_id':'m','records':2,'context':ctx,'counts':{c:{'total':2,'success':2} for c in CALCS},'retryable':False}
    a={'kind':'RESTORE_DURABLE_COMPLETION','evidence':{'molecule_id':'m','before':before,'before_sha256':row_sha(before),'receipt':rec,'context':ctx,'session':'session','source':'preserved.sqlite','desired_state':'COMPLETE'}}
    assert retry_transaction(db,lambda:action_apply(db,a))=='APPLIED'
    assert retry_transaction(db,lambda:action_apply(db,a))=='ALREADY_APPLIED'
    row=db.execute('SELECT * FROM molecules').fetchone();assert row['state']=='COMPLETE' and row['attempt']==0 and row['completion_rank']==1
    assert db.execute("SELECT value FROM meta WHERE key='completion_sequence'").fetchone()[0]=='1'
    # A real scientific once-retry remains RETRY_PENDING; metadata restoration
    # alone must never consume it. Changed queue rows fail the review binding.
    rec2={**rec,'retryable':True};before2=dict(row)
    db.execute("UPDATE molecules SET state='PENDING',receipt_json=NULL,owner=NULL WHERE molecule_id='m'")
    before2=dict(db.execute('SELECT * FROM molecules').fetchone())
    a2={'kind':'RESTORE_DURABLE_COMPLETION','evidence':{**a['evidence'],'before':before2,'before_sha256':row_sha(before2),'receipt':rec2,'desired_state':'RETRY_PENDING'}}
    assert retry_transaction(db,lambda:action_apply(db,a2))=='APPLIED'
    assert db.execute('SELECT attempt FROM molecules').fetchone()[0]==0
    db.execute("UPDATE molecules SET state='PENDING',receipt_json=NULL WHERE molecule_id='m'")
    try:retry_transaction(db,lambda:action_apply(db,a2));raise AssertionError('stale review accepted')
    except ValueError as e:assert 'CHANGED_SINCE_REVIEW' in str(e)
    # Complete 12 outcomes are required for each original record, not an
    # aggregation of partial attempts. Ordinary success has no raw rows.
    db.execute('CREATE TABLE records(record_id,calc_type,execution_id,molecule_id,scope_status,raw_sha256)')
    fullctx={'attempt_id':0,'job_id':1,'task_id':'t','lane':0,'execution_id':'session:0:0:test','reproduction_package_sha256':'p','audit_membership_sha256':'a'}
    fullrec={**rec,'requested_outcomes':24,'raw_policy':POLICY,'context':fullctx,'audited_records':0}
    rows=[{'record_id':'r1','molecule_id':'m'},{'record_id':'r2','molecule_id':'m'}]
    records=[{**r,'audit_selected':False,'tasks':[{'task':c,'scope_status':'SUCCESS','raw_ref':{'execution_id':fullctx['execution_id'],'output_retained':False}} for c in CALCS]} for r in rows]
    item={'molecule_id':'m','record_count':2,'wire_sha256':'wire','payload':{'context':fullctx,'population_rows':rows,'result':{'record_results':records}}}
    complete={'record_count':2,'wire_sha256':'wire','raw_calls':0,'receipt':fullrec}
    opt={'job_id':'1','task_id':'t','mode':'main','session':'session','reproduction_package_sha256':'p','audit_membership_sha256':'a'}
    assert validate_payload(item,complete,opt,db)['raw_calls']==0
    records.pop()
    try:validate_payload(item,complete,opt,db);raise AssertionError('partial SCI accepted')
    except ValueError as e:assert str(e)=='SCI_COMPLETE_RECORD_SET_DIFFERS'
    db.close();print('RECONCILIATION_METADATA_FIXTURE_PASS_NO_QM_NO_LMDB_NO_FORMAL_QUEUE')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=('plan','apply'),default='plan');p.add_argument('--check',action='store_true')
    p.add_argument('--queue',type=Path,default=ROOT/'queue/pending.sqlite');p.add_argument('--submitted',type=Path,default=ROOT/'submission/submitted_jobs.json')
    p.add_argument('--out',type=Path);p.add_argument('--workers',type=int,default=24);p.add_argument('--plan',type=Path);p.add_argument('--expected-plan-sha256')
    a=p.parse_args()
    if a.check:check()
    else:
        if not a.out:p.error('--out required')
        if a.mode=='plan' and a.workers<16:p.error('at least16 workers required for SCI reads')
        if a.mode=='apply' and (not a.plan or not a.expected_plan_sha256):p.error('--plan and --expected-plan-sha256 required')
        raise SystemExit(plan(a) if a.mode=='plan' else apply(a))
