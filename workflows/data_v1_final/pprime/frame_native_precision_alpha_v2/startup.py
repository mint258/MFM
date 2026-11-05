"""Consume the Root thin-v4 Alpha readonly proof; no queue or proof manufacture."""
from __future__ import annotations
import hashlib,os,pathlib,socket,sys,time
from secondary_cpu_queue_v1 import common as Q

ROOT=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
ENDPOINT='218.192.171.238:22';KEY='pprime_native_precision72_readonly_alpha_v2'
MODULE='frame_native_precision_alpha_v2.run';STAGE='PPRIME_NATIVE72_EXISTING_OUTPUT_DIAGNOSIS'
PLAN='SECONDARY_NATIVE72_READONLY_PLAN_V2';PROOF='SECONDARY_NATIVE72_READONLY_STARTUP_V2'


def startup(plan_path,proof_path,parameters):
    plan_path=pathlib.Path(plan_path);proof_path=pathlib.Path(proof_path)
    plan=Q.load(plan_path);review=Q.load_ref(plan['root_review_reference']);proof=Q.load(proof_path)
    primary=ROOT/'code/frame_native_precision_alpha_v2/run.py'
    argv=[plan['python'],'-B','-m',MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    Q.need(primary==pathlib.Path(sys.modules['__main__'].__file__).absolute() and
        pathlib.Path(sys.executable).absolute()==pathlib.Path(plan['python']).absolute()
        and sys.argv==[str(primary),*argv[4:]],'ACTUAL_ALPHA_PRIMARY_SOURCE_AND_ALL_ARGV_REQUIRED')
    Q.need(plan.get('schema')==PLAN and plan.get('producer_key')==plan.get('scope_key')==KEY and plan.get('stage')==STAGE
        and plan.get('scope_parameters')==parameters and plan.get('endpoint')==ENDPOINT and plan.get('uid')==1264
        and plan.get('run_root')==str(ROOT) and plan.get('node') in Q.NODES and plan.get('cpus')==16
        and plan.get('pilot') is False and plan.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED'
        and plan.get('wall_seconds')==3600 and plan.get('output_cap_bytes')==64<<20
        and plan.get('execution_argv')==argv and plan['startup_proof_path']==str(proof_path),'EXACT_ALPHA_NATIVE72_READONLY_PLAN_REQUIRED')
    Q.need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root','EXACT_ROOT_READONLY_REVIEW_REQUIRED')
    for key in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot',
            'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references'):
        Q.need(plan[key]==review[key],'EXACT_NATIVE72_REVIEW_FIELD_DIFFERS:'+key)
    Q.need(plan['source_references']==review['approved_source_references'],'EXACT_REVIEWED_SOURCE_SET_REQUIRED')
    Q.need(proof.get('schema')==PROOF and proof.get('endpoint')==ENDPOINT and proof.get('uid')==os.getuid()==1264
        and proof['node']==plan['node']==socket.gethostname().split('.')[0]
        and proof['boot_id']==pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'ACTUAL_ALPHA_UID_NODE_BOOT_NOT_MAIN_REQUIRED')
    env=os.environ
    Q.need(env.get('SLURM_JOB_ID')==str(proof['job_id']) and env.get('SLURM_JOB_PARTITION')=='cpu'
        and env.get('SLURM_CPUS_PER_TASK')=='16' and env.get('CUDA_VISIBLE_DEVICES')==''
        and all(env.get(key)=='1' for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),
        'ACTUAL_CPU16_ALPHA_ALLOCATION_AND_LIBRARY_THREADS_REQUIRED')
    Q.need(0<=time.time()-proof['observed_unix_seconds']<=120 and proof['plan_reference']==Q.ref(plan_path)
        and proof['root_review_reference']==plan['root_review_reference'],'FRESH_ROOT_ALPHA_STARTUP_REQUIRED')
    Q.need(proof['request']=={'kind':'analysis','pilot':False,'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
            'wall_seconds':3600,'execution_argv':argv} and proof['memory_limits_requested'] is False
        and proof['exclusive_requested'] is False and proof.get('bounded_readonly_scope_only') is True,'NO_MAIN_PROOF_OR_MEMORY_GENERATION_AUTHORITY')
    declared={row['path']:{key:row[key] for key in ('path','bytes','sha256')} for row in proof['source_target_verification']}
    for value in [*plan['source_references'],*plan['parent_evidence_references'],plan['root_review_reference'],Q.ref(plan_path)]:
        value=Q.normalized(value);Q.need(declared.get(value['path'])==value,'ACTUAL_APPROVED_TARGET_MISSING');Q.verify(value)
    for path in pathlib.Path(primary).parent.iterdir():
        if path.is_file() and path.suffix in {'.py','.json','.md'}:
            value=Q.ref(path);Q.need(value in plan['source_references'] and declared.get(value['path'])==value,'EVERY_LOCAL_ALPHA_PRODUCER_SOURCE_MUST_BE_PINNED')
    for path in (pathlib.Path(__file__).absolute(),pathlib.Path(Q.__file__).absolute(),pathlib.Path(Q.__file__).absolute().parent/'__init__.py'):
        value=Q.ref(path);Q.need(value in plan['source_references'] and declared.get(value['path'])==value,'ACTUAL_STARTUP_AND_BASE_HELPERS_MUST_BE_APPROVED')
    Q.need(plan['relocation_map_reference'] in plan['source_references'],'EXPLICIT_APPROVED_RELOCATION_MAP_REQUIRED')
    Q.need(plan.get('archive_locator_authority_reference')==plan['relocation_map_reference'],
        'EXACT_FIXED_TRANSITIVE_ARCHIVE_AUTHORITY_REQUIRED')
    signer=proof['controller_evidence']
    Q.need(signer['endpoint']==ENDPOINT and signer['uid']==1264 and signer['hostname']=='sonmi'
        and signer['proof_is_not_created_by_scientific_worker'] is True
        and signer['actual_script_reference']==proof['script_reference'],'ACTUAL_ALPHA_LOGIN_CONTROLLER_SIGNER_REQUIRED')
    script=Q.read_small(Q.verify(proof['script_reference'])).decode()
    for line in script.splitlines():
        if line.strip().startswith('#SBATCH'):Q.need(not any(word in line for word in ('--mem','--gres','--gpu','--exclusive')),'NO_EXPLICIT_MEMORY_GPU_OR_EXCLUSIVE')
    job=Q.fields(proof['job_metadata'])
    Q.need(job.get('JobId')==str(proof['job_id']) and job.get('UserId')=='alpha(1264)' and job.get('JobState')=='RUNNING'
        and job.get('NodeList')==plan['node'] and job.get('Partition')=='cpu' and job.get('NumCPUs')=='16'
        and job.get('NumTasks')=='1' and job.get('Requeue')=='0'
        and job.get('Command')==proof['script_reference']['path'] and Q.duration(job.get('TimeLimit',''))==3600,'ACTUAL_RUNNING_ALPHA_SCRIPT_CPU_AND_WALL_REQUIRED')
    gate=proof['actual_gate_process'];proc=pathlib.Path('/proc/self');tail=(proc/'stat').read_text().rsplit(')',1)[1].split()
    Q.need(gate['pid']==os.getpid() and gate['uid']==1264 and gate['start_ticks']==int(tail[19])
        and gate['pgid']==os.getpgrp() and gate['sid']==os.getsid(0)
        and gate['cgroup_sha256']==hashlib.sha256((proc/'cgroup').read_bytes()).hexdigest(),'ACTUAL_ATTESTED_EXEC_GATE_IDENTITY_REQUIRED')
    storage=proof['storage_observation'];Q.load_ref(proof['storage_observation_reference'])
    Q.need(proof['account_free_bytes']==storage['effective_free_bytes']
        and proof['account_free_bytes']-plan['output_cap_bytes']>=200000000000
        and 0<=time.time()-storage['observed_unix_seconds']<=120
        and storage['whole_output_caps_reserved_bytes']>=plan['output_cap_bytes'],'FRESH_ALPHA_STORAGE_AND200GB_REQUIRED')
    Q.need(plan['resource_authority_reference'] in plan['source_references'],'ACTUAL_AUTHORITY_MUST_BE_IN_APPROVED_SOURCES')
    authority=Q.load_ref(plan['resource_authority_reference'])
    Q.need(authority.get('schema')=='USER_AUTHORIZED_SECONDARY_DATA_CLUSTER_V1' and authority.get('status')=='USER_AUTHORIZED'
        and authority.get('endpoint')==ENDPOINT and authority.get('observed_uid')==1264
        and authority.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED','REAL_ALPHA_USER_AUTHORITY_REQUIRED')
    Q.need(plan['data_references']==[],'NO_INVENTED_KNOWN_DATABASE_WHOLE_SHA_USE_FIXED_TRANSITIVE_ARCHIVE_AUTHORITY')
    return plan,proof,declared
