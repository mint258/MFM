"""Actual R13 startup facts: small JSON metadata and78 session rows only.
No raw/labels/original LMDB scans, no source or queue mutation, no submissions.
"""
from __future__ import annotations
import collections,getpass,hashlib,json,os,re,socket,stat,time,traceback
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
PROJECT=Path('/share/home/zixiao/descriptor_analysis')
MANIFEST=ROOT/'submission/recovery_attempt_v13/submitted_jobs.json'
EXPECTED_SHA='8d16cbbf21354fc6e0dac43c1713e4979e0a041ce86926dc31bb6985fe72393d'
OUT=ROOT/'reports/r13_actual78_startup_fact_review_v1.json'
WATCH='runs/phase1_wp5_20261011/scripts/wp5_recovery_hourly_watch_v5.py'
MAX_JSON=2<<20
def sha_bytes(data):return hashlib.sha256(data).hexdigest()
def small(path):
    p=Path(path)
    if not p.exists():return None,None
    st=p.lstat()
    if st.st_uid!=1278 or not stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode):
        raise ValueError('METADATA_FILE_UID_OR_TYPE:'+str(p))
    if st.st_size>MAX_JSON:raise ValueError('SMALL_JSON_LIMIT:'+str(p))
    data=p.read_bytes()
    return json.loads(data),{'path':str(p),'bytes':len(data),'sha256':sha_bytes(data),'uid':st.st_uid,'mtime_epoch':st.st_mtime}
def totals(rows,key):
    values=[row.get(key) for row in rows]
    return sum(values) if all(type(v) is int for v in values) else None
def inspect(entry):
    job=str(entry['job_id']);task=str(entry['task_id'])
    row={k:entry[k] for k in ('job_id','task_id','mode','node','receipt')}
    roots=sorted((ROOT/'runtime'/('task_'+task)).glob('job_'+job+'_*'))
    row['root_count']=len(roots);row['roots']=[]
    for root in roots:
        current={'run_root':str(root),'metadata_refs':[]}
        try:
            run,ref=small(root/'run.json')
            if ref:current['metadata_refs'].append(ref)
            if run is None:raise ValueError('RUNTIME_RUN_JSON_MISSING')
            options=run['options']
            if str(options['job_id'])!=job or str(options['task_id'])!=task or run['node']!=entry['node']:
                raise ValueError('EXACT_RUN_JOB_TASK_NODE_DIFFERS')
            current.update(session=options['session'],original_contract=options.get('production_contract'),
                           original_package=options.get('reproduction_package'),actual_node=run['node'])
            # Keep actual original context; only parse small closure JSON.
            objects={}
            for name in ('completion.json','checkpoint.json','input_index.json','staging_summary.json','export_completion.json','runtime_error.json','export_error.json','queue_end_error.json'):
                obj,ref=small(root/name)
                objects[name]=obj
                if ref:current['metadata_refs'].append(ref)
            completion=objects['completion.json']
            current['completion_present']=completion is not None
            if completion is not None:
                workers=completion.get('workers',[]);same=[]
                for worker in workers:
                    errors=worker.get('errors',[])
                    text='\n'.join(error if isinstance(error,str) else json.dumps(error,ensure_ascii=False) for error in errors)
                    is_cwd=(bool(errors) and 'FileNotFoundError' in text and WATCH in text and
                            'load_production_metadata' in text and 'wp5_engine_v3.py' in text)
                    if is_cwd:same.append(worker.get('lane'))
                current.update(completion_status=completion.get('status'),
                    completed_molecules_this_run=completion.get('completed_molecules_this_run'),
                    completed_records_this_run=completion.get('completed_records_this_run'),
                    worker_count=len(workers),worker_completed_sum=totals(workers,'completed'),
                    worker_error_count_sum=totals(workers,'error_count'),
                    same_relative_cwd_error_workers=len(same),same_relative_cwd_error_lanes=same,
                    scientific_outcomes=(completion.get('archive') or {}).get('scientific_task_outcomes'),
                    raw_records=(completion.get('archive') or {}).get('raw_records'),
                    exported_families=len(completion.get('families') or []),
                    all_workers_cleanup_removed=bool(workers) and all(w.get('cleanup',{}).get('work_root_removed') is True for w in workers),
                    example_error_last_lines=[])
                if same:
                    worker=next(w for w in workers if w.get('lane') in same)
                    err=worker['errors'][0]
                    if isinstance(err,dict):text=next((v for v in err.values() if isinstance(v,str)),json.dumps(err))
                    else:text=err
                    current['example_error_last_lines']=text.splitlines()[-5:]
            else:current.update(completion_status=None,same_relative_cwd_error_workers=None)
            stage=objects['staging_summary.json']
            current['staging_summary']=({k:stage.get(k) for k in ('molecules','records','compressed_wire_bytes','uncompressed_wire_bytes')} if stage else None)
            current['input_index']=objects['input_index.json']
            current['other_small_error_files']=[k for k in ('runtime_error.json','export_error.json','queue_end_error.json') if objects[k] is not None]
            current['classification']=('STARTUP_RELATIVE_CWD_ERROR_BEFORE_QM' if completion is not None and current['worker_count']==24 and
                current['same_relative_cwd_error_workers']==24 and current['worker_completed_sum']==0 else
                'CLOSURE_WITH_OTHER_OR_PARTIAL_EVIDENCE' if completion is not None else 'NO_COMPLETION_YET')
        except BaseException:current.update(classification='METADATA_READ_ERROR',error=traceback.format_exc(limit=5))
        row['roots'].append(current)
    return row
def main():
    if os.getuid()!=1278 or getpass.getuser()!='zixiao':raise ValueError('ACTUAL_UID1278_ZIXIAO_REQUIRED')
    if OUT.exists():raise FileExistsError('Independent report already exists; preserve evidence')
    started=time.time();doc,mref=small(MANIFEST)
    if mref['sha256']!=EXPECTED_SHA or doc['status']!='ALL_MAIN_AND_SIX_CLEANUP_SUBMITTED' or doc.get('error') is not None:
        raise ValueError('EXACT_ACTUAL_R13_SUBMISSION_REQUIRED')
    entries=doc['main']+doc['cleanup'];jobs=[str(e['job_id']) for e in entries]
    if (len(doc['main']),len(doc['cleanup']),len(set(jobs)))!=(72,6,78):raise ValueError('ACTUAL72_PLUS6_UNIQUE_REQUIRED')
    receipt_refs=[]
    for entry in entries:
        receipt,ref=small(entry['receipt'])
        if str(receipt['job_id'])!=str(entry['job_id']) or receipt['node']!=entry['node'] or receipt.get('uid')!=1278 or receipt.get('user')!='zixiao':
            raise ValueError('ACTUAL_JOB_RECEIPT_UID_USER_NODE_DIFFERS')
        receipt_refs.append(ref)
    import wp5_accounting_v2 as A
    r=A.run_sacct(['-X','-n','-P','-j',','.join(jobs),'--format=JobID,User,State'],
        evidence_path=ROOT/'reports/r13_actual78_startup_accounting_v1.json',wait_seconds=0,max_age_seconds=180)
    states={};accounting_error=None
    if r.returncode==0:
        for line in r.stdout.splitlines():
            if not line.strip():continue
            parts=line.strip().split('|')
            if len(parts)!=3 or parts[1]!='zixiao':raise ValueError('ACTUAL_SACCT_USER_FORMAT_DIFFERS')
            states[parts[0]]=parts[2]
        if set(states)!=set(jobs):raise ValueError('EXACT78_FRESH_SACCT_IDS_DIFFERS')
    else:accounting_error=r.stderr
    cases=[inspect(entry) for entry in entries]
    sessions=[];sql_error=None;read_stats=None
    try:
        from wp5_queue_reconcile_v4 import BoundedReadonly
        database=BoundedReadonly(ROOT/'queue/pending.sqlite')
        try:
            sessions=[dict(row) for row in database.execute(
                'SELECT session_id,job_id,task_id,mode,claims,start,end FROM sessions WHERE job_id IN ('+
                ','.join('?' for unused in jobs)+')',jobs).fetchall()]
        finally:read_stats=dict(database.stats);database.close()
    except BaseException:sql_error=traceback.format_exc(limit=5)
    by_session=collections.defaultdict(list)
    for row in sessions:by_session[str(row['job_id'])].append(row)
    for case in cases:
        case['actual_state_at_snapshot']=states.get(str(case['job_id']))
        case['sessions']=by_session[str(case['job_id'])]
        case['claims_sum']=sum(s['claims'] for s in case['sessions']) if case['sessions'] and all(type(s['claims']) is int for s in case['sessions']) else None
    closed=[root for case in cases for root in case['roots'] if root.get('completion_present')]
    main_roots=[root for case in cases if case['mode']=='main' for root in case['roots']]
    cleanup_roots=[root for case in cases if case['mode']=='cleanup' for root in case['roots']]
    summary={'fresh_state_counts':dict(collections.Counter(states.values())),
        'main_current_states':dict(collections.Counter(states.get(str(c['job_id']),'UNKNOWN') for c in cases if c['mode']=='main')),
        'cleanup_current_states':dict(collections.Counter(states.get(str(c['job_id']),'UNKNOWN') for c in cases if c['mode']=='cleanup')),
        'main_roots':len(main_roots),'cleanup_roots':len(cleanup_roots),'completion_roots_read':len(closed),
        'main_same_cwd_failure_roots':sum(c.get('classification')=='STARTUP_RELATIVE_CWD_ERROR_BEFORE_QM' for c in main_roots),
        'cleanup_same_cwd_failure_roots':sum(c.get('classification')=='STARTUP_RELATIVE_CWD_ERROR_BEFORE_QM' for c in cleanup_roots),
        'same_cwd_failure_workers':sum(c.get('same_relative_cwd_error_workers') or 0 for c in closed),
        'completed_molecules_this_run_total':totals(closed,'completed_molecules_this_run'),
        'completed_records_this_run_total':totals(closed,'completed_records_this_run'),
        'worker_completed_sum_total':totals(closed,'worker_completed_sum'),
        'scientific_outcomes_total':totals(closed,'scientific_outcomes'),
        'raw_records_total':totals(closed,'raw_records'),
        'sessions_found':len(sessions),'sessions_unique_jobs':len(by_session),
        'claims_sum':sum(s['claims'] for s in sessions) if sessions and all(type(s['claims']) is int for s in sessions) else None,
        'all78_session_claims_zero':len(by_session)==78 and all(c['claims_sum']==0 for c in cases),
        'cleanup_nonterminal_jobs':[{'job_id':c['job_id'],'node':c['node'],'state':c['actual_state_at_snapshot']} for c in cases if c['mode']=='cleanup' and c['actual_state_at_snapshot'] not in {'COMPLETED','FAILED','CANCELLED','NODE_FAIL','OUT_OF_MEMORY','TIMEOUT','BOOT_FAIL','DEADLINE','PREEMPTED'}],
        'metadata_read_error_roots':sum(root.get('classification')=='METADATA_READ_ERROR' for case in cases for root in case['roots'])}
    batch=ROOT/'scripts/wp5_main_v13.sbatch'
    batch_text=batch.read_text()
    report={'schema':'WP5_R13_ACTUAL78_READONLY_STARTUP_FACT_REVIEW_V1','status':'STARTUP_FAILURE_FACTS_NOT_SCHEDULE_PASS',
        'created_epoch':time.time(),'read_seconds':time.time()-started,'actor_uid':os.getuid(),'actor_host':socket.gethostname(),
        'source':{'path':str(Path(__file__).resolve()),'sha256':sha_bytes(Path(__file__).read_bytes())},
        'actual_submission':mref,'registered_job_receipts':receipt_refs,
        'accounting':{'returncode':r.returncode,'error':accounting_error,'evidence_path':r.evidence_path,
                      'evidence_sha256':sha_bytes(Path(r.evidence_path).read_bytes()),'provenance':r.evidence.get('provenance')},
        'summary':summary,'cases':cases,'session_query':{'scope':'Exactly actual78 jobIDs, sessions table only; no molecules/raw query',
            'read_only':True,'error':sql_error,'read_stats':read_stats},
        'cwd_evidence':{'missing_relative_asset':WATCH,'project_source_exists':(PROJECT/WATCH).is_file(),
            'ROOT_relative_source_exists':(ROOT/WATCH).is_file(),
            'main_v13':{'path':str(batch),'sha256':sha_bytes(batch.read_bytes())},
            'declared_cd_lines':[line.strip() for line in batch_text.splitlines() if line.lstrip().startswith('cd ')]},
        'interpretation':'SLURM COMPLETED0 and WP5_JOB_CLOSED do not establish scientific success. Actual init errors and zero claims/outcomes are reported separately.',
        'scientific_raw_or_label_bodies_read':False,'original_LMDB_opened':False,'science_raw_queue_written':False,
        'frozen_sources_modified':False,'submission_STOP_or_signals_modified':False}
    with OUT.open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'report':str(OUT),'report_sha256':sha_bytes(OUT.read_bytes()),'summary':summary,
                      'cwd_evidence':report['cwd_evidence'],'accounting_returncode':r.returncode,'session_query_error':sql_error},allow_nan=False))
if __name__=='__main__':main()
