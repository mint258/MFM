"""S resource/lifecycle adapter around P's original fullFT primary statistics."""
import argparse
import contextlib
import hashlib
import importlib
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
from types import SimpleNamespace

import lifecycle_20261122 as life
from storage_20261122 import CONTROL, ROOT, REPO, write
from storage_line_20261122 import admit
from finetune_extension_20261124 import query
from seal_finetune_20261124 import seal


def run(c):
    node = socket.gethostname().split('.')[0]
    if (c.get('invoking_authority') != 'docs/s_recipe/USER_DIRECTIVE_20261123B.md'
            or c.get('ready') is not True or os.environ.get('CUDA_VISIBLE_DEVICES') != ''
            or node != c['node'] or node not in {'compute-0-'+str(i) for i in range(8,20)}
            or Path(c['output']).parent != CONTROL/'finetune_statistics_20261124'):
        raise ValueError('Only registered S fullFT CPU primary statistics')
    life.enable_subreaper()
    for path, expected in c['providers_sha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=expected:
            raise ValueError('Registered scientific statistics provider changed before loading')
    sys.path.insert(0,str(ROOT/'MFM_p_recipe/tools/p_recipe'))
    original_ft = importlib.import_module('finetune_entry')
    original_ft.native_query = query
    sys.path.insert(0,str(REPO/'current'))
    provider = importlib.import_module('finetune_statistics_entry')
    stop = SimpleNamespace(requested=False)
    original_ft.set_actual_deadline(c,stop)
    guard = life.Guard(float(os.environ['P_MANAGED_HARD_END']),c['cleanup_seconds'])
    guard.phase = 'cpu_statistics'
    done = threading.Event()
    record = dict(run=c['run'],job_id=int(os.environ['SLURM_JOB_ID']),node=node,
        started_at=time.time(),actual_deadline_epoch=guard.end_epoch,
        status='RUNNING',producer=vars(life.identity(os.getpid())))

    @contextlib.contextmanager
    def cooperative_stop():
        yield stop

    def resources(configuration):
        admit(c)

    def deadline(configuration,shared_stop):
        os.environ['P_MANAGED_HARD_END']=str(guard.end_epoch)
        os.environ['P_MANAGED_STOP_NEW_UNITS_AT']=str(guard.end_epoch-c['cleanup_seconds'])
        os.environ['P_MANAGED_UNIT_SECONDS']=str(c['work_unit_seconds'])

    def observe():
        while not done.wait(30):
            try:
                admit(c)
            except Exception as error:
                record['observer_error']=type(error).__name__+': '+str(error)
                guard.request('resource_observation_failed')
            if guard.stopping():
                stop.requested=True
                return

    observer=threading.Thread(target=observe,daemon=False)
    with guard:
        try:
            resources(c)
            # The login controller admits only actual C0 source fits. Each seal
            # additionally requires their original complete/owned-exit receipts.
            for item in c['completed_new_S_fits']:
                if guard.stopping():
                    record.update(status='CONTINUATION_REQUIRED',exit_code=75)
                    return 75
                seal(item['output'],item['lifecycle_record'])
            provider.CooperativeStop=cooperative_stop
            provider.set_actual_deadline=deadline
            provider.require_cpu_admission=resources
            observer.start()
            code=provider.run(c)
            record.update(status='COMPLETE' if code==0 else 'CONTINUATION_REQUIRED',exit_code=code)
            return code
        except BaseException as error:
            record.update(status='FAILED',error=type(error).__name__+': '+str(error))
            raise
        finally:
            guard.phase='closing'
            done.set()
            if observer.ident is not None:
                observer.join()
            life.close_children(180)
            record.update(ended_at=time.time(),owned_descendants_exited=True,
                          observer_joined=not observer.is_alive())
            write(CONTROL/(c['run']+'_guarded_'+os.environ['SLURM_JOB_ID']+'.json'),record)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--configuration',required=True)
    raise SystemExit(run(json.loads(Path(p.parse_args().configuration).read_text())))
