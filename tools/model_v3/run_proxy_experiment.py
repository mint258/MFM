"""Bounded source-bound proxy segments. Never submits jobs or declares Slurm C0."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

REPO = Path(__file__).absolute().parents[2]
sys.path.insert(0,str(REPO/'current'))


class PersistentOfflineTracker:
    """Native SDK commits and fsynced mirror; every segment has a new run."""
    def __init__(self, run, history):
        self.run, self.history = run, history
        self.id,self.path,self.settings,self.disabled = run.id,run.path,run.settings,False

    @property
    def step(self): return self.run.step

    def log(self, row, *, step, commit):
        self.run.log(row,step=step,commit=commit)
        with self.history.open('a',encoding='utf-8') as stream:
            stream.write(json.dumps({'step':step,'commit':commit,'row':row},allow_nan=False)+'\n')
            stream.flush(); os.fsync(stream.fileno())


def sdk_environment(root):
    """Set canonical persistent SDK locations before importing/initializing SDK."""
    os.environ.update(WANDB_MODE='offline',WANDB_DIR=str(root),WANDB_CACHE_DIR=str(root/'cache'),
        WANDB_DATA_DIR=str(root/'wandb_data'),WANDB_CONFIG_DIR=str(root/'wandb_config'))


def load_request(path, sha):
    from phychem_mfm.phase1.v3_sample_budget_events import binding,read_bound,require
    ref = binding(path)
    require(ref['sha256'] == sha,'Exact immutable request raw SHA required')
    return ref,read_bound(ref)


def execution_context(configuration):
    """Apply only the execution choices explicitly carried by this request."""
    import torch
    from phychem_mfm.phase1.v3_contract import require
    execution = configuration['proxy_contract']['execution']
    require(type(execution['threads']) is int and 1 <= execution['threads'] <= 16
        and type(execution['deterministic']) is bool,'Bounded explicit execution policy required')
    torch.set_num_threads(execution['threads']); torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(execution['deterministic'],warn_only=False)
    torch.backends.cudnn.deterministic = execution['deterministic']
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision('highest')
    if execution['device'] == 'cpu':
        require(configuration['engineering_only'] and not torch.cuda.is_available()
            and execution['gpu_uuid'] is None and execution['gpu_name'] is None,
            'CPU is an explicit hidden-CUDA engineering fixture only')
    else:
        require(execution['device'] == 'cuda' and torch.cuda.device_count() == 1
            and re.fullmatch(r'GPU-[a-fA-F0-9-]+',execution['gpu_uuid'] or '')
            and os.environ.get('CUDA_VISIBLE_DEVICES') == execution['gpu_uuid']
            and torch.cuda.get_device_name(0) == execution['gpu_name'],
            'Actual single physical GPU UUID/model differs from frozen execution')
    return {'python':sys.executable,'torch':str(torch.__version__),'cuda_runtime':torch.version.cuda,
        'execution':execution,'matmul_precision':torch.get_float32_matmul_precision(),
        'cublas_workspace_config':os.environ.get('CUBLAS_WORKSPACE_CONFIG'),
        'deterministic_algorithms':torch.are_deterministic_algorithms_enabled()}


def install_training_observer(experiment, configuration, output, *, request_reference):
    """Reuse owned runtime samplers; append bounded rows, never retain a trace."""
    handle = experiment.trainer.training_execution
    if handle is None:
        return None
    import torch
    from phychem_mfm.phase1.v3_sample_budget_events import encoded, write_once, require
    from runtime_monitor import owned_output_bytes, owned_process_observation, gpu_observation
    path = output/'training_capacity.jsonl'
    with path.open('xb'):
        pass
    used = 0
    def sink(row):
        nonlocal used
        raw = encoded(row)
        require(len(raw) <= 1 << 20 and used+len(raw) <= configuration['proxy_contract']['resources']['tracking_bytes'],
            'Training capacity trace exhausted its declared bounded tracking allowance')
        with path.open('ab') as stream:
            stream.write(raw)
            stream.flush(); os.fsync(stream.fileno())
        used += len(raw)
    handle.observer.set_sink(sink)
    execution = configuration['proxy_contract']['execution']
    def resources():
        process = owned_process_observation(os.getpid())
        gpu = None
        if execution['device'] == 'cuda':
            gpu = gpu_observation(execution['gpu_uuid'], own_pids=[p['pid'] for p in process['processes']])
            require(all(type(p['used_memory_bytes']) is int and p['used_memory_bytes'] >= 0
                for p in gpu['compute_processes']), 'Unknown GPU process memory is not a zero observation')
        else:
            require(configuration['engineering_only'] and not torch.cuda.is_available(),
                'A CPU observation cannot certify scientific CUDA capacity')
        return {'gpu_observation': gpu, 'peak_allocated_bytes': torch.cuda.max_memory_allocated() if gpu is not None else 0,
            'peak_reserved_bytes': torch.cuda.max_memory_reserved() if gpu is not None else 0,
            'process_rss_sum_bytes': process['rss_sum_bytes'], 'output_bytes': owned_output_bytes(output),
            'foreign_gpu_risk_observed': bool(gpu['foreign_processes']) if gpu is not None else False,
            'captured_unix': time.time(), 'resource_scope': 'actual_CUDA_training' if gpu is not None else 'engineering_CPU_only',
            'peak_scope': 'whole fresh segment allocator high-water; no per-step reset; includes probes and validation'}
    experiment.trainer.training_execution_resources = resources
    # The observer binds its environment on actual forward, never during setup.
    return {'observer': handle.observer, 'steps_path': path, 'request_reference': request_reference}


def finalize_training_observer(observation, output):
    """Save actual in-process observations; an outer C0 is still required."""
    if observation is None:
        return None
    from phychem_mfm.phase1.v3_sample_budget_events import binding, write_once
    configuration = write_once(output/'training_capacity_configuration.json', observation['observer'].configuration(request_reference=observation['request_reference']))
    summary = write_once(output/'training_capacity_summary.json', observation['observer'].summary())
    return {'configuration': configuration, 'summary': summary, 'steps': binding(observation['steps_path'])}


def run_segment(args):
    # Read bounded metadata without Torch. CUBLAS policy precedes imports.
    if 'torch' in sys.modules: raise RuntimeError('Proxy CLI requires fresh interpreter before Torch import')
    raw = args.request.read_bytes()
    if len(raw) > 2 << 20 or hashlib.sha256(raw).hexdigest() != args.request_sha256:
        raise ValueError('Bounded request raw SHA differs')
    preview = json.loads(raw)
    config_raw = Path(preview['configuration']['path']).read_bytes()
    if len(config_raw) > 2 << 20 or hashlib.sha256(config_raw).hexdigest() != preview['configuration']['sha256']:
        raise ValueError('Bounded configuration raw SHA differs')
    declared = json.loads(config_raw)
    if declared['proxy_contract']['execution']['deterministic']:
        os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    from phychem_mfm.phase1.v3_proxy_run import (validate_request,bind_inputs,build_experiment,
        checkpoint_capacity,validate_sources)
    from phychem_mfm.phase1.v3_sample_budget_events import physical,binding,write_once,require,encoded
    from phychem_mfm.phase1.v3_sample_budget_experiment import SegmentPause
    from phychem_mfm.phase1.v3_proxy_segments import allocate_launch
    from runtime_monitor import owned_output_bytes,owned_process_observation,gpu_observation
    ref,request = load_request(args.request,args.request_sha256)
    configuration,plan,registrations = validate_request(request,input_kind=args.input,engineering_only=args.engineering_only)
    require(os.environ.get('SLURM_JOB_ID') and int(os.environ.get('SLURM_CPUS_PER_TASK','0')) >= 16,
        'Owned Slurm allocation with at least16 CPUs required')
    require(not args.output.exists() and not physical(args.output).is_relative_to(REPO), 'Fresh outside-Git job root required')
    require(0 < args.until_samples <= plan.sample_budget,'Explicit registered advancing segment endpoint required')
    runtime = execution_context(configuration)
    now = time.time()
    require(all(receipt['verified_local_commit_epoch'] < now for receipt in registrations.values()),
        'Preregistration must precede actual training')
    contract = configuration['proxy_contract']; resources = contract['resources']
    # Unchanged outer supervisor must reserve this entire ledger allowance.
    outer_child = int(os.environ.get('MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES','0'))
    require(128 << 20 <= outer_child <= resources['joint_output_bytes']-resources['ledger_bytes']-(96 << 20),
        'Run under original supervisor with output cap <= joint cap minus full canonical ledger reserve')
    require(0 < resources['rss_bytes'] <= 56 << 30,'Explicit bounded RSS allowance required')
    from phychem_mfm.phase1.v3_long_run_storage import DurableLedger,allocate_long_launch,attach_experiment
    durable = DurableLedger(request,configuration) if 'long_run_policy' in configuration else None
    control_baseline = owned_output_bytes(durable.root) if durable is not None else 0
    canonical_baseline = owned_output_bytes(args.lineage_root) if durable is not None and args.lineage_root.exists() else 0
    inputs = bind_inputs(request,configuration)  # No candidate provider fallback.
    lock = None; run = None; experiment = None; failure = None; cleanup = []; outcome = None
    capacity_observation = None; capacity_artifacts = None
    phase='SETUP';failure_phase=None
    def set_phase(value):
        nonlocal phase
        phase=value
    started = time.monotonic(); args.output.mkdir(mode=0o700,parents=True)
    sdk_environment(args.output)
    try:
        if durable is not None:
            durable.allocate_segment(request_ref=ref,segment_id=args.segment_id,job_root=args.output,lineage_root=args.lineage_root)
        allocation = allocate_long_launch if durable is not None else allocate_launch
        allocation(args.lineage_root,request_ref=ref,lineage=args.lineage,job_root=args.output,segment_id=args.segment_id,
            maximum_attempts=plan.max_total_checkpoints,maximum_bytes=resources['ledger_bytes'])
        if contract['execution']['device'] == 'cuda':
            import fcntl
            uuid = contract['execution']['gpu_uuid']
            lock_root = Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks')
            lock = (lock_root/(uuid+'.lock')).open('a')
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            require(not gpu_observation(uuid,own_pids=(os.getpid(),))['foreign_processes'],'Selected GPU already occupied')
        import wandb
        run = wandb.init(project='mfm_model_v3_development',mode='offline',dir=str(args.output),
            name=f"proxy_{request['scope']}_{args.segment_id}_{os.environ['SLURM_JOB_ID']}",
            config={'request':ref,'configuration':configuration,'runtime':runtime,
                'source_state':request['sources']['state'],'runtime_files':request['sources']['runtime_files'],
                'engineering_only':configuration['engineering_only'],'scientific_acceptance':False})
        tracker = PersistentOfflineTracker(run,args.output/'history.jsonl')
        experiment = build_experiment(request,configuration,plan,inputs,tracker,output_root=args.output/'training',
            lineage_root=args.lineage_root,lineage=args.lineage,device=contract['execution']['device'])
        capacity_observation = install_training_observer(experiment, configuration, args.output, request_reference=ref)
        experiment.trainer.recipe_phase_observer=set_phase
        if durable is not None: attach_experiment(experiment,durable)
        capacity = checkpoint_capacity(experiment.trainer)
        reserve = resources['tracking_bytes']+(96 << 20)
        def census():
            if durable is not None: return durable.census()
            roots = experiment.lineage_output_roots()
            return sum(owned_output_bytes(root) for root in roots)
        def remaining():
            historical = durable.remaining(job_root=args.output) if durable is not None else resources['joint_output_bytes']-census()
            segment_remaining = resources['joint_output_bytes']-segment_bytes()
            return min(outer_child-owned_output_bytes(args.output),segment_remaining,historical)-reserve
        def segment_bytes():
            size = owned_output_bytes(args.output)
            if durable is not None:
                size += max(0,owned_output_bytes(durable.root)-control_baseline)
                size += max(0,owned_output_bytes(args.lineage_root)-canonical_baseline)
            return size
        experiment.joint_remaining_bytes = remaining
        def guard(action, context):
            set_phase('CHECKPOINT' if action == 'CHECKPOINT' else 'RESOURCE_PREFLIGHT')
            if action == 'CHECKPOINT': capacity.update(checkpoint_capacity(experiment.trainer))
            process = owned_process_observation(os.getpid()); size = census()
            row = {'action':action,'elapsed_inclusive_seconds':time.monotonic()-started,
                'lineage_owned_bytes':size,'current_job_bytes':owned_output_bytes(args.output),
                'rss_bytes':process['rss_sum_bytes'],'checkpoint_planning':capacity,
                'samples_consumed':context['samples_consumed']}
            require(row['elapsed_inclusive_seconds'] < plan.max_segment_seconds,'Whole-job inclusive wall budget exhausted')
            if action == 'STEP' and row['elapsed_inclusive_seconds'] >= plan.max_segment_seconds-plan.checkpoint_reserve_seconds:
                raise SegmentPause('inclusive checkpoint and SDK-finish wall reserve reached')
            require(row['rss_bytes'] <= resources['rss_bytes'],'Owned RSS allowance exhausted')
            if durable is not None: row['long_run_quota'] = durable.refresh()
            durable_limit = durable.limits['durable_bytes'] if durable is not None else resources['joint_output_bytes']
            require(row['current_job_bytes'] < outer_child and segment_bytes() < resources['joint_output_bytes']
                and size < durable_limit,'Segment or finite durable output cap exhausted')
            if contract['execution']['device'] == 'cuda':
                import torch
                gpu = gpu_observation(contract['execution']['gpu_uuid'],own_pids=[p['pid'] for p in process['processes']])
                own = sum(p['used_memory_bytes'] or 0 for p in gpu['compute_processes'] if p['own'])
                require(not gpu['foreign_processes'] and max(own,torch.cuda.max_memory_reserved(),torch.cuda.max_memory_allocated()) <= .85*gpu['total_bytes'],
                    'GPU ownership or original85percent bound exceeded')
                row['gpu'] = gpu
            if action in ('STEP','CHECKPOINT') and remaining() < capacity['planning_reserve_bytes']:
                if action == 'STEP': raise SegmentPause('joint lineage checkpoint planning reserve reached')
                raise MemoryError('Insufficient joint reserve for another complete checkpoint; prior immutable checkpoint retained')
            with (args.output/'resources.jsonl').open('ab') as stream: stream.write(encoded(row))
            if action in ('VALIDATION','VALIDATION_BATCH'): set_phase('VALIDATION')
        experiment.trainer.proxy_validation_guard = lambda: experiment._preflight('VALIDATION_BATCH',allow_pause=False)
        write_once(args.output/'RUN_BINDING.json',{'schema':'model_v3_proxy_segment_launch_v1','request':ref,
            'runtime':runtime,'registrations':registrations,'capacity_planning':capacity,
            'job_id':os.environ['SLURM_JOB_ID'],'lineage_root':str(physical(args.lineage_root)),
            'outer_child_budget_bytes':outer_child,'outer_terminal_evidence_required':True,
            'initial_cursors':{'optimizer_updates':experiment.trainer.clock.optimizer_updates,
                'samples_consumed':experiment.trainer.clock.samples_consumed,'log_cursor':experiment.trainer.log_cursor},
            'resume_complete':binding(args.resume_complete) if args.resume_complete else None,
            **({'training_execution': {'contract': experiment.trainer.contract['training_execution'],
                'provider_authority_receipt_sha256': experiment.trainer.bindings['proxy_authority_receipt_sha256'],
                'observation_configuration_pending_actual_forward': True}} if capacity_observation is not None else {})})
        parent = binding(args.resume_complete) if args.resume_complete else None
        set_phase('CONTROLLER')
        outcome = experiment.run_segment(segment_id=args.segment_id,until_samples=args.until_samples,
            request_ref=ref,parent=parent,preflight=guard)
        validate_sources(request)
    except BaseException as exc:
        failure_phase=phase
        failure = {'type':type(exc).__name__,'message':str(exc)[:600]}
        raise
    finally:
        for kind, callback in [('provider',inputs.provider.close),('wandb_finish',lambda: run.finish(exit_code=0 if failure is None else 1) if run else None)]:
            try: callback()
            except BaseException as exc: cleanup.append({'stage':kind,'type':type(exc).__name__,'message':str(exc)[:300]})
        if lock is not None:
            try: lock.close()
            except BaseException as exc: cleanup.append({'stage':'gpu_lock_close','type':type(exc).__name__,'message':str(exc)[:300]})
        if capacity_observation is not None:
            try:
                capacity_artifacts = finalize_training_observer(capacity_observation, args.output)
            except BaseException as exc:
                cleanup.append({'stage': 'training_capacity_finalize', 'type': type(exc).__name__, 'message': str(exc)[:300]})
        timed_out = time.monotonic()-started >= plan.max_segment_seconds
        if timed_out and failure is None:
            failure_phase='SDK_FINISH'
            failure = {'type':'TimeoutError','message':'Inclusive SDK cleanup exceeded registered segment wall budget'}
        status = 'CHILD_FINISHED_PENDING_ROOT_CLOSURE' if failure is None and not cleanup else 'CHILD_FAILED'
        receipt_ref = write_once(args.output/'CHILD_RECEIPT.json',{'schema':'model_v3_proxy_child_receipt_v1','status':status,
            'outcome':outcome,'first_failure':failure,'cleanup_errors':cleanup,'native_sdk_run_id':run.id if run else None,
            'elapsed_seconds_including_sdk_finish':time.monotonic()-started,
            'scientific_acceptance':False,'requires_actual_Slurm_C0_supervisor_and_SDK_verification':True,
            'job_id':os.environ['SLURM_JOB_ID'],
            **({'training_execution_capacity_artifacts': capacity_artifacts} if capacity_observation is not None else {}),
            'primary_failure':None if failure is None else {'schema':'model_v3_recipe_primary_failure_v1',
                'job_id':os.environ['SLURM_JOB_ID'],'phase':failure_phase,**failure},
            'committed_cursors':None if experiment is None else {
                'optimizer_updates':experiment.trainer.clock.optimizer_updates,'samples_consumed':experiment.trainer.clock.samples_consumed,
                'log_cursor':experiment.trainer.log_cursor,'pending_log':experiment.trainer.pending_log is not None}})
        if durable is not None and any(row['kind'] == 'launch_attempts' and row['identity'] == str(physical(args.output)) for row in durable.records()):
            durable.terminal(job_root=args.output,status='successful_segments' if status == 'CHILD_FINISHED_PENDING_ROOT_CLOSURE' else 'failed_attempts',result_ref=receipt_ref)
        if cleanup and failure is None: raise RuntimeError('Cleanup failed; see immutable CHILD_RECEIPT')
        if timed_out:
            raise TimeoutError('Inclusive SDK cleanup exceeded segment budget; outer closure required')


def parser():
    result = argparse.ArgumentParser(description=__doc__); commands = result.add_subparsers(dest='command',required=True)
    prepare = commands.add_parser('prepare-engineering')
    prepare.add_argument('--output',type=Path,required=True); prepare.add_argument('--base-code-sha',required=True)
    prepare.add_argument('--layers',type=int,choices=(1,6),default=1); prepare.add_argument('--sample-budget',type=int,default=6)
    prepare.add_argument('--views',choices=('two','three'),default='three')
    prepare.add_argument('--training-execution',type=Path); prepare.add_argument('--training-execution-sha256')
    prepare.add_argument('--groups',nargs='+',choices=('S','D','P'),default=['S','D','P'])
    run = commands.add_parser('run')
    run.add_argument('--request',type=Path,required=True); run.add_argument('--request-sha256',required=True)
    run.add_argument('--input',choices=('authoritative_proxy','authoritative_full_train','authoritative_grid_train','synthetic'),default='authoritative_proxy')
    run.add_argument('--engineering-only',action='store_true'); run.add_argument('--output',type=Path,required=True)
    run.add_argument('--lineage-root',type=Path,required=True); run.add_argument('--lineage',required=True)
    run.add_argument('--segment-id',required=True); run.add_argument('--until-samples',type=int,required=True)
    run.add_argument('--resume-complete',type=Path)
    for name in ('status','ack'):
        cmd = commands.add_parser(name); cmd.add_argument('--lineage-root',type=Path,required=True)
        cmd.add_argument('--ledger-bytes',type=int,required=True)
        if name == 'ack':
            for arg in ('event','result','evidence'): cmd.add_argument('--'+arg,type=Path,required=True)
    return result


def main():
    args = parser().parse_args()
    if args.command == 'run': return run_segment(args)
    from phychem_mfm.phase1.v3_proxy_run import engineering_request
    from phychem_mfm.phase1.v3_proxy_segments import BoundedLineageController
    from phychem_mfm.phase1.v3_sample_budget_events import read_bound,binding
    if args.command == 'prepare-engineering':
        if (args.training_execution is None) != (args.training_execution_sha256 is None):
            raise ValueError('Engineering execution declaration needs exact raw source SHA')
        execution = None
        if args.training_execution is not None:
            ref = binding(args.training_execution)
            if ref['sha256'] != args.training_execution_sha256:
                raise ValueError('Engineering execution source differs')
            execution = read_bound(ref)
        print(json.dumps(engineering_request(args.output,code_sha=args.base_code_sha,layers=args.layers,
            budget=args.sample_budget,views=args.views,groups=args.groups,training_execution=execution))); return
    contract = read_bound(binding(args.lineage_root/'EXPERIMENT.json'))['contract']
    if contract.get('model_configuration') is not None and 'long_run_policy' in read_bound(contract['model_configuration']):
        raise ValueError('Long-run status/ACK uses storage_control.py with a fresh complete operational request')
    controller = BoundedLineageController(args.lineage_root,contract=contract,
        max_records=contract['plan']['max_total_checkpoints'],maximum_bytes=args.ledger_bytes)
    if args.command == 'ack':
        print(json.dumps(controller.acknowledge(*(binding(getattr(args,key)) for key in ('event','result','evidence')))))
    else:
        # Metadata only. No model/weights, predictions or native labels read.
        print(json.dumps({'pending_event_count':len(controller.pending()),'curve':controller.curve()},allow_nan=False))


if __name__ == '__main__': main()
