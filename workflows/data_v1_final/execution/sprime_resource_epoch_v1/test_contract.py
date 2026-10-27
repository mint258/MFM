"""Three pure boundary fixtures; no files, quota process, task data, science or queue."""
import copy,unittest
from . import contract as E


class Boundaries(unittest.TestCase):
    def test_only_literal_quota_option_may_change(self):
        original=['PY','-B','run_batch.py','--config','C','--prepared','P','--root-preflight','F','--quota-reuse-review','old','--output','O']
        result=E.replace_quota(original,'old','new')
        self.assertEqual(original[10],'old');self.assertEqual(result[10],'new')
        self.assertEqual(result[:10]+result[11:],original[:10]+original[11:])
        for bad in (original+['--quota-reuse-review','old'],original[:9],original[:10]+['other']+original[11:]):
            with self.assertRaises(ValueError):E.replace_quota(bad,'old','new')

    def test_new_directory_preserves_policy_and_absolute_lease(self):
        old={'publisher_output_dir':'old','maximum_runtime_seconds':86400,'maximum_age_seconds':120,
          'refresh_seconds':30,'cpu_poll_seconds':60,'quota_reserve_bytes':200000000000,'root_scope_notes':'old'}
        new=dict(old,publisher_output_dir='new',root_scope_notes='explicit new Root review')
        E.same_provider_scope(old,new)
        for change in ({'publisher_output_dir':'old'},{'maximum_age_seconds':121},{'maximum_runtime_seconds':86401},
                       {'refresh_seconds':31},{'quota_reserve_bytes':199999999999}):
            with self.assertRaises(ValueError):E.same_provider_scope(old,dict(new,**change))
        identity={'expires_unix_seconds':1000}
        self.assertEqual(E.deadline(700,identity,100),700)
        for bad in (100,701,float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):E.deadline(bad,identity,100)

    def test_old_mixed_stopped_or_incomplete_probe_cannot_authorize(self):
        new={'path':'new/identity.json','bytes':1,'sha256':'1'*64}
        old=dict(new,path='old/identity.json')
        budget={'stop_new_dispatch':None,'observation_failure':None,'signals_sent_to_science':False,'natural_drain':True,
          'whole_wave_output_reserved_bytes':E.G.WAVE_RESERVE,'publisher_reserved_bytes':64<<20,
          'actual_memory_observations':[{'rss_bytes':1,'MemAvailable':8<<30}],
          'actual_quota_observations':[{'identity_reference':new}]}
        E.healthy_probe_budget(budget,new)
        mutations=({'actual_quota_observations':[{'identity_reference':old}]},
          {'actual_quota_observations':[{'identity_reference':new},{'identity_reference':old}]},
          {'stop_new_dispatch':'RESOURCE_OBSERVATION_UNAVAILABLE'},{'actual_memory_observations':[]},
          {'observation_failure':{'error':'actual'}},{'whole_wave_output_reserved_bytes':E.G.WAVE_RESERVE-1},
          {'publisher_reserved_bytes':0},{'signals_sent_to_science':True})
        for changes in mutations:
            with self.assertRaises(ValueError):E.healthy_probe_budget(dict(copy.deepcopy(budget),**changes),new)


if __name__=='__main__':unittest.main()
