"""Main metadata-only, non-expiring D3 storage admission and observation."""
import argparse,base64,contextlib,fcntl,hashlib,json,os,pathlib,re,shlex,socket,subprocess,sys,time

R=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
LEDGER=R/'control/root_current_all_future_ledger_v1.json'
LOCK=LEDGER.with_suffix('.lock')
TERMINAL={'COMPLETED','CANCELLED','FAILED','TIMEOUT','NODE_FAIL','PREEMPTED','OUT_OF_MEMORY','BOOT_FAIL','DEADLINE','REVOKED','SPECIAL_EXIT'}

def run(argv):
    value=subprocess.run(argv,capture_output=True,text=True)
    if value.returncode:raise RuntimeError((argv,value.returncode,value.stderr))
    return value.stdout

def read(value):
    path=pathlib.Path(value['path'] if isinstance(value,dict) else value)
    data=path.read_bytes()
    if isinstance(value,dict) and (len(data)!=value['bytes']or hashlib.sha256(data).hexdigest()!=value['sha256']):raise ValueError('PINNED_METADATA_CHANGED')
    return json.loads(data)

def save(path,value,pin=False):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    data=(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
    temporary=path.with_name(path.name+'.partial_'+str(os.getpid()))
    with temporary.open('wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)
    if pin:return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

def policy_reference(plan):
    if not isinstance(plan,dict):plan=read(plan)
    if 'quota_policy_reference' in plan:return plan['quota_policy_reference']
    for key in ('manifest','manifest_reference'):
        if key in plan:
            value=plan[key]
            return policy_reference(read(value) if isinstance(value,str) or 'path' in value else value)
    raise ValueError('QUOTA_POLICY_REFERENCE_REQUIRED')

def main_only():
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='sonmi':
        raise ValueError('MAIN_SONMI_UID1278_METADATA_ONLY')

@contextlib.contextmanager
def locked():
    with LOCK.open('a+') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(stream,fcntl.LOCK_UN)

def quota():
    started=time.time();argv=['quota','-v','-u','zixiao'];raw=run(argv);finished=time.time()
    if not re.search(r'Disk quotas for user zixiao\s+\(uid 1278\):',raw):raise ValueError('REAL_QUOTA_UID_REQUIRED')
    rows=[];lines=raw.splitlines()
    for index,line in enumerate(lines):
        parts=line.split()
        if not parts or parts[0]!='/dev/sda1':continue
        if len(parts)==1 and index+1<len(lines):parts+=lines[index+1].split()
        fields=[item.rstrip('*') for item in parts[1:4]]
        if len(fields)!=3 or not all(item.isdecimal() for item in fields):raise ValueError('REAL_QUOTA_BLOCKS_REQUIRED')
        used,soft,hard=map(int,fields);limits=[item for item in (soft,hard) if item>0]
        if not limits:raise ValueError('FINITE_REAL_ACCOUNT_QUOTA_REQUIRED')
        rows.append((used*1024,min(limits)*1024))
    if len(rows)!=1:raise ValueError('EXACT_DEV_SDA1_QUOTA_REQUIRED')
    used,limit=rows[0]
    return dict(free_bytes=limit-used,used_bytes=used,quota_limit_bytes=limit,
        observed_unix_seconds=finished,quota_query_started_unix_seconds=started,
        raw_quota=dict(argv=argv,stdout=raw,stderr='',returncode=0),uid=os.getuid(),
        node=socket.gethostname(),endpoint='202.38.247.57:22',filesystem='/dev/sda1')

def state(job):
    try:
        rows=[line.split('|') for line in run(['sacct','-X','-n','-P','-j',str(job),'--format=JobIDRaw,State,ExitCode']).splitlines()]
        rows=[row for row in rows if row[0]==str(job)]
        return rows[0][1].split()[0].rstrip('+') if len(rows)==1 else 'UNKNOWN'
    except Exception:return 'UNKNOWN'

def template_from_job(job):
    text=run(['scontrol','show','job','-o',str(job)])
    match=re.search(r'(?:^|\s)Command=(.*?)(?=\s[A-Za-z][A-Za-z0-9_]*=|$)',text)
    command=match.group(1) if match else ''
    candidates=[command]
    tokens=shlex.split(command)
    if tokens and pathlib.Path(tokens[0]).is_absolute():
        script=pathlib.Path(tokens[0])
        if script.is_file() and script.stat().st_size<=1<<20:candidates.append(script.read_text())
    for candidate in candidates:
        match=re.search(r'--template(?:=|\s+)([^\s;]+)',candidate)
        if match:
            path=pathlib.Path(match.group(1).strip('"\''))
            if not path.is_absolute() or '$' in str(path):continue
            value=read(path);cap=value.get('producer_plan',value).get('output_cap_bytes')
            if type(cap) is int and cap>0:return cap,dict(path=str(path),bytes=path.stat().st_size)
    raise ValueError('OWN_OTHER_JOB_FUTURE_UNKNOWN')

def refresh(ledger,policy,own_job):
    entries=ledger['entries']
    for peer in policy.get('peer_forecasts',[]):
        key='peer_'+str(peer['job_id'])
        if key not in entries:
            entries[key]=dict(job_id=str(peer['job_id']),future_reserved_bytes=peer['output_cap_bytes'],
                status='ACTIVE_OR_UNKNOWN',template_reference=peer['template_reference'])
        entries[key]['forecast_bytes']=peer['output_cap_bytes']
    for entry in entries.values():
        job=entry.get('job_id')
        if job is None or str(job)==str(own_job):continue
        actual=state(job);entry['last_actual_scheduler_state']=actual
        if type(entry.get('future_reserved_bytes')) is int and entry['future_reserved_bytes']>0:
            entry.setdefault('forecast_bytes',entry['future_reserved_bytes'])
        if actual in TERMINAL:entry.update(future_reserved_bytes=0,status='ACTUAL_TERMINAL_FUTURE_RELEASED_USED_BYTES_NOT_REFUNDED',confirmed_terminal_state=actual)
        elif actual=='UNKNOWN' and entry.get('confirmed_terminal_state')in TERMINAL:entry.update(future_reserved_bytes=0,status='CONFIRMED_TERMINAL_RETAINED_NO_NEW_RUNNING_EVIDENCE')
        elif type(entry.get('forecast_bytes')) is int:
            entry.update(future_reserved_bytes=entry['forecast_bytes'],status='ACTIVE_OR_UNKNOWN')
        elif entry.get('future_reserved_bytes') is None:
            try:
                cap,reference=template_from_job(job)
                entry.update(future_reserved_bytes=cap,status='CONSERVATIVE_KNOWN_TEMPLATE_FUTURE',template_reference=reference)
            except Exception:pass
    active=[line.split('|')[0] for line in run(['squeue','-h','-u','zixiao','-o','%i|%j']).splitlines() if line.strip()]
    registered={str(value.get('job_id')) for value in entries.values() if value.get('job_id') is not None}
    for job in active:
        if job==str(own_job) or job in registered:continue
        try:
            cap,reference=template_from_job(job)
            entries['observed_job_'+job]=dict(job_id=job,future_reserved_bytes=cap,forecast_bytes=cap,status='CONSERVATIVE_KNOWN_TEMPLATE_FUTURE',template_reference=reference)
        except Exception as error:
            entries['observed_job_'+job]=dict(job_id=job,future_reserved_bytes=None,status='UNKNOWN_FUTURE_WAIT',observation_error=repr(error))
    unknown=[key for key,value in entries.items() if type(value.get('future_reserved_bytes')) is not int or value['future_reserved_bytes']<0]
    ledger['known_future_reserved_bytes']=sum(value['future_reserved_bytes'] for value in entries.values() if type(value.get('future_reserved_bytes')) is int and value['future_reserved_bytes']>=0)
    ledger['unknown_future_entries']=unknown
    ledger['totals_derived_live_from_entries']=True
    ledger['entries_observed_unix_seconds']=time.time()
    ledger['total_future_reserved_bytes']=None if unknown else ledger['known_future_reserved_bytes']
    save(LEDGER,ledger)
    if unknown:raise ValueError('UNKNOWN_FUTURES_NOT_COUNTED_AS_ZERO:'+repr(unknown))
    return ledger['total_future_reserved_bytes']

def snapshot(reference,job=None):
    main_only();policy=read(reference)
    with locked():
        ledger=read(LEDGER);own=ledger['entries'][policy['scope_entry_key']]
        job=str(job or own.get('job_id'))
        if own.get('job_id') is None or str(own['job_id'])!=job or own['future_reserved_bytes']!=policy['own_forecast_bytes']:
            raise ValueError('ACTUAL_OWN_D3_ADMISSION_REQUIRED')
        total=refresh(ledger,policy,job);value=quota()
    return dict(value,total_future_reserved_bytes=total,own_forecast_bytes=policy['own_forecast_bytes'],
        quota_policy_reference=reference,own_allocated_credit_applied=False,credit_not_applied=True)

def admit(manifest_dict,job_id,node,output_root,forecast=300_000_000_000):
    main_only();reference=policy_reference(manifest_dict);policy=read(reference);job_id=str(job_id)
    if forecast!=policy['own_forecast_bytes'] or forecast!=300_000_000_000 or policy['account_floor_bytes']!=100_000_000_000:
        raise ValueError('ORIGINAL_FORECAST_AND_ACCOUNT_FLOOR_REQUIRED')
    directory=pathlib.Path(policy['execution_control_directory'])
    while True:
        try:
            running=run(['squeue','-h','-j',job_id,'-o','%i|%T|%N|%j']).strip().split('|')
            if running!=[job_id,'RUNNING',node,policy['job_name']]:raise ValueError('ACTUAL_RUNNING_OWN_NODE_AND_JOB_NAME_REQUIRED')
            with locked():
                ledger=read(LEDGER);own=ledger['entries'][policy['scope_entry_key']]
                if own.get('job_id') is not None and str(own['job_id'])!=job_id and own['future_reserved_bytes']:
                    raise ValueError('OTHER_ACTIVE_JOB_OWNS_SCOPE')
                total=refresh(ledger,policy,job_id);value=quota()
                total=total-own['future_reserved_bytes']+forecast
                if value['free_bytes']-total<policy['account_floor_bytes']:raise ValueError('WAITING_FOR_REAL_ACCOUNT_QUOTA_MINUS_ALL_FUTURES')
                own.update(job_id=job_id,future_reserved_bytes=forecast,status='ACTUAL_RUNNING_STORAGE_ADMITTED',
                    forecast_bytes=forecast,node=node,output_root=str(output_root),quota_policy_reference=reference)
                ledger['total_future_reserved_bytes']=ledger['known_future_reserved_bytes']=total;save(LEDGER,ledger)
                value.update(total_future_reserved_bytes=total,own_forecast_bytes=forecast,own_allocated_credit_applied=False,credit_not_applied=True)
                receipt=dict(status='ACTUAL_RUNNING_D3_STORAGE_ADMITTED',job_id=job_id,node=node,output_root=str(output_root),
                    quota_policy_reference=reference,quota_snapshot=value,forecast_is_not_output_hard_cap=True,no_expiry=True)
                receipt['user_resource_policy_reference']=policy['user_resource_policy_reference']
                admission=save(directory/('storage_admission_'+job_id+'.json'),receipt,pin=True)
                return dict(admission_reference=admission,admission_ref=admission,quota_snapshot=value,total_future_reserved_bytes=total)
        except Exception as error:
            save(directory/('storage_wait_'+job_id+'.json'),dict(status='WAITING_NO_SCIENCE_TERMINATION',job_id=job_id,
                observed_unix_seconds=time.time(),reason=repr(error)))
            time.sleep(60)

def retire(reference,job_id):
    main_only();policy=read(reference);job_id=str(job_id)
    if state(job_id)not in TERMINAL:return False
    with locked():
        ledger=read(LEDGER);own=ledger['entries'][policy['scope_entry_key']]
        if str(own.get('job_id'))!=job_id:return False
        own.update(future_reserved_bytes=0,status='ACTUAL_TERMINAL_D3_FUTURE_RETIRED_USED_BYTES_NOT_REFUNDED')
        refresh(ledger,policy,job_id)
    return True


def observe(plan,own_allocated_sample):
    """Budget retains its census locally and applies inode credit exactly once."""
    reference=policy_reference(plan);job=str(plan.get('job_id') or os.environ.get('SLURM_JOB_ID',''))
    encoded=base64.urlsafe_b64encode(json.dumps(reference).encode()).decode()
    command='PYTHONPATH='+shlex.quote(str(R/'repository'))+' '+shlex.quote(sys.executable)+' -B '+shlex.quote(str(pathlib.Path(__file__).resolve()))+' --observe --policy '+shlex.quote(encoded)
    if job:command+=' --job-id '+shlex.quote(job)
    return json.loads(run(['ssh','-n','-o','BatchMode=yes','sonmi',command]))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--observe',action='store_true',required=True)
    parser.add_argument('--policy',required=True);parser.add_argument('--job-id')
    args=parser.parse_args();print(json.dumps(snapshot(json.loads(base64.urlsafe_b64decode(args.policy)),args.job_id),sort_keys=True))
