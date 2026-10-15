"""Pure export of the exact19 terminal roots in actualV4 plan; noQM/LMDB.
Frozen R11 numeric export stays unchanged. Own-run receipt and guarded latest
publication adapters exist only in this metadata worker; frozen files stay intact.
"""
from __future__ import annotations
import argparse,ast,concurrent.futures,json,multiprocessing,os,platform,socket,time,traceback,sqlite3,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
import wp5_queue_reconcile_v8 as V
H=V.H;ROOT=H.ROOT
SCOPE=ROOT/'configs/terminal_phase14_export9_repair_scope_v1.json'
SCOPE_SHA='ccd3eab4339dd7cdc87b2a06216194bab51973fa8c473353e076a228249ae5f4'
CONTRACT=ROOT/'configs/production_contract_v6.json'
CONTRACT_SHA='dfbeb31ed87553a62f833d8aee22f7000dabffc973b4ed34366ce6edd1e65099'
RUNNER_SHA='258fd76ec1e0bac38db20fc2f3c0c1ef6f107d0d89261860f95b4b73099aed1f'
SCI=('wp5_engine_v3.py','wp5_parser_v2.py','wp5_archive_v5.py','wp5_parquet_v2.py','wp5_registry_coverage_v2.py','wp5_scf_metadata_v2.py')

# SQLite recovery access is limited to the existing production metadata queue.
# Source SCI archives and original LMDB readers are never reopened read/write.
BaseMetadataReadonly=V.BoundedReadonly
class MetadataRead(BaseMetadataReadonly):
    def __init__(self,path,fixture_root=None):
        self._recovered=False
        self._fixture_root=Path(fixture_root).resolve() if fixture_root else None
        super().__init__(path)
        self.stats.setdefault('reopened_after_readonly_rollback',0)
        self.stats.setdefault('sqlite_errors',[])
    def _recovery_scope(self):
        path=Path(self.path)
        if path.resolve()==(ROOT/'queue/pending.sqlite').resolve():
            return os.getuid()==1278 and path.stat().st_uid==1278
        own=self._fixture_root
        return bool(own and own.name.startswith('wp5_export_hotjournal_v3_') and
                    str(own.parent)=='/tmp' and path.parent==own and
                    own.stat().st_uid==os.getuid() and path.stat().st_uid==os.getuid())
    def execute(self,sql,parameters=()):
        try:return super().execute(sql,parameters)
        except sqlite3.DatabaseError as exc:
            code=getattr(exc,'sqlite_errorcode',None)
            event={'sqlite_errorcode':code,'sqlite_errorname':getattr(exc,'sqlite_errorname',None),
                   'message':str(exc),'statement_kind':sql.lstrip().split()[0] if sql.strip() else '',
                   'path':self.path,'worker_pid':os.getpid()}
            self.stats.setdefault('sqlite_errors',[]).append(event)
            # Primary READONLY8 is insufficient evidence. Do not mask IO,
            # permissions, generic READONLY or scientific archive failures.
            if code!=sqlite3.SQLITE_READONLY_ROLLBACK or self._recovered or not self._recovery_scope():
                raise
            self.db.close()
            from urllib.parse import quote
            self.db=sqlite3.connect('file:'+quote(self.path)+'?mode=rw',uri=True,
                                    timeout=1,isolation_level=None)
            self.db.row_factory=sqlite3.Row
            self.db.execute('PRAGMA query_only=ON').close()
            self.db.execute('PRAGMA busy_timeout=1000').close()
            self._recovered=True
            self.stats['reopened_after_readonly_rollback']=self.stats.get('reopened_after_readonly_rollback',0)+1
            self.stats['sqlite_internal_recovery_only']=True
            print(json.dumps({'event':'METADATA_HOT_JOURNAL_RECOVERY_ACCESS',**event,
                              'reopen_mode':'rw','query_only':True}),flush=True)
            # SQLite takes its own recovery locks; existing120s BUSY-only
            # detached-read retry remains unchanged. No manual journal deletion.
            return super().execute(sql,parameters)

def hotjournal_fixture():
    """Owned ~1MiB crash fixture; never open the real queue/SCI/LMDB."""
    with tempfile.TemporaryDirectory(prefix='wp5_export_hotjournal_v3_',dir='/tmp') as own:
        path=Path(own)/'fixture.sqlite'
        db=sqlite3.connect(path)
        db.execute('PRAGMA journal_mode=DELETE').fetchone()
        db.execute('PRAGMA synchronous=FULL')
        db.execute('CREATE TABLE evidence(id INTEGER PRIMARY KEY,payload BLOB)')
        db.executemany('INSERT INTO evidence VALUES(?,?)',[(i,b'A'*4096) for i in range(256)])
        db.commit();db.close()
        child_code=("import os,sqlite3,sys\n"
                    "db=sqlite3.connect(sys.argv[1],isolation_level=None)\n"
                    "db.execute('PRAGMA journal_mode=DELETE').fetchone()\n"
                    "db.execute('PRAGMA synchronous=FULL')\n"
                    "db.execute('PRAGMA cache_size=2')\n"
                    "db.execute('PRAGMA cache_spill=ON')\n"
                    "db.execute('BEGIN IMMEDIATE')\n"
                    "db.execute('UPDATE evidence SET payload=?',(b'B'*4096,)).close()\n"
                    "os._exit(77)\n")
        child=subprocess.run([sys.executable,'-c',child_code,str(path)],capture_output=True,timeout=30)
        if child.returncode!=77:raise AssertionError('FIXTURE_CRASH_CHILD_FAILED:'+child.stderr.decode(errors='replace'))
        journal=path.with_name(path.name+'-journal')
        if not journal.is_file() or journal.stat().st_size<=512:raise AssertionError('FIXTURE_HOT_JOURNAL_NOT_CREATED')
        from urllib.parse import quote
        ro=sqlite3.connect('file:'+quote(str(path))+'?mode=ro',uri=True,timeout=1,isolation_level=None)
        try:
            ro.execute('PRAGMA query_only=ON')
            try:ro.execute('SELECT count(*) FROM evidence').fetchone();raise AssertionError('RO_ACCEPTED_HOT_JOURNAL')
            except sqlite3.OperationalError as exc:
                if getattr(exc,'sqlite_errorcode',None)!=sqlite3.SQLITE_READONLY_ROLLBACK:raise
                observed={'code':exc.sqlite_errorcode,'name':exc.sqlite_errorname,'message':str(exc)}
        finally:ro.close()
        reader=MetadataRead(path,fixture_root=own)
        try:
            rows=reader.execute('SELECT count(*) AS n,min(hex(substr(payload,1,1))) AS lo,max(hex(substr(payload,1,1))) AS hi FROM evidence').fetchone()
            if tuple(rows)!=(256,'41','41'):raise AssertionError('RECOVERY_DID_NOT_RESTORE_COMMITTED_VALUE')
            if reader.execute('PRAGMA query_only').fetchone()[0]!=1:raise AssertionError('QUERY_ONLY_LOST')
            try:reader.execute("UPDATE evidence SET payload=x'43' WHERE id=0");raise AssertionError('QUERY_ONLY_ACCEPTED_USER_WRITE')
            except sqlite3.OperationalError as exc:
                if getattr(exc,'sqlite_errorcode',None)!=sqlite3.SQLITE_READONLY:raise
                rejected={'code':exc.sqlite_errorcode,'name':exc.sqlite_errorname}
            if reader.stats['reopened_after_readonly_rollback']!=1:raise AssertionError('RECOVERY_REOPEN_COUNT_DIFFERS')
            if reader.execute('SELECT hex(substr(payload,1,1)) FROM evidence WHERE id=0').fetchone()[0]!='41':
                raise AssertionError('USER_WRITE_CHANGED_COMMITTED_VALUE')
            report={'status':'OWNED_HOT_JOURNAL_FIXTURE_PASS','sqlite_version':sqlite3.sqlite_version,
                    'readonly_error':observed,'rw_query_only_recovered_committed_rows':256,
                    'user_write_rejected':rejected,'fixture_child_exit':77,
                    'metadata_reader_stats':dict(reader.stats),'real_queue_opened':False,
                    'SCI_or_LMDB_opened':False,'temporary_fixture_cleaned_on_exit':True}
        finally:reader.close()
    print(json.dumps(report,allow_nan=False))
    return report

def rebase_deadlines(options,mono,epoch,hours):
    out=dict(options);duration=min(float(hours),46.)*3600
    out.update(job_exit_monotonic=mono+48*3600,hard_monotonic=mono+duration,
               hard_epoch=epoch+duration,admit_monotonic=mono+duration,sql_deadline_monotonic=mono+duration)
    return out,mono+duration
def original_scope(receipt,opt):
    ctx=receipt['context']
    if receipt.get('raw_policy')!=H.POLICY or receipt['requested_outcomes']!=12*receipt['records']:
        raise ValueError('OWN_RECEIPT_TWELVE_TASK_POLICY_DIFFERS')
    if str(ctx['job_id'])!=str(opt['job_id']) or not ctx['execution_id'].startswith(opt['session']+':'):
        raise ValueError('OWN_RECEIPT_JOB_SESSION_DIFFERS')
    if opt['mode']=='main' and str(ctx['task_id'])!=str(opt['task_id']):raise ValueError('OWN_RECEIPT_TASK_DIFFERS')
    for k in ('reproduction_package_sha256','audit_membership_sha256'):
        if ctx[k]!=opt[k]:raise ValueError('OWN_RECEIPT_AUTHORITY_DIFFERS:'+k)
    return ctx
def same_execution(row,receipt,session):
    if row is None or row.get('owner')!=session or row.get('receipt_json') is None:return False
    old=json.loads(row['receipt_json'])
    return (row['attempt']==receipt['context']['attempt_id'] and old.get('context')==receipt['context'] and
            old.get('records')==receipt['records'] and old.get('counts')==receipt['counts'])
def pool_init(barrier):barrier.wait(timeout=180)
def hash_ref(ref):
    p=Path(ref['path']);actual=H.digest(p)
    if actual!=ref['sha256'] or ('bytes' in ref and p.stat().st_size!=ref['bytes']):raise ValueError('BOUND_SHA_BYTES_DIFFERS:'+str(p))
    return {**ref,'actual_sha256':actual,'actual_bytes':p.stat().st_size,'worker_pid':os.getpid()}
def hash_parallel(refs,workers):
    ctx=multiprocessing.get_context('spawn')
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers,mp_context=ctx) as pool:
        return list(pool.map(hash_ref,refs,chunksize=1))
def verify_inputs(args,out):
    H.node_guard()
    for path,wanted in ((args.scope_manifest,SCOPE_SHA),(args.plan,args.expected_plan_sha256),(args.apply_report,args.expected_apply_sha256),(args.contract,CONTRACT_SHA)):
        if not path or not wanted or H.digest(path)!=wanted:raise ValueError('EXACT_CURRENT_CONTROL_SHA_REQUIRED:'+str(path))
    scope=H.load(args.scope_manifest);plan=H.load(args.plan);applied=H.load(args.apply_report);contract=H.load(args.contract)
    if scope['schema']!='WP5_PHASE14_TERMINAL_EXPORT9_SCOPE_V1' or len(scope['roots'])!=9:raise ValueError('IMMUTABLE9_ROOT_SCOPE_REQUIRED')
    if plan['status']!='REVIEWABLE_TERMINAL_SUBSET_DRY_RUN' or plan['conflicts'] or not plan['all_selected_root_scans_complete']:
        raise ValueError('FULL_CONFLICT_FREE_TERMINAL_SUBSET_SCAN_REQUIRED')
    if plan.get('implementation_version')!=8 or plan.get('registered_jobs_count')!=385 or plan.get('control_jobmap')!={k:scope['jobmap'][k] for k in ('path','sha256')}:
        raise ValueError('CURRENT385_RECONCILE8_SCOPE_REQUIRED')
    if (applied['status'] not in {'TERMINAL_SUBSET_APPLIED_AND_VERIFIED','APPLIED_AND_VERIFIED'} or
        applied['plan']['sha256']!=args.expected_plan_sha256 or not applied['all_applied_rows_verified'] or
        applied.get('source',{}).get('sha256')!=plan['source_sha256'] or
        applied.get('registered_jobs_count')!=385 or
        any(not row.get('verified') or row['status'] not in {'APPLIED','ALREADY_APPLIED'} for row in applied['results'])):
        raise ValueError('CURRENT_RECONCILIATION_READBACK_REQUIRED')
    if H.digest(V.__file__)!=plan['source_sha256']:raise ValueError('RECONCILE8_CHANGED_AFTER_PLAN')
    if contract['schema']!='WP5_PRODUCTION_CONTRACT_V1' or contract['status']!='PRODUCTION_CONTRACT_FROZEN' or contract['policy']!=H.POLICY:raise ValueError('CURRENT_CONTRACT6_SCOPE_REQUIRED')
    for key in ('export_roots','run_reports','actions','queue_snapshot','already_closed_roots','skipped'):
        ref=plan[key]
        if H.digest(ref['path'])!=ref['sha256']:raise ValueError('PLAN_LEAF_CHANGED:'+key)
    jobs,manifests,registered_receipts=V.registry([ref['path'] for ref in plan['manifests']])
    if manifests!=plan['manifests'] or [{'path':x['path'],'sha256':x['sha256']} for x in manifests]!=scope['manifests']:raise ValueError('ACTUAL385_MANIFEST_BINDINGS_CHANGED')
    proof=H.terminal_proof(jobs,out);live,live_tasks=V.protection(jobs,proof)
    selected={row['run_root']:row for row in H.load(plan['export_roots']['path'])}
    closed={row['run_root']:row for row in H.load(plan['already_closed_roots']['path'])}
    sources={row['path']:row for row in contract['sources']};references=[]
    for name in SCI+('wp5_runner_v13.py','wp5_accounting_v2.py'):
        path=str(ROOT/'scripts'/name)
        if path not in sources:raise ValueError('CURRENT_CONTROL_SOURCE_NOT_BOUND:'+name)
        references.append(sources[path])
    if sources[str(ROOT/'scripts/wp5_runner_v13.py')]['sha256']!=RUNNER_SHA:raise ValueError('FROZEN_R13_BINDING_DIFFERS')
    references += [contract[k] for k in ('protocol','registry','audit_manifest','reproduction_package','node_authority','node_scope_plan','authority')]
    q=MetadataRead(plan['queue'])
    try:session_jobs=dict(q.execute('SELECT session_id,job_id FROM sessions').fetchall())
    finally:q.close()
    runs=[];already_closed=[]
    for declared in scope['roots']:
        root=Path(declared['run_root'])
        if proof['states'].get(declared['job_id']) not in H.TERMINAL:raise ValueError('REQUESTED_ROOT_NOT_ACTUAL_TERMINAL')
        if declared['task_id'] in live_tasks:raise ValueError('REQUESTED_ROOT_TASK_PROTECTED_BY_LIVE_JOB')
        if H.digest(root/'run.json')!=declared['run_json_sha256']:raise ValueError('ORIGINAL_RUN_JSON_CHANGED')
        if declared['run_root'] in closed:
            if H.digest(closed[declared['run_root']]['closure_path'])!=closed[declared['run_root']]['closure_sha256']:raise ValueError('ALREADY_CLOSED_PROOF_CHANGED')
            already_closed.append(closed[declared['run_root']]);continue
        row=selected.get(declared['run_root'])
        if not row or not row.get('scan_complete') or not row.get('repair_claim_allowed'):raise ValueError('REQUESTED_ROOT_FULL_SCI_SCAN_NOT_PRESENT')
        if any(row[k]!=declared[k] for k in ('run_root','job_id','session','run_json_sha256')):raise ValueError('REQUESTED_ROOT_IDENTITY_DIFFERS')
        old=H.load(root/'run.json')['options']
        if root.resolve()!=Path(old['run_root']).resolve() or not root.resolve().is_relative_to((ROOT/'runtime').resolve()):raise ValueError('ORIGINAL_RUNTIME_SCOPE_DIFFERS')
        if str(old['job_id'])!=row['job_id'] or old['session']!=row['session']:raise ValueError('ORIGINAL_JOB_SESSION_DIFFERS')
        if {'path':old['production_contract'],'sha256':old['production_contract_sha256']}!=scope['contract']:raise ValueError('ORIGINAL_PHASE14_CONTRACT_CHANGED')
        old_package={'path':old['reproduction_package'],'sha256':old['reproduction_package_sha256']}
        if any(old_package[k]!=scope['package'][k] for k in ('path','sha256')):raise ValueError('ORIGINAL_PHASE14_PACKAGE_CHANGED')
        old_refs={x['path']:x['sha256'] for x in old['source_bindings']}
        for name in SCI:
            path=str(ROOT/'scripts'/name)
            if old_refs.get(path)!=sources[path]['sha256']:raise ValueError('SCI_SOURCE_CHANGED_SINCE_EXECUTION:'+name)
        for old_key,new_key in (('protocol','protocol'),('registry','registry'),('audit_membership','audit_manifest')):
            if old_refs.get(old[old_key])!=contract[new_key]['sha256']:raise ValueError('OLD_SCI_AUTHORITY_DIFFERS:'+old_key)
        references.extend(old['source_bindings'])
        runs.append({'root_report':row,'options':old,'old_contract':declared['source_contract'],'old_package':old_package})
    by_path={}
    for ref in references:
        if ref['path'] in by_path and by_path[ref['path']]['sha256']!=ref['sha256']:raise ValueError('SOURCE_SHA_CONFLICT:'+ref['path'])
        by_path[ref['path']]=ref
    return plan,runs,hash_parallel(list(by_path.values()),args.workers),{'jobs':jobs,'session_jobs':session_jobs,'proof':proof,'live_tasks':sorted(live_tasks),'protected_jobs':{job:proof['states'][job] for job in sorted(live)},'queue_metadata_read_stats':dict(q.stats),'already_closed_requested_roots':already_closed,'expected_export_counts':(len(runs),sum(x['root_report']['molecules'] for x in runs),sum(x['root_report']['records'] for x in runs))}

def before_scope(arg):
    item,queue_path=arg
    from wp5_archive_v5 import ArchiveReader
    opt=item['options'];root=Path(opt['run_root']);seen={};q=MetadataRead(queue_path)
    already=(root/'export_completion.json').exists()
    paths=[root/'raw_archive.sqlite'] if already else sorted((root/'temporary_lanes').glob('lane_*.sqlite'))
    try:
        for path in paths:
            reader=ArchiveReader(path,opt['dictionaries'])
            try:
                if already:
                    elements=[]
                    for (mid,) in reader.db.execute('SELECT molecule_id FROM completion_receipts').fetchall():
                        c=reader.completion(mid);original_scope(c['receipt'],opt);elements.append((mid,c,c['record_count']))
                else:
                    elements=[]
                    for stage in reader.iter_staged():
                        c=reader.completion(stage['molecule_id']);H.validate_payload(stage,c,opt,reader.db)
                        elements.append((stage['molecule_id'],c,stage['record_count']))
                for mid,c,n in elements:
                    if mid in seen:raise ValueError('DUPLICATE_OWN_RUN_MOLECULE')
                    ctx=original_scope(c['receipt'],opt);row=q.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone()
                    if row is None:raise ValueError('OWN_SCI_MOLECULE_NOT_IN_FORMAL_QUEUE')
                    row=dict(row)
                    if row['receipt_json'] is None and row['attempt']==ctx['attempt_id']:raise ValueError('SAME_ATTEMPT_RECONCILIATION_STILL_MISSING')
                    seen[mid]={'molecule_id':mid,'records':n,'wire_sha256':c['wire_sha256'],'receipt':c['receipt'],
                               'receipt_sha256':H.sha(H.canonical(c['receipt'])),'context':ctx,'source_archive':str(path),'queue_before':row}
            finally:reader.close()
        expected=item['root_report']
        if (len(seen),sum(m['records'] for m in seen.values()))!=(expected['molecules'],expected['records']):
            raise ValueError('EXACT_PLANNED_OWN_RUN_SCI_COUNTS_DIFFER')
        return {'run_root':str(root),'already_closed':already,'molecules':list(seen.values()),'worker_pid':os.getpid(),'full_own_run_receipt_scan':True,'queue_metadata_read_stats':dict(q.stats)}
    finally:q.close()
class OwnReceiptDB:
    def __init__(self,real,receipts,session):self.real=real;self.receipts=receipts;self.session=session
    def execute(self,sql,parameters=()):
        if sql=='SELECT molecule_id,receipt_json FROM molecules WHERE owner=? AND receipt_json IS NOT NULL':
            if tuple(parameters)!=(self.session,):raise ValueError('OWN_CANONICAL_SESSION_DIFFERS')
            return V.DetachedReadResult([{'molecule_id':mid,'receipt_json':json.dumps(r)} for mid,r in self.receipts.items()])
        return self.real.execute(sql,parameters)
class ExportOnlyDB:
    """Keep frozen finalizer reads; reject its missing-receipt SCI-adoption update."""
    def __init__(self,real):self.real=real
    def execute(self,sql,parameters=()):
        if sql=="UPDATE molecules SET owner=?,state='RUNNING' WHERE molecule_id=?":
            raise RuntimeError('PURE_EXPORT_REQUIRES_RECONCILIATION_NOT_SCI_STATE_WRITE')
        return self.real.execute(sql,parameters)
    def __getattr__(self,name):return getattr(self.real,name)

def install_metadata_adapters(R,opt,before,authority,journal_path):
    frozen_canonical=R.canonical_index;receipts={m['molecule_id']:m['receipt'] for m in before['molecules']}
    def own_canonical(options,references,archive_path,queue):
        return frozen_canonical(options,references,archive_path,SimpleNamespace(db=OwnReceiptDB(queue.db,receipts,options['session'])))
    R.canonical_index=own_canonical
    class ExportQueue:
        def __init__(self,path,deadline=None,baseline_path=None):
            if not Path(path).is_file():raise FileNotFoundError('EXISTING_FORMAL_QUEUE_REQUIRED')
            self.path=Path(path);self.db=ExportOnlyDB(R.connection(path,deadline))
        def finish(self,*unused):raise RuntimeError('PURE_EXPORT_CANNOT_FINISH_OR_RECOMPUTE_SCI')
        def publish_export(self,session,references,archive):
            if session!=opt['session']:raise ValueError('PUBLICATION_ORIGINAL_SESSION_DIFFERS')
            encoded=json.dumps({'families':references,'archive':archive})
            for offset in range(0,len(before['molecules']),256):
                batch=before['molecules'][offset:offset+256]
                def publish():
                    entries=[]
                    for own in batch:
                        mid=own['molecule_id'];row=self.db.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone()
                        if row is None:raise ValueError('PUBLICATION_MOLECULE_DISAPPEARED')
                        row=dict(row);reason=V.guard(row,authority['session_jobs'],authority['jobs'],authority['proof'],set(authority['live_tasks']),str(opt['job_id']))
                        if reason is None and not same_execution(row,own['receipt'],session):reason='HISTORICAL_OR_NEWER_SCI_PRESERVED'
                        if reason:
                            entries.append({'molecule_id':mid,'status':'NOT_MUTATED','reason':reason,'before':row});continue
                        if row['state'] not in {'COMPLETE','RETRY_PENDING'}:raise ValueError('LATEST_SCI_STATE_NOT_CLOSED')
                        n=self.db.execute('UPDATE molecules SET export_json=?,archive_path=? WHERE molecule_id=? AND owner=? AND attempt=? AND receipt_json=? AND state=?',
                             (encoded,archive['path'],mid,session,row['attempt'],row['receipt_json'],row['state'])).rowcount
                        if n!=1:raise ValueError('SAME_EXECUTION_PUBLICATION_CAS_FAILED')
                        after=dict(self.db.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone())
                        if any(after[k]!=row[k] for k in row if k not in {'export_json','archive_path'}):
                            raise ValueError('EXPORT_MUTATED_SCI_STATE_COUNTS_RANK')
                        entries.append({'molecule_id':mid,'status':'PUBLISHED_SAME_EXECUTION','before':row,'after':after})
                    return entries
                committed=self.db.transaction(publish)
                with Path(journal_path).open('a') as f:
                    for entry in committed:f.write(json.dumps(entry,allow_nan=False)+'\n')
                    f.flush();os.fsync(f.fileno())
    R.Queue=ExportQueue
def finalizer_child(opt,before,authority,journal_path,pipe):
    try:
        import wp5_runner_v13 as R
        if H.digest(R.__file__)!=RUNNER_SHA:raise ValueError('FROZEN_R13_SOURCE_CHANGED')
        install_metadata_adapters(R,opt,before,authority,journal_path)
        result=R.finalize_run(opt)
        pipe.send({'result':result,'frozen_runner_sha256':RUNNER_SHA,'metadata_adapters':['own_run_canonical_receipts','same_execution_guarded_publication','existing_queue_no_DDL']})
    except BaseException:pipe.send({'error':traceback.format_exc(limit=16)})
    finally:pipe.close()
def own_finalize(opt,before,authority,journal_path):
    ctx=multiprocessing.get_context('spawn');parent,child=ctx.Pipe(duplex=False)
    process=ctx.Process(target=finalizer_child,args=(opt,before,authority,journal_path,child))
    process.start();child.close();outcome=None
    try:
        # Drain pipe before join. A current metadata root finishes naturally;
        # no new root starts after46h and no QM/old job is ever signalled.
        while outcome is None:
            if parent.poll(.5):
                outcome=parent.recv();break
            if not process.is_alive():break
        process.join()
        if outcome is None:return {'error':'METADATA_FINALIZER_EXIT_WITHOUT_RECEIPT','exitcode':process.exitcode}
        if process.exitcode!=0:return {'error':'METADATA_FINALIZER_NONZERO_EXIT','exitcode':process.exitcode,'outcome':outcome}
        return outcome
    finally:parent.close()
def after_scope(item,before,result,queue_path,journal_path):
    from wp5_archive_v5 import ArchiveReader
    opt=item['options'];root=Path(opt['run_root']);expected=item['root_report']
    if (result['molecules'],result['records'])!=(expected['molecules'],expected['records']):raise ValueError('PERMANENT_OWN_RUN_POPULATION_DIFFERS')
    if result['archive']['scientific_task_outcomes']!=12*expected['records']:raise ValueError('PERMANENT_SCI12N_DIFFERS')
    journal={}
    if Path(journal_path).exists():
        with Path(journal_path).open() as f:
            for line in f:
                j=json.loads(line);journal[j['molecule_id']]=j
    reader=ArchiveReader(result['archive']['path'],opt['dictionaries']);q=MetadataRead(queue_path)
    latest=historical=protected=0
    try:
        for own in before['molecules']:
            mid=own['molecule_id'];c=reader.completion(mid)
            if c is None or c['wire_sha256']!=own['wire_sha256'] or c['record_count']!=own['records'] or H.sha(H.canonical(c['receipt']))!=own['receipt_sha256']:
                raise ValueError('PERMANENT_RECEIPT_WIRE_OLD_PROVENANCE_DIFFERS')
            row=dict(q.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone());entry=journal.get(mid)
            if entry and entry['status']=='NOT_MUTATED' and entry['reason'].startswith('SKIP_'):
                protected+=1;continue
            if same_execution(row,own['receipt'],opt['session']):
                old=own['queue_before']
                if any(row[k]!=old[k] for k in ('state','attempt','owner','receipt_json','counts_json','completion_rank')):
                    raise ValueError('LATEST_SCI_STATE_RANK_CHANGED_DURING_EXPORT')
                pub=json.loads(row['export_json']) if row['export_json'] else None
                if pub is None or pub['archive']['path']!=result['archive']['path'] or pub['archive']['sha256']!=result['archive']['sha256'] or row['archive_path']!=result['archive']['path']:
                    raise ValueError('SAME_EXECUTION_QUEUE_EXPORT_NOT_CLOSED')
                latest+=1
            else:historical+=1
        if reader.db.execute('SELECT count(*) FROM completion_receipts').fetchone()[0]!=expected['molecules']:
            raise ValueError('PERMANENT_COMPLETION_POPULATION_DIFFERS')
    finally:reader.close();q.close()
    if H.digest(root/'run.json')!=expected['run_json_sha256']:raise ValueError('ORIGINAL_RUN_JSON_REWRITTEN')
    return {'run_root':str(root),'original_job_id':str(opt['job_id']),'original_session':opt['session'],
            'original_contract':item['old_contract'],'original_package':item['old_package'],'molecules':expected['molecules'],
            'records':expected['records'],'requested_outcomes':12*expected['records'],'latest_same_execution_queue_exports':latest,
            'historical_SCI_attempts_preserved':historical,'protected_queue_rows_not_mutated':protected,
            'receipt_wire_package_context_readback':True,'original_run_json_unchanged':True,
            'permanent_refs':result['families']+[result['canonical'],result['archive']],
            'queue_publication_journal':({'path':str(journal_path),'sha256':H.digest(journal_path)} if Path(journal_path).exists() else None)}
def execute(args):
    H.node_guard()
    if args.workers!=24:raise ValueError('EXACT24_CONTROL_ALLOCATION_REQUIRED')
    out=Path(args.out)
    if not out.resolve().is_relative_to((ROOT/'reports').resolve()):raise ValueError('NEW_REPORT_OUTPUT_ROOT_REQUIRED')
    out.mkdir(parents=True,exist_ok=False);start=time.monotonic();epoch=time.time();reports=[]
    base={'schema':'WP5_PHASE14_TERMINAL_EXPORT_ROOT_REPAIR_V5','implementation_version':5,'source':{'path':str(Path(__file__).resolve()),'sha256':H.digest(__file__)},
          'processing_job_id':os.environ.get('SLURM_JOB_ID'),'processing_host':socket.gethostname(),'python_version':platform.python_version(),
          'plan':{'path':str(args.plan),'sha256':args.expected_plan_sha256},'reconciliation_apply':{'path':str(args.apply_report),'sha256':args.expected_apply_sha256},
          'current_metadata_contract':{'path':str(args.contract),'sha256':CONTRACT_SHA},'frozen_runner_sha256':RUNNER_SHA,
          'QM_started':False,'original_LMDB_opened':False,'old_run_options_rewritten':False,'new_formal_phase_started':False,
          'execution_policy':'serial requested terminal roots; frozenR13 original family-worker configuration;24allocated control workers'}
    try:
        plan,items,bindings,authority=verify_inputs(args,out)
        base.update(source_binding_readback=bindings,accounting=authority['proof'],protected_jobs=authority['protected_jobs'],queue_session_read_stats=authority['queue_metadata_read_stats'],scope_manifest={'path':str(args.scope_manifest),'sha256':SCOPE_SHA},already_closed_requested_roots=authority['already_closed_requested_roots'],requested_root_count=9)
        count=min(args.workers,len(items));before=[]
        if count:
            ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(count)
            with concurrent.futures.ProcessPoolExecutor(max_workers=count,mp_context=ctx,initializer=pool_init,initargs=(barrier,)) as pool:
                before=list(pool.map(before_scope,[(item,plan['queue']) for item in items],chunksize=1))
        base['actual_SCI_verification_workers']=sorted({b['worker_pid'] for b in before})
        base['queue_metadata_before_scope_stats']=[b['queue_metadata_read_stats'] for b in before]
        base['requested_control_workers']=args.workers; base['actual_root_workers']=len(base['actual_SCI_verification_workers'])
        for index,(item,prior) in enumerate(zip(items,before)):
            label='root_'+str(index)+'_task_'+str(item['options']['task_id']);H.write_json(out/(label+'_before.json'),prior)
            options,deadline=rebase_deadlines(item['options'],start,epoch,args.metadata_hours)
            if time.monotonic()>=deadline:raise TimeoutError('46H_METADATA_ADMISSION_ENDED_NO_NEW_ROOT')
            proof=H.terminal_proof(authority['jobs'],out);live,live_tasks=V.protection(authority['jobs'],proof)
            if proof['states'].get(str(options['job_id'])) not in H.TERMINAL:raise ValueError('SOURCE_ROOT_NOT_TERMINAL')
            current={**authority,'proof':proof,'live_tasks':sorted(live_tasks)};journal=out/(label+'_queue_publication.jsonl')
            if prior['already_closed']:outcome={'result':H.load(Path(options['run_root'])/'export_completion.json'),'status':'ALREADY_CLOSED_VERIFY_ONLY'}
            else:outcome=own_finalize(options,prior,current,journal)
            H.write_json(out/(label+'_finalizer.json'),{'old_run_sha256':item['root_report']['run_json_sha256'],
                'original_contract':item['old_contract'],'original_package':item['old_package'],'original_job_session_preserved':True,
                'new_metadata_clock_host':socket.gethostname(),'rebased_controls':{k:options[k] for k in ('job_exit_monotonic','hard_monotonic','hard_epoch','admit_monotonic','sql_deadline_monotonic')},'outcome':outcome})
            if outcome.get('error'):raise RuntimeError('FROZEN_R13_EXPORT_ERROR:'+outcome['error'])
            closed=after_scope(item,prior,outcome['result'],plan['queue'],journal)
            closed.update(permanent_SHA_readback=hash_parallel(closed['permanent_refs'],args.workers),
                          metadata_export_status=outcome.get('status','EXPORTED_FROM_OWN_SCI'))
            reports.append(closed);H.write_json(out/(label+'_closure.json'),closed)
        base.update(status='PHASE14_REQUESTED_TERMINAL_ROOT_EXPORT_REPAIR_COMPLETE',roots=reports,
            molecules=sum(r['molecules'] for r in reports),records=sum(r['records'] for r in reports),
            requested_outcomes=sum(r['requested_outcomes'] for r in reports),
            latest_same_execution_queue_exports=sum(r['latest_same_execution_queue_exports'] for r in reports),
            historical_SCI_attempts_preserved=sum(r['historical_SCI_attempts_preserved'] for r in reports),
            protected_queue_rows_not_mutated=sum(r['protected_queue_rows_not_mutated'] for r in reports),
            elapsed_seconds=time.monotonic()-start)
        if (len(reports),base['molecules'],base['records'])!=authority['expected_export_counts']:raise ValueError('AUTHORITATIVE_PLAN_EXPORT_COUNTS_DIFFER')
        if len(reports)+len(authority['already_closed_requested_roots'])!=9:raise ValueError('REQUESTED9_ROOT_CLOSURE_INCOMPLETE')
        H.write_json(out/'report.json',base);print(json.dumps({k:base[k] for k in ('status','molecules','records','requested_outcomes','elapsed_seconds')}));return 0
    except BaseException:
        base.update(status='TERMINAL_EXPORT_REPAIR_RECORDED_ERROR',error=traceback.format_exc(limit=16),closed_roots=reports,elapsed_seconds=time.monotonic()-start)
        H.write_json(out/'report.json',base);print(base['error']);return 1
def check():
    ast.parse(Path(__file__).read_text());scope=H.load(SCOPE)
    assert H.digest(SCOPE)==SCOPE_SHA and len(scope['roots'])==9
    own=scope['roots'][0];job=own['job_id'];session=own['session']
    # The following states and names are private fixture facts, not actual job states.
    with tempfile.TemporaryDirectory(prefix='wp5_export_control_v5_',dir='/tmp') as td:
        path=Path(td)/'metadata.sqlite';db=sqlite3.connect(path,isolation_level=None);db.row_factory=sqlite3.Row
        db.execute('CREATE TABLE molecules(molecule_id TEXT PRIMARY KEY,task_id TEXT,state TEXT,attempt INTEGER,owner TEXT,receipt_json TEXT,counts_json TEXT,completion_rank INTEGER,export_json TEXT,archive_path TEXT)')
        receipt={'context':{'attempt_id':0,'execution_id':session+':0','job_id':job},'records':1,'counts':{'SUCCESS':12}}
        text=json.dumps(receipt);before=[]
        for mid,owner,attempt,state in [('fixture_own',session,0,'RETRY_PENDING'),('fixture_live','fixture_live_session',0,'RUNNING'),('fixture_newer','fixture_newer_session',1,'COMPLETE')]:
            db.execute('INSERT INTO molecules VALUES(?,?,?,?,?,?,?,?,?,?)',(mid,own['task_id'],state,attempt,owner,text,'{}',10,None,'old_lane'))
            before.append({'molecule_id':mid,'receipt':receipt})
        baseline={row['molecule_id']:dict(row) for row in db.execute('SELECT * FROM molecules')}
        class Connection:
            def execute(self,*args):return db.execute(*args)
            def transaction(self,fn):
                db.execute('BEGIN IMMEDIATE')
                try:value=fn();db.execute('COMMIT');return value
                except BaseException:db.execute('ROLLBACK');raise
            def close(self):pass
        original=Connection();fake=SimpleNamespace(canonical_index=lambda *args:None,connection=lambda *args:original)
        auth={'jobs':{job:{'task_id':own['task_id'],'mode':'main'},'4514410':{'task_id':'fixture_live_task','mode':'main'},'4514414':{'task_id':'fixture_newer_task','mode':'main'}},
              'proof':{'states':{job:'COMPLETED','4514410':'RUNNING','4514414':'COMPLETED'}},
              'session_jobs':{session:job,'fixture_live_session':'4514410','fixture_newer_session':'4514414'},'live_tasks':{'fixture_live_task'}}
        journal=Path(td)/'publication.jsonl';opt={'session':session,'job_id':job}
        install_metadata_adapters(fake,opt,{'molecules':before},auth,journal)
        q=fake.Queue(path);q.publish_export(session,[],{'path':'fixture_archive','sha256':'f'*64})
        rows={row['molecule_id']:dict(row) for row in db.execute('SELECT * FROM molecules')}
        for name in ('fixture_live','fixture_newer'):assert rows[name]==baseline[name]
        for key in baseline['fixture_own']:
            if key not in {'export_json','archive_path'}:assert rows['fixture_own'][key]==baseline['fixture_own'][key]
        assert rows['fixture_own']['state']=='RETRY_PENDING' and rows['fixture_own']['export_json']
        try:q.db.execute("UPDATE molecules SET owner=?,state='RUNNING' WHERE molecule_id=?",('x','fixture_own'));raise AssertionError('SCI adoption update allowed')
        except RuntimeError as exc:assert 'NOT_SCI_STATE_WRITE' in str(exc)
        db.close()
    print('PURE_EXPORT_V5_PRIVATE_METADATA_CAS_RETRY_PROTECTION_PASS_NO_QM_NO_SCI_NO_PRODUCTION_QUEUE')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
    p.add_argument('--plan',type=Path);p.add_argument('--expected-plan-sha256');p.add_argument('--apply-report',type=Path);p.add_argument('--expected-apply-sha256');p.add_argument('--scope-manifest',type=Path,default=SCOPE)
    p.add_argument('--contract',type=Path,default=CONTRACT);p.add_argument('--out',type=Path)
    p.add_argument('--workers',type=int,default=24);p.add_argument('--metadata-hours',type=float,default=46)
    args=p.parse_args()
    if args.check:
        check()
    else:
        if not args.out:p.error('--out required')
        if not 0<args.metadata_hours<=46:p.error('metadata-hours must be<=46')
        raise SystemExit(execute(args))
