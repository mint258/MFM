"""Frozen key functions through existing loader; complete original variants preserved."""
import os,time
from workflows.expansion.tdc_zip44_identity_main_v1.kernel import load
from . import rows as V
FUNCTIONS=None


def normalize(row,functions):
    V.validate(row);d=row['details'];variants=[];union=set();unknown=bool(d['issues']) or d['format_state']!='SELECTED_SOURCE_FIELDS_OBSERVED'
    for i,value in enumerate(d['properties']['smiles']):
        raw=V.token(value);keys=[];errors=[]
        if raw is None or raw==b'':state='MISSING_OR_EMPTY_ORIGINAL_SMILES_UNKNOWN'
        elif value['state']=='INVALID_UTF8_UNKNOWN':state='INVALID_UTF8_ORIGINAL_SMILES_UNKNOWN'
        else:
            keys,errors=functions['source_smiles_keys']({'native_smiles_property_'+str(i):value['text']})
            state='FULL_KEYS_DERIVED' if keys and not errors else 'ORIGINAL_SMILES_UNRESOLVED'
        union.update(keys);unknown|=state!='FULL_KEYS_DERIVED';variants.append({'original_variant_index':i,'original_token':value,'state':state,'full_InChIKeys':keys,'errors':errors})
    if not variants:unknown=True
    valid,invalid=functions['full_keys'](sorted(union),strict=False)
    if invalid:raise ValueError('FROZEN_KEY_OUTPUT_INVALID')
    return {'source':row,'variant_observations':variants,'identity_state':'ORIGINAL_VARIANT_KEYS_WITH_UNKNOWNS' if unknown else 'ALL_ORIGINAL_VARIANT_KEYS_DERIVED',
        'has_any_unknown':bool(unknown),'full_key_and_WP5_pairs':[[k,functions['wp5_key'](k)] for k in valid],
        'all_original_ID_name_and_SMILES_fields_retained':True,'native_SDF_graph_or_stereo_verified':False,
        'unknown_is_chemical_exclusion':False,'SMILES_repair_or_representative_choice':False}


def initialize(source_refs):
    global FUNCTIONS
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
    FUNCTIONS,_=load(source_refs)


def work(row):
    started=time.process_time()
    try:value=normalize(row,FUNCTIONS)
    except Exception as exc:value={'source':row,'identity_state':'TECHNICAL_UNRESOLVED','has_any_unknown':True,
        'full_key_and_WP5_pairs':[],'error':type(exc).__name__+': '+str(exc),'unknown_is_chemical_exclusion':False}
    return {'result':value,'worker_pid':os.getpid(),'worker_CPU_seconds':time.process_time()-started}
