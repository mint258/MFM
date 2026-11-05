"""The frozen original read/graph chain, with explicit execution pointers."""
from __future__ import annotations
import hashlib,importlib.util,json,os,pathlib,socket,stat,sys,time
from . import common as U
from .signatures import field_signature,canonical,sha
WORK={}

def module_from(reference,name):
    path=U.require(reference,True);spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def init_worker(context):
    global WORK
    proof=U.load(context['proof_reference']);parent=context['parent_pid']
    ticks=int(pathlib.Path('/proc',str(parent),'stat').read_text().rsplit(')',1)[1].split()[19])
    U.need(os.getppid()==parent and ticks==context['parent_start_ticks'] and os.getuid()==context['uid']
        and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID') and proof['boot_id']==pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'SAME_LIVE_ADMITTED_PARENT_ALLOCATION_NOT_REUSED_FRESH_PROOF')
    sources=context['science_sources'];recipe=U.load(context['recipe_reference'])
    for reference in sources.values():U.require(reference,True)
    U.need({pathlib.Path(sources[k]['path']).name for k in sources}=={'common.py','sprime_v6.py','prepare.py'},'EXACT_FROZEN_READER_SOURCE_NAMES')
    if 'prepare' in sys.modules:U.need(pathlib.Path(sys.modules['prepare'].__file__).absolute()==pathlib.Path(sources['prepare']['path']),'AMBIGUOUS_LEGACY_PREPARE_IMPORT')
    original=module_from(sources['common'],'_sparse32_original_common');recipe=original.load_config(context['recipe_reference']['path'])
    legacy=original.load_science(recipe)
    U.need(pathlib.Path(legacy.__file__).absolute()==pathlib.Path(sources['legacy']['path'])
        and pathlib.Path(sys.modules['prepare'].__file__).absolute()==pathlib.Path(sources['prepare']['path']),'ACTUAL_DEPLOYED_ORIGINAL_READER_AND_PREPARE')
    legacy.worker_init()
    from rdkit import rdBase
    U.need(original.version_tuple(rdBase.rdkitVersion)==(2025,9,5),'FROZEN_RDKIT2025_09_5_REQUIRED')
    import platform,numpy,torch,lmdb
    from importlib import metadata
    versions={'python':platform.python_version(),'numpy':numpy.__version__,'torch':str(torch.__version__),'torch_geometric':metadata.version('torch-geometric'),
        'rdkit':rdBase.rdkitVersion,'lmdb_python':lmdb.__version__,'liblmdb':list(lmdb.version())}
    WORK={'context':context,'common':original,'legacy':legacy,'versions':versions}

def raw_value(pointer):
    import lmdb
    path=pathlib.Path(pointer['source_path']);path=path if path.is_absolute() else WORK['legacy'].PROJECT/path
    before=path.stat();U.need(stat.S_ISREG(before.st_mode),'ORIGINAL_CANONICAL_LMDB_REGULAR_TARGET')
    def get(env):
        with env.begin(buffers=True) as tx:
            view=tx.get(U.raw_key(pointer))
            U.need(view is not None and len(view)<=U.RAW_CAP,'RAW_VALUE_ABSENT_OR_SOFTWARE8MIB_BOUND_UNKNOWN_STOP')
            return bytes(view)
    existing=WORK['legacy'].HANDLES.get(str(path))
    if existing is not None:value=get(existing)
    else:
        with lmdb.open(str(path),subdir=False,readonly=True,lock=False,create=False,readahead=False,max_readers=1024) as env:
            value=get(env)
    U.need(sha(value)==pointer['record_payload_sha256'] and U.frame(before)==U.frame(path.stat()),'EXACT_CANONICAL_RECORD_SHA_AND_SOURCE_FRAME')
    return value,str(path.absolute()),U.frame(before)

def graph_signature(raw):
    legacy=WORK['legacy'];original=WORK['common']
    mol,numbers,coordinates=legacy.graph(raw);stereo_source,signature=legacy.fix_stereo(mol,str(legacy.field(raw,'smiles')))
    return {'schema':'ORIGINAL_SOURCE_GRAPH_SIGNATURE_V1','atomic_numbers':numbers.tolist(),
      'atom_order_sha256':sha(numbers.astype('<i8').tobytes()),'ordered_graph_sha256':sha(canonical(legacy.ordered_graph(mol))),
      'pm7_geometry_sha256':original.geometry_sha(numbers,coordinates),'stereo_source':stereo_source,
      'stereo_signature_sha256':sha(canonical(signature)),'new_UFF_calls':0,'new_QM_calls':0}

def read_one(item):
    pointer=item['execution_pointer'];value,path,frame=raw_value(pointer)
    # This is the actual original function. No assignment to legacy.read,
    # PROJECT, HANDLES, or another frozen-module global occurs here.
    raw=WORK['legacy'].read(pointer)
    fields=field_signature(raw);graph=graph_signature(raw)
    members=raw.to_dict() if hasattr(raw,'to_dict') else raw if type(raw) is dict else {}
    idx={'present':True,'signature':field_signature(members['idx'])} if 'idx' in members else {'present':False,'native_field_missing':True}
    U.need(U.frame(pathlib.Path(path).stat())==frame,'SOURCE_FRAME_CHANGED_DURING_ORIGINAL_READ_AND_SIGNATURE')
    ticks=int(pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
    result={'record_id':pointer['record_id'],'molecule_id':pointer['molecule_id'],'origin_pointer':item['origin_pointer'],
      'execution_pointer':pointer,'key_hex':U.raw_key(pointer).hex(),'raw_bytes':len(value),'raw_sha256':sha(value),
      'actual_opened_LMDB':path,'actual_file_frame':frame,'field_signature':fields,'graph_signature':graph,'native_idx':idx,
      'runtime':{'uid':os.getuid(),'pid':os.getpid(),'start_ticks':ticks,'job_id':os.environ['SLURM_JOB_ID'],'node':socket.gethostname().split('.')[0]},
      'original_read_function_used':True,'frozen_module_globals_monkeypatched':False,'actual_versions':WORK['versions']}
    if item.get('return_raw_value'):result['opaque_original_value']=value
    return result

def read_pair(items):
    U.need(len(items)==2,'TWO_RECORDS_PER_ACTUAL_WORKER')
    WORK['context']['dispatch_barrier'].wait(timeout=300)
    return [read_one(item) for item in items]

def validate_graph_against_baseline(graph,validation,pointer):
    U.need(validation['status']=='ORIGINAL_SOURCE_AND_BASELINE_VALIDATED_NO_NEW_UFF'
        and validation['original_payload_sha256']==pointer['record_payload_sha256'],'ACTUAL_PREPARED_CANONICAL_SOURCE_VALIDATION')
    for key in ('atom_order_sha256','ordered_graph_sha256','pm7_geometry_sha256','stereo_source'):
        U.need(graph[key]==validation[key],'FROZEN_SOURCE_GRAPH_OR_STEREO_DRIFT:'+key)
    U.need(graph['stereo_signature_sha256']==sha(canonical(validation['stereo_signature'])) and graph['atomic_numbers']==validation['atomic_numbers'],
        'FROZEN_SOURCE_STEREO_SIGNATURE_OR_ATOMIC_NUMBERS_DRIFT')

def context(plan,proof,science_sources,recipe_reference):
    return {'proof_reference':U.pin(plan['actual_proof_path'],True),'parent_pid':os.getpid(),
      'parent_start_ticks':int(pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
      'uid':os.getuid(),'science_sources':science_sources,'recipe_reference':recipe_reference}
