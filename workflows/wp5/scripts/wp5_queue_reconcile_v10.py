"""Read-only by default. Terminal subset of463 actual WP5 submissions only.
Reuse frozen v2 SCI/receipt validators; never change scientific outputs or jobs.
Live/PD/unknown ownership is excluded both at planning and explicit Root apply.
"""
from __future__ import annotations
import argparse,concurrent.futures,json,multiprocessing,os,sqlite3,time,traceback
from collections import Counter
from pathlib import Path
import wp5_queue_reconcile_v2 as H
ROOT=H.ROOT
MANIFESTS=(ROOT/'submission/submitted_jobs.json',ROOT/'submission/recovery_attempt_v11/submitted_jobs.json',ROOT/'submission/startup_replacement_v1/submitted_jobs.json',ROOT/'submission/recovery_attempt_v13/submitted_jobs.json',ROOT/'submission/recovery_attempt_v14/submitted_jobs.json',ROOT/'submission/recovery_attempt_v15/submitted_jobs.json')
HELPER_SHA='fa8ff8c76b8be5de3aca269ad6c155ec18825bc18ab6facece9824c5e8208e84'
EXPECTED=((72,6),(72,6),(69,4),(72,6),(72,6),(72,6))
IMPLEMENTATION_VERSION=10
SCOPE=ROOT/'configs/terminal_phase15_recovery_scope_v1.json'
SCOPE_SHA='ee3349bcbfdad4822d2fddbea547645f23eb5298b633d4c12ca9f01865217be2'
def configure_scope(path,sha256):
    global SCOPE,SCOPE_SHA
    SCOPE=Path(path);SCOPE_SHA=sha256

def control_scope():
    if H.digest(SCOPE)!=SCOPE_SHA:raise ValueError('IMMUTABLE_PHASE15_RECOVERY_SCOPE_CHANGED')
    doc=H.load(SCOPE)
    if doc.get('schema')!='WP5_PHASE15_TERMINAL_RECOVERY_SCOPE_V1':raise ValueError('ACTUAL_PHASE15_SCOPE_REQUIRED')
    if len(doc.get('manifests',[]))!=6 or doc.get('jobmap',{}).get('actual_job_count')!=463:raise ValueError('ACTUAL463_SCOPE_REQUIRED')
    for ref in [doc['jobmap'],doc['previous385_apply'],doc['latest_phase_manifest']]+doc['manifests']:
        if H.digest(ref['path'])!=ref['sha256']:raise ValueError('ACTUAL_SCOPE_REFERENCE_CHANGED:'+ref['path'])
    if doc['latest_phase_manifest']!=doc['manifests'][-1]:raise ValueError('LATEST_PHASE_MANIFEST_REFERENCE_DIFFERS')
    incident=doc['incident']
    for key in ('STOP','foreign_repair_receipt','victim_completion'):
        ref=incident[key]
        if H.digest(ref['path'])!=ref['sha256']:raise ValueError('INCIDENT_EVIDENCE_CHANGED:'+key)
    root=Path(incident['victim_run_root']);run=H.load(root/'run.json');opt=run['options']
    stop=H.load(incident['STOP']['path'])
    if stop.get('reason')!='RAW_ARCHIVE_DURABILITY_FAILURE_LOCAL_EVIDENCE_PRESERVED':raise ValueError('EXACT_ARCHIVE_INCIDENT_REQUIRED')
    if str(stop.get('job_id'))!=str(opt['job_id']):raise ValueError('INCIDENT_SOURCE_JOB_DIFFERS')
    actual=[]
    for worker in H.load(incident['victim_completion']['path'])['workers']:
        for error in worker.get('errors',[]):
            text=error.get('error','')
            if 'wp5_archive_v5.py' not in text or 'sqlite3.OperationalError: attempt to write a readonly database' not in text:
                raise ValueError('NONINCIDENT_WORKER_ERROR_IN_SCOPE')
            actual.append({'molecule_id':error['molecule_id'],'lane':worker['lane'],'worker_error_sha256':H.sha(text.encode('utf-8'))})
    declared=incident['infra_failure_molecules']
    key=lambda row:(row['molecule_id'],row['lane'],row['worker_error_sha256'])
    if len(actual)!=24 or len({r['molecule_id'] for r in actual})!=24 or sorted(actual,key=key)!=sorted(declared,key=key):
        raise ValueError('ACTUAL24_ARCHIVE_ERROR_SCOPE_DIFFERS')
    roots=doc.get('roots',[])
    if len({r['run_root'] for r in roots})!=len(roots):raise ValueError('PHASE15_ROOT_DUPLICATE')
    for row in roots:
        path=Path(row['run_root'])/'run.json'
        if H.digest(path)!=row['run_json_sha256']:raise ValueError('PHASE15_RUN_JSON_CHANGED')
        run=H.load(path);o=run['options']
        if any(str(o[k])!=str(row[k]) for k in ('job_id','task_id','session','mode')) or run['node']!=row['node']:
            raise ValueError('PHASE15_ROOT_IDENTITY_DIFFERS')
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
    if len(paths)!=6:raise ValueError('EXACT_SIX_ACTUAL_MANIFESTS_REQUIRED')
    if [Path(p).resolve() for p in paths]!=[p.resolve() for p in MANIFESTS]:raise ValueError('EXACT_SIX_ACTUAL463_SUBMISSIONS_REQUIRED')
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
    if len(jobs)!=463:raise ValueError('EXACT463_ACTUAL_JOB_IDS_REQUIRED')
    scope=control_scope()
    if [{'path':ref['path'],'sha256':ref['sha256']} for ref in refs]!=scope['manifests']:raise ValueError('ACTUAL463_SCOPE_MANIFEST_SHA_DIFFERS')
    jobmap=scope['jobmap']
    declared=H.load(jobmap['path'])
    rows=declared['jobs'];mapped={str(row['job_id']):row for row in rows}
    if declared.get('actual_job_count')!=463 or len(mapped)!=463 or set(mapped)!=set(jobs):raise ValueError('ACTUAL463_CONTROL_JOBMAP_ID_DIFFERS')
    if any(mapped[j]['node']!=jobs[j]['node'] or str(mapped[j]['task_id'])!=jobs[j]['task_id'] for j in jobs):raise ValueError('ACTUAL463_CONTROL_JOBMAP_NODE_TASK_DIFFERS')
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

def phase15_diagnostic_pass(queue,session_ids,job_ids):
    """PK512 non-atomic diagnostic; no live cursor crosses a chunk."""
    started=time.time();last=None;rows_seen=chunks=0
    owners={'molecules':0,'records':0};receipts={'molecules':0,'records':0};identities=[]
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
                    identities.append({'molecule_id':row['molecule_id'],'attempt_id':receipt['context']['attempt_id'],'execution_id':receipt['context']['execution_id'],'job_id':str(receipt['context']['job_id'])})
        last=batch[-1]['molecule_id']
    return owners,receipts,{'current_phase_receipt_identities':identities,'started_epoch':started,'finished_epoch':time.time(),
        'atomic':False,'chunk_size':512,'nonempty_chunks':chunks,'rows_observed':rows_seen,
        'EOF_observed':True,'last_primary_key':last,
        'scope':'Sequential materialized PK chunks; each reader/cursor closed before Python aggregation and the next chunk. Concurrent inserts below the passed PK or later updates are outside this non-atomic diagnostic.'}

def latest_phase_metadata(snapshot,queue):
    """Session claims are from queue_snapshot; owner/receipt counts cover an interval."""
    phase=H.load(MANIFESTS[-1]);ids={str(row['job_id']) for row in phase['main']+phase['cleanup']}
    sessions=[row for row in snapshot['sessions'] if str(row['job_id']) in ids]
    unknown=[row['session_id'] for row in sessions if not isinstance(row.get('claims'),int) or row['claims']<0]
    claims=None if unknown else sum(row['claims'] for row in sessions)
    owners,receipts,interval=phase15_diagnostic_pass(queue,{row['session_id'] for row in sessions},ids)
    previous=control_scope()['previous385_apply']
    if H.digest(previous['path'])!=previous['sha256']:raise ValueError('ACTUAL_PRE_PHASE15_FULL385_APPLY_CHANGED')
    prior=H.load(previous['path'])
    if prior.get('original_job_count')!=385 or prior.get('status')!='APPLIED_AND_VERIFIED' or prior.get('full385_terminal_scope_verified') is not True:
        raise ValueError('ACTUAL_PRE_PHASE15_FULL385_APPLY_REQUIRED')
    present={str(row['job_id']) for row in sessions}
    return {'manifest':{'path':str(MANIFESTS[-1]),'sha256':H.digest(MANIFESTS[-1])},
        'actual_jobs':sorted(ids),'actual_sessions':sessions,'actual_session_count':len(sessions),
        'jobs_without_session':sorted(ids-present),'unknown_claim_counters':unknown,
        'durable_session_claims':claims,'session_claims_scope':'Earlier queue_snapshot.sessions; unknown counters remain None. Not atomic with the following owner/receipt pass.',
        'current_owned_rows':owners,'SCI_receipts_bound_to_phase15_jobs':receipts,
        'diagnostic_interval':{k:v for k,v in interval.items() if k!='current_phase_receipt_identities'},
        'current_phase_receipt_identities':interval['current_phase_receipt_identities'],
        'zero_claims_and_SCI_receipts_observed':claims==0 and owners['molecules']==0 and receipts['molecules']==0,
        'previous385_apply':previous,'scope':'Actual durable session counters plus a completed PK512 diagnostic interval; no-session jobs explicit. No atomic whole-population time point or QM status is claimed.'}

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
        try:owners,receipts,interval=phase15_diagnostic_pass(path,{'fixture_phase_a','fixture_phase_b'},{'4514407','4514413'})
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
# Process-local control adapter only; frozen helper source remains untouched.
LEGACY_QUEUE_SNAPSHOT=H.queue_snapshot

def queue_snapshot_rowid512(path):
    """Stable rowid-prefix interval; no source cursor survives a bounded page."""
    started=time.time()
    db=H.readonly(path)
    try:
        meta=dict(db.execute('SELECT key,value FROM meta'))
        tasks=[dict(row) for row in db.execute('SELECT * FROM tasks ORDER BY task_id')]
        sessions=[dict(row) for row in db.execute('SELECT * FROM sessions ORDER BY session_id')]
        repairs=[dict(row) for row in db.execute('SELECT * FROM export_repairs ORDER BY run_root')]
        end_rowid=db.execute('SELECT max(rowid) FROM molecules').fetchone()[0]
    finally:db.close()
    states={};by_task={};running=[];last=None;visited=chunks=0
    def add(target,key,row):
        item=target.setdefault(key,{'molecules':0,'records':None,'predicted_seconds':None})
        item['molecules']+=1
        for field,column in (('records','record_count'),('predicted_seconds','predicted_seconds')):
            value=row[column]
            if value is not None:item[field]=value if item[field] is None else item[field]+value
    while end_rowid is not None:
        db=H.readonly(path)
        try:
            if last is None:
                batch=db.execute('SELECT rowid AS _control_rowid,molecule_id,state,task_id,record_count,predicted_seconds FROM molecules WHERE rowid<=? ORDER BY rowid LIMIT ?',(end_rowid,512)).fetchall()
            else:
                batch=db.execute('SELECT rowid AS _control_rowid,molecule_id,state,task_id,record_count,predicted_seconds FROM molecules WHERE rowid>? AND rowid<=? ORDER BY rowid LIMIT ?',(last,end_rowid,512)).fetchall()
            batch=[dict(row) for row in batch]
        finally:db.close()
        if not batch:break
        # Only observed RUNNING rows need a full beforeimage. Refresh all fields
        # from that same row version before its state/task aggregates are counted.
        ids=[row['_control_rowid'] for row in batch if row['state']=='RUNNING'];full={}
        if ids:
            db=H.readonly(path)
            try:
                rows=db.execute('SELECT rowid AS _control_rowid,* FROM molecules WHERE rowid IN ('+','.join('?' for _ in ids)+') ORDER BY rowid',ids).fetchall()
                full={row['_control_rowid']:dict(row) for row in rows}
            finally:db.close()
            if set(full)!=set(ids):raise ValueError('STABLE_ROWID_PREFIX_ROW_DISAPPEARED')
        chunks+=1;visited+=len(batch)
        for observed in batch:
            key=observed['_control_rowid'];row=full.get(key,observed)
            add(states,row['state'],row);add(by_task,(row['task_id'],row['state']),row)
            if key in full and row['state']=='RUNNING':
                item=dict(row);item.pop('_control_rowid');running.append(item)
        last=batch[-1]['_control_rowid']
    def order(value):return (value is not None,value if value is not None else '')
    state_rows=[{'state':key,**states[key]} for key in sorted(states,key=order)]
    task_rows=[{'task_id':key[0],'state':key[1],**by_task[key]} for key in sorted(by_task,key=lambda key:(order(key[0]),order(key[1])))]
    running.sort(key=lambda row:row['molecule_id'])
    return {'meta':meta,'states':state_rows,'tasks':tasks,'sessions':sessions,'export_repairs':repairs,
        'by_task':task_rows,'running_rows':running,
        'diagnostic_interval':{'started_epoch':started,'finished_epoch':time.time(),'atomic':False,
            'chunk_size':512,'nonempty_chunks':chunks,'rows_observed':visited,
            'prefix_end_rowid':end_rowid,'last_rowid':last,'prefix_EOF_observed':True,
            'stable_prefix_basis':'Frozen ordinary rowid molecule table; production only UPDATE, no molecule INSERT/DELETE/VACUUM.',
            'aggregation':'Same observed row for state/task count and SUM; NULL inputs ignored and all-NULL SUM stays None. Prediction SUM uses rowid visit order.',
            'running_beforeimages':'Full row only for bounded-page RUNNING candidates, refreshed before aggregation; no live cursor/transaction crosses a page.',
            'scope':'Non-atomic observation interval. Small tables precede molecule pass; concurrent changes can occur between pages/statements.'}}

H.queue_snapshot=queue_snapshot_rowid512

def check_rowid512_snapshot():
    import tempfile
    with tempfile.TemporaryDirectory(prefix='wp5_r8_rowid512_',dir='/tmp') as td:
        path=Path(td)/'metadata.sqlite';db=sqlite3.connect(path)
        db.execute('CREATE TABLE meta(key TEXT,value TEXT)')
        db.execute('INSERT INTO meta VALUES(?,?)',('fixture','private_only'))
        db.execute('CREATE TABLE tasks(task_id TEXT,state TEXT)')
        db.execute('INSERT INTO tasks VALUES(?,?)',('fixture_task','RUNNING'))
        db.execute('CREATE TABLE sessions(session_id TEXT,job_id TEXT,claims INTEGER)')
        db.execute('INSERT INTO sessions VALUES(?,?,?)',('fixture_session','fixture_job',None))
        db.execute('CREATE TABLE export_repairs(run_root TEXT,state TEXT)')
        db.execute('CREATE TABLE molecules(molecule_id TEXT PRIMARY KEY,state TEXT,task_id TEXT,record_count INTEGER,predicted_seconds REAL,owner TEXT,receipt_json TEXT)')
        for i in range(513):
            state='RUNNING' if i%23==0 else 'COMPLETE';task='fixture_a' if i%2 else 'fixture_b'
            records=1+i%3;seconds=None if i%5==0 else (i%7)*.25
            if i==500:state='ALL_NULL';task='fixture_null';records=seconds=None
            db.execute('INSERT INTO molecules VALUES(?,?,?,?,?,?,?)',(f'fixture_{512-i:06d}',state,task,records,seconds,'fixture_session',None))
        db.commit();db.close()
        original=H.readonly;commits=[];queries=[]
        class TrackingReader:
            def __init__(self,p):self.real=original(p);self.page=False
            def execute(self,sql,parameters=()):
                queries.append(sql)
                if sql.startswith('SELECT rowid AS _control_rowid,molecule_id'):
                    assert 'LIMIT ?' in sql and parameters[-1]==512;self.page=True
                return self.real.execute(sql,parameters)
            def close(self):
                self.real.close()
                if self.page and not commits:
                    writer=sqlite3.connect(path,timeout=.01)
                    try:
                        writer.execute('BEGIN IMMEDIATE')
                        writer.execute("UPDATE molecules SET state='RUNNING',task_id='fixture_changed',record_count=7,predicted_seconds=NULL WHERE rowid=513")
                        writer.commit();commits.append('COMMITTED_BETWEEN_ROWID_PAGES')
                    finally:writer.close()
        H.readonly=TrackingReader
        try:current=queue_snapshot_rowid512(path)
        finally:H.readonly=original
        legacy=LEGACY_QUEUE_SNAPSHOT(path)
        for name in ('meta','states','tasks','sessions','export_repairs','by_task','running_rows'):
            assert current[name]==legacy[name],name
        interval=current['diagnostic_interval']
        assert interval['prefix_EOF_observed'] and not interval['atomic'] and interval['rows_observed']==513 and interval['nonempty_chunks']==2
        assert commits==['COMMITTED_BETWEEN_ROWID_PAGES']
        assert next(row for row in current['states'] if row['state']=='ALL_NULL')['records'] is None
        assert next(row for row in current['states'] if row['state']=='ALL_NULL')['predicted_seconds'] is None
        assert current['sessions'][0]['claims'] is None
        assert all('_control_rowid' not in row for row in current['running_rows'])
        print(json.dumps({'fixture':'PRIVATE_ROWID512_SNAPSHOT','rows':513,'chunk_count':2,'writer_interleave':commits,
            'all_legacy_SQL_fields_equal':True,'NULL_SUM_preserved':True,'RUNNING_full_rows':len(current['running_rows']),
            'whole_atomic':False,'EOF_observed':True,'production_SQL_run':False}))


# Only this new control process may route the exact metadata queue to a verified
# node-local mirror. Original H2, SCI readers, and production-write CAS remain.
import wp5_queue_mirror_copy_v2 as MIRROR
ORIGINAL_QUEUE_READONLY=H.readonly
MIRROR_CONTEXT=None

class ImmutableMirrorReadonly:
    """Owned verified post-recovery mirror only; never opens a source journal."""
    def __init__(self,path):
        from urllib.parse import quote
        self.path=str(path)
        self.stats={'path':self.path,'source_queue':str(MIRROR.QUEUE),'worker_pid':os.getpid(),'queries':0,'busy_retries':0,'busy_seconds':0.,'immutable_local_mirror':True}
        self.db=sqlite3.connect('file:'+quote(self.path)+'?mode=ro&immutable=1',uri=True,timeout=1,isolation_level=None)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA query_only=ON').close()
    def execute(self,sql,parameters=()):
        cursor=self.db.cursor()
        try:
            self.stats['queries']+=1;cursor.execute(sql,parameters)
            return DetachedReadResult(cursor.fetchall())
        finally:cursor.close()
    def close(self):
        if self.db is not None:self.db.close();self.db=None;READ_RETRY_EVENTS.append(dict(self.stats))

def install_read_mirror(path,expected_sha,hash_local=True):
    global MIRROR_CONTEXT
    doc=MIRROR.verify_manifest(path,expected_sha,hash_local=hash_local)
    if doc.get('repair_scope')!={'path':str(SCOPE),'sha256':SCOPE_SHA}:raise ValueError('MIRROR_CURRENT_SCOPE_BINDING_DIFFERS')
    if doc.get('control_source')!={'path':str(Path(__file__)), 'sha256':H.digest(__file__)}:raise ValueError('MIRROR_RECONCILIATION_SOURCE_CHANGED')
    def base_readonly(p):
        if MIRROR.normal(p)==MIRROR.normal(doc['local_queue']):return ImmutableMirrorReadonly(p)
        return ORIGINAL_QUEUE_READONLY(p)
    H.readonly=MIRROR.ExactQueueReadAdapter(MIRROR.QUEUE,doc['local_queue'],base_readonly)
    MIRROR_CONTEXT={'manifest':{'path':str(path),'sha256':expected_sha},
        'helper':{'path':MIRROR.__file__,'sha256':MIRROR.digest(MIRROR.__file__)},
        'source_queue':str(MIRROR.QUEUE),'local_queue':doc['local_queue'],
        'copy_job_id':doc['slurm_job_id'],'hostname':doc['hostname'],
        'source_fingerprints':doc['source_fingerprints_after'],'local_fingerprints':doc['local_fingerprints_after'],
        'source_file_copy_sha_readback':doc['source_file_copy_sha_readback'],'local_files_after':doc['local_files_after'],
        'local_recovery':doc['local_recovery'],'all463_terminal_at_copy':doc['accounting']['all_terminal'],
        'readonly_uri':'mode=ro&immutable=1; query_only=ON',
        'scope':'Only exact original metadata queue readonly opens are mapped. SCI/LMDB paths delegate unchanged to original strict reader; original queue path remains in plan and future apply.'}

def mirror_worker_init(barrier,manifest,expected_sha,scope_path=None,scope_sha=None):
    if scope_path is not None:configure_scope(scope_path,scope_sha)
    install_read_mirror(manifest,expected_sha,hash_local=False)
    H.worker_init(barrier)

def validate_apply_mirror_binding(args):
    # Explicit apply never installs the mirror. Fresh real-queue guards and
    # original beforeimages/CAS below remain the frozen production logic.
    p=H.load(args.plan);ctx=p.get('queue_read_mirror')
    if not ctx or ctx.get('source_queue')!=str(ROOT/'queue/pending.sqlite'):raise ValueError('REVIEWED_MIRROR_PLAN_PROVENANCE_REQUIRED')
    for ref in (ctx['manifest'],ctx['helper']):
        if H.digest(ref['path'])!=ref['sha256']:raise ValueError('REVIEWED_MIRROR_PROVENANCE_CHANGED')

def check_mirror_adapter_only():
    import tempfile
    with tempfile.TemporaryDirectory(prefix='wp5_r10_mirror_adapter_',dir='/tmp') as td:
        directory=Path(td);mirror=directory/'local.sqlite'
        db=sqlite3.connect(mirror);db.execute('CREATE TABLE sample(x INTEGER)');db.execute('INSERT INTO sample VALUES(7)');db.commit();db.close()
        opens=[];foreign=[]
        def private_factory(path):
            if Path(path)!=mirror:
                foreign.append(str(path));return 'DELEGATED_UNREAD_SCI_PATH'
            opens.append(str(path));return ImmutableMirrorReadonly(path)
        adapter=MIRROR.ExactQueueReadAdapter(MIRROR.QUEUE,mirror,private_factory)
        reader=adapter(MIRROR.QUEUE)
        try:
            assert reader.execute('SELECT x FROM sample').fetchone()[0]==7
            try:reader.execute('UPDATE sample SET x=0');raise AssertionError('Mirror write allowed')
            except sqlite3.OperationalError as exc:assert getattr(exc,'sqlite_errorcode',None)==sqlite3.SQLITE_READONLY
        finally:reader.close()
        fake_sci=ROOT/'runtime/private_fixture_NOT_OPENED/temporary_lanes/SCI.sqlite'
        fake_lmdb=ROOT/'original_private_fixture_NOT_OPENED.lmdb'
        assert adapter(fake_sci)=='DELEGATED_UNREAD_SCI_PATH' and adapter(fake_lmdb)=='DELEGATED_UNREAD_SCI_PATH'
        assert adapter(str(MIRROR.QUEUE)+'.other')=='DELEGATED_UNREAD_SCI_PATH'
        try:adapter(MIRROR.QUEUE,mode='rw');raise AssertionError('Nonreadonly invocation accepted')
        except TypeError:pass
        queue=directory/'fingerprint.sqlite';queue.write_bytes(b'own metadata fixture')
        for suffix in MIRROR.SUFFIXES[1:]:Path(str(queue)+suffix).write_bytes(b'fixture sidecar '+suffix.encode())
        before=MIRROR.inventory(queue)
        assert set(before)=={queue.name+s for s in MIRROR.SUFFIXES} and all(before.values())
        Path(str(queue)+'-journal').unlink()
        try:MIRROR.unchanged(queue,before);raise AssertionError('Journal omission accepted')
        except ValueError as exc:assert str(exc)=='SOURCE_DB_OR_JOURNAL_WAL_SHM_FILE_SET_CHANGED'
        assert len(opens)==1 and len(foreign)==3 and MIRROR_CONTEXT is None
        print(json.dumps({'fixture':'PRIVATE_EXACT_QUEUE_READ_MIRROR','mapped_source_never_opened':True,'mirror_SQL_read_only':True,
            'other_SCI_LMDB_paths_delegated_without_open':len(foreign),'nonreadonly_call_rejected':True,
            'journal_WAL_SHM_inventory_complete':True,'journal_omission_rejected':True,'production_queue_SQL':False,'copy_executed':False,'SCI_functions_executed':False}))

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
    if MIRROR_CONTEXT is None or not proof['all_terminal']:raise ValueError('VERIFIED_LOCAL_MIRROR_AND_FRESH_ALL463_TERMINAL_REQUIRED')
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
    scope=control_scope();latest_roots={r['run_root']:r for r in scope['roots']}
    phase_ids={str(row['job_id']) for row in H.load(MANIFESTS[-1])['main']+H.load(MANIFESTS[-1])['cleanup']}
    declared_root_jobs={str(r['job_id']) for r in scope['roots']}
    if not declared_root_jobs.issubset(phase_ids):raise ValueError('SCOPE_ROOT_NOT_LATEST_PHASE')
    observed_latest_roots=set()
    for path in sorted((ROOT/'runtime').glob('task_*/job_*/run.json')):
        run=H.load(path);opt=run['options'];job=str(opt['job_id'])
        if job not in jobs:continue
        root=Path(opt['run_root']);entry=jobs[job]
        if Path(opt['queue']).resolve()!=Path(args.queue).resolve():raise ValueError('RUNTIME_QUEUE_BINDING_DIFFERS')
        if proof['states'][job] not in H.TERMINAL or entry['mode']=='main' and entry['task_id'] in live_tasks:
            skipped.append({'run_root':str(root),'job_id':job,'task_id':entry['task_id'],'reason':'ACTIVE_OR_PD_JOB_TASK'});continue
        completion=root/'export_completion.json'
        latest=job in phase_ids
        if latest:
            if str(root) not in latest_roots or H.digest(path)!=latest_roots[str(root)]['run_json_sha256']:raise ValueError('LATEST_PHASE_ROOT_NOT_SCOPE_BOUND')
            observed_latest_roots.add(str(root))
        if completion.exists() and str(root) not in needed_closed and not latest:
            doc=H.load(completion)
            closed.append({'run_root':str(root),'job_id':job,'run_json_sha256':H.digest(path),'closure_path':str(completion),
                           'closure_sha256':H.digest(completion),'molecules':doc.get('molecules'),'records':doc.get('records'),
                           'archive':doc.get('archive'),'scope':'ALREADY_CLOSED_REUSED_NOT_REEXPORTED_NOT_RESCANNED'});continue
        selected.append(path)
    if observed_latest_roots!=set(latest_roots):raise ValueError('DECLARED_PHASE15_RUN_ROOT_NOT_FOUND')
    runs=[]
    if selected:
        count=min(args.workers,len(selected));ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(count)
        with concurrent.futures.ProcessPoolExecutor(max_workers=count,mp_context=ctx,initializer=mirror_worker_init,initargs=(barrier,MIRROR_CONTEXT['manifest']['path'],MIRROR_CONTEXT['manifest']['sha256'],str(SCOPE),SCOPE_SHA)) as pool:
            runs=list(pool.map(inspect_run_v4,[(str(p),str(args.queue),str(out)) for p in selected],chunksize=1))
    conflicts=[{'run_root':r['run_root'],'error':e} for r in runs for e in r['errors']]
    if not population['population_closed']:conflicts.append({'classification':'FORMAL_POPULATION_COUNT_MISMATCH','observed':population})
    actions=[];restores={};current_complete=set();same_attempt={};evidence_skips=[];complete_identities=set()
    for r in runs:
        with Path(r['evidence_file']['path']).open() as stream:
            for line in stream:
                e=json.loads(line);b=e['before'];reason=guard(b,session_jobs,jobs,proof,live_tasks,e['context']['job_id'])
                if reason:
                    evidence_skips.append({'molecule_id':e['molecule_id'],'run_root':e['run_root'],'reason':reason});continue
                complete_identities.add((e['molecule_id'],int(e['context']['attempt_id']),e['context']['execution_id']))
                key=(e['molecule_id'],int(e['context']['attempt_id']))
                if key in same_attempt and same_attempt[key]!=e['wire_sha256']:conflicts.append({'molecule_id':key[0],'attempt':key[1],'classification':'CROSS_EXECUTION_SAME_ATTEMPT_DIFFERENT_COMPLETE_SCI'})
                same_attempt[key]=e['wire_sha256']
                if int(b['attempt'])==int(e['context']['attempt_id']):current_complete.add(e['molecule_id'])
                if e['action'].startswith('CONFLICT_'):conflicts.append({'molecule_id':e['molecule_id'],'classification':e['action'],'run_root':e['run_root']})
                elif e['action']=='RESTORE_DURABLE_COMPLETION':restores.setdefault(e['molecule_id'],e)
    for item in phase_metadata['current_phase_receipt_identities']:
        if (item['molecule_id'],int(item['attempt_id']),item['execution_id']) not in complete_identities:
            conflicts.append({'classification':'LATEST_PHASE_PUBLISHED_RECEIPT_WITHOUT_COMPLETE_SCI_READBACK',**item})
    actions=[{'kind':'RESTORE_DURABLE_COMPLETION','molecule_id':m,'evidence':e} for m,e in sorted(restores.items())]
    infra_rows=incident_rows(args.queue,scope)
    for row in infra_rows:
        if row['molecule_id'] in restores:continue
        try:
            action=plan_infrastructure_release(row,scope,jobs,proof,session_jobs,live_tasks,current_complete)
            if action is not None:actions.append(action)
        except ValueError as exc:conflicts.append({'classification':'INCIDENT_ATTENTION_ROW_NOT_SAFELY_RECOVERABLE','molecule_id':row['molecule_id'],'error':str(exc)})
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
             for r in runs if r['staged_molecules']+r['retired_molecules'] and (r['staged_molecules']>0 or not (Path(r['run_root'])/'export_completion.json').exists())]
    # Allocated/requested workers and actual roots/PIDs are reported separately;
    # two terminal roots legitimately use two SCI workers, never fake16.
    for name,data in (('actions',actions),('run_reports',runs),('export_roots',exports),('already_closed_roots',closed),('skipped',skipped+evidence_skips)):
        H.write_json(out/(name+'.json'),data)
    plan={'schema':'WP5_TERMINAL_SUBSET_RECONCILIATION_PLAN_V3','status':'REVIEWABLE_TERMINAL_SUBSET_DRY_RUN' if not conflicts else 'DRY_RUN_EXPLICIT_CONFLICTS_NO_APPLY',
          'created_epoch':time.time(),'implementation_version':IMPLEMENTATION_VERSION,'source_sha256':H.digest(__file__),'metadata_reader_sources':METADATA_READER_REFS,'helper':{'path':H.__file__,'sha256':HELPER_SHA},'queue':str(args.queue),
          'control_jobmap':scope['jobmap'],'repair_scope':{'path':str(SCOPE),'sha256':SCOPE_SHA},'manifests':manifests,'registered_receipts':receipts,'registered_jobs':jobs,'registered_jobs_count':len(jobs),'accounting':proof,'all_registered_jobs_terminal':proof['all_terminal'],'plan_was_all463_terminal':not bool(live),
          'latest_phase_metadata':phase_metadata,'population_closure':population,'queue_read_mirror':MIRROR_CONTEXT,
           'forced_latest_phase_roots':len(latest_roots),'incident_attention_rows':len(infra_rows),
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

def incident_rows(queue,scope):
    result=[];q=H.readonly(queue)
    try:
        for item in scope['incident']['infra_failure_molecules']:
            row=q.execute('SELECT * FROM molecules WHERE molecule_id=?',(item['molecule_id'],)).fetchone()
            if row is None:raise ValueError('INCIDENT_MOLECULE_NOT_IN_FORMAL_QUEUE')
            result.append(dict(row))
    finally:q.close()
    return result

def plan_infrastructure_release(row,scope,jobs,proof,sessions,live_tasks,current_complete):
    mid=row['molecule_id'];incident=scope['incident']
    entry=next((r for r in incident['infra_failure_molecules'] if r['molecule_id']==mid),None)
    if entry is None:raise ValueError('NOT_EXACT_INCIDENT_MOLECULE')
    if mid in current_complete:return None
    if row['state']!='ATTENTION_REQUIRED':raise ValueError('INCIDENT_WITHOUT_CURRENT_SCI_MUST_BE_ATTENTION_REQUIRED')
    exported=json.loads(row['export_json']) if row.get('export_json') else {}
    summary=exported.get('unpublished_pipeline_failure') or {}
    ctx=summary.get('context') or {};text=summary.get('error','')
    run=H.load(Path(incident['victim_run_root'])/'run.json');opt=run['options']
    if summary.get('molecule_id')!=mid or summary.get('retryable') is not False:raise ValueError('EXACT_NONRETRYABLE_INFRA_SUMMARY_REQUIRED')
    if H.sha(text.encode('utf-8'))!=entry['worker_error_sha256']:raise ValueError('WORKER_ERROR_BODY_DIFFERS')
    if 'wp5_archive_v5.py' not in text or 'sqlite3.OperationalError: attempt to write a readonly database' not in text:raise ValueError('NOT_CONFIRMED_ARCHIVE_SQLITE_READONLY_FAILURE')
    if int(ctx.get('attempt_id',-1))!=int(row['attempt']) or int(ctx.get('lane',-1))!=entry['lane'] or summary.get('lane')!=entry['lane']:
        raise ValueError('INFRA_CURRENT_ATTEMPT_LANE_DIFFERS')
    if str(ctx.get('job_id'))!=str(opt['job_id']) or not str(ctx.get('execution_id','')).startswith(opt['session']+':'):
        raise ValueError('INFRA_VICTIM_JOB_EXECUTION_DIFFERS')
    if str(ctx.get('task_id'))!=str(row['task_id']):raise ValueError('INFRA_ASSIGNED_TASK_DIFFERS')
    for key in ('reproduction_package_sha256','audit_membership_sha256'):
        if ctx.get(key)!=opt[key]:raise ValueError('INFRA_EXECUTION_AUTHORITY_DIFFERS:'+key)
    reason=guard(row,sessions,jobs,proof,live_tasks,ctx['job_id'])
    if reason:raise ValueError(reason)
    return {'kind':'RELEASE_TERMINAL_INFRASTRUCTURE_FAILURE','before':row,'before_sha256':H.row_sha(row),
            'desired_state':'PENDING','failure_context':ctx,'worker_error_sha256':entry['worker_error_sha256'],
            'incident_evidence':{k:incident[k] for k in ('STOP','foreign_repair_receipt','victim_completion')},
            'scientific_attempt_unchanged':True,'all_selected_roots_scanned_before_release':True,
            'explanation':'Exact terminal archive DBMOVED incident; no current-attempt full SCI found. Reclaim same attempt; preserve prior receipt/export/history.'}

def infrastructure_after_matches(row,action):
    before=action['before']
    return row.get('state')=='PENDING' and row.get('owner') is None and all(
        row.get(k)==value for k,value in before.items() if k not in ('state','owner','updated'))

def infrastructure_action_apply(db,action):
    before=action['before'];mid=before['molecule_id']
    row=db.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone()
    if row is not None and infrastructure_after_matches(dict(row),action):return 'ALREADY_APPLIED'
    if row is None or H.row_sha(row)!=action['before_sha256']:raise ValueError('INFRA_ROW_CHANGED_SINCE_REVIEW')
    if before['state']!='ATTENTION_REQUIRED' or action['desired_state']!='PENDING' or action.get('scientific_attempt_unchanged') is not True:
        raise ValueError('EXACT_SAME_ATTEMPT_INFRA_RELEASE_REQUIRED')
    db.execute("UPDATE molecules SET state='PENDING',owner=NULL,updated=? WHERE molecule_id=?",(time.time(),mid))
    return 'APPLIED'

def check_infrastructure_actions():
    import tempfile
    with tempfile.TemporaryDirectory(prefix='wp5_r10_infra_private_',dir='/tmp') as td:
        db=sqlite3.connect(Path(td)/'private.sqlite',isolation_level=None);db.row_factory=sqlite3.Row
        db.execute('CREATE TABLE molecules(molecule_id TEXT PRIMARY KEY,state TEXT,owner TEXT,attempt INTEGER,receipt_json TEXT,counts_json TEXT,export_json TEXT,completion_rank INTEGER,archive_path TEXT,updated REAL)')
        for attempt in (0,1):
            mid='private_'+str(attempt)
            db.execute('INSERT INTO molecules VALUES(?,?,?,?,?,?,?,?,?,?)',(mid,'ATTENTION_REQUIRED',None,attempt,'old receipt','old counts','actual infrastructure error',42,'old history archive',1.))
            before=dict(db.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone())
            action={'kind':'RELEASE_TERMINAL_INFRASTRUCTURE_FAILURE','before':before,'before_sha256':H.row_sha(before),'desired_state':'PENDING','scientific_attempt_unchanged':True}
            assert H.retry_transaction(db,lambda:infrastructure_action_apply(db,action))=='APPLIED'
            assert verify_after(db,action)[0]
            assert H.retry_transaction(db,lambda:infrastructure_action_apply(db,action))=='ALREADY_APPLIED'
            after=dict(db.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone())
            assert after['attempt']==attempt and after['export_json']==before['export_json'] and after['receipt_json']==before['receipt_json']
        before=dict(db.execute("SELECT * FROM molecules WHERE molecule_id='private_0'").fetchone())
        action={'before':{**before,'state':'ATTENTION_REQUIRED'},'before_sha256':H.row_sha({**before,'state':'ATTENTION_REQUIRED'}),'desired_state':'PENDING','scientific_attempt_unchanged':True}
        db.execute("UPDATE molecules SET receipt_json='changed' WHERE molecule_id='private_0'")
        try:H.retry_transaction(db,lambda:infrastructure_action_apply(db,action));raise AssertionError('Changed row accepted')
        except ValueError as exc:assert str(exc)=='INFRA_ROW_CHANGED_SINCE_REVIEW'
        # Plan guard exercises real metadata shapes without any SCI/archive reads.
        runroot=Path(td)/'victim';runroot.mkdir()
        opts={'job_id':101,'session':'private_session','reproduction_package_sha256':'package','audit_membership_sha256':'audit'}
        H.write_json(runroot/'run.json',{'options':opts})
        text='wp5_archive_v5.py\nsqlite3.OperationalError: attempt to write a readonly database'
        item={'molecule_id':'private_scope','lane':16,'worker_error_sha256':H.sha(text.encode())}
        scope={'incident':{'victim_run_root':str(runroot),'infra_failure_molecules':[item],
                          'STOP':{'path':'private_stop','sha256':'s'},'foreign_repair_receipt':{'path':'private_foreign','sha256':'f'},'victim_completion':{'path':'private_completion','sha256':'c'}}}
        for attempt in (0,1):
            context={'attempt_id':attempt,'job_id':101,'task_id':'16','lane':16,'execution_id':'private_session:16:'+str(attempt)+':unique',
                     'reproduction_package_sha256':'package','audit_membership_sha256':'audit'}
            summary={'molecule_id':'private_scope','retryable':False,'lane':16,'context':context,'error':text}
            row={'molecule_id':'private_scope','state':'ATTENTION_REQUIRED','owner':None,'attempt':attempt,'task_id':'16',
                 'export_json':json.dumps({'unpublished_pipeline_failure':summary})}
            planned=plan_infrastructure_release(row,scope,{'101':{}},{'states':{'101':'COMPLETED'}},{},set(),set())
            assert planned['desired_state']=='PENDING' and planned['before']['attempt']==attempt
            assert plan_infrastructure_release(row,scope,{'101':{}},{'states':{'101':'COMPLETED'}},{},set(),{'private_scope'}) is None
            try:plan_infrastructure_release(row,scope,{'101':{}},{'states':{'101':'RUNNING'}},{},set(),set());raise AssertionError('Live source accepted')
            except ValueError as exc:assert str(exc)=='SKIP_CANDIDATE_NONTERMINAL_OR_UNREGISTERED'
            changed={**row,'attempt':attempt+1}
            try:plan_infrastructure_release(changed,scope,{'101':{}},{'states':{'101':'COMPLETED'}},{},set(),set());raise AssertionError('Wrong attempt accepted')
            except ValueError as exc:assert str(exc)=='INFRA_CURRENT_ATTEMPT_LANE_DIFFERS'
        db.close()
    print(json.dumps({'fixture':'EXACT_INFRASTRUCTURE_SAME_ATTEMPT_PENDING','attempts_tested':[0,1],'old_history_preserved':True,'idempotent':True,'CAS_changed_row_rejected':True,'full_SCI_precedes_release':True,'live_source_rejected':True,'wrong_attempt_rejected':True,'production_queue_opened':False,'QM_started':False}))

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
    if kind=='RELEASE_TERMINAL_INFRASTRUCTURE_FAILURE':
        row=db.execute('SELECT * FROM molecules WHERE molecule_id=?',(action['before']['molecule_id'],)).fetchone()
        if row is None:return 'SKIP_CURRENT_ROW_MISSING'
        return guard(dict(row),sessions,jobs,proof,live_tasks,action['failure_context']['job_id'])
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
    if kind=='RELEASE_TERMINAL_INFRASTRUCTURE_FAILURE':
        r=db.execute('SELECT * FROM molecules WHERE molecule_id=?',(action['before']['molecule_id'],)).fetchone()
        return (infrastructure_after_matches(dict(r),action),dict(r)) if r is not None else (False,None)
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
    if jobs!=p['registered_jobs']:raise ValueError('REGISTERED463_JOB_MAP_CHANGED')
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
                    return reason if reason else (infrastructure_action_apply(db,action) if action['kind']=='RELEASE_TERMINAL_INFRASTRUCTURE_FAILURE' else H.action_apply(db,action))
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
            'all_registered_jobs_terminal':proof['all_terminal'],'plan_was_all463_terminal':not bool(p['protected_jobs']),
            'all_applied_rows_verified':all_verified,'plan_skipped_count':p['skipped']['count'],'full463_terminal_scope_verified':full_scope_verified,'mutation_journal':{'path':str(out/'mutation_journal.jsonl'),'sha256':H.digest(out/'mutation_journal.jsonl')},
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
    ast.parse(Path(__file__).read_text());ast.parse(Path(MIRROR.__file__).read_text())
    check_mirror_adapter_only();check_infrastructure_actions()
    print('RECONCILE_V10_EXACT_PATH_READONLY_MIRROR_ADAPTER_PASS_NO_COPY_NO_SCI_NO_PRODUCTION_QUEUE')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--mode',choices=('dry-run','plan','apply'),default='dry-run')
    p.add_argument('--scope',type=Path,default=SCOPE);p.add_argument('--expected-scope-sha256',default=SCOPE_SHA)
    p.add_argument('--manifests',type=Path,nargs=6,default=list(MANIFESTS));p.add_argument('--queue',type=Path,default=ROOT/'queue/pending.sqlite')
    p.add_argument('--workers',type=int,default=16);p.add_argument('--out',type=Path);p.add_argument('--plan',type=Path);p.add_argument('--expected-plan-sha256')
    p.add_argument('--mirror-manifest',type=Path);p.add_argument('--expected-mirror-sha256')
    args=p.parse_args()
    configure_scope(args.scope,args.expected_scope_sha256)
    if args.check:
        check()
    else:
        if not args.out:p.error('--out required')
        if args.mode!='apply' and args.workers<16:p.error('at least16 SCI workers required')
        if args.mode=='apply' and (not args.plan or not args.expected_plan_sha256):p.error('explicit --plan and --expected-plan-sha256 required')
        if args.mode=='apply':
            if args.mirror_manifest or args.expected_mirror_sha256:p.error('Apply always reads/writes original queue; do not install a mirror')
            validate_apply_mirror_binding(args)
        else:
            if not args.mirror_manifest or not args.expected_mirror_sha256:p.error('Explicit verified mirror manifest and SHA required for dry-run')
            install_read_mirror(args.mirror_manifest,args.expected_mirror_sha256)
        raise SystemExit(apply(args) if args.mode=='apply' else dry_run(args))

