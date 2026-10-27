"""Root-started, finite Main-login quota metadata; no science or queue actions.

The CPU client consumes immutable observations through an atomic latest pointer.
It never interprets compute-local df/statvfs as the shared account's quota.
"""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,re,signal,socket,stat,subprocess,sys,time

HERE=pathlib.Path(__file__).absolute().parent
REPO=HERE.parents[3];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4 import contract as C

RUN=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
ENDPOINT='202.38.247.57:22';UID=1278;CAP=64<<20;SMALL=1<<20;SNAP_CAP=64<<10
REFRESH=30;MAX_AGE=120;POLL=60;TERMINAL_RESERVE=256<<10
POLICY='MAIN_LOGIN_SAME_STORAGE_REVIEWED_REFRESH30_FRESH120_POLL60'
REVIEW_SCHEMA='ROOT_MAIN_N1_SAME_STORAGE_QUOTA_PROVIDER_REVIEW_V1'
IDENTITY_SCHEMA='MAIN_LOGIN_ACCOUNT_QUOTA_PUBLISHER_IDENTITY_V1'
SNAPSHOT_SCHEMA='MAIN_LOGIN_ACCOUNT_QUOTA_OBSERVATION_V1'
LATEST_SCHEMA='MAIN_LOGIN_ACCOUNT_QUOTA_LATEST_V1'
QUOTA_ARGV=['quota','-v','-u','zixiao']
FINDMNT_ARGV=['findmnt','-n','-T',str(RUN),'-o','TARGET,SOURCE,FSTYPE,FSROOT']
DF_ARGV=['df','-Pk',str(RUN)]
MAPPING_PROBE_REFERENCE={'path':str(RUN/'control/n1_same_storage_mapping_probe_v1.json'),'bytes':8195,
    'sha256':'d7046a46882617aef2ffa3708ff4249a57828fea7aee3c62b24a2c1b324d714d'}
LOGIN_MOUNT={'target':'/share','source':'/dev/sda1','fstype':'xfs','fsroot':'/'}
COMPUTE_MOUNTS={'compute-0-13':{'target':'/share/home','source':'nfs:/share/home','fstype':'nfs4','fsroot':'/'}}
MARKER_IDENTITY={'inode':12957712902,'uid':UID,'bytes':213,'mtime_ns':1793029110467007740}
MAPPING_FILESYSTEM_TOTAL_KIB=31251898368


def small(path):
    path=pathlib.Path(path);C.need(path.is_absolute() and '..' not in path.parts
        and not any(p.is_symlink() for p in (path,*path.parents)),'OWN_LITERAL_METADATA_REQUIRED')
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno());C.need(stat.S_ISREG(before.st_mode) and before.st_uid==UID and before.st_size<=SMALL,'OWN_SMALL_METADATA_REQUIRED')
        raw=stream.read(SMALL+1);after=os.fstat(stream.fileno())
    C.need((before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns)
        and len(raw)==after.st_size,'METADATA_CHANGED_DURING_READ')
    return raw,{'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def pinned(reference):
    C.reference_shape(reference);raw,actual=small(reference['path']);C.need(actual==reference,'PINNED_PROVIDER_METADATA_CHANGED')
    return json.loads(raw)


def source_ref(path):return small(path)[1]


def load_review(reference):
    value=pinned(reference)
    C.need(value.get('schema')==REVIEW_SCHEMA and value.get('status')=='APPROVED_FOR_EXACT_SAME_STORAGE_PROVIDER'
        and value.get('reviewer')=='root' and value.get('endpoint')==ENDPOINT and value.get('uid')==UID
        and value.get('run_root')==str(RUN),'ROOT_EXACT_MAIN_SAME_STORAGE_REVIEW_REQUIRED')
    C.need(value['count_correction_authority_reference']==C.COUNT_CORRECTION_REFERENCE
        and value['policy']==POLICY and value['refresh_seconds']==REFRESH and value['maximum_age_seconds']==MAX_AGE
        and value['cpu_poll_seconds']==POLL and value['maximum_runtime_seconds']<=90000
        and type(value['maximum_runtime_seconds']) is int and value['maximum_runtime_seconds']>0
        and value['whole_provider_output_cap_bytes']==CAP and value['quota_reserve_bytes']==200000000000
        and value['quota_units']=='KiB' and value['local_df_is_not_account_quota'] is True,'EXACT_BOUNDED_REALTIME_QUOTA_POLICY_REQUIRED')
    C.need(value['login_node']=='sonmi' and value['login_quota_device']==value['login_mount']['source']
        and value['same_shared_account_quota_applies_to_all_listed_compute_mounts'] is True,
        'ROOT_REVIEWED_LOGIN_QUOTA_DEVICE_AND_SHARED_EXPORT_MAPPING_REQUIRED')
    C.need(value['login_mount']==LOGIN_MOUNT and value['compute_mount_by_node']==COMPUTE_MOUNTS,
        'ONLY_ACTUAL_PROBED_LOGIN_AND_COMPUTE13_STORAGE_SCOPE_ADMITTED')
    C.need(all(isinstance(mount,dict) and set(mount)=={'target','source','fstype','fsroot'}
        and all(isinstance(v,str) and v for v in mount.values())
        for mount in (value['login_mount'],*value['compute_mount_by_node'].values())),
        'EXACT_OBSERVED_FINDMNT_FIELD_DICTIONARIES_REQUIRED')
    expected={str(HERE/name) for name in ('contract.py','quota_provider.py')}
    C.need(len(value['provider_source_references'])==2 and {p['path'] for p in value['provider_source_references']}==expected,
        'EXACT_PROVIDER_AND_METADATA_CONTRACT_SOURCE_PINS_REQUIRED')
    for item in value['provider_source_references']:C.need(source_ref(item['path'])==item,'PROVIDER_SOURCE_CHANGED')
    C.need(value['probe_reference']==MAPPING_PROBE_REFERENCE and value['probe_reference'] in value['evidence_references'],
        'EXACT_ACTUAL_MAPPING_PROBE_AUTHORITY_REQUIRED')
    for item in value['evidence_references']:pinned(item)
    mapping=pinned(value['probe_reference']);views=[item['decoded'] for item in mapping['observations']]
    C.need(mapping['schema']=='ROOT_ACTUAL_MAIN_COMPUTE13_SHARED_STORAGE_MAPPING_PROBE_V1'
        and mapping['scientific_computation'] is False and len(views)==2
        and {item['node'] for item in views}=={'sonmi','compute-0-13'}
        and all(item['uid']==UID and item['endpoint']==ENDPOINT and item['run_root']==str(RUN)
            and item['marker_reference']==value['marker_reference']
            and all(item['marker_stat'][key]==n for key,n in MARKER_IDENTITY.items()) for item in views),
        'ACTUAL_TWO_HOST_SAME_MARKER_UID_INODE_MTIME_PROBE_REQUIRED')
    resolutions=[item for item in value['evidence_references'] if item['path']==str(RUN/'control/n1_nfs_hostname_resolution_v1.json')]
    C.need(len(resolutions)==1,'ACTUAL_MAIN_NFS_HOSTNAME_RESOLUTION_EVIDENCE_REQUIRED')
    resolution=pinned(resolutions[0])
    C.need(resolution['schema']=='MAIN_SHARED_NFS_HOSTNAME_RESOLUTION_V1' and resolution['node']=='sonmi'
        and resolution['nfs_addresses']==resolution['login_hostname_addresses']==['10.1.1.1'],
        'OBSERVED_NFS_SERVER_AND_MAIN_LOGIN_ADDRESS_BINDING_REQUIRED')
    C.reference_shape(value['marker_reference']);C.need(value['marker_reference']['bytes']<=4096,'SMALL_SHARED_MARKER_ONLY')
    C.need(RUN/'control' in pathlib.Path(value['marker_reference']['path']).parents,'SAME_RUN_SMALL_METADATA_MARKER_REQUIRED')
    output=pathlib.Path(value['publisher_output_dir'])
    C.need(output.is_absolute() and RUN/'control' in output.parents and '..' not in output.parts,
        'NEW_RUN_OWNED_PROVIDER_CONTROL_DIRECTORY_REQUIRED')
    return value


def references(review_reference):
    value=load_review(review_reference)
    return [review_reference,*value['provider_source_references'],*value['evidence_references'],value['marker_reference']]


def query(argv):
    began=time.time()
    try:
        result=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=15,
            env={**os.environ,'LC_ALL':'C'})
        row={'argv':list(argv),'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
    except subprocess.TimeoutExpired as exc:
        decode=lambda raw:raw.decode('utf-8','replace') if isinstance(raw,bytes) else raw or ''
        row={'argv':list(argv),'returncode':None,'stdout':decode(exc.stdout),'stderr':decode(exc.stderr),'error':'TIMEOUT15S'}
    except OSError as exc:row={'argv':list(argv),'returncode':None,'stdout':'','stderr':'','error':repr(exc)}
    row.update(started_unix_seconds=began,finished_unix_seconds=time.time())
    row['raw_output_complete']=True
    if len(C.canonical(row))>SNAP_CAP//2:
        for name in ('stdout','stderr'):
            raw=row[name].encode('utf-8');row[name+'_original_bytes']=len(raw)
            row[name+'_sha256']=hashlib.sha256(raw).hexdigest();row[name]=raw[:4096].decode('utf-8','replace')
        row.update(raw_output_complete=False,error='COMMAND_OUTPUT_EXCEEDED_METADATA_BOUND_PREFIX_AND_SHA_ONLY')
    return row


def parse_quota(row,device):
    C.need(row['argv']==QUOTA_ARGV and row['returncode']==0 and row['stderr']=='' and row.get('raw_output_complete') is True,
        'ACTUAL_SUCCESSFUL_COMPLETE_ACCOUNT_QUOTA_QUERY_REQUIRED')
    C.need(len(re.findall(r'^Disk quotas for user zixiao \(uid 1278\):\s*$',row['stdout'],re.M))==1,
        'EXACT_CURRENT_MAIN_ACCOUNT_QUOTA_HEADER_REQUIRED')
    matches=[line.split() for line in row['stdout'].splitlines() if line.split() and line.split()[0]==device]
    C.need(len(matches)==1 and len(matches[0])>=4,'ONE_MATCHING_REVIEWED_QUOTA_DEVICE_REQUIRED')
    values=matches[0][1:4];C.need(all(re.fullmatch(r'[0-9]+\*?',v) for v in values),'EXACT_KIB_QUOTA_NUMBERS_REQUIRED')
    used,soft,hard=[int(v.rstrip('*')) for v in values];limits=[n for n in (soft,hard) if n>0]
    C.need(limits,'FINITE_ACCOUNT_LIMIT_REQUIRED');limit=min(limits)
    return {'device':device,'uid':UID,'username':'zixiao','units':'KiB','used_kib':used,'limit_kib':limit,
        'free_bytes':(limit-used)*1024,'basis':'minimum_positive_user_soft_hard_limit_minus_used; no df substitution'}


def parse_mount(findmnt,df):
    C.need(findmnt['argv']==FINDMNT_ARGV and df['argv']==DF_ARGV and
        all(row['returncode']==0 and row['stderr']=='' and row.get('raw_output_complete') is True for row in (findmnt,df)),
        'COMPLETE_SUCCESSFUL_SAME_PATH_FINDMNT_AND_DF_REQUIRED')
    rows=[line.split() for line in findmnt['stdout'].splitlines() if line.strip()]
    C.need(rows and all(len(row)==4 for row in rows),'ALL_FINDMNT_ROWS_MUST_HAVE_EXACT_FOUR_FIELDS')
    mounts=[dict(zip(('target','source','fstype','fsroot'),row)) for row in rows]
    active=[row for row in mounts if row['fstype']!='autofs'];overlays=[row for row in mounts if row['fstype']=='autofs']
    C.need(len(active)==1,'EXACTLY_ONE_NON_AUTOFS_ACTIVE_OUTPUT_MOUNT_REQUIRED');chosen=active[0]
    C.need(all(row['source']=='systemd-1' and row['target']==chosen['target'] and row['fsroot']==chosen['fsroot']
        for row in overlays),'AUTOFS_IS_ONLY_OBSERVED_SAME_TARGET_OVERLAY_METADATA')
    lines=[line.split() for line in df['stdout'].splitlines() if line.strip()]
    C.need(len(lines)==2 and lines[0][0]=='Filesystem' and len(lines[1])==6,'UNIQUE_ACTIVE_POSIX_DF_ROW_REQUIRED')
    filesystem,total,used,available,capacity,target=lines[1]
    C.need(filesystem==chosen['source'] and target==chosen['target'] and all(re.fullmatch(r'[0-9]+',v) for v in (total,used,available))
        and int(total)>0 and re.fullmatch(r'[0-9]+%',capacity),'ACTIVE_FINDMNT_SOURCE_TARGET_AND_DF_MUST_AGREE')
    return {'active_mount':chosen,'all_findmnt_rows':mounts,'autofs_overlay_rows':overlays,
        'df_active_row':{'source':filesystem,'target':target,'total_kib':int(total),'used_kib':int(used),
            'available_kib':int(available),'capacity':capacity},
        'selection_basis':'unique non-autofs active row bound to same-path df; autofs retained only as overlay; df is not account quota'}


def storage_observation():
    observed={'endpoint':ENDPOINT,'uid':os.getuid(),'node':socket.gethostname().split('.')[0],
        'findmnt':query(FINDMNT_ARGV),'df':query(DF_ARGV)}
    try:
        selected=parse_mount(observed['findmnt'],observed['df']);observed.update(mount=selected['active_mount'],mount_selection=selected)
    except Exception as exc:observed.update(mount=None,mount_selection=None,parse_error=repr(exc))
    return observed


def verify_storage(review,observed,*,login):
    C.need(observed['endpoint']==ENDPOINT and observed['uid']==UID,'ACTUAL_MAIN_USER_STORAGE_IDENTITY_REQUIRED')
    expected=review['login_mount'] if login else review['compute_mount_by_node'].get(observed['node'])
    C.need(expected is not None and observed['mount']==expected and
        (not login or observed['node']==review['login_node']),'ACTUAL_OUTPUT_MOUNT_DIFFERS_FROM_ROOT_REVIEW')
    C.need(observed['mount_selection']['df_active_row']['total_kib']==MAPPING_FILESYSTEM_TOTAL_KIB,
        'CURRENT_SHARED_FILESYSTEM_TOTAL_DIFFERS_FROM_ACTUAL_MAPPING_PROBE')
    marker_raw,marker_ref=small(review['marker_reference']['path'])
    C.need(marker_ref==review['marker_reference'],'ACTUAL_SHARED_MARKER_BYTES_CHANGED:'+repr(marker_ref))
    info=pathlib.Path(marker_ref['path']).stat()
    marker_stat={'device':info.st_dev,'inode':info.st_ino,'uid':info.st_uid,'bytes':info.st_size,'mtime_ns':info.st_mtime_ns}
    C.need(all(marker_stat[name]==n for name,n in MARKER_IDENTITY.items()),'ACTUAL_MARKER_INODE_MTIME_IDENTITY_CHANGED:'+repr(marker_stat))
    return {'reference':marker_ref,'uid':UID,'bytes_checked':len(marker_raw),'stat':marker_stat,
        'device_identity_is_endpoint_local_not_compared_across_login_and_NFS':True,'scope':'shared metadata marker, not scientific data'}


def validate_observation(value,identity,identity_reference,review,review_reference,now):
    C.need(value['schema']==SNAPSHOT_SCHEMA and value['identity_reference']==identity_reference
        and value['review_reference']==review_reference and value['endpoint']==ENDPOINT and value['uid']==UID
        and value['node']==review['login_node'],'EXACT_ACTUAL_LOGIN_OBSERVATION_BINDING_REQUIRED')
    C.need(identity['schema']==IDENTITY_SCHEMA and identity['endpoint']==ENDPOINT and identity['uid']==UID
        and identity['node']==review['login_node'] and identity['review_reference']==review_reference
        and identity['provider_source_references']==review['provider_source_references']
        and 0<identity['expires_unix_seconds']-identity['started_unix_seconds']<=review['maximum_runtime_seconds']
        and identity['publisher_output_dir']==review['publisher_output_dir'],'EXACT_BOUNDED_PUBLISHER_IDENTITY_REQUIRED')
    duration=identity['expires_unix_seconds']-identity['started_unix_seconds']
    expected_argv=[PY,'-B',str(HERE/'quota_provider.py'),'--review',review_reference['path'],
        '--output',review['publisher_output_dir'],'--max-seconds',str(int(duration))]
    C.need(type(identity['pid']) is int and identity['pid']>0 and type(identity['start_ticks']) is int and identity['start_ticks']>0
        and re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',identity['boot_id'])
        and duration==int(duration) and identity['execution_argv']==expected_argv
        and identity['not_a_Slurm_science_job'] is True and identity['refresh_seconds']==REFRESH
        and identity['whole_output_cap_bytes']==CAP,'LITERAL_ACTUAL_FINITE_ROOT_PUBLISHER_PROCESS_METADATA_REQUIRED')
    C.need(type(value['sequence']) is int and value['sequence']>=0 and value['status']=='RUNNING',
        'PROVIDER_STOPPED_FAILED_OR_EXPIRED_NO_DISPATCH')
    sampled=value['observed_unix_seconds']
    C.need(type(sampled) in (int,float) and 0<=now-sampled<=MAX_AGE and now<identity['expires_unix_seconds']
        and identity['started_unix_seconds']<=sampled<identity['expires_unix_seconds'],'STALE_FUTURE_OR_EXPIRED_ACCOUNT_QUOTA_PROVIDER')
    C.need(value['storage']['mount']==review['login_mount'] and value['storage']['uid']==UID
        and value['storage']['node']==review['login_node'] and value['marker']['reference']==review['marker_reference'],
        'CURRENT_PUBLISHER_MOUNT_AND_SHARED_MARKER_BINDING_REQUIRED')
    C.need(value['marker']['uid']==UID and value['marker']['bytes_checked']==value['marker']['reference']['bytes']
        and all(value['marker']['stat'][key]==n for key,n in MARKER_IDENTITY.items()),
        'ACTUAL_PUBLISHER_SHARED_MARKER_STAT_IDENTITY_REQUIRED')
    selection=parse_mount(value['storage']['findmnt'],value['storage']['df'])
    C.need(value['storage']['mount_selection']==selection and selection['active_mount']==review['login_mount']
        and selection['df_active_row']['total_kib']==MAPPING_FILESYSTEM_TOTAL_KIB,
        'RAW_PUBLISHER_FINDMNT_DF_AND_DECLARED_MOUNT_SELECTION_DIFFER')
    parsed=parse_quota(value['quota_query'],review['login_quota_device'])
    C.need(value['parsed_quota']==parsed,'RAW_ACTUAL_QUOTA_AND_DECLARED_FREE_DIFFER')
    return parsed


class Client:
    """Parent-only current metadata reader; caller retains STOP and natural drain."""
    def __init__(self,review_reference,request):
        self.reference=review_reference;self.review=load_review(review_reference);self.request=request
        C.need(request['node'] in self.review['compute_mount_by_node'],'CURRENT_CPU_NODE_MUST_BE_IN_STORAGE_REVIEW')
        self.identity=None;self.sequence=-1;self.last=None
    def observe(self):
        review=load_review(self.reference);C.need(review==self.review,'SAME_PINNED_STORAGE_REVIEW_REQUIRED')
        observed=storage_observation();C.need(observed['node']==self.request['node'],'ACTUAL_CPU_NODE_REQUIRED')
        self.last={'cpu_storage':observed,'observed_unix_seconds':0,'publisher_expires_unix_seconds':0}
        marker=verify_storage(review,observed,login=False)
        root=pathlib.Path(review['publisher_output_dir']);raw,_=small(root/'latest.json');latest=json.loads(raw)
        C.need(latest['schema']==LATEST_SCHEMA and latest['review_reference']==self.reference,'EXACT_CURRENT_PROVIDER_POINTER_REQUIRED')
        identity_reference=latest['identity_reference'];snapshot_reference=latest['snapshot_reference']
        C.need(pathlib.Path(identity_reference['path'])==root/'identity.json' and pathlib.Path(snapshot_reference['path']).parent==root
            and re.fullmatch(r'observation_[0-9]{6}\.json',pathlib.Path(snapshot_reference['path']).name),
            'ONLY_EXACT_PROVIDER_OWNED_IMMUTABLE_LOCATORS_ALLOWED')
        identity=pinned(identity_reference);value=pinned(snapshot_reference)
        self.last={'identity_reference':identity_reference,'snapshot_reference':snapshot_reference,'provider_status':value.get('status'),
            'provider_error':value.get('error'),'previous_actual_observation_reference':value.get('previous_actual_observation_reference'),
            'publisher_expires_unix_seconds':identity.get('expires_unix_seconds'),
            'observed_unix_seconds':value.get('observed_unix_seconds'),'cpu_storage':observed,'cpu_marker':marker}
        parsed=validate_observation(value,identity,identity_reference,review,self.reference,time.time())
        C.need((self.identity is None or self.identity==identity_reference) and value['sequence']>=self.sequence,
            'PROVIDER_IDENTITY_CHANGED_OR_OBSERVATION_ROLLED_BACK')
        self.identity=identity_reference;self.sequence=value['sequence']
        self.last.update(free_bytes=parsed['free_bytes'],raw_quota=value['quota_query'],parsed_quota=parsed)
        return self.last


def own_bytes(root):
    total=0
    for path in root.iterdir():
        C.need(path.is_file() and not path.is_symlink() and path.stat().st_uid==UID,'OWN_FLAT_PROVIDER_METADATA_ONLY')
        total+=path.stat().st_size
    return total


def write_new(path,raw):
    C.need(len(raw)<=SNAP_CAP,'BOUNDED_PROVIDER_METADATA_WRITE')
    with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return source_ref(path)


def publish(root,value,identity_reference,review_reference,*,terminal=False):
    raw=C.canonical(value)+b'\n';reserve=0 if terminal else TERMINAL_RESERVE
    C.need(own_bytes(root)+len(raw)+2*SNAP_CAP<=CAP-reserve,'PROVIDER64MIB_WHOLE_OUTPUT_CAP')
    reference=write_new(root/('observation_%06d.json'%value['sequence']),raw)
    latest={'schema':LATEST_SCHEMA,'identity_reference':identity_reference,'snapshot_reference':reference,'review_reference':review_reference}
    pending=root/('latest_%06d.pending'%value['sequence']);write_new(pending,C.canonical(latest)+b'\n')
    os.replace(pending,root/'latest.json')
    descriptor=os.open(str(root),os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)
    return reference


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review',type=pathlib.Path,required=True);parser.add_argument('--output',type=pathlib.Path,required=True)
    parser.add_argument('--max-seconds',type=int,required=True);args=parser.parse_args()
    review_reference=source_ref(args.review);review=load_review(review_reference)
    C.need(os.getuid()==UID and socket.gethostname().split('.')[0]=='sonmi','ROOT_STARTS_ONLY_OWN_MAIN_LOGIN_METADATA_PUBLISHER')
    C.need(str(args.output)==review['publisher_output_dir'] and 0<args.max_seconds<=review['maximum_runtime_seconds'],
        'EXACT_REVIEWED_NEW_FINITE_PROVIDER_OUTPUT_REQUIRED')
    C.need(not args.output.exists() and not any(p.is_symlink() for p in (args.output,*args.output.parents)),
        'EXCLUSIVE_NEW_PROVIDER_DIRECTORY_REQUIRED')
    expected=[PY,'-B',str(HERE/'quota_provider.py'),'--review',str(args.review),'--output',str(args.output),'--max-seconds',str(args.max_seconds)]
    actual_argv=[item.decode('utf-8') for item in pathlib.Path('/proc/self/cmdline').read_bytes().split(b'\0') if item]
    C.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==HERE/'quota_provider.py'
        and pathlib.Path(sys.argv[0]).absolute()==HERE/'quota_provider.py'
        and pathlib.Path(sys.executable)==pathlib.Path(PY) and sys.argv[1:]==expected[3:] and actual_argv==expected,
        'EXACT_ACTUAL_PRIMARY_AND_COMPLETE_ROOT_PUBLISHER_PROCESS_ARGV_REQUIRED')
    args.output.mkdir(mode=0o700,parents=False,exist_ok=False)
    started=time.time();began=time.monotonic();stopping=[]
    for signum in (signal.SIGTERM,signal.SIGINT):signal.signal(signum,lambda number,frame:stopping.append(number))
    identity={'schema':IDENTITY_SCHEMA,'endpoint':ENDPOINT,'uid':os.getuid(),'node':socket.gethostname().split('.')[0],
        'pid':os.getpid(),'start_ticks':int(pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
        'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'execution_argv':expected,
        'started_unix_seconds':started,'expires_unix_seconds':started+args.max_seconds,'publisher_output_dir':str(args.output),
        'provider_source_references':review['provider_source_references'],'review_reference':review_reference,
        'not_a_Slurm_science_job':True,'refresh_seconds':REFRESH,'whole_output_cap_bytes':CAP}
    identity_reference=write_new(args.output/'identity.json',C.canonical(identity)+b'\n');sequence=0;failure=None;previous=None
    # Keep command/terminal-write time inside the finite lease; a metadata
    # command is bounded15s and there are at most three per observation.
    dispatch_deadline=began+max(0,args.max_seconds-60)
    while not stopping and time.monotonic()<dispatch_deadline:
        cycle_started=time.monotonic()
        value={'schema':SNAPSHOT_SCHEMA,'identity_reference':identity_reference,'review_reference':review_reference,
            'endpoint':ENDPOINT,'uid':os.getuid(),'node':'sonmi','sequence':sequence,'status':'RUNNING','observed_unix_seconds':time.time()}
        try:
            storage=storage_observation();value['storage']=storage;value['marker']=verify_storage(review,storage,login=True)
            value['quota_query']=query(QUOTA_ARGV);value['parsed_quota']=parse_quota(value['quota_query'],review['login_quota_device'])
        except Exception as exc:value.update(status='ERROR',error=repr(exc));failure=repr(exc)
        try:previous=publish(args.output,value,identity_reference,review_reference)
        except Exception as exc:failure=repr(exc);sequence+=1;break
        sequence+=1
        if failure:break
        deadline=min(dispatch_deadline,cycle_started+REFRESH)
        while not stopping and time.monotonic()<deadline:time.sleep(min(1,max(0,deadline-time.monotonic())))
    final={'schema':SNAPSHOT_SCHEMA,'identity_reference':identity_reference,'review_reference':review_reference,
        'endpoint':ENDPOINT,'uid':UID,'node':'sonmi','sequence':sequence,'observed_unix_seconds':time.time(),
        'status':'ERROR' if failure else 'STOPPED' if stopping else 'EXPIRED','error':failure,'observed_stop_signals':stopping,
        'previous_actual_observation_reference':previous,
        'scientific_calls':0,'forced_science_signals':False}
    publish(args.output,final,identity_reference,review_reference,terminal=True)
    print(json.dumps({'status':final['status'],'last_sequence':sequence,'managed_bytes':own_bytes(args.output),'scientific_calls':0}))
    return 3 if failure else 0


if __name__=='__main__':raise SystemExit(main())
