"""GPU-only continuation of PR13; closed results are retained, not replayed."""
import argparse
import csv
import json
import os
import signal
import subprocess
import threading
from pathlib import Path
import sys
import time
import warnings

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'model_v3'))
import step_overhead as ref
from regression import REPO, SCRATCH, capacity

ROOT = SCRATCH / 'gpu_20261118'
REPORT = REPO / 'results/perf_sync/gpu_20261118'
B3 = Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/fixed_20261115/fixed_20261115_provisional_B_20261116_round2_B3_5090_resumed_20261117/samples_3000000.pt')
VARIANTS = dict(S1=dict(sync_free=True), S2=dict(fused_optimizer=True), S3=dict(sdpa=True),
                S4_encoder=dict(compile='encoder'), S4_encoder_heads=dict(compile='encoder_heads'),
                S5=dict(async_transfer=True))


def configuration():
    return json.loads((REPO / 'configs/perf_sync/M2.json').read_text())


def variant_options(name):
    if name == 'S8':return json.loads((REPORT/'combination.json').read_text())['options']
    if name.endswith('_dynamic'):
        return dict(VARIANTS[name.removesuffix('_dynamic')],compile_mark_dynamic=True)
    return VARIANTS.get(name,{})


def noise():
    from phychem_mfm.phase1.p_recipe_input import prepare_samples, reader_metadata
    c = configuration()
    model, data, fields, families = ref.model_for(c, c['step_overhead'])
    metadata = reader_metadata(model['pd'], fields)
    rng = np.random.default_rng(0)
    choices = [ref.draw(data, rng, 32) for _ in range(20)]
    result = []
    rows = []
    try:
        for weights in ('random_seed0', 'B3_3M'):
            if weights == 'B3_3M':
                cp = torch.load(B3, map_location='cpu', weights_only=True)
                model.load_state_dict(cp['model'])
                del cp
            for batch, selected in enumerate(choices):
                capacity()
                samples = prepare_samples([data.read(m, conf) for m, conf in selected], metadata)
                cpu_rng, cuda_rng = torch.get_rng_state(), torch.cuda.get_rng_state()
                runs = []
                for repeat in range(2):
                    torch.set_rng_state(cpu_rng)
                    torch.cuda.set_rng_state(cuda_rng)
                    model.zero_grad(set_to_none=True)
                    total, loss = ref.calculate(model, samples, c, fields, families)
                    total.backward()
                    torch.cuda.synchronize()
                    grad = torch.cat([p.grad.detach().flatten() if p.grad is not None else p.new_zeros(p.numel()) for p in model.parameters()]).cpu()
                    values = {n: float(v.detach()) for n, v in loss.fields.items()}
                    runs.append((grad, values, [n for n, p in model.named_parameters() if p.grad is None]))
                    rows.extend(dict(weights=weights, batch=batch, repeat=repeat, field=n, loss=v) for n, v in values.items())
                    if repeat == 0:
                        target = ROOT / 'baseline_gradients' / weights
                        target.mkdir(parents=True, exist_ok=True)
                        torch.save(dict(gradient=grad, losses=values, unused=runs[-1][2], cpu_rng=cpu_rng, cuda_rng=cuda_rng), target / f'{batch:02d}.pt')
                g1, l1, _ = runs[0]
                g2, l2, _ = runs[1]
                # Per-field absolute+relative noise in the taskbook units.
                el = max(abs(l1[n]-l2[n]) / (1+abs(l1[n])) for n in l1)
                eg = float((g1.double()-g2.double()).norm() / g1.double().norm().clamp_min(1e-30))
                result.append(dict(weights=weights, batch=batch, epsilon_loss=el, epsilon_grad=eg))
                print('NOISE', weights, batch, el, eg, flush=True)
        summary = dict(status='PASS', epsilon_loss=max(r['epsilon_loss'] for r in result), epsilon_grad=max(r['epsilon_grad'] for r in result), records=result,
            checkpoint=str(B3), uuid=os.environ['CUDA_VISIBLE_DEVICES'], gpu=torch.cuda.get_device_name(), torch=torch.__version__, cuda=torch.version.cuda)
        (REPORT / 'S0_noise.json').write_text(json.dumps(summary, indent=2)+'\n')
        with (ROOT / 'S0_field_losses.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['weights','batch','repeat','field','loss'])
            writer.writeheader(); writer.writerows(rows)
    finally:
        data.close()


def profile(name='S0'):
    from phychem_mfm.phase1.p_recipe_training import train
    c = configuration()
    c.update(run=f'perf_sync_{name}_profile_20261118', output=str(ROOT/f'{name}_profile_training'), benchmark_updates=200)
    if name != 'S0': c['step_overhead'].update(variant_options(name))
    prof = torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU, torch.profiler.ProfilerActivity.CUDA], with_stack=True)
    original = torch.optim.AdamW.zero_grad
    steps = 0
    active = False
    def zero_grad(self, *args, **kwargs):
        nonlocal steps, active
        if steps == 100:
            torch.cuda.synchronize(); prof.start(); active = True
        if steps > 100:
            prof.step()
        steps += 1
        return original(self, *args, **kwargs)
    torch.optim.AdamW.zero_grad = zero_grad
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always')
            torch.cuda.set_sync_debug_mode('warn')
            result = train(c)
            torch.cuda.set_sync_debug_mode('default')
        if active:
            prof.stop(); active = False
        trace = ROOT/f'{name}_trace.json'
        prof.export_chrome_trace(str(trace))
        (ROOT/f'{name}_sync_warnings.txt').write_text('\n'.join(f'{w.filename}:{w.lineno}: {w.message}' for w in captured)+'\n')
        (REPORT/f'{name}_profile_runtime.json').write_text(json.dumps(dict(result=result, trace=str(trace), warmup=100, profiled=100, uuid=os.environ['CUDA_VISIBLE_DEVICES']), indent=2)+'\n')
    finally:
        torch.cuda.set_sync_debug_mode('default')
        torch.optim.AdamW.zero_grad = original
        if active: prof.stop()


def numerical(name):
    from phychem_mfm.phase1.p_recipe_input import prepare_samples, reader_metadata
    from phychem_mfm.phase1.perf_sync_transfer import async_batches
    from phychem_mfm.model.perf_sync import finite_checks
    c = configuration()
    options = dict(c['step_overhead'], **variant_options(name))
    model, data, fields, families = ref.model_for(c, options)
    meta = reader_metadata(model['pd'], fields, sync_free=options['sync_free'], async_transfer=options['async_transfer'])
    noise_result = json.loads((REPORT/'S0_noise.json').read_text())
    el, eg = noise_result['epsilon_loss'], noise_result['epsilon_grad']
    rng = np.random.default_rng(0)
    choices = [ref.draw(data, rng, 32) for _ in range(20)]
    comparisons, rows, backend_ops = [], [], []
    try:
        for weights in ('random_seed0', 'B3_3M'):
            if weights == 'B3_3M':
                cp = torch.load(B3, map_location='cpu', weights_only=True)
                model.load_state_dict(cp['model']); del cp
            for batch, selected in enumerate(choices):
                base = torch.load(ROOT/'baseline_gradients'/weights/f'{batch:02d}.pt', weights_only=True)
                samples = prepare_samples([data.read(m, conf) for m, conf in selected], meta)
                transfer = None
                if options['async_transfer']:
                    transfer = async_batches(iter([(samples, {})]))
                    samples, _ = next(transfer)
                torch.set_rng_state(base['cpu_rng']); torch.cuda.set_rng_state(base['cuda_rng'])
                model.zero_grad(set_to_none=True)
                backend_profile = torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU]) if name == 'S3' and weights == 'random_seed0' and batch == 0 else None
                with backend_profile if backend_profile is not None else __import__('contextlib').nullcontext():
                    with finite_checks() if options['sync_free'] else __import__('contextlib').nullcontext():
                        total, loss = ref.calculate(model, samples, c, fields, families)
                        total.backward()
                if backend_profile is not None:
                    backend_ops = sorted({e.key for e in backend_profile.key_averages() if 'scaled_dot_product' in e.key})
                torch.cuda.synchronize()
                if transfer is not None: transfer.close()
                grad = torch.cat([p.grad.detach().flatten() if p.grad is not None else p.new_zeros(p.numel()) for p in model.parameters()]).cpu()
                values = {n: float(v.detach()) for n, v in loss.fields.items()}
                gd = float((grad.double()-base['gradient'].double()).norm()/base['gradient'].double().norm().clamp_min(1e-30))
                same_unused = [n for n,p in model.named_parameters() if p.grad is None] == base['unused']
                bitwise = torch.equal(grad,base['gradient']) and values == base['losses'] and same_unused
                passed = same_unused and gd <= 10*eg and all(abs(values[n]-base['losses'][n]) <= 10*el*(1+abs(base['losses'][n])) for n in values)
                comparisons.append(dict(weights=weights,batch=batch,bitwise=bitwise,grad_relative=gd,B_pass=passed))
                rows.extend(dict(weights=weights,batch=batch,field=n,baseline=base['losses'][n],variant=v,absolute_difference=abs(v-base['losses'][n])) for n,v in values.items())
                print('NUMERICAL',name,weights,batch,bitwise,passed,gd,flush=True)
        expects_A=name in ('S1','S5') or (name=='S8' and set(json.loads((REPORT/'combination.json').read_text())['items']).issubset({'S1','S5'}))
        category = 'A' if expects_A and all(r['bitwise'] for r in comparisons) else 'B'
        result = dict(item=name,category=category,A_pass=all(r['bitwise'] for r in comparisons),B_single_step_pass=all(r['B_pass'] for r in comparisons),
                      comparisons=comparisons,epsilon_loss=el,epsilon_grad=eg,options=options,SDPA_observed_operators=backend_ops)
        (REPORT/f'{name}_numerical.json').write_text(json.dumps(result,indent=2)+'\n')
        with (ROOT/f'{name}_field_deviations.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    finally: data.close()


def benchmark(name):
    from phychem_mfm.phase1.p_recipe_training import train
    c=configuration()
    selected=name.removesuffix('_repeat2')
    options=dict(c['step_overhead'], **variant_options(selected))
    specification=REPORT/'combination.json'
    if selected == 'S8' or selected.startswith('S7_'):
        options.update(json.loads(specification.read_text())['options'])
    if selected.startswith('S7_'):
        _,cores,readers=selected.split('_')
        allowed=sorted(os.sched_getaffinity(0))
        if int(cores)>min(len(allowed),int(os.environ['SLURM_CPUS_PER_TASK'])):raise RuntimeError('CPU scan cannot exceed actual allocation')
        os.sched_setaffinity(0,allowed[:int(cores)])
        c['workers']=int(readers)
    c.update(run=f'perf_sync_{name}_20261118',output=str(ROOT/f'{name}_training'),
             step_overhead=options,benchmark_updates=1000,benchmark_warmup_batches=100)
    stopped=threading.Event(); telemetry=[]
    def capture():
        while not stopped.is_set():
            row=subprocess.check_output(['nvidia-smi','-i',os.environ['CUDA_VISIBLE_DEVICES'],'--query-gpu=power.draw,utilization.gpu','--format=csv,noheader,nounits'],text=True)
            telemetry.append([time.time(),*map(float,row.strip().split(','))]);stopped.wait(1)
    monitor=threading.Thread(target=capture,daemon=True);monitor.start()
    from torch._dynamo.utils import counters, guard_failures, compile_times, get_compilation_metrics, clear_compilation_metrics, set_compilation_metrics_limit
    from torch._guards import CompileId
    counters.clear()
    guard_failures.clear()
    clear_compilation_metrics();set_compilation_metrics_limit(10000)
    from phychem_mfm.phase1 import perf_sync_step
    original_optimizer=perf_sync_step.make_optimizer
    optimizer_observation={}
    warm_guard_count=0
    warm_compile_ids=set()
    def observe_optimizer(parameters, configuration):
        optimizer=original_optimizer(parameters, configuration)
        optimizer_observation.update(backend=getattr(optimizer,'perf_sync_backend','default'),
            param_groups=[dict(fused=g.get('fused'),foreach=g.get('foreach')) for g in optimizer.param_groups])
        zero=optimizer.zero_grad;calls=0
        def counted_zero(*args,**kwargs):
            nonlocal calls,warm_guard_count,warm_compile_ids
            calls+=1
            if calls==c['benchmark_warmup_batches']+2:
                warm_guard_count=sum(len(reasons) for reasons in guard_failures.values())
                warm_compile_ids={m.compile_id for m in get_compilation_metrics()}
            return zero(*args,**kwargs)
        optimizer.zero_grad=counted_zero
        return optimizer
    perf_sync_step.make_optimizer=observe_optimizer
    try: result=train(c)
    finally:
        perf_sync_step.make_optimizer=original_optimizer
        stopped.set();monitor.join(timeout=5)
    measured=[r for r in telemetry if result['measure_wall_start']<=r[0]<=result['measure_wall_end']]
    losses=list(csv.DictReader((ROOT/f'{name}_training/losses.csv').open()))
    last=[float(r['total']) for r in losses[-200:]]
    result.update(item=name,options=options,power_W=float(np.mean([r[1] for r in measured])),
                  last200_mean=float(np.mean(last)),finite=bool(np.isfinite([float(r['total']) for r in losses]).all()),
                  warmup='100 forward/backward passes on first batch, no optimizer updates, RNG restored',actual_optimizer_updates=1000)
    result['compile_counters']={group:dict(values) for group,values in counters.items()}
    metrics=get_compilation_metrics()
    recompile_ids={m.compile_id for m in metrics if m.compile_id is not None
        and (CompileId.from_string(m.compile_id).frame_compile_id or 0)>0}
    result['recompilations_total_including_warmup']=len(recompile_ids)
    result['recompilations']=len(recompile_ids-warm_compile_ids)
    result['guard_failure_diagnostics_in_measured_window']=sum(len(reasons) for reasons in guard_failures.values())-warm_guard_count
    result['compilation_metrics']=[dict(compile_id=m.compile_id,co_name=m.co_name,
        entire_frame_compile_time_s=m.entire_frame_compile_time_s,backend_compile_time_s=m.backend_compile_time_s,
        inductor_compile_time_s=m.inductor_compile_time_s,fail_type=m.fail_type) for m in metrics]
    result['optimizer_execution']=optimizer_observation
    result['compiler_timing_table']=compile_times()
    (REPORT/f'{name}_benchmark.json').write_text(json.dumps(result,indent=2)+'\n')
    with (ROOT/f'{name}_gpu.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['unix_seconds','power_W','utilization_percent']);writer.writerows(telemetry)


def suite():
    # The allocation stays alive across all stages. An unexpected failure pauses
    # this coordinator for diagnosis instead of releasing/reacquiring the card.
    stages=['benchmark_baseline']
    for name in VARIANTS:
        stages.extend(['numerical_'+name,'benchmark_'+name])
        if name == 'S1': stages.append('profile_S1')
    for stage in stages:
        if (REPORT/f'{stage}_complete.json').exists(): continue
        code=subprocess.call([sys.executable,'-B','-u',__file__,stage])
        if code:
            (REPORT/'NEEDS_DIAGNOSIS.json').write_text(json.dumps(dict(stage=stage,returncode=code,time=time.time()))+'\n')
            return
    (REPORT/'S1_S5_execution_complete.json').write_text(json.dumps(dict(time=time.time(),note='Await profile analysis, S6 condition, S7 and S8; not final acceptance'))+'\n')


def analyze_profiles():
    for name in ('S0','S1','S8'):
        source=REPORT/f'{name}_profile_runtime.json'
        if not source.exists(): continue
        if (REPORT/f'{name}_profile_summary.json').exists(): continue
        runtime=json.loads(source.read_text())
        events=json.loads(Path(runtime['trace']).read_text())['traceEvents']
        kernels=[e for e in events if e.get('cat')=='kernel' and e.get('ph')=='X']
        copies=[e for e in events if e.get('cat')=='gpu_memcpy' and e.get('ph')=='X']
        intervals=sorted((e['ts'],e['ts']+e['dur']) for e in kernels+copies)
        busy=0.;right=float('-inf')
        for start,end in intervals:
            busy+=max(0.,end-max(start,right));right=max(right,end)
        api=[e for e in events if e.get('cat')=='cuda_runtime' and e.get('ph')=='X']
        sync=[e for e in api if 'Synchronize' in e.get('name','')]
        launch=[e for e in api if 'LaunchKernel' in e.get('name','')]
        h2d=[e for e in copies if 'HtoD' in e.get('name','')]
        seconds=runtime['result']['measured_seconds']
        result=dict(profiled_steps=100,trace=runtime['trace'],GPU_busy_wall_ratio=busy/1e6/seconds,
                    kernels_per_step=len(kernels)/100,synchronizations_per_step=len(sync)/100,
                    host_kernel_launch_seconds_per_step=sum(e['dur'] for e in launch)/1e6/100,
                    H2D_copies_per_step=len(h2d)/100,H2D_bytes_per_step=sum(float(e.get('args',{}).get('bytes',0)) for e in h2d)/100,
                    synchronization_APIs={n:sum(e['name']==n for e in sync) for n in sorted({e['name'] for e in sync})},
                    note='Profiler overhead included; throughput acceptance uses separate unprofiled runs. During first200 updates, clip calibration intentionally retains CPU norm synchronization.')
        warnings_file=ROOT/f'{name}_sync_warnings.txt'
        if warnings_file.exists():
            locations={}
            for line in warnings_file.read_text().splitlines(): locations[line]=locations.get(line,0)+1
            result['sync_warning_locations']=locations
        (REPORT/f'{name}_profile_summary.json').write_text(json.dumps(result,indent=2)+'\n')
        print('PROFILE_SUMMARY',name,json.dumps(result),flush=True)


def finish_suite():
    # Only executed after the original single-allocation S1-S5 queue closes.
    baseline_path=REPORT/'baseline_benchmark.json'
    if not baseline_path.exists() or not (REPORT/'S1_S5_execution_complete.json').exists():
        print('WAIT_FOR_DIAGNOSIS: original suite incomplete',flush=True);return
    base=json.loads(baseline_path.read_text())
    assessments=[]
    for name in VARIANTS:
        numeric=json.loads((REPORT/f'{name}_numerical.json').read_text())
        run=json.loads((REPORT/f'{name}_benchmark.json').read_text())
        tested_name=name
        if name.startswith('S4') and run.get('recompilations',0)>20:
            tested_name=name+'_dynamic'
            for stage in ('numerical_'+tested_name,'benchmark_'+tested_name):
                if not (REPORT/f'{stage}_complete.json').exists():
                    if subprocess.call([sys.executable,'-B','-u',__file__,stage]):
                        (REPORT/'NEEDS_DIAGNOSIS.json').write_text(json.dumps(dict(stage=stage))+'\n');return
            numeric=json.loads((REPORT/f'{tested_name}_numerical.json').read_text())
            run=json.loads((REPORT/f'{tested_name}_benchmark.json').read_text())
        speed=run['samples_per_second']/base['samples_per_second']
        rates=[run['samples_per_second']]
        repeated_quality=True
        if speed<1.03:
            stage=f'benchmark_{tested_name}_repeat2'
            if not (REPORT/f'{stage}_complete.json').exists():
                if subprocess.call([sys.executable,'-B','-u',__file__,stage]):
                    (REPORT/'NEEDS_DIAGNOSIS.json').write_text(json.dumps(dict(stage=stage))+'\n');return
            repeated=json.loads((REPORT/f'{tested_name}_repeat2_benchmark.json').read_text())
            rates.append(repeated['samples_per_second'])
            repeated_quality=repeated['finite'] and abs(repeated['last200_mean']-base['last200_mean'])<=.01+.03*base['last200_mean']
        mean_speed=float(np.mean(rates))/base['samples_per_second']
        short_pass=repeated_quality and run['finite'] and base['finite'] and abs(run['last200_mean']-base['last200_mean'])<=.01+.03*base['last200_mean']
        accepted=numeric['A_pass'] if numeric['category']=='A' else numeric['B_single_step_pass'] and short_pass
        if name.startswith('S4') and run.get('recompilations',0)>20:accepted=False
        # S1's A path also needs log equality; timestamps are run-dependent.
        log_equal=None
        if name in ('S1','S5'):
            def logs(item):
                with (ROOT/f'{item}_training/losses.csv').open() as f:
                    return [{k:v for k,v in r.items() if k!='seconds'} for r in csv.DictReader(f)]
            log_equal=logs(name)==logs('baseline')
            if numeric['category']=='A' and not log_equal:
                numeric['category']='B';accepted=numeric['B_single_step_pass'] and short_pass
        assessments.append(dict(item=name,tested_variant=tested_name,category=numeric['category'],accepted=accepted,log_equal=log_equal,
             short_training_pass=short_pass,speedup=mean_speed,repetitions=len(rates),effective=accepted and mean_speed>=1.05,
             last200_mean=run['last200_mean'],recompilations=run.get('recompilations'),single_card_only=True))
    selected=[a for a in assessments if a['effective']]
    compile_arms=[a for a in selected if a['item'].startswith('S4')]
    if len(compile_arms)>1:
        winner=max(compile_arms,key=lambda a:a['speedup'])['item']
        selected=[a for a in selected if not a['item'].startswith('S4') or a['item']==winner]
    options={}
    for a in selected: options.update(variant_options(a['tested_variant']))
    (REPORT/'assessments.json').write_text(json.dumps(assessments,indent=2)+'\n')
    (REPORT/'combination.json').write_text(json.dumps(dict(items=[a['item'] for a in selected],options=options),indent=2)+'\n')
    # S6 is assessed from the S1 trace, never inferred from CPU utilization.
    analyze_profiles()
    s1=json.loads((REPORT/'S1_profile_summary.json').read_text())
    if s1['synchronizations_per_step']>0:
        (REPORT/'S6.json').write_text(json.dumps(dict(status='NOT_APPLICABLE',sync_per_step=s1['synchronizations_per_step']))+'\n')
    else:
        (REPORT/'NEEDS_DIAGNOSIS.json').write_text(json.dumps(dict(stage='S6_zero_sync_capture_required'))+'\n');return
    allocation=min(len(os.sched_getaffinity(0)),int(os.environ['SLURM_CPUS_PER_TASK']));scan=[]
    for cores in (4,8,16,24):
        for readers in (7,14,20):
            name=f'S7_{cores}_{readers}'
            if cores>allocation:
                scan.append(dict(cores=cores,readers=readers,status='PENDING_CPU_EXTENSION_CHECK'));continue
            stage='benchmark_'+name
            if not (REPORT/f'{stage}_complete.json').exists():
                if subprocess.call([sys.executable,'-B','-u',__file__,stage]):
                    (REPORT/'NEEDS_DIAGNOSIS.json').write_text(json.dumps(dict(stage=stage))+'\n');return
            r=json.loads((REPORT/f'{name}_benchmark.json').read_text())
            scan.append(dict(cores=cores,readers=readers,status='COMPLETE',samples_per_second=r['samples_per_second'],power_W=r['power_W'],main_CPU_percent=r['main_CPU_percent'],GPU_peak_bytes=r['GPU_peak_bytes']))
    (REPORT/'S7.json').write_text(json.dumps(scan,indent=2)+'\n')
    if not selected:
        (REPORT/'S8.json').write_text(json.dumps(dict(status='NO_EFFECTIVE_FLAGS',speedup=None,items=[]))+'\n')
    else:
        for stage in ('numerical_S8','benchmark_S8','profile_S8'):
            if not (REPORT/f'{stage}_complete.json').exists():
                if subprocess.call([sys.executable,'-B','-u',__file__,stage]):
                    (REPORT/'NEEDS_DIAGNOSIS.json').write_text(json.dumps(dict(stage=stage))+'\n');return
        analyze_profiles()
        numeric=json.loads((REPORT/'S8_numerical.json').read_text())
        run=json.loads((REPORT/'S8_benchmark.json').read_text())
        short_pass=run['finite'] and abs(run['last200_mean']-base['last200_mean'])<=.01+.03*base['last200_mean']
        accepted=numeric['A_pass'] if numeric['category']=='A' else numeric['B_single_step_pass'] and short_pass
        (REPORT/'S8.json').write_text(json.dumps(dict(status='PASS' if accepted else 'FAIL',category=numeric['category'],speedup=run['samples_per_second']/base['samples_per_second'],items=[a['item'] for a in selected]),indent=2)+'\n')


def scan24():
    # Supplementary CPU allocation, using the original continuously held UUID
    # reservation after its GPU stages have ended. No second GPU is acquired.
    owner=os.environ['PERF_SYNC_OWNER_JOB']
    observed=subprocess.check_output(['squeue','-h','-j',owner,'-o','%T'],text=True).strip()
    if observed!='RUNNING':raise RuntimeError('Original GPU reservation must remain live')
    if min(len(os.sched_getaffinity(0)),int(os.environ['SLURM_CPUS_PER_TASK']))<24:raise RuntimeError('Real 24-CPU allocation required')
    scan=json.loads((REPORT/'S7.json').read_text())
    for readers in (7,14,20):
        name=f'S7_24_{readers}';stage='benchmark_'+name
        if not (REPORT/f'{stage}_complete.json').exists():
            if subprocess.call([sys.executable,'-B','-u',__file__,stage]):raise RuntimeError(stage+' failed; retain output')
        r=json.loads((REPORT/f'{name}_benchmark.json').read_text())
        scan=[row for row in scan if not (row['cores']==24 and row['readers']==readers)]
        scan.append(dict(cores=24,readers=readers,status='COMPLETE',samples_per_second=r['samples_per_second'],power_W=r['power_W'],main_CPU_percent=r['main_CPU_percent'],GPU_peak_bytes=r['GPU_peak_bytes']))
        (REPORT/'S7.json').write_text(json.dumps(sorted(scan,key=lambda row:(row['cores'],row['readers'])),indent=2)+'\n')


def main():
    def terminated(signum, frame): raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM, terminated)
    p = argparse.ArgumentParser()
    p.add_argument('stage')
    p.add_argument('--child', action='store_true')
    args = p.parse_args()
    if not args.child:
        capacity()
        started=time.monotonic()
        process = subprocess.Popen([sys.executable, '-B', '-u', __file__, args.stage, '--child'], start_new_session=True)
        try:
            while process.poll() is None:
                capacity()
                sys.path.insert(0, str(REPO.parent/'MFM_p_recipe/tools/model_v3'))
                import v2_diagnosis_disk as disk
                disk.m.require_capacity(disk.m.filesystem_status('/dev/shm'), 2*1024**3, 10000)
                if args.stage not in ('suite','finish_suite','scan24') and time.monotonic()-started>4*3600:
                    (REPORT/f'{args.stage}_unresolved.json').write_text(json.dumps(dict(status='UNRESOLVED',reason='4h individual-stage timebox'))+'\n')
                    raise TimeoutError('Individual-stage timebox exceeded; retain output')
                time.sleep(5)
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait()
            raise
        if process.returncode: raise RuntimeError(f'{args.stage} child exited {process.returncode}; retain output')
        return
    if not torch.cuda.is_available(): raise RuntimeError('Actual GPU required')
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    capacity()
    ROOT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    marker = REPORT/f'{args.stage}_complete.json'
    if marker.exists(): raise RuntimeError('Completed GPU stage must not be repeated')
    if args.stage.startswith('analyze_'): analyze_profiles()
    elif args.stage.startswith('profile_'): profile(args.stage.removeprefix('profile_'))
    elif args.stage.startswith('numerical_'): numerical(args.stage.removeprefix('numerical_'))
    elif args.stage.startswith('benchmark_'): benchmark(args.stage.removeprefix('benchmark_'))
    else: globals()[args.stage]()
    marker.write_text(json.dumps(dict(completed=time.time(), job=os.environ['SLURM_JOB_ID']))+'\n')


if __name__ == '__main__': main()
