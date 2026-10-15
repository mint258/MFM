"""Read-only by default. Terminal subset of385 actual WP5 submissions only.
Reuse frozen v2 SCI/receipt validators; never change scientific outputs or jobs.
Live/PD/unknown ownership is excluded both at planning and explicit Root apply.
"""
from __future__ import annotations
import argparse,concurrent.futures,json,multiprocessing,os,sqlite3,time,traceback
from collections import Counter
from pathlib import Path
import wp5_queue_reconcile_v2 as H
ROOT=H.ROOT
MANIFESTS=(ROOT/'submission/submitted_jobs.json',ROOT/'submission/recovery_attempt_v11/submitted_jobs.json',ROOT/'submission/startup_replacement_v1/submitted_jobs.json',ROOT/'submission/recovery_attempt_v13/submitted_jobs.json',ROOT/'submission/recovery_attempt_v14/submitted_jobs.json')
HELPER_SHA='fa8ff8c76b8be5de3aca269ad6c155ec18825bc18ab6facece9824c5e8208e84'
EXPECTED=((72,6),(72,6),(69,4),(72,6),(72,6))
IMPLEMENTATION_VERSION=7
SCOPE=ROOT/'configs/terminal_phase14_export9_repair_scope_v1.json'
SCOPE_SHA='ccd3eab4339dd7cdc87b2a06216194bab51973fa8c473353e076a228249ae5f4'
CONTROL_JOBMAP=ROOT/'reports/wp5_acceptance_control_jobmap_actual385_v1.json'
CONTROL_JOBMAP_SHA='74f0410be60d7ea84c7aaec2278a7be9361d396c1fc1fea3d096eb39100ba4e9'
def control_scope():
    if H.digest(SCOPE)!=SCOPE_SHA:raise ValueError('IMMUTABLE_PHASE14_REPAIR_SCOPE_CHANGED')
    doc=H.load(SCOPE)
    if doc.get('schema')!='WP5_PHASE14_TERMINAL_EXPORT9_SCOPE_V1' or len(doc.get('roots',[]))!=9:raise ValueError('ACTUAL9_METADATA_SCOPE_REQUIRED')
    return doc

# Reuse the already validated776 recovery adapter only for the metadata queue.
# Its own strict scope guard leaves all SCI/LMDB readers in mode=ro.
import wp5_terminal_export_repair_v3 as METADATA
METADATA_READER_REFS=[
    {'path':METADATA.__file__,'sha256':'0df082e336f58bf00b72c3c423c833b9316afd3f461b3265a72b52fe3e0d7b6d','role':'776_metadata_recovery_reader'},
    {'path':METADATA.V.__file__,'sha256':'69f5b92237c522eba1176c842ce152e5af87d915dbe8ba6d822d9477f68c5e18','role':'120s_busy_only_detached_read_base'}]
for ref in METADATA_READER_REFS:
    if H.digest(ref['path'])!=ref['sha256']:
        raise ValueError('FROZEN_METADATA_READER_SOURCE_DIFFERS:'+ref['path'])
BoundedReadonly=METADATA.MetadataRead
DetachedReadResult=METADATA.V.DetachedReadResult
read_lock_error=METADATA.V.read_lock_error
READ_RETRY_EVENTS=METADATA.V.READ_RETRY_EVENTS
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
    if len(paths)!=5:raise ValueError('EXACT_FIVE_ACTUAL_MANIFESTS_REQUIRED')
    if [Path(p).resolve() for p in paths]!=[p.resolve() for p in MANIFESTS]:raise ValueError('EXACT_FIVE_ACTUAL385_SUBMISSIONS_REQUIRED')
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
    if len(jobs)!=385:raise ValueError('EXACT385_ACTUAL_JOB_IDS_REQUIRED')
    scope=control_scope()
    if [{'path':ref['path'],'sha256':ref['sha256']} for ref in refs]!=scope['manifests']:raise ValueError('ACTUAL385_SCOPE_MANIFEST_SHA_DIFFERS')
    if H.digest(CONTROL_JOBMAP)!=CONTROL_JOBMAP_SHA:raise ValueError('ACTUAL385_CONTROL_JOBMAP_CHANGED')
    declared=H.load(CONTROL_JOBMAP)
    rows=declared['jobs'];mapped={str(row['job_id']):row for row in rows}
    if declared.get('actual_job_count')!=385 or len(mapped)!=385 or set(mapped)!=set(jobs):raise ValueError('ACTUAL385_CONTROL_JOBMAP_ID_DIFFERS')
    if any(mapped[j]['node']!=jobs[j]['node'] or str(mapped[j]['task_id'])!=jobs[j]['task_id'] for j in jobs):raise ValueError('ACTUAL385_CONTROL_JOBMAP_NODE_TASK_DIFFERS')
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

def phase14_diagnostic_pass(queue,session_ids,job_ids):
    """PK512 non-atomic diagnostic; no live cursor crosses a chunk."""
    started=time.time();last=None;rows_seen=chunks=0
    owners={'molecules':0,'records':0};receipts={'molecules':0,'records':0}
    while True:
        q=H.readonly(queue)
        try:
            if last is None:
                batch=q.execute("SELECT molecule_id,owner,record_count,receipt_json FROM molecules ORDER BY molecule_id LIMIT ?",(512,)).fetchall()
            else:
                batch=q.execute("SELECT molecule_id,owner,record_count,receipt_json FROM molecules WHERE molecule_id>? ORDER BY molecule_id LIMIT ?",(last,512)).fetchall()
            batch=[dict(row) for row in batch]
        finally:q.close()
        if not batch:break
        chunks+=1;rows_seen+=len(batch)
        for row in batch:
            if row['owner'] in session_ids:
                owners['molecules']+=1;owners['records']+=row['record_count']
            if row['receipt_json'] is not None:
                receipt=json.loads(row['receipt_json'])
                if str((receipt.get('context') or {}).get('job_id')) in job_ids:
                    receipts['molecules']+=1;receipts['records']+=row['record_count']
        last=batch[-1]['molecule_id']
    return owners,receipts,{'started_epoch':started,'finished_epoch':time.time(),
        'atomic':False,'chunk_size':512,'nonempty_chunks':chunks,'rows_observed':rows_seen,
        'EOF_observed':True,'last_primary_key':last,
        'scope':'Sequential materialized PK chunks; each reader/cursor closed before Python aggregation and the next chunk. Concurrent inserts below the passed PK or later updates are outside this non-atomic diagnostic.'}

def latest_phase_metadata(snapshot,queue):
    """Session claims are from queue_snapshot; owner/receipt counts cover an interval."""
    phase=H.load(MANIFESTS[-1]);ids={str(row['job_id']) for row in phase['main']+phase['cleanup']}
    sessions=[row for row in snapshot['sessions'] if str(row['job_id']) in ids]
    unknown=[row['session_id'] for row in sessions if not isinstance(row.get('claims'),int) or row['claims']<0]
    claims=None if unknown else sum(row['claims'] for row in sessions)
    owners,receipts,interval=phase14_diagnostic_pass(queue,{row['session_id'] for row in sessions},ids)
    previous=control_scope()['previous307_apply']
    if H.digest(previous['path'])!=previous['sha256']:raise ValueError('ACTUAL_PRE_PHASE14_FULL307_APPLY_CHANGED')
    prior=H.load(previous['path'])
    if prior.get('original_job_count')!=307 or prior.get('status')!='APPLIED_AND_VERIFIED' or prior.get('full307_terminal_scope_verified') is not True:
        raise ValueError('ACTUAL_PRE_PHASE14_FULL307_APPLY_REQUIRED')
    present={str(row['job_id']) for row in sessions}
    return {'manifest':{'path':str(MANIFESTS[-1]),'sha256':H.digest(MANIFESTS[-1])},
        'actual_jobs':sorted(ids),'actual_sessions':sessions,'actual_session_count':len(sessions),
        'jobs_without_session':sorted(ids-present),'unknown_claim_counters':unknown,
        'durable_session_claims':claims,'session_claims_scope':'Earlier queue_snapshot.sessions; unknown counters remain None. Not atomic with the following owner/receipt pass.',
        'current_owned_rows':owners,'SCI_receipts_bound_to_phase14_jobs':receipts,
        'diagnostic_interval':interval,
        'zero_claims_and_SCI_receipts_observed':claims==0 and owners['molecules']==0 and receipts['molecules']==0,
        'previous307_apply':previous,'scope':'Actual durable session counters plus a completed PK512 diagnostic interval; no-session jobs explicit. No atomic whole-population time point or QM status is claimed.'}

def check_pk512_diagnostic():
    import tempfile
    with tempfile.TemporaryDirectory(prefix='wp5_r7_pk512_',dir='/tmp') as td:
        path=Path(td)/'metadata.sqlite';db=sqlite3.connect(path)
        db.execute('CREATE TABLE molecules(molecule_id TEXT PRIMARY KEY,owner TEXT,record_count INTEGER,receipt_json TEXT)')
        for i in range(513):
            owner=('fixture_phase_a','fixture_phase_b','fixture_outside',None)[i%4]
            job=('4514407','4514413','fixture_outside')[i%3]
            db.execute('INSERT INTO molecules VALUES(?,?,?,?)',(f'{i:06d}',owner,1+i%3,json.dumps({'context':{'job_id':job}})))
        db.commit();db.close()
        original=H.readonly;writes=[];read_stats=[]
        class TrackingReader:
            def __init__(self,p):self.real=original(p);self.p=p
            def execute(self,sql,parameters=()):
                assert 'json_extract' not in sql and 'LIMIT ?' in sql and parameters[-1]==512
                return self.real.execute(sql,parameters)
            def close(self):
                self.real.close();read_stats.append(dict(self.real.stats))
                if not writes:
                    writer=sqlite3.connect(self.p,timeout=.01)
                    try:
                        writer.execute('BEGIN IMMEDIATE')
                        writer.execute('INSERT INTO molecules VALUES(?,?,?,?)',('000513','fixture_phase_b',7,json.dumps({'context':{'job_id':'4514407'}})))
                        writer.commit();writes.append('COMMITTED_BETWEEN_PK_CHUNKS')
                    finally:writer.close()
        H.readonly=TrackingReader
        try:owners,receipts,interval=phase14_diagnostic_pass(path,{'fixture_phase_a','fixture_phase_b'},{'4514407','4514413'})
        finally:H.readonly=original
        db=sqlite3.connect(path)
        try:
            old_owners=db.execute("SELECT count(*),coalesce(sum(record_count),0) FROM molecules WHERE owner IN (?,?)",('fixture_phase_a','fixture_phase_b')).fetchone()
            old_receipts=db.execute("SELECT count(*),coalesce(sum(record_count),0) FROM molecules WHERE receipt_json IS NOT NULL AND cast(json_extract(receipt_json,'$.context.job_id') AS TEXT) IN (?,?)",('4514407','4514413')).fetchone()
        finally:db.close()
        assert (owners['molecules'],owners['records'])==old_owners==(258,522)
        assert (receipts['molecules'],receipts['records'])==old_receipts==(343,520)
        assert interval['EOF_observed'] and not interval['atomic'] and interval['rows_observed']==514 and interval['nonempty_chunks']==2
        assert writes==['COMMITTED_BETWEEN_PK_CHUNKS']
        print(json.dumps({'fixture':'PRIVATE_PK512_METADATA','initial_rows':513,'observed_rows':514,'owner_counts':owners,'receipt_counts':receipts,'old_SQL_counts_match':True,'writer_interleave':writes,'diagnostic_interval':interval,'production_SQL_run':False}))
def population_closure(snapshot):
    molecules=sum(row['molecules'] for row in snapshot['states'])
    records=sum(row['records'] for row in snapshot['states'])
    return {'observed_molecules':molecules,'observed_records':records,
        'formal_molecules':1220466,'formal_records':11231854,'population_closed':(molecules,records)==(1220466,11231854),
        'requested_calc_types':list(H.CALCS),'requested_task_outcomes':12*records,
        'scope':'Requested full population12N denominator; existing SCI root closure/readback evidence remains separate.'}

def dry_run(args):
    H.node_guard()
    if H.digest(H.__file__)!=HELPER_SHA:raise ValueError('FROZEN_V2_VALIDATOR_CHANGED')
    out=Path(args.out)
    if not out.resolve().is_relative_to((ROOT/'reports').resolve()) or Path(args.queue).resolve()!=(ROOT/'queue/pending.sqlite').resolve():raise ValueError('FORMAL_QUEUE_NEW_REPORT_ROOT_REQUIRED')
    out.mkdir(parents=True,exist_ok=False)
    jobs,manifests,receipts=registry(args.manifests);proof=H.terminal_proof(list(jobs),out)
    live,live_tasks=protection(jobs,proof)
    snapshot=H.queue_snapshot(args.queue);H.write_json(out/'queue_snapshot.json',snapshot)
    phase_metadata=latest_phase_metadata(snapshot,args.queue);population=population_closure(snapshot)
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
    if not population['population_closed']:conflicts.append({'classification':'FORMAL_POPULATION_COUNT_MISMATCH','observed':population})
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
          'created_epoch':time.time(),'implementation_version':IMPLEMENTATION_VERSION,'source_sha256':H.digest(__file__),'metadata_reader_sources':METADATA_READER_REFS,'helper':{'path':H.__file__,'sha256':HELPER_SHA},'queue':str(args.queue),
          'control_jobmap':{'path':str(CONTROL_JOBMAP),'sha256':CONTROL_JOBMAP_SHA},'repair_scope':{'path':str(SCOPE),'sha256':SCOPE_SHA},'manifests':manifests,'registered_receipts':receipts,'registered_jobs':jobs,'registered_jobs_count':len(jobs),'accounting':proof,'all_registered_jobs_terminal':proof['all_terminal'],'plan_was_all385_terminal':not bool(live),
          'latest_phase_metadata':phase_metadata,'population_closure':population,
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
    if p.get('metadata_reader_sources')!=METADATA_READER_REFS:raise ValueError('METADATA_READER_SOURCE_BINDING_DIFFERS')
    out=Path(args.out)
    if not out.resolve().is_relative_to((ROOT/'reports').resolve()):raise ValueError('NEW_ROOT_REPORT_ONLY')
    out.mkdir(parents=True,exist_ok=False)
    for ref in p['manifests']+p['registered_receipts']:
        if H.digest(ref['path'])!=ref['sha256']:raise ValueError('ACTUAL_SUBMISSION_OR_RECEIPT_CHANGED')
    jobs,refs,receipts=registry([r['path'] for r in p['manifests']])
    if jobs!=p['registered_jobs']:raise ValueError('REGISTERED385_JOB_MAP_CHANGED')
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
            'source':{'path':__file__,'sha256':H.digest(__file__)},'metadata_reader_sources':METADATA_READER_REFS,'helper':p['helper'],
            'control_jobmap':p['control_jobmap'],'repair_scope':p['repair_scope'],'prior_submissions':p['manifests'],'original_jobs':sorted(jobs),'original_job_count':len(jobs),'registered_jobs_count':len(jobs),
            'latest_phase_metadata':p['latest_phase_metadata'],'population_closure':p['population_closure'],
            'all_registered_jobs_terminal':proof['all_terminal'],'plan_was_all385_terminal':not bool(p['protected_jobs']),
            'all_applied_rows_verified':all_verified,'plan_skipped_count':p['skipped']['count'],'full385_terminal_scope_verified':full_scope_verified,'mutation_journal':{'path':str(out/'mutation_journal.jsonl'),'sha256':H.digest(out/'mutation_journal.jsonl')},
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
    ast.parse(Path(__file__).read_text());scope=control_scope()
    assert len(MANIFESTS)==len(EXPECTED)==5 and sum(sum(pair) for pair in EXPECTED)==385
    own=scope['roots'][0];dead=own['job_id'];live='4514410'
    jobs={dead:{'task_id':own['task_id'],'mode':'main'},live:{'task_id':'live_fixture','mode':'main'}}
    proof={'states':{dead:'COMPLETED',live:'RUNNING'}};protected,tasks=protection(jobs,proof)
    assert protected=={live} and tasks=={'live_fixture'}
    assert guard({'task_id':own['task_id'],'owner':'dead_fixture','state':'COMPLETE'}, {'dead_fixture':dead},jobs,proof,tasks,dead) is None
    assert guard({'task_id':own['task_id'],'owner':'live_fixture','state':'RUNNING'}, {'live_fixture':live},jobs,proof,tasks,dead)=='SKIP_ACTIVE_OR_PD_OWNER_SESSION'
    assert guard({'task_id':'live_fixture','owner':'dead_fixture','state':'RUNNING'}, {'dead_fixture':dead},jobs,proof,tasks,dead)=='SKIP_ACTIVE_OR_PD_TASK'
    check_pk512_diagnostic()
    print('RECONCILE_V7_PRIVATE_METADATA_SHAPE_GUARD_PASS_NO_SCI_NO_QUEUE')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--mode',choices=('dry-run','plan','apply'),default='dry-run')
    p.add_argument('--manifests',type=Path,nargs=5,default=list(MANIFESTS));p.add_argument('--queue',type=Path,default=ROOT/'queue/pending.sqlite')
    p.add_argument('--workers',type=int,default=16);p.add_argument('--out',type=Path);p.add_argument('--plan',type=Path);p.add_argument('--expected-plan-sha256')
    args=p.parse_args()
    if args.check:
        check()
    else:
        if not args.out:p.error('--out required')
        if args.mode!='apply' and args.workers<16:p.error('at least16 SCI workers required')
        if args.mode=='apply' and (not args.plan or not args.expected_plan_sha256):p.error('explicit --plan and --expected-plan-sha256 required')
        raise SystemExit(apply(args) if args.mode=='apply' else dry_run(args))
