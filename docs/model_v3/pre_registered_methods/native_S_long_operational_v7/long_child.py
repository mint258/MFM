"""One NativeCore segment; original step/validation/save math is unchanged."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import os
from pathlib import Path
import time
import json
import sys
from long_common import *
sys.dont_write_bytecode=True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',type=Path,required=True);parser.add_argument('--submission',type=Path,required=True)
    parser.add_argument('--submission-sha256',required=True);parser.add_argument('--runtime-contract',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--observations',type=Path,required=True)
    args=parser.parse_args();manifest,_=verify()
    submission=binding(args.submission);require(submission['sha256']==args.submission_sha256,'Root long submission changed')
    launch=read_ref(submission);job=os.environ['SLURM_JOB_ID']
    require(launch['actual_sbatch_job_id']==job and launch['phase']==str(args.phase)
        and launch['package_manifest']==manifest,'Actual allocated job/source/phase mismatch')
    contract,adapter=import_runtime(args.runtime_contract)
    os.environ['MODEL_V3_NATIVE_S_RUNTIME_CONTRACT']=str(args.runtime_contract)
    from a_execution_runtime import prepare_deterministic_controls,apply_deterministic_controls,guard_resources
    preimport=prepare_deterministic_controls(True)
    import torch
    torch.set_num_threads(8);torch.set_num_interop_threads(1)
    controls=apply_deterministic_controls(preimport)
    require(torch.cuda.is_available() and torch.cuda.device_count()==1
        and os.environ.get('CUDA_VISIBLE_DEVICES')==GPU and '5090' in torch.cuda.get_device_name(0)
        and str(torch.__version__).startswith('2.10.') and torch.version.cuda=='12.8',
        'Actual original physical5090/Torch2.10cu128 required')
    from runtime_monitor import gpu_observation,owned_output_bytes
    from private_runtime_storage import load_storage_bindings
    from run_native_s_precision import collect_native_sources,production_protocol
    from run_precision_experiment import PersistentOfflineTracker
    from phychem_mfm.phase1.v3_native_s_precision import NativeSPrecisionPlan,NativeSPrecisionExperiment
    from phychem_mfm.phase1.v3_native_s_precision_data import ExistingNativeSInputs
    import runtime_origin,long_frames,fcntl
    production_protocol();runtime_origin.audit_loaded(contract,classes=True)
    uuid_lock=LOCK.open('a');fcntl.flock(uuid_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    gpu=gpu_observation(GPU,own_pids=(os.getpid(),))
    require(not gpu['foreign_processes'] and gpu['driver_version']=='590.44.01','GPU foreign process/driver differs')
    runtime=dict(torch=str(torch.__version__),cuda=torch.version.cuda,logical_python=sys.executable,device='cuda',
        deterministic_execution_sha256=controls['execution_sha256'],gpu_uuid=GPU,
        gpu_name=torch.cuda.get_device_name(0),driver=gpu['driver_version'])
    plan=NativeSPrecisionPlan();sources=collect_native_sources()
    sources['external_Root_total_storage_hook']=binding(V2/'native_s_storage.py')['sha256']
    require(sources==launch['native_member']['sources'] and runtime==launch['native_member']['runtime'],
        'Actual member runtime/source must match both real profiles and Root admission')
    cap=int(os.environ.get('MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES','0'))
    require(cap==CHILD,'Keep inherited outer-minus96MiB child ceiling')
    private=load_storage_bindings()
    callback=dict(scope=adapter.SCOPE,plan=asdict(plan),seed=launch['seed'],precision=launch['precision'],
        code_sha=CODE,prereg_sha=PUBLIC,output_root=str(args.output),sources=sources,runtime=runtime,
        max_segment_bytes=cap,private_storage=private,wall_seconds=CHILD_SECONDS,
        resume_checkpoint=launch['resume_checkpoint'],resume_output_root=launch['resume_output_root'],
        fixed_checkpoint_updates=list(plan.checkpoint_updates))
    require(not args.output.exists(),'Fresh native science segment output required')
    os.environ.update(WANDB_MODE='offline',WANDB_CACHE_DIR=str(args.output/'cache'),
        WANDB_DATA_DIR=str(args.output/'wandb_data'),WANDB_CONFIG_DIR=str(args.output/'wandb_config'))
    management=args.output.parent/'management';baseline=read(management/'ledger_baseline.json')
    frames=long_frames.build(callback,contract,phase=args.phase,submission=submission,
        observations=args.observations,baseline=baseline)
    policy=adapter.bind_native_s_precision_storage(callback)
    require(policy.configuration['purpose']==adapter.SCIENCE,'Profile-only principal cannot run a science member')
    args.output.mkdir(mode=0o700)
    import wandb
    inputs=engine=run=outcome=None;failure=None;errors=[];started=time.monotonic()
    def retry_budget(additional):
        require(time.monotonic()-started<CHILD_SECONDS-30,'Native segment reached finalization reserve')
        guard_resources(args.output,GPU)
        current=long_frames.whole_census(args.phase,job,frames['parent']['stdio'],baseline,__import__('runtime_monitor'))
        require(owned_output_bytes(args.output)+additional<cap-(1<<20),
            'Rejected-feed observation would exhaust inherited child reserve')
        require(current['whole_job_bytes']+additional<=OUTER,'Rejected-feed observation exceeds original whole-job cap')
    import quota_retry
    retry_binding=quota_retry.install(policy,adapter,args.output,retry_budget)
    def guard(action,value):
        require(time.monotonic()-started<CHILD_SECONDS-30,'Native segment reached finalization reserve')
        resources=guard_resources(args.output,GPU)
        long_frames.whole_census(args.phase,job,frames['parent']['stdio'],baseline,__import__('runtime_monitor'))
        policy.guard(action,value)
        with (args.output/'resources.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(action=action,updates=value.clock.optimizer_updates,
                samples=value.clock.samples_consumed,**resources),allow_nan=False)+'\n')
    try:
        inputs=ExistingNativeSInputs(seed=launch['seed'])
        runtime_origin.audit_loaded(contract,classes=True)
        request={**callback,'deterministic_controls':controls,'Root_storage_binding':policy.binding,
            'operational_quota_revalidation':retry_binding}
        write(args.output/'SDK_expected_configuration.json',request)
        run=wandb.init(project='mfm_model_v3_development',mode='offline',dir=str(args.output),
            name=f'nativeS_B_{launch["precision"]}_seed{launch["seed"]}_{job}',config=request)
        engine=NativeSPrecisionExperiment(inputs,plan,seed=launch['seed'],precision=launch['precision'],
            tracker=PersistentOfflineTracker(run,args.output/'history.jsonl'),source_bindings=sources,
            code_sha=CODE,prereg_sha=PUBLIC,device='cuda',runtime_binding=runtime,storage_policy_binding=policy.binding)
        if launch['resume_checkpoint'] is not None:
            engine.load(Path(launch['resume_checkpoint']),output_root=Path(launch['resume_output_root']))
        require(engine.clock.optimizer_updates==launch['start_update'],'Safe loaded committed update differs')
        write(args.output/'configuration.json',dict(contract=engine.contract,source_inputs=inputs.bindings,
            tracker=engine.tracker_identity,resume_parent=engine.resume_parent,private_storage=private,
            Root_storage_binding=policy.binding,operational_runner_source=binding(__file__),
            operational_quota_revalidation=retry_binding,
            scientific_core_source=binding(RUNTIME/'current/phychem_mfm/phase1/v3_native_s_precision.py')))
        outcome=engine.run(args.output,until_update=launch['target_update'],guard=guard,
            pause_requested=lambda:time.monotonic()-started>=CHILD_SECONDS-300)
        require(launch['start_update']<outcome['optimizer_updates']<=launch['target_update'],
            'Segment must make genuine committed progress without exceeding target')
        require(collect_native_sources()=={key:value for key,value in sources.items()
            if key!='external_Root_total_storage_hook'},'Native source bytes changed')
        import profile_lifecycle
        summary=profile_lifecycle.summary_from_mirror(args.output/'history.jsonl',maximum_rows=1104)
        summary['native_B_segment']=dict(seed=launch['seed'],precision=launch['precision'],
            optimizer_updates=outcome['optimizer_updates'],target_update=launch['target_update'],
            full_20000=outcome['optimizer_updates']==20000,scientific_acceptance=False)
        run.summary.update(summary);write(args.output/'SDK_expected_summary.json',summary)
    except BaseException as error:
        failure=dict(type=type(error).__name__,message=str(error));raise
    finally:
        for role,close in (('inputs',None if inputs is None else inputs.close),('storage',policy.close),
            ('SDK',None if run is None else lambda:run.finish(exit_code=1 if failure or errors else 0))):
            if close:
                try:close()
                except BaseException as error:errors.append(dict(role=role,type=type(error).__name__,message=str(error)))
        try:
            final=long_frames.whole_census(args.phase,job,frames['parent']['stdio'],baseline,__import__('runtime_monitor'))
            require(owned_output_bytes(args.output)<cap-(1<<20),'Final child output exhausted inherited reserve')
        except BaseException as error:
            final=None;errors.append(dict(role='census',type=type(error).__name__,message=str(error)))
        write(args.output/'run_status.json',dict(schema='native_S_long_child_status_v1',
            status='CHILD_COMPLETE_PENDING_ROOT_SDK_AND_NUMERIC_GATES' if failure is None and not errors else 'FAILED',
            failure=failure,cleanup_errors=errors,optimizer_updates=None if outcome is None else outcome['optimizer_updates'],
            start_update=launch['start_update'],target_update=launch['target_update'],tracker_id=None if run is None else run.id,
            elapsed_seconds=time.monotonic()-started,current_whole_census=final,
            scientific_acceptance=False,D5_authority=False,offline_unsynced=True))
        uuid_lock.close()
        if errors and failure is None:raise RuntimeError('Native science segment cleanup/census failed')
    return 0


if __name__=='__main__':raise SystemExit(main())
