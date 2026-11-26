"""Only two newly integrated resource/old-Guard checks and new spawn syntax."""
import unittest
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
compile((C/'extension_native_spawn_20261124.py').read_text(),
    str(C/'extension_native_spawn_20261124.py'),'exec')
suite=unittest.defaultTestLoader.loadTestsFromName('test_future_fullft_resources_20261127')
count=suite.countTestCases()
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
value=dict(status='COMPLETE',new_tests=count,**execution_fields(),real_GPU_work=False,
    actual_process_launch=False,old_tests_replayed=False,active_training_modules_changed=False,
    scope='Future16 requires genuine estimate; legacy64 still valid; immutable node-clock copy accepted by unchanged pretraining NativeGuard')
write(C/'future_fullft_resources_check_20261127.json',value)
write(R/'results/s_recipe/future_fullft_resources_check_20261127.json',value)
