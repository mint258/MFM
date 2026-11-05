"""Direct unchanged Main identity function objects and bounded process worker."""
import importlib,os,sys,time
from pathlib import Path
from . import contract as C
FUNCTIONS=None


def load(source_refs):
    projection=importlib.import_module('workflows.expansion.identity_v2.projection_v2')
    common=importlib.import_module('workflows.expansion.common')
    for relative,(size,sha) in C.FROZEN.items():
        ref=C.Q.pin(C.Q.REPO/relative);C.Q.need(ref['bytes']==size and ref['sha256']==sha and ref in source_refs,'EXACT_UNCHANGED_FROZEN_IDENTITY_SOURCE_BYTES')
    for name,module in list(sys.modules.items()):
        file=getattr(module,'__file__',None)
        if name.startswith('workflows.expansion') and file and Path(file).suffix=='.py':
            C.Q.need(C.Q.pin(file) in source_refs,'EVERY_ACTUAL_IMPORTED_EXPANSION_SOURCE_PIN:'+name)
    projection.rdkit_identity_modules()
    functions={'full_keys':projection.full_keys,'source_smiles_keys':projection.source_smiles_keys,'wp5_key':common.wp5_key}
    proof={'basis':'DIRECT_FROZEN_FUNCTION_OBJECTS_FULL_FILE_SHA','RDKit_version':'2025.09.5',
        'functions':{n:{'module':f.__module__,'filename':f.__code__.co_filename,'first_line':f.__code__.co_firstlineno} for n,f in functions.items()}}
    return functions,proof


def normalize(row,functions):
    source=dict(row);drug=row['original_Drug'];value=drug['text'];keys=[];errors=[]
    if row['row_width']!=3:state='ROW_WIDTH_UNKNOWN'
    elif drug['state']=='INVALID_UTF8_UNKNOWN':state='INVALID_UTF8_UNKNOWN'
    elif value is None or value=='':state='MISSING_OR_EMPTY_SMILES_UNKNOWN'
    else:
        keys,errors=functions['source_smiles_keys']({'Drug':value});state='FULL_KEYS_DERIVED' if keys and not errors else 'ORIGINAL_SMILES_UNRESOLVED'
    valid,invalid=functions['full_keys'](keys,strict=False);C.Q.need(not invalid,'ORIGINAL_KERNEL_OUTPUT_KEYS')
    return {'source':source,'identity_state':state,'full_InChIKeys':valid,'WP5_keys':sorted({functions['wp5_key'](k) for k in valid}),
        'identity_errors':errors,'missing_or_invalid_ID_retained':row['original_Drug_ID']['text'] in (None,''),
        'technical_or_chemical_unknown_is_exclusion':False,'X_or_other_chemical_filter_applied':False}


def initialize(source_refs):
    global FUNCTIONS
    os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
    FUNCTIONS,_=load(source_refs)


def work(row):
    started=time.process_time()
    try:result=normalize(row,FUNCTIONS)
    except Exception as exc:result={'source':row,'identity_state':'TECHNICAL_UNRESOLVED','full_InChIKeys':[],'WP5_keys':[],
        'error':type(exc).__name__+': '+str(exc),'technical_unknown_is_chemical_exclusion':False}
    return {'result':result,'worker_pid':os.getpid(),'worker_CPU_seconds':time.process_time()-started}
