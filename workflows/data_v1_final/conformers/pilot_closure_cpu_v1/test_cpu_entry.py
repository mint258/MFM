"""Run original six fixtures through CPU entry exports, plus two scope boundaries."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode=True
import close_pilot_cpu as CPU
from runtime_adapter import admit,checkpoint,validate_scope,bounded_map


class CpuBoundaryTests(unittest.TestCase):
    def test_scope_cannot_promote_to_conformer_or_wrong_resources(self):
        config={"fixtures":{"scope_key":"sprime_closure_fixtures_6","cpus":16,"memory_gib":8,"wall_seconds":600}}
        request={"kind":"analysis","partition":"cpu","pilot":True,"resource_policy":"CPU_BOUNDED_TEST_LIVE_MEMORY_V1",
                 "scope_key":"sprime_closure_fixtures_6","cpus":16,"memory_gib":8,"wall_seconds":600}
        validate_scope(request,config,"fixtures")
        with self.assertRaisesRegex(ValueError,"SMALL_ANALYSIS"):
            validate_scope(dict(request,kind="conformer"),config,"fixtures")
        with self.assertRaisesRegex(ValueError,"RESOURCES"):
            validate_scope(dict(request,memory_gib=32),config,"fixtures")
    def test_checkpoint_denial_stops_before_any_new_io_submission(self):
        class Pool:
            submitted=0
            def submit(self,*args):self.submitted+=1;raise AssertionError("MUST_NOT_SUBMIT")
        def deny():raise RuntimeError("FIXTURE_RESOURCE_DENIAL")
        pool=Pool()
        with self.assertRaisesRegex(RuntimeError,"RESOURCE_DENIAL"):
            list(bounded_map(pool,lambda x:x,[1,2,3],checkpoint_fn=deny))
        self.assertEqual(pool.submitted,0)


def original_suite():
    source=Path(__file__).parent.parent/"pilot_closure_v1"/"test_closure.py"
    if CPU.IO.digest(source)!="4b2817d082fc7831f618d74dfec3ad01f3a6c2f202ee900256f425bf3901b60f":
        raise ValueError("ORIGINAL_SIX_FIXTURE_SOURCE_CHANGED")
    # The unchanged original fixture import explicitly resolves to this new CPU
    # entry's exported validation functions; no old main or guard is executed.
    previous=sys.modules.get("close_pilot");sys.modules["close_pilot"]=CPU
    try:
        spec=importlib.util.spec_from_file_location("_sb2_original_six_cpu_bound",source)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    finally:
        if previous is None:sys.modules.pop("close_pilot",None)
        else:sys.modules["close_pilot"]=previous
    suite=unittest.defaultTestLoader.loadTestsFromModule(module)
    if suite.countTestCases()!=6:raise ValueError("EXACT_ORIGINAL_SIX_FIXTURES_REQUIRED")
    return suite


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--config",type=Path,required=True)
    p.add_argument("--cpu-runconfig",type=Path,required=True);p.add_argument("--root-preflight",type=Path,required=True)
    a=p.parse_args()
    proof=admit(a.root_preflight,Path(__file__),a.cpu_runconfig,a.config,"fixtures")
    suite=original_suite();suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(CpuBoundaryTests))
    result=unittest.TextTestRunner(verbosity=2).run(suite);checkpoint()
    print(json.dumps({"status":"CPU_CLOSURE_FIXTURES_PASSED" if result.wasSuccessful() else "CPU_CLOSURE_FIXTURES_FAILED",
        "original_cases":6,"new_boundaries":2,"executed_cases":result.testsRun,"cpu_guard":proof,"scientific_calls":0}))
    return 0 if result.wasSuccessful() else 1


if __name__=="__main__":raise SystemExit(main())
