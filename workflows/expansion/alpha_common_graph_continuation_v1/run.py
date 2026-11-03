"""Fresh Alpha graph validation of a closed Main Common source stage."""
import argparse,concurrent.futures as cf,io,json,multiprocessing as mp,os,pathlib,tempfile,traceback,unittest
from . import io as I,science,transport,projection


def admit(plan,proof,plan_path,proof_path):
    from workflows.expansion.alpha_runtime_v1 import profile
    authority=profile.admit(plan,minimum_workers=16);request=proof['request']
    I.need(plan['schema']=='ALPHA_COMMON_GRAPH_CONTINUATION_PLAN_V1' and plan['mode'] in ('source','full')
      and request['scope_key']==plan['scope_key']=='alpha_common_graph_continuation_v1'
      and request['producer_plan_reference']==I.pin(plan_path),'EXACT_ALPHA_COMMON_PLAN')
    I.need(request['execution_argv']==plan['execution_argv'] and '--plan' in plan['execution_argv']
      and plan['execution_argv'][plan['execution_argv'].index('--plan')+1]==str(plan_path)
      and plan['execution_argv'][plan['execution_argv'].index('--startup-proof')+1]==str(proof_path),'EXACT_FRESH_ROOT_LAUNCH')
    I.need(os.getuid()==1264 and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID')
      and proof['boot_id']==pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'CURRENT_ALPHA_PARENT_NOT_MAIN_IDENTITY')
    refs={r['path']:r for r in request['source_references']}
    for file in pathlib.Path(__file__).parent.glob('*.py'):I.need(refs.get(str(file.absolute()))==I.pin(file),'CURRENT_NEW_ADAPTER_SOURCE')
    for ref in request['source_references']:I.read_source(ref)
    if plan.get('io_policy_reference') is not None:
        I.need(plan['io_policy_reference'] in request['source_references'],'EXPLICIT_NEW_IO_POLICY_IN_CURRENT_ROOT_SOURCE_AUTHORITY')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    return authority


def fixtures(plan,out,objects):
    from .test_source import Boundaries
    from workflows.expansion.common_molecular_fp_main_v1.test_v1 import Boundaries as Original
    scratch=out/'source_scratch';scratch.mkdir();tempfile.tempdir=str(scratch)
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (Original,Boundaries)])
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    I.need(result.testsRun==6 and result.wasSuccessful() and not result.skipped,'ORIGINAL3_AND_NEW3_SOURCE_CASES')
    ctx=mp.get_context('spawn');barrier=ctx.Barrier(16);directory=out/'source_worker_proofs';directory.mkdir()
    task=dict(molecule_id='SYNTHETIC_SOURCE_FIXTURE_ONLY',effective_role='TRAIN',native_records=1,
      variants=[dict(variant_id='source_fixture',status='SOURCE_GRAPH_PRESENT',source_smiles_for_original_template='CCO')])
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=science.initialize,initargs=(plan,barrier,str(directory))) as pool:
        answers=[f.result() for f in [pool.submit(objects['kernel'].work,task) for _ in range(64)]]
    I.need(len(list(directory.glob('worker_*.json')))==16 and all(v['reduction']['status']=='UNIQUE_GRAPH_PROJECTION_CANDIDATE' for v in answers),'FRESH16_SPAWN_WORKERS_ORIGINAL_KERNEL_AND_REDUCER')
    return I.save(out/'source_tests.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),
      transcript=stream.getvalue(),original3_cases_reused=True,new3_transport_IO_cases=True,fresh_spawn_workers=16,synthetic_tasks=64,before_population_DATA=True))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=json.loads(a.plan.read_text());proof=json.loads(a.startup_proof.read_text());authority=admit(plan,proof,a.plan,a.startup_proof)
    from workflows.expansion.alpha_runtime_v1.guard import Guard
    guard=Guard(plan);out=pathlib.Path(plan['output_directory'])
    try:
        guard.check();out.mkdir(parents=True,exist_ok=False);objects=science.load(plan);tests=fixtures(plan,out,objects);io_tests=None
        if plan.get('io_policy_reference') is not None:
            from . import grouped_io as G
            from .test_grouped_io import Boundaries as GroupedIOBoundaries
            policy=G.validate(I.read(plan['io_policy_reference']));stream=io.StringIO()
            suite=unittest.defaultTestLoader.loadTestsFromTestCase(GroupedIOBoundaries)
            result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
            io_tests=I.save(out/'grouped_io_source_tests.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),
              transcript=stream.getvalue(),policy_reference=plan['io_policy_reference'],before_population_DATA=True))
            I.need(result.testsRun==3 and result.wasSuccessful() and not result.skipped,'GROUPED_IO_BYTE_PREFIX_AND_SQLITE_SOURCE3_REQUIRED')
        if plan['mode']=='source':result=dict(status='SOURCE6_AND_FRESH16_SPAWN_ONLY_NO_POPULATION_DATA')
        else:
            origin,common,members,roles,formal,mapping=transport.inputs(plan)
            result=projection.produce(plan,out,guard,common,members,roles,formal,objects)
            result.update(origin_input_manifest_reference=plan['origin_input_manifest_reference'],origin_transport_review_reference=plan['origin_transport_review_reference'],
              original_Main_common_manifest_reference=origin['origin_common_manifest_reference'],Alpha_common_manifest_copy=mapping[origin['origin_common_manifest_reference']['path']],
              original_physical_geometry_references=origin['origin_physical_geometry_references'],original_uff_identity_references=origin['origin_uff_identity_references'],
              geometry_bodies_transported_or_revalidated=False,original_unknown3436_excluded=True)
        I.save(out/'receipt.json',dict(schema='ALPHA_COMMON_GRAPH_CONTINUATION_PRODUCER_V1',mode=plan['mode'],result=result,plan=I.pin(a.plan),startup_proof=I.pin(a.startup_proof),
          source_tests=tests,grouped_io_source_tests=io_tests,io_policy_reference=plan.get('io_policy_reference'),
          profile_admission=authority,runtime=guard.receipt(),uid=os.getuid(),job_id=os.environ['SLURM_JOB_ID'],
          Main_origin_parent_job_id='4525659',Main_origin_parent_state='STOPPED',Main_origin_parent_C0_claimed=False,
          actual_Alpha_parent_C0_pending_Root_readback=True,PM7_D7_numeric_computation_performed=False,orders_frozen=False,D7_released=False,new_UFF_QM_calls=0,
          common_scientific_membership_rules_changed=False,full_population_graph_computed=plan['mode']=='full',
          full_reference_candidate=plan['mode']=='full' and result['HOLD_MIDs']==0))
    except BaseException as exc:
        if out.is_dir():I.save(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),original_inputs_modified=False,Main_origin_parent_C0_claimed=False,no_fallback_reference_released=True,partials_retained=True))
        raise
    finally:guard.close()


if __name__=='__main__':main()
