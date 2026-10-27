"""Durable orchestration around the unchanged pilot compute() and reader."""
from __future__ import annotations
import os,pathlib,socket,time
from . import contract as C,io as I
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import core
SESSION=None


def initialize(session):
    global SESSION
    core.worker_init(session) # Original public initializer, original RDKit/reader.
    SESSION=session


def one(task,task_ref,claim_ref):
    I.P.continuation(SESSION);out=pathlib.Path(SESSION['output_root']);key=task['cache_key'];mid=task['meta']['molecule_id']
    runtime={'job_id':SESSION['job_id'],'uid':os.getuid(),'node':socket.gethostname().split('.')[0],
        'pid':os.getpid(),'start_ticks':I.R.proc_ticks(os.getpid()),'parent_pid':os.getppid(),'boot_id':SESSION['boot_id']}
    start=I.json_new(out/'starts'/(key+'.json'),{'cache_key':key,'molecule_id':mid,'task_reference':task_ref,
        'claim_reference':claim_ref,'runtime':runtime},out)
    def journal(rid,phase,event):
        I.append_progress(out/'progress'/(key+'.jsonl'),{'record_id':rid,'phase':phase,'event':event,
            'task_reference':task_ref,'runtime':runtime},out)
    try:result=core.compute(task,journal=journal)
    except Exception as exc:
        result={'schema':'PM7_INDEPENDENT_MOLECULE_CACHE_V1','molecule_id':mid,'cache_key':key,
            'source_population_authority':task['source_population_authority'],'source_records':task['records'],
            'PM7_source_count':len(task['records']),'record_ids':[r['record_id'] for r in task['records']],
            'pm7':[],'hof_by_record':task['hof'],'hof_mode':task['hof_mode'],
            'status':'PENDING_COMPUTE_EXCEPTION_PROGRESS_RETAINED','error':repr(exc)[:16000],
            'record_progress_locator':str(out/'progress'/(key+'.jsonl')),'common':False,
            'new_QM_calls':0,'new_UFF_calls':0,'geometry_generation_or_optimization_calls':0}
    result.update(runtime=runtime,task_reference=task_ref,claim_reference=claim_ref,worker_start_reference=start,
        hof_source_provenance_reference=task['hof_source_provenance_reference'])
    packet=I.packet(out/'molecules'/(key+'.json.gz'),result,out)
    finished=I.json_new(out/'finished'/(key+'.json'),{'cache_key':key,'molecule_id':mid,
        'packet_reference':packet,'task_reference':task_ref,'claim_reference':claim_ref,
        'worker_start_reference':start,'runtime':runtime,'status':result['status']},out)
    return {'cache_key':key,'molecule_id':mid,'packet_reference':packet,'finished_reference':finished,
        'worker_start_reference':start,'runtime':runtime,'status':result['status']}
