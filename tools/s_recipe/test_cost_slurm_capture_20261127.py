import unittest
from cost_slurm_capture_20261127 import cache_ready,parse_rows


class CostSlurm(unittest.TestCase):
    def test_filter_own_S_actual_jobs_and_preserve_failed_cpu_time(self):
        row='4540001|S_fit|zixiao|FAILED|75:0|compute-0-20|gpu|16|70|2026-11-27T04:00:00|2026-11-27T04:01:10|00:01:20|00:01:10|00:00:10'
        included,excluded=parse_rows('\n'.join((row,row.replace('4540001','4540002').replace('S_fit','P_fit'),
            row.replace('4540001','4540003').replace('zixiao','another_user'),row.replace('4540001','4540001.batch'))))
        self.assertEqual(len(included),1)
        self.assertEqual(included[0]['elapsed_seconds'],70)
        self.assertEqual(included[0]['total_cpu'],'00:01:20')
        self.assertEqual(excluded,[4540002,4540003])

    def test_running_zero_exit_is_not_terminal_but_unused_cancel_is(self):
        base=dict(state='PENDING',exit_code='0:0',elapsed_seconds=0,total_cpu='00:00:00')
        self.assertFalse(cache_ready(base))
        self.assertFalse(cache_ready(dict(base,state='RUNNING')))
        self.assertTrue(cache_ready(dict(base,state='CANCELLED by 1278')))
        self.assertFalse(cache_ready(dict(base,state='COMPLETED',total_cpu='Unknown')))


if __name__=='__main__':unittest.main()
