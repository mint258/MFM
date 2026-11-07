"""Fresh original guard with only explicit resource-phase primary/scope delta."""
import csv,hashlib,io,os,socket,sys,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import contracts as C,guard as ORIGINAL
from . import phase as A
account=ORIGINAL.account
main_authority=ORIGINAL.main_authority


def require_startup(plan_path,proof_path):
    plan=Q.load(plan_path);proof=Q.load(proof_path);mode=plan['mode'];Q.need(mode in C.MODES,'EXACT_PUBCHEM_MODE')
    spec=A.spec(A.phase(plan));primary=A.primary(A.phase(plan));wall=plan['wall_seconds'];cap=plan['output_cap_bytes']
    params=A.parameters(plan)
    argv=[plan['python'],'-B','-m',A.module(A.phase(plan)),'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    Q.need(plan['schema']==spec['plan'] and proof['schema']==spec['proof'] and plan['producer_key']==plan['scope_key']==spec['key']
        and plan['stage']==spec['stage'] and plan['scope_mode']==spec['scope_mode'] and plan['performance_profile'] is spec['performance_profile']
        and plan['scope_parameters']==params and plan['kind']=='analysis' and plan['pilot'] is spec['pilot']
        and plan['endpoint']==Q.ENDPOINT and plan['uid']==1264 and plan['run_root']==str(C.ROOT) and plan['node'] in Q.NODES
        and plan['cpus']==16 and plan['memory_policy']==Q.POLICY and type(wall) is int and 0<wall<=172800 and wall%60==0
        and type(cap) is int and (cap==spec['cap'] and wall==spec['wall'] if mode!='full_shard' else (16<<20)<=cap<=(1<<40)),
        'EXACT_ALPHA_MODE_SCOPE_RESOURCES_REQUIRED')
    Q.need(primary==Path(sys.modules['__main__'].__file__).absolute() and Path(sys.executable).absolute()==Path(plan['python']).absolute()
        and sys.argv==[str(primary),*argv[4:]] and plan['execution_argv']==argv and plan['startup_proof_path']==str(proof_path),'ACTUAL_PRIMARY_PYTHON_AND_ALL_ARGV')
    review=Q.load_ref(plan['root_review_reference']);Q.need(review['schema']=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','EXACT_ROOT_REVIEW_REQUIRED')
    for key in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot','wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references'):
        Q.need(plan[key]==review[key],'ROOT_STAGE_FIELD_DIFFERS:'+key)
    Q.need(plan['source_references']==review['approved_source_references'],'EXACT_APPROVED_SOURCE_SET')
    body_paths={row['path'] for row in plan['data_references']}
    Q.need(not any(row['path'] in body_paths for row in [*plan['source_references'],*plan['parent_evidence_references']]),'SCIENTIFIC_DATA_NEVER_PRE_FIXTURE_SOURCE_HASH')
    declared={row['path']:{k:row[k] for k in ('path','bytes','sha256')} for row in proof['source_target_verification']}
    for value in [*plan['source_references'],*plan['parent_evidence_references'],plan['root_review_reference'],Q.ref(plan_path)]:
        Q.need(declared.get(value['path'])==value,'ACTUAL_TARGET_SOURCE_PIN_MISSING');Q.verify(value)
    for path in [*(C.HERE/name for name in C.FILES),Path(Q.__file__),Path(Q.__file__).parent/'__init__.py']:
        Q.need(Q.ref(path) in plan['source_references'],'EVERY_ACTUAL_LOCAL_AND_BASE_SOURCE_REQUIRED')
    manifest=Q.load_ref(plan['frozen_manifest_reference'])
    for row in manifest['files']:Q.need(row['target_reference'] in plan['source_references'] and Q.ref(row['target_reference']['path'])==row['target_reference'],'ALL_EXACT_SCIENCE_SOURCE_COPIES_REQUIRED')
    Q.need(proof['endpoint']==Q.ENDPOINT and proof['uid']==os.getuid()==1264 and proof['node']==plan['node']==socket.gethostname().split('.')[0]
        and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and 0<=time.time()-proof['observed_unix_seconds']<=120
        and proof['plan_reference']==Q.ref(plan_path) and proof['root_review_reference']==plan['root_review_reference'],'FRESH_INDEPENDENT_ALPHA_STAGE_PROOF')
    Q.need(proof['scope_key']==spec['key'] and proof['scope_mode']==spec['scope_mode']
        and proof['performance_profile'] is spec['performance_profile'],'HONEST_MODE_AND_PERFORMANCE_STARTUP_PROOF')
    Q.need(proof['request']=={'kind':'analysis','pilot':spec['pilot'],'cpus':16,'memory_policy':Q.POLICY,'wall_seconds':wall,'execution_argv':argv}
        and proof['memory_limits_requested'] is False and proof['exclusive_requested'] is False,'NO_EXPLICIT_MEMORY_OR_EXCLUSIVE_REQUEST')
    env=os.environ;Q.need(env.get('SLURM_JOB_ID')==str(proof['job_id']) and env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('SLURM_CPUS_PER_TASK')=='16'
        and env.get('CUDA_VISIBLE_DEVICES')=='' and all(env.get(key)=='1' for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'REAL_CPU16_LIBRARY_THREADS')
    job=Q.fields(proof['job_metadata']);Q.need(job['JobId']==str(proof['job_id']) and job['UserId']=='alpha(1264)' and job['JobState']=='RUNNING'
        and job['NodeList']==plan['node'] and job['Partition']=='cpu' and job['NumCPUs']=='16' and job['NumTasks']=='1' and job['Requeue']=='0'
        and job['Command']==proof['script_reference']['path'] and Q.duration(job['TimeLimit'])==wall,'EXACT_RUNNING_SCRIPT_JOB_WALL')
    signer=proof['controller_evidence'];Q.need(signer['endpoint']==Q.ENDPOINT and signer['uid']==1264 and signer['hostname']=='sonmi'
        and signer['proof_is_not_created_by_scientific_worker'] is True and signer['actual_script_reference']==proof['script_reference'],'INDEPENDENT_LOGIN_CONTROLLER')
    for text in Q.read_small(Q.verify(proof['script_reference'])).decode().splitlines():
        if text.strip().startswith('#SBATCH'):Q.need(not any(word in text for word in ('--mem','--exclusive','--gpu','--gres')),'NO_MEMORY_GPU_OR_EXCLUSIVE_DIRECTIVE')
    tail=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split();gate=proof['actual_gate_process']
    Q.need(gate['pid']==os.getpid() and gate['uid']==1264 and gate['start_ticks']==int(tail[19]) and gate['pgid']==os.getpgrp() and gate['sid']==os.getsid(0)
        and gate['cgroup_sha256']==hashlib.sha256(Path('/proc/self/cgroup').read_bytes()).hexdigest(),'SAME_ATTESTED_EXEC_GATE_PROCESS')
    storage=proof['storage_observation'];raw=Q.load_ref(proof['storage_observation_reference']);scope_ref=storage['storage_scope_review_reference']
    Q.need(scope_ref['path']==str(C.STORAGE_SCOPE) and declared.get(scope_ref['path'])==scope_ref and raw['uid']==1264 and raw['node']==proof['node'] and raw['run_root']==str(C.ROOT)
        and raw['observed_unix_seconds']==storage['observed_unix_seconds'],'ACTUAL_SIGNED_RAW_STORAGE_AND_SCOPE')
    scope=Q.load_ref(scope_ref);extra=sum(row['whole_output_cap_bytes'] for row in scope.get('additional_task_output_reservations',[]))
    reserved=storage['whole_output_caps_reserved_bytes']-extra;Q.need(reserved>=cap,'OWN_WHOLE_CAP_RESERVED')
    Q.need(Q.effective_storage(raw,scope_ref['path'],reserved,reservation_evidence=storage['registered_task_reservation_evidence'])==storage
        and proof['account_free_bytes']==storage['effective_free_bytes'] and 0<=time.time()-storage['observed_unix_seconds']<=120,'RECOMPUTED_CURRENT_STORAGE_CAPS_PLUS200GB')
    for key in ('resource_authority_reference','cost_decision_reference','metadata_relocation_reference','frozen_manifest_reference'):
        Q.need(plan[key] in plan['source_references'],'EXPLICIT_APPROVED_ALPHA_AUTHORITY:'+key)
    authority=Q.load_ref(plan['resource_authority_reference']);cost=Q.load_ref(plan['cost_decision_reference'])
    Q.need(authority['schema']=='USER_AUTHORIZED_SECONDARY_DATA_CLUSTER_V1' and authority['status']=='USER_AUTHORIZED' and authority['endpoint']==Q.ENDPOINT and authority['observed_uid']==1264,'ACTUAL_ALPHA_AUTHORITY')
    Q.need(cost['schema']=='USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1' and cost['status']=='USER_AUTHORIZED'
        and cost['on_overrun']=='REPORT_AND_CONTINUE' and cost['scientific_quality_thresholds_unchanged'] is True,'COST_CONTINUE_DOES_NOT_RELEASE_QUALITY')
    main_inv,main_uniform=main_authority(plan)
    raw_receipt=Q.load_ref(plan['alpha_raw_validation_receipt_reference'])
    Q.need(plan['alpha_raw_validation_receipt_reference'] in plan['parent_evidence_references'] and raw_receipt['job_id']=='1884769'
        and raw_receipt['status']=='EXACT_MAIN_PUBLIC_RAW_COPY_SHA_GZIP_EOF_VALIDATED' and raw_receipt['endpoint']==Q.ENDPOINT and raw_receipt['uid']==1264
        and raw_receipt['actual_alpha_raw_reference']==plan['raw_reference'] and plan['raw_reference']['bytes']==C.RAW_BYTES
        and plan['raw_reference']['sha256']==C.RAW_SHA and raw_receipt['counts']['physical_rows']==C.N
        and raw_receipt['counts']['gzip_EOF_CRC_verified'] is True,'ACTUAL1884769_IDENTICAL_FULL_RAW_REQUIRED')
    account(plan['alpha_raw_validation_accounting_reference'],'1884769',Q.ENDPOINT,1264,plan['parent_evidence_references'])
    Q.need(all(plan['main_index_reference'][k]==main_inv['source_index']['reference'][k] for k in ('bytes','sha256')),'EXACT_MAIN_SOURCE_INDEX_COPY_PIN')
    if mode=='inventory':Q.need(plan['data_references']==[plan['raw_reference'],plan['main_index_reference']],'A_EXACT_RAW_AND_MAIN_INDEX_DATA')
    else:
        inventory=Q.load_ref(plan['alpha_inventory_receipt_reference']);Q.need(plan['alpha_inventory_receipt_reference'] in plan['parent_evidence_references']
            and inventory['status']=='ALPHA_PHYSICAL500_COMPLETE_NO_CHEMISTRY' and inventory['endpoint']==Q.ENDPOINT and inventory['uid']==1264
            and inventory['raw_reference']==plan['raw_reference'] and inventory['frozen_manifest_reference']==plan['frozen_manifest_reference']
            and inventory['inventory']['all500_parts_equal_Main_SHA_rows_bytes'] is True
            and inventory['inventory']['records']==C.N and inventory['inventory']['uncompressed_bytes']==C.UNCOMPRESSED_BYTES
            and inventory['inventory']['part_count']==500 and inventory['inventory']['gzip_EOF_CRC_revalidated'] is True,'ACTUAL_ALPHA_COMPLETE500_PARENT_REQUIRED')
        account(plan['alpha_inventory_accounting_reference'],inventory['job_id'],Q.ENDPOINT,1264,plan['parent_evidence_references'])
        data=inventory['inventory']
        if mode=='profile':
            Q.need(all(plan['main_uniform_journal_reference'][k]==main_uniform['uniform']['full_result_journal'][k] for k in ('bytes','sha256')),
                'MAIN10000_JOURNAL_EXACT_PRODUCER_PIN_NOT_LOGIN_OBSERVED')
            Q.need(plan['data_references']==[data['source_index'],data['uniform_locators'],data['longest_locators'],plan['main_uniform_journal_reference']],'B_EXACT_SCIENTIFIC_INPUT_DATA_SET')
        else:
            Q.need(plan['data_references']==([] if A.phase(plan)=='QA0' else [data['source_index']]) and review.get('actual_profile_equivalence_and_cost_reviewed') is True,'C_ROOT_PROFILE_COST_REVIEW_REQUIRED')
            Q.need(plan['accepted_profile_receipt_reference'] in plan['parent_evidence_references'],'ACTUAL_PROFILE_RECEIPT_APPROVED_PARENT_REQUIRED')
            profile=Q.load_ref(plan['accepted_profile_receipt_reference']);Q.need(profile['status']=='ALPHA_UNIFORM10000_EQUIVALENT_PROFILE_COMPLETE'
                and profile['endpoint']==Q.ENDPOINT and profile['uid']==1264 and profile['raw_reference']==plan['raw_reference']
                and profile['frozen_manifest_reference']==plan['frozen_manifest_reference']
                and profile['uniform']['counts']==main_uniform['uniform']['counts'] and profile['comparison']['scientific_mismatches']==0
                and profile['comparison']['compared_rows']==10000 and profile['full_source_pool_release_authorized'] is False,'ACTUAL_EQUIVALENT10000_NOT_FINAL_POOL_RELEASE')
            account(plan['accepted_profile_accounting_reference'],profile['job_id'],Q.ENDPOINT,1264,plan['parent_evidence_references'])
            Q.need(plan['full_shard_manifest_reference'] in plan['source_references'] and plan['profile_output_budget_reference'] in plan['source_references'],'ROOT_FROZEN_FULL_PARTITION_AND_BUDGET_REQUIRED')
            for path in [*(C.HERE/name for name in C.FILES),Path(Q.__file__),Path(Q.__file__).parent/'__init__.py']:
                Q.need(Q.ref(path) in profile['source_references'],'C_SAME_ACTUAL_PROFILE_EXECUTION_CORE_REQUIRED')
            budget=Q.load_ref(plan['profile_output_budget_reference'])
            Q.need(budget['schema']=='ALPHA_PUBCHEM_PROFILE_DERIVED_OUTPUT_BUDGET_V1'
                and budget['status']=='ROOT_REVIEWED_ACTUAL_PROFILE_COST_AND_STORAGE'
                and budget['profile_receipt_reference']==plan['accepted_profile_receipt_reference']
                and budget['frozen_manifest_reference']==plan['frozen_manifest_reference']
                and budget['uniform_rows']==10000 and budget['longest_excluded_from_uniform_projection'] is True
                and budget['worst_case_feature_size_proven'] is False,'ACTUAL_PROFILE_DERIVED_BUDGET_NOT_FALSE_WORST_CASE_PROOF')
            limits=[row for row in budget['reviewed_shards'] if row['shard_index']==plan['shard_index']]
            Q.need(len(limits)==1 and (A.phase(plan)=='QA0' or (limits[0]['wall_seconds']==wall and limits[0]['output_cap_bytes']==cap)),'ROOT_EXACT_SHARD_PROFILE_DERIVED_LIMITS')
    import pyarrow
    Q.need(sys.version.split()[0]=='3.11.14' and pyarrow.__version__=='17.0.0','ACTUAL_ALPHA_PYTHON_AND_ARROW')
    if mode!='inventory':
        from rdkit import rdBase
        Q.need(rdBase.rdkitVersion=='2025.09.5','EXACT_ORIGINAL_RDKIT_VERSION')
    out=Q.literal(plan['output_directory']);Q.need(C.ROOT/'artifacts' in out.parents and not out.exists() and len(str(out))<=1024,'NEW_FINITE_ALPHA_OUTPUT_LEAF')
    A.validate(plan)
    return plan,proof
