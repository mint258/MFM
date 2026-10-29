"""Root submits ONE explicit fresh R1 member after real routing7/SDK closure."""
from __future__ import annotations
import argparse,csv,hashlib,json,os,re,socket,stat,subprocess,time
from pathlib import Path
import admission as m
B,N,W,HERE=m.B,m.N,m.W,m.HERE;REG=N/'native_S_profile_registered_reservations_v6.json';LIMIT=m.LIMIT

def write(path,value,*,fresh=True):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();m.need(len(raw)<=2<<20,'Small owned control cap')
    target=path if fresh else path.with_name(path.name+'.pending')
    with target.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    if not fresh:os.replace(target,path)
    return m.reference(path)
def command(argv,*,env=None,timeout=45):
    r=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,env=env,timeout=timeout)
    m.need(len(r.stdout)+len(r.stderr)<=2<<20,'Bounded actual command observation')
    return dict(argv=argv,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
def previous_member(case,cfg,position,pins):
    if position==1:return None
    p=Path(case['R1_family'])/('member_'+str(position-1));sub=m.read(p/'control/Root_submission_actual_v1.json')
    m.need(sub['status']=='SUBMITTED' and sub['source_package']==pins and sub['cohort']==case['old_job_id']
        and sub['position']==position-1 and sub['series_id']==case['R1_series_id'],'Previous fresh member submission differs')
    out=p/'child';c=m.read(out/'configuration.json');s=m.read(out/'summary.json');r=m.read(out/'run_status.json');sup=m.read(p/'supervisor.json')
    m.need(c['job_id']==sup['job_id']==sub['job_id'] and s['series_id']==case['R1_series_id']
        and s['abba_position']==position-1 and s['role']==m.ROLES[position-2]
        and s['gpu_uuid']==c['gpu_uuid']==case['gpu_uuid'] and s['code_sha']==c['code_sha']==m.CODE
        and s['prereg_sha']==c['prereg_sha']==m.PUBLIC,'Previous current same-card member identity differs')
    m.need(s['status']==r['status']=='STANDALONE_TIMING_COMPLETED' and s['warmup_updates']==2 and s['measured_updates']==20
        and s['smoke'] is c['smoke'] is False and s['foreign_gpu_risk_observed'] is s['padding_exploration'] is False
        and s['tracking_mode']=='offline' and s['candidate_options_sha256']==c['candidate_options_sha256']==case['candidate_options']['sha256']
        and r['failure'] is None and r['cleanup_errors']==[]
        and r['stream_cleanup']['errors']==[] and r['stream_cleanup']['input_descriptors_closed'] is True,'Previous22updates/trainer/SDK finish required')
    m.need(sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
        and sup['remaining_recorded_processes_before_retirement']==[] and sup['private_storage_cleanup_errors']==[]
        and sup['foreign_gpu_processes_signalled'] is False
        and sup['supervisor_source_sha256']==m.read(HERE/'dependencies.json')['raw_refs']['routing_dependency_supervisor']['sha256'],
        'Previous original supervision/private cleanup required')
    for key in ('model','optimizer','loss_policy','loss_weights','supervision','schedule','reference_configuration','a4_configuration',
        'original_shard_snapshot_prejob_sha256','data_version','candidate'):
        m.need(m.exact(c[key],cfg[key]),'Previous exact current numeric cohort differs: '+key)
    m.need('performance_execution' not in c and 'performance_execution_request' not in c
        and m.exact(c['effective_options'],cfg['reference'] if m.ROLES[position-2]=='reference' else cfg['candidate'])
        and m.exact(c['source_sha256'],cfg['source_sha256'])
        and c['configuration_sha256']==s['configuration_sha256']==m.canonical({k:v for k,v in c.items() if k!='configuration_sha256'}),'Previous unintegrated options/source/config differs')
    run=s['tracking_run_id'];m.need(re.fullmatch('[a-z0-9]{8}',run),'Previous actual tracking ID required')
    paths=list((out/'wandb').glob('offline-run-*/run-'+run+'.wandb'));m.need(len(paths)==1,'One actual original SDK required')
    descriptors={}
    for name,path,cap in (('SDK',paths[0],128<<20),('steps',out/'steps.jsonl',32<<20)):
        info=path.lstat();m.need(path.resolve()==path and path.is_relative_to(out) and stat.S_ISREG(info.st_mode)
            and info.st_uid==1278 and info.st_nlink==1 and 0<info.st_size<=cap,'Previous SDK/journal stat identity differs')
        descriptors[name]=dict(path=str(path),bytes=info.st_size,payload_opened=False)
    raw=command(['sacct','-X','-n','-P','-j',sub['job_id'],'--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'])
    m.parents(raw,{sub['job_id']:case['expected_node']})
    return dict(submission=m.reference(p/'control/Root_submission_actual_v1.json'),actual_sacct=raw,SDK_and_steps_stat_only=descriptors)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort',choices=('4520486','4520405','4520456','4520438','4520411','4520549'),required=True)
    parser.add_argument('--position',type=int,choices=(1,2,3,4),required=True)
    parser.add_argument('--qualification',type=Path,required=True);parser.add_argument('--qualification-sha256',required=True)
    parser.add_argument('--source-pins-sha256',required=True)
    parser.add_argument('--method-publication',type=Path,required=True);parser.add_argument('--method-publication-sha256',required=True)
    parser.add_argument('--known-hosts-sha256');parser.add_argument('--submit',action='store_true',required=True)
    args=parser.parse_args();m.need(os.getuid()==os.geteuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
        and not os.environ.get('SLURM_JOB_ID'),'Explicit Root login metadata/submission action only')
    pins=m.verify_package(args.source_pins_sha256);pub=m.reference(args.method_publication)
    m.need(pub['sha256']==args.method_publication_sha256,'Actual new method raw SHA differs');m.verify_method(pub)
    qref=m.reference(args.qualification);m.need(qref['sha256']==args.qualification_sha256,'Explicit actual qualification input SHA differs')
    q=m.qualify(args.cohort,qref);case=q['case'];case['R1_family']=q['declared']['family'];case['R1_series_id']=q['declared']['series_id']
    cfg=q['numeric_configuration'];node=case['expected_node'];gpu=case['gpu_uuid'];api=m.policy()
    predecessor=previous_member(case,cfg,args.position,pins)
    raw=command(['sacct','-X','-n','-P','-j',','.join(sorted(q['actual_parent_nodes'])),
        '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']);m.parents(raw,q['actual_parent_nodes'])
    family=Path(case['R1_family'])/('member_'+str(args.position));control=family/'control';out=family/'child';record=family/'supervisor.json'
    m.need(not family.exists() and family.resolve()==family and family.is_relative_to(N),'Fresh one-use member family required')
    rid='remaining_Av2_R1_v3_'+args.cohort+'_member_'+str(args.position);control.mkdir(mode=0o700,parents=True)
    with api.registry_lock(REG):
        registry=api.read(REG);m.need(rid not in registry['reservations'] and rid not in registry.get(api.REGISTRY_KEY,{}),'Fresh independent hold/software ID required')
        principal=write(control/'principal.json',dict(schema='model_v3_Root_one_job_output_reservation_v1',authority='ROOT_ACTUAL',uid=1278,
            filesystem='/dev/sda1',reservation_id=rid,phase=str(family),max_bytes=LIMIT,reserved_additional_bytes=LIMIT,
            initial_existing_bytes=0,scientific_acceptance=False,source_package=pins))
        entry=dict(phase=str(family),principal=principal,principal_sha256=principal['sha256'],remaining_bytes=LIMIT);registry['reservations'][rid]=entry
        registration=api.make_registration(registration_id=rid,node=node,gpu_uuid=gpu,software_budget_bytes=64<<30,rss_limit_bytes=56<<30,
            Root_source=m.reference(__file__),source_pins=pins,proof_refs=(pub,qref))
        api.put_registration(registry,registration);write(REG,registry,fresh=False)
    bound_case=write(control/'BOUND_COHORT.json',dict(schema='model_v3_remaining_Av2_R1_precise_cohort_binding_v1',cohort=args.cohort,
        case=case,numeric_configuration=cfg,qualification_input=qref,qualification_source_root_refs={k:q['qualification'][k] for k in ('Root_numeric_closure','SDK_closure')},
        exact_server_CPython_integer_copy=True,source_package=pins,method_publication=pub,position=args.position,role=m.ROLES[args.position-1],reservation_id=rid,
        old_or_cross_UUID_timing_reused=False))
    attempt_path=control/'Root_submission_actual_v1.json';attempt=dict(schema='model_v3_remaining_Av2_R1_Root_single_submission_v1',status='ADMISSION_STARTED',
        job_id=None,cohort=args.cohort,position=args.position,role=m.ROLES[args.position-1],series_id=case['R1_series_id'],source_package=pins,
        method_publication=pub,qualification=qref,bound_cohort=bound_case,predecessor=predecessor,fresh_numeric_SDK_parents=raw,automatic_retry=False,
        Slurm_memory_mode='automatic_default',Slurm_requested_memory_bytes=None,software_memory_budget_bytes=64<<30,RSS_limit_bytes=56<<30,observations=[])
    write(attempt_path,attempt);intent=False
    def capture(argv):
        value=command(argv);attempt['observations'].append(value);write(attempt_path,attempt,fresh=False)
        m.need(value['returncode']==0,'Actual resource observation failed');return value['stdout']
    try:
        start=time.monotonic();node_raw=capture(['scontrol','show','node',node]);values=dict(re.findall(r'\b(CPUAlloc|CPUTot)=(\d+)',node_raw))
        m.need(len(values)==2 and int(values['CPUTot'])-int(values['CPUAlloc'])>=16
            and not any(x in node_raw for x in ('DOWN','DRAIN','FAIL','UNKNOWN','MAINT')),'Actual node/CPU16 capacity required')
        queue_raw=capture(['squeue','-h','-w',node,'-o','%i|%u|%t|%m|%C'])
        routing_plan=m.bound(m.read(HERE/'dependencies.json')['raw_refs']['routing_plan']);trust=routing_plan['routing_trust'][node]
        if trust['mode']=='PINNED_EXISTING_PUBLIC_PROJECTION':host=trust['reference'];m.bound(host,False)
        else:
            path=Path(trust['path']);info=path.lstat();m.need(path==Path('/share/home/zixiao/.ssh/known_hosts') and stat.S_ISREG(info.st_mode)
                and info.st_uid==1278 and info.st_nlink==1 and 0<info.st_size<=2<<20 and args.known_hosts_sha256,'Explicit existing personal trusted host SHA required')
            body=path.read_bytes();host=dict(path=str(path),bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
            m.need(host['sha256']==args.known_hosts_sha256,'Existing trusted host raw SHA differs')
        ssh=['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+host['path'],node]
        mem_raw=capture(ssh+['head -n 5 /proc/meminfo']);memory=api.assess(node_raw,queue_raw,mem_raw,node=node,
            software_budget_bytes=64<<30,rss_limit_bytes=56<<30,registry_path=REG,current_reservation_id=rid)
        quota_raw=capture(['quota','-v','-u','zixiao']);rows=[x.split() for x in quota_raw.splitlines() if x.split() and x.split()[0]=='/dev/sda1']
        m.need(len(rows)==1,'Actual quota row required');used,soft,hard=[int(rows[0][i].rstrip('*')) for i in (1,2,3)]
        limits=[x for x in (soft,hard) if x>0];m.need(limits,'Finite actual quota required');free=(min(limits)-used)*1024
        with api.registry_lock(REG):live=api.read(REG)
        amounts=[x['remaining_bytes'] for x in live['reservations'].values()];m.need(live['reservations'][rid]==entry and all(type(x) is int and x>=0 for x in amounts)
            and free>=sum(amounts)+(64<<30),'Every registered hold plus64GiB quota reserve required')
        gpu_raw=capture(ssh+['nvidia-smi --query-gpu=uuid,name,memory.total,memory.free,memory.used --format=csv,noheader,nounits'])
        selected=[x for x in csv.reader(gpu_raw.splitlines(),skipinitialspace=True) if x and x[0].strip()==gpu]
        m.need(len(selected)==1 and len(selected[0])==5 and case['expected_gpu'] in selected[0][1],'Actual matched GPU type/UUID required');g=selected[0]
        m.need(all(x.strip().isdigit() for x in g[2:]) and int(g[2])>0 and 0<int(g[3])<=int(g[2]) and 0<=int(g[4])<=int(g[2]),'Known physical GPU memory required')
        apps=capture(ssh+['nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader,nounits'])
        for app in csv.reader(apps.splitlines(),skipinitialspace=True):
            if not app or app==['No running processes found']:continue
            m.need(len(app)==4 and app[0].startswith('GPU-') and app[1].strip().isdigit() and app[0].strip()!=gpu,'Selected GPU occupied/unknown; never signal foreign processes')
        lock=B/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(gpu+'.lock');capture(ssh+['flock -n '+str(lock)+' true'])
        m.need(time.monotonic()-start<=120,'Original whole resource freshness exhausted')
        frame=write(control/'Root_admission_actual_v1.json',dict(schema='model_v3_remaining_Av2_R1_auto_Root_admission_v1',authority='ROOT_ACTUAL',
            captured_unix=time.time(),node=node,gpu_uuid=gpu,cpus=16,Slurm_memory_mode='automatic_default',software_memory_budget_bytes=64<<30,RSS_limit_bytes=56<<30,
            assessment=memory,quota_available_bytes=free,remaining_registered_bytes=sum(amounts),host_binding=host,observations=attempt['observations'],
            source_package=pins,method_publication=pub,bound_cohort=bound_case,UUID_lock_checked_and_released=True,finite_physical_memory_guarantee_claimed=False))
        env={k:v for k,v in os.environ.items() if not k.startswith('SBATCH_')};env.update(MODEL_V3_R1_PACKAGE=str(HERE),MODEL_V3_R1_PACKAGE_SHA=pins['sha256'],
            MODEL_V3_R1_BOUND_COHORT=bound_case['path'],MODEL_V3_R1_BOUND_COHORT_SHA=bound_case['sha256'],MODEL_V3_R1_ADMISSION=frame['path'],MODEL_V3_R1_ADMISSION_SHA=frame['sha256'],
            MODEL_V3_R1_GPU_UUID=gpu,MODEL_V3_R1_NODE=node)
        argv=['sbatch','--parsable','--partition=all','--nodelist='+node,'--cpus-per-task=16','--time=02:00:00','--export=ALL',
            '--output='+str(control/'slurm_%j.log'),'--error='+str(control/'slurm_%j.log'),str(HERE/'run_R1_ABBA.sbatch')]
        attempt.update(status='SUBMISSION_INTENT_PERSISTED',argv=argv,admission=frame);write(attempt_path,attempt,fresh=False);intent=True
        with api.registry_lock(REG):
            registry=api.read(REG);m.need(registry[api.REGISTRY_KEY][rid]==registration,'PRE registration changed')
            m.need(time.monotonic()-start<=120,'Resource frame expired before sbatch')
            actual=command(argv,env=env);token=actual['stdout'].strip().split(';',1)[0]
            m.need(actual['returncode']==0 and re.fullmatch('[1-9][0-9]*',token),'Unconfirmed submission: retain intent, no retry')
            immutable=write(control/'GPU_submission_binding_actual_v1.json',dict(schema='model_v3_GPU_software_budget_actual_submission_binding_v1',status='SUBMITTED',job_id=token,
                actual_sbatch=actual,source_package=pins,bound_cohort=bound_case,admission=frame))
            api.put_registration(registry,dict(registration,status='SUBMITTED',job_id=token,actual_submission=immutable));write(REG,registry,fresh=False)
        attempt.update(status='SUBMITTED',job_id=token,actual_sbatch=actual,immutable_GPU_submission_binding=immutable)
        defaults={}
        for label,argv in (('scontrol',['scontrol','show','job','-o',token]),('sacct',['sacct','-X','-j',token,'-n','-P','-o','JobIDRaw,ReqMem,ReqTRES,AllocTRES'])):
            try:defaults[label]=command(argv,timeout=20)
            except Exception as error:defaults[label]=dict(argv=argv,exception=type(error).__name__,actual_default_unavailable=True)
        attempt['actual_Slurm_default_memory']=defaults;result=write(attempt_path,attempt,fresh=False)
        print(json.dumps(dict(status='SUBMITTED',job_id=token,receipt=result)))
    except BaseException as error:
        attempt.update(status='SUBMISSION_OUTCOME_UNKNOWN_DO_NOT_RETRY' if intent else 'FAILED_BEFORE_SBATCH_NO_AUTORETRY',failure=dict(type=type(error).__name__,message=str(error)))
        write(attempt_path,attempt,fresh=False);raise
if __name__=='__main__':main()