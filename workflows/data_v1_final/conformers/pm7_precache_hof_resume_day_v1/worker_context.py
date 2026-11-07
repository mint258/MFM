"""Original worker initialization/packet IO with truthful general CPU identity.

No scientific function/global is patched: d7 and pm7_compute are original objects.
"""
import gzip,hashlib,json,math,os,pathlib,time,traceback
from workflows.data_v1_final.conformers.postprocess_day_v1 import contract as C,worker as ORIGINAL_WORKER
from . import io as I
from workflows.data_v1_final.conformers.postprocess_day_v1.math_bridge import geometry_orders,unique_representatives,pm7_compute
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import inheritance as H,contract as PC
SCIENCE=CONTEXT=None
PROOF=None
IO=H.profile_common().IO
d7=ORIGINAL_WORKER.d7

def initialize(context):
    global SCIENCE,CONTEXT
    CONTEXT=context;I.identity(context['proof']);pc=H.profile_common()
    SCIENCE=pc.IO.load_science({'science_source_pins':[PC.SCIENCE_SOURCE,PC.SCIENCE_PREPARE]});SCIENCE.worker_init()
    import torch
    torch.set_num_threads(1)
    if torch.get_num_interop_threads()!=1:torch.set_num_interop_threads(1)
    from rdkit import rdBase
    C.need(pc.IO.version_tuple(rdBase.rdkitVersion)==(2025,9,5),'EXACT_UNCHANGED_NATIVE_GRAPH_RMSD_VERSION')

def one(task,prior_cache,d7_task,output,claim_reference):
    I.identity(CONTEXT['proof']);mid=task['meta']['molecule_id'];events=[]
    root=pathlib.Path(output).parent.parent;key=pathlib.Path(output).name[:-8]
    start={'claim_reference':claim_reference,'molecule_id':mid,'job_id':str(CONTEXT['proof']['job_id']),'uid':os.getuid(),
      'node':CONTEXT['proof']['request']['node'],'boot_id':CONTEXT['proof']['boot_id'],'pid':os.getpid(),'pid_start_ticks':I.PIO.ticks(os.getpid())}
    start_ref=I.save(root/'starts'/(key+'.json'),start)
    progress=root/'progress'/(key+'.jsonl');I.PIO.exclusive(progress,b'')
    def journal(rid,phase,event):
        item={'record_id':rid,'phase':phase,'event':event};events.append(item)
        fd=os.open(progress,os.O_WRONLY|os.O_APPEND|os.O_NOFOLLOW)
        with os.fdopen(fd,'ab') as f:f.write(C.canonical(item)+b'\n');f.flush();os.fsync(f.fileno())
    result={'molecule_id':mid,'PM7_source_count':len(task['records']),'common':d7_task is not None,'runtime':{
      'job_id':str(CONTEXT['proof']['job_id']),'uid':os.getuid(),'node':CONTEXT['proof']['request']['node'],'pid':os.getpid()},
      'new_UFF_calls':0,'new_QM_calls':0,'production_once_written':False,'claim_reference':claim_reference,'worker_start_reference':start_ref,
      'source_role':task['meta'].get('split_role'),'effective_role':task['meta'].get('effective_role')}
    try:
        cache=prior_cache if prior_cache is not None else pm7_compute(task,SCIENCE,journal)
        result['cache']=cache;result['cache_origin']='IMPORTED_REAL_CLOSED_CACHE' if prior_cache is not None else 'NEW_READONLY_CACHE'
        result['d7']=d7(d7_task,cache,SCIENCE) if d7_task is not None and cache['status'].startswith('PM7_GEOMETRY_CACHE_COMPLETE') else None
        result['status']='DURABLE_READONLY_MOLECULE_RESULT'
    except BaseException as exc:result.update(status='READONLY_MOLECULE_UNKNOWN',error=repr(exc),traceback=traceback.format_exc())
    result['record_progress']=events
    raw=C.canonical(result);C.need(len(raw)<=256<<20,'EXPLICIT_WHOLE_MOLECULE_PACKET_BOUND')
    ref=I.PIO.exclusive(pathlib.Path(output),gzip.compress(raw,mtime=0))
    actual=json.loads(gzip.decompress(I.verify(ref).read_bytes()));C.need(actual==result,'FULL_FLOAT64_PACKET_REOPEN_NOT_ONLY_RETURN_STATUS')
    return {'molecule_id':mid,'packet_reference':ref,'status':result['status'],'cache_origin':result.get('cache_origin'),
      'geometry_status':result.get('cache',{}).get('status'),'d7_closed':result.get('d7') is not None,'runtime':result['runtime']}


def proof():
    """Actual CPU full-function text/AST and direct numerical-object witness."""
    global PROOF
    if PROOF is not None:return PROOF
    import ast,hashlib,inspect
    from . import metadata as M
    witness=M.meta(M.pin(M.HERE/'source_origin.json'))['worker_resource_context_source']
    original=pathlib.Path(ORIGINAL_WORKER.__file__).read_bytes()
    M.need(len(original)==witness['bytes'] and hashlib.sha256(original).hexdigest()==witness['sha256'],
        'EXACT_UNCHANGED_ORIGINAL_WORKER_SOURCE_NOT_FAKE_CONTEXT')
    old=original.decode();current=pathlib.Path(__file__).read_text()
    def function(text,name):
        nodes=[n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name]
        M.need(len(nodes)==1,'UNIQUE_WHOLE_ORIGINAL_WORKER_IO_FUNCTION:'+name);node=nodes[0]
        return ''.join(text.splitlines(keepends=True)[node.lineno-1:node.end_lineno]),ast.dump(node,include_attributes=False)
    for name in ('initialize','one'):
        M.need(function(old,name)==function(current,name),'ENTIRE_ORIGINAL_WORKER_IO_FUNCTION_BYTES_AND_AST:'+name)
    M.need(pm7_compute is ORIGINAL_WORKER.pm7_compute and d7 is ORIGINAL_WORKER.d7,
        'DIRECT_ORIGINAL_COMPUTE_D7_OBJECTS_NO_GLOBAL_MONKEYPATCH')
    PROOF={'status':'EXACT_ORIGINAL_INITIALIZE_ONE_TEXT_AST_DIRECT_SCIENTIFIC_OBJECTS',
        'original_worker_reference':witness,'resource_identity_only_context':True,
        'no_native_or_science_called_by_proof':True}
    return PROOF
