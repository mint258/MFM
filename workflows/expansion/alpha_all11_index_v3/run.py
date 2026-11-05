"""Actual Alpha full all11 V3 index producer; source approval is an input, not a side effect."""
import argparse
import io
import json
from pathlib import Path
import traceback
import unittest
from .reader import Reader,S
from .runtime import admit
from .science import initialize


def fixtures(out):
    from .test_reader import Native
    from .test_science import Science
    Native.root=out;suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (Native,Science)])
    stream=io.StringIO();tested=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    ref=S.save(out/'source_tests.json',dict(tests=tested.testsRun,failures=len(tested.failures),errors=len(tested.errors),
        skips=len(tested.skipped),transcript=stream.getvalue(),synthetic_fixtures_are_not_actual_source_adoption=True))
    S.need(tested.wasSuccessful() and tested.testsRun==4 and not tested.skipped,'FOUR_NATIVE_REPLICA_AND_ORIGINAL_V3_SEMANTIC_BOUNDARIES')
    return ref


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--startup-proof',type=Path,required=True);args=p.parse_args()
    plan=json.loads(args.plan.read_text());proof=json.loads(args.startup_proof.read_text())
    authority=admit(plan,proof,args.plan,args.startup_proof,'ALPHA_ALL11_EXCLUSION_INDEX_PLAN_V3','alpha_all11_index_v3')
    from workflows.expansion.alpha_runtime_v1.guard import Guard
    guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False);C,_,objects=initialize(proof);source_proof=S.save(out/'original_function_objects.json',objects)
        tests=fixtures(out);reader=Reader(plan,guard.check)
        manifest=reader.json(plan['source_manifest_reference']);ready9=reader.json(plan['ready9_manifest_reference'])
        S.need(manifest['prior_manifest_reference']==plan['ready9_manifest_reference']
               and manifest['root_molnet21_acceptance_reference']==plan['root_molnet21_acceptance_reference'],
               'EXACT_ORIGINAL_READY9_AND_ROOT_MOLNET_ORIGIN_BINDINGS')
        from .build import build
        result=build(plan,proof,out,reader,guard,manifest,ready9,C)
        result.update(plan_reference=S.pin(args.plan),startup_proof_reference=S.pin(args.startup_proof),
            original_function_object_proof=source_proof,source_tests=tests,profile_admission=authority,runtime=guard.receipt())
        S.save(out/'receipt.json',result)
    except BaseException as exc:
        if out.is_dir():S.save(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),partials_retained=True,
            no_incomplete_index_promoted=True,no_new_source_approval=True,original_graph_unknowns_retained=True))
        raise
    finally:guard.close()


if __name__=='__main__':main()
