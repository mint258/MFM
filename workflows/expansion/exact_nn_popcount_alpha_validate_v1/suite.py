"""Small real test-suite receipt; never claims full-reference equivalence."""
import argparse
import importlib
import os
from pathlib import Path
import unittest
from ..alpha_runtime_v1 import common as Q

SUITES = {'workflows.expansion.exact_nn_popcount_cpp_v1.test_native':8,
    'workflows.expansion.exact_nn_cached_v1.test_exact':9}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--module',required=True,choices=tuple(SUITES))
    p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    module=importlib.import_module(a.module);suite=unittest.defaultTestLoader.loadTestsFromModule(module)
    Q.need(suite.countTestCases()==SUITES[a.module],'Exact8/9 actual source cases required')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    body=dict(schema='ALPHA_POPCOUNT_BOUNDARY_SUITE_ONLY_V1',scope='SMALL_BOUNDARY_SUITE_ONLY',module=a.module,
        source_reference=Q.reference(module.__file__),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        skips=len(result.skipped),success=result.wasSuccessful()and not result.skipped,
        uid=os.getuid(),job_id=os.environ.get('SLURM_JOB_ID'),full_reference_equivalence_claimed=False)
    Q.write(a.output,body)
    Q.need(body['success']and body['tests']==SUITES[a.module],'Native small suite failed/skipped; no full benchmark')


if __name__=='__main__':main()
