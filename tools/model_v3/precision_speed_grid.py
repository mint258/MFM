"""Guarded speed grid; hand off only between independent, completed cells.

Each cell starts from the same seed0 initialization, exactly as the original
sbatch loop. A running cell is never interrupted: its 100 warmup and 1000
measured updates stay continuous. Completed cells, their real process/job
identities and telemetry are the complete state needed by the next executor.
No model/optimizer state is shared between independent precision/BS cells.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time

from precision_quality import ROOT, REPO, capacity, identity, read, run, write


def alive(record):
    try:
        return identity(record['pid']) == {k:record[k] for k in ('pid','uid','start_ticks','pgid')}
    except (FileNotFoundError,ProcessLookupError):
        return False


def cells(task):
    for batch in (32,128):
        for mode in ('fp32','tf32_islands','bf16_islands'):
            yield mode,batch,ROOT/('speed_'+mode+'_B'+str(batch)+'_'+task['grid_name'])


def closed(task,mode,batch,path):
    result=path/'benchmark.json'
    if not result.is_file():return False
    record=read(result)
    expected=dict(status='SPEED_COMPLETE',precision=mode,batch_size=batch,
        updates=1100,measured_updates=1000,timed_samples=1000*batch,uuid=task['gpu_uuid'])
    if any(record.get(key)!=value for key,value in expected.items()):
        raise RuntimeError('Invalid completed speed cell: '+str(path))
    return True


def requested(task):
    path=Path(task['grid_request'])
    if not path.is_file():return False
    request=read(path)
    if request.get('grid_name')!=task['grid_name']:raise RuntimeError('Wrong grid handoff request')
    try:
        query=subprocess.run(['squeue','-h','-j',str(int(request['job_id'])),'-o','%T'],
            capture_output=True,text=True,timeout=15)
    except subprocess.TimeoutExpired:
        return False
    if query.returncode:return False
    return 'RUNNING' in query.stdout.splitlines()


def worker(task):
    if socket.gethostname().split('.')[0]!=task['node'] or task['node']=='compute-0-21':
        raise RuntimeError('Wrong/excluded speed node')
    # Called as a child of precision_quality.run, which owns the UUID lock,
    # real process group and five-second disk/quota protection.
    parent=(Path('/proc')/str(os.getppid())/'cmdline').read_bytes()
    if b'precision_quality.py' not in parent and b'precision_speed_grid.py' not in parent:
        raise RuntimeError('Use the guarded native or Slurm entry point')
    capacity();state_path=Path(task['grid_state'])
    state=read(state_path) if state_path.is_file() else dict(history=[],unit_complete=False)
    if state.get('status')=='FAILED':raise RuntimeError('Preserve and inspect the failed cell before any recovery')
    execution='Slurm' if os.environ.get('SLURM_JOB_ID') else 'native_SSH'
    state.update(grid_name=task['grid_name'],node=task['node'],gpu_uuid=task['gpu_uuid'],
        execution=execution,job_id=int(os.environ['SLURM_JOB_ID']) if execution=='Slurm' else None,
        executor=identity(os.getpid()),status='RUNNING')

    def launch(command,cell):
        capacity()
        context=subprocess.check_output(['nvidia-smi','-i',task['gpu_uuid'],
            '--query-compute-apps=pid,process_name','--format=csv,noheader'],text=True,timeout=15)
        process=subprocess.Popen(command,stdin=subprocess.DEVNULL,cwd=REPO)
        entry=dict(cell=cell,execution=execution,job_id=state['job_id'],started_at=time.time(),
            process=identity(process.pid),command=command,preexisting_gpu_contexts=context.splitlines())
        state['active']=entry;write(state_path,state)
        print(json.dumps(entry),flush=True)
        code=process.wait();entry.update(exit_code=code,ended_at=time.time())
        state['history'].append(entry);state['active']=None
        if code:
            state.update(status='FAILED',exit_code=code);write(state_path,state)
            raise RuntimeError('Cell process failed with exit '+str(code))
        write(state_path,state)

    pending=[(mode,batch,path) for mode,batch,path in cells(task) if not closed(task,mode,batch,path)]
    if not pending:
        state.update(status='COMPLETED',ended_at=time.time());write(state_path,state);return 0
    for mode,batch,path in pending:
        if path.exists():raise RuntimeError('Incomplete output retained; do not silently rerun '+str(path))
    if not state['unit_complete']:
        launch([task['python'],'-B','-m','pytest','-q','-p','no:cacheprovider',
                'current/tests/test_p_precision_islands.py'],'sole_island_unit')
        state['unit_complete']=True;write(state_path,state)
    for mode,batch,path in pending:
        if execution=='native_SSH' and requested(task):
            state.update(status='HANDOFF_READY',ended_at=time.time(),
                completed_cells=[str(p) for m,b,p in cells(task) if closed(task,m,b,p)])
            write(state_path,state);return 0
        launch([task['python'],'-B','-u','tools/model_v3/precision_study.py','benchmark',
                '--precision',mode,'--batch-size',str(batch),'--output',str(path)],mode+'_B'+str(batch))
        if not closed(task,mode,batch,path):raise RuntimeError('Child exited without complete benchmark output')
    state.update(status='COMPLETED',ended_at=time.time(),completed_cells=[str(p) for _,_,p in cells(task)])
    write(state_path,state);return 0


def standby(task):
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('A real Slurm allocation is required')
    capacity();native_path=Path(task['native_state'])
    native=read(native_path) if native_path.is_file() else None
    if native and alive(native):
        write(task['grid_request'],dict(grid_name=task['grid_name'],job_id=int(os.environ['SLURM_JOB_ID']),
            requested_at=time.time(),handoff_boundary='end of complete independent100warmup+1000measured cell'))
        while alive(native):
            time.sleep(5);capacity()
    state=read(task['grid_state']) if Path(task['grid_state']).is_file() else None
    if state and state.get('status')=='COMPLETED':
        if not all(closed(task,m,b,p) for m,b,p in cells(task)):raise RuntimeError('Incomplete completed grid')
        return 0
    if state and state.get('status')!='HANDOFF_READY':
        raise RuntimeError('Native task did not end at a verified complete-cell boundary')
    while True:
        try:return run(task,task['configuration'],slurm=True)
        except BlockingIOError:time.sleep(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('worker','standby'))
    parser.add_argument('--task',required=True);args=parser.parse_args();task=read(args.task)
    raise SystemExit(worker(task) if args.action=='worker' else standby(task))
