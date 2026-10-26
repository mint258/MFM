"""Consume one exact Alpha fresh readonly proof using the existing base helpers."""
from __future__ import annotations
import hashlib,os,pathlib,socket,sys,time
from secondary_cpu_queue_v1 import common as Q
from . import contract as C


def require_startup(plan_path,proof_path):
    plan_path=Q.literal(plan_path);proof_path=Q.literal(proof_path)
    plan=Q.load(plan_path);review=Q.load_ref(plan['root_review_reference']);proof=Q.load(proof_path)
    primary=C.HERE/'run.py'
    argv=[plan['python'],'-B','-m',C.MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    Q.need(primary==pathlib.Path(sys.modules['__main__'].__file__).absolute()
        and pathlib.Path(sys.executable).absolute()==pathlib.Path(plan['python']).absolute()
        and sys.argv==[str(primary),*argv[4:]],'ACTUAL_ALPHA_PRIMARY_PYTHON_AND_FULL_ARGV_REQUIRED')
    Q.need(plan.get('schema')==C.PLAN and plan.get('producer_key')==plan.get('scope_key')==C.KEY
        and plan.get('stage')==C.STAGE and plan.get('scope_parameters')==C.SCOPE
        and plan.get('kind','analysis')=='analysis' and plan.get('endpoint')==Q.ENDPOINT
        and plan.get('uid')==1264 and plan.get('run_root')==str(C.ROOT) and plan.get('node') in Q.NODES
        and plan.get('cpus')==16 and plan.get('pilot') is False
        and plan.get('memory_policy')==Q.POLICY and plan.get('wall_seconds')==600
        and plan.get('output_cap_bytes')==32<<20 and plan.get('data_references')==C.DATA
        and plan.get('execution_argv')==argv and plan['startup_proof_path']==str(proof_path),
        'EXACT_UNIQUE_INVARIANTS_SCOPE_RESOURCES_AND_TWO_BODY_LOCATORS_REQUIRED')
    Q.need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root','EXACT_ROOT_READONLY_REVIEW_REQUIRED')
    for key in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy',
            'pilot','wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references'):
        Q.need(plan[key]==review[key],'EXACT_REVIEW_FIELD_DIFFERS:'+key)
    Q.need(plan['source_references']==review['approved_source_references'],'EXACT_REVIEWED_SOURCE_SET_REQUIRED')
    body_paths={item['path'] for item in C.DATA}
    Q.need(not any(item['path'] in body_paths for item in [*plan['source_references'],*plan['parent_evidence_references']]),
        'TWO_BODY_LOCATORS_MUST_NOT_BE_HASHED_AS_STARTUP_SOURCE_METADATA')
    Q.need(proof.get('schema')==C.PROOF and proof.get('endpoint')==Q.ENDPOINT and proof.get('uid')==os.getuid()==1264
        and proof['node']==plan['node']==socket.gethostname().split('.')[0]
        and proof['boot_id']==pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        and proof.get('scope_key')==C.KEY and proof.get('stage')==C.STAGE,'ACTUAL_ALPHA_SCOPE_UID_NODE_BOOT_REQUIRED')
    env=os.environ
    Q.need(env.get('SLURM_JOB_ID')==str(proof['job_id']) and env.get('SLURM_JOB_PARTITION')=='cpu'
        and env.get('SLURM_CPUS_PER_TASK')=='16' and env.get('CUDA_VISIBLE_DEVICES')==''
        and all(env.get(key)=='1' for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),
        'CPU16_NO_GPU_AND_LIBRARY_THREADS_ONE_REQUIRED')
    Q.need(0<=time.time()-proof['observed_unix_seconds']<=120 and proof['plan_reference']==Q.ref(plan_path)
        and proof['root_review_reference']==plan['root_review_reference'],'FRESH_ROOT_STARTUP_BOUND_TO_EXACT_PLAN_REQUIRED')
    Q.need(proof['request']=={'kind':'analysis','pilot':False,'cpus':16,'memory_policy':Q.POLICY,
            'wall_seconds':600,'execution_argv':argv} and proof['memory_limits_requested'] is False
        and proof['exclusive_requested'] is False and proof.get('bounded_readonly_scope_only') is True,
        'NO_EXPLICIT_MEMORY_EXCLUSIVE_OR_GENERATION_AUTHORITY')
    declared={row['path']:{key:row[key] for key in ('path','bytes','sha256')} for row in proof['source_target_verification']}
    for value in [*plan['source_references'],*plan['parent_evidence_references'],plan['root_review_reference'],Q.ref(plan_path)]:
        value=Q.normalized(value);Q.need(declared.get(value['path'])==value,'ACTUAL_APPROVED_SOURCE_TARGET_MISSING');Q.verify(value)
    for value in [C.CONFIG,C.SMALL_SUMMARY,*C.OLD_HELPERS]:
        Q.need(value in plan['source_references'],'EXACT_EXISTING_SMALL_SCIENCE_HELPER_OR_METADATA_REQUIRED')
    for path in [*(C.HERE/name for name in C.FILES),pathlib.Path(Q.__file__).absolute(),pathlib.Path(Q.__file__).absolute().parent/'__init__.py']:
        value=Q.ref(path);Q.need(value in plan['source_references'] and declared.get(value['path'])==value,'ACTUAL_LOCAL_SOURCE_AND_BASE_HELPER_APPROVAL_REQUIRED')
    for path in C.HERE.iterdir():
        if path.is_file() and path.suffix in {'.py','.md','.json'}:Q.need(Q.ref(path) in plan['source_references'],'NO_UNPINNED_LOCAL_SOURCE')
    Q.need(plan['resource_authority_reference'] in plan['source_references'],'REAL_ALPHA_AUTHORITY_IN_SOURCE_SET_REQUIRED')
    authority=Q.load_ref(plan['resource_authority_reference'])
    Q.need(authority.get('schema')=='USER_AUTHORIZED_SECONDARY_DATA_CLUSTER_V1' and authority.get('status')=='USER_AUTHORIZED'
        and authority.get('endpoint')==Q.ENDPOINT and authority.get('observed_uid')==1264 and authority.get('memory_policy')==Q.POLICY,
        'INDEPENDENT_ALPHA_RESOURCE_AUTHORITY_REQUIRED')
    signer=proof['controller_evidence']
    Q.need(signer['endpoint']==Q.ENDPOINT and signer['uid']==1264 and signer['hostname']=='sonmi'
        and signer['proof_is_not_created_by_scientific_worker'] is True
        and signer['actual_script_reference']==proof['script_reference'],'ACTUAL_LOGIN_CONTROLLER_PROOF_ORIGIN_REQUIRED')
    script=Q.read_small(Q.verify(proof['script_reference'])).decode()
    for line in script.splitlines():
        if line.strip().startswith('#SBATCH'):Q.need(not any(w in line for w in ('--mem','--gres','--gpu','--exclusive')),'NO_EXPLICIT_MEMORY_GPU_OR_EXCLUSIVE')
    job=Q.fields(proof['job_metadata'])
    Q.need(job.get('JobId')==str(proof['job_id']) and job.get('UserId')=='alpha(1264)' and job.get('JobState')=='RUNNING'
        and job.get('NodeList')==plan['node'] and job.get('Partition')=='cpu' and job.get('NumCPUs')=='16'
        and job.get('NumTasks')=='1' and job.get('Requeue')=='0' and job.get('Command')==proof['script_reference']['path']
        and Q.duration(job.get('TimeLimit',''))==600,'ACTUAL_CPU16_RUNNING_SCRIPT_AND_WALL_REQUIRED')
    gate=proof['actual_gate_process'];proc=pathlib.Path('/proc/self');tail=(proc/'stat').read_text().rsplit(')',1)[1].split()
    Q.need(gate['pid']==os.getpid() and gate['uid']==1264 and gate['start_ticks']==int(tail[19])
        and gate['pgid']==os.getpgrp() and gate['sid']==os.getsid(0)
        and gate['cgroup_sha256']==hashlib.sha256((proc/'cgroup').read_bytes()).hexdigest(),'ACTUAL_ATTESTED_GATE_PROCESS_REQUIRED')
    storage=proof['storage_observation'];Q.need(Q.load_ref(proof['storage_observation_reference'])==storage,'EXACT_STORAGE_OBSERVATION_REQUIRED')
    Q.need(proof['account_free_bytes']==storage['effective_free_bytes'] and 0<=time.time()-storage['observed_unix_seconds']<=120
        and proof['account_free_bytes']-plan['output_cap_bytes']>=200000000000
        and storage['whole_output_caps_reserved_bytes']>=plan['output_cap_bytes'],'FRESH_RESERVED_OUTPUT_AND200GB_REQUIRED')
    out=Q.literal(plan['output_directory']);Q.need(C.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_INDEPENDENT_ALPHA_OUTPUT_LEAF_REQUIRED')
    return plan,proof
