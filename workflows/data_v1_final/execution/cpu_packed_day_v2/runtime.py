"""One real packed parent after exec; no old16 proof and no child Slurm IDs."""
import os,socket,sys,time
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import primary_binding
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.registry import process_identity
from . import contract as C
Q=C.Q

def require_resource_review(request,*,now=None,require_lease=False):
    return C.resources(request,now=now,lease=require_lease)

def require_startup(proof_path,*,expected_scope_key=None,expected_scope_parameters=None,expected_execution_argv=None,
                    expected_source=None,expected_kind=None,required_references=()):
    proof_path=Path(proof_path).absolute();p=Q.load(proof_path);r=p['request'];C.validate(r)
    C.need(p['schema']==C.PROOF and proof_path==Path(r['startup_proof_path']) and p['request_reference']==Q.pin(p['request_reference']['path'])
        and Q.load(p['request_reference']['path'])==r,'ONLY_TRUE_PACKED_REQUEST_AND_FRESH_PROOF')
    actual=process_identity(os.getpid());ready=p['parent_identity'];C.need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID')==str(p['job_id'])
        and socket.gethostname().split('.')[0]==r['node'] and os.environ.get('SLURM_JOB_PARTITION')=='cpu'
        and os.environ.get('SLURM_CPUS_PER_TASK')==str(r['cpus']) and os.environ.get('CUDA_VISIBLE_DEVICES')=='',
        'ACTUAL_PACKED_PARENT_ALLOCATION_NOT_CPU16_MASQUERADE')
    for k in ('pid','uid','start_ticks','boot_id','pgid','sid','cgroup_sha256'):
        C.need(actual[k]==ready[k],'SAME_REAL_PARENT_EXEC_IDENTITY:'+k)
    C.need(p['uid']==1278 and p['node']==r['node'] and p['boot_id']==actual['boot_id'] and p['memory_policy']==C.MEMORY
        and p['memory_admission_evaluated'] is False and p['memory_limits_requested'] is False
        and p['execution_admission_granted'] is True and p['actual_cpus']==r['cpus'] and p['source_references']==r['source_references'],
        'PACKED_PROOF_REAL_IDENTITY_ACTUAL_CPU_COUNT_AND_NO_MEMORY_REQUEST')
    now=time.time();epoch=p['memory_observation']['observed_unix_seconds'];C.need(type(epoch)in (int,float) and 0<=now-epoch<=120,'ORIGINAL_FRESH120_NO_EXTENSION')
    C.job_identity(r,p['job_metadata'],p['job_id']);carve,review,identity=C.resources(r)
    C.need(identity['expires_unix_seconds']>=p['lease_coverage_checked_unix_seconds']+86700
        and p['quota_provider_identity_reference']==r['quota_provider_identity_reference']
        and p['quota_provider_review_reference']==r['quota_provider_review_reference'] and p['root_carveout_review_reference']==r['root_carveout_review_reference']
        and p['account_free_bytes']-carve['total_future_reserved_bytes']>=C.RESERVE,'ACTUAL_FINITE_LEASE_AND_CURRENT_WHOLE_FUTURE_RESERVE')
    main=Path(sys.modules['__main__'].__file__).absolute();primary_binding(r,main,sys.argv[1:])
    C.need(Q.pin(main) in r['source_references'] and actual['argv']==r['execution_argv'],'ACTUAL_OS_FULL_ARGV_AND_PRIMARY_SOURCE')
    if expected_source is not None:
        ref=expected_source if isinstance(expected_source,dict) else Q.pin(Path(expected_source).absolute())
        C.need(ref==Q.pin(main) and ref in r['source_references'],'EXPECTED_PACKED_PRODUCER_SOURCE')
    if expected_scope_key is not None:C.need(expected_scope_key==r['scope_key']==C.KEY,'ONLY_SPRIME_PACKED_SCOPE')
    if expected_scope_parameters is not None:C.need(C.O.same(expected_scope_parameters,r['scope_parameters']),'EXACT_ROOT_PRODUCER_PARAMETERS')
    if expected_execution_argv is not None:C.need(list(expected_execution_argv)==r['execution_argv'],'EXACT_ROOT_PRODUCER_FULL_ARGV')
    if expected_kind is not None:C.need(expected_kind==r['kind'],'ONLY_CONFORMER_PACKED_ROLE')
    allowed={v['path']:v for group in ('source_references','data_references') for v in r[group]}
    for ref in required_references:C.need(allowed.get(ref['path'])==ref,'EXACT_PACKED_PLAN_INPUT_OR_RESOURCE_REFERENCE')
    for path in C.sources():C.need(Q.pin(path) in r['source_references'],'ALL_PACKED_PROTOCOL_AND_ORIGINAL_HELPER_SOURCE_PINS')
    return p
