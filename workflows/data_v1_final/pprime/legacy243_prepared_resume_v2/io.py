"""Private exact-index guard and original quotas with the existing RSS56 MRO."""
import contextlib,types
from workflows.data_v1_final.pprime.formal_packed_day_v1 import io as Old
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v3 import resource as Resource
from . import contract as C
Store=Old.Store
# Formal inherits pilot settle's entire code, but pilot globals.C.CAP is32GiB.
# Bind ONLY this function's private C to the unchanged formal64GiB authority.
_settle_origin=Old.Roles.settle
_settle_globals=dict(_settle_origin.__globals__);_settle_globals['C']=Old.C
_formal_settle=types.FunctionType(_settle_origin.__code__,_settle_globals,_settle_origin.__name__,
    _settle_origin.__defaults__,_settle_origin.__closure__)
_formal_settle.__kwdefaults__=_settle_origin.__kwdefaults__
class Roles(Old.Roles):
    settle=_formal_settle

def roles_binding_proof():
    C.need(Roles.__bases__==(Old.Roles,) and Roles.settle.__code__ is _settle_origin.__code__
      and Roles.settle.__defaults__ is _settle_origin.__defaults__ and Roles.settle.__closure__ is _settle_origin.__closure__
      and Roles.settle.__kwdefaults__ is _settle_origin.__kwdefaults__,'ENTIRE_ORIGINAL_SETTLE_CODE_DEFAULTS_CLOSURE')
    C.need(set(_settle_globals)==set(_settle_origin.__globals__)and all(_settle_globals[k]is _settle_origin.__globals__[k]
      for k in _settle_globals if k!='C')and _settle_globals['C']is Old.C and Old.C.CAP==64<<30
      and _settle_origin.__globals__['C'].CAP==32<<30,'ONLY_PRIVATE_SETTLE_FORMAL64_C_NOT_PILOT32_NO_GLOBAL_PATCH')
    C.need(Roles.bound is Old.Roles.bound and Roles.can_start is Old.Roles.can_start and Roles.add_export is Old.Roles.add_export,
      'EXACT_FORMAL_ROLE_BOUNDS_ADMISSION_EXPORT_AND_UNKNOWN_ACCOUNTING')
    return {'entire_settle_code_unchanged':True,'only_private_C_binding':'formal_packed_day_v1.contract',
      'formal_CAP_bytes':64<<30,'old_pilot_CAP_bytes':32<<30,'old_shared_modules_modified':False}

roles_binding_proof()

class Budget(Old.Budget,Resource.Budget):
    def report(self):
        return dict(super().report(),software_working_budget_bytes=self.SOFTWARE_WORKING_BUDGET_BYTES,
          RSS_limit_bytes=self.RSS_LIMIT_BYTES,MemAvailable_minimum_bytes=4<<30,
          MemAvailable_minimum_node_fraction=.15,resource_version='PPRIME_PRIVATE_RSS56_V3',
          Slurm_memory_requested=False)

def execution_io(index,out):
    """Only this exact adopted index may cross the original new-output guard."""
    inner=types.SimpleNamespace(**vars(Old.I));outer=types.SimpleNamespace(**vars(Old))
    @contextlib.contextmanager
    def held(ref,roots,declared=None):
        if ref==index:
            C.need(roots==[out] and declared==[index]
              and index['path']==str(C.OLD_OUTPUT/'prepare/prepared.duckdb'),
              'EXACT_IMMUTABLE_ADOPTED_INDEX_SEAM_ONLY')
            roots=[C.OLD_OUTPUT/'prepare']
        with Old.I.held(ref,roots,declared) as value:yield value
    inner.held=held;outer.I=inner
    return outer
