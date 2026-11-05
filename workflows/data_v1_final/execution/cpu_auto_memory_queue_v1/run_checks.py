"""Only eight new synthetic policy checks; no old fixtures or science reruns."""
import os,sys,unittest
from pathlib import Path
from .runtime import require_startup
from .shared import ROOT,write_new,now


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--startup-proof',required=True);a=p.parse_args()
    proof=require_startup(a.startup_proof,expected_source=Path(__file__),expected_kind='analysis')
    suite=unittest.defaultTestLoader.loadTestsFromName('workflows.data_v1_final.execution.cpu_auto_memory_queue_v1.test_contract')
    if suite.countTestCases()!=8:raise ValueError('EXACT_EIGHT_NEW_POLICY_CHECKS_REQUIRED')
    result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2).run(suite)
    passed=result.wasSuccessful() and result.testsRun==8 and not result.skipped
    write_new(ROOT/'control/cpu_auto_memory_checks'/(str(proof['job_id'])+'.json'),{
        'schema':'ACTUAL_CPU_AUTO_MEMORY_FIXTURES_V1','job_id':str(proof['job_id']),'observed_at':now(),
        'status':'EIGHT_NEW_BOUNDARIES_PASSED' if passed else 'NEW_BOUNDARY_FAILURE',
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
        'source_records_read':0,'scientific_calls':0,'memory_policy':proof['memory_policy'],
        'memory_admission_evaluated':False,'old_tests_rerun':False})
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
