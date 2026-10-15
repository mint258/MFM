"""Read-only by default. Terminal subset of229 actual WP5 submissions only.
Reuse frozen v2 SCI/receipt validators; never change scientific outputs or jobs.
Live/PD/unknown ownership is excluded both at planning and explicit Root apply.
"""
from __future__ import annotations
import argparse,concurrent.futures,json,multiprocessing,os,sqlite3,time,traceback
from collections import Counter
from pathlib import Path
import wp5_queue_reconcile_v2 as H
ROOT=H.ROOT
MANIFESTS=(ROOT/'submission/submitted_jobs.json',ROOT/'submission/recovery_attempt_v11/submitted_jobs.json',ROOT/'submission/startup_replacement_v1/submitted_jobs.json')
HELPER_SHA='fa8ff8c76b8be5de3aca269ad6c155ec18825bc18ab6facece9824c5e8208e84'
EXPECTED=((72,6),(72,6),(69,4))
IMPLEMENTATION_VERSION=4
READ_RETRY_EVENTS=[]

class DetachedReadResult:
    """Cursor-compatible small queue rows, detached before SCI decompression."""
    def __init__(self,rows):self.rows=rows;self.offset=0
    def fetchone(self):
        if self.offset>=len(self.rows):return None
        row=self.rows[self.offset];self.offset+=1;return row
    def fetchall(self):
        out=self.rows[self.offset:];self.offset=len(self.rows);return out
    def __iter__(self):return iter(self.fetchall())
    def close(self):self.rows=[];self.offset=0

def read_lock_error(exc):
    code=getattr(exc,'sqlite_errorcode',None)
    if isinstance(code,int):return (code & 255) in (sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED)
    return str(exc).lower() in {'database is locked','database table is locked','database is busy'}

class BoundedReadonly:
    """No transaction/journal changes,1s sqlite wait,120s BUSY-only read retry."""
    def __init__(self,path):
        from urllib.parse import quote
        self.path=str(Path(path).resolve());self.stats={'path':self.path,'worker_pid':os.getpid(),'queries':0,'busy_retries':0,'busy_seconds':0.,'interrupted':False}
        self.db=sqlite3.connect('file:'+quote(self.path)+'?mode=ro',uri=True,timeout=1,isolation_level=None)
        self.db.row_factory=sqlite3.Row
        self.execute('PRAGMA query_only=ON');self.execute('PRAGMA busy_timeout=1000')
    def execute(self,sql,parameters=()):
        self.stats['queries']+=1;deadline=time.monotonic()+120.
        while True:
            cursor=None;began=time.monotonic()
            try:
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    self.stats['interrupted']=True
                    raise TimeoutError('QUEUE_READ_BUSY_RETRY120S_EXPIRED')
                # SQLite's own sleep also fits inside the remaining120s budget.
                self.db.execute('PRAGMA busy_timeout='+str(max(1,min(1000,int(remaining*1000))))).close()
                cursor=self.db.cursor();cursor.execute(sql,parameters);rows=cursor.fetchall()
                return DetachedReadResult(rows)
            except sqlite3.OperationalError as exc:
                if not read_lock_error(exc):raise
                self.stats['busy_retries']+=1;self.stats['busy_seconds']+=time.monotonic()-began
                if time.monotonic()>=deadline:
                    self.stats['interrupted']=True;raise
            finally:
                # Even failed/partial read cursors are closed before retry sleep.
                if cursor is not None:cursor.close()
            wait=min(.1,max(0.,deadline-time.monotonic()));time.sleep(wait);self.stats['busy_seconds']+=wait
    def close(self):
        if self.db is not None:
            self.db.close();self.db=None;READ_RETRY_EVENTS.append(dict(self.stats))

# This substitution exists only inside new V4 processes. Frozen helper bytes and
# SCI validators are unchanged; its queue reads use this small metadata adapter.
H.readonly=BoundedReadonly

def inspect_run_v4(arg):
    start=len(READ_RETRY_EVENTS);report=H.inspect_run(arg)
    report['implementation_version']=IMPLEMENTATION_VERSION
    report['scan_complete']=not bool(report['errors'])
    report['repair_claim_allowed']=report['scan_complete']
    report['sci_counter_scope']='COMPLETE_ROOT_SCAN' if report['scan_complete'] else 'PARTIAL_READ_NOT_ROOT_CLOSURE'
    report['queue_read_retry_stats']=READ_RETRY_EVENTS[start:]
    return report

def registry(paths):
    if len(paths)!=3:raise ValueError('EXACT_THREE_ACTUAL_MANIFESTS_REQUIRED')
    jobs={};refs=[];receipts=[]
    for path,count in zip(paths,EXPECTED):
        path=Path(path)
        if not path.resolve().is_relative_to((ROOT/'submission').resolve()):raise ValueError('ACTUAL_MANIFEST_SCOPE_DIFFERS')
        doc=H.load(path);main=doc.get('main',[]);cleanup=doc.get('cleanup',[])
        if (len(main),len(cleanup))!=count or doc.get('error') is not None:raise ValueError('ACTUAL_MANIFEST_COUNTS_OR_ERROR_DIFFER')
        refs.append({'path':str(path),'sha256':H.digest(path),'main':count[0],'cleanup':count[1],'status':doc['status']})
        for entry in main+cleanup:
            job=str(entry['job_id'])
            if job in jobs:raise ValueError('SUBMISSION_JOB_DUPLICATED:'+job)
            rp=Path(entry['receipt']);receipt=H.load(rp)
            if str(receipt['job_id'])!=job or receipt['node']!=entry['node'] or receipt.get('uid')!=1278 or receipt.get('user')!='zixiao':raise ValueError('ACTUAL_RECEIPT_ID_NODE_UID_USER_DIFFER')
            jobs[job]={**entry,'job_id':job,'task_id':str(entry['task_id'])}
            receipts.append({'path':str(rp),'sha256':H.digest(rp),'job_id':job,'node':entry['node']})
    if len(jobs)!=229:raise ValueError('EXACT229_ACTUAL_JOB_IDS_REQUIRED')
    return jobs,refs,receipts

def protection(jobs,proof):
    live={job for job,state in proof['states'].items() if state not in H.TERMINAL}
    tasks={jobs[job]['task_id'] for job in live if jobs[job]['mode']=='main'}
    return live,tasks

def guard(row,session_jobs,jobs,proof,live_tasks,candidate_job=None):
    if candidate_job is not None and proof['states'].get(str(candidate_job)) not in H.TERMINAL:return 'SKIP_CANDIDATE_NONTERMINAL_OR_UNREGISTERED'
    if str(row.get('task_id')) in live_tasks:return 'SKIP_ACTIVE_OR_PD_TASK'
    owner=row.get('owner')
    if owner:
        job=session_jobs.get(str(owner))
        if job is None or job not in jobs:return 'SKIP_UNKNOWN_OWNER_JOB'
        if proof['states'].get(job) not in H.TERMINAL:return 'SKIP_ACTIVE_OR_PD_OWNER_SESSION'
    elif row.get('state')=='RUNNING':return 'SKIP_RUNNING_WITH_UNKNOWN_OWNER'
    return None

def root_for_archive(path):
    if not path:return None
    p=Path(path)
    return str(p.parent.parent if p.parent.name=='temporary_lanes' else p.parent)

def dry_run(args):
    H.node_guard()
    if H.digest(H.__file__)!=HELPER_SHA:raise ValueError('FROZEN_V2_VALIDATOR_CHANGED')
    out=Path(args.out)
    if not out.resolve().is_relative_to((ROOT/'reports').resolve()) or Path(args.queue).resolve()!=(ROOT/'queue/pending.sqlite').resolve():raise ValueError('FORMAL_QUEUE_NEW_REPORT_ROOT_REQUIRED')
    out.mkdir(parents=True,exist_ok=False)
    jobs,manifests,receipts=registry(args.manifests);proof=H.terminal_proof(list(jobs),out)
    live,live_tasks=protection(jobs,proof)
    snapshot=H.queue_snapshot(args.queue);H.write_json(out/'queue_snapshot.json',snapshot)
    session_jobs={str(r['session_id']):str(r['job_id']) for r in snapshot['sessions']}
    # No BEGIN/read cursor is held while wire decompression runs.
    q=H.readonly(args.queue)
    try:
        missing=[dict(r) for r in q.execute("SELECT molecule_id,owner,task_id,archive_path,state,attempt FROM molecules WHERE archive_path IS NOT NULL AND receipt_json IS NULL AND state IN ('RUNNING','RETRY_PENDING','ATTENTION_REQUIRED')")]
    finally:q.close()
    needed_closed={root_for_archive(r['archive_path']) for r in missing if not guard(r,session_jobs,jobs,proof,live_tasks)}
    needed_closed|={root_for_archive(r['archive_path']) for r in snapshot['running_rows'] if not guard(r,session_jobs,jobs,proof,live_tasks)}
    selected=[];skipped=[];closed=[]
    for path in sorted((ROOT/'runtime').glob('task_*/job_*/run.json')):
        run=H.load(path);opt=run['options'];job=str(opt['job_id'])
        if job not in jobs:continue
        root=Path(opt['run_root']);entry=jobs[job]
        if Path(opt['queue']).resolve()!=Path(args.queue).resolve():raise ValueError('RUNTIME_QUEUE_BINDING_DIFFERS')
        if proof['states'][job] not in H.TERMINAL or entry['mode']=='main' and entry['task_id'] in live_tasks:
            skipped.append({'run_root':str(root),'job_id':job,'task_id':entry['task_id'],'reason':'ACTIVE_OR_PD_JOB_TASK'});continue
        completion=root/'export_completion.json'
        if completion.exists() and str(root) not in needed_closed:
            doc=H.load(completion)
            closed.append({'run_root':str(root),'job_id':job,'run_json_sha256':H.digest(path),'closure_path':str(completion),
                           'closure_sha256':H.digest(completion),'molecules':doc.get('molecules'),'records':doc.get('records'),
                           'archive':doc.get('archive'),'scope':'ALREADY_CLOSED_REUSED_NOT_REEXPORTED_NOT_RESCANNED'});continue
        selected.append(path)
    runs=[]
    if selected:
        count=min(args.workers,len(selected));ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(count)
        with concurrent.futures.ProcessPoolExecutor(max_workers=count,mp_context=ctx,initializer=H.worker_init,initargs=(barrier,)) as pool:
            runs=list(pool.map(inspect_run_v4,[(str(p),str(args.queue),str(out)) for p in selected],chunksize=1))
    conflicts=[{'run_root':r['run_root'],'error':e} for r in runs for e in r['errors']]
    actions=[];restores={};current_complete=set();same_attempt={};evidence_skips=[]
    for r in runs:
        with Path(r['evidence_file']['path']).open() as stream:
            for line in stream:
                e=json.loads(line);b=e['before'];reason=guard(b,session_jobs,jobs,proof,live_tasks,e['context']['job_id'])
                if reason:
                    evidence_skips.append({'molecule_id':e['molecule_id'],'run_root':e['run_root'],'reason':reason});continue
                key=(e['molecule_id'],int(e['context']['attempt_id']))
                if key in same_attempt and same_attempt[key]!=e['wire_sha256']:conflicts.append({'molecule_id':key[0],'attempt':key[1],'classification':'CROSS_EXECUTION_SAME_ATTEMPT_DIFFERENT_COMPLETE_SCI'})
                same_attempt[key]=e['wire_sha256']
                if int(b['attempt'])==int(e['context']['attempt_id']):current_complete.add(e['molecule_id'])
                if e['action'].startswith('CONFLICT_'):conflicts.append({'molecule_id':e['molecule_id'],'classification':e['action'],'run_root':e['run_root']})
                elif e['action']=='RESTORE_DURABLE_COMPLETION':restores.setdefault(e['molecule_id'],e)
    actions=[{'kind':'RESTORE_DURABLE_COMPLETION','molecule_id':m,'evidence':e} for m,e in sorted(restores.items())]
    for row in snapshot['running_rows']:
        reason=guard(row,session_jobs,jobs,proof,live_tasks)
        if reason:
            evidence_skips.append({'molecule_id':row['molecule_id'],'reason':reason});continue
        if row['molecule_id'] in restores:continue
        if row['molecule_id'] not in current_complete:
            actions.append({'kind':'RELEASE_TERMINAL_INCOMPLETE','before':row,'before_sha256':H.row_sha(row),
                            'desired_state':'RETRY_PENDING' if row['attempt']==0 else 'FINAL_FAILURE',
                            'explanation':'No CURRENT-attempt fullSCI after complete terminal-subset search; preserve old attempts, never splice'})
        else:conflicts.append({'molecule_id':row['molecule_id'],'classification':'RUNNING_CURRENT_DURABLE_HISTORY_NOT_RECONCILABLE'})
    for row in snapshot['export_repairs']:
        if row['state']!='RUNNING':continue
        job=str(row['job_id'])
        reason=guard(row,session_jobs,jobs,proof,live_tasks)
        if job not in jobs or proof['states'].get(job) not in H.TERMINAL or reason:
            evidence_skips.append({'run_root':row['run_root'],'job_id':job,'reason':reason or 'SKIP_ACTIVE_PD_OR_UNKNOWN_EXPORT_CLAIM'});continue
        actions.append({'kind':'RESET_TERMINAL_EXPORT_CLAIM','before':row,'before_sha256':H.row_sha(row)})
    for row in snapshot['tasks']:
        if row['state']!='RUNNING':continue
        job=str(row['job_id'])
        if str(row['task_id']) in live_tasks or job not in jobs or proof['states'].get(job) not in H.TERMINAL:
            evidence_skips.append({'task_id':row['task_id'],'job_id':job,'reason':'SKIP_ACTIVE_PD_OR_UNKNOWN_TASK'});continue
        # Unknown/live molecule owners keep the task intact.
        owned=[r for r in snapshot['running_rows'] if r['task_id']==row['task_id']]
        if any(guard(r,session_jobs,jobs,proof,live_tasks) for r in owned):
            evidence_skips.append({'task_id':row['task_id'],'reason':'SKIP_TASK_WITH_PROTECTED_RUNNING_MOLECULE'});continue
        actions.append({'kind':'MARK_TERMINAL_TASK_DEAD','before':row,'before_sha256':H.row_sha(row)})
    exports=[{'run_root':r['run_root'],'run_json_sha256':r['run_json_sha256'],'job_id':r['job_id'],'session':r['session'],
              'molecules':r['staged_molecules']+r['retired_molecules'],'records':r['records'],'old_attempts_preserved':True,
              'repair_only_no_QM':True,'own_run_receipts_required_for_historical_canonical':True,'scan_complete':r['scan_complete'],'repair_claim_allowed':r['scan_complete']}
             for r in runs if r['staged_molecules']+r['retired_molecules'] and not (Path(r['run_root'])/'export_completion.json').exists()]
    # Allocated/requested workers and actual roots/PIDs are reported separately;
    # two terminal roots legitimately use two SCI workers, never fake16.
    for name,data in (('actions',actions),('run_reports',runs),('export_roots',exports),('already_closed_roots',closed),('skipped',skipped+evidence_skips)):
        H.write_json(out/(name+'.json'),data)
    plan={'schema':'WP5_TERMINAL_SUBSET_RECONCILIATION_PLAN_V3','status':'REVIEWABLE_TERMINAL_SUBSET_DRY_RUN' if not conflicts else 'DRY_RUN_EXPLICIT_CONFLICTS_NO_APPLY',
          'created_epoch':time.time(),'implementation_version':IMPLEMENTATION_VERSION,'source_sha256':H.digest(__file__),'helper':{'path':H.__file__,'sha256':HELPER_SHA},'queue':str(args.queue),
          'manifests':manifests,'registered_receipts':receipts,'registered_jobs':jobs,'accounting':proof,
          'protected_jobs':{j:proof['states'][j] for j in sorted(live)},'protected_tasks':sorted(live_tasks),
          'terminal_jobs':sorted(set(jobs)-live),'queue_plan_sha256':snapshot['meta']['plan_sha256'],'queue_population':snapshot['meta'],
          'actions':{'path':str(out/'actions.json'),'sha256':H.digest(out/'actions.json'),'count':len(actions),'by_kind':dict(Counter(a['kind'] for a in actions))},
          'run_reports':{'path':str(out/'run_reports.json'),'sha256':H.digest(out/'run_reports.json')},
          'export_roots':{'path':str(out/'export_roots.json'),'sha256':H.digest(out/'export_roots.json')},
          'already_closed_roots':{'path':str(out/'already_closed_roots.json'),'sha256':H.digest(out/'already_closed_roots.json'),'count':len(closed)},
          'skipped':{'path':str(out/'skipped.json'),'sha256':H.digest(out/'skipped.json'),'count':len(skipped)+len(evidence_skips)},
          'queue_snapshot':{'path':str(out/'queue_snapshot.json'),'sha256':H.digest(out/'queue_snapshot.json')},
          'conflicts':conflicts,'workers_requested':args.workers,'roots_requested':len(selected),'actual_SCI_workers':sorted({r['worker_pid'] for r in runs}),
          'all_selected_root_scans_complete':all(r['scan_complete'] for r in runs),'queue_read_retry_stats':READ_RETRY_EVENTS,
          'SCI_attempt_molecules_read':sum(r['staged_molecules']+r['retired_molecules'] for r in runs),
          'SCI_attempt_records_read':sum(r['records'] for r in runs),'queue_modified':False,'QM_started':False,'original_LMDB_opened':False,
          'global_STOP_changed_or_required':False,'old_SCI_contract_package_execution_provenance_preserved':True}
    H.write_json(out/'plan.json',plan)
    print(json.dumps({k:plan[k] for k in ('status','actions','protected_jobs','protected_tasks','SCI_attempt_molecules_read','SCI_attempt_records_read','conflicts')}))
    return 0 if not conflicts else 2

def candidate_readback(e):
    from wp5_archive_v5 import ArchiveReader
    run=H.load(Path(e['run_root'])/'run.json')
    if H.digest(Path(e['run_root'])/'run.json')!=e['source_run_sha256']:raise ValueError('OLD_RUN_CHANGED')
    reader=ArchiveReader(e['source'],run['options']['dictionaries'])
    try:
        c=reader.completion(e['molecule_id'])
        if c is None or c['wire_sha256']!=e['wire_sha256'] or H.sha(H.canonical(c['receipt']))!=e['receipt_sha256']:raise ValueError('DURABLE_OLD_SCI_RECEIPT_CHANGED')
        row=reader.db.execute('SELECT uncompressed_bytes,dict_id,wire_frame FROM parsed_molecules WHERE molecule_id=?',(e['molecule_id'],)).fetchone()
        if row is not None:
            d=reader.dicts['pm7_B'];wire=reader.zstd.decompress(row['wire_frame'],d['data'],row['uncompressed_bytes'])
            if row['dict_id']!=d['dict_id'] or H.sha(wire)!=e['wire_sha256']:raise ValueError('OLD_SCI_WIRE_CHANGED')
        elif e.get('retirement_export_id'):
            saved=reader.db.execute('SELECT references_json FROM parquet_exports WHERE export_id=?',(e['retirement_export_id'],)).fetchone()
            if saved is None or H.sha(H.canonical(json.loads(saved[0])))!=e['retirement_export_id']:raise ValueError('OLD_RETIRED_EXPORT_BINDING_CHANGED')
            for ref in json.loads(saved[0]):
                if Path(ref['path']).stat().st_size!=ref['bytes'] or H.digest(ref['path'])!=ref['sha256']:raise ValueError('OLD_PERMANENT_EXPORT_CHANGED')
        else:raise ValueError('OLD_SCI_STAGE_DISAPPEARED_WITHOUT_EXPORT_PROOF')
    finally:reader.close()

def current_action_guard(db,action,jobs,proof,live_tasks):
    kind=action['kind'];sessions={str(r[0]):str(r[1]) for r in db.execute('SELECT session_id,job_id FROM sessions')}
    if kind in {'RESTORE_DURABLE_COMPLETION','RELEASE_TERMINAL_INCOMPLETE'}:
        mid=action['evidence']['molecule_id'] if kind=='RESTORE_DURABLE_COMPLETION' else action['before']['molecule_id']
        row=db.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone()
        if row is None:return 'SKIP_CURRENT_ROW_MISSING'
        candidate=action['evidence']['context']['job_id'] if kind=='RESTORE_DURABLE_COMPLETION' else None
        return guard(dict(row),sessions,jobs,proof,live_tasks,candidate)
    if kind=='RESET_TERMINAL_EXPORT_CLAIM':
        row=db.execute('SELECT * FROM export_repairs WHERE run_root=?',(action['before']['run_root'],)).fetchone()
        if row is None:return 'SKIP_EXPORT_CLAIM_MISSING'
        job=str(row['job_id'])
        if job not in jobs or proof['states'].get(job) not in H.TERMINAL:return 'SKIP_CURRENT_EXPORT_OWNER_ACTIVE_PD_OR_UNKNOWN'
        return guard(dict(row),sessions,jobs,proof,live_tasks)
    if kind=='MARK_TERMINAL_TASK_DEAD':
        row=db.execute('SELECT * FROM tasks WHERE task_id=?',(action['before']['task_id'],)).fetchone()
        if row is None:return 'SKIP_CURRENT_TASK_MISSING'
        if str(row['task_id']) in live_tasks or proof['states'].get(str(row['job_id'])) not in H.TERMINAL:return 'SKIP_CURRENT_TASK_ACTIVE_PD_OR_UNKNOWN'
        for mol in db.execute("SELECT * FROM molecules WHERE task_id=? AND state='RUNNING'",(row['task_id'],)):
            if guard(dict(mol),sessions,jobs,proof,live_tasks):return 'SKIP_TASK_WITH_PROTECTED_RUNNING_MOLECULE'
    return None

def verify_after(db,action):
    kind=action['kind']
    if kind=='RESTORE_DURABLE_COMPLETION':
        e=action['evidence'];r=db.execute('SELECT * FROM molecules WHERE molecule_id=?',(e['molecule_id'],)).fetchone()
        if r is None:return False,None
        receipt=json.loads(r['receipt_json']) if r['receipt_json'] else None
        good=(r['state']==e['desired_state'] and r['attempt']==e['context']['attempt_id'] and receipt is not None
              and receipt['context']==e['context'] and receipt['counts']==e['receipt']['counts'])
    elif kind=='RELEASE_TERMINAL_INCOMPLETE':
        b=action['before'];r=db.execute('SELECT * FROM molecules WHERE molecule_id=?',(b['molecule_id'],)).fetchone()
        good=r is not None and r['state']==action['desired_state'] and r['owner'] is None and r['attempt']==b['attempt']
    elif kind=='RESET_TERMINAL_EXPORT_CLAIM':
        r=db.execute('SELECT * FROM export_repairs WHERE run_root=?',(action['before']['run_root'],)).fetchone()
        good=r is not None and r['state']=='ERROR' and r['error']=='TERMINAL_METADATA_RECONCILIATION_RETRYABLE_NO_QM'
    else:
        r=db.execute('SELECT * FROM tasks WHERE task_id=?',(action['before']['task_id'],)).fetchone();good=r is not None and r['state']=='DEAD'
    return bool(good),dict(r) if r is not None else None
def apply(args):
    H.node_guard();path=Path(args.plan)
    if H.digest(path)!=args.expected_plan_sha256:raise ValueError('REVIEWED_PLAN_EXACT_SHA_REQUIRED')
    p=H.load(path)
    if p['status']!='REVIEWABLE_TERMINAL_SUBSET_DRY_RUN' or p['conflicts']:raise ValueError('CONFLICT_FREE_TERMINAL_SUBSET_PLAN_REQUIRED')
    if H.digest(__file__)!=p['source_sha256'] or H.digest(H.__file__)!=p['helper']['sha256']:raise ValueError('SOURCE_CHANGED_AFTER_REVIEW')
    out=Path(args.out)
    if not out.resolve().is_relative_to((ROOT/'reports').resolve()):raise ValueError('NEW_ROOT_REPORT_ONLY')
    out.mkdir(parents=True,exist_ok=False)
    for ref in p['manifests']+p['registered_receipts']:
        if H.digest(ref['path'])!=ref['sha256']:raise ValueError('ACTUAL_SUBMISSION_OR_RECEIPT_CHANGED')
    jobs,refs,receipts=registry([r['path'] for r in p['manifests']])
    if jobs!=p['registered_jobs']:raise ValueError('REGISTERED229_JOB_MAP_CHANGED')
    proof=H.terminal_proof(list(jobs),out);live,live_tasks=protection(jobs,proof)
    for name in ('actions','run_reports','export_roots','already_closed_roots','skipped','queue_snapshot'):
        ref=p[name]
        if H.digest(ref['path'])!=ref['sha256']:raise ValueError('REVIEWED_PLAN_LEAF_CHANGED:'+name)
    for r in H.load(p['run_reports']['path']):
        if H.digest(Path(r['run_root'])/'run.json')!=r['run_json_sha256'] or H.digest(r['evidence_file']['path'])!=r['evidence_file']['sha256']:raise ValueError('OLD_RUN_EVIDENCE_CHANGED')
    actions=H.load(p['actions']['path']);results=[]
    db=sqlite3.connect(p['queue'],timeout=1,isolation_level=None);db.row_factory=sqlite3.Row
    db.execute('PRAGMA busy_timeout=1000');db.execute('PRAGMA synchronous=FULL')
    try:
        if dict(db.execute('SELECT key,value FROM meta')).get('plan_sha256')!=p['queue_plan_sha256']:raise ValueError('POPULATION_SCOPE_CHANGED')
        with (out/'mutation_journal.jsonl').open('x') as journal:
            for i,action in enumerate(actions):
                # A fresh actual live/PD state or changed ownership skips that
                # action without pausing healthy science or rewriting its row.
                reason=current_action_guard(db,action,jobs,proof,live_tasks)
                if reason:
                    results.append({'index':i,'kind':action['kind'],'status':reason});continue
                if action['kind']=='RESTORE_DURABLE_COMPLETION':candidate_readback(action['evidence'])
                journal.write(json.dumps({'event':'BEFORE','index':i,'action':action},separators=(',',':'),allow_nan=False)+'\n');journal.flush();os.fsync(journal.fileno())
                def mutation():
                    reason=current_action_guard(db,action,jobs,proof,live_tasks)
                    return reason if reason else H.action_apply(db,action)
                try:status=H.retry_transaction(db,mutation)
                except ValueError as exc:
                    if 'CHANGED_SINCE_REVIEW' in str(exc):status='SKIP_ROW_CHANGED_SINCE_REVIEW'
                    else:raise
                verified,after=verify_after(db,action) if status in {'APPLIED','ALREADY_APPLIED'} else (False,None)
                row={'index':i,'kind':action['kind'],'status':status,'verified':verified,'after':after};results.append(row)
                journal.write(json.dumps({'event':'AFTER',**row})+'\n');journal.flush();os.fsync(journal.fileno())
    finally:db.close()
    all_verified=all(r['status'] in {'APPLIED','ALREADY_APPLIED'} and r.get('verified') is True for r in results)
    full_terminal_scope=proof['all_terminal'] and not p['protected_jobs']
    full_scope_verified=full_terminal_scope and not p['skipped']['count'] and all_verified
    status='APPLIED_AND_VERIFIED' if full_scope_verified else ('TERMINAL_SUBSET_APPLIED_AND_VERIFIED' if all_verified and not full_terminal_scope else 'TERMINAL_SUBSET_APPLY_RECORDED_SKIPS_OR_UNVERIFIED')
    report={'schema':'WP5_TERMINAL_SUBSET_RECONCILIATION_APPLY_V3','status':status,'implementation_version':IMPLEMENTATION_VERSION,
            'source':{'path':__file__,'sha256':H.digest(__file__)},'helper':p['helper'],
            'prior_submissions':p['manifests'],'original_jobs':sorted(jobs),'original_job_count':len(jobs),
            'all_registered_jobs_terminal':proof['all_terminal'],'plan_was_all229_terminal':not bool(p['protected_jobs']),
            'all_applied_rows_verified':all_verified,'plan_skipped_count':p['skipped']['count'],'full229_terminal_scope_verified':full_scope_verified,'mutation_journal':{'path':str(out/'mutation_journal.jsonl'),'sha256':H.digest(out/'mutation_journal.jsonl')},
            'plan':{'path':str(path),'sha256':args.expected_plan_sha256},'accounting':proof,
            'protected_jobs':{j:proof['states'][j] for j in sorted(live)},'protected_tasks':sorted(live_tasks),
            'results':results,'result_counts':dict(Counter(r['status'] for r in results)),
            'queue_modified':any(r['status']=='APPLIED' for r in results),'QM_started':False,'original_LMDB_opened':False,
            'historical_files_modified':False,'global_STOP_changed_or_required':False,'scientific_attempts_reset':False,
            'old_SCI_contract_package_execution_provenance_preserved':True,'export_repair_separate_no_QM_step':p['export_roots']}
    H.write_json(out/'report.json',report);print(json.dumps({'status':report['status'],'results':report['result_counts'],'protected_jobs':report['protected_jobs']}));return 0

def check_bounded_readonly():
    import tempfile
    with tempfile.TemporaryDirectory(prefix='wp5_ro_fixture_') as td:
        path=Path(td)/'test_only.sqlite';db=sqlite3.connect(path)
        db.execute('CREATE TABLE sample(value INTEGER)');db.executemany('INSERT INTO sample VALUES(?)',[(1,),(2,)])
        db.commit();db.close();ro=BoundedReadonly(path)
        result=ro.execute('SELECT value FROM sample ORDER BY value')
        # Results survive connection closure: the source cursor has already closed.
        ro.close();assert result.fetchone()[0]==1 and result.fetchall()[0][0]==2
        ro=BoundedReadonly(path)
        try:ro.execute('INSERT INTO sample VALUES(3)');raise AssertionError('read-only write allowed')
        except sqlite3.OperationalError as exc:assert not read_lock_error(exc)
        finally:ro.close()
    assert read_lock_error(sqlite3.OperationalError('database is locked'))
    assert not read_lock_error(sqlite3.OperationalError('disk I/O error'))
    print('V4_DETACHED_READONLY_BUSY_ONLY_FIXTURE_PASS_NO_FORMAL_DB')
def check():
    import ast
    ast.parse(Path(__file__).read_text());H.check();check_bounded_readonly()
    jobs={'dead':{'task_id':'t0','mode':'main'},'live':{'task_id':'t1','mode':'main'},'pd':{'task_id':'t2','mode':'main'}}
    proof={'states':{'dead':'FAILED','live':'RUNNING','pd':'PENDING'}};live,tasks=protection(jobs,proof)
    sessions={'s0':'dead','s1':'live','s2':'pd'}
    assert live=={'live','pd'} and tasks=={'t1','t2'}
    assert guard({'task_id':'t1','owner':'s0','state':'RUNNING'},sessions,jobs,proof,tasks)=='SKIP_ACTIVE_OR_PD_TASK'
    assert guard({'task_id':'t0','owner':'s1','state':'RUNNING'},sessions,jobs,proof,tasks)=='SKIP_ACTIVE_OR_PD_OWNER_SESSION'
    assert guard({'task_id':'t0','owner':'s2','state':'RUNNING'},sessions,jobs,proof,tasks)=='SKIP_ACTIVE_OR_PD_OWNER_SESSION'
    assert guard({'task_id':'t0','owner':'unknown','state':'RUNNING'},sessions,jobs,proof,tasks)=='SKIP_UNKNOWN_OWNER_JOB'
    assert guard({'task_id':'t0','owner':'s0','state':'RUNNING'},sessions,jobs,proof,tasks) is None
    assert guard({'task_id':'t0','owner':None,'state':'RUNNING'},sessions,jobs,proof,tasks)=='SKIP_RUNNING_WITH_UNKNOWN_OWNER'
    assert root_for_archive('/r/job/temporary_lanes/lane.sqlite')=='/r/job'
    assert root_for_archive('/r/job/raw_archive.sqlite')=='/r/job'
    print('TERMINAL_SUBSET229_GUARD_FIXTURES_PASS_NO_QM_NO_LMDB_NO_FORMAL_QUEUE')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--mode',choices=('dry-run','plan','apply'),default='dry-run')
    p.add_argument('--manifests',type=Path,nargs=3,default=list(MANIFESTS));p.add_argument('--queue',type=Path,default=ROOT/'queue/pending.sqlite')
    p.add_argument('--workers',type=int,default=16);p.add_argument('--out',type=Path);p.add_argument('--plan',type=Path);p.add_argument('--expected-plan-sha256')
    args=p.parse_args()
    if args.check:check()
    else:
        if not args.out:p.error('--out required')
        if args.mode!='apply' and args.workers<16:p.error('at least16 SCI workers required')
        if args.mode=='apply' and (not args.plan or not args.expected_plan_sha256):p.error('explicit --plan and --expected-plan-sha256 required')
        raise SystemExit(apply(args) if args.mode=='apply' else dry_run(args))
