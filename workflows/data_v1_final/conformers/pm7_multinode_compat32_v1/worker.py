"""Own isolated worker context; never assigns frozen core SCIENCE/SESSION."""
import os,pathlib,socket,sys
from . import contract as C,resources as R,io as I,compute as K
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import contract as PC,inheritance as H
CONTEXT=None


def initialize(session):
    global CONTEXT
    R.continuation(session);pc=H.profile_common()
    science=pc.IO.load_science({'science_source_pins':[PC.SCIENCE_SOURCE,PC.SCIENCE_PREPARE]});science.worker_init()
    C.need(pathlib.Path(sys.modules['prepare'].__file__).absolute()==pathlib.Path(PC.SCIENCE_PREPARE['path']),'EXACT_ORIGINAL_NATIVE_READER_IMPORT')
    import torch
    torch.set_num_threads(1)
    if torch.get_num_interop_threads()!=1:torch.set_num_interop_threads(1)
    from rdkit import rdBase
    C.need(pc.IO.version_tuple(rdBase.rdkitVersion)==(2025,9,5),'EXACT_ORIGINAL_RDKIT_VERSION')
    CONTEXT={'session':session,'science':science}


def one(task,task_ref):
    session=CONTEXT['session'];R.continuation(session);out=pathlib.Path(session['output_root']);key=task['cache_key']
    runtime={'job_id':session['job_id'],'uid':os.getuid(),'node':socket.gethostname().split('.')[0],'pid':os.getpid(),
        'parent_pid':os.getppid(),'start_ticks':I.P.R.proc_ticks(os.getpid()),'boot_id':session['boot_id']}
    start=I.json_new(out/'starts'/(key+'.json'),{'schema':'PM7_NODE19_QA_WORKER_START_V1','cache_key':key,
        'molecule_id':task['meta']['molecule_id'],'task_reference':task_ref,'runtime':runtime,'startup_proof_reference':session['proof_reference'],
        'QA_only':True,'new_population_rows':0},out)
    def journal(record_id,phase,event):
        I.progress(out/'progress'/(key+'.jsonl'),{'record_id':record_id,'phase':phase,'event':event,'task_reference':task_ref,'runtime':runtime},out)
    try:result=K.compute(task,CONTEXT['science'],journal=journal)
    except Exception as exc:
        result={'schema':'PM7_INDEPENDENT_MOLECULE_CACHE_V1','molecule_id':task['meta']['molecule_id'],'cache_key':key,
            'status':'QA_COMPUTE_EXCEPTION_NOT_COMPATIBLE','pm7':[],'source_errors':[repr(exc)[:16000]],'error':repr(exc)[:16000],
            'new_UFF_calls':0,'new_QM_calls':0,'common':False}
    result.update(runtime=runtime,task_reference=task_ref,worker_start_reference=start,startup_proof_reference=session['proof_reference'],QA_only=True,new_population_rows=0)
    packet=I.packet(out/'molecules'/(key+'.json.gz'),result,out)
    finished=I.json_new(out/'finished'/(key+'.json'),{'molecule_id':task['meta']['molecule_id'],'cache_key':key,'packet_reference':packet,
        'worker_start_reference':start,'task_reference':task_ref,'runtime':runtime,'status':result['status'],'QA_only':True},out)
    return {'molecule_id':task['meta']['molecule_id'],'packet_reference':packet,'finished_reference':finished,'worker_start_reference':start,
        'task_reference':task_ref,'runtime':runtime,'status':result['status']}
