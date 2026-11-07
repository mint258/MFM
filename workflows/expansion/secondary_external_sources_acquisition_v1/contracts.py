"""Exact Alpha profile/full acquisition contract, without future data pins."""
import csv,hashlib,io,os,socket,sys,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as q

ROOT=q.ROOT;UID=1264;KEY='moleculenet_missing11_acquisition_alpha_v1'
MODULE='secondary_external_sources_acquisition_v1.run'
STAGE='OFFICIAL_MOLECULENET11_DOWNLOAD_AND_CONTAINER_INVENTORY'
IDS=('hiv','muv','pcba','sider','tox21','toxcast','qm7b_mat','qm8_sdf','pdbbind_general','pdbbind_refined','pdbbind_core')
FILENAMES=('HIV.csv','muv.csv.gz','pcba.csv.gz','sider.csv.gz','tox21.csv.gz','toxcast_data.csv.gz','qm7b.mat','gdb8.tar.gz',
 'pdbbindv2019/pdbbind_v2019_other_PL.tar.gz','pdbbindv2019/pdbbind_v2019_refined.tar.gz','pdbbind_v2013_core_set.tar.gz')
SIZES=(2193844,1755511,15449358,34759,122925,404948,16067096,8764619,1759178739,651882567,45317121)
URLS=dict(zip(IDS,('https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/'+x for x in FILENAMES)))
need=q.need;pin=q.ref;load=q.load;verify=q.verify;literal=q.literal

def parameters(mode):
    need(mode in ('profile','full'),'EXACT_ACQUISITION_MODE_REQUIRED')
    return {'mode':mode,'catalog_sources':list(IDS),'download_source_ids':['sider'] if mode=='profile' else [x for x in IDS if x!='sider'],
      'reuse_profile_sider_without_GET':mode=='full','maximum_concurrent_GETs':16,'GET_attempts_per_source':1,
      'conditional_ETag_and_LastModified':True,'normal_proxy_environment_inherited':True,'network_configuration_changed':False,
      'alternate_domains_or_mirrors':False,'extract_archive_members':False,'chemical_normalization':False,
      'maximum_inventory_record_bytes':4096,'maximum_expanded_bytes_per_source':256*1024**3,
      'container_buffer_bytes':1024**2,'MAT_variable_arrays_inspected':False,'identity_coverage_accepted':False,
      'algorithm_RSS_reference_bytes':48*1024**3,'runtime_MemAvailable_min_fraction':.15,'cost_overrun_action':'REPORT_AND_CONTINUE'}

def frame(s):return {'device':s.st_dev,'inode':s.st_ino,'size':s.st_size,'mtime_ns':s.st_mtime_ns,'uid':s.st_uid}

def write_new(path,value):
    import json
    raw=(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
    need(len(raw)<=2*1024**2,'SMALL_METADATA_RECEIPT_REQUIRED')
    with Path(path).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())

def actual_account(ref,job):
    account=q.load_ref(ref);parent=account['actual_parent']
    need(account['query_returncode']==0 and account['endpoint']==q.ENDPOINT and account['uid']==UID and
      parent['JobIDRaw']==str(job) and parent['State']=='COMPLETED' and parent['ExitCode']=='0:0' and
      parent['UID']==str(UID) and parent['AllocCPUS']=='16','ACTUAL_ALPHA_C0_PARENT_REQUIRED')
    rows=list(csv.DictReader(io.StringIO(q.read_small(q.verify(account['raw_sacct_reference'])).decode()),delimiter='|'))
    selected=[x for x in rows if x.get('JobIDRaw')==str(job)]
    need(len(selected)==1 and all(selected[0][k]==parent[k] for k in ('State','ExitCode','UID','ElapsedRaw','AllocCPUS','NodeList','Partition'))
      and account['allocated_core_seconds_observed']==int(parent['ElapsedRaw'])*16,'ACTUAL_RAW_PARENT_COST_REQUIRED')
    return account

def startup(plan_path,proof_path,primary):
    plan=load(plan_path);proof=load(proof_path);review=q.load_ref(plan['root_review_reference']);mode=plan['mode'];pilot=mode=='profile'
    cap=64*1024**2 if pilot else 16*1024**3;wall=plan['wall_seconds'];source=ROOT/'code/secondary_external_sources_acquisition_v1/run.py'
    argv=[plan['python'],'-B','-m',MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    need(plan.get('schema')=='SECONDARY_EXTERNAL_SOURCE_ACQUISITION_PLAN_V1' and plan.get('producer_key')==plan.get('scope_key')==KEY and
      plan.get('stage')==STAGE+('_PROFILE' if pilot else '_FULL') and plan.get('mode') in ('profile','full') and plan.get('pilot') is pilot and
      plan.get('scope_parameters')==parameters(mode) and plan.get('endpoint')==q.ENDPOINT and plan.get('uid')==UID and
      plan.get('run_root')==str(ROOT) and plan.get('node') in q.NODES and plan.get('cpus')==16 and
      plan.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED' and type(wall) is int and 0<wall<=(3600 if pilot else 172800) and wall%60==0 and
      plan.get('output_cap_bytes')==cap,'EXACT_OFFICIAL_ACQUISITION_PHASE_PLAN_REQUIRED')
    need(Path(primary).absolute()==source==Path(sys.modules['__main__'].__file__).absolute() and
      Path(sys.executable).absolute()==Path(plan['python']).absolute() and sys.argv==[str(source),*argv[4:]] and
      plan['execution_argv']==argv and plan['startup_proof_path']==str(proof_path),'ACTUAL_MAIN_AND_ALL_ARGV_REQUIRED')
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and
      review.get('reviewer')=='root','EXACT_ROOT_PHASE_REVIEW_REQUIRED')
    for k in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot','wall_seconds',
      'output_cap_bytes','execution_argv','data_references','parent_evidence_references'):need(plan[k]==review[k],'ROOT_SCOPE_DIFFERS:'+k)
    need(plan['source_references']==review['approved_source_references'],'EXACT_REVIEWED_SOURCE_SET')
    need(proof.get('schema')=='SECONDARY_EXTERNAL_SOURCE_ACQUISITION_STARTUP_V1' and proof.get('endpoint')==q.ENDPOINT and
      proof.get('uid')==os.getuid()==UID and proof['node']==plan['node']==socket.gethostname().split('.')[0] and
      proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and 0<=time.time()-proof['observed_unix_seconds']<=120 and
      proof['plan_reference']==pin(plan_path) and proof['root_review_reference']==plan['root_review_reference'],'ACTUAL_FRESH_ALPHA_PHASE_PROOF')
    need(proof['request']=={'kind':'analysis','pilot':pilot,'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','wall_seconds':wall,'execution_argv':argv}
      and proof['memory_limits_requested'] is False and proof['exclusive_requested'] is False
      and proof.get('bounded_source_acquisition_scope_only') is True and proof.get('bounded_readonly_scope_only') is False,
      'EXACT_DEFAULT_MEMORY_ACQUISITION_NOT_READONLY_REQUEST_PROOF')
    env=os.environ
    need(env.get('SLURM_JOB_ID')==str(proof['job_id']) and env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('SLURM_CPUS_PER_TASK')=='16' and
      env.get('CUDA_VISIBLE_DEVICES')=='' and all(env.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'REAL_CPU16_LIBRARY_THREADS_REQUIRED')
    declared={r['path']:{k:r[k] for k in ('path','bytes','sha256')} for r in proof['source_target_verification']}
    for ref in [*plan['source_references'],*plan['parent_evidence_references'],plan['root_review_reference'],pin(plan_path)]:
        need(declared.get(ref['path'])==ref,'ACTUAL_APPROVED_TARGET_MISSING');q.verify(ref)
    for path in [*source.parent.glob('*.py'),Path(q.__file__),Path(q.__file__).parent/'__init__.py']:
        need(pin(path) in plan['source_references'],'EXACT_IMPORTED_NEW_AND_BASE_CODE_REQUIRED')
    origin=proof['controller_evidence'];need(origin['endpoint']==q.ENDPOINT and origin['uid']==UID and origin['hostname']=='sonmi' and
      origin['proof_is_not_created_by_scientific_worker'] is True and origin['actual_script_reference']==proof['script_reference'],'ACTUAL_ALPHA_LOGIN_SIGNER')
    for line in q.read_small(q.verify(proof['script_reference'])).decode().splitlines():
        if line.strip().startswith('#SBATCH'):need(not any(x in line for x in ('--mem','--exclusive','--gres','--gpu')),'NO_MEMORY_EXCLUSIVE_GPU_DIRECTIVE')
    job=q.fields(proof['job_metadata']);need(job.get('JobId')==str(proof['job_id']) and job.get('UserId')=='alpha(1264)' and
      job.get('JobState')=='RUNNING' and job.get('NodeList')==plan['node'] and job.get('Partition')=='cpu' and job.get('NumCPUs')=='16' and
      job.get('NumTasks')=='1' and job.get('Requeue')=='0' and job.get('Command')==proof['script_reference']['path'] and
      q.duration(job.get('TimeLimit',''))==wall,'ACTUAL_OWN_SCRIPT_JOB_AND_WALL')
    gate=proof['actual_gate_process'];tail=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    need(gate['pid']==os.getpid() and gate['uid']==UID and gate['start_ticks']==int(tail[19]) and gate['pgid']==os.getpgrp() and gate['sid']==os.getsid(0)
      and gate['cgroup_sha256']==hashlib.sha256(Path('/proc/self/cgroup').read_bytes()).hexdigest(),'SAME_ATTESTED_EXEC_GATE_PROCESS')
    storage=proof['storage_observation'];q.load_ref(proof['storage_observation_reference'])
    need(proof['account_free_bytes']==storage['effective_free_bytes'] and proof['account_free_bytes']-cap>=200000000000 and
      storage['whole_output_caps_reserved_bytes']>=cap and 0<=time.time()-storage['observed_unix_seconds']<=120,'FRESH_ALL_CAPS200GB_STORAGE')
    for key in ('resource_authority_reference','cost_decision_reference','locator_catalog_reference','head_receipt_reference'):
        need(plan[key] in plan['source_references'],'SMALL_PHASE_AUTHORITY_NOT_APPROVED:'+key)
    authority=q.load_ref(plan['resource_authority_reference']);need(authority.get('schema')=='USER_AUTHORIZED_SECONDARY_DATA_CLUSTER_V1' and
      authority.get('status')=='USER_AUTHORIZED' and authority.get('endpoint')==q.ENDPOINT and authority.get('observed_uid')==UID and
      authority.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED','REAL_ALPHA_USER_AUTHORITY')
    cost=q.load_ref(plan['cost_decision_reference']);need(cost.get('schema')=='USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1' and
      cost.get('status')=='USER_AUTHORIZED' and cost.get('on_overrun')=='REPORT_AND_CONTINUE' and cost.get('scientific_quality_thresholds_unchanged') is True,'REAL_COST_CONTINUE_AUTHORITY')
    catalog=q.load_ref(plan['locator_catalog_reference']);need(catalog['schema']=='MOLECULENET_MISSING11_ACTUAL_HEAD_LOCATORS_V1' and
      catalog['head_job_id']=='4521094' and catalog['physical_file_count']==11 and catalog['total_expected_compressed_bytes']==2501171487,'EXACT_ACTUAL1094_CATALOG')
    head=q.load_ref(plan['head_receipt_reference']);need(head['job_id']=='4521094' and head['status']=='HEAD_OBSERVATIONS_COMPLETE_ALL_SOURCE_COVERAGE_PENDING' and
      plan['head_receipt_reference']['sha256']==catalog['head_receipt_reference']['sha256'],'ACTUAL1094_RECEIPT_COPY')
    rows={x['source_id']:x for x in catalog['entries']};need(set(rows)==set(IDS) and len(rows)==len(catalog['entries']),'EXACT_ELEVEN_NO_EXTRA_SOURCE_IDS')
    copies=plan['head_observation_references'];need(len(copies)==11 and {x['source_id'] for x in copies}==set(IDS),'ELEVEN_SMALL_HEAD_COPIES')
    for id,size in zip(IDS,SIZES):
        row=rows[id];need(row['url']==URLS[id] and row['expected_compressed_bytes']==size and row['head_http_status']==200,'FROZEN_URL_LENGTH_REQUIRED')
        kind='MAT' if id=='qm7b_mat' else 'TAR_GZIP' if id=='qm8_sdf' or id.startswith('pdbbind_') else 'CSV_BYTES' if id=='hiv' else 'GZIP_CSV_BYTES'
        need(row['container']==kind,'EXACT_SOURCE_CONTAINER_KERNEL_REQUIRED')
        ref=next(x['reference'] for x in copies if x['source_id']==id);need(ref in plan['source_references'] and
          all(ref[k]==row['head_reference'][k] for k in ('bytes','sha256')),'EXACT_HEAD_COPY_PIN')
        observation=q.load_ref(ref);block=observation['redirect_chain'][-1]['http_blocks'][-1]
        need(observation['http_status']==200 and observation['candidate']['url']==observation['final_url']['url']==row['url'] and
          block['content_length_bytes']==size and block['headers']['etag'][0]['value']==row['expected_etag'] and
          block['headers']['last-modified'][0]['value']==row['expected_last_modified'],'FROZEN_HEAD_SEMANTICS_DIFFER')
    prior=None
    if pilot:need(plan['data_references']==[],'PROFILE_DOWNLOAD_HAS_NO_PREEXISTING_DATA_INPUT')
    else:
        for key in ('accepted_profile_receipt_reference','accepted_profile_accounting_reference'):
            need(plan[key] in plan['parent_evidence_references'],'ACTUAL_PROFILE_PARENT_BINDING')
        prior=q.load_ref(plan['accepted_profile_receipt_reference']);need(prior['schema']=='SECONDARY_EXTERNAL_SOURCE_ACQUISITION_RECEIPT_V1' and
          prior['status']=='OFFICIAL_SINGLE_SOURCE_CONTAINER_PROFILE_COMPLETE' and prior['mode']=='profile' and
          prior['locator_catalog_sha256']==plan['locator_catalog_reference']['sha256'] and prior['kernel_source_references']==
          [pin(source.parent/x) for x in ('__init__.py','contracts.py','runtime.py','run.py')] and review.get('actual_profile_cost_and_container_path_reviewed') is True,'SAME_KERNEL_ACTUAL_PROFILE_BEFORE_FULL')
        actual_account(plan['accepted_profile_accounting_reference'],prior['job_id'])
        need(len(prior['sources'])==1 and prior['sources'][0]['source_id']=='sider' and prior['sources'][0]['status']=='COMPLETE_CONTAINER_OBSERVED' and
          plan['data_references']==[prior['sources'][0]['payload_reference']],'REUSE_ONLY_REAL_SIDER_PAYLOAD_NO_REGET')
    return plan,proof,rows,prior
