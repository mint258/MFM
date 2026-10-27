"""Direct original scientific callable under a new truthful parent context."""
import gzip,hashlib,os,pathlib,socket,time,traceback
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import runtime_io as OLD
from . import contract as C,runtime as I
SCIENCE=None;VALUE=None;CONTEXT=None


def initialize(context):
    global SCIENCE,VALUE,CONTEXT
    CONTEXT=context;I.identity(context['proof'])
    C.need(I.ticks(context['parent_pid'])==context['parent_start_ticks'],'REAL_PACKED_PARENT_STILL_PRESENT_AT_NATIVE_INIT')
    VALUE=C.F.config(context['config_reference'])
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[name]='1'
    _,SCIENCE=OLD.load_science(VALUE) # exact original worker_init and process_task objects
    C.need(SCIENCE.process_task.__code__.co_filename==C.F.sources()['science']['path'],'DIRECT_ORIGINAL_PROCESS_TASK_SOURCE')


def one(task,dispatch_reference,batch_id):
    proof=CONTEXT['proof'];I.identity(proof);mid=task['meta']['molecule_id'];key=task['meta']['task_key'];out=pathlib.Path(CONTEXT['out'])
    claim=I.read_json(dispatch_reference);C.need(claim['task_key']==key and claim['task_sha256']==C.F.sha_value(task)
        and claim['job_id']==str(proof['job_id']) and claim['packed_plan_reference']==CONTEXT['plan_reference'],'PACKED_EXACT_CANONICAL_ONCE_CLAIM')
    start={'schema':'SPRIME_ONCE_WORKER_STARTED_V3','dispatch_reference':dispatch_reference,'task_key':key,'task_sha256':claim['task_sha256'],
        'molecule_id':mid,'cohort':task['meta']['cohort'],'seed':claim['seed'],'job_id':str(proof['job_id']),'uid':os.getuid(),
        'node':socket.gethostname().split('.')[0],'pid':os.getpid(),'pid_start_ticks':I.ticks(os.getpid()),'boot_id':proof['boot_id'],
        'observed_unix_seconds':time.time(),'resource_scope':C.KEY,'single_real_parent':True,'internal_batch_id':batch_id}
    sr=I.write_bounded(out,CONTEXT['cap'],out/'starts'/(key+'.json'),C.F.canonical(start)+b'\n',key)
    try:
        result=SCIENCE.process_task(task) # numerical source/recipe/seed/RMSD/graph/stereo unchanged
        C.need(result['summary']['molecule_id']==mid and result['summary']['seed']==claim['seed'],'ORIGINAL_KERNEL_RESULT_MID_AND_SEED')
        result['formal_start']=start
        old_sha={OLD.common().geometry_sha(row['atomic_numbers'],row['coordinates']) for row in result.get('conformers',[]) if row['origin']=='accepted_sprime'}
        new=[row for row in result.get('conformers',[]) if row['origin']!='accepted_sprime']
        result['packed_lineage']={'resource_scope':C.KEY,'single_parent_job_id':str(proof['job_id']),'packed_plan_reference':CONTEXT['plan_reference'],
            'internal_batch_id':batch_id,'no_child_job_or_child_C0':True,'new_optimized_output_rows':len(new),
            'generated_rows_with_exact_geometry_SHA_already_in_retained_baseline':sum(row['geometry_sha256'] in old_sha for row in new),
            'all_output_distinct_geometry_SHA_count':len({row['geometry_sha256'] for row in result.get('conformers',[])}),
            'new_optimization_does_not_claim_all_geometries_are_unique':True}
        raw=C.F.canonical(result);C.need(len(raw)<=VALUE['packet_uncompressed_limit_bytes'],'ORIGINAL_FULL_PACKET_UNCOMPRESSED_BOUND')
        compressed=gzip.compress(raw,mtime=0);C.need(len(compressed)<=VALUE['packet_compressed_limit_bytes'],'ORIGINAL_FULL_PACKET_COMPRESSED_BOUND')
        ref=I.write_bounded(out,CONTEXT['cap'],out/'packets'/(key+'.json.gz'),compressed,key)
        actual=OLD.read_packet(ref,VALUE);C.need(actual==result,'DIRECT_ORIGINAL_FLOAT64_PACKET_READBACK')
        return {'task_key':key,'molecule_id':mid,'package_reference':ref,'start_reference':sr,'scientific_status':result['summary']['status'],
            'actual_single_parent_job_id':str(proof['job_id']),'internal_batch_id':batch_id,'task_sha256':claim['task_sha256']}
    except BaseException as exc:
        error={'task_key':key,'molecule_id':mid,'start_reference':sr,'error':repr(exc),'traceback':traceback.format_exc(),
            'science_result_observed':False,'actual_single_parent_job_id':str(proof['job_id']),'consumed_unknown_no_retry':True}
        I.write_bounded(out,CONTEXT['cap'],out/'errors'/(key+'.json'),C.F.canonical(error)+b'\n',key)
        raise
