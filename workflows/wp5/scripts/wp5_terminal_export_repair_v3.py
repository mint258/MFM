"""Pure export of the exact19 terminal roots in actualV4 plan; noQM/LMDB.
Frozen R11 numeric export stays unchanged. Own-run receipt and guarded latest
publication adapters exist only in this metadata worker; frozen files stay intact.
"""
from __future__ import annotations
import argparse,ast,concurrent.futures,json,multiprocessing,os,platform,socket,time,traceback,sqlite3,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
import wp5_queue_reconcile_v4 as V
H=V.H;ROOT=H.ROOT
PLAN=ROOT/'reports/terminal_subset_dryrun_v4_job_4514264/plan.json'
PLAN_SHA='7c3ca934f3b9534c9a11721ff487c073297fe2fe91adf5bb1a3158967dbc43a8'
APPLY=ROOT/'reports/terminal_subset_apply_v4_job_4514265/report.json'
APPLY_SHA='a9777aff3536b7ff5826ea2d65549d6cafb205b679420ed9b5d65bde139db427'
CONTRACT=ROOT/'configs/production_contract_v4.json'
CONTRACT_SHA='41852032a9f063ed5c4fe88912ad72ec65b1b0e69fd4c11e9ccbb0db65f2b84d'
RUNNER_SHA='e7828b4b78e42cd9a31c686ee30190cc9e788630d9c737980300606aa0236e7b'
EXPORT_SHA='0e9e89ccb977924795e3239d7d97ab3ae21fe8ef60b80fed39c1e1b7ddafe3db'
EXPECTED=(19,13735,95413)
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
    for path,wanted in ((args.plan,PLAN_SHA),(args.apply_report,APPLY_SHA),(args.contract,CONTRACT_SHA)):
        if H.digest(path)!=wanted:raise ValueError('EXACT_ACTUAL_PLAN_APPLY_CONTRACT_SHA_REQUIRED:'+str(path))
    plan=H.load(args.plan);applied=H.load(args.apply_report);contract=H.load(args.contract)
    if plan['status']!='REVIEWABLE_TERMINAL_SUBSET_DRY_RUN' or plan['conflicts'] or not plan['all_selected_root_scans_complete']:
        raise ValueError('FULL_CONFLICT_FREE_ROOT_SCAN_REQUIRED')
    if (applied['status'] not in {'TERMINAL_SUBSET_APPLIED_AND_VERIFIED','APPLIED_AND_VERIFIED'} or
        applied['plan']['sha256']!=PLAN_SHA or not applied['all_applied_rows_verified'] or len(applied['results'])!=178 or
        any(not r.get('verified') or r['status'] not in {'APPLIED','ALREADY_APPLIED'} for r in applied['results'])):
        raise ValueError('ACTUAL178_APPLY_READBACK_REQUIRED')
    if contract['schema']!='WP5_PRODUCTION_CONTRACT_V1' or contract['status']!='PRODUCTION_CONTRACT_FROZEN' or contract['policy']!=H.POLICY:
        raise ValueError('CURRENT_METADATA_CONTRACT4_SCOPE_DIFFERS')
    for key in ('export_roots','run_reports','actions','queue_snapshot','already_closed_roots','skipped'):
        ref=plan[key]
        if H.digest(ref['path'])!=ref['sha256']:raise ValueError('PLAN_LEAF_CHANGED:'+key)
    if plan['export_roots']['sha256']!=EXPORT_SHA:raise ValueError('EXACT19_EXPORT_ROOTS_REQUIRED')
    selected=H.load(plan['export_roots']['path'])
    if (len(selected),sum(r['molecules'] for r in selected),sum(r['records'] for r in selected))!=EXPECTED:
        raise ValueError('EXACT19_13735_95413_SCOPE_DIFFERS')
    sources={r['path']:r for r in contract['sources']};references=[]
    for name in SCI+('wp5_runner_v11.py','wp5_accounting_v2.py'):
        p=str(ROOT/'scripts'/name)
        if p not in sources:raise ValueError('CURRENT_METADATA_SOURCE_NOT_BOUND:'+name)
        references.append(sources[p])
    if sources[str(ROOT/'scripts/wp5_runner_v11.py')]['sha256']!=RUNNER_SHA:raise ValueError('FROZEN_R11_BINDING_DIFFERS')
    references += [contract[k] for k in ('protocol','registry','audit_manifest','reproduction_package','node_authority','node_scope_plan','authority')]
    jobs,manifests,registered_receipts=V.registry([r['path'] for r in plan['manifests']])
    if manifests!=plan['manifests']:raise ValueError('REGISTERED229_MANIFEST_BINDINGS_CHANGED')
    proof=H.terminal_proof(jobs,out);live,live_tasks=V.protection(jobs,proof);runs=[]
    q=MetadataRead(plan['queue'])
    try:session_jobs=dict(q.execute('SELECT session_id,job_id FROM sessions').fetchall())
    finally:q.close()
    for r in selected:
        if not r.get('scan_complete') or not r.get('repair_claim_allowed'):raise ValueError('INTERRUPTED_ROOT_EXPORT_FORBIDDEN')
        root=Path(r['run_root']);run=H.load(root/'run.json');old=run['options']
        if H.digest(root/'run.json')!=r['run_json_sha256']:raise ValueError('ORIGINAL_RUN_JSON_CHANGED')
        if not root.resolve().is_relative_to((ROOT/'runtime').resolve()) or root.resolve()!=Path(old['run_root']).resolve():
            raise ValueError('ORIGINAL_RUN_ROOT_SCOPE_DIFFERS')
        if str(old['job_id'])!=r['job_id'] or old['session']!=r['session'] or proof['states'].get(r['job_id']) not in H.TERMINAL:
            raise ValueError('SOURCE_RUN_NOT_EXACT_REGISTERED_TERMINAL')
        old_refs={x['path']:x['sha256'] for x in old['source_bindings']}
        for name in SCI:
            p=str(ROOT/'scripts'/name)
            if old_refs.get(p)!=sources[p]['sha256']:raise ValueError('SCI_SOURCE_CHANGED_SINCE_EXECUTION:'+name)
        for old_key,new_key in (('protocol','protocol'),('registry','registry'),('audit_membership','audit_manifest')):
            if old_refs.get(old[old_key])!=contract[new_key]['sha256']:raise ValueError('OLD_SCI_AUTHORITY_DIFFERS:'+old_key)
        references.extend(old['source_bindings'])
        runs.append({'root_report':r,'options':old,'old_contract':{'path':old['production_contract'],'sha256':H.digest(old['production_contract'])},
                     'old_package':{'path':old['reproduction_package'],'sha256':old['reproduction_package_sha256']}})
    by_path={}
    for ref in references:
        if ref['path'] in by_path and by_path[ref['path']]['sha256']!=ref['sha256']:raise ValueError('SOURCE_EXPECTED_SHA_CONFLICT:'+ref['path'])
        by_path[ref['path']]=ref
    bindings=hash_parallel(list(by_path.values()),args.workers)
    return plan,runs,bindings,{'jobs':jobs,'session_jobs':session_jobs,'proof':proof,'live_tasks':sorted(live_tasks),
                             'protected_jobs':{j:proof['states'][j] for j in sorted(live)},'queue_metadata_read_stats':dict(q.stats)}
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
def install_metadata_adapters(R,opt,before,authority,journal_path):
    frozen_canonical=R.canonical_index;receipts={m['molecule_id']:m['receipt'] for m in before['molecules']}
    def own_canonical(options,references,archive_path,queue):
        return frozen_canonical(options,references,archive_path,SimpleNamespace(db=OwnReceiptDB(queue.db,receipts,options['session'])))
    R.canonical_index=own_canonical
    class ExportQueue:
        def __init__(self,path,deadline=None,baseline_path=None):
            if not Path(path).is_file():raise FileNotFoundError('EXISTING_FORMAL_QUEUE_REQUIRED')
            self.path=Path(path);self.db=R.connection(path,deadline)
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
        import wp5_runner_v11 as R
        if H.digest(R.__file__)!=RUNNER_SHA:raise ValueError('FROZEN_R11_SOURCE_CHANGED')
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
    if args.workers!=16:raise ValueError('EXACT16_SCI_EXPORT_WORKERS_REQUIRED')
    out=Path(args.out)
    if not out.resolve().is_relative_to((ROOT/'reports').resolve()):raise ValueError('NEW_REPORT_OUTPUT_ROOT_REQUIRED')
    out.mkdir(parents=True,exist_ok=False);start=time.monotonic();epoch=time.time();reports=[]
    base={'schema':'WP5_TERMINAL_NINETEEN_ROOT_EXPORT_REPAIR_V3','implementation_version':3,'source':{'path':str(Path(__file__).resolve()),'sha256':H.digest(__file__)},
          'processing_job_id':os.environ.get('SLURM_JOB_ID'),'processing_host':socket.gethostname(),'python_version':platform.python_version(),
          'plan':{'path':str(args.plan),'sha256':PLAN_SHA},'reconciliation_apply':{'path':str(args.apply_report),'sha256':APPLY_SHA},
          'current_metadata_contract':{'path':str(args.contract),'sha256':CONTRACT_SHA},'frozen_runner_sha256':RUNNER_SHA,
          'QM_started':False,'original_LMDB_opened':False,'old_run_options_rewritten':False,'new_formal_phase_started':False,
          'execution_policy':'serial19 roots; frozenR11 16 family workers per root'}
    try:
        plan,items,bindings,authority=verify_inputs(args,out)
        base.update(source_binding_readback=bindings,accounting=authority['proof'],protected_jobs=authority['protected_jobs'],queue_session_read_stats=authority['queue_metadata_read_stats'])
        ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(args.workers)
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=ctx,initializer=pool_init,initargs=(barrier,)) as pool:
            before=list(pool.map(before_scope,[(item,plan['queue']) for item in items],chunksize=1))
        base['actual_SCI_verification_workers']=sorted({b['worker_pid'] for b in before})
        base['queue_metadata_before_scope_stats']=[b['queue_metadata_read_stats'] for b in before]
        if len(base['actual_SCI_verification_workers'])!=16:raise ValueError('16ACTUAL_SCI_VERIFICATION_WORKERS_NOT_OBSERVED')
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
            if outcome.get('error'):raise RuntimeError('FROZEN_R11_EXPORT_ERROR:'+outcome['error'])
            closed=after_scope(item,prior,outcome['result'],plan['queue'],journal)
            closed.update(permanent_SHA_readback=hash_parallel(closed['permanent_refs'],args.workers),
                          metadata_export_status=outcome.get('status','EXPORTED_FROM_OWN_SCI'))
            reports.append(closed);H.write_json(out/(label+'_closure.json'),closed)
        base.update(status='EXACT19_TERMINAL_ROOT_EXPORT_REPAIR_COMPLETE',roots=reports,
            molecules=sum(r['molecules'] for r in reports),records=sum(r['records'] for r in reports),
            requested_outcomes=sum(r['requested_outcomes'] for r in reports),
            latest_same_execution_queue_exports=sum(r['latest_same_execution_queue_exports'] for r in reports),
            historical_SCI_attempts_preserved=sum(r['historical_SCI_attempts_preserved'] for r in reports),
            protected_queue_rows_not_mutated=sum(r['protected_queue_rows_not_mutated'] for r in reports),
            elapsed_seconds=time.monotonic()-start)
        if (len(reports),base['molecules'],base['records'])!=EXPECTED:raise ValueError('EXACT19_ROOT_CLOSURE_DIFFERS')
        H.write_json(out/'report.json',base);print(json.dumps({k:base[k] for k in ('status','molecules','records','requested_outcomes','elapsed_seconds')}));return 0
    except BaseException:
        base.update(status='TERMINAL_EXPORT_REPAIR_RECORDED_ERROR',error=traceback.format_exc(limit=16),closed_roots=reports,elapsed_seconds=time.monotonic()-start)
        H.write_json(out/'report.json',base);print(base['error']);return 1
def check():
    ast.parse(Path(__file__).read_text());import sqlite3
    r={'records':1,'counts':{'x':1},'context':{'attempt_id':0,'execution_id':'s:0','job_id':'1'}}
    row={'owner':'s','attempt':0,'receipt_json':json.dumps(r)}
    assert same_execution(row,r,'s')
    assert not same_execution({**row,'owner':'new'},r,'s')
    assert not same_execution({**row,'attempt':1},r,'s')
    assert not same_execution({**row,'receipt_json':json.dumps({**r,'context':{**r['context'],'execution_id':'s:other'}})},r,'s')
    db=sqlite3.connect(':memory:');own=OwnReceiptDB(db,{'m':r},'s')
    got=list(own.execute('SELECT molecule_id,receipt_json FROM molecules WHERE owner=? AND receipt_json IS NOT NULL',('s',)))
    assert len(got)==1 and json.loads(got[0]['receipt_json'])==r
    assert own.execute('SELECT 42').fetchone()[0]==42
    old={'session':'original','job_id':1,'production_contract':'old3','reproduction_package':'pkg3','source_bindings':['old'],'hard_monotonic':-10}
    rebased,d=rebase_deadlines(old,1000,2000,46)
    assert d==1000+46*3600 and rebased['job_exit_monotonic']==1000+48*3600 and old['hard_monotonic']==-10
    for k in old:
        if k!='hard_monotonic':assert old[k]==rebased[k]
    tree=ast.parse(Path(__file__).read_text())
    called={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
    assert not called.intersection({'initialize_worker','compute_molecule','claim','read_native','invoke'})
    db.close();print('OWN_RECEIPT_CANONICAL_LATEST_EXECUTION_DEADLINE_FIXTURE_PASS_NO_QM_NO_LMDB_NO_FORMAL_QUEUE')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
    p.add_argument('--plan',type=Path,default=PLAN);p.add_argument('--apply-report',type=Path,default=APPLY)
    p.add_argument('--contract',type=Path,default=CONTRACT);p.add_argument('--out',type=Path)
    p.add_argument('--workers',type=int,default=16);p.add_argument('--metadata-hours',type=float,default=46)
    args=p.parse_args()
    if args.check:
        check();hotjournal_fixture()
    else:
        if not args.out:p.error('--out required')
        if not 0<args.metadata_hours<=46:p.error('metadata-hours must be<=46')
        raise SystemExit(execute(args))
