"""Only two new future-task-copy checks; running k5 is untouched."""
import unittest
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
suite=unittest.defaultTestLoader.loadTestsFromName('test_extension_spawn_clock_20261127')
count=suite.countTestCases()
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
value=dict(status='COMPLETE',new_tests=count,**execution_fields(),real_GPU_work=False,
    real_process_launch=False,old_tests_replayed=False,active_training_modules_changed=False,
    scope='Future node-clock task copy preserves original/science/duration and never extends deadline; bounds/misbound identity rejected')
write(C/'extension_spawn_clock_check_20261127.json',value)
write(R/'results/s_recipe/extension_spawn_clock_check_20261127.json',value)
