import unittest
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
suite=unittest.defaultTestLoader.loadTestsFromName('test_physical_fullft_integration_20261127')
count=suite.countTestCases();result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
value=dict(status='COMPLETE',new_tests=count,**execution_fields(),real_GPU_work=False,
    old_tests_replayed=False,scope='Closed actual75 partial resumes identical scientific identity; 8GiB restricted to actually traced interpreter/provider')
write(C/'physical_fullft_integration_check_20261127.json',value)
write(R/'results/s_recipe/physical_fullft_integration_check_20261127.json',value)
