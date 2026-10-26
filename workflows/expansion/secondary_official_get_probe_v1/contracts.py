"""One exact three-URL probe and independent fresh Alpha allocation authority."""
import hashlib,os,socket,sys,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as q
ROOT=q.ROOT;KEY='official_three_get_probe_alpha_v1';MODULE='official_get_probe_v1.run';HERE=ROOT/'code/official_get_probe_v1'
STAGE='OFFICIAL_THREE_URL_BOUNDED_GET_ONLY_NO_IDENTITY';MODE='EXACT_OFFICIAL_THREE_URL_GET_PROBE_NO_FULL_RELEASE';CAP=256<<20
FILES=('__init__.py','contracts.py','http.py','run.py','test_probe.py','README.md')
SPECS=(
 {'source_id':'tdc_admet_group_zip','url':'https://dataverse.harvard.edu/api/access/datafile/4426004','cap_bytes':128<<20,'range_first_MiB':False,
  'version':'c310c35f27e3f506411018ac43d97b8ba23ca652','official_path':'tdc/metadata.py'},
 {'source_id':'marcel_drugs_zip_landing','url':'https://drive.google.com/file/d/1PHgbrxdDyyjnxSUA71zXWG8WNwocDLPH/view?usp=sharing','cap_bytes':1<<20,'range_first_MiB':True,
  'version':'dae6b3b824b68d1362ed3b9fa23b34a45fa5366c','official_path':'datasets/Drugs/README.md'},
 {'source_id':'marcel_kraken_zip_landing','url':'https://drive.google.com/file/d/1QrV651Re7s6UF7Lg4KC9PM5QQUMPU7wd/view?usp=sharing','cap_bytes':1<<20,'range_first_MiB':True,
  'version':'dae6b3b824b68d1362ed3b9fa23b34a45fa5366c','official_path':'datasets/Kraken/README.md'})
PARAMETERS={'original_source_ids':[s['source_id'] for s in SPECS],'original_URLs':[s['url'] for s in SPECS],
 'source_entity_byte_caps':[s['cap_bytes'] for s in SPECS],'source_requests':'SERIAL_THREE_ORIGINAL_URLS_ONLY','synthetic_fixture_tests':5,
 'fixtures_before_any_network':True,'method':'GET','stream':True,'TLS_verify':True,'trust_environment_proxy_or_netrc':False,
 'redirects':'NORMAL_HTTPS_LOCATION_MAX5_CLOSE_UNREAD_INTERMEDIATE_BODY','redirect_metadata':'HOST_ONLY_NO_LOCATION_QUERY',
 'MARCEL_Range':'bytes=0-1048575','MARCEL_archive_acceptance_allowed':False,'entity_bytes':'RAW_NO_CONTENT_DECODING',
 'at_exact_byte_cap':'PARTIAL_NO_EXTRA_PEEK_NO_EOF_CLAIM','whole_archive_SHA_requires':'TDC_STATUS200_ACTUAL_EOF_LENGTH_MAGIC_ALL_ZIP_CRC_PASS',
 'ZIP_max_entries':256,'ZIP_max_total_expanded_bytes':1<<30,'ZIP_max_one_entry_bytes':128<<20,'ZIP_max_central_directory_bytes':16<<20,
 'ZIP64_or_multidisk_acceptance':False,'CSV_or_identity_decode':False,
 'automatic_retry_or_confirmation_or_auth_bypass':False,'new_UFF_QM_calls':0,'identity_or_pool_or_training_release':False,
 'RSS_software_soft_stop_bytes':2<<30,'MemAvailable_software_floor_bytes':4<<30,'output_cap_bytes':CAP}
ORIGIN_CATALOG={'path':'/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/expansion/official_source_head_catalog_v1.json',
 'bytes':42335,'sha256':'ac77dff2ceef3d1b177765c7338e29aa094f0e8074c1f58d2249e3f42b5b45dd'}
ORIGIN_RESEARCH={'path':'/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/docs/data_v1/tdc_marcel_official_source_research_20261027_v1.md',
 'bytes':8668,'sha256':'ec9b9a996b5374fe66f5ba0cee3a6529ebca20b8ebc89c1d1992cbd3b147b745'}
PLAN_SCHEMA='SECONDARY_OFFICIAL_THREE_GET_PROBE_PLAN_V1';PROOF_SCHEMA='SECONDARY_OFFICIAL_THREE_GET_PROBE_STARTUP_V1'
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot','wall_seconds',
 'output_cap_bytes','output_directory','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')

def metadata(plan):
    q.need(plan['data_references']==[],'NO_EXISTING_SCIENTIFIC_BODY_INPUTS_OR_HASH_ON_LOGIN')
    for key in ('resource_authority_reference','cost_decision_reference','locator_catalog_reference','research_reference'):
        q.need(plan[key] in plan['source_references'],'EXPLICIT_EXACT_PROBE_AUTHORITY:'+key);q.verify(plan[key])
    for key,origin in (('locator_catalog_reference',ORIGIN_CATALOG),('research_reference',ORIGIN_RESEARCH)):
        q.need(plan['origin_'+key]==origin and all(plan[key][k]==origin[k] for k in ('bytes','sha256')),'ORIGINAL_METADATA_BYTES_NO_SILENT_REWRITE')
        q.need(plan[key] in plan['parent_evidence_references'],'ORIGINAL_LOCATOR_OR_RESEARCH_PARENT_REQUIRED')
    catalog=q.load_ref(plan['locator_catalog_reference']);q.need(catalog['schema']=='SB5_OFFICIAL_SOURCE_HEAD_CATALOG_V1','EXACT_ORIGINAL_CATALOG_SCHEMA')
    entries={r['source_id']:r for r in catalog['probe_sources']}
    for spec in SPECS:
        row=entries[spec['source_id']];project='mims-harvard/TDC' if spec['source_id']=='tdc_admet_group_zip' else 'SXKDZ/MARCEL'
        q.need(row['url']==spec['url'] and row['method']=='HEAD' and row['metadata_source_commit']==spec['version']
            and row['official_text_reference']=='https://github.com/'+project+'/blob/'+spec['version']+'/'+spec['official_path'],
            'SAME_ORIGINAL_OFFICIAL_URL_VERSION_NO_MIRROR_OR_NEW_SOURCE')
    for path in [*(HERE/name for name in FILES),*q.PACKAGE.glob('*.py')]:q.need(q.ref(path) in plan['source_references'],'ALL_PROBE_AND_BASE_RUNTIME_SOURCE_PINS')
    q.authority(plan['resource_authority_reference']['path'])
    cost=q.load_ref(plan['cost_decision_reference']);q.need(cost.get('schema')=='USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1'
        and cost.get('status')=='USER_AUTHORIZED' and cost.get('on_overrun')=='REPORT_AND_CONTINUE','ACTUAL_COST_REPORT_CONTINUE')

def startup(plan_path,proof_path):
    plan=q.load(plan_path);proof=q.load(proof_path);source=HERE/'run.py'
    argv=[plan['python'],'-B','-m',MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    q.need(plan.get('schema')==PLAN_SCHEMA and plan.get('scope_key')==plan.get('producer_key')==KEY and plan.get('stage')==STAGE
        and plan.get('scope_parameters')==PARAMETERS and plan.get('kind')=='analysis' and plan.get('pilot') is False
        and plan.get('scope_mode')==MODE and plan.get('performance_profile') is False and plan.get('endpoint')==q.ENDPOINT and plan.get('uid')==1264
        and plan.get('run_root')==str(ROOT) and plan.get('node') in q.NODES and plan.get('cpus')==16 and plan.get('memory_policy')==q.POLICY
        and type(plan.get('wall_seconds')) is int and 120<plan['wall_seconds']<=3600 and plan['wall_seconds']%60==0
        and plan.get('output_cap_bytes')==CAP,'EXACT_NEW_ALPHA_THREE_GET_PROBE_SCOPE')
    out=q.literal(plan['output_directory']);q.need(ROOT/'artifacts/official_get_probe_v1' in out.parents and not out.exists(),'FRESH_EXACT_PROBE_OUTPUT')
    q.need(Path(sys.modules['__main__'].__file__).absolute()==source and Path(sys.executable).absolute()==Path(plan['python'])
        and sys.argv[1:]==argv[4:] and plan['execution_argv']==argv and plan['startup_proof_path']==str(proof_path),'ACTUAL_PROBE_PRIMARY_AND_ALL_ARGV')
    review=q.load_ref(plan['root_review_reference']);q.need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root','EXACT_PROBE_ROOT_REVIEW')
    for key in REVIEW_FIELDS:q.need(plan[key]==review[key],'EXACT_PROBE_ROOT_REVIEW_DIFFERS:'+key)
    q.need(plan['source_references']==review['approved_source_references'],'EXACT_PROBE_SOURCE_SET')
    node=socket.gethostname().split('.')[0]
    q.need(proof.get('schema')==PROOF_SCHEMA and proof.get('scope_key')==KEY and proof.get('stage')==STAGE and proof.get('endpoint')==q.ENDPOINT
        and proof.get('uid')==os.getuid()==1264 and proof['node']==plan['node']==node and os.environ.get('SLURM_JOB_ID')==str(proof['job_id'])
        and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and 0<=time.time()-proof['observed_unix_seconds']<=120,
        'FRESH_ACTUAL_ALPHA_UID_NODE_BOOT_JOB_NOT_MAIN_PROOF')
    q.need(proof['request']=={'kind':'analysis','pilot':False,'cpus':16,'memory_policy':q.POLICY,'wall_seconds':plan['wall_seconds'],'execution_argv':argv}
        and proof['plan_reference']==q.ref(plan_path) and proof['root_review_reference']==plan['root_review_reference']
        and proof['memory_limits_requested'] is False and proof['exclusive_requested'] is False,'ACTUAL_NEW_NO_MEM_PROBE_REQUEST')
    q.need(os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
        and os.environ.get('CUDA_VISIBLE_DEVICES')=='','ACTUAL_ALPHA_CPU16_NO_GPU')
    declared={r['path']:r for r in proof['source_target_verification']}
    for r in [*plan['source_references'],*plan['parent_evidence_references'],plan['root_review_reference'],q.ref(plan_path)]:
        q.need(declared.get(r['path'])==r,'ACTUAL_PROBE_SMALL_SOURCE_TARGET_PIN');q.verify(r)
    metadata(plan)
    job=q.fields(proof['job_metadata']);q.need(job.get('JobId')==str(proof['job_id']) and job.get('UserId')=='alpha(1264)'
        and job.get('JobState')=='RUNNING' and job.get('Partition')=='cpu' and job.get('NodeList')==node and job.get('NumCPUs')=='16'
        and job.get('NumTasks')=='1' and job.get('Requeue')=='0' and job.get('Command')==proof['script_reference']['path']
        and q.duration(job['TimeLimit'])==plan['wall_seconds'],'ACTUAL_ALPHA_JOB_SCRIPT_CPU_WALL')
    for line in q.verify(proof['script_reference']).read_text().splitlines():
        if line.strip().startswith('#SBATCH'):q.need(not any(x in line for x in ('--mem','--exclusive','--gres','--gpu')),'NO_MEMORY_EXCLUSIVE_GPU_DIRECTIVES')
    gate=proof['actual_gate_process'];ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
    q.need(gate['pid']==os.getpid() and gate['uid']==1264 and gate['start_ticks']==ticks and gate['pgid']==os.getpgrp() and gate['sid']==os.getsid(0)
        and gate['cgroup_sha256']==hashlib.sha256(Path('/proc/self/cgroup').read_bytes()).hexdigest(),'SAME_ATTESTED_REAL_ALPHA_GATE_PROCESS')
    origin=proof['controller_evidence'];q.need(origin['endpoint']==q.ENDPOINT and origin['uid']==1264 and origin['hostname']=='sonmi'
        and origin['proof_is_not_created_by_scientific_worker'] is True and origin['actual_script_reference']==proof['script_reference'],'INDEPENDENT_ALPHA_LOGIN_CONTROLLER')
    storage=proof['storage_observation'];q.verify(proof['storage_observation_reference'])
    q.need(proof['account_free_bytes']==storage['effective_free_bytes'] and proof['account_free_bytes']-CAP>=200000000000
        and storage['whole_output_caps_reserved_bytes']>=CAP and 0<=time.time()-storage['observed_unix_seconds']<=120,'FRESH_SCOPE7_ALL_CAPS_QUOTA200GB')
    return plan,proof
