"""Exact original orchestration objects; no scientific function copies."""
import importlib,pathlib,sys
from . import contract as C

def verify_sources():
    origin=C.meta(C.Q.pin(C.HERE/'source_origin.json'))
    C.need(origin['schema']=='PPRIME2000_DIRECT_ORIGINAL_SOURCE_OBJECTS_V1','EXACT_SOURCE_ORIGIN')
    refs=[]
    for item in origin['files']:
        path=C.Q.REPO/item['relative_path'];ref=C.Q.pin(path)
        C.need(ref['bytes']==item['bytes'] and ref['sha256']==item['sha256'],'UNCHANGED_ORIGINAL_MODULE:'+item['relative_path'])
        refs.append(ref)
    return refs

def objects():
    verify_sources();base=C.Q.REPO/'workflows/data_v1_final/pprime'
    sys.path[:0]=[str(base),str(base/'retention_v1')]
    result={}
    for name,attribute in (('engine_adapter','compute_pair'),('raw_archive','RawSink'),('raw_archive','RawReader'),
                           ('export_families','export'),('retention_policy_v1','prove_raw'),('close_pilot','assess')):
        module=importlib.import_module(name);expected=base/('retention_v1' if name=='retention_policy_v1' else '')/(name+'.py')
        C.need(pathlib.Path(module.__file__).absolute()==expected,'ACTUAL_ORIGINAL_MODULE_IMPORT:'+name)
        result[attribute]=getattr(module,attribute)
    return result
