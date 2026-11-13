"""Taskbook step 1 only: idle-GPU profile and uninstrumented baseline."""
import argparse
import csv
import json
import importlib.util
import os
import signal
from pathlib import Path
import subprocess
import sys
import time

BASE = Path('/share/home/zixiao/descriptor_analysis')
REPO = BASE / 'MFM_model_v3_cpu_perf_20261112'
CHECKPOINT = Path('/lfshome/zixiao/model_v31_20261105/P_C1_0_seed0_micro32_continuation_20261110/samples_4000000.pt')
SCRATCH = Path('/lfshome/zixiao/model_v3_perf_20261112')
GPUS = os.environ.get('MFM_CPU_GPU_UUIDS', 'GPU-8bfd2ba3-f622-24a9-09cf-e30a88e90ad5,GPU-ec788ed1-7da1-8f93-bb23-b4fdb2018b02').split(',')


def query(*args):
    return subprocess.check_output(args, text=True).strip()


def capacity():
    from v2_watch_disk import filesystem_status, require_capacity
    require_capacity(filesystem_status('/'), 0)
    require_capacity(filesystem_status(SCRATCH), 4_000_000_000, 500)
    require_capacity(filesystem_status(REPO), 64 * 1024**2, 100)
    text = query('lfs', 'quota', '-u', str(os.getuid()), '/lfshome')
    # Lustre output uses KiB, including hard limit; zero quota is not unlimited.
    rows = [line.split() for line in text.splitlines() if line.strip().startswith('/lfshome')]
    if len(rows) != 1 or len(rows[0]) < 4:
        raise RuntimeError('Unknown account quota; no writes admitted')
    used, limit = int(rows[0][1].rstrip('*')), int(rows[0][3])
    control = BASE / 'runs/data_v1_20261025/control/window2_20261105'
    nfs = json.loads((control/'share_quota_available_v3.json').read_text())
    if (nfs['schema'] != 'XFS_USER_QUOTA_AVAILABLE_V1' or nfs['uid'] != os.getuid()
            or nfs['filesystem'] != '/share' or not 0 <= time.time()-nfs['observed_time'] <= 5):
        raise RuntimeError('Unknown or stale NFS quota; refusing writes')
    if nfs['available_bytes'] < 100_000_000_000 + 23_179_869_184 + 8*1024**3 + 64*1024**2:
        raise RuntimeError('Insufficient NFS quota after concurrent data-line forecast')
    # Debit already allocated files from each shared forecast exactly once.
    spec = importlib.util.spec_from_file_location('cpu_perf_model_budget', REPO/'tools/model_v3/v2_diagnosis_disk.py')
    guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
    model_allocated, model_remaining = guard.model_growth_forecast()
    other_remaining = guard.remaining_d6() + 6_000_000_000
    own_allocated = 0
    for path in SCRATCH.rglob('*') if SCRATCH.exists() else ():
        try:
            if path.is_file():
                own_allocated += path.stat().st_blocks*512
        except FileNotFoundError:
            # An atomic checkpoint rename may race metadata observation.
            # Skipping it over-reserves future bytes rather than under-reserving.
            continue
    own_remaining = max(0, 4_000_000_000-own_allocated)
    if own_remaining == 0:
        raise RuntimeError('Own 4GB physical forecast consumed; replan before new writes')
    required = 100_000_000_000 + model_remaining + other_remaining + own_remaining + 8*1024**3
    if limit <= 0 or (limit-used)*1024 < required:
        raise RuntimeError('Insufficient quota after actual concurrent remaining forecasts')
    return dict(available_bytes=(limit-used)*1024, required_bytes=required,
                mainline_allocated_bytes=model_allocated, mainline_remaining_forecast=model_remaining,
                own_allocated_bytes=own_allocated, own_remaining_forecast=own_remaining,
                other_remaining_forecast=other_remaining)

def idle_gpu():
    occupied = {line.split(',')[0].strip() for line in query('nvidia-smi',
        '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader').splitlines()}
    for gpu in GPUS:
        if gpu not in occupied:
            return gpu
    raise RuntimeError('No idle authorized GPU; leaving all existing processes untouched')


def measured_updates_available(path):
    """The first segment row is emitted only after all 100 warmup updates."""
    try:
        with Path(path).open(newline='') as file:
            return next(csv.DictReader(file), None) is not None
    except FileNotFoundError:
        return False


def train(mode, directory):
    if os.environ.get('MFM_CPU_COHORT_GATE'):
        from model_gpu_registry import register_current
        cores = [int(value) for value in os.environ['MFM_CPU_COHORT_CORES'].split(',')]
        if not set(cores) <= os.sched_getaffinity(0):
            raise RuntimeError('Requested cores are outside the actual Slurm affinity')
        os.sched_setaffinity(0, cores)
        identity = register_current(os.environ['CUDA_VISIBLE_DEVICES'], directory, benchmark=True)
        ready = directory.parent / (directory.name+'.registered.json')
        pending = ready.with_suffix('.pending')
        pending.write_text(json.dumps(identity)+'\n')
        pending.replace(ready)
        parent_pid = os.getppid()
        while not Path(os.environ['MFM_CPU_COHORT_GATE']).is_file():
            if os.getppid() != parent_pid:
                raise RuntimeError('Cohort parent exited before release')
            time.sleep(.05)
    import torch
    from phychem_mfm.phase1.v31_experiments import train_v31
    checkpoint = torch.load(CHECKPOINT, weights_only=True, map_location='cpu')
    configuration = dict(checkpoint['configuration'])
    assert configuration['condition'] == 'P' and configuration['distance_bias'] == 'C1-0'
    assert configuration['batch_size'] == configuration['microbatch_size'] == 32
    assert configuration['expected_molecules'] == 240000
    assert checkpoint['clock']['samples_consumed'] == 4000000
    cores = int(os.environ.get('SLURM_CPUS_PER_TASK', '16'))
    workers = int(os.environ['MFM_CPU_FIXED_WORKERS']) if os.environ.get('MFM_CPU_FIXED_WORKERS') else min(configuration['workers'], max(1, cores-2))
    configuration.update(output=str(directory), resume=str(CHECKPOINT), run_until_samples=None, workers=workers)
    os.environ['MFM_CPU_MEASURE_STEPS'] = '1100' if mode == 'profile' else '1000'
    if mode == 'profile':
        os.environ['MFM_CPU_PROFILE_DIR'] = str(directory.parent / 'segments')
    else:
        os.environ.pop('MFM_CPU_PROFILE_DIR', None)
    train_v31(configuration)


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child', choices=['profile', 'baseline'])
    parser.add_argument('--directory', type=Path)
    args = parser.parse_args()
    if args.child:
        train(args.child, args.directory)
        return
    quota = capacity()
    gpu = idle_gpu()
    lock = BASE / 'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks' / (gpu + '.lock')
    import fcntl
    with lock.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if idle_gpu() != gpu:
            raise RuntimeError('GPU availability changed')
        root = SCRATCH / (os.environ.get('MFM_CPU_RUN_PREFIX', 'step1') + '_' + os.environ['SLURM_JOB_ID'])
        root.mkdir(parents=True, exist_ok=False)
        (root / 'admission.json').write_text(json.dumps(dict(gpu=gpu, gpu_name=query('nvidia-smi','-i',gpu,'--query-gpu=name','--format=csv,noheader'), cores=int(os.environ['SLURM_CPUS_PER_TASK']), workers=min(14,max(1,int(os.environ['SLURM_CPUS_PER_TASK'])-2)), quota=quota, checkpoint=str(CHECKPOINT)), indent=2))
        temporary = root / 'tmp'
        temporary.mkdir()
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu, TMPDIR=str(temporary))
        # Prepared in isolated scratch before requesting a GPU, not in a shared environment.
        spy = SCRATCH / 'sampler_tools_v1/bin/py-spy'
        if not spy.is_file():
            raise RuntimeError('Prepare the isolated native sampler before requesting a GPU')
        modes = ('baseline',) if os.environ.get('MFM_CPU_BASELINE_ONLY') == '1' else ('profile', 'baseline')
        for mode in modes:
            capacity()
            if idle_gpu() != gpu:
                raise RuntimeError('Selected GPU is no longer idle; controlled card must stay fixed')
            directory = root / mode
            command = [sys.executable, '-u', str(Path(__file__).absolute()), '--child', mode,
                       '--directory', str(directory)]
            telemetry = root / (mode + '_telemetry.csv')
            with (root / (mode + '.log')).open('x') as log, telemetry.open('x', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['unix_time', 'main_cpu_percent', 'gpu_power_watts', 'gpu_memory_MiB', 'training_started', 'losses_bytes'])
                child = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                sampler = None
                previous_cpu, previous_time = None, None
                training_started = False
                try:
                    while child.poll() is None:
                        capacity()  # real byte/inode/quota protection while writes grow
                        occupied = query('nvidia-smi', '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader')
                        for line in occupied.splitlines():
                            parts = [s.strip() for s in line.split(',')]
                            if parts[0] == gpu and int(parts[1]) != child.pid:
                                raise RuntimeError('External GPU process appeared; stopping own measurement')
                        now = time.monotonic()
                        if mode == 'profile' and sampler is None and measured_updates_available(root/'segments/segments.csv'):
                            sampler = subprocess.Popen([str(spy), 'record', '--native', '-d', '120',
                                '--pid', str(child.pid), '-o', str(root/'flame.svg')], env=env,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                        try:
                            stat = Path(f'/proc/{child.pid}/stat').read_text().rsplit(')', 1)[1].split()
                            cpu = (int(stat[11]) + int(stat[12])) / os.sysconf('SC_CLK_TCK')
                            percent = '' if previous_cpu is None else 100*(cpu-previous_cpu)/(now-previous_time)
                            previous_cpu, previous_time = cpu, now
                            power, memory = query('nvidia-smi', '-i', gpu, '--query-gpu=power.draw,memory.used',
                                                  '--format=csv,noheader,nounits').split(',')
                            losses_path = directory/'losses.csv'
                            if not training_started:
                                training_started = measured_updates_available(losses_path)
                            losses_bytes = losses_path.stat().st_size if losses_path.is_file() else 0
                            writer.writerow([time.time(), percent, power.strip(), memory.strip(), int(training_started), losses_bytes])
                            file.flush()
                        except FileNotFoundError:
                            if child.poll() is None:
                                raise
                        time.sleep(1)
                    if child.returncode:
                        raise RuntimeError(f'{mode} child exit {child.returncode}; inspect {root}')
                    if mode == 'profile' and (sampler is None or sampler.wait() != 0):
                        raise RuntimeError('Native flame sampling failed; inspect retained artifacts')
                finally:
                    if child.poll() is None:
                        os.killpg(child.pid, signal.SIGTERM)
                        try:
                            child.wait(timeout=30)
                        except subprocess.TimeoutExpired:
                            os.killpg(child.pid, signal.SIGKILL)
                            child.wait()
                    if sampler is not None and sampler.poll() is None:
                        sampler.terminate()
                        sampler.wait()
        (root/'STEP1_COMPLETE.json').write_text(json.dumps(dict(status='MEASUREMENTS_ONLY',
            next='Inspect segment shares and flame before selecting at most two optimizations'))+'\n')
        print(root, flush=True)


if __name__ == '__main__':
    run()
