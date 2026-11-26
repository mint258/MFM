import unittest
import e1_local_decision_20261127
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
suite=unittest.defaultTestLoader.loadTestsFromName('test_e1_cached_components_20261127')
count=suite.countTestCases()
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
value=dict(status='COMPLETE',new_tests=count,**execution_fields(),new_fits=0,new_bootstrap_draws=0,
    real_prediction_files_read=0,old_tests_replayed=False,
    scope='Final E1 can reuse closed frozen components without original arrays; mismatched cached point means rejected')
write(C/'e1_cached_components_check_20261127.json',value)
write(R/'results/s_recipe/e1_cached_components_check_20261127.json',value)
