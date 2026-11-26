import unittest
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
suite=unittest.defaultTestLoader.loadTestsFromName('test_native_clock_anchor_20261127')
count=suite.countTestCases()
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
value=dict(status='COMPLETE',new_tests=count,**execution_fields(),real_job_controls=False,
    real_GPU_work=False,old_tests_replayed=False,
    scope='Both guards tolerate <=5s cross-host future timestamps without extending deadlines; stale/far-future contracts still fail')
write(C/'native_clock_anchor_check_20261127.json',value)
write(R/'results/s_recipe/native_clock_anchor_check_20261127.json',value)
