"""Fresh Alpha read-only format profile, bound to actual eleven-source parents."""
from __future__ import annotations
import hashlib,os,re,socket,sys,time
from pathlib import Path
from secondary_external_sources_acquisition_v1 import contracts as prior
from .formats import CSV_IDS,TAR_IDS,HEADER_CAP,RECORD_CAP,IDENTITY_FIELD_CAP,NATIVE_CAP

q=prior.q;ROOT=q.ROOT;UID=1264;IDS=prior.IDS
KEY='moleculenet_missing11_identity_format_probe_alpha_v1'
MODULE='secondary_missing11_identity_format_probe_v1.run'
STAGE='IDENTITY_INPUT_FORMAT_METADATA_PROBE'
PARAMETERS={'source_ids':list(IDS),'CSV_sources':6,'TAR_sources':4,'MAT_sources':1,'input_payloads':11,'input_TAR_inventories':4,
 'data_inputs':15,'expected_payload_bytes':2501171487,'expected_TAR_inventory_bytes':25359956,
 'CSV_full_physical_record_count':True,'CSV_header_cap_bytes':HEADER_CAP,'CSV_record_software_cap_bytes':RECORD_CAP,
 'CSV_selected_identity_field_cap_bytes':IDENTITY_FIELD_CAP,'CSV_assay_values_decoded':False,'identity_values_persisted':False,
 'TAR_inventory_all_member_classification':True,'native_record_cap_bytes':NATIVE_CAP,'maximum_native_candidates_per_format_per_archive':1,
 'native_SDF_MOL2_graph_keys':False,'RDKit_MOL2_charge_stereo_inference':False,'QM7b_whosmat_only':True,'QM7_adapter_on_QM7b':False,
 'current_full_payload_SHA_reverified':False,'payload_verification':'PRODUCER_FULL_SHA_PLUS_UNCHANGED_FRAME',
 'current_TAR_inventory_full_SHA_reverified':True,'maximum_source_threads':16,'synthetic_fixture_tests':8,
 'fixtures_before_any_data_body':True,'maximum_expanded_bytes_per_source':256<<30,'algorithm_RSS_reference_bytes':48<<30,
 'runtime_MemAvailable_min_fraction':.15,'official_loader_commit':'455d07f3e17e880a4d980b5b0365e4a02b417e14',
 'new_GETs':0,'new_UFF_QM_calls':0,'chemical_normalization':False,'all_split_identity_coverage_accepted':False,
 'pool_training_export_release':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}
need=q.need;load=q.load;verify=q.verify;pin=q.ref;write_new=prior.write_new;frame=prior.frame

def body_reference(value):
    need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'} and type(value['bytes']) is int and value['bytes']>=0
      and isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256']),'EXACT_DATA_LOCATOR_TRIPLE')
    q.literal(value['path']);return value

def startup(plan_path,proof_path,primary):
    plan=load(plan_path);proof=load(proof_path);source=ROOT/'code/secondary_missing11_identity_format_probe_v1/run.py'
    argv=[plan['python'],'-B','-m',MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)];wall=plan['wall_seconds'];cap=64<<20
    need(plan.get('schema')=='SECONDARY_MISSING11_IDENTITY_FORMAT_PROFILE_PLAN_V1' and plan.get('producer_key')==plan.get('scope_key')==KEY
      and plan.get('stage')==STAGE and plan.get('mode')=='format_profile' and plan.get('kind')=='analysis' and plan.get('pilot') is False
      and plan.get('scope_parameters')==PARAMETERS and plan.get('endpoint')==q.ENDPOINT and plan.get('uid')==UID
      and plan.get('run_root')==str(ROOT) and plan.get('node') in q.NODES and plan.get('cpus')==16
      and plan.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED' and type(wall) is int and 0<wall<=3600 and wall%60==0
      and plan.get('output_cap_bytes')==cap,'EXACT_READONLY_MISSING11_FORMAT_PROFILE_PLAN')
    out=q.literal(plan['output_directory']);need(ROOT/'artifacts/moleculenet_missing11_identity_format_probe_v1' in out.parents and not out.exists(),'NEW_FORMAT_PROFILE_ARTIFACT_CHILD')
    need(Path(primary).absolute()==source==Path(sys.modules['__main__'].__file__).absolute() and Path(sys.executable).absolute()==Path(plan['python']).absolute()
      and sys.argv==[str(source),*argv[4:]] and plan['execution_argv']==argv and plan['startup_proof_path']==str(proof_path),'ACTUAL_FORMAT_PROFILE_PRIMARY_ALL_ARGV')
    review=q.load_ref(plan['root_review_reference'])
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root','NEW_FORMAT_PROFILE_EXACT_ROOT_REVIEW')
    for key in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot','wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references'):
        need(plan[key]==review[key],'FORMAT_PROFILE_REVIEW_DIFFERS:'+key)
    need(plan['source_references']==review['approved_source_references'],'FORMAT_PROFILE_EXACT_SOURCES')
    need(not ({r['path'] for r in plan['source_references']}&{r['path'] for r in plan['data_references']}),'BODY_LOCATOR_NOT_PRE_FIXTURE_SOURCE')
    need(proof.get('schema')=='SECONDARY_MISSING11_IDENTITY_FORMAT_PROFILE_STARTUP_V1' and proof.get('endpoint')==q.ENDPOINT
      and proof.get('uid')==os.getuid()==UID and proof['node']==plan['node']==socket.gethostname().split('.')[0]
      and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and 0<=time.time()-proof['observed_unix_seconds']<=120
      and proof['plan_reference']==pin(plan_path) and proof['root_review_reference']==plan['root_review_reference'],'NEW_ALPHA_FRESH_FORMAT_PROFILE_PROOF')
    need(str(proof['job_id']) not in {'1884783','1884784'} and proof['request']=={'kind':'analysis','pilot':False,'cpus':16,
      'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','wall_seconds':wall,'execution_argv':argv} and proof['memory_limits_requested'] is False
      and proof['exclusive_requested'] is False and proof.get('bounded_readonly_scope_only') is True,'NEW_READONLY_DEFAULT_MEMORY_REQUEST')
    env=os.environ
    need(env.get('SLURM_JOB_ID')==str(proof['job_id']) and env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('SLURM_CPUS_PER_TASK')=='16'
      and env.get('CUDA_VISIBLE_DEVICES')=='' and all(env.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'ACTUAL_FORMAT_PROFILE_CPU16_THREADS')
    declared={r['path']:{k:r[k] for k in ('path','bytes','sha256')} for r in proof['source_target_verification']}
    for ref in [*plan['source_references'],*plan['parent_evidence_references'],plan['root_review_reference'],pin(plan_path)]:
        need(declared.get(ref['path'])==ref,'FORMAT_PROFILE_ACTUAL_SMALL_SOURCE_TARGET_MISSING');verify(ref)
    for path in [*source.parent.glob('*.py'),*source.parent.glob('*.md'),Path(q.__file__),Path(q.__file__).parent/'__init__.py']:
        need(pin(path) in plan['source_references'],'ALL_FORMAT_PROFILE_AND_BASE_SOURCES_PINNED')
    kernel=Path(prior.__file__).parent
    for name in ('__init__.py','contracts.py','runtime.py','run.py'):need(pin(kernel/name) in plan['source_references'],'ALL_FROZEN_ACQUISITION_HELPERS_PINNED')
    origin=proof['controller_evidence'];need(origin['endpoint']==q.ENDPOINT and origin['uid']==UID and origin['hostname']=='sonmi'
      and origin['proof_is_not_created_by_scientific_worker'] is True and origin['actual_script_reference']==proof['script_reference'],'REAL_ALPHA_LOGIN_CONTROLLER_PROOF')
    for line in q.read_small(verify(proof['script_reference'])).decode().splitlines():
        if line.strip().startswith('#SBATCH'):need(not any(x in line for x in ('--mem','--exclusive','--gres','--gpu')),'NO_MEMORY_EXCLUSIVE_GPU_DIRECTIVE')
    job=q.fields(proof['job_metadata']);need(job.get('JobId')==str(proof['job_id']) and job.get('UserId')=='alpha(1264)' and job.get('JobState')=='RUNNING'
      and job.get('NodeList')==plan['node'] and job.get('Partition')=='cpu' and job.get('NumCPUs')=='16' and job.get('NumTasks')=='1'
      and job.get('Requeue')=='0' and job.get('Command')==proof['script_reference']['path'] and q.duration(job.get('TimeLimit',''))==wall,'ACTUAL_ALPHA_FORMAT_PROFILE_JOB_SCRIPT_WALL')
    gate=proof['actual_gate_process'];tail=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    need(gate['pid']==os.getpid() and gate['uid']==UID and gate['start_ticks']==int(tail[19]) and gate['pgid']==os.getpgrp() and gate['sid']==os.getsid(0)
      and gate['cgroup_sha256']==hashlib.sha256(Path('/proc/self/cgroup').read_bytes()).hexdigest(),'SAME_ATTESTED_ALPHA_GATE_PROCESS')
    storage=proof['storage_observation'];q.load_ref(proof['storage_observation_reference'])
    need(proof['account_free_bytes']==storage['effective_free_bytes'] and proof['account_free_bytes']-cap>=200000000000
      and storage['whole_output_caps_reserved_bytes']>=cap and 0<=time.time()-storage['observed_unix_seconds']<=120,'FRESH_FORMAT_PROFILE_ALL_CAPS200GB_STORAGE')
    for key in ('resource_authority_reference','cost_decision_reference','locator_catalog_reference','identity_input_contract_reference'):
        need(plan[key] in plan['source_references'],'EXPLICIT_SMALL_FORMAT_PROFILE_AUTHORITY:'+key)
    authority=q.load_ref(plan['resource_authority_reference']);need(authority.get('schema')=='USER_AUTHORIZED_SECONDARY_DATA_CLUSTER_V1'
      and authority.get('status')=='USER_AUTHORIZED' and authority.get('endpoint')==q.ENDPOINT and authority.get('observed_uid')==UID
      and authority.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED','EXACT_ALPHA_RESOURCE_AUTHORITY')
    cost=q.load_ref(plan['cost_decision_reference']);need(cost.get('schema')=='USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1'
      and cost.get('status')=='USER_AUTHORIZED' and cost.get('on_overrun')=='REPORT_AND_CONTINUE' and cost.get('scientific_quality_thresholds_unchanged') is True,'EXACT_COST_REPORT_CONTINUE_AUTHORITY')
    for key in ('acquisition_receipt_reference','acquisition_accounting_reference','reused_sider_receipt_reference','reused_sider_accounting_reference'):
        need(plan[key] in plan['parent_evidence_references'],'ACTUAL_FORMAT_PROFILE_PARENT_PIN:'+key)
    full=q.load_ref(plan['acquisition_receipt_reference']);single=q.load_ref(plan['reused_sider_receipt_reference'])
    for ref,job_id in ((plan['acquisition_accounting_reference'],'1884784'),(plan['reused_sider_accounting_reference'],'1884783')):
        account=prior.actual_account(ref,job_id);need(account['raw_sacct_reference'] in plan['parent_evidence_references'],'ACTUAL_PARENT_RAW_PIN')
    need(full['status']=='OFFICIAL_ELEVEN_SOURCE_CONTAINER_ACQUISITION_COMPLETE' and full['job_id']=='1884784' and full['uid']==UID and full['endpoint']==q.ENDPOINT
      and full['kernel_source_references']==[pin(kernel/name) for name in ('__init__.py','contracts.py','runtime.py','run.py')],'ACTUAL_COMPLETE_ELEVEN_CONTAINER_PARENT')
    need(single['job_id']=='1884783' and single['status']=='OFFICIAL_SINGLE_SOURCE_CONTAINER_PROFILE_COMPLETE' and len(single['sources'])==1,'ACTUAL_SIDER_PROFILE_PARENT')
    catalog=q.load_ref(plan['locator_catalog_reference']);need(catalog['schema']=='MOLECULENET_MISSING11_ACTUAL_HEAD_LOCATORS_V1'
      and catalog['official_loader_commit']==PARAMETERS['official_loader_commit'] and catalog['physical_file_count']==11
      and catalog['total_expected_compressed_bytes']==2501171487 and full['locator_catalog_sha256']==plan['locator_catalog_reference']['sha256'],'EXACT_ELEVEN_OFFICIAL_CATALOG')
    sources={r['source_id']:r for r in full['sources']};entries={r['source_id']:r for r in catalog['entries']}
    need(len(sources)==len(full['sources'])==len(entries)==11 and set(sources)==set(entries)==set(IDS),'EXACT_ELEVEN_NO_EXTRA_SOURCES')
    for id in IDS:
        row=sources[id];entry=entries[id]
        need(row['status']=='COMPLETE_CONTAINER_OBSERVED' and row['full_file_disk_SHA_verified'] is True
          and row['payload_reference']['bytes']==entry['expected_compressed_bytes'] and row['url']==entry['url'] and row['container']['container']==entry['container'],'ACTUAL_SOURCE_BYTES_KIND_AND_PRODUCER_HASH')
        body_reference(row['payload_reference'])
    need(sources['sider']['payload_reference']==single['sources'][0]['payload_reference'] and sources['sider']['payload_frame']==single['sources'][0]['payload_frame'],'REUSED_SIDER_EXACT_PRODUCER_FRAME')
    data=[sources[id]['payload_reference'] for id in IDS]+[sources[id]['container']['inventory_reference'] for id in TAR_IDS]
    for value in data:body_reference(value)
    need(plan['data_references']==data and sum(r['bytes'] for r in data)==2526531443 and len({r['path'] for r in data})==15,'EXACT_REAL_ELEVEN_PLUS_FOUR_INPUT_LOCATORS')
    return plan,proof,sources
