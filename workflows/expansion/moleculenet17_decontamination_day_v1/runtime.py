"""Original guarded DATA streams/strict readback and resource Budget context."""
import time
from workflows.expansion.local6_tdc_decontamination_day_v1.io import held,frame,Lines,rows,readback,write,data_pin
from workflows.expansion.marcel_drugs_keys_main_v1.runtime import Budget as OriginalBudget
from workflows.data_v1_final.execution.cpu_analysis_day_v1.quota_provider import Client
from workflows.data_v1_final.execution.cpu_analysis_day_v1.contract import carveout
from workflows.data_v1_final.execution import finite_quota_observation_guard_v1 as QuotaGuard
from . import contract as C

class Budget(OriginalBudget):
    def __init__(self,plan,proof,out):
        super().__init__(plan,proof,out);self.carve=C.meta(plan['root_carveout_review_reference']);self.client=Client(plan['quota_provider_review_reference'],proof['request'])
        carveout(self.carve,{'scope_key':C.KEY,'node':proof['request']['node'],'resource_authority_reference':plan['resource_authority_reference'],
          'estimated_peak_output_bytes':self.cap});self.total=self.carve['total_future_reserved_bytes']
        self.next_quota=0;self.quota=None;self.written=0
        self.quota_guard_events=self.out/'quota_guard_events';self.quota_guard_events.mkdir(mode=0o700)
        self.quota_guard_event_references=[]
    def record_quota_guard_event(self,event):
        # Original write charges before exclusive creation/fsync and never calls
        # check/observe, so recording a rejected observation cannot recurse.
        path=self.quota_guard_events/('event_%06d.json'%len(self.quota_guard_event_references))
        self.quota_guard_event_references.append(write(path,event,self))
    def charge(self,n):
        C.need(type(n)is int and n>=0,'EXACT_OUTPUT_BYTES');self.written+=n;C.need(self.written+(258<<20)<self.cap,'FINITE_OUTPUT_PLUS_DRAIN')
    def check(self,dispatch=True,force=False):
        super().check(dispatch,force)
        if time.monotonic()>=self.next_quota:
            first=self.quota is None;self.quota=QuotaGuard.observe(self.client,
              expected_identity_reference=self.plan['quota_provider_identity_reference'],record=self.record_quota_guard_event)
            self.next_quota=time.monotonic()+60
            C.need(self.quota['identity_reference']==self.plan['quota_provider_identity_reference'],'EXACT_NEW_FINITE_PROVIDER_NO_RENEWAL')
            if first:C.need(self.quota['publisher_expires_unix_seconds']>=time.time()+self.plan['wall_seconds']-self.elapsed+300,'ACTUAL_LEASE_COVERS_REMAINING_DAY')
            C.need(self.quota['free_bytes']-self.total>=200000000000,'CURRENT_ACCOUNT_FUTURE_ONCE_PLUS200GB')

def positive(ref):return {k:ref[k] for k in ('path','bytes','sha256')}

def json_rows(ref,budget):return rows(positive(ref),lambda:budget.check())

def parquet(ref,plan,budget,columns=None):
    import pyarrow.parquet as pq
    with held(ref,[C.Q.ROOT/'artifacts'],plan['data_references']) as (stream,before):
        src=pq.ParquetFile(stream,pre_buffer=False)
        try:
            if columns is not None:C.need(set(columns)<=set(src.schema_arrow.names),'ACTUAL_ORIGINAL_COLUMNS_REQUIRED')
            ordinal=0
            for batch in src.iter_batches(batch_size=256,columns=columns,use_threads=False):
                budget.check()
                for row in batch.to_pylist():yield ordinal,row;ordinal+=1
        finally:src.close()
