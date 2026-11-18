"""Bounded-memory trace export/analysis; synthetic CPU tests cover the I/O."""
import gzip
import json
import os
from pathlib import Path
import re
import stat
import subprocess


def export_gzip(profiler,destination,*,completion_timeout=None):
    destination=Path(destination)
    logical=destination.with_suffix('')
    temporary=Path(str(logical)+'.tmp')
    if destination.suffix!='.gz' or logical.suffix!='.json':
        raise ValueError('A new .json.gz destination is required')
    if any(p.exists() or p.is_symlink() for p in (destination,logical,temporary)):
        raise FileExistsError('Never overwrite an existing trace')
    os.mkfifo(temporary,0o600)
    compressor=None
    try:
        with destination.open('xb') as output:
            # A separate process consumes the FIFO while Kineto holds the GIL.
            compressor=subprocess.Popen(['bash','-c','exec gzip -1 -c < "$1"','gzip-trace',str(temporary)],
                stdout=output,start_new_session=True)
            profiler.export_chrome_trace(str(logical))
            if compressor.wait(timeout=completion_timeout)!=0:
                raise OSError('Trace compressor failed')
        if not logical.exists() or not stat.S_ISFIFO(logical.lstat().st_mode):
            raise OSError('Kineto did not use its expected atomic .tmp export')
        return destination
    finally:
        if compressor is not None and compressor.poll() is None:
            compressor.terminate();compressor.wait()
        for path in (temporary,logical):
            if path.exists() and stat.S_ISFIFO(path.lstat().st_mode):
                path.unlink()


def events(path,*,chunk_size=1024*1024):
    """Read each Chrome event once with a cursor; no quadratic buffer slicing."""
    decoder=json.JSONDecoder()
    with gzip.open(path,'rt',encoding='utf-8') as source:
        buffer=''
        while True:
            chunk=source.read(chunk_size)
            if not chunk:raise ValueError('Missing traceEvents array')
            buffer+=chunk
            match=re.search(r'"traceEvents"\s*:\s*\[',buffer)
            if match:position=match.end();break
        while True:
            while position<len(buffer) and buffer[position] in ' \r\n\t,':position+=1
            if position<len(buffer) and buffer[position]==']':return
            try:event,end=decoder.raw_decode(buffer,position)
            except json.JSONDecodeError:
                chunk=source.read(chunk_size)
                if not chunk:raise ValueError('Truncated trace event array')
                buffer=buffer[position:]+chunk;position=0;continue
            if not isinstance(event,dict):raise ValueError('Trace event is not an object')
            yield event
            position=end


def summarize(path,seconds,steps=100,main_tid=None):
    intervals=[];kernels=copies=byte_count=launch_us=all_launch_us=0
    sync={};sync_events=[];boundaries=[];regions=[]
    for event in events(path):
        if event.get('ph')!='X':continue
        kind=event.get('cat');name=event.get('name','')
        if name=='PERF5090_TRAINING_REGION':regions.append((event['ts'],event['ts']+event['dur']))
        if name in ('PERF5090_INSTRUMENTATION_SYNC','PERF5090_REPORTING_SYNC'):
            boundaries.append((event['ts'],event['ts']+event['dur']))
        if kind in ('kernel','gpu_memcpy'):
            intervals.append((event['ts'],event['ts']+event['dur']))
        if kind=='kernel':kernels+=1
        if kind=='gpu_memcpy' and 'HtoD' in name:
            copies+=1;byte_count+=float(event.get('args',{}).get('bytes',0))
        if kind in ('cuda_runtime','cuda_driver'):
            if 'Synchronize' in name:
                sync[name]=sync.get(name,0)+1;sync_events.append((event['ts'],event['ts']+event['dur']))
            if 'LaunchKernel' in name or 'GraphLaunch' in name:
                all_launch_us+=event['dur']
                if main_tid is None or event.get('tid')==main_tid:launch_us+=event['dur']
    busy=0.;right=float('-inf')
    for start,end in sorted(intervals):
        busy+=max(0.,end-max(start,right));right=max(right,end)
    excluded=sum((regions and not any(a<=start and end<=b for a,b in regions)) or any(a<=start and end<=b for a,b in boundaries) for start,end in sync_events)
    return dict(training_region_present=bool(regions),instrumentation_syncs=excluded,training_synchronizations_per_step=(sum(sync.values())-excluded)/steps,
        profiled_steps=steps,trace=str(path),GPU_busy_wall_ratio=busy/1e6/seconds,
        kernels_per_step=kernels/steps,synchronizations_per_step=sum(sync.values())/steps,
        synchronization_APIs=sync,host_kernel_launch_seconds_per_step=launch_us/1e6/steps,
        host_all_threads_kernel_launch_seconds_per_step=all_launch_us/1e6/steps,main_thread_id=main_tid,
        H2D_copies_per_step=copies/steps,H2D_bytes_per_step=byte_count/steps,
        note='Same100-step CPU/CUDA+stack capture; raw trace exported losslessly to gzip through an owned FIFO; parser reads events once.')
