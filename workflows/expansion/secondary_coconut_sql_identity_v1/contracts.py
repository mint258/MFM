"""New actual Alpha phase proof; reuse only frozen small-file/producer helpers."""
import csv,io,os,socket,sys,time
from pathlib import Path
from secondary_coconut_sql_inventory_v1 import contracts as base

ROOT,UID,ENDPOINT=base.ROOT,base.UID,base.ENDPOINT
need,literal,pin,load,verify,verify_pin,write_new,frame=base.need,base.literal,base.pin,base.load,base.verify,base.verify_pin,base.write_new,base.frame
KEY='coconut_sql_identity_inventory_alpha_v1';MODULE='secondary_coconut_sql_identity_v1.run'

def parameters(mode,profile_limit):
    need(mode in ('profile','full'),'EXACT_INVENTORY_MODE_REQUIRED')
    need(type(profile_limit) is int and (16*1024**2<=profile_limit<base.SQL_BYTES if mode=='profile' else profile_limit==0),'EXACT_FINITE_PROFILE_LIMIT_REQUIRED')
    return {'mode':mode,'profile_limit_bytes':profile_limit,'stop_at_complete_logical_record':True,
        'maximum_profile_boundary_overshoot_bytes':64*1024**2,'maximum_selected_field_bytes':1024**2,
        'input_chunk_bytes':1024**2,'SQL_metadata_statement_cap_bytes':1024**2,
        'decode_or_persist_nonidentity_values':False,'execute_downloaded_SQL':False,'chemical_normalization':False,
        'all_physical_statuses_and_invalid_entries_retained':True,'unpublished_hard_deleted_history_required':False,
        'algorithm_self_RSS_softcap_bytes':2*1024**3,'runtime_MemAvailable_min_fraction':.15,
        'cost_overrun_action':'REPORT_AND_CONTINUE'}

def startup(plan_path,proof_path,primary_source):
    plan=load(plan_path);proof=load(proof_path);review=verify(plan['root_review_reference'])
    mode=plan['mode'];pilot=mode=='profile';stage='SQL_IDENTITY_PROJECTION_PROFILE' if pilot else 'SQL_IDENTITY_PROJECTION_FULL'
    cap=2*1024**3 if pilot else 64*1024**3
    need(plan.get('schema')=='SECONDARY_COCONUT_SQL_IDENTITY_INVENTORY_PLAN_V1' and plan.get('producer_key')==plan.get('scope_key')==KEY and
        plan.get('stage')==stage and plan.get('pilot') is pilot and plan.get('endpoint')==ENDPOINT and plan.get('uid')==UID and
        plan.get('run_root')==str(ROOT) and plan.get('node') in base.NODES and plan.get('cpus')==16 and
        plan.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED' and type(plan.get('wall_seconds')) is int and
        0<plan['wall_seconds']<=172800 and plan['wall_seconds']%60==0 and plan.get('output_cap_bytes')==cap and
        plan['scope_parameters']==parameters(mode,plan['scope_parameters']['profile_limit_bytes']),'EXACT_PHASE_SPECIFIC_INVENTORY_PLAN_REQUIRED')
    primary=ROOT/'code/secondary_coconut_sql_identity_v1/run.py'
    argv=[plan['python'],'-B','-m',MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    need(Path(primary_source).absolute()==primary==Path(sys.modules['__main__'].__file__).absolute() and
        Path(sys.executable).absolute()==Path(plan['python']).absolute() and sys.argv==[str(primary),*argv[4:]] and
        plan['execution_argv']==argv and plan['startup_proof_path']==str(proof_path),'REAL_MAIN_AND_COMPLETE_PHASE_ARGV_REQUIRED')
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and
        review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root','EXACT_ROOT_INVENTORY_REVIEW_REQUIRED')
    for k in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot',
              'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references'):
        need(plan[k]==review[k],'ROOT_EXACT_PHASE_FIELD_DIFFERS:'+k)
    need(plan['source_references']==review['approved_source_references'],'EXACT_REVIEWED_SOURCE_SET_REQUIRED')
    need(proof.get('schema')=='SECONDARY_COCONUT_SQL_IDENTITY_INVENTORY_STARTUP_V1' and proof.get('endpoint')==ENDPOINT and
        proof.get('uid')==os.getuid()==UID and proof['node']==plan['node']==socket.gethostname().split('.')[0] and
        proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and
        0<=time.time()-proof['observed_unix_seconds']<=120,'ACTUAL_FRESH_ALPHA_PHASE_IDENTITY_REQUIRED')
    need(proof['plan_reference']==pin(plan_path) and proof['root_review_reference']==plan['root_review_reference'] and
        proof['request']=={'kind':'analysis','pilot':pilot,'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
                          'wall_seconds':plan['wall_seconds'],'execution_argv':argv},'INDEPENDENT_EXACT_PHASE_REQUEST_PROOF')
    env=os.environ
    need(env.get('SLURM_JOB_ID')==str(proof['job_id']) and env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('SLURM_CPUS_PER_TASK')=='16' and
        env.get('CUDA_VISIBLE_DEVICES')=='' and all(env.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')) and
        proof['memory_limits_requested'] is False and proof['exclusive_requested'] is False,'REAL_CPU16_DEFAULT_MEMORY_NO_GPU')
    declared={r['path']:r for r in proof['source_target_verification']}
    for ref in [*plan['source_references'],*plan['parent_evidence_references'],plan['root_review_reference'],pin(plan_path)]:
        need(declared.get(ref['path'])==ref,'ACTUAL_PHASE_SOURCE_NOT_BOUND');verify_pin(ref)
    for path in (primary,primary.parent/'contracts.py',primary.parent/'copy_text.py',primary.parent/'__init__.py',
                 ROOT/'code/secondary_coconut_sql_inventory_v1/probe.py',ROOT/'code/secondary_coconut_sql_inventory_v1/contracts.py'):
        need(pin(path) in plan['source_references'],'ACTUAL_REUSED_AND_NEW_SOURCE_PINS_REQUIRED')
    need(pin(ROOT/'code/secondary_coconut_sql_inventory_v1/__init__.py') in plan['source_references'],'FROZEN_PROBE_PACKAGE_SOURCE_REQUIRED')
    need(Path(__file__).absolute()==primary.parent/'contracts.py','ACTUAL_IMPORTED_PHASE_CONTRACT_PATH')
    origin=proof['controller_evidence']
    need(origin['endpoint']==ENDPOINT and origin['uid']==UID and origin['hostname']=='sonmi' and
        origin['proof_is_not_created_by_scientific_worker'] is True and origin['actual_script_reference']==proof['script_reference'],
        'INDEPENDENT_LOGIN_CONTROLLER_REQUIRED')
    script=base.verify_text(proof['script_reference'])
    for line in script.splitlines():
        if line.strip().startswith('#SBATCH'):need(not any(k in line for k in ('--mem','--gres','--gpu','--exclusive')),'NO_MEMORY_EXCLUSIVE_GPU')
    job=base.fields(proof['job_metadata'])
    need(job.get('JobId')==str(proof['job_id']) and job.get('UserId')=='alpha(1264)' and job.get('JobState')=='RUNNING' and
        job.get('NodeList')==plan['node'] and job.get('Partition')=='cpu' and job.get('NumCPUs')=='16' and job.get('NumTasks')=='1' and
        job.get('Requeue')=='0' and job.get('Command')==proof['script_reference']['path'] and base.wall(job.get('TimeLimit',''))==plan['wall_seconds'],
        'ACTUAL_OWN_SCRIPT_JOB_AND_PHASE_WALL_REQUIRED')
    gate=proof['actual_gate_process'];raw=Path('/proc/self/stat').read_text();tail=raw[raw.rfind(')')+2:].split()
    import hashlib
    need(gate['pid']==os.getpid() and gate['uid']==UID and gate['start_ticks']==int(tail[19]) and gate['pgid']==os.getpgrp() and gate['sid']==os.getsid(0) and
        gate['cgroup_sha256']==hashlib.sha256(Path('/proc/self/cgroup').read_bytes()).hexdigest(),'SAME_ATTESTED_EXEC_GATE_PROCESS_REQUIRED')
    storage=proof['storage_observation'];verify_pin(proof['storage_observation_reference'])
    need(proof['account_free_bytes']==storage['effective_free_bytes'] and proof['account_free_bytes']-cap>=200000000000 and
        storage['whole_output_caps_reserved_bytes']>=cap and 0<=time.time()-storage['observed_unix_seconds']<=120,'FRESH_ALL_CAPS200GB_STORAGE_REQUIRED')
    authority=verify(plan['resource_authority_reference'])
    need(authority.get('schema')=='USER_AUTHORIZED_SECONDARY_DATA_CLUSTER_V1' and authority.get('status')=='USER_AUTHORIZED' and
        authority.get('endpoint')==ENDPOINT and authority.get('observed_uid')==UID and authority.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED','ACTUAL_ALPHA_RESOURCE_AUTHORITY')
    payload,upstream=base.producer(plan)
    probe=verify(plan['format_probe_receipt_reference']);account=verify(plan['format_probe_accounting_reference'])
    need(probe['job_id']=='1884767' and probe['status']=='BOUNDED_SQL_SCHEMA_OBSERVED_NO_LOGICAL_IDENTITY_ACCEPTANCE' and
        probe['input_SQL_reference_from_actual_producer']==payload and probe['schema_observations']==plan['schema_observations_reference'] and
        account['query_returncode']==0 and account['actual_parent']['JobIDRaw']=='1884767' and account['actual_parent']['State']=='COMPLETED' and
        account['actual_parent']['ExitCode']=='0:0' and account['actual_parent']['UID']==str(UID),'ACTUAL_FORMAT1884767_C0_REQUIRED')
    raw_account=base.verify_text(account['raw_sacct_reference']);rows=list(csv.DictReader(io.StringIO(raw_account),delimiter='|'))
    parents=[r for r in rows if r.get('JobIDRaw')=='1884767']
    need(len(parents)==1 and all(parents[0][k]==account['actual_parent'][k] for k in ('State','ExitCode','UID','ElapsedRaw','AllocCPUS','NodeList','Partition')),
        'ACTUAL_FORMAT_PARENT_RAW_SACCT_REQUIRED')
    schema=verify(plan['schema_observations_reference'])
    need(len(schema['tables'])==15 and all(t['complete_CREATE_TABLE_in_bounded_region'] for t in schema['tables']) and
        schema['actual_prefix_bytes']==16*1024**2 and schema['standard_conforming_strings_markers']==['ON'],'EXACT_OBSERVED_SCHEMA_SCOPE_REQUIRED')
    upstream['format_probe_current_frame']=probe['current_fstat_after']
    if not pilot:
        profile_ref=plan['accepted_profile_receipt_reference'];profile=verify(profile_ref)
        need(profile_ref in plan['parent_evidence_references'] and profile['mode']=='profile' and profile['status']=='BOUNDED_SQL_IDENTITY_PROJECTION_PROFILE_COMPLETE' and
            profile['input_reference']==payload and profile['scope_key']==KEY and review.get('actual_profile_cost_and_coverage_reviewed') is True,
            'FULL_REQUIRES_ACTUAL_SAME_KERNEL_PROFILE_AND_ROOT_COST_REVIEW')
        current_kernel=[pin(primary.parent/name) for name in ('__init__.py','contracts.py','copy_text.py','run.py')]
        need(profile['kernel_source_references']==current_kernel,'PROFILE_AND_FULL_KERNEL_SOURCE_BYTES_DIFFER')
        account_ref=plan['accepted_profile_accounting_reference'];accepted=verify(account_ref)
        need(account_ref in plan['parent_evidence_references'] and accepted['endpoint']==ENDPOINT and accepted['uid']==UID and
            accepted['query_returncode']==0 and accepted['actual_parent']['JobIDRaw']==profile['job_id'] and
            accepted['actual_parent']['State']=='COMPLETED' and accepted['actual_parent']['ExitCode']=='0:0' and
            accepted['actual_parent']['UID']==str(UID) and accepted['actual_parent']['AllocCPUS']=='16','ACTUAL_PROFILE_C0_PARENT_COST_REQUIRED')
        raw=base.verify_text(accepted['raw_sacct_reference']);rows=list(csv.DictReader(io.StringIO(raw),delimiter='|'))
        matching=[r for r in rows if r.get('JobIDRaw')==profile['job_id']]
        need(len(matching)==1 and all(matching[0][k]==accepted['actual_parent'][k] for k in
            ('State','ExitCode','UID','ElapsedRaw','AllocCPUS','NodeList','Partition')) and
            accepted['allocated_core_seconds_observed']==int(matching[0]['ElapsedRaw'])*16,'RAW_PROFILE_PARENT_ALLOCATION_COST_DIFFERS')
    return plan,proof,payload,upstream,schema
