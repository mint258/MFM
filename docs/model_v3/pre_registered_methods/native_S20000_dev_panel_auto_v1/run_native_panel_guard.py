#!/usr/bin/env python3
"""One Native panel, original limits, evaluator-only UUID lock; no submission."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import traceback
from native_admission import (B,N,LIMIT,PANEL_SHA,binding,read_ref,load,need,canonical,
    bridge_admission,native_admission,storage_admission,independent_root,same_reference,metadata_selfcheck,whole_output_bytes)
FIXED_RUNTIME_MONITOR=B/'MFM_model_v3_profiler_v2/tools/model_v3/runtime_monitor.py'
IDENTITY_ROOT=B/'MFM_model_v3_a_checkpoint/tools/model_v3'
RESOURCE=Path(__file__).absolute().parent/'panel_auto_resources.py'
HERE=Path(__file__).absolute().parent
require=need

def write(path,value):
    raw=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    require(len(raw)<=2*1024**2,'Bounded guard metadata required')
    with Path(path).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())

def checked_reference(candidate,authority,*,state_key=None):
    same_reference(candidate,authority,state_key=state_key)

def verify_sources(spec,request):
    import panel_auto_resources as auto
    require(spec['operations_source_pins']==auto.verify_sources(),'Exact published20k method sources required')
    auto.verify_publication(spec['method_publication'])
    root=Path(spec['repository_root'])
    bridge=bridge_admission(spec['bridge_validation'])
    require(bridge['evaluation_code_sha']==spec['code_sha'] and bridge['tree_sha']==spec['bridge_tree_sha'],
            'Current complete tested/public tree differs')
    for item in request['source_files']:
        path=(root/item['path']).resolve()
        require(path.is_relative_to(root.resolve()) and binding(path,16*1024**2)['sha256']==item['sha256'],
                'Executed request source inventory changed')
    for key in ('external_guard','external_preparer','native_admission_implementation','runtime_monitor',
                'Root_resource_guard_source','supervisor_source','protected_dependencies','sbatch_template'):
        ref=spec[key];require(binding(ref['path'])==ref,'Protected implementation changed: '+key)
    dependencies=read_ref(spec['protected_dependencies'])
    for ref in dependencies['files']:
        require(binding(ref['path'])=={k:ref[k] for k in ('path','bytes','sha256')},'Protected external dependency changed')
    for ref in spec['identity_dependencies'].values():
        require(binding(ref['path'])==ref,'Identity implementation changed')
    require(spec['external_guard']==binding(__file__) and spec['runtime_monitor']['path']==str(FIXED_RUNTIME_MONITOR),
            'Actual guard/fixed profiler monitor differs')
    native=native_admission(spec['native_authority'])
    require(native==spec['native_endpoint'],'Closed Native endpoint changed')
    checked_reference(request['checkpoint'],spec['source_checkpoint'],state_key='model')
    checked_reference(request['model_configuration'],spec['original_configuration'])
    checked_reference(request['training_completion'],spec['checkpoint_complete'])
    require(request['reference_kind']=='primary' and request['historical_reference'] is None,
            'Native-only declared primary pair required')

def runtime_modules(spec):
    require(spec['supervisor_source']['path']==str(IDENTITY_ROOT/'run_supervised.py'), 'Fixed identity supervisor required')
    for name in ('runtime_monitor','private_runtime_storage'):
        expected=spec['identity_dependencies'][name]
        require(expected['path']==str(IDENTITY_ROOT/(name+'.py')) and binding(expected['path'])==expected,
                'Fixed identity dependency differs')
        if name in sys.modules:
            require(Path(sys.modules[name].__file__).absolute()==Path(expected['path']),'Bare identity module contamination')
    sys.path.insert(0,str(IDENTITY_ROOT))
    identity=load(spec['supervisor_source']['path'],'native_panel_bound_supervisor')
    monitor=load(spec['runtime_monitor']['path'],'native_panel_bound_output_monitor')
    resource=load(spec['Root_resource_guard_source']['path'],'native_panel_bound_resource_guard')
    require(Path(resource.__file__).absolute()==RESOURCE,'Only existing validated Root resource helper permitted')
    return identity,monitor,resource

def precision(torch):
    return {'default_dtype':str(torch.get_default_dtype()),'matmul_precision':torch.get_float32_matmul_precision(),
        'cuda_matmul_allow_tf32':bool(torch.backends.cuda.matmul.allow_tf32),
        'cudnn_allow_tf32':bool(torch.backends.cudnn.allow_tf32),'cudnn_deterministic':bool(torch.backends.cudnn.deterministic),
        'cudnn_benchmark':bool(torch.backends.cudnn.benchmark),
        'deterministic_algorithms':torch.are_deterministic_algorithms_enabled(),
        'deterministic_warn_only':torch.is_deterministic_algorithms_warn_only_enabled(),
        'NVIDIA_TF32_OVERRIDE':os.environ.get('NVIDIA_TF32_OVERRIDE'),'CUBLAS_WORKSPACE_CONFIG':os.environ.get('CUBLAS_WORKSPACE_CONFIG')}

def child(spec,guard_output):
    request=read_ref(spec['request']);verify_sources(spec,request)
    root=Path(spec['repository_root']);sys.path.insert(0,str(root/'current'))
    import torch
    before=precision(torch);require(before['default_dtype']=='torch.float32','Unchanged FP32 export policy required')
    state={'schema':'model_v3_native_S_panel_child_runtime_v1','policy_before':before,
        'launcher_changes_precision_policy':False,'request_sha256':spec['request']['sha256'],
        'torch':str(torch.__version__),'torch_cuda':torch.version.cuda,'actual_argv':spec['request_argv'],
        'cuda_uuid':os.environ['CUDA_VISIBLE_DEVICES'],'H0_export_precision':'fp32_noAMP_declared_base_options',
        'pretraining_precision':spec['native_endpoint']['precision']}
    write(guard_output/'child_runtime_start.json',state);rc=1
    try:
        runner=load(root/'tools/model_v3/evaluate_dev_panel.py','native_guarded_original_evaluation_cli')
        sys.argv=spec['request_argv'][3:];rc=runner.main();return rc
    finally:
        after=precision(torch);state.update(policy_after=after,policy_unchanged=before==after,returncode=rc)
        if torch.cuda.is_initialized():
            state.update(torch_peak_allocated_bytes=torch.cuda.max_memory_allocated(),torch_peak_reserved_bytes=torch.cuda.max_memory_reserved())
        import resource
        state['process_peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        write(guard_output/'child_runtime_finish.json',state)
        require(before==after,'Evaluator changed ambient precision policy')

def observe(identity,process,observed,cgroup):
    # Discovery is not signal authority. Every discovered identity is bound to this kernel job.
    candidates=[]
    try:candidates=[identity.psutil.Process(process.pid),*identity.psutil.Process(process.pid).children(recursive=True)]
    except identity.psutil.NoSuchProcess:pass
    for candidate in candidates:
        current=identity.capture_process_identity(candidate.pid,expected_cgroup=cgroup)
        if current['status'] in {'GONE','EXITING'}:continue
        require(current['status']=='ACTIVE' and current['uid']==os.getuid(),'Descendant kernel identity/cgroup is invalid')
        key=(current['pid'],current['start_ticks'])
        if key in observed:
            require(all(observed[key][k]==current[k] for k in identity.IDENTITY_KEYS),'Observed descendant identity changed')
        observed[key]=current
    rss=0;live=[]
    for row in observed.values():
        state=identity.recorded_process_state(row)
        if state['status'] in {'GONE','EXITING'}:continue
        require(state['status']=='MATCH','Recorded identity changed; no new signal authority inferred')
        try:rss+=identity.psutil.Process(row['pid']).memory_info().rss;live.append(row['pid'])
        except identity.psutil.NoSuchProcess:pass
    return {'rss_bytes':rss,'pids':live}

def census(spec,request,monitor):
    base=independent_root(spec['output_base'],spec['repository_root'])
    total=whole_output_bytes(base,monitor)
    child=monitor.owned_output_bytes(Path(request['output_root']))
    child_limit=int(os.environ['MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES'])
    require(child_limit==LIMIT-96*1024**2,'Preserve actual supervisor-derived child ceiling')
    require(child<=child_limit and total-child<=96*1024**2 and total<=LIMIT-(64<<10),
            'Unified2GiB census or child/management allowance exceeded')
    return {'whole_output_base_bytes':total,'child_bytes':child,'management_unique_bytes':total-child,
            'physical_unique_root':str(base),'includes_control_guard_outer_stdio':True}

def verify_primary_result(spec, request, result):
    require(result.get('status') == 'COMPLETED' and result['request_sha256'] == spec['request']['sha256']
        and result['reference_kind'] == request['reference_kind'] == 'primary', 'Primary result/request scope differs')
    require(result['code_sha'] == request['code_sha'] == spec['code_sha'],
        'Actual executed evaluator code differs')
    pair = result['encoder_pair']
    for ref in (request['checkpoint'], pair['checkpoint']):
        checked_reference(ref, spec['source_checkpoint'], state_key='model')
    for ref in (request['model_configuration'], pair['original_configuration']):
        checked_reference(ref, spec['original_configuration'])
    require(pair['H0_dimension'] == 512 and pair['reference_kind'] == 'primary'
        and pair['checkpoint_schema'] == 'model_v3_native_S_immutable_checkpoint',
        'Actual primary512 candidate source/configuration differs')
    native=pair['native_checkpoint'];endpoint=spec['native_endpoint']
    require(native['schema']=='model_v3_native_S_checkpoint_encoder_binding_v1'
        and native['pretraining_code_sha']==endpoint['producer_code_sha']
        and native['pretraining_precision']==endpoint['precision']
        and native['optimizer_updates']==endpoint['optimizer_updates']
        and native['samples_consumed']==endpoint['samples_consumed']
        and native['native_contract_sha256']==endpoint['contract_sha256']
        and native['H0_export_precision']=='fp32_noAMP_declared_base_options'
        and native['BF16_training_forward_bitwise_replay_claimed'] is False,
        'Actual Native typed encoder provenance/precision/clocks differs')
    checked_reference(pair['training_completion'],spec['checkpoint_complete'])
    require(pair['architecture_sha256'] == result['architecture_sha256'] == request['architecture_sha256']
        and pair['random_reference_seed'] == result['random_reference_initialization_seed'] == 20261025
        and pair['pretraining_seed'] == request['pretraining_seed'] == result['pretraining_seed']
        and result['readout_seed'] == 0, 'Candidate/random full configuration or seeds differ')
    require(pair['checkpoint_encoder_state_sha256'] != pair['random_encoder_state_sha256'], 'Candidate and random weights must differ')
    tasks = {'cyp.3A4', 'cyp.2D6', 'exp.LogD', 'exp.LogS', 'exp.Log_HLM_CLint', 'qm9.U0', 'qm9.homo', 'qm9.lumo', 'qm9.alpha'}
    for name, expected in (('primary_18_cells', {task+'@'+readout for task in tasks for readout in ('ridge', 'linear64_relu')}),
        ('ridge', {task+'@ridge' for task in tasks}), ('linear64_relu', {task+'@linear64_relu' for task in tasks})):
        summary = result['summaries'][name]
        require(summary['complete'] is True and set(summary['tasks']) == expected
            and summary['bootstrap_samples'] == summary['bootstrap_defined'] == 1000, 'Incomplete frozen18cell/paired bootstrap result')
    caches = result['h0_caches']
    require(set(caches) == {label+'/'+dataset for label in ('candidate', 'reference')
        for dataset in ('cyp_isoform', 'expansionrx', 'qm9')}, 'Both primary512 native H0 inventories required')
    for dataset in ('cyp_isoform', 'expansionrx', 'qm9'):
        candidate, reference = (caches[label+'/'+dataset] for label in ('candidate', 'reference'))
        left, right = candidate['binding'], reference['binding']
        for key in ('architecture_sha256', 'membership_sha256', 'geometry_sha256', 'dimension',
                    'packing_plan_sha256', 'packing_budget_sha256', 'effective_runtime_sha256'):
            require(left[key] == right[key], 'Candidate/random primary H0 bindings differ')
        require(left['dimension'] == 512 and candidate['targets_cached'] is reference['targets_cached'] is False
            and candidate['molecules'] == reference['molecules'] and candidate['atoms'] == reference['atoms'],
            'Primary H0 dimension/target-free native inventory differs')
        require(left['encoder_sha256'] == pair['checkpoint_encoder_state_sha256']
            and right['encoder_sha256'] == pair['random_encoder_state_sha256'], 'Primary paired H0 weight-state binding differs')



def main():
    started=time.monotonic();p=argparse.ArgumentParser(description=__doc__)
    for flag in ('spec','spec-sha256','node','gpu-uuid','guard-output','root-admission','root-admission-sha256'):
        p.add_argument('--'+flag,required=True)
    p.add_argument('--child',action='store_true');a=p.parse_args()
    spec=read_ref({**binding(a.spec),'sha256':a.spec_sha256})
    require(spec['schema']=='model_v3_native_S_dev9_external_launch_v1' and spec['preregistration_sha']==PANEL_SHA,
            'Bound Native panel specification required')
    require(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID') and a.node==spec['node']=='compute-0-21'
        and socket.gethostname().split('.')[0]==a.node and os.environ.get('SLURMD_NODENAME')==a.node
        and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==16,
        'Actual UID/node/exact16CPU automatic allocation required')
    require(a.gpu_uuid==spec['gpu_uuid']==os.environ.get('CUDA_VISIBLE_DEVICES'),'Actual explicit physical UUID differs')
    require(spec['maximum_child_wall_seconds']==3500 and spec['maximum_process_group_rss_bytes']==28*1024**3
        and spec['maximum_output_and_cache_bytes']==LIMIT and spec['requested_memory_bytes'] is None
        and spec['software_memory_budget_bytes']==32*1024**3 and spec['Slurm_memory_mode']=='automatic_default'
        and spec['maximum_global_gpu_memory_fraction']==.85,'Original reviewed resource limits must remain unchanged')
    require(Path(sys.executable).absolute()==Path(spec['python_entry']).absolute(),'Verified logical Python required')
    request=read_ref(spec['request']);guard_output=Path(a.guard_output).absolute()
    base=independent_root(spec['output_base'],spec['repository_root'])
    require(guard_output.parent==base and guard_output.name=='guard_'+os.environ['SLURM_JOB_ID'],'Fresh task guard location differs')
    require(Path(request['output_root'])==base/'evaluation' and Path(request['cache_root'])==base/'evaluation/h0_cache',
            'One independent panel/cache family required')
    for fd in (1,2):
        target=Path(os.readlink('/proc/self/fd/'+str(fd)))
        require(target.is_absolute() and target.resolve().is_relative_to(base),'All inherited job stdio must be in same budgeted panel family')
    if a.child:return child(spec,guard_output)
    require(not guard_output.exists() and not Path(request['output_root']).exists(),'Fresh guard/evaluation/cold cache required')
    guard_output.mkdir(mode=0o700)
    outcome={'schema':'model_v3_native_S_panel_guard_result_v1','status':'FAILED','job_id':os.environ['SLURM_JOB_ID'],
        'node':a.node,'gpu_uuid':a.gpu_uuid,'spec_sha256':a.spec_sha256,'request_sha256':spec['request']['sha256'],
        'code_sha':spec['code_sha'],'producer_code_sha':spec['producer_code_sha'],
        'checkpoint_scope':spec['checkpoint_scope'],'GPU_GRES_isolation_claimed':False,
        'architecture_selection_claimed':False,'formal_pretraining_complete':False,'source':binding(__file__)}
    process=None;identity=None;observed={};recorder=None
    try:
        outcome['inline_metadata_controls']=metadata_selfcheck()
        verify_sources(spec,request);identity,monitor,resource=runtime_modules(spec)
        admission=read_ref({**binding(a.root_admission),'sha256':a.root_admission_sha256})
        require(admission['schema']=='model_v3_native_S_panel_Root_admission_v1' and admission['spec']==binding(a.spec)
            and admission['resource_guard_source']==spec['Root_resource_guard_source']
            and admission['storage']['registry_path']==spec['storage']['registry_path']
            and admission['storage']['reservation_id']==spec['storage']['reservation_id']
            and admission['actual_sbatch']==spec['prepared_sbatch']==binding(spec['prepared_sbatch']['path']),'Fresh actual Root admission binding differs')
        resource.verify_root_resources(admission['Root_resources'],{'gpu_uuid':a.gpu_uuid},spec=spec)
        private=sys.modules['private_runtime_storage'].load_storage_bindings()
        require(private['private_storage_budget_bytes']==LIMIT and len(private['roots'])==1
            and private['roots'][0]['kind']=='task_scratch'
            and private['roots'][0]['path']=='/tmp/mv3n_'+os.environ['SLURM_JOB_ID'],
            'Actual independently bounded private task scratch differs')
        outcome['actual_private_storage_binding']=private
        recorder=resource.Recorder();allocation=resource.actual_allocation_identity(spec)
        outcome['worker_admission']=resource.worker_resource_evidence(recorder,{'gpu_uuid':a.gpu_uuid},admission['Root_resources'],allocation,spec=spec)
        outcome['actual_allocation']=allocation
        storage=storage_admission(admission['storage'],base,quota_free_bytes=admission['Root_resources']['quota']['reserve_bytes'],
                                  current_output_bytes=whole_output_bytes(base,monitor))
        require(storage['entry_snapshot']==admission['storage_snapshot']['entry_snapshot'],'Actual independently registered hold changed')
        outcome['storage']=storage
        argv=[spec['python_entry'],'-u','-B',str(Path(__file__).absolute()),'--spec',a.spec,'--spec-sha256',a.spec_sha256,
              '--node',a.node,'--gpu-uuid',a.gpu_uuid,'--guard-output',str(guard_output),
              '--root-admission',a.root_admission,'--root-admission-sha256',a.root_admission_sha256,'--child']
        cgroup=Path('/proc/self/cgroup').read_text()
        with (guard_output/'child.log').open('xb') as log,(guard_output/'resource_samples.jsonl').open('x') as samples:
            process=subprocess.Popen(argv,cwd=spec['repository_root'],stdin=subprocess.DEVNULL,stdout=log,
                                     stderr=subprocess.STDOUT,start_new_session=True)
            initial=identity.capture_process_identity(process.pid,expected_cgroup=cgroup,expected_argv=argv)
            require(initial['status']=='ACTIVE' and initial['pgid']==initial['sid']==process.pid,'Actual child argv/PGID/SID/job identity differs')
            observed[(initial['pid'],initial['start_ticks'])]=initial;outcome['launch_identity']=initial
            next_sample=0.
            while process.poll() is None:
                now=time.monotonic();require(now-started<3500,'Original whole-panel3500s guard exhausted')
                usage=census(spec,request,monitor);group=observe(identity,process,observed,cgroup)
                require(group['rss_bytes']<=28*1024**3,'Owned panel descendant RSS exceeded28GiB')
                if now>=next_sample:
                    gpu=identity.gpu_observation(a.gpu_uuid,own_pids=[os.getpid(),*group['pids']])
                    require(not gpu['foreign_processes'],'Foreign GPU process observed; never signal foreign work')
                    require(type(gpu['total_bytes']) is int and gpu['total_bytes']>0
                        and type(gpu['used_bytes']) is int and gpu['used_bytes']>=0
                        and gpu['used_bytes']<=.85*gpu['total_bytes'],'Known actual global GPU memory must remain within85%')
                    row={'elapsed_seconds':now-started,'gpu':gpu,'owned':group,'census':usage}
                    samples.write(json.dumps(row,allow_nan=False)+'\n');samples.flush();os.fsync(samples.fileno());next_sample=now+5
                time.sleep(1)
            outcome['child_returncode']=process.returncode
        require(process.returncode==0,'Native full panel child exited nonzero')
        verify_sources(spec,request)
        runtime=json.loads((guard_output/'child_runtime_finish.json').read_bytes())
        require(runtime['policy_unchanged'] and runtime['process_peak_rss_bytes']<=28*1024**3,'Final FP32 export/RSS policy differs')
        result_path=Path(request['output_root'])/'result.json';result=json.loads(result_path.read_bytes())
        verify_primary_result(spec,request,result)
        require(time.monotonic()-started<=3500,'Inclusive original guard wall exhausted')
        outcome.update(status='COMPLETED',result=binding(result_path),child_runtime=runtime,final_census=census(spec,request,monitor),
            readouts=['ridge','linear64_relu'],H0_dimension=512,independent_WandB_SDK_verification_complete=False)
    except BaseException as exc:
        outcome.update(status='FAILED',exception_type=type(exc).__name__,reason=str(exc),exception_chain=traceback.format_exc())
    finally:
        if recorder is not None:outcome['actual_worker_observations']=recorder.rows
        if identity is not None and observed:
            retirement=identity.stop_recorded(observed,grace_seconds=15)
            outcome['retirement']=retirement
            if retirement['remaining']:
                outcome['status']='FAILED';outcome.setdefault('reason','Recorded child identities did not close')
        if process is not None:
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                outcome['status']='FAILED';outcome.setdefault('reason','Owned child failed final wait')
        outcome['elapsed_seconds_including_cleanup']=time.monotonic()-started
        write(guard_output/'guard_result.json',outcome)
    return 0 if outcome['status']=='COMPLETED' else 1
if __name__=='__main__':raise SystemExit(main())