"""One explicit author MolBlock seam; original frozen SMILES/full/WP5 objects."""
import os,time
from workflows.expansion.tdc_zip44_identity_main_v1.kernel import load
from . import contract as C
FUNCTIONS=None;CHEM=None


def graph_key(text,functions,chem):
    # Exact author invocation; default sanitize=True and strictParsing=True.
    mol=chem.MolFromMolBlock(text,removeHs=False)
    C.Q.need(mol is not None,'ORIGINAL_MOLBLOCK_PARSE_UNRESOLVED')
    key=chem.MolToInchiKey(mol);valid,invalid=functions['full_keys']([key],strict=False)
    C.Q.need(len(valid)==1 and not invalid,'ORIGINAL_MOLBLOCK_STANDARD_FULL_KEY_UNRESOLVED')
    return valid


def normalize(row,functions,chem):
    token=row['source_string'];keys=[];errors=[]
    if not token['strict_UTF8_valid'] or token['text']=='':state='ORIGINAL_EMPTY_OR_NON_UTF8_SOURCE_UNKNOWN'
    elif row['kind']=='root_SMILES':
        keys,errors=functions['source_smiles_keys']({'original_root_SMILES':token['text']})
        state='ROOT_SMILES_FULL_KEYS_DERIVED' if keys and not errors else 'ORIGINAL_ROOT_SMILES_UNRESOLVED'
    else:
        C.Q.need(row['kind']=='conformer_MolBlock','EXACT_SOURCE_KIND')
        try:keys=graph_key(token['text'],functions,chem);state='MOLBLOCK_GRAPH_FULL_KEY_DERIVED'
        except Exception as exc:state='ORIGINAL_MOLBLOCK_GRAPH_UNRESOLVED';errors=[{'exception_type':type(exc).__name__,'message':str(exc)}]
    valid,invalid=functions['full_keys'](keys,strict=False);C.Q.need(not invalid,'EXACT_FROZEN_OUTPUT_KEYS')
    return {'source':row,'identity_state':state,'full_key_and_WP5_pairs':[[k,functions['wp5_key'](k)] for k in valid],
        'has_any_unknown':state not in ('ROOT_SMILES_FULL_KEYS_DERIVED','MOLBLOCK_GRAPH_FULL_KEY_DERIVED'),'errors':errors,
        'unknown_is_chemical_exclusion':False,'source_SMILES_or_native_graph_repaired':False,'source_or_pool_accepted':False}


def initialize(source_refs):
    global FUNCTIONS,CHEM
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
    FUNCTIONS,_=load(source_refs)
    from workflows.expansion.identity_v2.projection_v2 import rdkit_identity_modules
    CHEM=rdkit_identity_modules()


def work(row):
    started=time.process_time()
    try:value=normalize(row,FUNCTIONS,CHEM)
    except Exception as exc:value={'source':row,'identity_state':'TECHNICAL_UNRESOLVED','has_any_unknown':True,
        'full_key_and_WP5_pairs':[],'error':type(exc).__name__+': '+str(exc),'unknown_is_chemical_exclusion':False,'source_or_pool_accepted':False}
    return {'result':value,'worker_pid':os.getpid(),'worker_CPU_seconds':time.process_time()-started}
