"""Private resource MRO; original quota/local-book/cost checks remain inherited."""
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2.io import *
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import io as Before
from . import contract as C,resource as Resource

class Budget(Before.Budget,Resource.Budget):
    # Resource.Budget is immediately before the common base observer in this
    # instance's MRO. The unchanged Preparation.Budget.check super() reaches it;
    # no shared class, module, callable, or running worker is patched.
    def __init__(self,plan,proof,out,roles,parent_store):
        I.OriginalBudget.__init__(self,plan,proof,out);self.roles=roles;self.parent_store=parent_store;self.plan=plan
        self.carve=C.meta(plan['root_carveout_review_reference']);self.cap=plan['output_cap_bytes']
        C.M.carveout(self.carve,{'scope_key':C.MODES[plan['mode']],'node':plan['node'],'resource_authority_reference':plan['resource_authority_reference'],'estimated_peak_output_bytes':self.cap})
        self.total=self.carve['total_future_reserved_bytes'];node=plan['node']
        if node=='compute-0-13':Client=C.M.Client
        elif node=='compute-0-19':
            from workflows.data_v1_final.execution.cpu_analysis_cpu19_v1.quota_provider import Client
        elif node in ('compute-0-14','compute-0-18'):
            from workflows.data_v1_final.execution.cpu_analysis_day_v1.quota_provider import Client
        else:
            from workflows.data_v1_final.execution.cpu_analysis_general_nodes_v1.quota_provider import Client
        self.client=Client(plan['quota_provider_review_reference'],proof['request']);self.next_quota=0;self.quota=None;self.written=0
        self.quota_guard_events=out/'quota_guard_events';self.quota_guard_events.mkdir();self.quota_guard_event_references=[]
        self.quota_guard_store=Store(self.quota_guard_events,64<<20);self.forecast_records=max(1,plan.get('maximum_assigned_records',C.MAX_RECORDS));self.scope_forecast_records=self.forecast_records;self.local_root=None;self.node_book=None
    def report(self):
        return dict(super().report(),software_working_budget_bytes=self.SOFTWARE_WORKING_BUDGET_BYTES,
          RSS_limit_bytes=self.RSS_LIMIT_BYTES,MemAvailable_minimum_bytes=4<<30,
          MemAvailable_minimum_node_fraction=.15,resource_version='PPRIME_PRIVATE_RSS56_V3',
          Slurm_memory_requested=False)
