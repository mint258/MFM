import unittest
from pathlib import Path
from workflows.benchmark_data.uniform_pprime_scope import remaining_budget,scope_base
from workflows.benchmark_data.uniform_sprime_scope import PEER_ENVIRONMENT_RESERVE

class ScopeBudget(unittest.TestCase):
    def test_both_active_outputs_and_peer_reserve_remain_budgeted(self):
        self.assertEqual(remaining_budget(10_000_000_000,20_000_000_000,1),
                         130_000_000_000+PEER_ENVIRONMENT_RESERVE)
        self.assertEqual(remaining_budget(100_000_000_000,100_000_000_000,1),
                         2*67108864+PEER_ENVIRONMENT_RESERVE)

    def test_large_pending_write_and_root_scope_are_preserved(self):
        self.assertEqual(remaining_budget(0,0,90_000_000_000),
                         170_000_000_000+PEER_ENVIRONMENT_RESERVE)
        self.assertEqual(scope_base(Path('/base/directive19/uniform_Sprime')),Path('/base'))
        with self.assertRaises(ValueError):scope_base(Path('/base/other'))

if __name__=='__main__':unittest.main()
