"""Admitted native synthetic validation only, without any all11 source adoption."""
import argparse
import json
from pathlib import Path
from .reader import S
from .runtime import admit
from .science import initialize
from .run import fixtures


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--startup-proof',type=Path,required=True);args=p.parse_args()
    plan=json.loads(args.plan.read_text());proof=json.loads(args.startup_proof.read_text())
    authority=admit(plan,proof,args.plan,args.startup_proof,'ALPHA_ALL11_SOURCE_FIXTURE_PLAN_V1','alpha_all11_source_fixture_v1')
    from workflows.expansion.alpha_runtime_v1.guard import Guard
    guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False);_,_,objects=initialize(proof);tested=fixtures(out);guard.check()
        S.save(out/'receipt.json',dict(schema='ALPHA_ALL11_NATIVE_SOURCE_FIXTURES_ONLY_V1',status='FOUR_SYNTHETIC_NATIVE_SOURCE_FIXTURES_PASS',
            plan_reference=S.pin(args.plan),startup_proof_reference=S.pin(args.startup_proof),profile_admission=authority,
            source_tests=tested,original_function_objects=objects,runtime=guard.receipt(),real_DATA_read=False,
            user_scope_approval_created_or_inferred=False,all11_source_manifest_created=False,index_or_filter_created=False,
            actual_parent_C0_pending_root_readback=True,global_pool_release=False))
    finally:guard.close()


if __name__=='__main__':main()
