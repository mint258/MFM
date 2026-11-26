"""Two affected standby IO regressions only; no real model/job controls."""
import unittest
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
suite=unittest.defaultTestLoader.loadTestsFromName('test_handoff_path_20261127')
count=suite.countTestCases()
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
for path in (R/'tools/s_recipe/e1_frozen_report_20261126.py',
             C/'close_readout_resources_20261126.py',C/'inspect_failed_readout_standby_20261127.py'):
    compile(path.read_text(),str(path),'exec')
value=dict(status='COMPLETE',new_tests=count,**execution_fields(),
    scope='Two real standby functions publish string task paths and skip completed work; actual job/model controls mocked',
    real_GPU_work=False,real_job_controls=False,old_tests_replayed=False)
write(C/'handoff_path_check_20261127.json',value)
write(R/'results/s_recipe/handoff_path_check_20261127.json',value)
