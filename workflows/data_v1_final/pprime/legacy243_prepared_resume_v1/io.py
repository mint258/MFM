"""Private exact-index guard and original quotas with the existing RSS56 MRO."""
import contextlib,types
from workflows.data_v1_final.pprime.formal_packed_day_v1 import io as Old
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v3 import resource as Resource
from . import contract as C
Store=Old.Store;Roles=Old.Roles

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
