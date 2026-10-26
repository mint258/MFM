"""Explicit real-native profile-only bootstrap; never submits or accepts B.

Root supplies a profile-only finite principal, actual quota feed, exact native
source/operational admission and external supervisor. No final-D profile is
needed for this short measured bootstrap. Only frozen native APIs are composed.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import importlib
import json
import os
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode=True
import native_s_storage as adapter
import precision_observer
import runtime_origin
import profile_lifecycle


def parser():
    value=argparse.ArgumentParser(description=__doc__)
    value.add_argument('--runtime-contract',type=Path,required=True)
    value.add_argument('--output',type=Path,required=True)
    value.add_argument('--precision',choices=('fp32','bf16'),required=True)
    value.add_argument('--updates',type=int,default=20)
    value.add_argument('--expected-gpu',choices=('3090','4090','5090'),required=True)
    value.add_argument('--code-sha',required=True); value.add_argument('--prereg-sha',required=True)
    value.add_argument('--wall-seconds',type=int,default=6900)
    return value


def run(args):
    require=adapter.require
    started=time.monotonic()
    args.output=args.output.absolute()
    require(1<=args.updates<=100 and args.wall_seconds==6900,'Explicit short profile endpoint/original bounded wall required')
    require(os.environ.get('SLURM_JOB_ID') and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=16,'Owned>=16CPU GPU allocation required')
    require(all(re.fullmatch('[0-9a-f]{40}',value) for value in (args.code_sha,args.prereg_sha)),'Exact actual/public source SHA required')
    contract=runtime_origin.read_contract(args.runtime_contract,allow_candidate_profile=True)
    require(contract['status']!='CANDIDATE_PROFILE_ONLY' or args.updates==20,'Candidate contract permits exactly20 profile updates')
    runtime_origin.configure_paths(contract)
    native=Path(contract['runtime_root']).absolute()
    require(args.code_sha==contract['combined_commit'] and args.prereg_sha==contract['public_commit'],
        'Profile must use actual combined/public exact-tree source commits')
    os.environ['MODEL_V3_NATIVE_S_RUNTIME_CONTRACT']=str(args.runtime_contract.absolute())
    require(not args.output.exists() and not args.output.absolute().is_relative_to(native),'Fresh outside-Git profile root required')
    from a_execution_runtime import prepare_deterministic_controls,apply_deterministic_controls
    preimport=prepare_deterministic_controls(True)
    import torch
    torch.set_num_threads(8); torch.set_num_interop_threads(1)
    deterministic=apply_deterministic_controls(preimport)
    require(torch.cuda.is_available() and torch.cuda.device_count()==1,'Actual CUDA required, no CPU fused/bf16 substitution')
    gpu_uuid=os.environ.get('CUDA_VISIBLE_DEVICES','')
    require(re.fullmatch('GPU-[a-fA-F0-9-]+',gpu_uuid),'One complete physical GPU UUID required')
    require(args.expected_gpu in torch.cuda.get_device_name(0),'Actual requested physical GPU type required')
    from runtime_monitor import gpu_observation,owned_output_bytes
    from private_runtime_storage import load_storage_bindings
    from run_native_s_precision import collect_native_sources
    from run_precision_experiment import PersistentOfflineTracker
    from phychem_mfm.phase1.v3_native_s_precision import NativeSPrecisionPlan,NativeSPrecisionExperiment
    from phychem_mfm.phase1.v3_native_s_precision_data import ExistingNativeSInputs
    from phychem_mfm.phase1.v3_precision_experiment import write_new_json
    from a_execution_runtime import guard_resources
    origin=runtime_origin.audit_loaded(contract,classes=True)
    import fcntl
    lock_path=Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks')/(gpu_uuid+'.lock')
    lock=lock_path.open('a'); fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    gpu=gpu_observation(gpu_uuid,own_pids=(os.getpid(),))
    require(not gpu['foreign_processes'],'Selected physical GPU has foreign compute process')
    runtime=dict(torch=str(torch.__version__),cuda=torch.version.cuda,logical_python=sys.executable,device='cuda',
        deterministic_execution_sha256=deterministic['execution_sha256'],gpu_uuid=gpu_uuid,
        gpu_name=torch.cuda.get_device_name(0),driver=gpu['driver_version'])
    plan=NativeSPrecisionPlan(); sources=collect_native_sources()
    sources['external_Root_total_storage_hook']=adapter.sha(adapter.__file__)
    outer_budget=2<<30
    child_budget=profile_lifecycle.inherited_budget(outer_budget)
    callback=dict(scope=adapter.SCOPE,plan=asdict(plan),seed=0,precision=args.precision,code_sha=args.code_sha,
        prereg_sha=args.prereg_sha,output_root=str(args.output.absolute()),sources=sources,runtime=runtime,
        max_segment_bytes=child_budget,wall_seconds=6900,private_storage=load_storage_bindings(),
        resume_checkpoint=None,resume_output_root=None,fixed_checkpoint_updates=list(plan.checkpoint_updates))
    os.environ.update(WANDB_CACHE_DIR=str(args.output/'cache'),WANDB_DATA_DIR=str(args.output/'wandb_data'),
        WANDB_CONFIG_DIR=str(args.output/'wandb_config'))
    storage=adapter.bind_native_s_precision_storage(callback)
    require(storage.configuration['purpose']==adapter.PROFILE and storage.configuration['profile_updates']==args.updates,
        'Separate Root profile-only admission required, not a B member reservation')
    require(storage.ledger.admission['admission']['profile_runner_source']['sha256']==adapter.sha(__file__),
        'Root must pin this exact external profile runner')
    require(storage.ledger.admission['admission']['profile_observer_source']['sha256']==adapter.sha(precision_observer.__file__),
        'Root must pin this exact dispatch observer')
    args.output.mkdir(mode=0o700,parents=True)
    os.environ.update(WANDB_MODE='offline',WANDB_CACHE_DIR=str(args.output/'cache'),WANDB_DATA_DIR=str(args.output/'wandb_data'))
    import wandb
    inputs=engine=run=outcome=None; failure=None; errors=[]
    times=dict(validation=[],save=[],cleanup=[]); shapes=[]; census_times=[]
    def synchronized(): torch.cuda.synchronize()
    class ProfileExperiment(NativeSPrecisionExperiment):
        direct_precision_observation=None
        def _forward(self,prepared):
            if profile_lifecycle.should_pause(started,args.wall_seconds,time.monotonic()):
                raise profile_lifecycle.CommittedProfilePause('300-second boundary reached before another TRAIN/VAL forward')
            lengths=prepared.views.batch.ptr.diff()
            shapes.append(dict(role=prepared.role,base_records=len(prepared.choices),graphs=len(lengths),
                maximum_atoms=int(lengths.max()),packed_atoms=int(lengths.sum()),
                padded_cost=int(len(lengths)*int(lengths.max())**2)))
            if self.direct_precision_observation is None:
                with precision_observer.observe(self.model,self.precision,torch,device_type='cuda',expected_layers=6) as receipt:
                    result=super()._forward(prepared)
                    require(result[2].total.dtype==torch.float32 and all(v.dtype==torch.float32 for v in result[2].fields.values()),
                        'Actual loss fields/total left fp32')
                require(receipt['status']=='OBSERVED_OPERATOR_INTERFACES' and set(receipt['layers'])==set(map(str,range(6)))
                    and all(row['attention_class']=='phychem_mfm.model.v3_performance.RuntimeDenseAttention' for row in receipt['layers'].values()),
                    'Actual512x6 attention/geometry/normalization dispatch observation incomplete')
                receipt['loss_fields_and_total_fp32']=True
                self.direct_precision_observation=receipt
                return result
            return super()._forward(prepared)
        def validate(self):
            synchronized(); tick=time.perf_counter()
            result=super().validate(); synchronized(); times['validation'].append(time.perf_counter()-tick)
            return result
        def save(self,path,*,output_root):
            synchronized(); tick=time.perf_counter()
            result=super().save(path,output_root=output_root); synchronized(); times['save'].append(time.perf_counter()-tick)
            return result
    def guard(action,value):
        require(time.monotonic()-started<args.wall_seconds-30,'Original profile wall/finalization reserve exceeded')
        if action!='checkpoint':
            if profile_lifecycle.should_pause(started,args.wall_seconds,time.monotonic()):
                raise profile_lifecycle.CommittedProfilePause('Profile paused before more model/validation work inside300-second reserve')
        row=guard_resources(args.output,gpu_uuid); storage.guard(action,value)
        with (args.output/'resources.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(action=action,updates=value.clock.optimizer_updates,**row),allow_nan=False)+'\n')
    try:
        inputs=ExistingNativeSInputs(seed=0)
        origin=runtime_origin.audit_loaded(contract,classes=True)
        sdk_config=dict(purpose=adapter.PROFILE,callback=callback,Root_storage_binding=storage.binding,
            profile_runner_source=dict(path=str(Path(__file__).absolute()),sha256=adapter.sha(__file__)))
        write_new_json(args.output/'SDK_expected_configuration.json',sdk_config)
        run=wandb.init(project='mfm_model_v3_development',mode='offline',dir=str(args.output),
            name=f'nativeS_storage_PROFILE_ONLY_{args.precision}_{os.environ["SLURM_JOB_ID"]}',
            config=sdk_config)
        engine=ProfileExperiment(inputs,plan,seed=0,precision=args.precision,tracker=PersistentOfflineTracker(run,args.output/'history.jsonl'),
            source_bindings=sources,code_sha=args.code_sha,prereg_sha=args.prereg_sha,device='cuda',runtime_binding=runtime,
            storage_policy_binding=storage.binding)
        write_new_json(args.output/'configuration.json',dict(contract=engine.contract,source_inputs=inputs.bindings,
            purpose=adapter.PROFILE,profile_updates=args.updates,deterministic_controls=deterministic))
        try:
            outcome=engine.run(args.output,until_update=args.updates,guard=guard,
                pause_requested=lambda:profile_lifecycle.should_pause(started,args.wall_seconds,time.monotonic()))
        except profile_lifecycle.CommittedProfilePause:
            # Covers a boundary crossed during guard/prefetch after the frozen
            # run loop's pause check. Do not consume or fabricate that batch.
            if engine.clock.optimizer_updates not in engine.saved_updates:
                guard('checkpoint',engine)
                engine.save(args.output/f'checkpoint_u{engine.clock.optimizer_updates}_log{engine.log_cursor}',output_root=args.output)
            raise
        require(outcome['optimizer_updates']==args.updates and set(outcome['validation'])=={'0'},'Complete short native profile + one full1024VAL required')
        # Current profile scale only. A separate CPU metadata-pressure result
        # must cover the full future root/index envelope before long admission.
        tick=time.perf_counter(); storage.ledger.refresh(); census_times.append(time.perf_counter()-tick)
        require(collect_native_sources()=={k:v for k,v in sources.items() if k!='external_Root_total_storage_hook'},'Native source bytes changed')
        sdk_summary=profile_lifecycle.summary_from_mirror(args.output/'history.jsonl')
        sdk_summary['profile_v2']=dict(purpose=adapter.PROFILE,completed_requested_short_target=True,
            optimizer_updates=outcome['optimizer_updates'],native_code_sha=args.code_sha,D5_authority=False)
        run.summary.update(sdk_summary)
        write_new_json(args.output/'SDK_expected_summary.json',sdk_summary)
    except BaseException as error:
        failure=dict(type=type(error).__name__,message=str(error)); raise
    finally:
        for name,close in (('native_inputs',None if inputs is None else inputs.close),('storage',storage.close),
            ('SDK',None if run is None else lambda:run.finish(exit_code=1 if failure or errors else 0))):
            if close:
                tick=time.perf_counter()
                try: close()
                except BaseException as error: errors.append(dict(component=name,type=type(error).__name__,message=str(error)))
                times['cleanup'].append(time.perf_counter()-tick)
        try:
            require(owned_output_bytes(args.output)<child_budget-(1<<20),'Profile output exceeds inherited child reserve')
            sdk=list((args.output/'wandb').glob('offline-run-*/run-*.wandb'))
            payloads=list(args.output.glob('checkpoint_u*/payload.pt'))
            errors=profile_lifecycle.completion_errors(failure=failure,cleanup_errors=errors,target_updates=args.updates,
                actual_updates=None if outcome is None else outcome['optimizer_updates'],sdk_count=len(sdk),payload_count=len(payloads))
            complete=not errors
            measurements=None
            if complete:
                wall=outcome['segment_throughput']['training_step_wall_seconds']
                measurements=dict(checkpoint_bytes=payloads[0].stat().st_size,
                    non_checkpoint_output_bytes_before_profile_result=owned_output_bytes(args.output)-sum(path.stat().st_size for path in payloads),
                    save_seconds=max(times['save']),validation_seconds=max(times['validation']),cleanup_seconds=sum(times['cleanup']),
                    base_records_per_second=outcome['segment_throughput']['base_records']/wall,
                    current_accounting_seconds=sum(census_times),current_managed_roots=len(storage.ledger.root_records()),
                    provider_future_state_bound_bytes=None,optimizer_future_state_bound_bytes=None)
            write_new_json(args.output/'profile_result.json',dict(schema='existing_native_S_storage_profile_result_v2',
                status='PROFILE_CHILD_COMPLETED_PENDING_OUTER_AND_NATIVE_SDK' if complete else 'FAILED',purpose=adapter.PROFILE,
                scope=adapter.SCOPE,precision=args.precision,native_code_sha=args.code_sha,tracker_id=None if run is None else run.id,
                native_sources=sources,runtime=runtime,prereg_sha=args.prereg_sha,
                runtime_contract_status=contract['status'],production_20k_allowed=False,
                origin_preflight=origin,inherited_child_output_budget_bytes=child_budget,admitted_outer_output_budget_bytes=outer_budget,
                measurements=measurements,shapes=shapes,full_TRAIN_disjointness=None if inputs is None else inputs.disjoint_receipt,
                source=adapter.SOURCE,observed_profile_updates=None if outcome is None else outcome['optimizer_updates'],
                checkpoint_ref=None if not payloads or payloads[0].stat().st_size>storage.ledger.limits['checkpoint_bytes'] else
                    dict(path=str(payloads[0]),bytes=payloads[0].stat().st_size,sha256=adapter.sha(payloads[0])),
                oversize_checkpoint_bytes=None if not payloads or payloads[0].stat().st_size<=storage.ledger.limits['checkpoint_bytes'] else payloads[0].stat().st_size,
                native_SDK_file_bytes=None if len(sdk)!=1 else sdk[0].stat().st_size,
                SDK_expectations=None if not complete else dict(
                    sdk=storage.storage.binding(sdk[0]),mirror=storage.storage.binding(args.output/'history.jsonl'),
                    configuration=storage.storage.binding(args.output/'SDK_expected_configuration.json'),
                    summary=storage.storage.binding(args.output/'SDK_expected_summary.json')),
                coverage_observation=None if not (args.output/'actual_root_coverage_v2.json').exists() else
                    storage.storage.binding(args.output/'actual_root_coverage_v2.json'),
                actual_parameter_count=None if engine is None else sum(p.numel() for p in engine.model.parameters()),
                direct_precision_observation=None if engine is None else engine.direct_precision_observation,
                scientific_acceptance=False,D5_authority=False,failure=failure,cleanup_errors=errors,
                native_SDK_verification='REQUIRED_INDEPENDENTLY',future_state_bounds='Root_must_prove_from_actual_safe_CP_and_frozen_shapes',
                candidate_shape_coverage='actual512x6_original8M_budget_observed_native_batches; not_all_future_batches_certified'))
            post_result_bytes=owned_output_bytes(args.output)
            require(post_result_bytes<=child_budget,'Post-profile-result child census exceeds inherited budget')
            print(json.dumps(dict(schema='native_S_profile_post_result_census_v2',child_root=str(args.output),
                sampled_bytes_after_profile_result=post_result_bytes,child_budget_bytes=child_budget,
                final_outer_census_authority='Root_supervisor_after_child_exit',status='COMPLETED' if complete else 'FAILED'),allow_nan=False),flush=True)
        finally: lock.close()
        profile_lifecycle.enforce_failed_exit(errors,original_failure=failure)


if __name__=='__main__': run(parser().parse_args())
