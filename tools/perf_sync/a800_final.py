"""One paid allocation: bounded A800 screens and paired batch-size timings."""
import argparse
import csv
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time

HOME = Path('/share/home/202264640132')
ROOT = HOME/'perf_A800_20261120'
REPO = Path(__file__).resolve().parents[2]
BASE_OPTIONS = dict(grouped_fields=True, head_checkpointing=False,
                    distance_tiling=True, prepared_input=True, sync_free=False,
                    fused_optimizer=False, sdpa=False, compile='none',
                    async_transfer=False, cuda_graphs=False)
VARIANTS = dict(baseline={}, S1=dict(sync_free=True), S2=dict(fused_optimizer=True),
                S3=dict(sdpa=True), S5=dict(async_transfer=True),
                S4_encoder=dict(compile='encoder'),
                S4_encoder_heads=dict(compile='encoder_heads'),
                S8=dict(sync_free=True, fused_optimizer=True, async_transfer=True))

# Spawn readers import this file as __mp_main__; install before their initializer.
if os.environ.get('A800_PORTABLE_READER') == '1':
    from a800_portable import install
    install()


def publish(path, value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    temporary.replace(path)


def capacity():
    if os.getuid() != 67109 or socket.gethostname().startswith('login'):
        raise RuntimeError('School compute node and expected UID required')
    root = os.statvfs('/')
    if root.f_bavail*root.f_frsize < max(10*1024**3, root.f_blocks*root.f_frsize//10):
        raise OSError('Root filesystem reserve')
    disk = os.statvfs(ROOT)
    if disk.f_bavail*disk.f_frsize < 220_000_000_000 or disk.f_favail < 100000:
        raise OSError('Shared filesystem bytes/inodes reserve')
    raw = subprocess.check_output(['/usr/lpp/mmfs/bin/mmlsquota', '-Y', '-u', '67109',
                                   '--block-size', '1K', 'dssgdev'], text=True, timeout=10)
    header = None
    quota = None
    for line in raw.splitlines():
        cells = line.split(':')
        if len(cells)>4 and cells[0]=='mmlsquota' and cells[2]=='HEADER':
            header = cells
        elif header and cells[0]=='mmlsquota':
            row = dict(zip(header, cells))
            if row.get('id')=='67109' and row.get('filesystemName')=='dssgdev':
                quota = row
    if quota is None:
        raise OSError('Actual UID quota unavailable')
    limits = [int(quota[k])*1024 for k in ('blockQuota','blockLimit') if int(quota[k])>0]
    available = min(limits)-(int(quota['blockUsage'])+int(quota['blockInDoubt']))*1024
    if available < 220_000_000_000:
        raise OSError('Account quota and concurrent reserve')
    allocated = sum(p.stat().st_blocks*512 for p in ROOT.rglob('*') if p.is_file())
    if allocated > 8*1024**3:
        raise OSError('Owned source, caches and output exceeded8GiB')
    return dict(node=socket.gethostname(), available_quota_bytes=available,
                shared_free_bytes=disk.f_bavail*disk.f_frsize, shared_free_inodes=disk.f_favail,
                root_free_bytes=root.f_bavail*root.f_frsize)


def foreign_contexts(uuid, owned_group=None):
    raw = subprocess.check_output(['nvidia-smi','-i',uuid,'--query-compute-apps=pid',
                                   '--format=csv,noheader,nounits'], text=True, timeout=10)
    foreign = []
    for line in raw.splitlines():
        if not line.strip().isdigit():
            continue
        pid = int(line)
        try:
            if owned_group is None or os.getpgid(pid) != owned_group:
                foreign.append(pid)
        except ProcessLookupError:
            pass
    return foreign


def terminate(process):
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
    except ProcessLookupError:
        process.wait()


def child(batch, variant, destination):
    import numpy as np
    import torch
    from torch._dynamo.utils import counters
    from phychem_mfm.phase1.p_recipe_training import train
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision('highest')
    counters.clear()
    configuration = json.loads((REPO/'configs/perf_sync/M2_5090.json').read_text())
    configuration.update(root=str(HOME/'descriptor_analysis_migration_20261115/data/training_lmdb'),
        compressed_lmdb=True, workers=7, seed=0, precision='fp32', batch_size=batch,
        microbatch_size=batch, activation_checkpointing=False,
        label_parameters=str(HOME/'descriptor_analysis_migration_20261115/models/label_parameters/PM7_A1.json'),
        run='a800_'+destination.name, output=str(destination/'training'),
        benchmark_updates=100, benchmark_warmup_batches=25,
        checkpoint_samples=[], step_overhead=dict(BASE_OPTIONS, **VARIANTS[variant]))
    telemetry = []
    errors = []
    stopped = threading.Event()
    def capture():
        while not stopped.is_set():
            try:
                raw = subprocess.check_output(['nvidia-smi','-i',os.environ['CUDA_VISIBLE_DEVICES'],
                    '--query-gpu=power.draw,utilization.gpu','--format=csv,noheader,nounits'],
                    text=True, timeout=8)
                telemetry.append([time.time(), *map(float, raw.strip().split(','))])
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                errors.append(str(error))
            stopped.wait(1)
    thread = threading.Thread(target=capture, daemon=True)
    thread.start()
    try:
        result = train(configuration)
    finally:
        stopped.set()
        thread.join(timeout=10)
    with (destination/'training/losses.csv').open() as stream:
        losses = list(csv.DictReader(stream))
    finite = len(losses)==100 and all(np.isfinite(float(r['total'])) and
                                     np.isfinite(float(r['preclip_norm'])) for r in losses)
    measured = [r for r in telemetry if result['measure_wall_start']<=r[0]<=result['measure_wall_end']]
    if result['measured_updates'] != 100 or not finite or not measured:
        raise RuntimeError('Incomplete updates, nonfinite trajectory, or missing timed telemetry')
    with (destination/'telemetry.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['unix_seconds','power_W','GPU_percent'])
        writer.writerows(telemetry)
    result.update(variant=variant, options=configuration['step_overhead'],
        uuid=os.environ['CUDA_VISIBLE_DEVICES'], gpu=torch.cuda.get_device_name(),
        torch=torch.__version__, cuda=torch.version.cuda, node=socket.gethostname(),
        readers=7, cpu_affinity=sorted(os.sched_getaffinity(0)),
        actual_optimizer_updates=100, no_update_warmup_batches=25, finite=finite,
        power_W=float(np.mean([r[1] for r in measured])),
        GPU_utilization_percent=float(np.mean([r[2] for r in measured])),
        telemetry_errors=errors, precision=dict(matmul_allow_tf32=torch.backends.cuda.matmul.allow_tf32,
            cudnn_allow_tf32=torch.backends.cudnn.allow_tf32, matmul_precision=torch.get_float32_matmul_precision()),
        dynamo_counters={str(group):dict(values) for group,values in counters.items()},
        last20_mean_loss=float(np.mean([float(r['total']) for r in losses[-20:]])))
    publish(destination/'benchmark.json', result)


def controller():
    if int(os.environ.get('SLURM_CPUS_PER_TASK','0')) != 9 or not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Exactly9 allocated CPUs and one real GPU job required')
    os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:9])
    admission = capacity()
    for name in ('tmp','cache','inductor','triton'):
        (ROOT/name).mkdir(exist_ok=True)
    output = ROOT/('job_'+os.environ['SLURM_JOB_ID'])
    output.mkdir(exist_ok=False)
    started = time.time()
    deadline = time.monotonic()+3450
    uuid = subprocess.check_output([sys.executable,'-B',str(HOME/'precision_20261115/source/tools/model_v3/precision_allocated_gpu.py')], text=True).strip()
    os.environ['CUDA_VISIBLE_DEVICES'] = uuid
    environment = dict(os.environ, A800_PORTABLE_READER='1', WANDB_MODE='offline')
    report = dict(status='RUNNING',job_id=os.environ['SLURM_JOB_ID'],uuid=uuid,
        cpus=9,readers=7,allocated_gpu_count=1,time_limit_seconds=3600,
        started_unix=started,source_revision='ab14ec97640cba6e04d5bcdb667ea6ed074043d9+20261120_A800_harness',
        admission=admission,cells=[],abba={},screens={},
        protocol='25 no-update warmup passes (RNG restored),100 timed actual updates per cell;FP32/TF32off;no backbone recomputation at every BS',
        quality='Speed experiment only; no new1000-update/two-seed quality qualification')
    def save():
        publish(output/'results.json', report)
    def run(name, batch, variant, limit=210):
        if time.monotonic()+limit > deadline:
            row=dict(name=name,batch_size=batch,variant=variant,status='NOT_RUN_TIME_BUDGET')
            report['cells'].append(row);save();return None
        capacity()
        foreign=foreign_contexts(uuid)
        if foreign:
            raise RuntimeError('Foreign contexts before cell: '+str(foreign))
        destination=output/name
        destination.mkdir()
        command=[sys.executable,'-B','-u',__file__,'--child',str(batch),variant,str(destination)]
        print('CELL_START',name,flush=True)
        begin=time.monotonic()
        reason=None
        with (destination/'stdout.log').open('w') as log:
            process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
                                     env=environment,start_new_session=True)
            try:
                last_disk=begin
                while process.poll() is None:
                    foreign=foreign_contexts(uuid,process.pid)
                    if foreign:
                        raise RuntimeError('Foreign GPU context during measurement: '+str(foreign))
                    if time.monotonic()-begin > limit:
                        reason='TIMEOUT';terminate(process);break
                    if time.monotonic()-last_disk >= 20:
                        capacity();last_disk=time.monotonic()
                    time.sleep(2)
                foreign=foreign_contexts(uuid,process.pid)
                if foreign:
                    raise RuntimeError('Foreign GPU context at cell completion: '+str(foreign))
            except BaseException:
                terminate(process)
                raise
        row=dict(name=name,batch_size=batch,variant=variant,returncode=process.returncode,
                 wall_seconds=time.monotonic()-begin,status=reason or ('COMPLETE' if process.returncode==0 else 'FAILED'))
        if row['status']=='COMPLETE':
            row['measurement']=json.loads((destination/'benchmark.json').read_text())
        report['cells'].append(row);save()
        print('CELL_END',name,row['status'],flush=True)
        return row.get('measurement')
    save()
    try:
        # Full paired BS comparisons take priority over optional individual screens.
        for batch in (32,16,64,128):
            measurements=[]
            for position,variant in enumerate(('baseline','S8','S8','baseline')):
                result=run(f'B{batch}_ABBA_{position}_{variant}',batch,variant,
                           limit=210 if batch<=64 else 300)
                if result is None:
                    measurements=[];break
                measurements.append(result)
            if len(measurements)==4:
                from statistics_5090 import abba
                summary=abba([r['samples_per_second'] for r in measurements])
                summary['candidate_repeat_gap_samples_per_second']=abs(measurements[1]['samples_per_second']-measurements[2]['samples_per_second'])
                summary['quality_qualified']=False
                report['abba'][str(batch)]=summary;save()
        # Individual S1-S5 are bounded screens, explicitly separate from paired ABBA.
        reference=report['abba'].get('32',{}).get('baseline_mean')
        for variant in ('S1','S2','S3','S5','S4_encoder','S4_encoder_heads'):
            result=run('screen_B32_'+variant,32,variant,limit=180 if variant.startswith('S4') else 150)
            if result:
                report['screens'][variant]=dict(samples_per_second=result['samples_per_second'],
                    speedup_screen_only=result['samples_per_second']/reference if reference else None)
                save()
        report['status']='COMPLETE' if len(report['abba'])==4 else 'PARTIAL_TIME_OR_CELL_FAILURE'
    except BaseException as error:
        report.update(status='FAILED',error=repr(error))
        raise
    finally:
        report.update(ended_unix=time.time(),elapsed_seconds=time.time()-started)
        save()
        with (output/'cells.csv').open('w',newline='') as stream:
            columns=['name','batch_size','variant','status','returncode','wall_seconds','samples_per_second','main_CPU_percent','power_W','GPU_peak_bytes']
            writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
            for cell in report['cells']:
                row={k:cell.get(k) for k in columns}
                row.update({k:cell.get('measurement',{}).get(k) for k in columns[6:]})
                writer.writerow(row)
        print('FINAL_REPORT',output,report['status'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--child',nargs=3,metavar=('BS','VARIANT','OUTPUT'))
    args=parser.parse_args()
    if args.child:
        child(int(args.child[0]),args.child[1],Path(args.child[2]))
    else:
        controller()
