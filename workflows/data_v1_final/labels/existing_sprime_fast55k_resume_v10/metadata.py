"""Original draft/stage/close chain with explicit v10 source files."""
import types
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v8 import metadata as OLD
def source_paths():return list(dict.fromkeys([*OLD.source_paths(),*(C.HERE/n for n in C.FILES)]))
def draft(request_path,out):
    f=OLD.draft;g=dict(f.__globals__,C=C,source_paths=source_paths)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(request_path,out)
def stage(plan_path,out,scope_review=None):
    f=OLD.stage;g=dict(f.__globals__,C=C)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(plan_path,out,scope_review)
def close(registration_path,out):
    f=OLD.close;g=dict(f.__globals__,C=C)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(registration_path,out)
