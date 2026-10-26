"""Independent Alpha CPU output readback, never a Main CPU or population claim."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,io,json,os,socket,stat,sys,time
from pathlib import Path

from portable_secondary_uff_v1.bridge import scientific_sha
from portable_secondary_uff_v1.prepare_existing_controls import select_metadata
from portable_secondary_uff_v1.contract import canonical,sha,need,prep_metadata,recipe_equivalence,CONTROL_MODE,MISSING_IDS
from secondary_cpu_queue_v1 import common as queue_common

ROOT=Path('/gfshome/alpha/codex_data_v1_20261026');MAIN_PROJECT=Path('/share/home/zixiao/descriptor_analysis')
MAIN_ENDPOINT='202.38.247.57:22';ALPHA_ENDPOINT='218.192.171.238:22'
MAIN_PREP_JOB='4521182';ALPHA_JOB='1884766';ALPHA_NODE='compute-0-6'
KEY='uff_control16_independent_readback_alpha_v1';MODULE='secondary_uff_readback_alpha_v1.readback'
STAGE='UFF_CONTROL16_INDEPENDENT_READBACK';PLAN='SECONDARY_UFF_CONTROL16_READONLY_PLAN_V1';PROOF='SECONDARY_UFF_CONTROL16_READONLY_STARTUP_V1'
PARAMETERS={'existing_control_count':16,'population_members_added':0,'two_missing_replayed':False,
    'alpha_source_job_id':ALPHA_JOB,'historical_main_preparation_job_id':MAIN_PREP_JOB,
    'readback_endpoint':ALPHA_ENDPOINT,'readback_uid':1264,'new_UFF_QM_LMDB_calls':0,
    'scientific_comparison':'full_packet_canonical_SHA_except_summary_elapsed_seconds'}
VERSIONS={'python':'3.11.14','numpy':'2.2.6','rdkit':'2025.09.5','torch':'2.5.1+cpu','torch_geometric':'2.7.0'}
MAIN_HELPERS_SOURCE={'path':'/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/execution/secondary_uff_acceptance_v1/readback.py',
    'sha256':'d7a634bd8e438a245aac3314de0e0be4603fcfb95447aead4929d9c2cfd56598',
    'unchanged_pure_function_text':['normalized','actual_parent','packet_facts']}


def normalized(value):
    out={key:value[key] for key in ('path','bytes','sha256')}
    need(Path(out['path']).is_absolute() and type(out['bytes']) is int and out['bytes']>=0 and
         isinstance(out['sha256'],str) and len(out['sha256'])==64 and set(out['sha256'])<=set('0123456789abcdef'),
         'EXACT_FILE_REFERENCE_REQUIRED')
    return out


def actual_parent(account,raw,job_id,*,endpoint,uid,node):
    rows=list(csv.DictReader(io.StringIO(raw),delimiter='|'))
    raw_parent=[row for row in rows if row.get('JobIDRaw')==job_id]
    if endpoint==ALPHA_ENDPOINT:
        need(account.get('schema')=='SECONDARY_CPU_ACTUAL_ACCOUNTING_EVIDENCE_V1' and
             account.get('endpoint')==endpoint and account.get('uid')==uid and account.get('job_id')==job_id and
             account.get('actual_terminal') is True and account.get('query_returncode')==0 and
             account['command_argv'][0]=='sacct','ACTUAL_ALPHA_TERMINAL_ACCOUNTING_REQUIRED')
        parents=[account['actual_parent']]
    else:
        need(account.get('schema')=='DATA_V1_OWNED_ACCOUNTING_POINT_IN_TIME_V2' and account.get('query_returncode')==0,
             'ACTUAL_MAIN_OWNED_ACCOUNTING_REQUIRED')
        parents=[row for row in account['actual_parents'] if row.get('JobIDRaw')==job_id]
    need(len(parents)==len(raw_parent)==1,'ONE_EXACT_ENDPOINT_PARENT_AND_RAW_ROW_REQUIRED')
    parent=parents[0]
    for key in ('JobIDRaw','State','ExitCode','ElapsedRaw','AllocCPUS','NodeList','Partition'):
        need(parent[key]==raw_parent[0][key],'ACTUAL_ACCOUNTING_AND_RAW_PARENT_DIFFERS:'+key)
    need(parent['JobIDRaw']==job_id and parent['State']=='COMPLETED' and parent['ExitCode']=='0:0' and
         parent['NodeList']==node and parent['Partition']=='cpu' and int(parent['AllocCPUS'])==16 and
         int(parent['ElapsedRaw'])>=0,'ACTUAL_C0_CPU16_PARENT_REQUIRED')
    if endpoint==ALPHA_ENDPOINT:
        need(parent['UID']==raw_parent[0]['UID']==str(uid) and parent['User']==raw_parent[0]['User']=='alpha',
             'ACTUAL_ALPHA_PARENT_OWNER_REQUIRED')
    elif 'UID' in raw_parent[0]:need(raw_parent[0]['UID']==str(uid),'ACTUAL_MAIN_PARENT_OWNER_DIFFERS')
    seconds=int(parent['ElapsedRaw'])*16
    if endpoint==ALPHA_ENDPOINT:need(account['allocated_core_seconds_observed']==seconds,'ACTUAL_ALPHA_CORE_COST_DIFFERS')
    return {'endpoint':endpoint,'uid':uid,'job_id':job_id,'actual_parent':parent,'allocated_core_seconds':seconds,
        'raw_steps_retained_not_added_to_parent_cost':[row for row in rows if row.get('JobIDRaw','').startswith(job_id+'.')],
        'zero_integer_seconds_not_claimed_true_zero_cost':True}


def packet_facts(packet,mid,expected):
    summary=packet['summary'];conformers=packet['conformers'];pm7=packet['pm7']
    need(summary['molecule_id']==mid and summary['status']=='SUCCESS' and type(summary['seed']) is int and summary['seed']>0 and
         summary['expected_conformers']==expected['expected_conformers'] and summary['heavy_atoms']==expected['heavy_atoms'] and
         len(conformers)==summary['expected_conformers'] and summary['source_record_id'] and summary['atom_order_sha256'],
         'CONTROL_TASK_SEED_SOURCE_ATOM_ORDER_OR_COUNT_DIFFERS')
    need(len({row['sprime_conf_idx'] for row in conformers})==len(conformers) and
         all(row['status']=='SUCCESS' and row['converged'] is True and row['source_record_id']==summary['source_record_id'] and
             row['atom_order_sha256']==summary['atom_order_sha256'] and len(row['geometry_sha256'])==64 for row in conformers) and
         len({row['record_id'] for row in pm7})==len(pm7) and all(len(row['geometry_sha256'])==64 for row in pm7),
         'CONTROL_GEOMETRY_OR_NATIVE_ANCHOR_IDENTITY_DIFFERS')
    return {'seed':summary['seed'],'cohort':summary['cohort'],'source_record_id':summary['source_record_id'],
        'atom_order_sha256':summary['atom_order_sha256'],'heavy_atoms':summary['heavy_atoms'],'expected_conformers':summary['expected_conformers'],
        'uff_geometry_ids_and_hashes':[(row['sprime_conf_idx'],row['geometry_sha256']) for row in conformers],
        'pm7_native_ids_and_hashes':[(row['record_id'],row['geometry_sha256']) for row in pm7]}


def source(value,declared):
    value=normalized(value)
    need(ROOT in Path(value['path']).parents and declared.get(value['path'])==value,'ACTUAL_DECLARED_ALPHA_SMALL_INPUT_REQUIRED')
    queue_common.verify(value);return Path(value['path'])


def small(value,declared):return json.loads(queue_common.read_small(source(value,declared)))


def startup(plan_path,proof_path):
    plan=queue_common.load(plan_path);review=queue_common.load_ref(plan['root_review_reference']);proof=queue_common.load(proof_path)
    primary=ROOT/'code/secondary_uff_readback_alpha_v1/readback.py'
    argv=[plan['python'],'-B','-m',MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    need(Path(__file__).absolute()==primary==Path(sys.modules['__main__'].__file__).absolute() and
         Path(sys.executable).absolute()==Path(plan['python']).absolute() and sys.argv==[str(primary),*argv[4:]],
         'REAL_ALPHA_READBACK_PRIMARY_AND_ALL_ARGUMENTS_REQUIRED')
    need(plan.get('schema')==PLAN and plan.get('producer_key')==plan.get('scope_key')==KEY and plan.get('stage')==STAGE and
         plan.get('scope_parameters')==PARAMETERS and plan.get('endpoint')==ALPHA_ENDPOINT and plan.get('uid')==1264 and
         plan.get('run_root')==str(ROOT) and plan.get('node') in queue_common.NODES and plan.get('cpus')==16 and
         plan.get('pilot') is False and plan.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED' and plan.get('wall_seconds')==600 and
         plan.get('output_cap_bytes')==64<<20 and plan['execution_argv']==argv and plan['startup_proof_path']==str(proof_path),
         'EXACT_INDEPENDENT_ALPHA_CONTROL16_READONLY_PLAN_REQUIRED')
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review.get('reviewer')=='root' and
         review.get('status')=='APPROVED_FOR_EXACT_STAGE','EXACT_ALPHA_READONLY_ROOT_REVIEW_REQUIRED')
    for key in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot',
                'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references'):
        need(plan[key]==review[key],'EXACT_READBACK_ROOT_SCOPE_DIFFERS:'+key)
    need(plan['source_references']==review['approved_source_references'],'EXACT_READBACK_APPROVED_SOURCE_SET_REQUIRED')
    need(proof.get('schema')==PROOF and proof.get('endpoint')==ALPHA_ENDPOINT and proof.get('uid')==os.getuid()==1264 and
         proof['node']==plan['node']==socket.gethostname().split('.')[0] and
         proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'ACTUAL_ALPHA_NOT_MAIN_UID_NODE_BOOT_REQUIRED')
    env=os.environ
    need(env.get('SLURM_JOB_ID')==str(proof['job_id']) and env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('SLURM_CPUS_PER_TASK')=='16' and
         env.get('CUDA_VISIBLE_DEVICES')=='' and all(env.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),
         'ACTUAL_ALPHA_CPU16_AND_LIBRARY_THREADS_REQUIRED')
    need(0<=time.time()-proof['observed_unix_seconds']<=120 and proof['plan_reference']==queue_common.ref(plan_path) and
         proof['root_review_reference']==plan['root_review_reference'],'FRESH_INDEPENDENT_ALPHA_READBACK_PROOF_REQUIRED')
    need(proof['request']=={'kind':'analysis','pilot':False,'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
         'wall_seconds':600,'execution_argv':argv} and proof['memory_limits_requested'] is False and proof['exclusive_requested'] is False and
         proof.get('bounded_readonly_scope_only') is True,'NO_MEMORY_EXCLUSIVE_OR_GENERATION_AUTHORITY')
    declared={row['path']:normalized(row) for row in proof['source_target_verification']}
    for value in [*plan['source_references'],*plan['parent_evidence_references'],plan['root_review_reference'],queue_common.ref(plan_path)]:
        source(value,declared)
    import portable_secondary_uff_v1.bridge as bridge_module
    import portable_secondary_uff_v1.contract as contract_module
    import portable_secondary_uff_v1.prepare_existing_controls as selection_module
    for path in (primary,Path(queue_common.__file__).absolute(),Path(queue_common.__file__).absolute().parent/'__init__.py',
                 Path(bridge_module.__file__).absolute(),Path(bridge_module.__file__).absolute().parent/'__init__.py',
                 Path(contract_module.__file__).absolute(),Path(selection_module.__file__).absolute()):
        reference=queue_common.ref(path)
        need(reference in plan['source_references'],'ACTUAL_IMPORTED_CODE_MUST_BE_IN_ROOT_APPROVED_SOURCES')
        source(reference,declared)
    signer=proof['controller_evidence']
    need(signer['endpoint']==ALPHA_ENDPOINT and signer['uid']==1264 and signer['hostname']=='sonmi' and
         signer['proof_is_not_created_by_scientific_worker'] is True and signer['actual_script_reference']==proof['script_reference'],
         'REAL_ALPHA_LOGIN_CONTROLLER_NOT_WORKER_OR_MAIN_PROOF')
    script=queue_common.read_small(queue_common.verify(proof['script_reference'])).decode()
    for line in script.splitlines():
        if line.strip().startswith('#SBATCH'):need(not any(s in line for s in ('--mem','--gres','--gpu','--exclusive')),'NO_EXPLICIT_MEMORY_GPU_EXCLUSIVE')
    job=queue_common.fields(proof['job_metadata'])
    need(job.get('JobId')==str(proof['job_id']) and job.get('UserId')=='alpha(1264)' and job.get('JobState')=='RUNNING' and
         job.get('NodeList')==plan['node'] and job.get('Partition')=='cpu' and job.get('NumCPUs')=='16' and job.get('NumTasks')=='1' and
         job.get('Requeue')=='0' and job.get('Command')==proof['script_reference']['path'] and queue_common.duration(job.get('TimeLimit',''))==600,
         'ACTUAL_ALPHA_RUNNING_SCRIPT_CPU_AND_WALL_REQUIRED')
    gate=proof['actual_gate_process'];proc=Path('/proc/self');raw=(proc/'stat').read_text();tail=raw[raw.rfind(')')+2:].split()
    need(gate['pid']==os.getpid() and gate['uid']==1264 and gate['start_ticks']==int(tail[19]) and gate['pgid']==os.getpgrp() and
         gate['sid']==os.getsid(0) and gate['cgroup_sha256']==sha((proc/'cgroup').read_bytes()),'ATTESTED_EXEC_GATE_PROCESS_IDENTITY_REQUIRED')
    storage=proof['storage_observation'];queue_common.load_ref(proof['storage_observation_reference'])
    need(proof['account_free_bytes']==storage['effective_free_bytes'] and proof['account_free_bytes']-plan['output_cap_bytes']>=200000000000 and
         0<=time.time()-storage['observed_unix_seconds']<=120 and storage['whole_output_caps_reserved_bytes']>=plan['output_cap_bytes'],
         'FRESH_ALPHA_STORAGE_ALL_CAPS_AND200GB_REQUIRED')
    authority=small(plan['resource_authority_reference'],declared)
    need(authority.get('schema')=='USER_AUTHORIZED_SECONDARY_DATA_CLUSTER_V1' and authority.get('status')=='USER_AUTHORIZED' and
         authority.get('endpoint')==ALPHA_ENDPOINT and authority.get('observed_uid')==1264 and
         authority.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED','ACTUAL_ALPHA_USER_AUTHORITY_REQUIRED')
    return plan,proof,declared


def metadata_resolver(inputs,declared):
    mapping={}
    for row in inputs['metadata_copies']:
        old,new=normalized(row['origin_reference']),normalized(row['target_locator'])
        need(MAIN_PROJECT in Path(old['path']).parents and ROOT in Path(new['path']).parents and
             old['bytes']==new['bytes'] and old['sha256']==new['sha256'],'MAIN_METADATA_COPY_BYTES_CHANGED_OR_FAKE_ALIAS')
        key=canonical(old);need(key not in mapping,'DUPLICATE_MAIN_METADATA_ORIGIN');source(new,declared);mapping[key]=new
    def target(value):
        value=normalized(value)
        if ROOT in Path(value['path']).parents:return value
        need(canonical(value) in mapping,'MAIN_ORIGIN_HAS_NO_EXACT_ALPHA_COPY_LOCATOR');return mapping[canonical(value)]
    def read(value):return small(target(value),declared)
    return target,read


def read_packet(reference,data_refs):
    reference=normalized(reference);path=Path(reference['path'])
    need(ROOT in path.parents and path.name.endswith('.json.gz') and not any(p.is_symlink() for p in (path,*path.parents)) and
         data_refs.get(str(path))==reference,'EXACT_DECLARED_ALPHA_PACKET_ONLY')
    def identity(info):return {'device':info.st_dev,'inode':info.st_ino,'bytes':info.st_size,'mtime_ns':info.st_mtime_ns,'uid':info.st_uid}
    before=path.stat();frame=identity(before)
    need(stat.S_ISREG(before.st_mode) and before.st_uid==1264 and before.st_size==reference['bytes'],'ACTUAL_ALPHA_PACKET_OWNER_OR_SIZE_DIFFERS')
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):digest.update(block)
    need(digest.hexdigest()==reference['sha256'] and identity(path.stat())==frame,'FULL_PACKET_SHA_OR_ALPHA_IDENTITY_CHANGED')
    with gzip.open(path,'rb') as stream:raw=stream.read((1<<30)+1)
    need(len(raw)<=1<<30 and identity(path.stat())==frame,'PACKET_INFLATED_CAP_OR_ALPHA_IDENTITY_CHANGED')
    return json.loads(raw),{'actual_alpha_reference':reference,'actual_alpha_file_identity':frame,
        'full_compressed_sha_verified':True,'gzip_EOF_CRC_verified':True,'uncompressed_bytes':len(raw),
        'main_original_file_view_claimed':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--startup-proof',type=Path,required=True)
    args=parser.parse_args();started=time.monotonic();plan,proof,declared=startup(args.plan,args.startup_proof)
    inputs=small(plan['inputs_reference'],declared)
    need(inputs.get('schema')=='SECONDARY_UFF_CONTROL16_ALPHA_READBACK_INPUTS_V1' and
         inputs.get('status')=='ROOT_STAGED_EXACT_COPIES_FOR_ALPHA_CPU_READBACK' and inputs.get('reviewer')=='root',
         'EXACT_ALPHA_READBACK_INPUTS_REQUIRED')
    target,read=metadata_resolver(inputs,declared)
    prep=read(inputs['main_preparation_origin_reference']);expected=prep_metadata(prep)
    closed=read(prep['original_complete_packages_reference'])
    need(len(closed)==len({row['molecule_id'] for row in closed})==334 and not {row['molecule_id'] for row in closed}&MISSING_IDS,
         'EXACT_EXISTING334_SELECTION_METADATA_REQUIRED')
    selected,selection=select_metadata(closed)
    need(len(selected)==16 and [row['molecule_id'] for row in selected]==prep['allowed_original_control_ids'],'FIXED32_30_60_HASH_SELECTION_DIFFERS')
    for row in selected:
        golden=expected[row['molecule_id']]
        need(normalized(row['reference'])==normalized(golden['baseline_packet_reference']) and row['file_identity']==golden['baseline_file_identity'] and
             row['summary']['heavy_atoms']==golden['heavy_atoms'] and row['summary']['expected_conformers']==golden['expected_conformers'] and
             row['science_worker_seconds']==golden['observed_main_elapsed_seconds'],'ORIGINAL_MAIN_METADATA_AND_GOLDEN_DIFFERS')
    runtime=prep['main_preparation_runtime'];old_startup=read(prep['root_preflight_reference'])
    need(runtime['uid']==old_startup['uid']==1278 and runtime['job_id']==str(old_startup['job_id'])==MAIN_PREP_JOB and
         old_startup['node']==runtime['node'] and old_startup['schema']=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1',
         'HISTORICAL_MAIN1182_EVIDENCE_REQUIRED_NOT_CURRENT_ALPHA_ADMISSION')
    main_account=read(inputs['main_accounting_origin_reference'])
    main_raw=queue_common.read_small(source(target(main_account['raw_sacct_reference']),declared)).decode()
    main_cost=actual_parent(main_account,main_raw,MAIN_PREP_JOB,endpoint=MAIN_ENDPOINT,uid=1278,node=runtime['node'])
    submission=read(main_cost['actual_parent']['receipt_reference'])
    need(str(submission['job_id'])==MAIN_PREP_JOB and submission['sbatch_returncode']==0,'ACTUAL_HISTORICAL_MAIN_SUBMISSION_REQUIRED')
    alpha=small(inputs['alpha_receipt_reference'],declared);deployment=small(inputs['alpha_deployment_map_reference'],declared)
    alpha_startup=small(inputs['alpha_startup_proof_reference'],declared);alpha_account=small(inputs['alpha_accounting_reference'],declared)
    need(normalized(inputs['alpha_deployment_map_reference'])==normalized(alpha['deployment_map_reference']) and
         normalized(inputs['alpha_startup_proof_reference'])==normalized(alpha['startup_proof_reference']) and
         normalized(inputs['alpha_raw_sacct_reference'])==normalized(alpha_account['raw_sacct_reference']),
         'EXACT_EXISTING_ALPHA1884766_METADATA_REFERENCES_REQUIRED')
    alpha_raw=queue_common.read_small(source(inputs['alpha_raw_sacct_reference'],declared)).decode()
    alpha_cost=actual_parent(alpha_account,alpha_raw,ALPHA_JOB,endpoint=ALPHA_ENDPOINT,uid=1264,node=ALPHA_NODE)
    endpoint_id=sha(canonical(deployment['target']));target_context=deployment['target']
    need(target_context['ssh_host']=='218.192.171.238' and target_context['ssh_user']=='alpha' and target_context['uid']==1264 and
         target_context['deployment_root']==str(ROOT) and deployment['endpoint_id']==prep['endpoint_id']==endpoint_id and
         alpha['endpoint_id']==alpha_startup['endpoint_id']==endpoint_id and alpha['uid']==alpha_startup['uid']==1264 and
         str(alpha['job_id'])==str(alpha_startup['job_id'])==ALPHA_JOB and alpha['node']==alpha_startup['node']==ALPHA_NODE and
         alpha_startup['schema']=='SECONDARY_PORTABLE_UFF_CONTROL16_STARTUP_V1' and
         normalized(alpha_startup['deployment_map_reference'])==normalized(alpha['deployment_map_reference']),
         'DO_NOT_MIX_ENDPOINT_UID_JOB_OR_MAP_IDENTITIES')
    need(alpha['schema']=='SECONDARY_PORTABLE_UFF_CONTROL16_RECEIPT_V1' and alpha['mode']==deployment['mode']==CONTROL_MODE and
         alpha['status']=='CONTROL16_EXACT_SCIENCE_MATCH_REQUIRES_MAIN_SOFTWARE_ACCEPTANCE' and alpha['formal_generation_authorized'] is False and
         deployment['formal_generation_authorized'] is False and alpha['population_members_added']==0 and alpha['two_missing_replayed'] is False and
         alpha['current_main_recovery_2plus14_scope_changed'] is False and alpha['main_lmdb_or_once_ledger_opened'] is False and
         alpha['main_unified_acceptance_granted'] is False and alpha['automatic_retry'] is False and not alpha['errors'] and
         alpha['soft_memavailable_denial'] is False and alpha['actual_target_scientific_sources_verified_byte_identical'] is True,
         'EXACT_COMPLETE_BOUNDED_QA_ONLY_NO_FORMAL_OR_POPULATION_AUTHORITY')
    need(normalized(deployment['main_preparation_origin_reference'])==normalized(inputs['main_preparation_origin_reference']) and
         normalized(alpha['main_preparation_reference'])==normalized(deployment['main_preparation_target_locator']) and
         all(alpha['main_preparation_reference'][k]==inputs['main_preparation_origin_reference'][k] for k in ('bytes','sha256')),
         'ORIGINAL_MAIN_PREPARATION_LINEAGE_REQUIRED')
    recipe=read(deployment['original_recipe_reference'])
    need(deployment['original_recipe_reference']['bytes']==3629 and deployment['original_recipe_reference']['sha256']==
         'cfd153fb524ad823d3903b0ff7d78e402bbbcb74e124136b4bfeb3035279407a','EXACT_ORIGINAL_RECIPE_REQUIRED')
    science=deployment['science_sources'];names={'common.py','science.py','selection.py','statistics_tools.py','run_pilot.py','sprime_v6.py','prepare.py'}
    need(len(science)==7 and {row['basename'] for row in science}==names,'EXACT_SEVEN_ORIGINAL_SCIENCE_SOURCES_REQUIRED')
    for row in science:
        local=target(row['origin_reference']);source(local,declared)
        need(local==normalized(row['target_locator']) and all(row['origin_reference'][k]==local[k] for k in ('bytes','sha256')),
             'SEVEN_SCIENCE_SOURCE_BYTES_OR_ALPHA_LOCATORS_CHANGED')
    need(normalized(inputs['alpha_deployed_recipe_reference'])==normalized(deployment['recipe_target_locator']) and
         canonical(deployment['original_recipe_value'])==canonical(recipe),'EXACT_ACTUAL_ALPHA_RECIPE_REFERENCE_REQUIRED')
    deployed_recipe=small(inputs['alpha_deployed_recipe_reference'],declared)
    recipe_check=recipe_equivalence(recipe,deployed_recipe,{row['origin_reference']['path']:row['target_locator'] for row in science},ROOT/'outputs')
    fee_origin=normalized(inputs['fee_override_origin_reference']);fee_target=target(fee_origin);source(fee_target,declared)
    executions={row['molecule_id']:row for row in alpha['executions']};copies={row['molecule_id']:row for row in inputs['baseline_copies']}
    need(len(executions)==len(alpha['executions'])==len(copies)==len(inputs['baseline_copies'])==16 and
         set(executions)==set(copies)==set(expected) and not set(expected)&MISSING_IDS,'EXACT16_BOTH_GROUPS_NO_MISSING_OR_DUPLICATE')
    need(len({(row['worker_identity']['pid'],row['worker_identity']['start_ticks']) for row in executions.values()})==16,'ACTUAL16_DISTINCT_QA_WORKERS_REQUIRED')
    data_refs={row['path']:normalized(row) for row in plan['data_references']}
    needed=[normalized(row['packet_reference']) for row in executions.values()]+[normalized(row['target_locator']) for row in copies.values()]
    need(len(data_refs)==len(plan['data_references'])==32 and {canonical(row) for row in needed}=={canonical(row) for row in plan['data_references']},
         'EXACT32_ALPHA_PACKET_LOCATORS_ONLY')
    verified=[]
    for mid in prep['allowed_original_control_ids']:
        need(time.monotonic()-started<540,'STOP_NEW_READBACK_WORK_WITH60SECOND_DRAIN_MARGIN')
        execution=executions[mid];golden=expected[mid];copy=copies[mid];identity=execution['worker_identity']
        need(identity['uid']==1264 and str(identity['job_id'])==ALPHA_JOB and identity['endpoint_id']==endpoint_id and
             execution['main_golden_exact_match'] is True and execution['task_sha256']==golden['task_sha256'] and execution['actual_versions']==VERSIONS,
             'ACTUAL_QA_TASK_ENVIRONMENT_OR_WORKER_DIFFERS')
        old,new=normalized(copy['origin_reference']),normalized(copy['target_locator'])
        need(old==normalized(golden['baseline_packet_reference']) and all(old[k]==new[k] for k in ('bytes','sha256')),
             'ORIGINAL_MAIN_BASELINE_AND_ALPHA_COPY_BYTES_DIFFER')
        actual,actual_check=read_packet(execution['packet_reference'],data_refs);baseline,baseline_check=read_packet(new,data_refs)
        signature=scientific_sha(actual);baseline_signature=scientific_sha(baseline)
        need(signature==baseline_signature==execution['scientific_sha256_excluding_elapsed_seconds']==golden['scientific_sha256_excluding_elapsed_seconds'],
             'EXACT_FOUR_WAY_FULL_SCIENTIFIC_SHA_MISMATCH_NO_TOLERANCE')
        facts=packet_facts(actual,mid,golden);need(canonical(facts)==canonical(packet_facts(baseline,mid,golden)),'SEED_GEOMETRY_ATOM_ORDER_OR_NATIVE_ID_DIFFERS')
        verified.append({'molecule_id':mid,'task_sha256':golden['task_sha256'],'scientific_sha256_excluding_elapsed_seconds':signature,
            'alpha1884766_original_packet_readback':actual_check,'main_origin_reference':old,'alpha_copy_of_main_packet_readback':baseline_check,
            'historical_main_file_identity_from1182':golden['baseline_file_identity'],'main_original_fstat_read_on_alpha':False,
            'seed_geometry_and_native_identity':facts})
    output=queue_common.literal(plan['output_directory']);need(ROOT/'artifacts' in output.parents and not output.exists(),'NEW_ALPHA_READBACK_OUTPUT_REQUIRED')
    output.mkdir(parents=True,mode=0o700)
    report={'schema':'SECONDARY_UFF_CONTROL16_INDEPENDENT_ALPHA_READBACK_V1',
        'status':'ALPHA_INDEPENDENT_CONTROL16_EXACT_READBACK_COMPLETE_REQUIRES_ROOT_UNIFIED_SOFTWARE_SCOPE_REVIEW',
        'readback_endpoint':ALPHA_ENDPOINT,'readback_uid':os.getuid(),'readback_job_id':str(proof['job_id']),'readback_node':proof['node'],
        'plan_reference':queue_common.ref(args.plan),'startup_proof_reference':queue_common.ref(args.startup_proof),
        'inputs_reference':plan['inputs_reference'],'mode':CONTROL_MODE,'endpoint_id':endpoint_id,'controls':16,
        'verified_controls':verified,'actual_alpha_versions':VERSIONS,'comparison_excludes_only':'summary.elapsed_seconds',
        'recipe_equivalence':recipe_check,'original_recipe_reference':deployment['original_recipe_reference'],'original_seven_science_sources':science,
        'selection_rule':selection['selection_rule'],'eligible_existing_controls':selection['eligible_count'],
        'historical_main1182_actual_parent_cost':main_cost,'alpha1884766_actual_parent_cost':alpha_cost,
        'this_readback_terminal_cost':'PENDING_ROOT_ACTUAL_ALPHA_SACCT_PARENT_AND_STEPS',
        'fee_override_origin_reference_unchanged':fee_origin,'fee_override_actual_alpha_copy':fee_target,'quality_gates_changed_or_waived':False,
        'main_cpu_execution_claimed':False,'main_uid1278_execution_claimed':False,'root_unified_software_scope_review_granted':False,
        'population_members_added':0,'two_missing_replayed':False,'readback_UFF_QM_pickle_LMDB_onceledger_calls':0,
        'formal_generation_authorized':False,'all_molecules_programs_or_formal_data_claimed_passed':False,
        'alpha_original_map_receipt_or_reports_modified':False,'pure_helper_source':MAIN_HELPERS_SOURCE,'elapsed_seconds':time.monotonic()-started}
    reference=queue_common.write_new(output/'readback.json',report)
    need((output/'readback.json').stat().st_size+output.stat().st_size<=plan['output_cap_bytes'],'READBACK_OUTPUT_CAP_EXCEEDED')
    print(json.dumps({'status':report['status'],'readback_endpoint':ALPHA_ENDPOINT,'readback_uid':1264,
        'readback_job_id':str(proof['job_id']),'report_reference':reference,'population_members_added':0,'formal_generation_authorized':False}))


if __name__=='__main__':main()
