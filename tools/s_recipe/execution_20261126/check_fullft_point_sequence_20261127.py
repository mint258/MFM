"""Only the three new foreground orchestration boundaries; no real controls."""
import unittest
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
suite=unittest.defaultTestLoader.loadTestsFromName('test_fullft_point_sequence_20261127')
count=suite.countTestCases()
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
value=dict(status='COMPLETE',new_tests=count,**execution_fields(),real_GPU_work=False,
    real_job_controls=False,old_tests_replayed=False,
    scope='Running0:0 is not completion; finite wait does not cancel/launch; next point is never advanced')
write(C/'fullft_point_sequence_check_20261127.json',value)
write(R/'results/s_recipe/fullft_point_sequence_check_20261127.json',value)
