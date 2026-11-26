"""Finite owned CPU execution under the user's Nov26 direct-SSH rule."""
import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import resource
import runpy
import shlex
import socket
import stat
import subprocess
import sys
import threading
import time

import lifecycle_20261122 as life
from storage_20261122 import CONTROL as C, REPO as R, write
from storage_line_20261122 import admit

AUTHORITY = 'docs/interfaces/SCHEDULING_RULE_20261126.md'


def worker(c):
    from cpu_execution_20261126 import execution_fields, native_record
    native_record()
    if c['stage'] == 'budget_validation_curve':
        from budget_validation_curve_20261126 import run as report
        return report()
    if c['stage'] == 'budget_statistics':
        from budget_statistics_native_20261126 import run as statistics
        return statistics(c)
    if c['stage'] == 'fullft_statistics':
        from finetune_statistics_extension_20261124 import run as statistics
        return statistics(json.loads(Path(c['source_configuration']).read_text()))
    if c['stage'] == 'terminal':
        import readouts
        import s_statistics
        import snapshot_readouts_20261122 as snapshot
        import terminal_readouts_20261122 as terminal
        source = json.loads(Path(c['source_configuration']).read_text())
        source['node'] = c['node']
        terminal.registered(source, source['samples'])
        phase = terminal.closed_phase(Path(source['output'])/'readout/terminal_gpu_status.json', source)
        if phase['status'] != 'GPU_TERMINAL_COMPLETE_WAITING_CPU':
            raise ValueError('Original GPU phase must be complete and owned-exited')
        guard = life.Guard(float(os.environ['S_NATIVE_CPU_HARD_END']), c['cleanup_seconds'])
        life.enable_subreaper()
        with guard:
            try:
                guard.phase = 'native_original_statistics'
                with snapshot.evaluation_scope(readouts, guard), terminal.admitted_legacy_scope(s_statistics):
                    s_statistics.finalize(source, execution=execution_fields())
            finally:
                guard.phase = 'closing'
                life.close_children(180)
        return 0
    scripts = {'matrix':'prepare_matrix_only_20261125.py',
               'population':'prepare_extensions_and_register_20261125.py',
               'publish':'prepare_merge_publish_20261122.py',
               'import':'import_published_commit_20261122.py',
               'extension_progress':'report_extensions_startup_20261126.py',
               'extension_daily':'refresh_extension_daily_20261126.py',
               'generic_publish':'prepare_status_milestone_20261126.py',
               'writer_admission_check':'check_gpu_writer_admission_20261126.py',
               'budget_adapter_check':'check_budget_adapter_source_20261126.py',
               'native_output_check':'check_native_output_budget_20261126.py',
               'fullft_provider_inspection':'inspect_fullft_provider_pins_20261126.py',
               'mixed_fullft_check':'check_mixed_fullft_runtime_20261126.py',
               'mixed_fullft_binding_check':'check_mixed_fullft_binding_20261126.py',
               'fullft_resume_check':'check_fullft_resume_20261126.py',
               'execution_delivery':'deliver_execution_adapters_20261126.py',
               'readout_runtime_check':'check_readout_runtime_20261126.py',
               'readout_delivery':'deliver_readout_adapters_20261126.py',
               'standby_settlement_check':'check_standby_settlement_20261126.py',
               'e1_frozen_report':'report_E1_frozen_components_20261126.py',
               'handoff_path_check':'check_handoff_path_20261127.py'}
    if c['stage'] not in scripts:
        raise ValueError('No unregistered CPU stage')
    if c['stage'] == 'population':
        import retire_diagnostic_scratch_20261124 as retirement
        original_query = retirement.query
        def scheduler_metadata(arguments,*args,**kwargs):
            if arguments[0] == '/usr/bin/sacct':
                return original_query(['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=5',
                    'sonmi',shlex.join(['/usr/bin/timeout','15s',*arguments])],*args,**kwargs)
            return original_query(arguments,*args,**kwargs)
        retirement.query = scheduler_metadata
    runpy.run_path(str(C/scripts[c['stage']]), run_name='__main__')
    return 0


def main(configuration, child=False):
    c = json.loads(Path(configuration).read_text())
    node = socket.gethostname().split('.')[0]
    directory = C/'native_cpu_20261126'/c['handle']
    if (c.get('authority') != AUTHORITY or node != c['node']
            or node not in {'compute-0-'+str(i) for i in range(8,20)}
            or os.getuid() != 1278 or os.environ.get('CUDA_VISIBLE_DEVICES') != ''
            or os.environ.get('SLURM_JOB_ID') or not 1 <= len(c['cores']) <= 16
            or set(os.sched_getaffinity(0)) != set(c['cores'])
            or Path(configuration) != directory/'configuration.json'):
        raise ValueError('Only the real bound owned native CPU execution may enter')
    if child:
        return worker(c)
    if not -5 <= time.time()-c['preflight']['observed_time'] <= 5:
        raise ValueError('Native launch requires its fresh five-second core observation')
    end = float(os.environ['S_NATIVE_CPU_HARD_END'])
    guard = life.Guard(end, c['cleanup_seconds'])
    life.enable_subreaper()
    started = time.time()
    record = dict(execution='native_cpu',handle=c['handle'],stage=c['stage'],job_id=None,
        node=node,cores=c['cores'],producer=vars(life.identity(os.getpid())),
        started_at=started,hard_end_epoch=end,cleanup_seconds=c['cleanup_seconds'],
        status='PREPARING',owned_descendants_exited=False,configuration=str(configuration))
    filename = directory/'record.json'
    child_process = None
    child_identity = None
    done = threading.Event()

    def observe():
        while not done.wait(30):
            try:
                admit(c)
            except Exception as error:
                record['observer_error'] = type(error).__name__+': '+str(error)
                guard.request('resource_observation_failed')

    observer = threading.Thread(target=observe, daemon=False)
    with contextlib.ExitStack() as core_leases, (directory/'owner.lock').open('a') as lock, guard:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # Coordinate with the P short-CPU runtime's existing UID/core leases.
        for core in c['cores']:
            fd=os.open('/tmp/P_CPU_SSH_1278_core'+str(core)+'.lock',
                       os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
            stream=core_leases.enter_context(os.fdopen(fd,'a'))
            observed=os.fstat(stream.fileno())
            if observed.st_uid!=os.getuid() or not stat.S_ISREG(observed.st_mode) or observed.st_nlink!=1:
                raise ValueError('CPU core lease must be a single owned regular file')
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if filename.exists():
            raise ValueError('Inspect the existing actual execution; never double-run this handle')
        try:
            mem = next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()
                       if line.startswith('MemAvailable:'))
            if mem < c['peak_ram_bytes']+4*1024**3:
                raise ValueError('Native CPU requires peak resident RAM plus4GiB')
            record['admission'] = admit(c)
            record['status'] = 'RUNNING'
            write(filename,record)
            environment = dict(os.environ,S_NATIVE_CPU_RECORD=str(filename))
            child_process = subprocess.Popen([sys.executable,'-B','-u',__file__,
                '--configuration',str(configuration),'--worker'],env=environment,cwd=R)
            child_identity = life.identity(child_process.pid)
            record['worker'] = vars(child_identity)
            write(filename,record)
            observer.start()
            while child_process.poll() is None:
                guard.await_next()
                time.sleep(.1)
            record['exit_code'] = child_process.wait()
            record['status'] = 'COMPLETE' if record['exit_code'] == 0 else 'FAILED'
        except life.StopAtBoundary:
            record.update(status='CONTINUATION_REQUIRED',exit_code=75,reason=guard.reason)
        except BaseException as error:
            record.update(status='FAILED',exit_code=1,error=type(error).__name__+': '+str(error))
        finally:
            guard.phase = 'closing'
            done.set()
            if observer.ident is not None:
                observer.join()
            if child_process is not None and child_process.poll() is None:
                record['stop_request'] = life.terminate_once(child_identity)
            try:
                life.close_children(max(180,c['cleanup_seconds']-30))
                if child_process is not None:
                    child_process.wait()
                record['owned_descendants_exited'] = True
            except BaseException as error:
                record.update(status='UNCLEAN_EXIT',exit_code=1,
                    cleanup_error=type(error).__name__+': '+str(error))
            own = resource.getrusage(resource.RUSAGE_SELF)
            descendants = resource.getrusage(resource.RUSAGE_CHILDREN)
            record.update(ended_at=time.time(),wall_seconds=time.time()-started,
                cpu_user_seconds=own.ru_utime+descendants.ru_utime,
                cpu_system_seconds=own.ru_stime+descendants.ru_stime,
                peak_child_RSS_bytes=descendants.ru_maxrss*1024,observer_joined=not observer.is_alive())
            write(filename,record)
            if c['stage'] == 'terminal':
                source = json.loads(Path(c['source_configuration']).read_text())
                proof = dict(record,run=source['run'],samples=source['samples'],mode='cpu',layer=6,
                             original_statistics=True)
                write(Path(source['output'])/'readout/terminal_statistics_status.json',proof)
            print(json.dumps({k:v for k,v in record.items() if k!='admission'}),flush=True)
    return record.get('exit_code',1)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--configuration',required=True)
    parser.add_argument('--worker',action='store_true')
    args=parser.parse_args()
    raise SystemExit(main(args.configuration,args.worker))
