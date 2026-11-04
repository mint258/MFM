"""Original staging and closure, with one explicit checkpoint declaration."""
import types
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v7 import metadata as OLD
def source_paths():return list(dict.fromkeys([*OLD.source_paths(),*(C.HERE/n for n in C.FILES)]))
def draft(request_path,out):
    f=OLD.draft;g=dict(f.__globals__,C=C,source_paths=source_paths)
    ref=types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(request_path,out/'base')
    p=C.meta(ref);request=C.meta(C.P.pin(request_path))
    p['metadata_recovery_reference']=request['metadata_recovery_reference']
    p['source_references']=C.unique([*p['source_references'],p['metadata_recovery_reference'],
      *request.get('checkpoint_source_references',[])])
    p['scope_parameters']=C.scope(p)
    return C.P.write(out/'plan_candidate.json',p)
def stage(plan_path,out,scope_review=None):
    f=OLD.stage;g=dict(f.__globals__,C=C)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(plan_path,out,scope_review)
def close(registration_path,out):
    f=OLD.close;g=dict(f.__globals__,C=C)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(registration_path,out)
