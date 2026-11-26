"""Only the two new subset reporting boundaries, no scientific replay."""
import unittest
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
suite=unittest.defaultTestLoader.loadTestsFromName('test_molecule_scaling_delivery_20261127')
count=suite.countTestCases()
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
value=dict(status='COMPLETE',new_tests=count,**execution_fields(),real_GPU_work=False,
    old_tests_replayed=False,new_scientific_bootstrap_draws=0,
    scope='Matched9M boundaries/group identity only; missing second subset blocks original primary consumption')
write(C/'molecule_scaling_delivery_check_20261127.json',value)
write(R/'results/s_recipe/molecule_scaling_delivery_check_20261127.json',value)
