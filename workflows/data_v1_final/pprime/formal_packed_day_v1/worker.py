"""Entire original worker functions with isolated new authority/IO state only."""
import types
from workflows.data_v1_final.pprime.pilot2000_execution_day_v1 import worker as Original
from . import contract as C,io as I
_state=dict(Original.__dict__);_state.update(C=C,I=I,Q=C.Q,__name__=__name__)
_names=('close','initialize','original_protocol_with_owned_scratch','one')
for _name in _names:
    _old=getattr(Original,_name)
    _new=types.FunctionType(_old.__code__,_state,_old.__name__,_old.__defaults__,_old.__closure__)
    _new.__kwdefaults__=_old.__kwdefaults__;_state[_name]=_new;globals()[_name]=_new
# Sink's callable body uses no contract/global lifecycle state; original object.
Sink=Original.Sink

def inverse():
    for name in _names:
        old=getattr(Original,name);new=globals()[name]
        C.need(new.__code__ is old.__code__ and new.__defaults__==old.__defaults__ and new.__closure__ is old.__closure__,
          'ENTIRE_ORIGINAL_WORKER_CODE_DEFAULTS_CLOSURE:'+name)
    C.need(Sink is Original.Sink and C.record_once_key is C.Original.record_once_key,'ORIGINAL_SINK_AND_GLOBAL_PHYSICAL_ONCE_OBJECTS')
    C.need(_state['C'] is C and _state['I'] is I and Original.C is not C and Original.I is not I,'PRIVATE_NEW_AUTHORITY_CONTEXT_NO_OLD_GLOBAL_PATCH')
    return {'entire_original_worker_code':True,'physical_once_namespace_unchanged':True,'shared_scientific_module_mutation':False}
