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
    if name == 'S1': c['step_overhead'].update(VARIANTS['S1'])
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
    options = dict(c['step_overhead'], **VARIANTS[name])
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
        category = 'A' if name in ('S1','S5') and all(r['bitwise'] for r in comparisons) else 'B'
        result = dict(item=name,category=category,A_pass=all(r['bitwise'] for r in comparisons),B_single_step_pass=all(r['B_pass'] for r in comparisons),
                      comparisons=comparisons,epsilon_loss=el,epsilon_grad=eg,options=options,SDPA_observed_operators=backend_ops)
        (REPORT/f'{name}_numerical.json').write_text(json.dumps(result,indent=2)+'\n')
        with (ROOT/f'{name}_field_deviations.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    finally: data.close()


def benchmark(name):
    from phychem_mfm.phase1.p_recipe_training import train
    c=configuration()
    options=dict(c['step_overhead'], **VARIANTS.get(name,{}))
    c.update(run=f'perf_sync_{name}_20261118',output=str(ROOT/f'{name}_training'),
             step_overhead=options,benchmark_updates=1000,benchmark_warmup_batches=100)
    stopped=threading.Event(); telemetry=[]
    def capture():
        while not stopped.is_set():
            row=subprocess.check_output(['nvidia-smi','-i',os.environ['CUDA_VISIBLE_DEVICES'],'--query-gpu=power.draw,utilization.gpu','--format=csv,noheader,nounits'],text=True)
            telemetry.append([time.time(),*map(float,row.strip().split(','))]);stopped.wait(1)
    monitor=threading.Thread(target=capture,daemon=True);monitor.start()
    from torch._dynamo.utils import counters
    counters.clear()
    try: result=train(c)
    finally: stopped.set();monitor.join(timeout=5)
    measured=[r for r in telemetry if result['measure_wall_start']<=r[0]<=result['measure_wall_end']]
    losses=list(csv.DictReader((ROOT/f'{name}_training/losses.csv').open()))
    last=[float(r['total']) for r in losses[-200:]]
    result.update(item=name,options=options,power_W=float(np.mean([r[1] for r in measured])),
                  last200_mean=float(np.mean(last)),finite=bool(np.isfinite([float(r['total']) for r in losses]).all()),
                  warmup='100 forward/backward passes on first batch, no optimizer updates, RNG restored',actual_optimizer_updates=1000)
    result['compile_counters']={group:dict(values) for group,values in counters.items()}
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
    for name in ('S0','S1'):
        source=REPORT/f'{name}_profile_runtime.json'
        if not source.exists(): continue
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


def main():
    def terminated(signum, frame): raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM, terminated)
    p = argparse.ArgumentParser()
    p.add_argument('stage')
    p.add_argument('--child', action='store_true')
    args = p.parse_args()
    if not args.child:
        capacity()
        process = subprocess.Popen([sys.executable, '-B', '-u', __file__, args.stage, '--child'], start_new_session=True)
        try:
            while process.poll() is None:
                capacity()
                sys.path.insert(0, str(REPO.parent/'MFM_p_recipe/tools/model_v3'))
                import v2_diagnosis_disk as disk
                disk.m.require_capacity(disk.m.filesystem_status('/dev/shm'), 2*1024**3, 10000)
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
    if args.stage.startswith('profile_'): profile(args.stage.removeprefix('profile_'))
    elif args.stage.startswith('numerical_'): numerical(args.stage.removeprefix('numerical_'))
    elif args.stage.startswith('benchmark_'): benchmark(args.stage.removeprefix('benchmark_'))
    else: globals()[args.stage]()
    marker.write_text(json.dumps(dict(completed=time.time(), job=os.environ['SLURM_JOB_ID']))+'\n')


if __name__ == '__main__': main()
