"""Original Budget/Writer plus original finite account-quota Client, no renewal."""
import os,time
from workflows.expansion.marcel_drugs_keys_main_v1.runtime import Budget as OriginalBudget,Writer
from . import contract as C
Q=C.Q
class Budget:
    def __init__(self,plan,proof,out):
        self.base=OriginalBudget(plan,proof,out);self.cap=self.base.cap;self.plan=plan;self.last_poll=0;self.observations=0;self.last_quota=None
        review=C.meta(plan['quota_reuse_reference']);self.wave=review['whole_wave_output_reserve_bytes']
        self.client=C.Provider.Client(review['provider_review_reference'],proof['request'])
        self.check(True,True)
    def used(self):return self.base.used()
    def check(self,dispatch=True,force=False):
        self.base.check(dispatch=False,force=force)
        if force or time.monotonic()-self.last_poll>=60:
            self.last_poll=time.monotonic()
            try:
                obs=self.client.observe();self.last_quota=obs;self.observations+=1
                remaining=max(0,self.cap-self.used());free=obs['free_bytes']
                Q.need(free-self.wave-remaining>=200000000000,'ACCOUNT_QUOTA_WHOLE_WAVE_PLUS_OWN_REMAINING_PLUS200GB')
                physical=os.statvfs(Q.ROOT);physical_free=physical.f_bavail*physical.f_frsize
                Q.need(physical_free-self.wave-remaining>=200000000000,'VERIFIED_SHARED_PHYSICAL_WAVE_PLUS_OWN_PLUS200GB')
                obs['current_shared_physical_available_bytes']=physical_free
            except Exception as exc:
                self.base.stop_new=self.base.stop_new or 'QUOTA_PROVIDER_UNKNOWN_EXPIRED_OR_RESERVE_STOP:'+type(exc).__name__+':'+str(exc)
        if dispatch:Q.need(self.base.stop_new is None,self.base.stop_new or 'STOP_NEW_DISPATCH_NATURAL_DRAIN')
    def receipt(self):return {'original_Budget_and_Writer_objects':True,'original_quota_Client_object':False,'finite25h_resource_bridge_original_parser_freshness':True,'quota_observations':self.observations,
        'last_actual_quota_observation':self.last_quota,'whole_wave_reserve_bytes':self.wave,'peak_parent_children_RSS_bytes':self.base.peak,
        'minimum_MemAvailable_bytes':self.base.minimum,'stop_new_reason':self.base.stop_new,'publisher_renewed':False,'forced_signals_sent':False}
