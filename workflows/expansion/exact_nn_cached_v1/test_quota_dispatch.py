"""Metadata resource dispatch only, no real quota/scientific calculations."""
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
from .run import Guard


class QuotaDispatch(unittest.TestCase):
    def test_Alpha_actual_scope_credit_and_Main_Lustre_zero_credit_remain_separate(self):
        for kind,profile,default in [('gluster_directory_quota_deem_statfs',{'fixture':True},True),
                ('gluster_directory_quota_deem_statfs',None,False),('lustre',None,False),('sdk',None,False)]:
            guard=object.__new__(Guard)
            guard.plan={'output_cap_bytes':100,'parent_rss_cap_bytes':10,'quota_authority':{'kind':kind}}
            if profile:guard.plan['runtime_profile_reference']=profile
            guard.scope=Path('/fixture');guard.last=0;guard.usage=lambda:7;guard.checker=Mock()
            with patch('workflows.expansion.exact_nn_cached_v1.run.current_rss',return_value=1):guard.poll(True,reserve=2)
            provider=guard.checker.call_args.kwargs['prequery_credit_provider']
            if default:self.assertIsNone(provider)
            else:self.assertEqual(provider(12345),0)
            self.assertEqual(guard.checker.call_args.args[1],7)


if __name__=='__main__':unittest.main()
