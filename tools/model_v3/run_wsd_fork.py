"""Run a preregistered WSD child; never submits jobs or declares Root closure."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import time

REPO = Path(__file__).absolute().parents[2]
sys.path.insert(0,str(REPO/'current'))


def run(args):
    if 'torch' in sys.modules: raise RuntimeError('Fresh interpreter required before deterministic Torch import')
    raw = args.request.read_bytes()
    if len(raw) > 2 << 20 or hashlib.sha256(raw).hexdigest() != args.request_sha256: raise ValueError('Bounded request raw SHA differs')
    preview = json.loads(raw); raw = Path(preview['configuration']['path']).read_bytes()
    if len(raw) > 2 << 20 or hashlib.sha256(raw).hexdigest() != preview['configuration']['sha256']: raise ValueError('Configuration raw SHA differs')
    configuration = json.loads(raw)
    if configuration['proxy_contract']['execution']['deterministic']: os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    from run_proxy_experiment import (PersistentOfflineTracker,sdk_environment,execution_context,load_request,
        install_training_observer,finalize_training_observer)
    from phychem_mfm.phase1 import v3_proxy_run as proxy
    from phychem_mfm.phase1.v3_wsd_fork import validate_fork,restore_and_fork,ForkFamily,verify_parent_sources,verify_fork_chain
    from phychem_mfm.phase1.v3_sample_budget_events import binding,physical,write_once,encoded
    from phychem_mfm.phase1.v3_sample_budget_experiment import SegmentPause
    from runtime_monitor import owned_output_bytes,owned_process_observation,gpu_observation
    require = proxy.require
    ref,request = load_request(args.request,args.request_sha256)
    config,plan,registrations,parent,parent_config,state,source_proof = validate_fork(request,
        input_kind=args.input,engineering_only=args.engineering_only)
    require(os.environ.get('SLURM_JOB_ID') and int(os.environ.get('SLURM_CPUS_PER_TASK','0')) >= 16,'Owned at least16CPU Slurm allocation required')
    require(not args.output.exists() and not physical(args.output).is_relative_to(REPO),'Fresh outside-Git WSD job root required')
    require(str(physical(args.family_root)) == request['fork']['family_root'],'Family root is immutable request provenance; no fresh budget root')
    roots = [physical(p) for p in (args.output,args.lineage_root,args.family_root)]
    require(all(not p.is_relative_to(REPO) for p in roots)
        and all(a != b and not a.is_relative_to(b) and not b.is_relative_to(a) for i,a in enumerate(roots) for b in roots[i+1:]),
        'Disjoint outside-Git job, child ledger and shared family roots required')
    n = config['wsd_fork']['fork_samples']
    require(n < args.until_samples <= plan.sample_budget,'Explicit advancing decay segment endpoint required')
    runtime = execution_context(config)
    require(all(v['verified_local_commit_epoch'] < time.time() for v in registrations.values()),'Actual training must follow preregistration')
    resources = config['proxy_contract']['resources']; policy = config['wsd_fork']
    outer = int(os.environ.get('MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES','0'))
    require(128 << 20 <= outer <= resources['joint_output_bytes']-resources['ledger_bytes']-policy['family_ledger_bytes']-(96 << 20),
        'Original supervisor must additionally reserve child and family ledgers within original2GiB')
    from phychem_mfm.phase1.v3_long_run_storage import DurableLedger,attach_experiment,stable_request_identity
    durable = DurableLedger(request,config) if 'long_run_policy' in config else None
    control_baseline = owned_output_bytes(durable.root) if durable is not None else 0
    canonical_baseline = owned_output_bytes(args.lineage_root) if durable is not None and args.lineage_root.exists() else 0
    family_baseline = owned_output_bytes(args.family_root) if durable is not None and args.family_root.exists() else 0
    # Both requests receive actual final-authority verification. Only the parent
    # provider is retained and restored; no new provider replaces its state.
    inputs = proxy.bind_inputs(parent,parent_config)
    duplicate = None; run_object = None; lock = None; experiment = None; failure = None; cleanup = []; outcome = None
    capacity_observation = None; capacity_artifacts = None
    started = time.monotonic(); args.output.mkdir(mode=0o700,parents=True)
    sdk_environment(args.output)
    try:
        family = ForkFamily(args.family_root,fork=request['fork'],policy=policy,child_identity=proxy.identity(config),maximum_checkpoints=plan.max_total_checkpoints)
        if durable is not None:
            durable.register_root(args.family_root,kind='management')
            durable.append('wsd_children',str(physical(args.lineage_root)),{'family_root':str(physical(args.family_root)),
                'stable_request_identity_sha256':stable_request_identity(request)})
            durable.allocate_segment(request_ref=ref,segment_id=args.segment_id,job_root=args.output,lineage_root=args.lineage_root)
        family.register_child(lineage=args.lineage,ledger=args.lineage_root,request_ref=ref)
        family.reserve_launch(args.lineage_root,request_ref=ref,lineage=args.lineage,job_root=args.output,segment_id=args.segment_id,
            maximum_attempts=plan.max_total_checkpoints,maximum_bytes=resources['ledger_bytes'])
        for known_root in family.roots():
            if durable is not None and str(known_root) not in {row['path'] for row in durable.root_records()}:
                durable.register_root(known_root,kind='management',must_exist=True)
        initial_family_bytes = durable.census() if durable is not None else sum(owned_output_bytes(root) for root in family.roots())
        family_cap = durable.limits['durable_bytes'] if durable is not None else resources['joint_output_bytes']
        require(initial_family_bytes+resources['tracking_bytes']+(96 << 20) < family_cap
            and len(family.checkpoint_directories()) < plan.max_total_checkpoints,
            'Shared parent/fork family already exhausts declared storage/checkpoint/attempt allowance')
        duplicate = proxy.bind_inputs(request,config)
        require(type(duplicate.provider) is type(inputs.provider) and duplicate.structural_binding == inputs.structural_binding,
            'Child authority must preserve original provider and structural roles')
        child_receipt = deepcopy(duplicate.authority_receipt)
        duplicate.provider.close(); duplicate = None
        if config['proxy_contract']['execution']['device'] == 'cuda':
            import fcntl
            uuid = config['proxy_contract']['execution']['gpu_uuid']
            folder = Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks')
            lock = (folder/(uuid+'.lock')).open('a'); fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            require(not gpu_observation(uuid,own_pids=(os.getpid(),))['foreign_processes'],'Declared physical GPU is occupied')
        import wandb
        run_object = wandb.init(project='mfm_model_v3_development',mode='offline',dir=str(args.output),
            name=f'wsd_{args.lineage}_{args.segment_id}',config={'request':ref,'configuration':config,'runtime':runtime,
                'parent_source_proof':source_proof,'engineering_only':config['engineering_only'],'scientific_acceptance':False})
        tracker = PersistentOfflineTracker(run_object,args.output/'history.jsonl')
        experiment = restore_and_fork(request,config,plan,inputs,tracker,output_root=args.output,lineage_root=args.lineage_root,
            lineage=args.lineage,family=family,parent=parent,parent_config=parent_config,parent_state=state,
            child_authority_receipt=child_receipt)
        capacity_observation = install_training_observer(experiment, config, args.output, request_reference=ref)
        if durable is not None: attach_experiment(experiment,durable)
        capacity = proxy.checkpoint_capacity(experiment.trainer); reserve = resources['tracking_bytes']+(96 << 20)
        def census(): return durable.census() if durable is not None else sum(owned_output_bytes(root) for root in experiment.lineage_output_roots())
        def remaining():
            historical = durable.remaining(job_root=args.output) if durable is not None else resources['joint_output_bytes']-census()
            return min(outer-owned_output_bytes(args.output),resources['joint_output_bytes']-segment_bytes(),historical)-reserve
        def segment_bytes():
            size = owned_output_bytes(args.output)
            if durable is not None:
                size += max(0,owned_output_bytes(durable.root)-control_baseline)
                size += max(0,owned_output_bytes(args.lineage_root)-canonical_baseline)
                size += max(0,owned_output_bytes(args.family_root)-family_baseline)
            return size
        experiment.joint_remaining_bytes = remaining
        def guard(action,context):
            elapsed = time.monotonic()-started; size = census(); process = owned_process_observation(os.getpid())
            require(elapsed < plan.max_segment_seconds and process['rss_sum_bytes'] <= resources['rss_bytes'], 'Inclusive wall/RSS budget exhausted')
            require(size < family_cap and owned_output_bytes(args.output) < outer
                and segment_bytes() < resources['joint_output_bytes'],'Segment or finite durable parent/fork cap exhausted')
            if action == 'STEP' and elapsed >= plan.max_segment_seconds-plan.checkpoint_reserve_seconds:
                raise SegmentPause('inclusive WSD checkpoint/SDK finish reserve reached')
            if action == 'CHECKPOINT': capacity.update(proxy.checkpoint_capacity(experiment.trainer))
            row = {'action':action,'inclusive_elapsed_seconds':elapsed,'joint_family_bytes':size,'RSS_bytes':process['rss_sum_bytes'],
                'samples_consumed':context['samples_consumed'],'capacity':capacity}
            if durable is not None: row['long_run_quota'] = durable.refresh()
            if config['proxy_contract']['execution']['device'] == 'cuda':
                import torch
                gpu = gpu_observation(config['proxy_contract']['execution']['gpu_uuid'],own_pids=[p['pid'] for p in process['processes']])
                own = sum(p['used_memory_bytes'] or 0 for p in gpu['compute_processes'] if p['own'])
                require(not gpu['foreign_processes'] and max(own,torch.cuda.max_memory_allocated(),torch.cuda.max_memory_reserved()) <= .85*gpu['total_bytes'],
                    'Physical GPU ownership/85percent capacity drift')
                row['gpu'] = gpu
            if action in ('STEP','CHECKPOINT') and remaining() < capacity['planning_reserve_bytes']:
                if action == 'STEP': raise SegmentPause('joint family checkpoint reserve reached')
                raise MemoryError('Insufficient family reserve; retain every previous checkpoint')
            with (args.output/'resources.jsonl').open('ab') as stream: stream.write(encoded(row))
        experiment.trainer.proxy_validation_guard = lambda: experiment._preflight('VALIDATION_BATCH',allow_pause=False)
        write_once(args.output/'RUN_BINDING.json',{'schema':'model_v3_wsd_launch_v1','request':ref,'runtime':runtime,
            'source_proof':source_proof,'registrations':registrations,'job_id':os.environ['SLURM_JOB_ID'],
            'parent_complete':request['fork']['parent_complete'],'family_root':str(physical(args.family_root)),
            'outer_child_budget_bytes':outer,'scientific_acceptance':False,'actual_Root_terminal_required':True,
            **({'training_execution': {'contract': experiment.trainer.contract['training_execution'],
                'provider_authority_receipt_sha256': experiment.trainer.bindings['proxy_authority_receipt_sha256'],
                'observation_configuration_pending_actual_forward': True}} if capacity_observation is not None else {})})
        child_parent = binding(args.resume_complete) if args.resume_complete else None
        outcome = experiment.run_segment(segment_id=args.segment_id,until_samples=args.until_samples,request_ref=ref,
            parent=child_parent,preflight=guard)
        if outcome['last_checkpoint'] is not None:
            write_once(args.output/'FORK_CHAIN.json',verify_fork_chain(experiment,outcome['last_checkpoint']))
        proxy.validate_sources(request); verify_parent_sources(parent,config)
    except BaseException as exc:
        failure = {'type':type(exc).__name__,'message':str(exc)[:600]}; raise
    finally:
        callbacks = [('provider',inputs.provider.close),('duplicate_provider',lambda: duplicate.provider.close() if duplicate else None),
            ('wandb_finish',lambda: run_object.finish(exit_code=0 if failure is None else 1) if run_object else None),
            ('gpu_lock',lambda: lock.close() if lock else None)]
        for stage,callback in callbacks:
            try: callback()
            except BaseException as exc: cleanup.append({'stage':stage,'type':type(exc).__name__,'message':str(exc)[:300]})
        if capacity_observation is not None:
            try:
                capacity_artifacts = finalize_training_observer(capacity_observation, args.output)
            except BaseException as exc:
                cleanup.append({'stage':'training_capacity_finalize','type':type(exc).__name__,'message':str(exc)[:300]})
        elapsed = time.monotonic()-started; timed_out = elapsed >= plan.max_segment_seconds
        if timed_out and failure is None: failure = {'type':'TimeoutError','message':'Inclusive WSD finish exceeded registered wall budget'}
        receipt_ref = write_once(args.output/'CHILD_RECEIPT.json',{'schema':'model_v3_wsd_child_receipt_v1',
            'status':'CHILD_FINISHED_PENDING_ROOT_CLOSURE' if failure is None and not cleanup else 'CHILD_FAILED',
            'outcome':outcome,'first_failure':failure,'cleanup_errors':cleanup,'native_sdk_run_id':run_object.id if run_object else None,
            'inclusive_elapsed_seconds':elapsed,'scientific_acceptance':False,'actual_Root_terminal_and_SDK_verification_required':True,
            **({'job_id':os.environ['SLURM_JOB_ID'], 'training_execution_capacity_artifacts':capacity_artifacts,
                'committed_cursors': {'optimizer_updates':experiment.trainer.clock.optimizer_updates,
                    'samples_consumed':experiment.trainer.clock.samples_consumed,'log_cursor':experiment.trainer.log_cursor,
                    'pending_log':experiment.trainer.pending_log is not None}}
                if capacity_observation is not None else {})})
        if durable is not None and any(row['kind'] == 'launch_attempts' and row['identity'] == str(physical(args.output)) for row in durable.records()):
            durable.terminal(job_root=args.output,status='successful_segments' if failure is None and not cleanup else 'failed_attempts',result_ref=receipt_ref)
        if timed_out: raise TimeoutError('Inclusive WSD job wall exhausted')
        if cleanup and failure is None: raise RuntimeError('WSD cleanup failed; first failure/cleanup receipts retained')


def parser():
    result = argparse.ArgumentParser(description=__doc__); commands = result.add_subparsers(dest='command',required=True)
    prepare = commands.add_parser('prepare-engineering')
    for name in ('parent-request','parent-complete','parent-ledger','parent-segment-registration','family-root','output'):
        prepare.add_argument('--'+name,type=Path,required=True)
    prepare.add_argument('--base-code-sha',required=True); prepare.add_argument('--decay-samples',type=int,required=True)
    cmd = commands.add_parser('run')
    for name in ('request','output','lineage-root','family-root'): cmd.add_argument('--'+name,type=Path,required=True)
    cmd.add_argument('--request-sha256',required=True); cmd.add_argument('--lineage',required=True); cmd.add_argument('--segment-id',required=True)
    cmd.add_argument('--until-samples',type=int,required=True); cmd.add_argument('--resume-complete',type=Path)
    cmd.add_argument('--input',choices=('authoritative_proxy','synthetic'),default='authoritative_proxy')
    cmd.add_argument('--engineering-only',action='store_true')
    return result


def main():
    args = parser().parse_args()
    if args.command == 'run': return run(args)
    from phychem_mfm.phase1.v3_wsd_fork import engineering_fork_request
    from phychem_mfm.phase1.v3_sample_budget_events import binding
    ref = engineering_fork_request(args.output,parent_request_ref=binding(args.parent_request),parent_complete_ref=binding(args.parent_complete),
        parent_ledger=args.parent_ledger,parent_segment_registration=binding(args.parent_segment_registration),
        family_root=args.family_root,code_sha=args.base_code_sha,decay_samples=args.decay_samples)
    print(json.dumps(ref))


if __name__ == '__main__': main()
