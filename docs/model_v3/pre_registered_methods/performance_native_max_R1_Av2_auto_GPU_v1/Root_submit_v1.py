"""One explicit Root metadata admission/submission for the frozen native maximum-singleton R1 probe."""
import argparse,ast,csv,datetime,hashlib,importlib.util,json,os,pathlib,re,socket,stat,subprocess,time
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';O=B/'runs/model_v3_20261025'
W=B/'MFM_model_v3_A_acceptance_v2_candidate_v1';PKG=N/'performance_native_max_R1_Av2_auto_GPU_v1_source'
FAMILY=N/'performance_native_max_R1_Av2_auto_v1';CONTROL=FAMILY/'control';OUT=FAMILY/'child';RECORD=FAMILY/'supervisor.json'
NODE='compute-0-21';GPU='GPU-c35f2434-9137-9723-1af5-dc69b6295243';SOFTWARE=64<<30;RSS=56<<30;LIMIT=2147483648
GIT=O/'cpu_git_tools_v1/bin/git';SB=O/'run_native_S_max712_Av2_auto_R1_capacity_v1.sbatch';REG=N/'native_S_profile_registered_reservations_v6.json'
def need(value,message):
 if not value:raise ValueError(message)
def ref(path):
 path=pathlib.Path(path);s=path.lstat()
 need(stat.S_ISREG(s.st_mode) and s.st_uid==1278 and s.st_nlink==1 and s.st_size<=2<<20,'Small owned raw source/metadata required: '+str(path))
 raw=path.read_bytes();return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(path):return json.loads(pathlib.Path(path).read_bytes())
def write(path,value,fresh=True):
 raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();need(len(raw)<=2<<20,'Small control cap')
 if fresh:
  with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 else:
  tmp=path.with_name(path.name+'.pending');need(not tmp.exists(),'Fresh atomic update path')
  with tmp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
 return ref(path)
def command(argv,timeout=45,env=None):
 r=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout,env=env)
 need(len(r.stdout)+len(r.stderr)<=2<<20,'Bounded raw command output')
 return dict(argv=argv,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--method-publication',type=pathlib.Path,required=True)
parser.add_argument('--method-publication-sha256',required=True)
parser.add_argument('--current-r1-publication',type=pathlib.Path,required=True)
parser.add_argument('--current-r1-publication-sha256',required=True)
parser.add_argument('--driver-publication',type=pathlib.Path,required=True)
parser.add_argument('--driver-publication-sha256',required=True)
cli=parser.parse_args()
need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi' and not os.environ.get('SLURM_JOB_ID'),'Root login metadata only')
cleared_SBATCH_environment_keys=sorted(k for k in os.environ if k.startswith('SBATCH_'))
for task_scheduler_key in cleared_SBATCH_environment_keys:os.environ.pop(task_scheduler_key)

for task_git_args,expected in [(['rev-parse','HEAD'],'7ffe8a5557590b1481f4ca74073007f070dc6a50'),(['rev-parse','HEAD^{tree}'],'8f9530415034bdb885c1c765aee434797c70e7c7'),(['status','--porcelain=v1','--untracked-files=all'],'')]:
 r=command([str(GIT),'-C',str(W),*task_git_args]);need(r['returncode']==0 and r['stdout'].strip()==expected,'Exact clean tested W/code/tree required')
pins=ref(PKG/'source_pins.json');need(pins['sha256']=='ab150abc1bcc255c2a9640f8013f610dedf728fe23eea8aaa56dbff92e463533','Frozen source package differs')
for item in read(PKG/'source_pins.json')['files']:
 actual=ref(item['path']);need(all(actual[k]==item[k] for k in actual),'Frozen package leaf drift')
need(ref(SB)['sha256']==ref(PKG/'run_native_max_R1.sbatch')['sha256'],'Installed thin SB must be byte-identical')
# Reuse the actual current seven-blob R1 admission, not old9e/4580/pack3705 gates.
deps=read(PKG/'dependencies.json')
for item in deps['raw_refs'].values():need(ref(item['path'])==item,'Current maximum-probe dependency rawref drift')
admission_ref=deps['raw_refs']['current_R1_admission_source']
need(admission_ref['path']==str(N/'performance_current_Av2_R1_ABBA_v1_source/admission.py')
     and admission_ref['sha256']=='0753c530dfb980747501c5a8b8aa59e39250d77c94d7bbfb7b18c3694f100a30',
     'Exact current R1 admission source required')
spec=importlib.util.spec_from_file_location('native_max_current_R1_original_admission',admission_ref['path'])
need(spec is not None and spec.loader is not None,'Current admission loader missing')
admission=importlib.util.module_from_spec(spec);spec.loader.exec_module(admission)
r1_pins=deps['raw_refs']['current_R1_source_pins']
need(r1_pins['sha256']=='7a7544310828af89ef2f75446bbee3f74e029b5a4676797b30ff1bcef2866ba5'
     and admission.verify_package(r1_pins['sha256'])==r1_pins,'Exact current R1 seven-leaf package required')
current_R1_publication_ref=ref(cli.current_r1_publication.absolute())
need(current_R1_publication_ref['sha256']==cli.current_r1_publication_sha256,'Current R1 publication rawSHA differs')
current_R1_publication=admission.verify_method(current_R1_publication_ref)
need(current_R1_publication['public_code_sha']=='7f790e9363a5f7ec4b10d475bbabdb2e6969bd5d',
     'Exact actual current R1 public seven blobs required')
SDK_ref=deps['raw_refs']['head_off_SDK_qualification']
need(SDK_ref['sha256']=='d430d86fe2378ef5f3cee4e726919b9ec98d2180147b17b3efc6ca87359c4841',
     'Exact actual HeadOff4722 full native audit/selective-sync closure required')
qualification=admission.qualify('head_off',SDK_ref)
qualified_configuration=qualification['configuration'];qualified_case=qualification['case']
need(qualified_case['numeric_job_id']=='4524722' and qualified_configuration['code_sha']==admission.CODE
     and admission.CODE=='7ffe8a5557590b1481f4ca74073007f070dc6a50'
     and admission.TREE=='8f9530415034bdb885c1c765aee434797c70e7c7'
     and admission.W==W,'Actual current4722/full115 source qualification differs')
full_ref=deps['raw_refs']['full_CPU_Root_closure'];full=read(full_ref['path'])
need(full_ref['sha256']=='2e1355acd9776443eb0ab2bf2eb0d8e4a212951f0e1bf57dd2c0637465f8403f'
     and full['job_id']=='4524695' and full['code_commit']==admission.CODE
     and full['test_file_count']==115 and full['all_runtime_before_after_and_current_verified'] is True,
     'Exact actual current full115 CPU4695 closure required; original guard verifies full scope')
candidate=read(deps['raw_refs']['candidate_options']['path'])
need(candidate==qualified_configuration['candidate'] and candidate['precision']=='fp32'
     and candidate['distance_checkpointing'] is True and candidate['backbone_checkpointing'] is True
     and candidate['head_checkpointing'] is False,'Exact current head-off candidate only')
execution=read(deps['raw_refs']['manual_execution']['path'])
need(execution['checkpoint_policy']=='manual' and execution.get('padding') is None,
     'Unmodified manual head-off singleton layout, not A5/automatic capacity consumption')
counts=read(deps['raw_refs']['counts_Root_closure']['path'])
need(counts['counts_before_after_raw_and_source_match'] is True
     and counts['global_counts']['records']==11104772 and counts['global_counts']['max_native_atoms']==712
     and counts['global_counts']['maximum_singleton_padded_cost']==1520832,
     'Actual signed full TRAIN count authority required; child selects and decodes maximum itself')
OPUB=cli.method_publication.absolute();operation_ref=ref(OPUB)
need(operation_ref['sha256']==cli.method_publication_sha256,'Actual operations publication rawSHA differs')
operations=read(OPUB)
need(operations['schema']=='model_v3_exact_tree_publication_actual_v1'
     and operations['repository_full_name']=='mint258/MFM' and operations['branch']=='model-v3'
     and operations['public_branch_readback_verified'] is True
     and operations['public_Git_API_tree_readback_verified'] is True
     and all(isinstance(operations[key],str) and re.fullmatch('[0-9a-f]{40}',operations[key])
             for key in ('local_code_sha','public_code_sha','tree_sha')),
     'Actual generic exact-tree/readback operations publication required')
published={row['path']:row for row in operations['files']}
need(len(published)==len(operations['files']),'Duplicate published paths')
prefix='docs/model_v3/pre_registered_methods/performance_native_max_R1_Av2_auto_GPU_v1/'
operation_files={name:PKG/name for name in ('native_max_input.py','run_native_max_R1.py','run_native_max_R1.sbatch','dependencies.json','README.md','source_pins.json')}
for name,path in operation_files.items():
 raw=path.read_bytes();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+bytes([0])+raw).hexdigest()
 item=published[prefix+name]
 need(item['type']=='blob' and item['sha']==blob,'Current maximum probe operation source not exact published Git blob: '+name)
# New automatic six-leaf method and Root driver require one actual exact-tree
# receipt; unchanged fixed six-leaf9545 provenance is separately source-bound.
driver_publication_ref=ref(cli.driver_publication.absolute())
need(driver_publication_ref['sha256']==cli.driver_publication_sha256,'New Root-driver publication rawSHA differs')
driver_publication=read(driver_publication_ref['path'])
need(driver_publication['schema']=='model_v3_exact_tree_publication_actual_v1'
     and driver_publication['repository_full_name']=='mint258/MFM' and driver_publication['branch']=='model-v3'
     and driver_publication['public_branch_readback_verified'] is True
     and driver_publication['public_Git_API_tree_readback_verified'] is True
     and all(isinstance(driver_publication[key],str) and re.fullmatch('[0-9a-f]{40}',driver_publication[key])
             for key in ('local_code_sha','public_code_sha','tree_sha')),
     'Actual new exact-tree/readback publication of the Root driver required')
driver_published={row['path']:row for row in driver_publication['files']}
need(len(driver_published)==len(driver_publication['files']),'Duplicate new Root-driver publication paths')
driver_operation_files={**operation_files,'Root_submit_v1.py':pathlib.Path(__file__).absolute()}
for name,path in driver_operation_files.items():
 raw=path.read_bytes();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+bytes([0])+raw).hexdigest()
 item=driver_published[prefix+name]
 need(item['type']=='blob' and item['sha']==blob,'New exact seven-blob publication differs: '+name)
need(driver_publication_ref==operation_ref,'One actual new auto6+driver7+shared5 exact-tree receipt required')
prior_pub=read(deps['raw_refs']['preserved_fixed_six_publication']['path'])
need(deps['raw_refs']['preserved_fixed_six_source_pins']['sha256']=='2f695298b85878cbab79a86ac7d81586ead18a215607893141f2124fcf06aa51'
     and deps['raw_refs']['preserved_fixed_Root_driver']['sha256']=='a0de15aa0d1af4870d0c0713a081770ac6752c62bc9e80c76021b0cf2b0fcf94'
     and prior_pub['schema']=='model_v3_exact_tree_publication_actual_v1'
     and prior_pub['public_code_sha']=='9545fceae1ee3e4cb43bfc36324574fa05c1042d'
     and prior_pub['public_branch_readback_verified'] is True and prior_pub['public_Git_API_tree_readback_verified'] is True,
     'Frozen original fixed six-leaf/source/Root publication provenance differs')
policy_ref=deps['raw_refs']['GPU_auto_memory_policy_source']
spec=importlib.util.spec_from_file_location('native_max_auto_shared_memory_policy',policy_ref['path'])
memory_policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(memory_policy)
need(memory_policy.verify_package('cbb3d620f90768272abb2e135a11e928a861a896e9c51c80b5bea82ec6eca245')==
     deps['raw_refs']['GPU_auto_memory_policy_pins'],'Exact sole shared auto memory policy required')
memory_policy.verify_publication(operation_ref)
with admission.registry_lock(REG):
    need(not FAMILY.exists() and not OUT.exists() and not RECORD.exists(),'Fresh single-use current maximum R1 family required')
    CONTROL.mkdir(parents=True,mode=0o700)
    registry=read(REG);before=ref(REG);need('performance_native_max_R1_Av2_auto_v1' not in registry['reservations'],'No duplicate hold')
    write(CONTROL/'registry_before.json',registry)
    principal=dict(schema='model_v3_Root_one_job_output_reservation_v1',authority='ROOT_ACTUAL',uid=1278,filesystem='/dev/sda1',
    reservation_id='performance_native_max_R1_Av2_auto_v1',phase=str(FAMILY),max_bytes=LIMIT,reserved_additional_bytes=LIMIT,
    initial_existing_bytes=0,status='ROOT_RESERVED_FINITE_SINGLE_GPU_TASK',scientific_acceptance=False,source_package=pins)
    pr=write(CONTROL/'principal.json',principal)
    entry=dict(phase=str(FAMILY),principal=pr,principal_sha256=pr['sha256'],remaining_bytes=LIMIT)
    registry['reservations']['performance_native_max_R1_Av2_auto_v1']=entry
    gpu_registration=memory_policy.make_registration(registration_id='performance_native_max_R1_Av2_auto_v1',node=NODE,gpu_uuid=GPU,
     software_budget_bytes=SOFTWARE,rss_limit_bytes=RSS,Root_source=ref(__file__),source_pins=pins,proof_refs=(operation_ref,pr))
    memory_policy.put_registration(registry,gpu_registration)
    need(ref(REG)==before,'Live registry changed before addition')
    write(REG,registry,fresh=False)
    hold=write(CONTROL/'Root_hold_actual_v1.json',dict(schema='model_v3_Root_independent_output_hold_v1',authority='ROOT_ACTUAL',registry_path=str(REG),
    reservation_id='performance_native_max_R1_Av2_auto_v1',entry_snapshot=entry,principal=pr,reserved_additional_bytes=LIMIT,
    Native_S_principal_or_counters_changed=False,physical_allocation_of_2GiB_file_claimed=False,original_registry_before=ref(CONTROL/'registry_before.json')))
attempt_path=CONTROL/'Root_submission_actual_v1.json'
attempt=dict(schema='model_v3_native_max_R1_Root_single_submission_v1',status='ADMISSION_STARTED',job_id=None,source_package=pins,installed_sbatch=ref(SB),
Root_driver=ref(__file__),operations_publication=ref(OPUB),hold=hold,observations=[],GPU_GRES_isolation_claimed=False,automatic_retry=False)
attempt.update(current_R1_publication=current_R1_publication_ref,driver_publication=driver_publication_ref,
 qualified_current_head_off_numeric=deps['raw_refs']['head_off_R2_qualification'],qualified_current_head_off_SDK=SDK_ref,
 current_full115_CPU=full_ref,current_R1_package=r1_pins,cleared_SBATCH_environment_keys=cleared_SBATCH_environment_keys,
 registry_mutation_and_quota_snapshot_protected_by_original_current_R1_registry_lock=True,
 prior_numeric_or_SDK_qualification_is_not_new_maximum_capacity_evidence=True,
 GPU_software_registration=gpu_registration,Slurm_memory_mode='automatic_default',Slurm_requested_memory_MiB=None,
 software_memory_budget_bytes=SOFTWARE,RSS_limit_bytes=RSS)
write(attempt_path,attempt)
intent=False
def capture(argv,timeout=45):
 r=command(argv,timeout);attempt['observations'].append(r);write(attempt_path,attempt,fresh=False)
 need(r['returncode']==0,'Actual observation failed: '+str(argv));return r['stdout']
ssh=['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(O/'compute21_known_hosts_v1'),NODE]
try:
 start=time.monotonic()
 raw=capture(['scontrol','show','node',NODE]);v=dict(re.findall(r'(CPUAlloc|CPUTot|RealMemory|AllocMem)=(\d+)',raw))
 need(len(v)==4 and int(v['CPUTot'])-int(v['CPUAlloc'])>=16 and not any(x in raw for x in ['State=DOWN','DRAIN','FAIL']),'No actual CPU/node headroom')
 queue_raw=capture(['squeue','-h','-w',NODE,'-o','%i|%u|%t|%m|%C'])
 mem_raw=capture(ssh+['head -n 5 /proc/meminfo'])
 memory=memory_policy.assess(raw,queue_raw,mem_raw,node=NODE,software_budget_bytes=SOFTWARE,rss_limit_bytes=RSS,
  registry_path=REG,current_reservation_id='performance_native_max_R1_Av2_auto_v1')
 available=memory['MemAvailable_MiB']
 qraw=capture(['quota','-v','-u','zixiao']);rows=[x.split() for x in qraw.splitlines() if x.split() and x.split()[0]=='/dev/sda1']
 need(len(rows)==1,'Actual quota row absent');used,soft,hard=[int(rows[0][x].rstrip('*')) for x in (1,2,3)]
 limits=[x for x in [soft,hard] if x>0];need(limits,'Quota limit unknown');free=(min(limits)-used)*1024
 with admission.registry_lock(REG):
  live=read(REG);need(live['reservations']['performance_native_max_R1_Av2_auto_v1']==entry,'Independent hold changed')
  need(all(type(x['remaining_bytes']) is int and x['remaining_bytes']>=0 for x in live['reservations'].values()),'Unknown holds')
  remaining=sum(x['remaining_bytes'] for x in live['reservations'].values())
 need(free>=remaining+64*1024**3,'Quota must cover every registered hold plus64GiB reserve')
 quota=write(CONTROL/'Root_quota_actual_v1.json',dict(schema='model_v3_Root_actual_quota_observation_v1',authority='ROOT_ACTUAL',
captured_unix=time.time(),raw_quota=qraw,used_KiB=used,soft_KiB=soft,hard_KiB=hard,available_bytes=free,
remaining_all_registered_bytes=remaining,additional_reserve_bytes=64*1024**3,hold=hold))
 gpu_raw=capture(ssh+['nvidia-smi --query-gpu=uuid,name,driver_version,memory.total,memory.free,memory.used --format=csv,noheader,nounits'])
 selected=[x for x in csv.reader(gpu_raw.splitlines(),skipinitialspace=True) if x and x[0].strip()==GPU]
 need(len(selected)==1 and len(selected[0])==6 and '5090' in selected[0][1],'Exact selected5090 missing')
 gpu=selected[0];need(int(gpu[3])>0 and 0<int(gpu[4])<=int(gpu[3]) and 0<=int(gpu[5])<=int(gpu[3]),'GPU memory fields unknown/invalid; no capacity admission')
 apps_raw=capture(ssh+['nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader,nounits'])
 for row in csv.reader(apps_raw.splitlines(),skipinitialspace=True):
  if not row or row==['No running processes found']:continue
  need(len(row)==4 and row[0].startswith('GPU-') and row[1].strip().isdigit(),'Unknown NVML compute-process observation')
  need(row[0].strip()!=GPU,'Selected GPU occupied; never signal foreign processes')
 lock=B/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(GPU+'.lock')
 capture(ssh+['flock -n '+str(lock)+' true'])
 need(time.monotonic()-start<=120,'Fresh Root resource frame expired')
 frame=write(CONTROL/'Root_admission_actual_v1.json',dict(schema='model_v3_native_max_R1_Root_actual_admission_v1',authority='ROOT_ACTUAL',
captured_unix=time.time(),node=NODE,gpu_uuid=GPU,cpus=16,requested_memory_MiB=None,Slurm_memory_mode='automatic_default',
software_memory_budget_bytes=SOFTWARE,RSS_limit_bytes=RSS,memory_policy_assessment=memory,
observed_AllocMem_MiB=int(v['AllocMem']),RealMemory_MiB=int(v['RealMemory']),
MemAvailable_MiB=available,selected_GPU_fields=gpu,selected_compute_processes=[],quota=quota,hold=hold,
resources_raw_observations=attempt['observations'],UUID_lock_checked_and_released=True,GPU_GRES_isolation_claimed=False,
worker_must_revalidate_actual_UUID_foreign_processes_and_caps=True,freshness_seconds=time.monotonic()-start))
 env={**{k:v for k,v in os.environ.items() if not k.startswith('SBATCH_')},'MODEL_V3_GPU_UUID':GPU,'MODEL_V3_EXPECTED_NODE':NODE,'MODEL_V3_OUT':str(OUT),'MODEL_V3_RECORD':str(RECORD),
'MODEL_V3_PACKAGE_PINS_SHA256':pins['sha256']}
 for name,r in [('MODEL_V3_ROOT_ADMISSION',frame),('MODEL_V3_QUOTA',quota),('MODEL_V3_HOLD',hold),('MODEL_V3_METHOD_PUBLICATION',operation_ref),('MODEL_V3_CURRENT_AV2_R1_PUBLICATION',current_R1_publication_ref),('MODEL_V3_ROOT_DRIVER_PUBLICATION',driver_publication_ref)]:
  env[name+'_PATH']=r['path'];env[name+'_SHA256']=r['sha256']
 argv=['sbatch','--parsable','--partition=all','--nodelist='+NODE,'--cpus-per-task=16','--time=02:00:00',
'--output='+str(CONTROL/'slurm_%j.log'),str(SB)]
 attempt.update(status='SUBMISSION_INTENT_PERSISTED',admission=frame,quota=quota,bindings={k:env[k] for k in env if k.startswith('MODEL_V3_')},argv=argv)
 write(attempt_path,attempt,fresh=False);intent=True
 need(time.monotonic()-start<=120,'Resource frame became stale before sbatch')
 with admission.registry_lock(REG):
  current_registry=read(REG)
  need(current_registry.get(memory_policy.REGISTRY_KEY,{}).get('performance_native_max_R1_Av2_auto_v1')==gpu_registration,
       'Software intent changed before one actual submission')
  need(time.monotonic()-start<=120,'Fresh resource frame expired waiting for original mutex')
  r=command(argv,45,env);attempt['observations'].append(r)
  m=re.fullmatch(r'(\d+)(?:;[A-Za-z0-9_.-]+)?',r['stdout'].strip())
  need(r['returncode']==0 and m is not None,'Unconfirmed sbatch outcome; inspect before retry')
  binding=write(CONTROL/'GPU_submission_binding_actual_v1.json',dict(
   schema='model_v3_GPU_software_budget_actual_submission_binding_v1',status='SUBMITTED',job_id=m[1],
   actual_sbatch=r,Root_source=ref(__file__),source_package=pins,operations_publication=operation_ref,
   software_memory_budget_bytes=SOFTWARE,RSS_limit_bytes=RSS,Slurm_memory_mode='automatic_default',
   fixed_Slurm_memory_requested_bytes=None,finite_physical_guarantee_claimed=False,
   captured_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat()))
  submitted_registration=memory_policy.make_registration(**{key:value for key,value in gpu_registration.items()
   if key not in ('schema','authority','uid','user','status','job_id','actual_submission')},
   status='SUBMITTED',job_id=m[1],actual_submission=binding)
  memory_policy.put_registration(current_registry,submitted_registration)
  write(REG,current_registry,fresh=False)
 # The exact actual binding is immutable. Observation latency does not hold the
 # registry mutex or consume the original worker source-only30s lock wait.
 defaults={}
 for label,observation_argv in (
  ('scontrol',['scontrol','show','job','-o',m[1]]),
  ('sacct',['sacct','-X','-j',m[1],'-n','-P','-o','JobIDRaw,ReqMem,ReqTRES,AllocTRES'])):
  try: observation=command(observation_argv,30)
  except Exception as error:
   observation=dict(argv=observation_argv,exception=type(error).__name__,message=str(error),actual_default_not_available=True)
  defaults[label]=observation;attempt['observations'].append(observation)
 attempt.update(status='SUBMITTED',job_id=m[1],finished_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
  immutable_GPU_submission_binding=binding,actual_Slurm_default_memory=defaults,
  finite_physical_memory_guarantee_claimed=False)
 write(attempt_path,attempt,fresh=False)
 print(json.dumps(dict(status='SUBMITTED',job_id=m[1],receipt=ref(attempt_path),family=str(FAMILY),gpu_uuid=GPU,resource_freshness_seconds=time.monotonic()-start)),flush=True)
except Exception as e:
 attempt.update(status='SUBMISSION_OUTCOME_UNKNOWN_DO_NOT_RETRY' if intent else 'FAILED_BEFORE_SBATCH_NO_AUTORETRY',exception=type(e).__name__,message=str(e))
 write(attempt_path,attempt,fresh=False);raise
