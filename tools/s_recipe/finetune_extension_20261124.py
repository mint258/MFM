"""S-authorized fullFT, reusing the P entry and optimizer/selection unchanged.

Only resource admission, deadlines and lifecycle are S-owned adapters. The
runtime config's authority identifies the reused P scientific protocol; its
invoking_authority records the independent S user authorization.
"""
import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import socket
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import lifecycle_20261122 as life
from storage_20261122 import ROOT, REPO, CONTROL, write
from storage_line_20261122 import admit

AUTHORITY = 'docs/s_recipe/USER_DIRECTIVE_20261123B.md'
PROTOCOL = 'docs/p_recipe/USER_DIRECTIVE_20261122B.md'
TASKS = ('qm9.U0_atom', 'qm9.homo', 'exp.LogD', 'exp.LogS')


def validate(c):
    if (c.get('invoking_authority') != AUTHORITY or c.get('authority') != PROTOCOL
            or c.get('kind') != 'F' or c.get('mode') != 'full'
            or c.get('ready') is not True or c.get('task') not in TASKS
            or type(c.get('seed')) is not int or c['seed'] not in (0, 1, 2)):
        raise ValueError('Explicit registered S fullFT authorization is required')
    if c.get('pretraining_seed') != 0 or c.get('internal_split_seed') != 20261112:
        raise ValueError('Only frozen seed0 sources and the original inner split')
    if c.get('bootstrap_seed') != 20261025:
        raise ValueError('Original paired molecular bootstrap seed is fixed')
    if (Path(c['output']).parent != CONTROL/'finetune_20261124'
            or not re.fullmatch(r'S_FT_[A-Za-z0-9_]+',c.get('run',''))
            or Path(c['output']).name != c['run']):
        raise ValueError('FullFT output must remain in its S-owned output root')
    source = c['source_binding']
    checkpoint = Path(source['checkpoint'])
    if (checkpoint.parent.parent != CONTROL/'training'
            or checkpoint.name != 'samples_'+str(source['samples'])+'.pt'
            or source.get('source_training_budget') not in (3000000, 9000000)):
        raise ValueError('Bind one original, registered complete S checkpoint')
    allowed = {(f'S_{arm}_s0_3M',3000000,3000000) for arm in ('B0','G1','N1','N2','R1','R2')}
    allowed.update((f'S_E1_k{k}_s0_3M',3000000,3000000) for k in (1,2,5))
    allowed.update((f'S_{arm}_s0_9M',9000000,9000000) for arm in ('B0','final','subset_T5','subset_T6'))
    allowed.update(('S_final_s0_9M',9000000,count) for count in (1000000,3000000,6000000))
    if ((source.get('run'),source['source_training_budget'],source['samples']) not in allowed
            or checkpoint.parent.name != source['run']):
        raise ValueError('Only the explicitly registered16 distinct source points may be fitted')
    if (c.get('output_mount') != '/share' or c.get('cleanup_seconds') != 900
            or c.get('peak_ram_bytes') != 64*1024**3 or c.get('cpus') != 16
            or c.get('minimum_free_gpu_mib') != 22000
            or c.get('work_unit_seconds') != 120):
        raise ValueError('Registered resource and safe-boundary contract changed')
    mixed=c.get('execution_backend')=='mixed_gpu_native_20261126'
    allowed={'compute-0-'+str(i) for i in ((20,22) if mixed else range(8))}
    if c['node'] not in allowed:
        raise ValueError('Use an ordinary0..7 GPU or explicitly registered mixed20/22 execution')
    return c


def query(argv, stop):
    if stop.requested:
        raise RuntimeError('No new metadata subprocess during closing')
    child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, stdin=subprocess.DEVNULL)
    saved = life.identity(child.pid)
    try:
        stdout, stderr = child.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        if saved is not None:
            life.terminate_once(saved)
        life.close_children(30)
        raise RuntimeError('Bounded observation failed; owned exit requires verification')
    if child.returncode:
        raise RuntimeError('Metadata observation failed: '+stderr)
    return stdout


def load_provider():
    path = ROOT/'MFM_p_recipe/tools/p_recipe/finetune_entry.py'
    spec = importlib.util.spec_from_file_location('s_reused_p_fullft_entry', path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(module)
    return module


def _run(path,native_context=None):
    c = validate(json.loads(Path(path).read_text()))
    if (socket.gethostname().split('.')[0] != c['node']
            or os.environ.get('CUDA_VISIBLE_DEVICES') != c['gpu_uuid']
            or (native_context is None and int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) < c['cpus'])):
        raise ValueError('Actual allocation must match the registered node/UUID/CPU')
    life.enable_subreaper()
    for provider_path, expected in c['providers_sha256'].items():
        if hashlib.sha256(Path(provider_path).read_bytes()).hexdigest() != expected:
            raise ValueError('Registered shared scientific provider changed before loading')
    provider = load_provider()
    # Reuse the P fitting/selection code with the original frozen S encoder,
    # probe and native-store implementation used by this line's formal R3.
    sys.path.insert(0,str(REPO/'current'))
    provider.native_query = query
    stop = SimpleNamespace(requested=False)
    # Reuse P's checked actual RUNNING job/UID/node/finite EndTime query. A
    # queue wait therefore never consumes this new fit's usable time limit.
    if native_context is None:
        provider.set_actual_deadline(c, stop)
        guard = life.Guard(float(os.environ['P_MANAGED_HARD_END']), 900)
        guard.deadline_basis = 'actual_scontrol_EndTime_via_reused_P_provider'
    else:
        from mixed_fullft_runtime_20261126 import native_guard,bind_native_main
        guard=native_guard(native_context,c)
        bind_native_main(provider,c['cpus'])
    guard.phase = 'optimizing'
    state_path = (CONTROL/(c['run']+'_guarded_'+os.environ['SLURM_JOB_ID']+'.json')
        if native_context is None else Path(native_context['native_record']))
    record = dict(run=c['run'], job_id=int(os.environ['SLURM_JOB_ID']) if native_context is None else None, node=c['node'],
        gpu_uuid=c['gpu_uuid'], producer=vars(life.identity(os.getpid())),
        started_at=time.time(), actual_deadline_epoch=guard.end_epoch,
        closing_reserve_seconds=900, protocol_provider='P finetune_entry.py + finetune.py',
        invoking_authority=AUTHORITY, status='PREPARING')
    if native_context is not None:
        record.update(native_handle=native_context['native_handle'],execution='native_gpu',
            standby_job_id=native_context['standby_job_id'],cpus_requested=c['cpus'],slurm_cpus_allocated=0)
        write(state_path,record)
    done = threading.Event()

    @contextlib.contextmanager
    def cooperative_stop():
        # Keep S Guard's real signal handlers. The shared loop receives its
        # own existing stop flag, set before the next complete update boundary.
        yield stop

    def actual_deadline(configuration, shared_stop):
        os.environ['P_MANAGED_HARD_END'] = str(guard.end_epoch)
        os.environ['P_MANAGED_STOP_NEW_UNITS_AT'] = str(guard.end_epoch-900)
        os.environ['P_MANAGED_UNIT_SECONDS'] = '120'

    def admission(configuration):
        validate(configuration)
        if c['source_binding']['bytes'] != Path(c['source_binding']['checkpoint']).stat().st_size:
            raise ValueError('Selected complete source checkpoint size changed')
        closure = json.loads(Path(c['source_binding']['producer_exit_evidence']).read_text())
        if not closure.get('owned_descendants_exited'):
            raise ValueError('Source pretraining producer has not closed its owned subtree')
        admit(c)
        return c['node']

    def observer():
        while not done.wait(30):
            try:
                admit(c)
                if native_context is not None:
                    from mixed_fullft_runtime_20261126 import observe_handoff
                    observe_handoff(native_context,c,guard)
            except Exception as error:
                record['observer_error'] = type(error).__name__+': '+str(error)
                guard.request('storage_observation_failed')
            if guard.stopping():
                stop.requested = True
                return

    observer_thread = threading.Thread(target=observer, daemon=False)
    with guard:
        try:
            provider.REPO = REPO
            provider.CooperativeStop = cooperative_stop
            provider.set_actual_deadline = actual_deadline
            provider.admission = admission
            provider.native_query = query
            if c.get('execution_backend')=='mixed_gpu_native_20261126':
                from mixed_fullft_runtime_20261126 import mixed_gpu_lock
                provider.gpu_lock_and_check=mixed_gpu_lock
            observer_thread.start()
            code = provider.main(str(path))
            if native_context is not None and code==0:
                summary_path=Path(c['output'])/'summary.json'
                summary=json.loads(summary_path.read_text())
                summary['native_execution']=dict(native_handle=native_context['native_handle'],
                    native_record=str(state_path),producer=record['producer'],node=c['node'],run=c['run'])
                write(summary_path,summary)
            record.update(status='COMPLETE' if code == 0 else 'CONTINUATION_REQUIRED', exit_code=code)
            return code
        except BaseException as error:
            record.update(status='FAILED', error=type(error).__name__+': '+str(error))
            raise
        finally:
            guard.phase = 'closing'
            done.set()
            if observer_thread.ident is not None:
                observer_thread.join()
            life.close_children(180)
            record['peak_RSS_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
            record['child_peak_RSS_bytes']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024
            torch=sys.modules.get('torch')
            if torch is not None and torch.cuda.is_initialized():
                try:
                    record['peak_cuda_allocated_bytes']=torch.cuda.max_memory_allocated()
                    record['peak_cuda_reserved_bytes']=torch.cuda.max_memory_reserved()
                except Exception as error:
                    record['memory_observation_error']=type(error).__name__+': '+str(error)
            record.update(ended_at=time.time(), owned_descendants_exited=True,
                          observer_joined=not observer_thread.is_alive())
            write(state_path, record)


def run(path,native_context=None):
    c = validate(json.loads(Path(path).read_text()))
    with (CONTROL/(c['run']+'_fullFT.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run(path,native_context=native_context)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--configuration', required=True)
    raise SystemExit(run(p.parse_args().configuration))
