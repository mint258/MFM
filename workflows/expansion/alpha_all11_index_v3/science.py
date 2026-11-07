"""Call original V3 objects directly; record their real deployed source bodies."""
import importlib
import inspect
from pathlib import Path
from .reader import S


def initialize(proof):
    C=importlib.import_module('workflows.expansion.coconut735_recovery_v1.consumer')
    M=importlib.import_module('workflows.expansion.coconut735_recovery_v1.manifest')
    refs={r['path']:r for r in proof['request']['source_references']};objects={}
    functions={name:getattr(C,name) for name in ('identity_keys','install_tables','insert_constraint','rules','vector','index_header')}
    functions['legacy_wp5_key']=C.legacy.wp5_key;functions['v3_require']=C.require
    functions['original_source_manifest_compose']=M.compose
    for name,function in functions.items():
        file=Path(inspect.getsourcefile(function)).absolute();ref=S.pin(file)
        S.need(refs.get(str(file))==ref,'EXACT_DECLARED_ORIGINAL_V3_FUNCTION_SOURCE '+name)
        objects[name]=dict(qualified_name=function.__module__+'.'+function.__qualname__,
            source_reference=ref,filename=function.__code__.co_filename,first_line=function.__code__.co_firstlineno)
    return C,M,dict(objects=objects,scientific_objects_called_directly_without_rewriting=True,
        original_Main_resource_helpers_invoked=False,RDKit_or_new_chemistry_invoked=False)
