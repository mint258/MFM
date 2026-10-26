"""Small owned metadata, exact Slurm fields, finite observable commands."""
from __future__ import annotations
import datetime,hashlib,json,os,re,socket,stat,subprocess,threading,time
from pathlib import Path

ROOT=Path('/gfshome/alpha/codex_data_v1_20261026')
ENDPOINT='218.192.171.238:22';UID=1264;SMALL=2*1024**2
NODES={'compute-0-1','compute-0-3','compute-0-4','compute-0-5','compute-0-6','sonmi1'}
PACKAGE=ROOT/'code/secondary_cpu_queue_v1'
POLICY='SLURM_DEFAULT_UNSPECIFIED'


def need(ok,code):
    if not ok:raise ValueError(code)


def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def state(value):return str(value).split()[0].rstrip('+')


def self_identity():
    path=Path('/proc')/str(os.getpid());raw=(path/'stat').read_text();parts=raw[raw.rfind(')')+2:].split()
    argv=(path/'cmdline').read_bytes();cgroup=(path/'cgroup').read_bytes()
    return {'pid':os.getpid(),'uid':os.getuid(),'hostname':socket.gethostname().split('.')[0],
        'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(parts[19]),
        'pgid':int(parts[2]),'sid':int(parts[3]),'argv':[s.decode() for s in argv.rstrip(b'\0').split(b'\0')],
        'argv_sha256':sha(argv),'cgroup':cgroup.decode(),'cgroup_sha256':sha(cgroup)}


def event(status,**extra):
    print(json.dumps({'observed_at':now(),'status':status,**extra},ensure_ascii=False,allow_nan=False),flush=True)


class Heartbeat:
    """Bound to this foreground invocation, never a persistent service."""
    def __init__(self):self.stop=threading.Event();self.thread=threading.Thread(target=self.loop,daemon=True)
    def loop(self):
        while not self.stop.wait(10):event('PENDING_METADATA_CONTROLLER_FOREGROUND')
    def __enter__(self):self.thread.start();return self
    def __exit__(self,*unused):self.stop.set();self.thread.join(timeout=2)


def literal(path,*,inside=True):
    path=Path(path)
    need(path.is_absolute() and '..' not in path.parts and
         not any(p.is_symlink() for p in (path,*path.parents)),'LITERAL_ABSOLUTE_PATH_REQUIRED')
    if inside:need(ROOT in path.parents,'OWN_ALPHA_RUN_CHILD_REQUIRED')
    return path


def read_small(path,*,inside=True):
    path=literal(path,inside=inside)
    with path.open('rb') as stream:
        a=os.fstat(stream.fileno());need(stat.S_ISREG(a.st_mode) and a.st_uid==os.getuid() and a.st_size<=SMALL,'SMALL_OWNED_METADATA_REQUIRED')
        raw=stream.read(SMALL+1);b=os.fstat(stream.fileno())
    need(len(raw)==a.st_size and (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'METADATA_CHANGED')
    return raw


def ref(path,*,inside=True):
    path=Path(path);raw=read_small(path,inside=inside)
    return {'path':str(path),'bytes':len(raw),'sha256':sha(raw)}


def normalized(value):
    need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'} and
         type(value['bytes']) is int and 0<=value['bytes']<=SMALL and
         isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256']),'EXACT_SMALL_REFERENCE_REQUIRED')
    return value


def verify(value):
    normalized(value);need(ref(value['path'])==value,'ACTUAL_ALPHA_TARGET_PIN_CHANGED');return Path(value['path'])


def pairs_unique(pairs):
    out={}
    for key,value in pairs:need(key not in out,'DUPLICATE_JSON_KEY');out[key]=value
    return out


def load(path,*,inside=True):return json.loads(read_small(path,inside=inside),object_pairs_hook=pairs_unique)
def load_ref(value):return load(verify(value))


def write_new(path,value):
    """Atomic, exclusive publication. Never overwrite an old proof or receipt."""
    path=literal(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=canonical(value)+b'\n';need(len(raw)<=SMALL,'SMALL_METADATA_OUTPUT_LIMIT')
    temporary=path.with_name('.'+path.name+'.tmp.'+str(os.getpid()))
    fd=os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.link(temporary,path,follow_symlinks=False)
    finally:
        if temporary.exists():temporary.unlink()
    return ref(path)


def fields(raw):
    need(isinstance(raw,str),'SCONTROL_TEXT_REQUIRED')
    matches=list(re.finditer(r'(?<!\S)([A-Za-z][A-Za-z0-9_./+:-]*)=',raw))
    need(matches and not raw[:matches[0].start()].strip(),'SCONTROL_FIELDS_REQUIRED')
    out={}
    for index,match in enumerate(matches):
        key=match[1];need(key not in out,'DUPLICATE_SCONTROL_FIELD:'+key)
        out[key]=raw[match.end():matches[index+1].start() if index+1<len(matches) else len(raw)].strip()
    return out


def duration(value):
    match=re.fullmatch(r'(?:(\d+)-)?(\d+):(\d{2}):(\d{2})',value)
    need(match is not None,'FINITE_SLURM_HH_MM_SS_REQUIRED')
    days,hours,minutes,seconds=map(int,(match[1] or '0',match[2],match[3],match[4]))
    need(minutes<60 and seconds<60,'INVALID_SLURM_CLOCK')
    return days*86400+hours*3600+minutes*60+seconds


def wall(value):
    need(type(value) is int and 0<value<=172800 and value%60==0,'EXACT_WHOLE_MINUTE_MAX48H_REQUIRED')
    return '%02d:%02d:00'%(value//3600,value%3600//60)


def query(argv,*,allow_failure=False,timeout=15,env=None,emit=True):
    if emit:event('PENDING_METADATA_QUERY',command=argv[0])
    started=time.monotonic()
    try:
        result=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=timeout,env=env)
    except subprocess.TimeoutExpired as exc:
        raise ValueError('METADATA_QUERY_TIMEOUT_NO_SUBMISSION_RETRY:'+argv[0]) from exc
    need(len(result.stdout.encode())+len(result.stderr.encode())<=SMALL,'QUERY_METADATA_OUTPUT_LIMIT')
    row={'argv':argv,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
         'observed_at':now(),'observed_unix_seconds':time.time(),'elapsed_seconds':time.monotonic()-started}
    need(allow_failure or result.returncode==0,'METADATA_QUERY_FAILED:'+canonical(row).decode())
    return row


def login():
    need(os.name=='posix' and os.getuid()==UID and socket.gethostname().split('.')[0]=='sonmi' and
         not os.environ.get('SLURM_JOB_ID'),'INDEPENDENT_ALPHA_LOGIN_CONTROLLER_ONLY')


def source_review(path):
    review=load(path)
    need(review.get('schema')=='ROOT_SECONDARY_CPU_CONTROLLER_SOURCE_REVIEW_V1' and
         review.get('status')=='APPROVED_FOR_METADATA_CONTROL_ONLY' and review.get('reviewer')=='root' and
         review.get('endpoint')==ENDPOINT and review.get('uid')==UID and review.get('run_root')==str(ROOT) and
         review.get('login_hostname')=='sonmi','ROOT_CONTROLLER_SOURCE_REVIEW_REQUIRED')
    rows=review['sources'];expected={str(p) for p in PACKAGE.glob('*.py')}
    need(rows and {r['target_locator']['path'] for r in rows}==expected and len(rows)==len(expected),'EXACT_CONTROLLER_SOURCE_SET_REQUIRED')
    for row in rows:
        old,new=row['origin_reference'],row['target_locator']
        need(old['bytes']==new['bytes'] and old['sha256']==new['sha256'],'MAIN_TO_ALPHA_SOURCE_BYTES_DIFFER')
        verify(new)
    need(str(Path(__file__).absolute()) in expected,'ACTUAL_CONTROLLER_PACKAGE_PATH_REQUIRED')
    return review


def authority(path):
    value=load(path)
    if value.get('schema')=='USER_AUTHORIZED_SECONDARY_DATA_CLUSTER_V1':
        need(value.get('endpoint')==ENDPOINT and value.get('username')=='alpha' and value.get('observed_uid')==UID and
             value.get('run_root')==str(ROOT) and value.get('cpus_per_task')==16 and value.get('no_gpu') is True and
             value.get('no_exclusive') is True,'EXACT_ALPHA_CLUSTER_AUTHORITY_REQUIRED')
        nodes=value['actual_cpu_nodes']
    else:
        target=value.get('target',{})
        need(value.get('schema')=='USER_AUTHORIZED_SECONDARY_FREE_CPU_UFF_V1' and
             target.get('ssh_host')=='218.192.171.238' and target.get('ssh_user')=='alpha' and target.get('uid')==UID and
             target.get('deployment_root')==str(ROOT) and value.get('formal_generation_authorized') is False,
             'EXACT_ALPHA_UFF_QA_AUTHORITY_REQUIRED')
        nodes=target['allowed_cpu_nodes']
    need(value.get('status')=='USER_AUTHORIZED' and value.get('memory_policy')==POLICY and set(nodes)==NODES and
         type(value.get('max_wall_seconds')) is int and 0<value['max_wall_seconds']<=172800,'LATEST_ALPHA_CPU_RESOURCE_AUTHORITY_REQUIRED')
    return value


def job_identity(request,raw,jid,*,held=False):
    job=fields(raw)
    need(job.get('JobId')==str(jid) and job.get('UserId')=='alpha(1264)' and job.get('JobName')==request['job_name'] and
         job.get('Partition')=='cpu' and job.get('NumCPUs')=='16' and job.get('NumTasks')=='1' and job.get('Requeue')=='0' and
         job.get('Command')==request['script_reference']['path'] and job.get('WorkDir')==str(ROOT) and
         duration(job.get('TimeLimit',''))==request['wall_seconds'],'EXACT_OWN_ALPHA_JOB_SCRIPT_CPU_WALL_REQUIRED')
    if held:
        need(job.get('JobState')=='PENDING' and job.get('Reason')=='JobHeldUser' and job.get('Priority')=='0' and
             job.get('ReqNodeList')==request['node'] and job.get('NumNodes') in {'1','1-1'},'EXACT_OWN_HELD_ALPHA_JOB_REQUIRED')
    else:
        need(job.get('JobState')=='RUNNING' and job.get('NodeList')==request['node'] and job.get('NumNodes')=='1','EXACT_OWN_RUNNING_ALPHA_JOB_REQUIRED')
    return job


def free_cpus(request):
    row=query(['scontrol','show','node',request['node'],'--oneliner']);node=fields(row['stdout'])
    need(node.get('NodeName')==request['node'] and 'cpu' in node.get('Partitions','').split(','),'ACTUAL_CPU_NODE_REQUIRED')
    total,used=int(node['CPUTot']),int(node['CPUAlloc'])
    need(0<=used<=total,'NODE_CPU_COUNTS_INVALID')
    return {'free_cpus':total-used,'required_cpus':16,'memory_admission_evaluated':False,'actual_query':row}


def storage_observation(*,quiet=False):
    path=literal(ROOT/'control');v=os.statvfs(path)
    mount=query(['findmnt','-n','-T',str(ROOT),'-t','fuse.glusterfs','-o','TARGET,FSTYPE,SOURCE'],emit=not quiet)
    rows=[line for line in mount['stdout'].splitlines() if line.strip()]
    need(len(rows)==1,'ONE_ACTUAL_GFSHOME_GLUSTER_MOUNT_REQUIRED')
    parts=rows[0].split(None,2);need(len(parts)==3 and parts[1]=='fuse.glusterfs','ACTUAL_GFSHOME_MOUNT_REQUIRED')
    return {'observed_unix_seconds':time.time(),'node':socket.gethostname().split('.')[0],'uid':os.getuid(),
        'run_root':str(ROOT),'statvfs':{'f_bavail':v.f_bavail,'f_frsize':v.f_frsize,'available_bytes':v.f_bavail*v.f_frsize},
        'mount':{'target':parts[0],'filesystem_type':parts[1],'source':parts[2]},'findmnt':mount,
        'mount_selection_basis':'This run explicitly expects fuse.glusterfs; findmnt type filter excludes the overlapping autofs systemd-1 mount. Raw filtered output is retained.',
        'df':query(['df','-P','-T',str(ROOT)],emit=not quiet),'quota':query(['quota','-v','-u','alpha'],allow_failure=True,emit=not quiet),
        'quota_output_not_automatically_applied_to_gfshome':True}


def effective_storage(observation,review_path,output_cap,*,reservation_evidence=None):
    review=load(review_path)
    need(review.get('schema')=='ROOT_SECONDARY_GFSHOME_STORAGE_SCOPE_V1' and
         review.get('status')=='OBSERVED_CURRENT_MOUNT_AND_QUOTA_SCOPE' and review.get('reviewer')=='root' and
         review.get('endpoint')==ENDPOINT and review.get('uid')==UID and review.get('run_root')==str(ROOT) and
         review.get('no_matching_mount_user_quota_reported') is True and
         review.get('statvfs_is_current_effective_free_basis') is True and
         review.get('independent_project_quota_absence_claimed') is False and review.get('quota_scope_explanation') and
         review.get('evidence_references'),'ACTUAL_GFSHOME_OBSERVED_STORAGE_SCOPE_REQUIRED')
    need(review['mount_target']==observation['mount']['target'] and review['filesystem_type']==observation['mount']['filesystem_type'] and
         (Path(review['mount_target'])==ROOT or Path(review['mount_target']) in ROOT.parents),'ACTUAL_MOUNT_DIFFERS_FROM_REVIEWED_QUOTA_SCOPE')
    for value in review['evidence_references']:verify(value)
    extra=0
    for row in review.get('additional_task_output_reservations',[]):
        verify(row['metadata_reference']);need(type(row['whole_output_cap_bytes']) is int and row['whole_output_cap_bytes']>=0,
                                             'EXPLICIT_ADDITIONAL_OWN_TASK_WHOLE_CAP_REQUIRED')
        extra+=row['whole_output_cap_bytes']
    free=observation['statvfs']['available_bytes'];reserved=output_cap+extra
    need(type(free) is int and free-reserved>=200000000000,'WAIT_EFFECTIVE_FREE_WHOLE_CAP_PLUS200GB')
    return {'effective_free_bytes':free,'effective_free_basis':'Actual f_bavail*f_frsize on the observed gfshome mount; current tools report no matching mount user quota. Other-device quota not used; hidden project quota absence is not claimed.',
        'observed_unix_seconds':observation['observed_unix_seconds'],'storage_scope_review_reference':ref(review_path),
        'out_of_scope_quota_devices':review.get('out_of_scope_quota_devices',[]),'memory_admission_evaluated':False,
        'whole_output_caps_reserved_bytes':reserved,'registered_task_reservation_evidence':reservation_evidence,
        'additional_root_recorded_task_output_reservations':review.get('additional_task_output_reservations',[]),
        'independent_project_quota_absence_claimed':False}
