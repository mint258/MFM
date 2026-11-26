"""Only new finite sequence safety boundaries; no old checks or science replay."""
import unittest
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
suite=unittest.defaultTestLoader.loadTestsFromName('test_controller_sequence_20261127')
count=suite.countTestCases()
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
value=dict(status='COMPLETE',new_tests=count,**execution_fields(),real_GPU_work=False,
    real_job_controls=False,old_tests_replayed=False,
    scope='Paused fits cannot advance; final original9M prefix cannot create an unregistered GPU point')
write(C/'controller_sequence_check_20261127.json',value)
write(R/'results/s_recipe/controller_sequence_check_20261127.json',value)
