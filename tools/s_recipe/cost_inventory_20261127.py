"""Incremental inventory of execution metadata only; no scientific outputs."""
import json
from pathlib import Path
import time

from cost_accounting_20261127 import identity, interval_union_seconds

GPU_NODES = {'compute-0-'+str(i) for i in (*range(8),20,22)}
CPU_NODES = {'compute-0-'+str(i) for i in range(8,20)}


def gpu_proof(value, source, binding=None):
    if not isinstance(value,dict):return 'NOT_GPU_PROOF',None
    binding = binding or {}
    node = value.get('node', binding.get('node'))
    uuid = value.get('gpu_uuid', binding.get('gpu_uuid'))
    if node not in GPU_NODES or not uuid or value.get('started_at') is None:
        return 'NOT_GPU_PROOF', None
    producer = value.get('producer') or value
    if producer.get('uid') != 1278 or producer.get('pid') is None or producer.get('start_ticks') is None:
        return 'NOT_GPU_PROOF', None
    if binding.get('gpu_uuid') and value.get('gpu_uuid') and binding['gpu_uuid'] != value['gpu_uuid']:
        raise ValueError('The actual lifecycle UUID differs from its execution binding')
    if value.get('ended_at') is None or value.get('owned_descendants_exited') is False or value.get('observer_joined') is False:
        return 'OPEN', dict(source=source,node=node,gpu_uuid=uuid,kind='GPU',
            identity=list(identity(dict(value,node=node,producer=producer))))
    row=dict(node=node,gpu_uuid=uuid,producer={key:producer[key] for key in ('uid','pid','start_ticks')},
        started_at=value['started_at'],ended_at=value['ended_at'],exit_code=value.get('exit_code'),
        source=source,status=value.get('status'),run=value.get('run'),job_id=value.get('job_id'),
        closure_verified=value.get('owned_descendants_exited') is True and value.get('observer_joined') is True)
    identity(row);interval_union_seconds([(row['started_at'],row['ended_at'])])
    return 'CLOSED',row


def cpu_proof(value, source, command=None):
    if not isinstance(value,dict):return 'NOT_CPU_PROOF',None
    if value.get('node') not in CPU_NODES or value.get('execution')!='native_cpu':
        return 'NOT_CPU_PROOF',None
    identity(value)
    if (value.get('ended_at') is None or not value.get('owned_descendants_exited')
            or not value.get('observer_joined')):
        return 'OPEN',dict(source=source,handle=value.get('handle'),kind='native_CPU',identity=list(identity(value)))
    row={key:value.get(key) for key in ('node','producer','handle','stage','started_at','ended_at',
        'exit_code','cpu_user_seconds','cpu_system_seconds','wall_seconds')}
    row.update(source=source,command_exit_code=(command or {}).get('exit_code'))
    interval_union_seconds([(row['started_at'],row['ended_at'])])
    return 'CLOSED',row


def inventory(control):
    """Cache closed proofs once; revisit only open/new metadata sources."""
    control=Path(control)
    path=control/'cost_inventory_20261127.json'
    read=lambda p:json.loads(Path(p).read_text())
    cache=read(path) if path.exists() else {}
    gpu=dict(cache.get('closed_GPU_proofs',{}));cpu=dict(cache.get('closed_native_CPU_proofs',{}))
    ignored=set(cache.get('ignored_non_execution_sources',[]))
    superseded=list(cache.get('superseded_open_descriptors',[]))
    resolved_sources={row['source'] for row in superseded}
    bindings={}
    ledger=read(control/'execution.json')
    for bucket in ('runs','statistics'):
        for row in ledger[bucket].values():
            for key in ('lifecycle_record','native_origin_record','native_lifecycle_record','native_record'):
                if row.get(key):bindings.setdefault(row[key],row)
    paths={Path(p) for p in bindings if Path(p).is_relative_to(control)}
    for pattern in ('*process.json','*native*.json','*guarded*.json','*producer_exit_evidence.json'):
        paths.update(control.glob(pattern))
    opened=[];missing=[];unrecognized=[];new_gpu=0;new_cpu=0
    for source in sorted(paths):
        key=str(source)
        if key in gpu or key in resolved_sources or (key in ignored and key not in bindings):continue
        if not source.is_file():
            if key in bindings:missing.append(key)
            continue
        status,row=gpu_proof(read(source),key,bindings.get(key))
        if status=='CLOSED':gpu[key]=row;new_gpu+=1
        elif status=='OPEN':opened.append(row)
        elif key in bindings and bindings[key].get('node') in GPU_NODES and bindings[key].get('gpu_uuid'):
            unrecognized.append(key)
        else:ignored.add(key)
    legacy=control/'cost_accounting_snapshot_20261123.json'
    legacy_consumed=cache.get('legacy_snapshot_consumed',False)
    if not legacy_consumed and legacy.exists():
        # Reuse the earlier cost snapshot, including flattened legacy identities.
        for index,value in enumerate(read(legacy).get('native_closed_phases',[])):
            key=str(legacy)+'#native_closed_phases/'+str(index)
            if key in gpu:continue
            status,row=gpu_proof(value,key)
            if status=='CLOSED':gpu[key]=row;new_gpu+=1
        legacy_consumed=True
    for source in sorted((control/'native_cpu_20261126').glob('*/record.json')):
        key=str(source)
        if key in cpu:continue
        command=source.with_name('command_exit.json')
        status,row=cpu_proof(read(source),key,read(command) if command.exists() else None)
        if status=='CLOSED':cpu[key]=row;new_cpu+=1
        elif status=='OPEN':opened.append(row)
    closed_ids={}
    for row in gpu.values():closed_ids.setdefault(('GPU',identity(row),row['gpu_uuid']),[]).append(row['source'])
    for row in cpu.values():closed_ids.setdefault(('native_CPU',identity(row),None),[]).append(row['source'])
    unresolved=[]
    for row in opened:
        sources=closed_ids.get((row['kind'],tuple(row['identity']),row.get('gpu_uuid')))
        if sources:superseded.append(dict(row,closed_sources=sorted(sources)))
        else:unresolved.append(row)
    return dict(schema='S_COST_EXECUTION_INVENTORY_20261127_V1',
        status='PARTIAL_EXECUTION_INVENTORY_NOT_FINAL_COST_REPORT',observed_time=time.time(),
        closed_GPU_proofs=gpu,closed_native_CPU_proofs=cpu,ignored_non_execution_sources=sorted(ignored),
        open_execution_sources=unresolved,superseded_open_descriptors=superseded,
        missing_bound_sources=missing,new_GPU_proofs=new_gpu,
        unrecognized_bound_execution_sources=unrecognized,legacy_snapshot_consumed=legacy_consumed,
        new_native_CPU_proofs=new_cpu,legacy_GPU_closure_unverified=[k for k,v in gpu.items() if not v['closure_verified']],
        models_predictions_labels_scores_VAL_read=False,actual_Slurm_cost_capture_included=False,
        scope='Observed producer intervals only; no final coverage claim or monetary/energy inference')
