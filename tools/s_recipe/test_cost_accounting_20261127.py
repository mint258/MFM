import unittest
from cost_accounting_20261127 import cpu_account, duration_seconds, gpu_wall_account


class CostAccounting(unittest.TestCase):
    def test_slurm_duration_and_unknown(self):
        self.assertEqual(duration_seconds('1-02:03:04.50'), 93784.5)
        self.assertEqual(duration_seconds('00:02.5'), 2.5)
        self.assertEqual(duration_seconds('00:00:00'), 0)
        self.assertIsNone(duration_seconds('Unknown'))
        with self.assertRaises(ValueError):
            duration_seconds('00:60:00')

    def test_gpu_handoff_union_duplicate_and_unknown_exit(self):
        base = dict(node='compute-0-20', producer=dict(uid=1278, pid=1, start_ticks=10),
            gpu_uuid='GPU-example', started_at=0, ended_at=10, exit_code=None, source='native')
        takeover = dict(base, producer=dict(uid=1278, pid=2, start_ticks=20),
            started_at=8, ended_at=20, exit_code=0, source='slurm')
        result = gpu_wall_account([base, dict(base, source='native_copy'), takeover])
        self.assertEqual(result['bound_GPU_wall_seconds'], 20)
        self.assertEqual(len(result['unique_producers']), 2)
        self.assertEqual(result['unknown_producer_exit_codes'], 1)
        with self.assertRaises(ValueError):
            gpu_wall_account([base, dict(base, gpu_uuid='GPU-other')])

    def test_cpu_failed_segments_zero_standby_and_duplicates(self):
        job = dict(job_id=1, user='zixiao', name='S_failed', allocated_cpus=2,
            elapsed_seconds=60, total_cpu='00:00:30', exit_code='75:0')
        standby = dict(job, job_id=2, name='S_unused', allocated_cpus=0,
            elapsed_seconds=0, total_cpu='00:00:00', exit_code='0:0')
        native = dict(node='compute-0-11', producer=dict(uid=1278, pid=3, start_ticks=30),
            cpu_user_seconds=4.0, cpu_system_seconds=1.0, exit_code=1)
        unknown = dict(native, producer=dict(uid=1278, pid=4, start_ticks=40),
            cpu_user_seconds=None, cpu_system_seconds=None)
        result = cpu_account([job, standby, job], [native, native, unknown])
        self.assertEqual(result['Slurm_allocated_CPU_seconds'], 120)
        self.assertEqual(result['Slurm_measured_CPU_seconds'], 30)
        self.assertEqual(result['native_measured_CPU_seconds'], 5)
        self.assertEqual(result['native_producers_missing_CPU_time'], 1)
        self.assertEqual(result['native_unique_producers'], 2)


if __name__ == '__main__':
    unittest.main()
