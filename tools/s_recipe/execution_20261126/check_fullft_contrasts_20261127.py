import unittest
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
suite=unittest.defaultTestLoader.loadTestsFromName('test_fullft_contrasts_20261127')
count=suite.countTestCases()
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
value=dict(status='COMPLETE',new_tests=count,**execution_fields(),new_fits=0,
    new_bootstrap_draws=0,real_prediction_files_read=0,old_tests_replayed=False,
    scope='New aggregate estimands stay separate; original P function rejects mismatched molecular draws')
write(C/'fullft_contrast_check_20261127.json',value)
write(R/'results/s_recipe/fullft_contrast_check_20261127.json',value)
