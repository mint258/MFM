"""Fresh Alpha authority independent of all historical Main/Alpha proofs."""
import csv,hashlib,io,os,socket,sys,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from . import contracts as C

def account(reference,job,endpoint,uid,parents):
    Q.need(reference in parents,'ACTUAL_PARENT_ACCOUNTING_PIN_REQUIRED');value=Q.load_ref(reference);p=value['actual_parent']
    Q.need(value['query_returncode']==0 and value['endpoint']==endpoint and value['uid']==uid and p['JobIDRaw']==str(job)
        and p['State']=='COMPLETED' and p['ExitCode']=='0:0' and p['AllocCPUS']=='16' and p['UID']==str(uid)
        and (uid!=1264 or (p['NodeList'] in Q.NODES and p['Partition']=='cpu')),'ACTUAL_C0_PARENT_REQUIRED')
    raw=value['raw_sacct_reference'];Q.need(raw in parents,'RAW_PARENT_ACCOUNTING_PIN_REQUIRED')
    rows=list(csv.DictReader(io.StringIO(Q.read_small(Q.verify(raw)).decode()),delimiter='|'));found=[x for x in rows if x.get('JobIDRaw')==str(job)]
    Q.need(len(found)==1 and all(found[0][k]==p[k] for k in ('State','ExitCode','UID','ElapsedRaw','AllocCPUS','NodeList','Partition'))
        and value['allocated_core_seconds_observed']==int(p['ElapsedRaw'])*16,'RAW_PARENT_STATE_AND_COST_MATCH_REQUIRED')
    return value

def main_authority(plan):
    refs=plan['main_evidence_references'];copies=Q.load_ref(plan['metadata_relocation_reference'])
    rows=copies['copies'];by_target={row['target_reference']['path']:row for row in rows}
    for value in refs.values():
        Q.need(value in plan['source_references'] and value['path'] in by_target,'EXACT_APPROVED_MAIN_METADATA_COPY_REQUIRED')
        copied=by_target[value['path']];Q.need(value==copied['target_reference'] and all(value[k]==copied['origin_reference'][k] for k in ('bytes','sha256')),'MAIN_METADATA_BYTES_NOT_REWRITTEN')
    inv=Q.load_ref(refs['inventory1093']);uniform=Q.load_ref(refs['uniform1316']);full=Q.load_ref(refs['full414']);closure=Q.load_ref(refs['full414_closure']);compat=Q.load_ref(refs['compat597'])
    Q.need(inv['job_id']=='4521093' and inv['status']=='RAW_FULL_EOF_INVENTORY_COMPLETE_NO_CHEMICAL_SCREENING'
        and inv['raw_complete_SHA_verified'] is True and inv['gzip_EOF_CRC_revalidated'] is True and inv['counts']['records']==C.N
        and inv['counts']['uncompressed_bytes']==C.UNCOMPRESSED_BYTES and inv['counts']['maximum_source_line_bytes']==C.MAX_LINE
        and inv['source_index']['part_count']==C.PARTS,'ACTUAL_MAIN_COMPLETE_RAW500_INVENTORY_REQUIRED')
    Q.need(uniform['job_id']=='4521316' and uniform['population_N']==C.N and uniform['seed']==C.SEED and uniform['rdkit']=='2025.09.5'
        and uniform['uniform']['completed_rows']==10000 and uniform['uniform']['counts']=={'accepted':8773,'chemReject':1223,'technicalUnresolved':4}
        and uniform['synthetic_fixtures']=={'tests_run':5,'failures':0,'errors':0,'skips':0}
        and uniform['longest_is_warm_pool_and_not_in_uniform_mean'] is True,'ACTUAL_UNIFORM10000_FIVE_FIXTURE_AUTHORITY_REQUIRED')
    Q.need(full['job_id']==closure['actual_parent']['JobIDRaw']=='4520414' and full['status']=='FULL_X_RULE_PASS_COMMON_SCOPE_PENDING'
        and closure['actual_parent']['State']=='COMPLETED' and closure['actual_parent']['ExitCode']=='0:0'
        and full['evaluated_records']==15879477 and full['chemical_admission_agreement']==1.0
        and full['conditional_geometry_identity_selection_agreement']==1.0 and full['five_portable_flag_agreement']>=.999
        and all(full['counts'][key]==0 for key in ('native_rule_mismatch','raw_native_rule_mismatch','enriched_native_rule_mismatch','enrichment_metadata_mismatch','unexplained'))
        and full['final_training_or_full_expansion_gate_released'] is False,'ACTUAL414_FULL_REGRESSION_NOT_FINAL_COMMON_RELEASE')
    Q.need(compat['job_id']=='4520597' and compat['status']=='PAIRED_PREFIX_CANDIDATE_EVALUATED_NOT_APPLIED'
        and compat['counts']['classification:OLD_PASS_ALL_FIELDS_PRESERVED']==8198
        and compat['counts']['classification:RECOVERED_CONFIRMED_GENERIC_RING_ORDER']==753
        and compat['counts']['classification:CHEMICAL_REJECTION_UNCHANGED']==1049
        and compat['repair_applied'] is False and compat['pool_modified'] is False,'ACTUAL597_COMPOSITIONAL_PASSTHROUGH_REQUIRED')
    return inv,uniform

def require_startup(plan_path,proof_path):
    plan=Q.load(plan_path);proof=Q.load(proof_path);mode=plan['mode'];Q.need(mode in C.MODES,'EXACT_PUBCHEM_MODE')
    spec=C.MODES[mode];primary=C.HERE/'run.py';wall=plan['wall_seconds'];cap=plan['output_cap_bytes']
    params=C.parameters(mode,*([plan[k] for k in ('first_part','last_part','first_ordinal','last_ordinal')] if mode=='full_shard' else []))
    argv=[plan['python'],'-B','-m',C.MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)]
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
            Q.need(plan['data_references']==[data['source_index']] and review.get('actual_profile_equivalence_and_cost_reviewed') is True,'C_ROOT_PROFILE_COST_REVIEW_REQUIRED')
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
            Q.need(len(limits)==1 and limits[0]['wall_seconds']==wall and limits[0]['output_cap_bytes']==cap,'ROOT_EXACT_SHARD_PROFILE_DERIVED_LIMITS')
    import pyarrow
    Q.need(sys.version.split()[0]=='3.11.14' and pyarrow.__version__=='17.0.0','ACTUAL_ALPHA_PYTHON_AND_ARROW')
    if mode!='inventory':
        from rdkit import rdBase
        Q.need(rdBase.rdkitVersion=='2025.09.5','EXACT_ORIGINAL_RDKIT_VERSION')
    out=Q.literal(plan['output_directory']);Q.need(C.ROOT/'artifacts' in out.parents and not out.exists() and len(str(out))<=1024,'NEW_FINITE_ALPHA_OUTPUT_LEAF')
    return plan,proof
