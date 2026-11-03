"""Original stable DATA guards, quotas and RSS56 observer for CPU export only."""
import time
from workflows.data_v1_final.pprime.formal_packed_day_v1 import io as Old
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v3 import resource as Resource
from . import contract as C
Store=Old.Store;held=Old.I.held;body=Old.body;value=Old.value

class Budget(C.M.Budget,Resource.Budget):
    def __init__(self,plan,proof,out,store):
        Old.I.OriginalBudget.__init__(self,plan,proof,out);self.store=store
        self.carve=C.meta(plan['root_carveout_review_reference'])
        C.M.carveout(self.carve,{'scope_key':C.KEY,'node':plan['node'],
          'resource_authority_reference':plan['resource_authority_reference'],'estimated_peak_output_bytes':self.cap})
        self.total=self.carve['total_future_reserved_bytes']
        if plan['node']=='compute-0-13':Client=C.M.Client
        elif plan['node']=='compute-0-19':
            from workflows.data_v1_final.execution.cpu_analysis_cpu19_v1.quota_provider import Client
        elif plan['node'] in ('compute-0-14','compute-0-18'):
            from workflows.data_v1_final.execution.cpu_analysis_day_v1.quota_provider import Client
        else:
            from workflows.data_v1_final.execution.cpu_analysis_general_nodes_v1.quota_provider import Client
        self.client=Client(plan['quota_provider_review_reference'],proof['request'])
        self.next_quota=0;self.quota=None;self.written=0
        self.active_mid_bytes={};self.unknown_mid_bytes={};self.peak_parallel_mids=0
        self.quota_guard_events=out/'quota_guard_events';self.quota_guard_events.mkdir()
        self.quota_guard_event_references=[]
    def used(self):return self.store.charged+sum(self.active_mid_bytes.values())+sum(self.unknown_mid_bytes.values())+(2<<20)
    def admit_mid(self,mid,cap):
        C.need(mid not in self.active_mid_bytes and mid not in self.unknown_mid_bytes,'ONE_UNIQUE_PARENT_MID_OUTPUT_ROLE')
        C.need(self.used()+cap+(258<<20)<self.cap,'PREPAID_MID_OUTPUT_PARTITION_AND_DRAIN')
        self.active_mid_bytes[mid]=cap;self.peak_parallel_mids=max(self.peak_parallel_mids,len(self.active_mid_bytes))
    def close_mid(self,mid,charged):
        cap=self.active_mid_bytes[mid]
        C.need(type(charged)is int and 0<=charged<=cap,'CLOSED_MID_BYTES_WITHIN_PREPAID_PARTITION')
        del self.active_mid_bytes[mid]
        self.store.reserve(charged)
    def unknown_mid(self,mid):
        self.unknown_mid_bytes[mid]=self.active_mid_bytes.pop(mid)
    def record(self,event):
        ref=self.store.json(self.quota_guard_events/('event_%06d.json'%len(self.quota_guard_event_references)),event)
        self.quota_guard_event_references.append(ref)
    def report(self):
        return {'charged_output_bytes':self.store.charged,'prepaid_metadata_drain_bytes':2<<20,
          'active_MID_output_reserved_bytes':sum(self.active_mid_bytes.values()),
          'UNKNOWN_MID_output_reserved_bytes':sum(self.unknown_mid_bytes.values()),
          'peak_actual_parallel_MID_roles':self.peak_parallel_mids,
          'all_future_reserved_bytes_counted_once':self.total,'last_actual_quota_observation':self.quota,
          'RSS_peak_bytes':self.peak,'minimum_MemAvailable_bytes':self.minimum,'stop_new':self.stop_new,
          'RSS_limit_bytes':self.RSS_LIMIT_BYTES,'software_working_budget_bytes':self.SOFTWARE_WORKING_BUDGET_BYTES,
          'Slurm_memory_requested':False,'signals_sent':False,'active_output_tree_stat_calls':0}
