"""Actual CPU guide fallback guard validation."""
import json,os,socket,time,unittest
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
assert socket.gethostname().split('.')[0] in ['compute-0-'+str(n) for n in [2,8,9,10,11,12,13,14,15,16,17,18,19]] and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
out=R/'validation'/('message_bootstrap_guards_job'+os.environ['SLURM_JOB_ID']);out.mkdir(exist_ok=False)
start=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_message_bootstrap_v1'))
document=dict(status='MESSAGE_BOOTSTRAP_GUIDE_GUARDS_PASS' if result.wasSuccessful() else 'MESSAGE_BOOTSTRAP_GUIDE_GUARDS_FAILED',job_id=os.environ['SLURM_JOB_ID'],tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),elapsed_seconds=time.monotonic()-start,scientific_updates=0,formal_training_authorized=False)
with (out/'result.json').open('x') as f:json.dump(document,f,indent=2);f.write('\n')
assert result.wasSuccessful() and result.testsRun==10
