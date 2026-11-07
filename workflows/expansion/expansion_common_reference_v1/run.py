"""Full actual Common source component; stop before PM7/D7 computations."""
import argparse
import io
import json
import os
from pathlib import Path
import time
import traceback
import unittest
from .runtime import Budget,admit,need,pin,read,save
from .context import Context,bind_original_namespace,ensure_spawn_entrypoint
from . import census,projection

MODULE='workflows.expansion.expansion_common_reference_v1.run'
NAMESPACE_ENV='EXPANSION_COMMON_ORIGINAL_CONFIG_REFERENCE'

# multiprocessing spawn replays this actual entry module before unpickling
# original scientific callables. Route its legacy imports just as in the parent.
if __name__=='__mp_main__' and NAMESPACE_ENV in os.environ:
    bind_original_namespace(json.loads(os.environ[NAMESPACE_ENV]))


def fixtures(out):
    from .test_source_views import SourceViews
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(SourceViews)
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    ref=save(out/'source_tests.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        skips=len(result.skipped),transcript=stream.getvalue(),before_original_DATA=True))
    need(result.wasSuccessful() and result.testsRun==7 and not result.skipped,'SEVEN_SOURCE_VIEW_TESTS_REQUIRED')
    return ref


def run(plan,proof,plan_path,proof_path):
    admit(plan,proof,plan_path,proof_path,MODULE)
    out=Path(plan['output_directory']);base=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion')
    need(out.is_absolute() and base in out.parents and not out.exists() and '..' not in out.parts,'FRESH_ABSOLUTE_EXPANSION_ARTIFACT_OUTPUT')
    out.mkdir(parents=True);os.environ[NAMESPACE_ENV]=json.dumps(plan['original_config_reference'],sort_keys=True)
    bind_original_namespace(plan['original_config_reference'])
    tests=fixtures(out);budget=Budget(plan,proof,out);ctx=Context(plan,proof,out,budget)
    start=time.monotonic();membership_ref=graph_ref=None
    try:
        if plan['mode'] in ('membership','all'):
            from workflows.data_v1_final.conformers.postprocess_day_v1 import common as Original
            from workflows.data_v1_final.conformers.formal_cpu_auto_finalize_mapping_v2 import finalize as Scientific
            need(Original.membership is Scientific.membership and Original.merge_counts is Scientific.merge_counts
                and Original.exclusion_gates is Scientific.exclusion_gates,'DIRECT_ORIGINAL_COMMON_SCIENTIFIC_OBJECTS')
            index_ref,index=census.derive(ctx)
            ensure_spawn_entrypoint()
            Original.build(ctx,index_ref)
            membership_ref=ctx.reference(ctx.common_out/'manifest.json');common=ctx.read(membership_ref)
            need(common['schema']=='COMMON_POPULATION_PRODUCER_V1' and common['pilot_only'] is False
                and common['execution_unresolved_molecules']==3436 and len(common['membership_tables'])==16,
                'ACTUAL_FULL_ORIGINAL_COMMON_NOT_PILOT_PROXY')
        else:
            acceptance=read(plan['common_acceptance_reference'])
            need(acceptance['schema']=='ROOT_EXPANSION_FULL_COMMON_COMPONENT_ACCEPTANCE_V1'
                and acceptance['status']=='APPROVED_ACTUAL_COMPLETE_COMMON_MEMBERSHIP'
                and acceptance['reviewer']=='root' and acceptance['D7_or_orders_release'] is False,
                'INDEPENDENT_ACTUAL_FULL_COMMON_ACCEPTANCE_REQUIRED')
            membership_ref=acceptance['source_manifest_reference'];ctx.trust([membership_ref]);common=ctx.read(membership_ref)
            need(common['schema']=='COMMON_POPULATION_PRODUCER_V1' and common['pilot_only'] is False,'ACTUAL_NONPILOT_COMMON')
            ctx.common_out=Path(membership_ref['path']).parent;ctx.trust(common['membership_tables']+common['physical_geometry_tables'])
        ctx.common_reference=membership_ref
        if plan['mode'] in ('projection','all'):
            graph_ref,graph=projection.produce(ctx,common)
        else:graph=None
        receipt=dict(schema='EXPANSION_COMMON_REFERENCE_RECEIPT_V1',
            status='COMPONENTS_PRODUCED_PENDING_ACTUAL_PARENT_C0_AND_ROOT_ACCEPTANCE',
            job_id=str(proof['job_id']),uid=os.getuid(),node=plan['node'],cpus=plan['cpus'],
            plan_reference=pin(plan_path),startup_proof_reference=pin(proof_path),source_tests=tests,
            common_producer_manifest=membership_ref,graph_producer_receipt=graph_ref,
            original_full_source_molecules=1220466,ordinary_supported_outcomes=90069,
            original_unknown_excluded=3436,ordinary_UFF_unsupported=9282,
            common_reference_is_full=True,PM7_D7_numeric_computation_performed=False,
            orders_frozen=False,D7_released=False,new_UFF_QM_calls=0,
            membership_quality_rules_unchanged=True,graph_HOLD_MIDs=graph['HOLD_MIDs'] if graph else None,
            actual_parent_C0_not_self_claimed=True,elapsed_seconds=time.monotonic()-start,resources=budget.receipt())
        receipt['reused_closed_source_index']=getattr(ctx,'reused_index_provenance',None)
        return save(out/'receipt.json',receipt)
    except BaseException as exc:
        save(out/'failure.json',dict(schema='EXPANSION_COMMON_REFERENCE_FAILURE_V1',error=repr(exc),traceback=traceback.format_exc(),
            actual_job_id=str(proof['job_id']),common_candidate_reference=membership_ref,original_inputs_modified=False,
            no_fallback_reference_released=True,resources=budget.receipt()))
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path);p.add_argument('--startup-proof',type=Path)
    p.add_argument('--source-spawn-fixture',type=Path)
    a=p.parse_args()
    if a.source_spawn_fixture:
        from .spawn_fixture import run as source_fixture
        print(json.dumps(source_fixture(a.source_spawn_fixture),sort_keys=True));return
    if a.plan is None or a.startup_proof is None:p.error('production requires --plan and --startup-proof')
    plan=json.loads(a.plan.read_text());proof=json.loads(a.startup_proof.read_text())
    print(json.dumps(run(plan,proof,a.plan,a.startup_proof),sort_keys=True))


if __name__=='__main__':main()
