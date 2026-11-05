"""Explicit20k metadata reserve/inputs, then one separate Root GPU submission.

No action occurs on import; no payload/SDK/array read, model or training loop.
"""
from __future__ import annotations
import argparse,hashlib,json,os,re,socket,stat,subprocess,sys
from pathlib import Path
from native_admission import B,N,REGISTRY,LIMIT,binding,read_ref,bare,need,independent_root,storage_admission,load,whole_output_bytes
import panel_auto_resources as resource

HERE=Path(__file__).absolute().parent
BASE=N/'Native_S20000_seed0_fp32_dev9_auto_v1/panel'
RID='Native_S20000_seed0_fp32_dev9_auto_v1'
OLD_SPEC=N/'Native_S10000_seed0_fp32_dev9_v2/panel/control/launch_spec.public_method_bound_v1.json'
CLOSURE=N/'native_S_B20k_v3/slots/slot_021/management/ROOT_LONG_SEGMENT_CLOSURE.json'


def write(path,value,*,replace=False):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    need(len(raw)<=2<<20,'Small Root metadata cap')
    target=path.with_name(path.name+'.pending') if replace else path
    with target.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    if replace:os.replace(target,path)
    return binding(path)


def source_map():
    pins=read_ref(resource.verify_sources())
    rows=[binding(HERE/x['relative_path']) for x in pins['files']]+[binding(HERE/'source_pins.json')]
    rows += [bare(x) for x in read_ref(pins['dependencies'])['files']]
    return {row['path']:row['sha256'] for row in rows}


def root_only():
    need(os.getuid()==os.geteuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
        and not os.environ.get('SLURM_JOB_ID'),'Explicit Root login metadata action only')


def endpoint_metadata():
    closed=read_ref(binding(CLOSURE));member_ref=closed['member_result'];member=read_ref(member_ref)
    need(closed['status']=='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING' and closed['failure'] is None
        and closed['optimizer_updates']==member['optimizer_updates']==20000
        and member['seed']==0 and member['precision']=='fp32','Exact real closed20k seed0 FP32 endpoint required')
    marker_path=Path(closed['checkpoint_directory'])/'COMPLETE.json';marker_ref=binding(marker_path);marker=read_ref(marker_ref)
    payload=marker_path.parent/'payload.pt';before=payload.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_nlink==1
        and not any(path.is_symlink() for path in (payload,*payload.parents))
        and before.st_size==marker['payload_bytes'] and marker['optimizer_updates']==20000
        and marker['samples_consumed']==member['samples_consumed'], 'Closed marker/payload STAT identity differs')
    # Root never hashes/deserializes payload: actual CPU preparation does it.
    return dict(member_result=member_ref,completion=marker_ref,
        payload=dict(path=str(payload),bytes=before.st_size,sha256=marker['payload_sha256']),segment_closure=binding(CLOSURE))


def reserve_inputs(args):
    need(not BASE.exists(),'Fresh20k family required; do not overwrite/automatically retry')
    old=read_ref(binding(OLD_SPEC));native=endpoint_metadata();api=resource.policy()
    publication=binding(args.method_publication);need(publication['sha256']==args.method_publication_sha256,'Publication SHA differs')
    resource.verify_publication(publication);pins=resource.verify_sources()
    need(old['preregistration_sha']=='39cf4929299cd227a3c361183a4b26c8b1405900','Original panel preregistration differs')
    recorder=resource.Recorder()
    quota=resource.quota_reserve(recorder.capture(['quota','-v','-u','zixiao']))
    BASE.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with api.registry_lock(REGISTRY):
        registry=api.read(REGISTRY)
        need(RID not in registry['reservations'] and RID not in registry.get(api.REGISTRY_KEY,{}),'Fresh independent hold/registration required')
        amounts=[row['remaining_bytes'] for row in registry['reservations'].values()]
        need(all(type(value) is int and value>=0 for value in amounts)
            and quota['reserve_bytes']>=sum(amounts)+LIMIT+(64<<30),
            'Fresh quota must cover all registered remaining holds, new2GiB and64GiB reserve')
        need(not BASE.exists(),'Panel family appeared before explicit reservation')
        BASE.mkdir(mode=0o700);(BASE/'control').mkdir(mode=0o700)
        principal=write(BASE/'control/principal.json',dict(schema='model_v3_Root_one_job_output_reservation_v1',
            authority='ROOT_ACTUAL',uid=1278,filesystem='/dev/sda1',reservation_id=RID,phase=str(BASE),
            max_bytes=LIMIT,reserved_additional_bytes=LIMIT,initial_existing_bytes=0,scientific_acceptance=False,
            status='ROOT_RESERVED_FINITE_ONE_NATIVE_PANEL',source_package=pins))
        entry=dict(phase=str(BASE),principal=principal,principal_sha256=principal['sha256'],remaining_bytes=LIMIT)
        registry['reservations'][RID]=entry
        record=api.make_registration(registration_id=RID,node=resource.NODE,gpu_uuid=resource.GPU,
            software_budget_bytes=32<<30,rss_limit_bytes=28<<30,Root_source=binding(__file__),source_pins=pins,
            proof_refs=(publication,principal,native['segment_closure']))
        api.put_registration(registry,record)
        write(REGISTRY,registry,replace=True)
        hold=write(BASE/'control/Root_hold_actual_v1.json',dict(schema='model_v3_Root_independent_output_hold_v1',
            authority='ROOT_ACTUAL',registry_path=str(REGISTRY),reservation_id=RID,entry_snapshot=entry,principal=principal,
            reserved_additional_bytes=LIMIT,initial_output_root_was_absent=True,Native_principal_or_counters_changed=False,
            actual_quota=quota,quota_observation=recorder.rows[-1]))
    dependencies=read_ref(pins_read()['dependencies'])
    original544=next(bare(row) for row in dependencies['files'] if row['role']=='original544_spec')
    value=dict(schema='model_v3_native_S_dev_panel_prepare_inputs_v1',status='ROOT_REAL20K_METADATA_BOUND_CPU_PREPARATION_REQUIRED',
        bridge=old['bridge_validation'],native=native,output_base=str(BASE),run_id='Native_S20000_seed0_fp32_dev9_auto_v1',
        node=resource.NODE,gpu_uuid=resource.GPU,original544_spec=original544,
        storage=dict(registry_path=str(REGISTRY),reservation_id=RID,principal=principal),
        resource_guard_source=binding(HERE/'panel_auto_resources.py'),supervisor_source=old['supervisor_source'],
        identity_dependencies=old['identity_dependencies'],method_publication=publication,operations_source_pins=pins,
        Root_hold=hold,Root_payload_or_array_or_SDK_read=False)
    item=write(BASE/'control/CPU_PREPARE_INPUTS.json',value)
    print(json.dumps(dict(status='RESERVED_AND_METADATA_INPUTS_BOUND_NO_CPU_OR_GPU_SUBMISSION',inputs=item,
        software_registration=record,Root_payload_hashed=False)))


def pins_read():
    return read_ref(resource.verify_sources())


def verify_cpu(spec,args):
    receipt=read_ref(binding(BASE/'cpu_prepare/CPU_PREPARATION.json'));job=receipt['actual_job_id']
    need(job==args.cpu_job_id and receipt['status']=='CPU_PREPARED_FULL9_NATIVE20K_SOURCE_AND_PAYLOAD_CHECKS_COMPLETED'
        and receipt['prepared_spec']==binding(args.spec) and receipt['source_before']==receipt['source_after']
        and receipt['source_after']==source_map(),'Actual same-source CPU preparation required')
    sup=read_ref(binding(args.cpu_supervisor))
    need(str(sup['job_id'])==job and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
        and sup['remaining']==[] and sup['private_storage']['first_sampling_failure'] is None
        and sup['command']==receipt['actual_argv'],'Actual CPU supervisor/source command/cleanup required')
    need(sup['gpu_initialization_permitted'] is False and 0<sup['elapsed_seconds']<=900
        and type(sup['last_total_bytes']) is int and sup['last_total_bytes']<=LIMIT,'Original CPU wall/output cap closure required')
    dependencies=read_ref(pins_read()['dependencies'])['files']
    cpu_roles={'cpu_supervisor','cpu_runtime_monitor','cpu_identity_supervisor','cpu_private_runtime_storage'}
    expected={row['path']:row['sha256'] for row in dependencies if row['role'] in cpu_roles}
    need(len(expected)==4 and sup['sources_sha256']==expected,'Exact original four CPU supervision sources required')
    for path,sha in expected.items():need(binding(path)['sha256']==sha,'Actual CPU supervisor helpers changed')
    private=sup['private_storage']
    need(private['budget_bytes']==LIMIT and type(private['samples']) is int and private['samples']>0
        and type(private['sampled_max_bytes']) is int and 0<=private['sampled_max_bytes']<=LIMIT,
        'Actual original CPU private sampling budget required')
    parent_argv=receipt['actual_supervisor_argv']
    for flag,expected in (('--wall-seconds','900'),('--rss-limit-bytes',str(12<<30)),('--output-budget-bytes',str(LIMIT))):
        need(parent_argv.count(flag)==1 and parent_argv[parent_argv.index(flag)+1]==expected,'CPU resource declaration differs')
    recorder=resource.Recorder()
    text=recorder.capture(['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'])
    rows=[line.split('|') for line in text.splitlines() if line.strip()]
    need(len(rows)==1 and len(rows[0])==7 and rows[0][:4]==[job,'zixiao','COMPLETED','0:0']
        and rows[0][4].isdigit() and int(rows[0][4])>0 and rows[0][5].isdigit() and int(rows[0][5])>=16
        and re.fullmatch(r'compute-0-(?:2|[89]|1[0-9])',rows[0][6]), 'Fresh actual owned >=16CPU C0 preparation parent required')
    return dict(receipt=binding(BASE/'cpu_prepare/CPU_PREPARATION.json'),supervisor=binding(args.cpu_supervisor),actual_sacct=recorder.rows[-1])


def submit(args):
    need(args.attempt and re.fullmatch(r'attempt[0-9]{3}',args.attempt),'Fresh explicit attempt label required')
    spec_ref=binding(args.spec);spec=read_ref(spec_ref)
    need(Path(args.spec).parent==BASE/'cpu_prepare' and spec['output_base']==str(BASE)
        and spec['native_endpoint']['optimizer_updates']==20000 and spec['native_endpoint']['seed']==0
        and spec['native_endpoint']['precision']=='fp32' and spec['storage']['reservation_id']==RID,
        'Exact prepared20k panel specification required')
    resource.verify_sources();resource.verify_publication(spec['method_publication'])
    for path in (BASE/'control').glob('Root_submission_attempt*.json'):
        previous=read_ref(binding(path))
        need(previous['status']=='FAILED_BEFORE_SBATCH_NO_AUTORETRY','Existing submitted/ambiguous intent forbids replay')
    cpu=verify_cpu(spec,args);api=resource.policy()
    need(not (BASE/'evaluation').exists(),'Cold full-panel output required')
    cleared=sorted(key for key in os.environ if key.startswith('SBATCH_'))
    env={key:value for key,value in os.environ.items() if not key.startswith('SBATCH_')}
    source_script=Path(spec['prepared_sbatch']['path']);attempt_path=BASE/'control'/('Root_submission_'+args.attempt+'.json')
    need(not attempt_path.exists(),'Fresh attempt metadata required')
    attempt=dict(schema='native_S20000_panel_auto_Root_submission_v1',status='ADMISSION_STARTED',job_id=None,
        source_pins=resource.verify_sources(),spec=spec_ref,CPU_preparation=cpu,cleared_SBATCH_environment_keys=cleared,
        Slurm_memory_mode='automatic_default',software_memory_budget_bytes=32<<30,RSS_limit_bytes=28<<30,
        automatic_retry=False,method_publication=spec['method_publication'])
    write(attempt_path,attempt);intent=False
    try:
        frame=resource.capture_root(spec,BASE/'control')
        monitor=load(spec['runtime_monitor']['path'],'native20k_Root_original_census')
        descriptor=spec['storage'];snapshot=storage_admission(descriptor,BASE,quota_free_bytes=frame['quota']['reserve_bytes'],
            current_output_bytes=whole_output_bytes(BASE,monitor))
        need(frame['quota']['reserve_bytes']>=snapshot['remaining_registered_bytes']+(64<<30), 'All registered holds plus64GiB quota required')
        admission=write(BASE/'control'/('Root_admission_'+args.attempt+'.json'),dict(
            schema='model_v3_native_S_panel_Root_admission_v1',spec=spec_ref,Root_resources=frame,
            actual_sbatch=binding(source_script),storage=descriptor,storage_snapshot=snapshot,
            resource_guard_source=spec['Root_resource_guard_source'],authority='ROOT_ACTUAL_CAPTURE_NOT_WORKER_LIVE',no_submission=True))
        for name,value in dict(MODEL_V3_PANEL_SPEC=spec_ref['path'],MODEL_V3_PANEL_SPEC_SHA=spec_ref['sha256'],
            MODEL_V3_PANEL_ROOT_ADMISSION=admission['path'],MODEL_V3_PANEL_ROOT_ADMISSION_SHA=admission['sha256'],
            MODEL_V3_PANEL_GPU_UUID=resource.GPU,MODEL_V3_PANEL_OUTPUT_BASE=str(BASE),
            MODEL_V3_PANEL_REPOSITORY=spec['repository_root']).items():env[name]=value
        argv=['sbatch','--parsable','--partition=all','--nodelist='+resource.NODE,'--cpus-per-task=16','--time=01:00:00',
            '--output='+str(BASE/('slurm-'+args.attempt+'-%j.out')),'--error='+str(BASE/('slurm-'+args.attempt+'-%j.out')),str(source_script)]
        attempt.update(status='SUBMISSION_INTENT_PERSISTED',admission=admission,argv=argv)
        write(attempt_path,attempt,replace=True);intent=True
        with api.registry_lock(REGISTRY):
            registry=api.read(REGISTRY);record=registry[api.REGISTRY_KEY][RID]
            need(record['status']=='PRE_SUBMISSION' and record['job_id'] is None,'One unsubmitted software registration required')
            resource.verify_root_resources(frame,{'gpu_uuid':resource.GPU},spec=spec)
            done=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,env=env,timeout=45)
            actual=dict(argv=argv,returncode=done.returncode,stdout=done.stdout,stderr=done.stderr)
            token=done.stdout.strip().split(';',1)[0]
            need(done.returncode==0 and re.fullmatch('[1-9][0-9]*',token),'Unconfirmed sbatch; preserve intent and reconcile')
            bound=write(BASE/'control'/('GPU_submission_binding_'+args.attempt+'.json'),dict(
                schema='model_v3_GPU_software_budget_actual_submission_binding_v1',status='SUBMITTED',job_id=token,
                actual_sbatch=actual,source_pins=resource.verify_sources(),spec=spec_ref,admission=admission))
            updated=dict(record,status='SUBMITTED',job_id=token,actual_submission=bound)
            api.put_registration(registry,updated);write(REGISTRY,registry,replace=True)
        attempt.update(status='SUBMITTED',job_id=token,actual_sbatch=actual,immutable_GPU_submission_binding=bound)
        observations={}
        for role,command in (('scontrol',['scontrol','show','job','-o',token]),
            ('sacct',['sacct','-X','-j',token,'-n','-P','-o','JobIDRaw,ReqMem,ReqTRES,AllocTRES'])):
            try:
                row=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=20)
                observations[role]=dict(argv=command,returncode=row.returncode,stdout=row.stdout,stderr=row.stderr)
            except Exception as error:observations[role]=dict(argv=command,exception=type(error).__name__,actual_default_unavailable=True)
        attempt['actual_Slurm_default_memory']=observations;attempt['finite_physical_memory_guarantee_claimed']=False
        result=write(attempt_path,attempt,replace=True)
        print(json.dumps(dict(status='SUBMITTED',job_id=token,receipt=result)))
    except BaseException as error:
        attempt.update(status='SUBMISSION_OUTCOME_UNKNOWN_DO_NOT_RETRY' if intent else 'FAILED_BEFORE_SBATCH_NO_AUTORETRY',
            failure=dict(type=type(error).__name__,message=str(error)))
        write(attempt_path,attempt,replace=True);raise


def main():
    root_only();parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='mode',required=True)
    p=sub.add_parser('reserve-inputs');p.add_argument('--method-publication',type=Path,required=True)
    p.add_argument('--method-publication-sha256',required=True)
    p=sub.add_parser('submit');p.add_argument('--spec',type=Path,required=True);p.add_argument('--attempt',required=True)
    p.add_argument('--cpu-job-id',required=True);p.add_argument('--cpu-supervisor',type=Path,required=True)
    args=parser.parse_args();return reserve_inputs(args) if args.mode=='reserve-inputs' else submit(args)


if __name__=='__main__':main()
