"""Check only new failed-startup settlement and unchanged-state continuation."""
import json
from pathlib import Path
import shutil
import unittest
from fullft_startup_failure_20261127 import POLICY
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
suite=unittest.defaultTestLoader.loadTestsFromName('test_fullft_startup_failure_20261127')
count=suite.countTestCases()
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
for path in (R/'tools/s_recipe/fullft_native_execution_20261126.py',C/'close_failed_fullft_startup_20261127.py',C/'stop_failed_startup_wait_20261128.py',C/'launch_fullft_20261124.py',
        C/'deliver_execution_progress_20261127.py',C/'refresh_extension_daily_20261126.py'):
    compile(path.read_text(),str(path),'exec')
proof=dict(status='COMPLETE',policy=POLICY,new_tests=count,**execution_fields(),
    scientific_inputs_read=False,old_scientific_results_replayed=False,
    targeted_existing_cases_rechecked=8,added_boundary_cases=4,full_repository_regression_replayed=False,
    active_pretraining_or_global_guard_modified=False,
    scope='Exact producer, unchanged saved state, held zero-work cancel or actually closed wait-only allocation, unknown-exit no-replay, exact retirement and identical scientific inputs')
write(C/'fullft_startup_failure_check_20261127.json',proof)
write(R/'results/s_recipe/fullft_startup_failure_check_20261127.json',proof)
for name in ('check_fullft_startup_failure_20261127.py','close_failed_fullft_startup_20261127.py','stop_failed_startup_wait_20261128.py'):
    shutil.copyfile(C/name,R/'tools/s_recipe/execution_20261126'/name)
print(json.dumps(proof),flush=True)
