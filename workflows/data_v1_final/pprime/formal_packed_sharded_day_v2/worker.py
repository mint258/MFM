"""Original entire worker code with only isolated local data-pin IO context."""
import types
from workflows.data_v1_final.pprime.pilot2000_execution_day_v1 import worker as Original
from . import contract as C,io as I

def local_raw_pin(path,roots):
    root=_state.get('OUT');C.need(root is not None and root in __import__('pathlib').Path(path).parents,'CURRENT_OWN_WORKER_LOCAL_ROOT')
    return I.pin(path,roots)

# A private namespace proxy is not mutation of P, ResourceOrigin, engine or the
# registered scientific modules. Only their output-only data_pin seam differs.
_origin_io=types.SimpleNamespace(**C.P.ResourceOrigin.I.__dict__);_origin_io.data_pin=local_raw_pin
_origin=types.SimpleNamespace(**C.P.ResourceOrigin.__dict__);_origin.I=_origin_io
_prepare=types.SimpleNamespace(**C.P.__dict__);_prepare.ResourceOrigin=_origin
_contract=types.SimpleNamespace(**C.__dict__);_contract.P=_prepare
_state=dict(Original.__dict__);_state.update(C=_contract,I=I,Q=C.Q,__name__=__name__)
_names=('close','initialize','original_protocol_with_owned_scratch','one')
for _name in _names:
    _old=getattr(Original,_name);_new=types.FunctionType(_old.__code__,_state,_old.__name__,_old.__defaults__,_old.__closure__)
    _new.__kwdefaults__=_old.__kwdefaults__;_state[_name]=_new;globals()[_name]=_new
Sink=Original.Sink

def inverse():
    for name in _names:
        old=getattr(Original,name);new=globals()[name]
        C.need(new.__code__ is old.__code__ and new.__defaults__==old.__defaults__ and new.__closure__ is old.__closure__,
          'ENTIRE_ORIGINAL_WORKER_CODE_DEFAULTS_CLOSURE:'+name)
    C.need(Sink is Original.Sink and C.record_once_key is C.Original.record_once_key,'ORIGINAL_SINK_AND_PHYSICAL_ONCE_OBJECT')
    C.need(Original.C is not _contract and Original.I is not I and C.P.ResourceOrigin.I.data_pin is not local_raw_pin,
      'NO_PATCH_TO_ORIGINAL_SCIENTIFIC_OR_IO_MODULES')
    return {'entire_original_worker_code':True,'only_private_output_data_pin_context_differs':True,
      'original_raw_sink_compute_pair_parser_export_readback_objects':True,'shared_module_monkeypatch':False}
