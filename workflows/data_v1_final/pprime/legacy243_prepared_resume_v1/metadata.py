"""Unchanged formal metadata code, privately bound to this exact adopter."""
import types
from workflows.data_v1_final.pprime.formal_packed_day_v1 import metadata as Old
from . import contract as C
_state=dict(Old.__dict__);_state.update(C=C,Q=C.Q,M=C.M,__name__=__name__)
for _name in ('draft','finalize','main'):
    _old=getattr(Old,_name)
    _new=types.FunctionType(_old.__code__,_state,_old.__name__,_old.__defaults__,_old.__closure__)
    _new.__kwdefaults__=_old.__kwdefaults__;_state[_name]=_new;globals()[_name]=_new
if __name__=='__main__':main()
