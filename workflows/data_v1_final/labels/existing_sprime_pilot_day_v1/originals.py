"""Exact label-source imports isolated from legacy unqualified module aliases.

Only the two legacy consumers are loaded under private names. Their source is
executed verbatim; their module-local import resolver binds three ambiguous
names to the actual qualified original modules. No old module/global alias or
sys.path is patched. All numerical functions remain original source objects.
"""
import builtins,importlib,importlib.util,sys,threading
from pathlib import Path
from . import contract as C
_LOCK=threading.RLock();_CACHE=None;_REFERENCES=()
_SHORT=('common','calibration','support','build_registry','reduce')

def _qualified(name,path):
    module=importlib.import_module(name)
    C.need(Path(module.__file__).absolute()==path,'EXACT_QUALIFIED_ORIGINAL_MODULE_PATH:'+name)
    raw,reference=C.P.small(path)
    return module,reference

def _legacy(name,path,aliases):
    raw,reference=C.P.small(path);C.need(name not in sys.modules,'UNIQUE_PRIVATE_ORIGINAL_MODULE_NAME')
    spec=importlib.util.spec_from_file_location(name,path);C.need(spec is not None,'REAL_ORIGINAL_SOURCE_SPEC')
    module=importlib.util.module_from_spec(spec)
    def import_exact(import_name,globals=None,locals=None,fromlist=(),level=0):
        if level==0 and import_name in aliases:return aliases[import_name]
        return builtins.__import__(import_name,globals,locals,fromlist,level)
    module.__dict__['__builtins__']=dict(vars(builtins),__import__=import_exact)
    sys.modules[name]=module
    try:
        exec(compile(raw,str(path),'exec'),module.__dict__)
        C.need(Path(module.__file__).absolute()==path and C.P.pin(path)==reference,'VERBATIM_PINNED_SOURCE_STABLE_DURING_ISOLATED_IMPORT')
    except BaseException:
        if sys.modules.get(name)is module:del sys.modules[name]
        raise
    return module,reference

def objects():
    global _CACHE,_REFERENCES
    with _LOCK:
        if _CACHE is not None:
            for ref in _REFERENCES:C.need(C.P.pin(ref['path'])==ref,'SAME_ORIGINAL_SOURCE_BYTES_AFTER_ISOLATED_IMPORT')
            return _CACHE
        labels=C.REPO/'workflows/data_v1_final/labels';stream=labels/'streaming_v1'
        before={name:sys.modules.get(name) for name in _SHORT};path_before=list(sys.path);private=[]
        try:
            common,cr=_qualified('workflows.data_v1_final.labels.common',labels/'common.py')
            calibration,ar=_qualified('workflows.data_v1_final.labels.streaming_v1.calibration',stream/'calibration.py')
            support,sr=_qualified('workflows.data_v1_final.labels.streaming_v1.support',stream/'support.py')
            aliases={'common':common,'calibration':calibration,'support':support}
            registry,rr=_legacy('_dv1_existing_sprime_original_registry_r3',labels/'build_registry.py',aliases);private.append(registry)
            reducer,dr=_legacy('_dv1_existing_sprime_original_reduce_r3',stream/'reduce.py',aliases);private.append(reducer)
            series,vr=_qualified('workflows.data_v1_final.labels.normalization_v1.series',labels/'normalization_v1/series.py')
            compact,kr=_qualified('workflows.data_v1_final.labels.streaming_v1.compact',stream/'compact.py')
            masks,mr=_qualified('workflows.data_v1_final.export.pipeline_v1.masks',C.REPO/'workflows/data_v1_final/export/pipeline_v1/masks.py')
            C.need(registry.D20_NAMES is common.D20_NAMES and registry.read_json is common.read_json
                and reducer.merge_qr is calibration.merge_qr and reducer.path_list is support.path_list,'ACTUAL_ORIGINAL_DEPENDENCY_OBJECTS_BOUND_NOT_SHORT_ALIAS_COLLISIONS')
            from . import bindings as B
            C.need(reducer.merge_qr is B.merge_qr and series.views is B.views and series.inventory is B.inventory,'EXACT_SHARED_ORIGINAL_MATH_OBJECT_IDENTITY')
            C.need(all(sys.modules.get(name)is value for name,value in before.items()) and sys.path==path_before,'NO_GLOBAL_LEGACY_ALIAS_OR_SYS_PATH_MUTATION')
            _REFERENCES=(cr,ar,sr,rr,dr,vr,kr,mr);_CACHE=(registry,reducer,series,compact,masks)
            return _CACHE
        except BaseException:
            for module in private:
                if sys.modules.get(module.__name__)is module:del sys.modules[module.__name__]
            raise

def proof():
    registry,reducer,series,compact,masks=objects()
    return {'status':'EXACT_ORIGINAL_SOURCE_WITH_MODULE_LOCAL_AMBIGUOUS_IMPORT_BINDINGS',
        'source_references':list(_REFERENCES),'registry_file':registry.__file__,'reducer_file':reducer.__file__,
        'series_file':series.__file__,'legacy_short_aliases_modified':False,'sys_path_modified':False,
        'old_originals_or_scientific_module_globals_patched':False,'source_text_or_math_rewritten':False}
