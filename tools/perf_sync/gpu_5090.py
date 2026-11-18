"""5090-only continuation: immutable3090 artifacts, bounded short runs."""
import argparse
from collections import Counter
import csv
from contextlib import nullcontext
import gc
import inspect
import gzip
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import traceback
import warnings

from regression import REPO,SCRATCH,LIMIT,capacity,allocated_bytes
ROOT=SCRATCH/'gpu_5090_20261118'
REPORT=REPO/'results/perf_sync/gpu_5090_20261118'
os.environ['TORCHINDUCTOR_CACHE_DIR']=str(SCRATCH/'inductor_5090_20261118')
os.environ['TRITON_CACHE_DIR']=str(SCRATCH/'triton_5090_20261118')
# Never inherit the3090 driver workaround into Blackwell.
os.environ.pop('TRITON_PTXAS_PATH',None)
os.environ['NVIDIA_TF32_OVERRIDE']='0'
os.environ.pop('TORCH_ALLOW_TF32_CUBLAS_OVERRIDE',None)

import numpy as np
import torch
sys.path.insert(0,str(REPO/'tools/model_v3'))
import step_overhead as ref
from statistics_5090 import abba,two_seed_quality
from trace_5090 import export_gzip,summarize

UUID='GPU-9b6008d0-35dd-4bff-f69a-0927b04b7eef'
B3=Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/fixed_20261115/fixed_20261115_provisional_B_20261116_round2_B3_5090_resumed_20261117/samples_3000000.pt')
_BUDGET_NOTIFIED=False


def budget_note():
    global _BUDGET_NOTIFIED
    elapsed=time.time()-float(os.environ.get('PERF5090_LEASE_STARTED',time.time()))+float(os.environ.get('PERF5090_PREVIOUS_GPU_SECONDS',0))
    if elapsed>6*3600 and not _BUDGET_NOTIFIED:
        print('GPU_BUDGET_EXCEEDED_REPORT_ONLY_CONTINUE',elapsed,flush=True);_BUDGET_NOTIFIED=True


VARIANTS=dict(S1=dict(sync_free=True),S2=dict(fused_optimizer=True),S3=dict(sdpa=True),
    S4_encoder=dict(compile='encoder'),S4_encoder_heads=dict(compile='encoder_heads'),
    S5=dict(async_transfer=True))


def read(name):
    return json.loads((REPORT/(name+'.json')).read_text())


def publish(name,value):
    REPORT.mkdir(parents=True,exist_ok=True)
    target=REPORT/(name+'.json')
    temporary=target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n')
    temporary.replace(target)


def configuration():
    c=json.loads((REPO/'configs/perf_sync/M2_5090.json').read_text())
    if c['batch_size']!=32 or c['microbatch_size']!=32 or c['workers']!=14:
        raise ValueError('Frozen5090 baseline changed')
    return c


def options(name):
    if name in ('baseline','S0'):return {}
    if name=='S8':return read('combination')['options']
    if name=='S1b':return dict(sync_free=True)
    if name.endswith('_dynamic'):
        return dict(VARIANTS[name.removesuffix('_dynamic')],compile_mark_dynamic=True)
    return dict(VARIANTS[name])


def snapshot(model,samples,c,fields,families,execution):
    from phychem_mfm.model.perf_sync import finite_checks
    model.zero_grad(set_to_none=True)
    with finite_checks() if execution.get('sync_free') else nullcontext():
        total,loss=ref.calculate(model,samples,c,fields,families)
        total.backward()
    torch.cuda.synchronize()
    gradient=torch.cat([p.grad.detach().reshape(-1) if p.grad is not None else p.new_zeros(p.numel())
        for p in model.parameters()]).cpu()
    return gradient,{name:float(value.detach()) for name,value in loss.fields.items()},[n for n,p in model.named_parameters() if p.grad is None]


def gradient_difference(first,second):
    return float((first.double()-second.double()).norm()/first.double().norm().clamp_min(1e-30))


def noise():
    from phychem_mfm.phase1.p_recipe_input import prepare_samples,reader_metadata
    c=configuration();model,data,fields,families=ref.model_for(c,c['step_overhead'])
    meta=reader_metadata(model['pd'],fields)
    rng=np.random.default_rng(0);choices=[ref.draw(data,rng,32) for _ in range(20)]
    comparisons=[];rows=[]
    try:
        for weights in ('random_seed0','B3_3M'):
            if weights=='B3_3M':model.load_state_dict(torch.load(B3,map_location='cpu',weights_only=True)['model'])
            for batch,selected in enumerate(choices):
                capacity()
                samples=prepare_samples([data.read(m,k) for m,k in selected],meta)
                cpu_rng,cuda_rng=torch.get_rng_state(),torch.cuda.get_rng_state()
                torch.set_rng_state(cpu_rng);torch.cuda.set_rng_state(cuda_rng)
                first=snapshot(model,samples,c,fields,families,{})
                torch.set_rng_state(cpu_rng);torch.cuda.set_rng_state(cuda_rng)
                second=snapshot(model,samples,c,fields,families,{})
                el=max(abs(first[1][n]-second[1][n])/max(abs(first[1][n]),1e-30) for n in first[1])
                eg=gradient_difference(first[0],second[0])
                comparisons.append(dict(weights=weights,batch=batch,epsilon_loss=el,epsilon_grad=eg))
                for repeat,result in enumerate((first,second)):
                    rows.extend(dict(weights=weights,batch=batch,repeat=repeat,field=n,loss=v) for n,v in result[1].items())
                print('NOISE5090',weights,batch,el,eg,flush=True)
        summary=dict(status='COMPLETE',gpu=torch.cuda.get_device_name(),uuid=UUID,
            torch=torch.__version__,cuda=torch.version.cuda,checkpoint=str(B3),
            epsilon_loss=max(r['epsilon_loss'] for r in comparisons),
            epsilon_grad=max(r['epsilon_grad'] for r in comparisons),comparisons=comparisons,
            note='Fresh5090 PR8 relative noise definition. Full gradients compared in RAM; no new multi-GB gradient files.')
        with (ROOT/'S0_field_losses.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        publish('S0_noise',summary)
    finally:data.close()


def numerical(name):
    from phychem_mfm.phase1.p_recipe_input import prepare_samples,reader_metadata
    from phychem_mfm.phase1.perf_sync_transfer import async_batches
    c=configuration();base_options=dict(c['step_overhead']);execution=dict(base_options,**options(name))
    base,data,fields,families=ref.model_for(c,base_options)
    candidate,extra,candidate_fields,candidate_families=ref.model_for(c,execution);extra.close()
    if fields!=candidate_fields or families!=candidate_families:raise ValueError('Scientific fields changed')
    base_meta=reader_metadata(base['pd'],fields)
    variant_meta=reader_metadata(candidate['pd'],fields,sync_free=execution['sync_free'],async_transfer=execution['async_transfer'])
    rng=np.random.default_rng(0);choices=[ref.draw(data,rng,32) for _ in range(20)]
    floor=read('S0_noise');el,eg=floor['epsilon_loss'],floor['epsilon_grad']
    comparisons=[];rows=[];backend=[]
    try:
        for weights in ('random_seed0','B3_3M'):
            if weights=='B3_3M':
                cp=torch.load(B3,map_location='cpu',weights_only=True)
                base.load_state_dict(cp['model']);candidate.load_state_dict(cp['model']);del cp
            for batch,selected in enumerate(choices):
                capacity()
                raw=[data.read(m,k) for m,k in selected]
                baseline_samples=prepare_samples(raw,base_meta)
                variant_samples=prepare_samples(raw,variant_meta)
                cpu_rng,cuda_rng=torch.get_rng_state(),torch.cuda.get_rng_state()
                first=snapshot(base,baseline_samples,c,fields,families,{})
                torch.set_rng_state(cpu_rng);torch.cuda.set_rng_state(cuda_rng)
                transfer=None
                if execution['async_transfer']:
                    transfer=async_batches(iter([(variant_samples,{})]));variant_samples,_=next(transfer)
                profiler=torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU]) if name=='S3' and weights=='random_seed0' and batch==0 else None
                with profiler if profiler is not None else nullcontext():
                    second=snapshot(candidate,variant_samples,c,fields,families,execution)
                if transfer is not None:transfer.close()
                if profiler is not None:backend=sorted({e.key for e in profiler.key_averages() if 'scaled_dot_product' in e.key})
                gd=gradient_difference(first[0],second[0])
                keys_equal=set(first[1])==set(second[1])
                same_unused=first[2]==second[2]
                bitwise=torch.equal(first[0],second[0]) and first[1]==second[1] and same_unused
                losses_pass=keys_equal and all(abs(second[1][n]-first[1][n])<=10*el*(1+abs(first[1][n])) for n in first[1])
                gradient_gate=weights=='random_seed0'
                passed=same_unused and losses_pass and math.isfinite(gd) and (not gradient_gate or gd<=10*eg)
                comparisons.append(dict(weights=weights,batch=batch,bitwise=bitwise,grad_relative=gd,
                    gradient_gate_applied=gradient_gate,losses_pass=losses_pass,B_pass=passed))
                rows.extend(dict(weights=weights,batch=batch,field=n,baseline=first[1][n],variant=second[1][n],
                    absolute_difference=abs(second[1][n]-first[1][n])) for n in first[1])
                print('NUMERICAL5090',name,weights,batch,gd,passed,flush=True)
        expects_A=name in ('S1','S1b','S5') or (name=='S8' and set(read('combination')['items']).issubset({'S1','S1b','S5'}))
        exact=all(r['bitwise'] for r in comparisons)
        summary=dict(item=name,category='A' if expects_A and exact else 'B',A_pass=exact,
            B_single_step_pass=all(r['B_pass'] for r in comparisons),comparisons=comparisons,
            epsilon_loss=el,epsilon_grad=eg,options=execution,SDPA_observed_operators=backend,
            note='B3 gradient relative difference is reported, not thresholded; loss tolerance unchanged. Fresh paired reference on each batch avoids gradient-file duplication.')
        with (ROOT/(name+'_field_deviations.csv')).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        publish(name+'_numerical',summary)
    finally:data.close()


def profile(name,variant):
    from phychem_mfm.phase1.p_recipe_training import train
    # Native Kineto may keep one internal temporary; export itself is piped.
    if allocated_bytes((SCRATCH,REPO/'results/perf_sync/scratch'))+6*1024**3>LIMIT:
        raise OSError('Reserve6GiB for native profiler temporary plus compressed output')
    c=configuration();c['step_overhead'].update(options(variant))
    c.update(run='perf5090_'+name+'_profile',output=str(ROOT/(name+'_profile_'+os.environ['SLURM_JOB_ID'])),benchmark_updates=200)
    profiler=torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU,torch.profiler.ProfilerActivity.CUDA],with_stack=True)
    from phychem_mfm.phase1.perf_sync_step import StepBuffer
    original=torch.optim.AdamW.zero_grad;original_sync=torch.cuda.synchronize;original_drain=StepBuffer.drain
    steps=0;active=False;region=None
    def timer_sync(*args,**kwargs):
        frame=inspect.currentframe().f_back;filename=frame.f_code.co_filename
        measured=filename.endswith('p_recipe_training.py') or '/torch/autograd/profiler.py' in filename or '/torch/profiler/profiler.py' in filename
        with torch.profiler.record_function('PERF5090_INSTRUMENTATION_SYNC') if measured else nullcontext():
            return original_sync(*args,**kwargs)
    def report_drain(self,*args,**kwargs):
        with torch.profiler.record_function('PERF5090_REPORTING_SYNC'):
            return original_drain(self,*args,**kwargs)
    torch.cuda.synchronize=timer_sync;StepBuffer.drain=report_drain
    def zero_grad(self,*args,**kwargs):
        nonlocal steps,active,region
        if steps==100:
            original_sync();profiler.start();active=True
            region=torch.profiler.record_function('PERF5090_TRAINING_REGION');region.__enter__()
        if steps>100:profiler.step()
        steps+=1
        return original(self,*args,**kwargs)
    torch.optim.AdamW.zero_grad=zero_grad
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always');torch.cuda.set_sync_debug_mode('warn')
            result=train(c);torch.cuda.set_sync_debug_mode('default')
        region.__exit__(None,None,None);region=None
        profiler.stop();active=False
        trace=ROOT/(name+'_trace_'+os.environ['SLURM_JOB_ID']+'.json.gz')
        export_gzip(profiler,trace)
        locations=Counter(w.filename+':'+str(w.lineno)+': '+str(w.message) for w in captured)
        (ROOT/(name+'_sync_warnings.txt')).write_text('\n'.join(str(n)+' '+s for s,n in locations.items())+'\n')
        summary=summarize(trace,result['measured_seconds'],main_tid=os.getpid())
        summary.update(item=name,uuid=UUID,sync_warning_locations=dict(locations),result=result)
        publish(name+'_profile',summary)
        print('PROFILE5090',json.dumps(summary),flush=True)
    finally:
        torch.cuda.set_sync_debug_mode('default');torch.optim.AdamW.zero_grad=original
        torch.cuda.synchronize=original_sync;StepBuffer.drain=original_drain
        if region is not None:region.__exit__(None,None,None)
        if active:profiler.stop()

def benchmark(name,variant,seed=0,cores=16):
    from phychem_mfm.phase1.p_recipe_training import train
    from phychem_mfm.phase1 import perf_sync_step
    from torch._dynamo.utils import counters,compile_times,get_compilation_metrics,clear_compilation_metrics,set_compilation_metrics_limit
    from torch._guards import CompileId
    allowed=sorted(os.sched_getaffinity(0))
    if cores>min(len(allowed),int(os.environ['SLURM_CPUS_PER_TASK'])):raise RuntimeError('CPU scan exceeds actual allocation')
    os.sched_setaffinity(0,allowed[:cores])
    c=configuration();execution=dict(c['step_overhead'],**options(variant))
    output=ROOT/(name+'_training_'+os.environ['SLURM_JOB_ID'])
    if output.exists():raise FileExistsError('Retain failed output; use a distinct attempt name')
    c.update(run='perf5090_'+name,output=str(output),seed=seed,workers=14,
        step_overhead=execution,benchmark_updates=1000,benchmark_warmup_batches=100)
    stopped=threading.Event();telemetry=[];telemetry_errors=[]
    def capture():
        while not stopped.is_set():
            try:
                value=subprocess.check_output(['nvidia-smi','-i',UUID,'--query-gpu=power.draw,utilization.gpu','--format=csv,noheader,nounits'],text=True)
                telemetry.append([time.time(),*map(float,value.strip().split(','))])
            except (OSError,ValueError,subprocess.CalledProcessError) as error:telemetry_errors.append(str(error))
            stopped.wait(1)
    monitor=threading.Thread(target=capture,daemon=True);monitor.start()
    counters.clear();clear_compilation_metrics();set_compilation_metrics_limit(10000)
    original=perf_sync_step.make_optimizer;observation={};warm_ids=set()
    def optimizer(parameters,configuration):
        result=original(parameters,configuration)
        observation.update(backend=getattr(result,'perf_sync_backend','default'),
            parameter_dtypes=sorted({str(p.dtype) for g in result.param_groups for p in g['params']}),
            param_groups=[dict(fused=g.get('fused'),foreach=g.get('foreach')) for g in result.param_groups])
        zero=result.zero_grad;calls=0
        def counted(*args,**kwargs):
            nonlocal calls,warm_ids
            calls+=1
            if calls==102:warm_ids={str(m.compile_id) for m in get_compilation_metrics()}
            return zero(*args,**kwargs)
        result.zero_grad=counted
        return result
    perf_sync_step.make_optimizer=optimizer
    try:result=train(c)
    finally:
        perf_sync_step.make_optimizer=original;stopped.set();monitor.join(timeout=5)
    if result['updates']!=1000 or result['measured_updates']!=1000:raise RuntimeError('Actual/measured update cap differs')
    measured=[r for r in telemetry if result['measure_wall_start']<=r[0]<=result['measure_wall_end']]
    if not measured:raise RuntimeError('No actual in-window power samples')
    with (output/'losses.csv').open() as f:losses=list(csv.DictReader(f))
    if len(losses)!=1000:raise RuntimeError('Missing per-update loss rows')
    totals=[float(r['total']) for r in losses]
    metrics=get_compilation_metrics();ids=set()
    for metric in metrics:
        if metric.compile_id is None:continue
        identifier=str(metric.compile_id)
        if (CompileId.from_string(identifier).frame_compile_id or 0)>0:ids.add(identifier)
    result.update(item=name,variant=variant,seed=seed,cpu_affinity=sorted(os.sched_getaffinity(0)),readers=14,
        options=execution,uuid=UUID,gpu=torch.cuda.get_device_name(),torch=torch.__version__,cuda=torch.version.cuda,
        actual_optimizer_updates=1000,precision=dict(matmul_allow_tf32=torch.backends.cuda.matmul.allow_tf32,cudnn_allow_tf32=torch.backends.cudnn.allow_tf32,matmul_precision=torch.get_float32_matmul_precision(),NVIDIA_TF32_OVERRIDE=os.environ.get('NVIDIA_TF32_OVERRIDE')),warmup='100 no-update forward/backward passes; CPU/CUDA RNG restored',
        power_W=float(np.mean([r[1] for r in measured])),last200_mean=float(np.mean(totals[-200:])),
        finite=bool(np.isfinite(totals).all()),recompilations=len(ids-warm_ids),
        recompilations_total_including_warmup=len(ids),optimizer_execution=observation,
        compilation_metrics=[dict(compile_id=str(m.compile_id),co_name=m.co_name,
            entire_frame_compile_time_s=m.entire_frame_compile_time_s,backend_compile_time_s=m.backend_compile_time_s,
            inductor_compile_time_s=m.inductor_compile_time_s,fail_type=m.fail_type) for m in metrics],
        compiler_timing_table=compile_times(),telemetry_errors=telemetry_errors)
    with (ROOT/(name+'_telemetry.csv')).open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['unix_seconds','power_W','utilization_percent']);writer.writerows(telemetry)
    publish(name+'_benchmark',result)


def foreign_contexts():
    output=subprocess.check_output(['nvidia-smi','-i',UUID,'--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True)
    foreign=[]
    for line in output.splitlines():
        if not line.strip().isdigit():continue
        pid=int(line);path=Path('/proc')/str(pid)/'cgroup'
        try:groups=path.read_text()
        except FileNotFoundError:continue
        except PermissionError:foreign.append(pid);continue
        token='/job_'+os.environ['SLURM_JOB_ID']
        if not any(token+'/' in part or part.endswith(token) for part in groups.splitlines()):foreign.append(pid)
    return foreign


def stage(kind,name=None,variant=None,seed=0,cores=16):
    key='S0_noise' if kind=='noise' else name+('_profile' if kind=='profile' else '_numerical' if kind=='numerical' else '_benchmark')
    if (REPORT/(key+'_interference.json')).exists():raise RuntimeError('Contaminated stage retained; a new controlled attempt is required')
    if (REPORT/(key+'.json')).exists():return read(key)
    existing=foreign_contexts()
    if existing:raise RuntimeError('Foreign CUDA contexts; do not start new work: '+str(existing))
    command=[sys.executable,'-B','-u',__file__,kind,'--name',name or 'S0','--variant',variant or 'baseline','--seed',str(seed),'--cores',str(cores)]
    child=subprocess.Popen(command,start_new_session=True)
    interference=set();started=time.monotonic()
    try:
        while child.poll() is None:
            budget_note();capacity()
            if kind=='profile' and allocated_bytes((SCRATCH,REPO/'results/perf_sync/scratch'))>LIMIT-1024**3:
                raise OSError('Stop new profiling writes before scratch headroom is consumed')
            sys.path.insert(0,str(REPO.parent/'MFM_p_recipe/tools/model_v3'))
            import v2_diagnosis_disk as disk
            disk.m.require_capacity(disk.m.filesystem_status('/dev/shm'),2*1024**3,10000)
            interference.update(foreign_contexts())
            time.sleep(1 if kind=='profile' else 5)
        if child.returncode:raise RuntimeError(key+' exited '+str(child.returncode)+'; retain unfinished artifacts')
        if interference:
            publish(key+'_interference',dict(foreign_pids=sorted(interference),status='CONTAMINATED',elapsed=time.monotonic()-started))
            raise RuntimeError('External GPU interference; this block is not controlled')
        return read(key)
    except BaseException:
        if child.poll() is None:os.killpg(child.pid,signal.SIGTERM);child.wait()
        raise


def measure_abba(name):
    refs=[]
    for suffix,variant in (('A0','baseline'),('B0',name),('B1',name),('A1','baseline')):
        key=name+'_'+suffix
        result=stage('benchmark',key,variant)
        refs.append(result)
    result=abba([r['samples_per_second'] for r in refs])
    compile_ok=all(r['recompilations']<=20 for r in (refs[1],refs[2])) if name.startswith('S4') else True
    result.update(item=name,run_order=[r['item'] for r in refs],rates=[r['samples_per_second'] for r in refs],
        compile_count=[r['recompilations'] for r in refs],compile_valid=compile_ok,
        speed_effective=result['speed_effective'] and compile_ok,quality_seed0_source=refs[1]['item'])
    publish(name+'_ABBA',result)
    return result


def initial():
    stage('profile','S0','baseline');stage('noise')
    tested=[]
    for name in VARIANTS:
        stage('numerical',name,name);result=measure_abba(name)
        chosen=name
        if name.startswith('S4') and not result['compile_valid']:
            chosen=name+'_dynamic';stage('numerical',chosen,chosen);result=measure_abba(chosen)
        tested.append(chosen)
        if name=='S1':stage('profile','S1','S1')
        publish('initial_progress',dict(completed=tested,remaining=[n for n in VARIANTS if not any(t.startswith(n) for t in tested)]))
    s0,s1=read('S0_profile'),read('S1_profile')
    needs_b=s0['GPU_busy_wall_ratio']<.70 and s1['training_synchronizations_per_step']>20
    publish('initial',dict(status='COMPLETE',candidates=tested,S1b_required=needs_b,
        S0_GPU_busy=s0['GPU_busy_wall_ratio'],S1_sync_per_step=s1['training_synchronizations_per_step']))
    if needs_b:
        publish('S1b',dict(status='NEEDS_IMPLEMENTATION',condition=True,timebox_hours=4,
            allowed_sites=s0.get('sync_warning_locations',{})))
        print('WAIT_FOR_S1B_IMPLEMENTATION',flush=True)
    else:
        publish('S1b',dict(status='NOT_APPLICABLE',condition=False))
        finish()


def measure_s1b():
    if read('S1b').get('condition') is not True:raise RuntimeError('S1b condition not met')
    stage('numerical','S1b','S1b');measure_abba('S1b');stage('profile','S1b','S1b')
    publish('S1b',dict(status='COMPLETE',condition=True))
    finish()


def quality(name):
    baseline0=read('S1_A0_benchmark')
    baseline1=stage('benchmark','quality_baseline_seed1','baseline',seed=1)
    candidate0=read(name+'_B0_benchmark')
    candidate1=stage('benchmark','quality_'+name+'_seed1',name,seed=1)
    result=two_seed_quality({0:baseline0['last200_mean'],1:baseline1['last200_mean']},
        {0:candidate0['last200_mean'],1:candidate1['last200_mean']},
        {0:baseline0['finite'] and candidate0['finite'],1:baseline1['finite'] and candidate1['finite']})
    result.update(item=name,seed0_reused_from_ABBA=True,baseline_seed0='S1_A0',
        baseline_seed1='quality_baseline_seed1',candidate_seed0=name+'_B0',candidate_seed1='quality_'+name+'_seed1',
        baseline_losses=[baseline0['last200_mean'],baseline1['last200_mean']],
        candidate_losses=[candidate0['last200_mean'],candidate1['last200_mean']])
    publish(name+'_quality',result)
    return result


def finish():
    initial_result=read('initial');candidates=list(initial_result['candidates'])
    s1b=read('S1b')
    if s1b['status']=='NEEDS_IMPLEMENTATION':raise RuntimeError('S1b is still required')
    if s1b['status']=='COMPLETE':candidates=['S1b' if n=='S1' else n for n in candidates]
    available=min(len(os.sched_getaffinity(0)),int(os.environ['SLURM_CPUS_PER_TASK']))
    scan=[]
    for cores in (4,8,16,24):
        if cores>available and not (REPORT/('S7_'+str(cores)+'_benchmark.json')).exists():
            scan.append(dict(cores=cores,readers=14,status='NOT_AVAILABLE_CPU',allocation=available));continue
        result=stage('benchmark','S7_'+str(cores),'baseline',cores=cores)
        scan.append(dict(cores=cores,readers=14,status='COMPLETE',samples_per_second=result['samples_per_second'],
            main_CPU_percent=result['main_CPU_percent'],power_W=result['power_W'],GPU_peak_bytes=result['GPU_peak_bytes']))
    publish('S7',scan)
    assessments=[]
    for name in candidates:
        speed=read(name+'_ABBA');numeric=read(name+'_numerical')
        training=quality(name) if speed['speed_effective'] else None
        accepted=numeric['A_pass'] if numeric['category']=='A' else numeric['B_single_step_pass']
        accepted=bool(accepted and training is not None and training['passed'])
        assessments.append(dict(item=name,speed_effective=speed['speed_effective'],single_step=numeric['category'],
            single_pass=numeric['A_pass'] if numeric['category']=='A' else numeric['B_single_step_pass'],
            quality_pass=None if training is None else training['passed'],effective=speed['speed_effective'] and accepted,
            ABBA_speedup=speed['speedup'],baseline_noise_fraction=speed['baseline_noise_fraction']))
    publish('assessments',assessments)
    sync=read(('S1b' if s1b['status']=='COMPLETE' else 'S1')+'_profile')['training_synchronizations_per_step']
    if sync>0:
        publish('S6',dict(status='NOT_APPLICABLE',measured_sync_per_step=sync))
    elif not (REPORT/'S6.json').exists():
        publish('S6',dict(status='NEEDS_IMPLEMENTATION',measured_sync_per_step=sync,timebox_hours=4))
        print('WAIT_FOR_S6_IMPLEMENTATION',flush=True);return
    if read('S6')['status']=='NEEDS_IMPLEMENTATION':return
    selected=[a for a in assessments if a['effective']]
    compile_modes=[a for a in selected if a['item'].startswith('S4')]
    if len(compile_modes)>1:
        best=max(compile_modes,key=lambda a:a['ABBA_speedup'])['item']
        selected=[a for a in selected if not a['item'].startswith('S4') or a['item']==best]
    combined={}
    for item in selected:combined.update(options(item['item']))
    publish('combination',dict(items=[a['item'] for a in selected],options=combined))
    stage('numerical','S8','S8');speed=measure_abba('S8');training=quality('S8')
    stage('profile','S8','S8')
    numeric=read('S8_numerical')
    single=numeric['A_pass'] if numeric['category']=='A' else numeric['B_single_step_pass']
    publish('S8',dict(status='PASS' if single and training['passed'] else 'FAIL',
        items=[a['item'] for a in selected],options=combined,ABBA=speed,quality=training,
        single_pass=single,empty_combination_control=not bool(selected),
        adoptable_speedup=speed['speedup'] if selected and single and training['passed'] and speed['speed_effective'] else 1.0))


def drive():
    try:initial()
    except BaseException as error:
        publish('NEEDS_DIAGNOSIS',dict(error=str(error),job=os.environ['SLURM_JOB_ID'],time=time.time()))
        traceback.print_exc()
    while not (REPORT/'S8.json').exists():
        capacity()
        budget_note()
        request=REPORT/'NEXT_PHASE'
        if request.exists():
            phase=request.read_text().strip();request.rename(REPORT/('started_'+phase+'_'+str(int(time.time()))))
            if phase not in ('initial','measure_s1b','finish'):raise ValueError('Unknown continuation phase')
            try:globals()[phase]()
            except BaseException as error:
                publish('NEEDS_DIAGNOSIS',dict(error=str(error),phase=phase,job=os.environ['SLURM_JOB_ID'],time=time.time()))
                traceback.print_exc()
        time.sleep(5)


def main():
    def terminated(signum,frame):raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,terminated);signal.signal(signal.SIGINT,terminated)
    parser=argparse.ArgumentParser()
    parser.add_argument('kind',choices=('noise','numerical','profile','benchmark','drive'))
    parser.add_argument('--name',default='S0');parser.add_argument('--variant',default='baseline')
    parser.add_argument('--seed',type=int,choices=(0,1),default=0);parser.add_argument('--cores',type=int,choices=(4,8,16,24),default=16)
    args=parser.parse_args()
    if os.environ.get('CUDA_VISIBLE_DEVICES')!=UUID or not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Registered single5090 Slurm allocation required')
    if args.kind!='drive':
        requested=args.cores if args.kind=='benchmark' else 16
        allowed=sorted(os.sched_getaffinity(0))
        if requested>min(len(allowed),int(os.environ['SLURM_CPUS_PER_TASK'])):raise RuntimeError('Requested affinity exceeds allocation')
        os.sched_setaffinity(0,allowed[:requested])
        if not torch.cuda.is_available() or '5090' not in torch.cuda.get_device_name():raise RuntimeError('Actual5090 required')
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    capacity();ROOT.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
    if args.kind=='drive':drive()
    elif args.kind=='noise':noise()
    elif args.kind=='numerical':numerical(args.variant)
    elif args.kind=='profile':profile(args.name,args.variant)
    else:benchmark(args.name,args.variant,args.seed,args.cores)


if __name__=='__main__':main()
