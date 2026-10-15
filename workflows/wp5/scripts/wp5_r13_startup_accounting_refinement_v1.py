"""One metadata-only supplement; keep original78 startup evidence intact."""
from __future__ import annotations
import hashlib,json,os,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
ORIGINAL=ROOT/'reports/r13_actual78_startup_fact_review_v1.json'
OUT=ROOT/'reports/r13_actual78_startup_fact_review_accounting_followup_v1.json'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def small(path):
    p=Path(path)
    if not p.exists():return None
    if p.stat().st_uid!=1278 or p.stat().st_size>2<<20:raise ValueError('SMALL_OWNED_METADATA_REQUIRED')
    return json.loads(p.read_bytes())
def main():
    if os.getuid()!=1278:raise ValueError('UID1278_REQUIRED')
    old=small(ORIGINAL)
    if sha(ORIGINAL)!='79ab1d682d429d169006f688968306d7fd1dd4dc16387631e0fc527ff3839f24':raise ValueError('ORIGINAL_SNAPSHOT_SHA_DIFFERS')
    jobs=[str(case['job_id']) for case in old['cases']]
    import wp5_accounting_v2 as A
    r=A.run_sacct(['-X','-n','-P','-j',','.join(jobs),'--format=JobID,User,State'],
        evidence_path=ROOT/'reports/r13_actual78_startup_accounting_followup_v1.json',
        wait_seconds=120,max_age_seconds=180)
    states={}
    if r.returncode==0:
        for line in r.stdout.splitlines():
            p=line.strip().split('|')
            if p and p[-1]=='':p=p[:-1]
            if len(p)!=3 or p[1]!='zixiao':raise ValueError('EXACT_ACTUAL_SACCT_USER_WIDTH_REQUIRED')
            states[p[0]]=p[2].split()[0]
        if set(states)!=set(jobs):raise ValueError('EXACT78_IDS_REQUIRED')
    refined=[]
    for job in ('4514359','4514365'):
        case=next(case for case in old['cases'] if str(case['job_id'])==job)
        for root in case['roots']:
            path=Path(root['run_root']);comp=small(path/'completion.json')
            stage=small(path/'staging_summary.json');index=small(path/'input_index.json')
            info={'job_id':job,'task_id':case['task_id'],'run_root':str(path),'state':states.get(job),
                  'completion_present':comp is not None,'staging_summary':stage,'input_index':index}
            if comp is not None:
                workers=comp.get('workers',[]);matched=0
                for worker in workers:
                    text=json.dumps(worker.get('errors',[]))
                    matched+=bool('FileNotFoundError' in text and 'load_production_metadata' in text and 'runs/phase1_wp5_20261011/scripts/wp5_recovery_hourly_watch_v5.py' in text)
                info.update(completion_sha256=sha(path/'completion.json'),worker_count=len(workers),
                    same_cwd_failure_workers=matched,worker_completed_sum=sum(w.get('completed',0) for w in workers),
                    worker_error_count_sum=sum(w.get('error_count',0) for w in workers),
                    completed_molecules_this_run=comp.get('completed_molecules_this_run'),
                    completed_records_this_run=comp.get('completed_records_this_run'),
                    new_scientific_outcomes=(comp.get('archive') or {}).get('scientific_task_outcomes'),
                    new_raw_records=(comp.get('archive') or {}).get('raw_records'))
            refined.append(info)
    import collections
    main=[case for case in old['cases'] if case['mode']=='main']
    cleanup=[case for case in old['cases'] if case['mode']=='cleanup']
    summary={'fresh_actual_states_available':r.returncode==0,
       'main_actual_states':dict(collections.Counter(states.get(str(c['job_id']),'UNKNOWN') for c in main)),
       'cleanup_actual_states':dict(collections.Counter(states.get(str(c['job_id']),'UNKNOWN') for c in cleanup)),
       'cleanup_nonterminal':[{'job_id':c['job_id'],'state':states.get(str(c['job_id'])),'node':c['node']} for c in cleanup if states.get(str(c['job_id'])) not in A.TERMINAL],
       'main_cwd_failure_jobs':old['summary']['main_same_cwd_failure_roots'],
       'main_empty_scope_jobs':1,'original_zero_claim_sessions':old['summary']['sessions_found'],
       'original_all78_claims_zero':old['summary']['all78_session_claims_zero'],
       'original_new_SCI_and_raw':{'scientific_outcomes':old['summary']['scientific_outcomes_total'],'raw_records':old['summary']['raw_records_total']}}
    later_cleanup=next((x for x in refined if x['job_id']=='4514365'),None)
    if later_cleanup and later_cleanup.get('worker_count')==24 and later_cleanup.get('same_cwd_failure_workers')==24:
        summary.update(cleanup_same_cwd_failure_jobs=6,total_same_cwd_failure_workers=old['summary']['same_cwd_failure_workers']+24,
                       all78_completion_roots_present=True)
    else:summary.update(cleanup_same_cwd_failure_jobs=5,total_same_cwd_failure_workers=old['summary']['same_cwd_failure_workers'],
                        all78_completion_roots_present=bool(later_cleanup and later_cleanup['completion_present']))
    report={'schema':'WP5_R13_STARTUP_ACCOUNTING_FOLLOWUP_V1','status':'READ_ONLY_ACTUAL_STARTUP_FACT_SUPPLEMENT_NOT_SCHEDULE_PASS',
       'created_epoch':time.time(),'original_report':{'path':str(ORIGINAL),'sha256':sha(ORIGINAL)},
       'source':{'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},
       'accounting':{'returncode':r.returncode,'error':r.stderr,'evidence_path':r.evidence_path,'evidence_sha256':sha(r.evidence_path),'provenance':r.evidence.get('provenance')},
       'summary':summary,'actual_states':states,'two_root_metadata':refined,
       'SCI_raw_labels_or_original_data_read':False,'queue_written':False,'source_modified':False,'QM_or_submission_or_STOP_started':False}
    with OUT.open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'report':str(OUT),'sha256':sha(OUT),'summary':summary,'two_root_metadata':refined,'accounting_returncode':r.returncode},allow_nan=False))
if __name__=='__main__':main()
