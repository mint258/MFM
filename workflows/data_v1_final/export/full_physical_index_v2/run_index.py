"""Admitted D6 identity-only builder with real separate Main/Lustre budgets."""
import argparse,json,pathlib,sys,traceback
import build_index as B
import resource_runtime as R
from workflows.data_v1_final.execution.cpu_account100_queue_v1.runtime import require_startup
from workflows.data_v1_final.execution.cpu_account100_queue_v1 import shared as Q


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True,type=pathlib.Path);parser.add_argument('--startup-proof',required=True,type=pathlib.Path)
    args=parser.parse_args();plan=R.load(args.plan);cfg=plan['resource_binding']
    argv=[Q.PY,'-B',str(pathlib.Path(__file__).absolute()),'--plan',str(args.plan),'--startup-proof',str(args.startup_proof)]
    proof=require_startup(args.startup_proof,expected_kind='analysis',expected_scope_key=R.KEY,
        expected_scope_parameters=R.parameters(plan),expected_execution_argv=argv,expected_source=pathlib.Path(__file__).absolute(),
        required_references=(Q.pin(args.plan),))
    request=proof['request']
    R.need(request['node']=='compute-0-18' and request['cpus']==16 and request['wall_seconds']==cfg['wall_seconds']
        and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and request['estimated_peak_output_bytes']==R.MAIN_CAP,
        'ACTUAL_GENERIC16_MAIN64MIB_CONTROL_NOT_LUSTRE16GIB_AS_MAIN')
    # Root may bind the existing v5 instance or a distinct newly launched finite
    # day instance. Actual review/identity/source/lease are verified unchanged.
    for ref in (cfg['quota_provider_review_reference'],cfg['quota_provider_identity_reference'],cfg['quota_floor_policy_reference']):
        allowed=(R.ROOT/'control',R.ROOT/'repository/configs/data_v1') if ref==cfg['quota_floor_policy_reference'] else (R.ROOT/'control',)
        R.need(any(root in pathlib.Path(ref['path']).parents for root in allowed) and ref in request['source_references'],
            'EXACT_ROOT_BOUND_REAL_PROVIDER_AND_POLICY_SOURCE_REFERENCE')
    floor=R.load(R.ROOT/'control/current_account_quota_floor_policy.json')
    R.need(floor['account_quota_floor_bytes']==R.FLOOR and floor['policy_reference']==cfg['quota_floor_policy_reference'],'ACTUAL_USER100GB_POLICY')
    declared={r['path']:r for r in request['source_references']}
    paths=[pathlib.Path(__file__).absolute(),pathlib.Path(B.__file__),pathlib.Path(R.__file__),pathlib.Path(R.DAY.__file__),
        pathlib.Path(R.GUARD.__file__),pathlib.Path(R.OLD_LFS.__file__)]
    import inspect
    paths.extend([pathlib.Path(inspect.getsourcefile(R.wall_clock)),pathlib.Path(inspect.getsourcefile(B.opened)),pathlib.Path(inspect.getsourcefile(B.lookup_batch))])
    for path in paths:R.need(declared.get(str(path))==Q.pin(path),'EXPLICIT_CURRENT_SOURCE_PIN:'+str(path))
    R.need({r['path']:r for r in request['data_references']}=={r['path']:r for r in plan['data_references']},'EXACT_ORIGINAL_FULL_INDEX_DATA_LOCATORS')
    monitor=None;result=None;error=None;status='UNSTARTED';code=1
    try:
        monitor=R.Monitor(plan,proof,Q.pin(args.plan),Q.pin(args.startup_proof));monitor.start()
        B.set_resource_check(monitor.check)
        result=B.build(plan,plan['output_directory'],worker_initializer=R.worker_initialize,worker_initargs=(monitor.parent,))
        status='CLOSED_ORIGINAL_IDENTITY_INDEX_PENDING_ACTUAL_PARENT';code=0
    except R.ResourceStop as exc:
        status='RESOURCE_PARTIAL_CLOSED_WRITERS_NOT_A_COMPLETE_INDEX';error=dict(error=repr(exc),traceback=traceback.format_exc());code=3
    except BaseException as exc:
        status='INDEX_BUILD_FAILED_CLOSED_WRITERS_PARTIALS_PRESERVED';error=dict(error=repr(exc),traceback=traceback.format_exc());code=1
    finally:
        B.close_writers()
        if monitor is not None:monitor.finish()
    control=R.literal(cfg['control_directory'])
    R.save(control/'resource_result.json',dict(schema='D6_FULL_INDEX_RESOURCE_WRAPPER_RESULT_V1',status=status,
        job_id=str(proof['job_id']),plan_reference=Q.pin(args.plan),startup_proof_reference=Q.pin(args.startup_proof),
        index_manifest_reference=result,error=error,stop=None if monitor is None else monitor.stop,
        all_builder_writer_contexts_exited=True,partials_preserved=True,signals_sent=False,
        Main_control_forecast_bytes=R.MAIN_CAP,Lustre_forecast_bytes=R.LFS_CAP,Lustre_forecast_not_added_to_Main=True,
        final_Common_or_D6_training_release=False,new_QM_UFF_calls=0,actual_parent_C0_not_claimed=True))
    return code

if __name__=='__main__':raise SystemExit(main())