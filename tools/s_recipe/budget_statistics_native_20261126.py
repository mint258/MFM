"""Original trajectory statistics inside the verified finite native CPU parent."""
import json
import os
from pathlib import Path
import resource
import time
from cpu_execution_20261126 import execution_fields, native_record
import lifecycle_20261122 as life
from storage_20261122 import write
from budget_readouts_extension_20261124 import registered, work


def run(configuration):
    context=native_record()
    c=json.loads(Path(configuration['source_configuration']).read_text())
    samples=c['readout_samples']
    registered(c,samples)
    c.update(node=configuration['node'],gpu_uuid='')
    output=Path(c['output'])/('readout_'+str(samples))
    previous=output/'snapshot_statistics_status.json'
    if previous.exists() and json.loads(previous.read_text()).get('status')=='COMPLETE':
        raise ValueError('Preserve already closed trajectory statistics')
    upstream=json.loads((output/'snapshot_gpu_status.json').read_text())
    if (upstream.get('run')!=c['run'] or upstream.get('samples')!=samples
            or upstream.get('status')!='GPU_SNAPSHOT_COMPLETE_WAITING_CPU'
            or not upstream.get('owned_descendants_exited') or not upstream.get('ended_at')):
        raise ValueError('The original GPU trajectory readout must have closed')
    guard=life.Guard(context['hard_end_epoch'],configuration['cleanup_seconds'])
    started=time.time()
    state=dict(run=c['run'],samples=samples,mode='cpu',node=c['node'],
        **execution_fields(),producer=vars(life.identity(os.getpid())),
        started_at=started,status='PREPARING',actual_deadline_epoch=guard.end_epoch,
        closing_reserve_seconds=configuration['cleanup_seconds'])
    with guard:
        try:
            state.update(work(c,samples,'cpu',guard))
            return 0
        except life.StopAtBoundary:
            state.update(status='PAUSED_READOUT',reason=guard.reason)
            return 75
        except BaseException as error:
            state.update(status='FAILED',error=type(error).__name__+': '+str(error))
            raise
        finally:
            guard.phase='closing'
            life.close_children(180)
            state.update(ended_at=time.time(),elapsed_seconds=time.time()-started,
                peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                owned_descendants_exited=True)
            write(previous,state)
