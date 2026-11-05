"""Point-in-time model accounting: preserve v12 identities and add explicit CPU receipts."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
from cpu_receipt_registry_v13_rev2 import O,N,require,raw_ref,read,bound,load_cpu_registry,top_cpu_inventory

HISTORICAL_GPU={'4520485','4520486','4520525','4520544','4520546','4520549',
    '4520576','4520579','4520580','4520583','4520589','4520590'}
COLUMNS=['JobIDRaw','JobName','User','State','ExitCode','ElapsedRaw','AllocCPUS','ReqMem','NodeList','ReqTRES','AllocTRES']


def write(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
    return raw_ref(path)


def registry_prepare(args):
    require(args.inventory_output and args.prepare_cpu_registry,'Registry prepare needs two fresh explicit paths')
    require(not args.prepare_cpu_registry.exists() and not args.inventory_output.exists(),'Preserve earlier registry/inventory')
    entries,files=top_cpu_inventory();previous=read(args.previous_ledger)
    previous_ids={row['job_id'] for row in previous['jobs']}
    previous_gpu={row['job_id'] for row in previous['jobs'] if row['gpu_node_job']}
    for item in files:
        for legacy in item.get('legacy_array_job_fields',[]):
            require(legacy['job_id'] in previous_gpu,'Legacy array identities must already be in previous exact GPU scope')
        for legacy in item.get('legacy_grouped_job_fields',[]):
            require(legacy['job_id'] in previous_ids and legacy['job_id'] not in previous_gpu,
                'Unverifiable legacy grouped CPU parent must not be newly inferred')
    inventory=write(args.inventory_output,dict(schema='model_v3_top_level_actual_submission_inventory_v13',
        scope='Only immediate O/N submission-named JSON; no payload or recursive discovery',files=files,
        verified_cpu_job_ids=[row['job_id'] for row in entries],previous_ledger=raw_ref(args.previous_ledger),
        CPU_missing_from_previous=[row for row in entries if row['job_id'] not in previous_ids]))
    registry=write(args.prepare_cpu_registry,dict(schema='model_v3_explicit_CPU_receipt_registry_v1',
        scope='Verified actual CPU-only helper/queued receipts, not a GPU classification rule',jobs=entries,
        metadata_inventory=inventory,generated_from_source=raw_ref(__file__),
        receipt_verifier_source=raw_ref(N/'cpu_receipt_registry_v13_rev2.py')))
    print(json.dumps(dict(status='CPU_RECEIPT_REGISTRY_PREPARED_NO_SCHEDULER_CALLS',registry=registry,
        inventory=inventory,CPU_count=len(entries),missing_from_previous=[row['job_id'] for row in entries if row['job_id'] not in previous_ids])))


def inputs(args):
    prior=read(O/'job_ledger_through_457_v3.json');previous=read(args.previous_ledger)
    require(previous['schema'].startswith('model_v3_actual_parent_accounting_v'), 'Known prior point-time accounting required')
    require(len({row['job_id'] for row in previous['jobs']})==len(previous['jobs']),'Duplicate previous parents')
    gpu_ids={row['job_id'] for row in prior['jobs'] if row['gpu_node_job']}|HISTORICAL_GPU
    extra=read(args.gpu_registry);extra_ids=set()
    for entry in extra['jobs']:
        receipt=Path(entry['submission_receipt']);field=entry.get('receipt_job_id_field','job_id')
        require(field in ('job_id','actual_sbatch_job_id','actual_job_id'),'Known actual GPU receipt identity field required')
        require(raw_ref(receipt)['sha256']==entry['submission_receipt_sha256']
            and read(receipt)[field]==entry['job_id'],'GPU registry must bind actual submission receipt')
        require(entry['job_id'] not in extra_ids,'Duplicate GPU registry parent');extra_ids.add(entry['job_id'])
    gpu_ids.update(extra_ids)
    require({row['job_id'] for row in previous['jobs'] if row['gpu_node_job']}<=gpu_ids,
        'Previous exact GPU classification must be preserved by known original/extra registries')
    registry,cpu_ids,cpu_refs=load_cpu_registry(args.cpu_registry)
    require(not(cpu_ids&gpu_ids),'CPU/GPU identity overlap; never classify CPU as GPU')
    fresh_entries,_=top_cpu_inventory()
    require(fresh_entries==registry['jobs'],'Current top CPU receipts differ; prepare a fresh explicit CPU registry')
    inventory=bound(registry['metadata_inventory'])
    require(inventory['verified_cpu_job_ids']==sorted(cpu_ids,key=int),'CPU inventory identity scope differs')
    return prior,previous,gpu_ids,extra,registry,cpu_ids,cpu_refs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label');parser.add_argument('--gpu-registry',type=Path)
    parser.add_argument('--cpu-registry',type=Path)
    parser.add_argument('--previous-ledger',type=Path,default=O/'job_ledger_model_v3_active_v15.json')
    parser.add_argument('--prepare-cpu-registry',type=Path);parser.add_argument('--inventory-output',type=Path)
    parser.add_argument('--validate-only',action='store_true');args=parser.parse_args()
    require(os.getuid()==1278 and socket.gethostname()=='sonmi','Actual Root login metadata identity required')
    if args.prepare_cpu_registry:registry_prepare(args);return 0
    require(args.gpu_registry and args.cpu_registry,'Explicit GPU and CPU receipt registries required')
    pinned=[raw_ref(path) for path in (args.previous_ledger,args.gpu_registry,args.cpu_registry,
        O/'job_ledger_through_457_v3.json',N/'capture_ledger_v12.py',Path(__file__),N/'cpu_receipt_registry_v13_rev2.py')]
    prior,previous,gpu_ids,extra_registry,cpu_registry,cpu_ids,cpu_refs=inputs(args)
    if args.validate_only:
        print(json.dumps(dict(status='ACCOUNTING_INPUTS_VALID_NO_SCHEDULER_CALLS',previous_parents=len(previous['jobs']),
            explicit_CPU_parents=len(cpu_ids),exact_GPU_parents=len(gpu_ids),
            additional_CPU_ids=sorted(cpu_ids-{row['job_id'] for row in previous['jobs']},key=int))));return 0
    require(args.label and args.label.replace('_','').isalnum(),'Simple fresh label required')
    out=O/(args.label+'.json');rawpath=O/(args.label+'.psv');discovery_path=O/(args.label+'.discovery.psv')
    require(not any(path.exists() for path in (out,rawpath,discovery_path)),'Preserve earlier accounting snapshots')
    discovery=['sacct','-S','2026-10-25T00:00:00','-u','zixiao','-X','-n','-P','-o',','.join(COLUMNS)]
    discovered=subprocess.run(discovery,capture_output=True,text=True,check=True,timeout=45)
    exact={row['job_id'] for row in prior['jobs']}|{row['job_id'] for row in previous['jobs']}
    for line in discovered.stdout.splitlines():
        fields=line.split('|')
        if len(fields)>=3 and fields[1].startswith('model_v3'):
            require(fields[0].isdigit() and fields[2]=='zixiao','Unexpected discovered owner/parent');exact.add(fields[0])
    active_argv=['squeue','-u','zixiao','-h','-o','%i|%j|%u']
    active_raw=subprocess.check_output(active_argv,text=True,timeout=45);active_discovered=set()
    for line in active_raw.splitlines():
        fields=line.split('|')
        if len(fields)==3 and fields[1].startswith('model_v3'):
            require(fields[0].isdigit() and fields[2]=='zixiao','Actual active owned model parents required')
            exact.add(fields[0]);active_discovered.add(fields[0])
    exact.update(gpu_ids);exact.update(cpu_ids)
    query=['sacct','-j',','.join(sorted(exact,key=int)),'-X','-n','-P','-o',','.join(COLUMNS)]
    captured=subprocess.run(query,capture_output=True,text=True,check=True,timeout=45);rows=[]
    for line in captured.stdout.splitlines():
        fields=line.split('|')
        if len(fields)==len(COLUMNS)+1 and fields[-1]=='':fields.pop()
        require(len(fields)==len(COLUMNS),'Actual sacct schema differs');row=dict(zip(COLUMNS,fields))
        require(row['User']=='zixiao' and row['JobIDRaw'].isdigit() and row['JobIDRaw'] in exact,'Owned exact actual parents only')
        job=row['JobIDRaw'];elapsed=int(row['ElapsedRaw']);cpus=int(row['AllocCPUS'])
        require(elapsed>=0 and cpus>=0,'Negative actual accounting observation')
        if job in cpu_ids:
            require('gpu=' not in row['ReqTRES'].lower() and 'gpu=' not in row['AllocTRES'].lower(),
                'Explicit CPU receipt has unexpected GPU allocation')
        row.update(job_id=job,elapsed_seconds=elapsed,allocated_cpus=cpus,gpu_node_job=job in gpu_ids,
            allocated_cpu_seconds=elapsed*cpus,terminal=row['State'].split()[0] in
            {'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL'},
            explicit_CPU_receipt_registered=job in cpu_ids)
        rows.append(row)
    actual={row['job_id'] for row in rows};missing=exact-actual
    require(len(actual)==len(rows) and not missing,'Missing or duplicate registered/discovered parents: '+repr(sorted(missing)))
    for value in pinned+cpu_refs:require(raw_ref(value['path'])==value,'Accounting source/input/receipt changed')
    with rawpath.open('x') as stream:stream.write(captured.stdout)
    with discovery_path.open('x') as stream:stream.write(discovered.stdout)
    result=dict(schema='model_v3_actual_parent_accounting_v13',captured_utc=datetime.now(timezone.utc).isoformat(),
        query=query,raw_receipt_sha256=raw_ref(rawpath)['sha256'],jobs=rows,
        active_queue_discovery_argv=active_argv,active_queue_discovery_raw=active_raw,
        discovery_query=discovery,discovery_sha256=raw_ref(discovery_path)['sha256'],
        registered_job_count=len(rows),exact_registered_job_ids=sorted(actual,key=int),
        discovery_scope='v12 model_v3 prefix discovery plus all previous exact parents plus explicit CPU/GPU receipt registries',
        active_job_ids=[row['job_id'] for row in rows if not row['terminal']],all_terminal=all(row['terminal'] for row in rows),
        allocated_cpu_seconds=sum(row['allocated_cpu_seconds'] for row in rows),
        allocated_gpu_node_job_seconds=sum(row['elapsed_seconds'] for row in rows if row['gpu_node_job']),
        gpu_time_is_utilization=False,active_costs_are_point_in_time=True,not_final_global_task_completion=True,
        gpu_classification='Exact v12 scientific GPU identities and bound extra registry; explicit CPU identities never GPU',
        exact_GPU_job_ids=sorted(gpu_ids,key=int),additional_GPU_job_registry=extra_registry,
        additional_GPU_registry_sha256=raw_ref(args.gpu_registry)['sha256'],explicit_CPU_job_registry=cpu_registry,
        explicit_CPU_registry_ref=raw_ref(args.cpu_registry),previous_exact_ledger=raw_ref(args.previous_ledger),
        accounting_runtime_sources=pinned,
        CPU_parents_previously_omitted=sorted(cpu_ids-{row['job_id'] for row in previous['jobs']},key=int))
    write(out,result)
    print(json.dumps({key:result[key] for key in ('registered_job_count','active_job_ids','CPU_parents_previously_omitted',
        'allocated_cpu_seconds','allocated_gpu_node_job_seconds')}));return 0


if __name__=='__main__':raise SystemExit(main())
