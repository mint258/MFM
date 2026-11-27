import unittest
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
suite=unittest.defaultTestLoader.loadTestsFromName('test_fullft_exp_ram_20261127')
count=suite.countTestCases();result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
value=dict(status='COMPLETE',new_tests=count,**execution_fields(),real_GPU_work=False,
    scope='Closed actual partial scientific identity; larger peaks, QM9 and untraced interpreter/provider rejected')
write(C/'fullft_exp_ram_check_20261127.json',value)
write(R/'results/s_recipe/fullft_exp_ram_check_20261127.json',value)
