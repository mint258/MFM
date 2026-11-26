import unittest
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
suite=unittest.defaultTestLoader.loadTestsFromName('test_point_only_sequence_20261127')
count=suite.countTestCases();result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
value=dict(status='COMPLETE',new_tests=count,**execution_fields(),real_GPU_work=False,
    real_job_controls=False,old_tests_replayed=False,
    scope='Explicit same-point registered continuation; final member cannot submit another point, allowing E1 priority before T6')
write(C/'point_only_sequence_check_20261127.json',value)
write(R/'results/s_recipe/point_only_sequence_check_20261127.json',value)
