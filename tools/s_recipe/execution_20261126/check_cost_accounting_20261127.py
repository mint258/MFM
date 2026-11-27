"""Check cost metadata arithmetic only, without collecting actual results."""
import shutil
import unittest
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
suite=unittest.defaultTestLoader.loadTestsFromName('test_cost_accounting_20261127')
count=suite.countTestCases();result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
value=dict(status='COMPLETE',new_tests=count,**execution_fields(),real_GPU_work=False,
    scope='Cost duration, actual-identity deduplication and interval union only; no actual cost collection, model, label, prediction, VAL or bootstrap inputs')
write(C/'cost_accounting_check_20261127.json',value)
write(R/'results/s_recipe/cost_accounting_check_20261127.json',value)
shutil.copyfile(C/'check_cost_accounting_20261127.py',
    R/'tools/s_recipe/execution_20261126/check_cost_accounting_20261127.py')
