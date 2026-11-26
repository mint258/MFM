"""Only the two new reporting boundaries; no model/old test replay."""
import unittest
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C, REPO as R, write
suite=unittest.defaultTestLoader.loadTestsFromName('test_reporting_delivery_20261127')
count=suite.countTestCases()
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful(): raise SystemExit(1)
value=dict(status='COMPLETE', new_tests=count, **execution_fields(),
    real_model_work=False, original_score_files_consumed=0, old_tests_replayed=False,
    scope='Seed-mean and ensemble CI stay distinct; missing final prefix blocks all source-score reads')
write(C/'reporting_delivery_check_20261127.json', value)
write(R/'results/s_recipe/reporting_delivery_check_20261127.json', value)
