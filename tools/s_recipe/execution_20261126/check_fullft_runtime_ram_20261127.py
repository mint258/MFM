"""Check only the new optional runtime remaining-RAM accounting."""
import json
import os
from pathlib import Path
import shutil
import unittest
import lifecycle_20261122 as life
from fullft_runtime_ram_20261127 import POLICY,self_sample
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
suite=unittest.defaultTestLoader.loadTestsFromName('test_fullft_runtime_ram_20261127')
count=suite.countTestCases()
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
sample=self_sample(vars(life.identity(os.getpid())),6*1024**3)
for path in (R/'tools/s_recipe/finetune_extension_20261124.py',C/'launch_fullft_20261124.py'):
    compile(path.read_text(),str(path),'exec')
proof=dict(status='COMPLETE',policy=POLICY,new_tests=count,actual_self_anon_observation=sample,
    **execution_fields(),scientific_inputs_read=False,old_results_or_tests_replayed=False,
    global_storage_or_pretraining_source_modified=False,
    scope='Runtime own anonymous PSS, remaining-vs-peak arithmetic, true shortage, shrinking residency, default-off, exact owner and original disk refusal only')
write(C/'fullft_runtime_ram_check_20261127.json',proof)
write(R/'results/s_recipe/fullft_runtime_ram_check_20261127.json',proof)
shutil.copyfile(C/'check_fullft_runtime_ram_20261127.py',R/'tools/s_recipe/execution_20261126/check_fullft_runtime_ram_20261127.py')
print(json.dumps(proof),flush=True)
