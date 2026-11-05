"""Main metadata RPC for a separate Lustre D3 forecast; no finite service."""
import argparse,base64,contextlib,fcntl,hashlib,json,os,pathlib,re,shlex,socket,subprocess,sys,time

R=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
MAIN_LEDGER=R/'control/root_current_all_future_ledger_v1.json'
LEDGER=R/'control/root_lustre_current_all_future_ledger_v1.json'
LOCK=LEDGER.with_suffix('.lock')
OUTPUT=pathlib.Path('/lfshome/zixiao/data_v1_20261025/D3_pilot_provisional_lustre_v1')
TERMINAL={'COMPLETED','CANCELLED','FAILED','TIMEOUT','NODE_FAIL','PREEMPTED','OUT_OF_MEMORY','BOOT_FAIL','DEADLINE','REVOKED','SPECIAL_EXIT'}

def run(argv):
    value=subprocess.run(argv,capture_output=True,text=True)
    if value.returncode:raise RuntimeError((argv,value.returncode,value.stderr))
    return value.stdout

def read(reference):
    path=pathlib.Path(reference['path'] if isinstance(reference,dict) else reference)
    if not path.is_absolute() or '..' in path.parts or path.is_symlink():raise ValueError('LITERAL_ABSOLUTE_METADATA_PATH_REQUIRED')
    before=path.stat()
    if before.st_uid!=1278 or before.st_size>16<<20:raise ValueError('OWN_SMALL_METADATA_REQUIRED')
    data=path.read_bytes();after=path.stat()
    if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('METADATA_CHANGED')
    if isinstance(reference,dict) and (len(data)!=reference['bytes'] or hashlib.sha256(data).hexdigest()!=reference['sha256']):
        raise ValueError('METADATA_PIN_BYTES_OR_SHA_CHANGED')
    return json.loads(data)

def save(path,value,pin=False):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    data=(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
    temporary=path.with_name(path.name+'.partial_'+str(os.getpid()))
    with temporary.open('wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)
    if pin:return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

def main_only():
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='sonmi':raise ValueError('MAIN_SONMI_UID1278_METADATA_ONLY')

@contextlib.contextmanager
def locked(ledger=LEDGER):
    with pathlib.Path(ledger).with_suffix('.lock').open('a+') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(stream,fcntl.LOCK_UN)

def state(job):
    try:
        rows=[line.split('|') for line in run(['sacct','-X','-n','-P','-j',str(job),'--format=JobIDRaw,State,ExitCode']).splitlines()]
        rows=[row for row in rows if row[0]==str(job)]
        return rows[0][1].split()[0].rstrip('+') if len(rows)==1 else 'UNKNOWN'
    except Exception:return 'UNKNOWN'

def policy_reference(plan):
    if not isinstance(plan,dict):plan=read(plan)
    if 'quota_policy_reference' in plan:return plan['quota_policy_reference']
    for key in ('manifest','manifest_reference'):
        if key in plan:
            value=plan[key]
            return policy_reference(read(value) if isinstance(value,str) or 'path' in value else value)
    raise ValueError('QUOTA_POLICY_REFERENCE_REQUIRED')

def policy(reference):
    path=pathlib.Path(reference['path'] if isinstance(reference,dict) else reference)
    if R/'control' not in path.parents:raise ValueError('MAIN_CONTROL_POLICY_REQUIRED')
    value=read(reference);directory=pathlib.Path(value['execution_control_directory'])
    if not directory.is_absolute() or '..' in directory.parts or R/'control' not in directory.parents:raise ValueError('MAIN_CONTROL_METADATA_DIRECTORY_REQUIRED')
    if value['quota_endpoint']!='202.38.247.57:22' or value['account_floor_bytes']!=100_000_000_000 or value['own_forecast_bytes']!=750_000_000_000:
        raise ValueError('EXACT_LUSTRE_FORECAST_AND_ACCOUNT_FLOOR_REQUIRED')
    return value

def quota():
    started=time.time();argv=['lfs','quota','-u','zixiao','/lfshome'];raw=run(argv);finished=time.time();rows=[];lines=raw.splitlines()
    for index,line in enumerate(lines):
        parts=line.split()
        if not parts or parts[0]!='/lfshome':continue
        if len(parts)==1 and index+1<len(lines):parts+=lines[index+1].split()
        fields=[item.rstrip('*') for item in parts[1:4]]
        if len(fields)!=3 or not all(item.isdecimal() for item in fields):raise ValueError('REAL_LUSTRE_KIB_FIELDS_REQUIRED')
        used,soft,hard=map(int,fields);limits=[item for item in (soft,hard) if item>0]
        if not limits:raise ValueError('FINITE_REAL_LUSTRE_ALLOWANCE_REQUIRED')
        rows.append((used*1024,min(limits)*1024))
    if len(rows)!=1:raise ValueError('EXACT_LFSHOME_QUOTA_ROW_REQUIRED')
    used,limit=rows[0]
    return dict(free_bytes=limit-used,used_bytes=used,limit_bytes=limit,quota_limit_bytes=limit,
        observed_unix_seconds=finished,quota_query_started_unix_seconds=started,uid=os.getuid(),node=socket.gethostname(),
        endpoint='202.38.247.57:22',filesystem='/lfshome',storage_domain='LUSTRE',
        raw_quota=dict(argv=argv,stdout=raw,stderr='',returncode=0))

def totals(ledger):
    entries=ledger['entries'];unknown=[key for key,value in entries.items() if type(value.get('future_reserved_bytes')) is not int or value['future_reserved_bytes']<0]
    ledger['known_future_reserved_bytes']=sum(value['future_reserved_bytes'] for value in entries.values() if type(value.get('future_reserved_bytes')) is int and value['future_reserved_bytes']>=0)
    ledger['unknown_future_entries']=unknown
    ledger['total_future_reserved_bytes']=None if unknown else ledger['known_future_reserved_bytes']
    return ledger['total_future_reserved_bytes']

def main_entry(value,job,output,status='LUSTRE_OUTPUT_MAIN_METADATA_COVERED_BY_EXISTING_LEGACY'):
    with locked(MAIN_LEDGER):
        ledger=read(MAIN_LEDGER);entries=ledger['entries'];old=entries.get(value['scope_entry_key'],{})
        if old.get('job_id') is not None and str(old['job_id'])!=job and (state(old['job_id']) not in TERMINAL or str(old['job_id']) in current_jobs()):raise ValueError('OTHER_ACTUAL_JOB_OWNS_MAIN_SCOPE')
        entries[value['scope_entry_key']]=dict(old,job_id=job,future_reserved_bytes=0,forecast_bytes=0,status=status,
            output_root=str(output),storage_domain='LUSTRE_MAIN_METADATA_ONLY')
        totals(ledger);save(MAIN_LEDGER,ledger)
        return ledger

def describe(value):
    view=value.get('producer_plan',value)
    if not isinstance(view,dict):return None
    roots=[view[key] for key in ('output_directory','output_root') if isinstance(view.get(key),str)]
    if not roots:return None
    cap=view.get('output_cap_bytes',view.get('own_forecast_bytes',view.get('forecast_bytes')))
    if any(pathlib.Path('/lfshome')==pathlib.Path(root) or pathlib.Path('/lfshome') in pathlib.Path(root).parents for root in roots):
        return ('LUSTRE',cap) if type(cap) is int and cap>0 else None
    if all(pathlib.Path('/share') in pathlib.Path(root).parents for root in roots):return 'MAIN',0
    return None

def writer(job,main_ledger):
    for entry in main_ledger['entries'].values():
        if str(entry.get('job_id'))!=job:continue
        result=describe(entry)
        if result:return result,dict(source='MAIN_LEDGER_ENTRY',job_id=job)
        for key in ('template_reference','plan_reference'):
            if entry.get(key):
                try:
                    result=describe(read(entry[key]))
                    if result:return result,entry[key]
                except Exception:pass
    text=run(['scontrol','show','job','-o',job]);match=re.search(r'(?:^|\s)Command=(.*?)(?=\s[A-Za-z][A-Za-z0-9_]*=|$)',text)
    command=match.group(1) if match else '';candidates=[command];tokens=shlex.split(command)
    if tokens and pathlib.Path(tokens[0]).is_absolute():
        path=pathlib.Path(tokens[0])
        if path.is_file() and path.stat().st_size<=1<<20:candidates.append(path.read_text())
    for candidate in candidates:
        for match in re.finditer(r'--(?:template|plan)(?:=|\s+)([^\s;]+)',candidate):
            path=pathlib.Path(match.group(1).strip('"\''))
            if not path.is_absolute() or '$' in str(path):continue
            result=describe(read(path))
            if result:return result,dict(path=str(path),bytes=path.stat().st_size)
    raise ValueError('OTHER_CURRENT_WRITER_STORAGE_OR_FORECAST_UNKNOWN')

def current_jobs():
    return {line.split('|')[0]:line.split('|')[1] for line in run(['squeue','-h','-u','zixiao','-o','%i|%T']).splitlines() if line.strip()}

def refresh(ledger,own_job,main_ledger):
    active=current_jobs();entries=ledger['entries'];registered={str(entry.get('job_id')) for entry in entries.values() if entry.get('job_id') is not None}
    for job in active:
        if job!=own_job and job not in registered:entries['observed_job_'+job]=dict(job_id=job,future_reserved_bytes=None,status='UNKNOWN_WRITER_WAIT')
    for entry in entries.values():
        job=str(entry['job_id']) if entry.get('job_id') is not None else None
        if job is None or job==own_job:continue
        actual=state(job);entry['last_actual_scheduler_state']=actual
        if actual in TERMINAL and job not in active:
            entry.update(future_reserved_bytes=0,status='ACTUAL_TERMINAL_FUTURE_RELEASED_USED_BYTES_NOT_REFUNDED');continue
        if entry.get('storage_domain')=='LUSTRE' and type(entry.get('forecast_bytes')) is int:
            entry.update(future_reserved_bytes=entry['forecast_bytes'],status='ACTIVE_OR_UNKNOWN');continue
        try:
            (domain,cap),reference=writer(job,main_ledger)
            entry.update(storage_domain=domain,future_reserved_bytes=cap,forecast_bytes=cap,writer_reference=reference,
                status='KNOWN_MAIN_NOT_A_LUSTRE_FUTURE' if domain=='MAIN' else 'ACTIVE_OR_UNKNOWN_LUSTRE_FORECAST')
        except Exception as error:entry.update(future_reserved_bytes=None,status='UNKNOWN_WRITER_WAIT',observation_error=repr(error))
    total=totals(ledger);save(LEDGER,ledger)
    if total is None:raise ValueError('UNKNOWN_LUSTRE_WRITERS_NOT_COUNTED_AS_ZERO:'+repr(ledger['unknown_future_entries']))
    return total

def snapshot(reference,job=None):
    main_only();value=policy(reference)
    with locked(MAIN_LEDGER):main_ledger=read(MAIN_LEDGER)
    with locked():
        ledger=read(LEDGER);own=ledger['entries'][value['scope_entry_key']];job=str(job or own.get('job_id'))
        if str(own.get('job_id'))!=job or own.get('job_id') is None or own['future_reserved_bytes']!=value['own_forecast_bytes']:raise ValueError('ACTUAL_OWN_LUSTRE_ADMISSION_REQUIRED')
        total=refresh(ledger,job,main_ledger);result=quota()
    return dict(result,total_future_reserved_bytes=total,own_forecast_bytes=value['own_forecast_bytes'],
        quota_policy_reference=reference,credit_not_applied=True,own_allocated_credit_applied=False)

def admit(manifest,job_id,node,outputroot,forecast=750_000_000_000):
    main_only();reference=policy_reference(manifest);value=policy(reference);job_id=str(job_id);output=pathlib.Path(outputroot)
    if forecast!=value['own_forecast_bytes'] or node not in manifest['allowed_nodes'] or not output.is_absolute() or '..' in output.parts or not (output==OUTPUT or OUTPUT in output.parents):raise ValueError('EXACT_LUSTRE_OUTPUT_NODE_AND_FORECAST_REQUIRED')
    directory=pathlib.Path(value['execution_control_directory'])
    while True:
        try:
            running=run(['squeue','-h','-j',job_id,'-o','%i|%T|%N|%j|%C|%u']).strip().split('|')
            if running!=[job_id,'RUNNING',node,value['job_name'],'16','zixiao']:raise ValueError('ACTUAL_OWN_RUNNING_NODE21_16CPU_JOB_REQUIRED')
            main_ledger=main_entry(value,job_id,output)
            with locked():
                ledger=read(LEDGER) if LEDGER.exists() else dict(schema='ROOT_LUSTRE_ALL_FUTURE_LEDGER_V1',entries={},quota_policy_reference=reference)
                own=ledger['entries'].setdefault(value['scope_entry_key'],dict(job_id=None,future_reserved_bytes=0,status='DEFERRED_STORAGE_ADMISSION'))
                if own.get('job_id') is not None and str(own['job_id'])!=job_id and (state(own['job_id']) not in TERMINAL or str(own['job_id']) in current_jobs()):raise ValueError('OTHER_ACTUAL_JOB_OWNS_LUSTRE_SCOPE')
                total=refresh(ledger,job_id,main_ledger);result=quota();total=total-own['future_reserved_bytes']+forecast
                if result['free_bytes']-total<value['account_floor_bytes']:raise ValueError('WAITING_FOR_REAL_LUSTRE_QUOTA_MINUS_ALL_LUSTRE_FUTURES')
                own.update(job_id=job_id,future_reserved_bytes=forecast,forecast_bytes=forecast,storage_domain='LUSTRE',status='ACTUAL_RUNNING_STORAGE_ADMITTED',output_root=str(output),node=node)
                totals(ledger);save(LEDGER,ledger)
                result.update(total_future_reserved_bytes=total,own_forecast_bytes=forecast,credit_not_applied=True,own_allocated_credit_applied=False)
                receipt=dict(status='ACTUAL_RUNNING_LUSTRE_D3_STORAGE_ADMITTED',job_id=job_id,node=node,output_root=str(output),
                    quota_policy_reference=reference,quota_snapshot=result,forecast_is_not_output_hard_cap=True,no_expiry=True,main_scope_future_bytes=0)
                admission=save(directory/('storage_admission_'+job_id+'.json'),receipt,pin=True)
                return dict(admission_reference=admission,admission_ref=admission,quota_snapshot=result,total_future_reserved_bytes=total)
        except Exception as error:
            save(directory/('storage_wait_'+job_id+'.json'),dict(status='WAITING_NO_SCIENCE_TERMINATION',job_id=job_id,observed_unix_seconds=time.time(),reason=repr(error)))
            time.sleep(60)

def observe(plan,earlier):
    reference=policy_reference(plan);job=str(plan.get('job_id') or os.environ.get('SLURM_JOB_ID',''))
    encoded=base64.urlsafe_b64encode(json.dumps(reference).encode()).decode()
    command='PYTHONPATH='+shlex.quote(str(R/'repository'))+' '+shlex.quote(sys.executable)+' -B '+shlex.quote(str(pathlib.Path(__file__).resolve()))+' --observe --policy '+shlex.quote(encoded)
    if job:command+=' --job-id '+shlex.quote(job)
    lines=run(['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=12','zixiao@sonmi',command]).strip().splitlines()
    if not lines:raise ValueError('NO_MAIN_QUOTA_JSON')
    return json.loads(lines[-1])

def retire(policyref,jid):
    main_only();value=policy(policyref);jid=str(jid);actual=state(jid)
    if actual not in TERMINAL or jid in current_jobs():raise ValueError('ACTUAL_TERMINAL_REQUIRED_TO_RETIRE_FUTURE')
    with locked():
        ledger=read(LEDGER);own=ledger['entries'][value['scope_entry_key']]
        if str(own.get('job_id'))!=jid:raise ValueError('EXACT_LUSTRE_SCOPE_JOB_REQUIRED')
        own.update(future_reserved_bytes=0,status='ACTUAL_TERMINAL_FUTURE_RELEASED_USED_BYTES_NOT_REFUNDED',last_actual_scheduler_state=actual)
        totals(ledger);save(LEDGER,ledger);total=ledger['total_future_reserved_bytes']
    main_entry(value,jid,own['output_root'],status='ACTUAL_TERMINAL_MAIN_METADATA_SCOPE_ZERO')
    return dict(job_id=jid,actual_state=actual,lustre_total_future_reserved_bytes=total,own_future_reserved_bytes=0,main_own_future_reserved_bytes=0,actual_used_bytes_refunded=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--observe',action='store_true');mode.add_argument('--retire',action='store_true')
    parser.add_argument('--policy',required=True);parser.add_argument('--job-id');args=parser.parse_args()
    reference=json.loads(base64.urlsafe_b64decode(args.policy))
    print(json.dumps(retire(reference,args.job_id) if args.retire else snapshot(reference,args.job_id),sort_keys=True))
