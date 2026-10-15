"""Read-only accounting from Root's real sonmi publisher; no compute networking.
Exact actual rows are projected to the requested sacct format. Unknown, stale,
unregistered and failed queries never become empty successful accounting results.
"""
from __future__ import annotations
import argparse,getpass,hashlib,json,os,re,shlex,socket,subprocess,time,uuid
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
SNAPSHOT=ROOT/'reports/observation_latest.json'
PUBLISHER_SHA='fa03acc9dbb5ca3cc4ffe1b98f038a99d34734bbb313d9ab13408e528ae2cc7c'
TERMINAL={'COMPLETED','FAILED','CANCELLED','NODE_FAIL','OUT_OF_MEMORY','TIMEOUT','BOOT_FAIL','DEADLINE','PREEMPTED'}

def sha(data):return hashlib.sha256(data).hexdigest()

def requested(args):
    args=[str(x) for x in args]
    if args and Path(args[0]).name=='sacct':args=args[1:]
    jobs=None;fields=None;i=0
    while i<len(args):
        arg=args[i]
        if arg in ('-X','-n','-P'):i+=1;continue
        if arg in ('-j','--jobs','--format'):
            if i+1>=len(args):raise ValueError('ACCOUNTING_MISSING_OPTION_VALUE')
            if arg=='--format':fields=args[i+1].split(',')
            else:jobs=args[i+1].split(',')
            i+=2;continue
        if arg.startswith('--format='):fields=arg.split('=',1)[1].split(',');i+=1;continue
        if arg.startswith('--jobs='):jobs=arg.split('=',1)[1].split(',');i+=1;continue
        raise ValueError('ACCOUNTING_UNSUPPORTED_READ_QUERY_OPTION:'+arg)
    if not jobs or len(jobs)!=len(set(jobs)) or any(not re.fullmatch(r'\d+(?:_\d+)?',job) for job in jobs):raise ValueError('ACCOUNTING_EXACT_UNIQUE_JOB_IDS_REQUIRED')
    fields=fields or ['JobID','User','State']
    if not fields or any(not re.fullmatch(r'[A-Za-z]+',field) for field in fields):raise ValueError('ACCOUNTING_INVALID_FORMAT')
    return ['sacct',*args],jobs,fields

def source_format(argv):
    for i,arg in enumerate(argv):
        if arg.startswith('--format='):return arg.split('=',1)[1].split(',')
        if arg=='--format' and i+1<len(argv):return argv[i+1].split(',')
    raise ValueError('PUBLISHED_SACCT_FORMAT_MISSING')

def project(document,data,jobs,fields,now,started_epoch,max_age):
    if document.get('uid')!=1278 or document.get('hostname','').split('.')[0]!='sonmi':raise ValueError('WRONG_PUBLISHED_UID_OR_HOST')
    stamp=document.get('time')
    if not isinstance(stamp,(int,float)):raise ValueError('PUBLISHED_TIME_MISSING')
    age=now-stamp
    if age < -5 or age>max_age:raise ValueError('PUBLISHED_ACCOUNTING_STALE_OR_FUTURE:'+str(age))
    publisher=document.get('publisher',{})
    if publisher.get('sha256')!=PUBLISHER_SHA:raise ValueError('WRONG_ACTUAL_PUBLISHER_SOURCE_SHA')
    publisher_path=Path(publisher.get('script',''))
    if not publisher_path.resolve().is_relative_to(ROOT.resolve()) or sha(publisher_path.read_bytes())!=PUBLISHER_SHA:raise ValueError('PUBLISHER_SOURCE_BINDING_DIFFERS')
    registered={}
    for entry in document.get('registered',[]):
        job=str(entry['job_id'])
        if job in registered:raise ValueError('PUBLISHED_REGISTERED_JOB_DUPLICATE:'+job)
        registered[job]=entry
    for job in jobs:
        if job not in registered:raise ValueError('REQUESTED_JOB_NOT_REGISTERED:'+job)
        entry=registered[job];rp=Path(entry['receipt'])
        if not rp.resolve().is_relative_to(ROOT.resolve()) or rp.stat().st_uid!=1278:raise ValueError('REGISTERED_RECEIPT_SCOPE_OR_UID:'+job)
        raw=rp.read_bytes()
        if sha(raw)!=entry.get('receipt_sha256'):raise ValueError('REGISTERED_RECEIPT_SHA_DIFFERS:'+job)
        receipt=json.loads(raw)
        if str(receipt['job_id'])!=job or receipt['node']!=entry['node']:raise ValueError('REGISTERED_ID_NODE_BINDING:'+job)
    actual=document.get('sacct',{})
    if actual.get('returncode')!=0 or not actual.get('stdout','').strip():raise ValueError('REAL_SACCT_FAILED_OR_EMPTY:'+json.dumps(actual))
    columns=source_format(actual.get('argv',[]))
    if not {'JobID','User','State'}.issubset(columns) or not set(fields).issubset(columns):raise ValueError('REQUESTED_FORMAT_NOT_IN_REAL_SACCT')
    rows={}
    for line in actual['stdout'].splitlines():
        tokens=[part.strip() for part in line.split('|')]
        if tokens and tokens[-1]=='':tokens=tokens[:-1]
        if len(tokens)!=len(columns):raise ValueError('REAL_SACCT_ROW_WIDTH_DIFFERS:'+line)
        record=dict(zip(columns,tokens));job=record['JobID']
        if job not in jobs:continue
        if job in rows:raise ValueError('REAL_SACCT_JOB_DUPLICATE:'+job)
        if record['User']!='zixiao' or not record['State']:raise ValueError('REAL_SACCT_REQUESTED_USER_OR_STATE_INVALID:'+job)
        rows[job]=record
    if set(rows)!=set(jobs):raise ValueError('REQUESTED_ID_MISSING_FROM_REAL_SACCT:'+','.join(sorted(set(jobs)-set(rows))))
    # Terminal observations are stable and can use a <=180 s Root snapshot.
    # For any active row, wait for a post-request publication so afterany cleanup
    # sees a fresh ended task while other genuinely active jobs stay RUNNING.
    if any(row['State'].split()[0] not in TERMINAL for row in rows.values()) and stamp<started_epoch:
        raise ValueError('WAITING_FOR_POST_REQUEST_ACTIVE_JOB_OBSERVATION')
    stdout=''.join('|'.join(rows[job][field] for field in fields)+'|\n' for job in jobs)
    provenance={'snapshot_path':str(SNAPSHOT),'snapshot_sha256':sha(data),'snapshot_time':stamp,'snapshot_age_seconds':age,
       'publisher':publisher,'source_sacct_argv':actual['argv'],'source_sacct_returncode':actual['returncode'],
       'source_sacct_stdout':actual['stdout'],'source_sacct_stderr':actual.get('stderr',''),
       'registered_requested_jobs':[registered[job] for job in jobs]}
    return stdout,actual.get('stderr',''),provenance

def run_sacct(args,timeout=60,evidence_path=None,wait_seconds=120,max_age_seconds=180):
    """CompletedProcess API. timeout is accepted for old callers; publisher wait <=120s."""
    if os.getuid()!=1278 or getpass.getuser()!='zixiao':raise ValueError('SAME_ACTUAL_ZIXIAO_UID1278_REQUIRED')
    argv,jobs,fields=requested(args);began=time.monotonic();started_epoch=time.time();deadline=began+min(float(wait_seconds),120.)
    rc=75;stdout='';stderr='PUBLISHED_ACCOUNTING_NOT_YET_AVAILABLE';provenance={};attempts=0
    while True:
        attempts+=1
        try:
            if SNAPSHOT.stat().st_uid!=1278:raise ValueError('SNAPSHOT_OWNER_UID_MISMATCH')
            data=SNAPSHOT.read_bytes();document=json.loads(data)
            stdout,stderr,provenance=project(document,data,jobs,fields,time.time(),started_epoch,float(max_age_seconds));rc=0;break
        except (OSError,ValueError,KeyError,TypeError) as exc:
            stderr='PUBLISHED_ACCOUNTING_UNAVAILABLE:'+type(exc).__name__+':'+str(exc)
        remaining=deadline-time.monotonic()
        if remaining<=0:break
        time.sleep(min(10.,remaining))
    evidence={'schema':'WP5_ACCOUNTING_SNAPSHOT_QUERY_V1','request_epoch':started_epoch,'seconds':time.monotonic()-began,
       'job_id':os.environ.get('SLURM_JOB_ID'),'node':socket.gethostname().split('.')[0],'user':getpass.getuser(),'uid':os.getuid(),
       'transport':'READONLY_ACTUAL_ROOT_LOGIN_SNAPSHOT','requested_argv':argv,'returncode':rc,'stdout':stdout,'stderr':stderr,
       'wait_seconds':min(float(wait_seconds),120.),'max_age_seconds':float(max_age_seconds),'read_attempts':attempts,
       'legacy_timeout_argument_seconds':timeout,'provenance':provenance,'direct_network':False,'QM_started':False}
    target=Path(evidence_path) if evidence_path else ROOT/'gates/accounting'/('job_'+os.environ.get('SLURM_JOB_ID','login'))/(str(time.time_ns())+'_'+uuid.uuid4().hex[:8]+'.json')
    if not target.resolve().is_relative_to(ROOT.resolve()):raise ValueError('Accounting receipts only in this WP5 root')
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x') as f:
        json.dump(evidence,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    result=subprocess.CompletedProcess(argv,rc,stdout,stderr);result.evidence=evidence;result.evidence_path=str(target)
    return result

def check():
    command,jobs,fields=requested(['sacct','-X','-n','-P','-j','4513901,4513904','--format=JobID,User,State'])
    assert jobs==['4513901','4513904'] and fields==['JobID','User','State'] and command[0]=='sacct'
    assert source_format(['sacct','--format=JobID,JobName,User,State'])==['JobID','JobName','User','State']
    try:requested(['-j','4513901,4513901']);raise AssertionError('duplicate query accepted')
    except ValueError:pass
    print('ACCOUNTING_SNAPSHOT_QUERY_FIXTURES_PASS_NO_NETWORK_NO_QM')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--job-id');p.add_argument('--wait-seconds',type=float,default=120);a=p.parse_args()
    if a.check:check()
    elif a.job_id:
        r=run_sacct(['-X','-n','-P','-j',a.job_id,'--format=JobID,User,State'],wait_seconds=a.wait_seconds)
        print(json.dumps({'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'evidence_path':r.evidence_path}));raise SystemExit(r.returncode)
