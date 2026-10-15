"""Small read-only log/receipt collector for exactly73 replacement Slurm jobs.
Run on sonmi: no SQLite connect, raw/SCI payload, original LMDB, QM or submits.
"""
from __future__ import annotations
import argparse,concurrent.futures,datetime,hashlib,json,os,re,socket,time,traceback
from collections import Counter
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
SUB=ROOT/'submission/startup_replacement_v1/submitted_jobs.json'
OBS=ROOT/'reports/observation_latest.json'
LIMIT=32*1024
MAX_JSON=256*1024

def sha(b):return hashlib.sha256(b).hexdigest()
def read_json(path):
    raw=Path(path).read_bytes();return json.loads(raw),{'path':str(path),'bytes':len(raw),'sha256':sha(raw)}
def tail(path):
    path=Path(path)
    if not path.is_file():return {'path':str(path),'exists':False,'bytes':None,'tail_bytes':0,'text':''}
    with path.open('rb') as f:
        f.seek(0,2);size=f.tell();f.seek(max(0,size-LIMIT));raw=f.read(LIMIT)
    return {'path':str(path),'exists':True,'bytes':size,'tail_bytes':len(raw),'tail_sha256':sha(raw),'text':raw.decode('utf-8','replace')}
def safe_text(value,limit=32768):
    if value is None:return None
    text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)
    return text[-limit:]
def worker_rows(value):
    if isinstance(value,list):return [v for v in value if isinstance(v,dict)]
    if isinstance(value,dict):
        for key in ('reports','workers','lanes'):
            if isinstance(value.get(key),list):return worker_rows(value[key])
        return [value]
    return []
def number(value):return value if isinstance(value,(int,float)) and not isinstance(value,bool) else None

def metadata(path):
    path=Path(path);size=path.stat().st_size
    if size>MAX_JSON:return {'path':str(path),'name':path.name,'bytes':size,'not_read_reason':'EXCEEDS256KiB_SMALL_JSON_LIMIT'}
    doc,ref=read_json(path);out={**ref,'name':path.name}
    if not isinstance(doc,dict):return {**out,'read_error':'JSON_NOT_OBJECT'}
    for key in ('status','molecules','records','requested_outcomes','completed_records_this_run','actual_completed_records_this_run'):
        if key in doc:out[key]=doc[key]
    for key in ('error','traceback','runtime_error'):
        if key in doc:out[key]=safe_text(doc[key])
    if path.name=='run.json':
        opt=doc.get('options',{});out['run_scope']={k:opt.get(k) for k in ('session','job_id','task_id','mode','production_contract','reproduction_package','queue','hard_epoch')}
    workers=worker_rows(doc.get('workers',doc.get('worker_reports')))
    if workers:
        completed=[number(v.get('completed')) for v in workers]
        out['worker_completed']=sum(v for v in completed if v is not None)
        out['worker_errors']=[safe_text(v['errors']) for v in workers if v.get('errors')]
        out['worker_report_count']=len(workers)
    if isinstance(doc.get('archive'),dict):out['archive']={k:doc['archive'].get(k) for k in ('path','sha256','bytes','molecules','raw_records','scientific_task_outcomes')}
    if isinstance(doc.get('families'),list):out['family_refs']=[{k:r.get(k) for k in ('family','path','sha256','bytes','rows')} for r in doc['families'] if isinstance(r,dict)]
    return out

def accounting():
    doc,ref=read_json(OBS)
    if doc.get('uid')!=1278 or doc.get('hostname','').split('.')[0]!='sonmi':raise ValueError('ACTUAL_PUBLISHER_UID_HOST_INVALID')
    actual=doc.get('sacct',{})
    if actual.get('returncode')!=0 or not actual.get('stdout','').strip():raise ValueError('ACTUAL_SACCT_FAILED_OR_EMPTY')
    fmt=next((a.split('=',1)[1] for a in actual['argv'] if a.startswith('--format=')),None)
    if fmt is None:raise ValueError('ACTUAL_SACCT_FORMAT_MISSING')
    columns=fmt.split(',');rows={}
    if not {'JobID','User','State'}.issubset(columns):raise ValueError('ACTUAL_FORMAT_INCOMPLETE')
    for line in actual['stdout'].splitlines():
        fields=line.strip().split('|')
        if fields and fields[-1]=='':fields.pop()
        if len(fields)!=len(columns):raise ValueError('ACTUAL_SACCT_ROW_WIDTH_DIFFER')
        row=dict(zip(columns,fields));rows[row['JobID']]=row
    age=time.time()-doc['time']
    return rows,{**ref,'time':doc['time'],'age_seconds':age,'fresh180s':-5<=age<=180,'uid':doc['uid'],
                 'hostname':doc['hostname'],'sacct_returncode':actual['returncode'],'sacct_argv':actual['argv'],'publisher':doc.get('publisher')}

def collect(entry):
    job=str(entry['job_id']);err=tail(ROOT/'logs'/(entry['name']+'_'+job+'.err'));stdout=tail(ROOT/'logs'/(entry['name']+'_'+job+'.out'))
    text=err['text']+'\n'+stdout['text'];locked=bool(re.search(r'database (?:is|table is) locked|SQLITE_BUSY|SQL_METADATA_RETRY',text))
    # __init__ alone is not proof: worker/archive construction may happen after
    # other workers started. Require the main Queue(args.queue) source line.
    startup_ctor=locked and bool(re.search(r'queue\s*=\s*Queue\(args\.queue',text))
    phase='NO_ERROR_OR_CLOSURE_IN_TAIL';science='UNKNOWN_NO_CURRENT_EXECUTION_EVIDENCE'
    if startup_ctor:phase='STARTUP_CONSTRUCTOR_LOCK';science='NOT_STARTED_MAIN_QUEUE_CONSTRUCTOR_BEFORE_WORKERS'
    elif locked and re.search(r'queue\.start\(|INSERT INTO sessions',text):phase='STARTUP_SESSION_LOCK'
    elif locked and re.search(r'queue\.claim\(|in claim',text):phase='RUNTIME_CLAIM_LOCK'
    elif locked and re.search(r'queue\.finish\(|in finish',text):phase='RUNTIME_FINISH_LOCK_SCI_MAY_BE_DURABLE'
    elif locked:phase='OTHER_SQLITE_LOCK'
    elif 'Traceback' in text:phase='OTHER_RUNTIME_ERROR'
    parent=ROOT/'runtime'/('task_'+str(entry['task_id']));paths=sorted(parent.glob('job_'+job+'_*')) if parent.is_dir() else []
    saved=[];errors=[];reconcile=[];complete_records=0;complete_molecules=0
    for root in paths:
        # Directory names/stat only; no sqlite contents are opened.
        lane_dir=root/'temporary_lanes';lane_names=sorted(p.name for p in lane_dir.glob('lane_*.sqlite')) if lane_dir.is_dir() else []
        names={'run.json','completion.json','runtime_error.json','export_completion.json','queue_error.json'}
        names.update(p.name for p in root.glob('worker*.json'))
        names.update(p.name for p in root.glob('queue*error*.json'))
        names.update(p.name for p in root.glob('runtime*error*.json'))
        capsules=[]
        for name in sorted(names):
            path=root/name
            if not path.is_file():continue
            try:cap=metadata(path);capsules.append(cap)
            except Exception as exc:capsules.append({'path':str(path),'name':name,'read_error':str(exc)})
        export=next((v for v in capsules if v['name']=='export_completion.json' and 'molecules' in v),None)
        completion=next((v for v in capsules if v['name']=='completion.json'),None)
        run=next((v for v in capsules if v['name']=='run.json'),None)
        if export:
            phase='SUCCESSFUL_PERMANENT_EXPORT_CLOSURE';n=number(export.get('molecules')) or 0;r=number(export.get('records')) or 0
            complete_molecules+=n;complete_records+=r
            science='COMPLETE_SCI_REPORTED_IN_PERMANENT_CLOSURE' if n else 'ZERO_NEW_COMPLETE_SCI_METADATA_CLOSURE'
        elif completion and (number(completion.get('worker_completed')) or 0)>0:science='SCI_PRODUCTION_CONFIRMED_BY_WORKER_COMPLETION'
        if run and startup_ctor:
            # Cannot claim zero SCI if a same-job run reached the runtime stage.
            science='RUN_CREATED_STARTUP_CLASSIFICATION_REQUIRES_REVIEW'
        runtime_errors=[v for v in capsules if v.get('error') or v.get('traceback') or v.get('runtime_error') or v.get('worker_errors')]
        if runtime_errors and not export and not startup_ctor:phase='RUNTIME_METADATA_OR_PIPELINE_ERROR'
        if lane_names and not export:reconcile.append({'run_root':str(root),'lane_db_names':lane_names,'reason':'UNEXPORTED_RUNTIME_LANES_PRESENT; completeSCI_not_inspected'})
        saved.append({'run_root':str(root),'lane_db_names':lane_names,'SCI_database_content_read':False,'small_json':capsules})
    frames=re.findall(r'File "[^"]*wp5_runner_v11.py", line \d+, in [^\r\n]+',text)
    return {'job_id':job,'old_job_id':entry.get('old_job_id'),'task_id':str(entry['task_id']),'mode':entry['mode'],'node':entry['node'],
            'classification':phase,'science_started_evidence':science,'locked':locked,'stack_frames':frames,
            'stderr':err,'stdout':stdout,'runtime_roots':saved,'reconcile_candidates':reconcile,
            'permanent_closure_molecules':complete_molecules,'permanent_closure_records':complete_records,'collection_errors':errors}

def execute(args):
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='sonmi':raise ValueError('ROOT_LOGIN_METADATA_COLLECTOR_REQUIRES_ZIXIAO_SONMI')
    began=time.time();submitted,ref=read_json(SUB);entries=submitted['main']+submitted['cleanup']
    if len(submitted['main'])!=69 or len(submitted['cleanup'])!=4 or len({str(e['job_id']) for e in entries})!=73:raise ValueError('EXACT69_MAIN_PLUS4_CLEANUP_SCOPE_REQUIRED')
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.workers,12)) as pool:cases=list(pool.map(collect,entries))
    actual,observation=accounting() # Freshness taken AFTER I/O, not before it.
    for case in cases:
        case['actual']=actual.get(case['job_id'])
        if case['actual'] is None or case['actual']['User']!='zixiao':raise ValueError('EXACT_JOB_USER_NOT_IN_FRESH_ACTUAL_ACCOUNTING:'+case['job_id'])
    report={'schema':'WP5_STARTUP_REPLACEMENT_FAILURE_REVIEW_V1','status':'READ_ONLY_SMALL_METADATA_LOG_TAIL_REVIEW',
        'created_epoch':time.time(),'created_local_iso':datetime.datetime.now().astimezone().isoformat(),'source_sha256':sha(Path(__file__).read_bytes()),
        'scope_jobs':73,'source_submission':ref,'observation':observation,
        'actual_states':dict(Counter(c['actual']['State'].split()[0] for c in cases)),
        'classifications':dict(Counter(c['classification'] for c in cases)),
        'science_evidence':dict(Counter(c['science_started_evidence'] for c in cases)),
        'permanent_closure_molecules':sum(c['permanent_closure_molecules'] for c in cases),'permanent_closure_records':sum(c['permanent_closure_records'] for c in cases),
        'reconcile_candidates':[r for c in cases for r in c['reconcile_candidates']],
        'cases':cases,'elapsed_seconds':time.time()-began,'queue_written':False,'QM_run':False,'original_LMDB_opened':False,
        'SCI_or_RAW_database_content_read':False,'submitted':False,'historical_modified':False,
        'limitations':['Only log tail32KiB and <=256KiB receipt JSON; larger files explicitly skipped',
            'Lane filenames do not prove completeSCI; later terminal reconciliation must verify actual wire/receipts',
            'New job constructor failure does not invalidate old job SCI',
            'Active/missing closure is not evidence of zeroQM; completed scheduler status is not scientific closure']}
    target=Path(args.out)
    if not target.resolve().is_relative_to((ROOT/'reports').resolve()):raise ValueError('NEW_REPORT_PATH_ONLY')
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    print(json.dumps({k:report[k] for k in ('actual_states','classifications','science_evidence','permanent_closure_molecules','permanent_closure_records','reconcile_candidates','elapsed_seconds')},ensure_ascii=False));return 0

def check():
    import ast
    ast.parse(Path(__file__).read_text())
    assert len(worker_rows([{'completed':2}]))==1
    assert len(worker_rows({'reports':[{'completed':2}]}))==1
    # A worker __init__ cannot be misrepresented as zero science.
    assert re.search(r'queue\s*=\s*Queue\(args\.queue','queue=Queue(args.queue,deadline=1)')
    assert not re.search(r'queue\s*=\s*Queue\(args\.queue','queue=Queue(options["queue"])')
    print('SMALL_METADATA_COLLECTOR_AST_SCOPE_FIXTURE_PASS_NO_DATABASE_NO_QM')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--workers',type=int,default=8)
    p.add_argument('--out',type=Path,default=ROOT/'reports/startup_replacement_failure_review_v1.json');a=p.parse_args()
    if a.check:check()
    else:raise SystemExit(execute(a))
