"""Point-in-time accounting of this task's actual Slurm parents, including failures."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);parser.add_argument('--gpu-registry',type=Path,required=True);args=parser.parse_args()
    if not args.label.replace('_','').isalnum():raise ValueError('Simple fresh label required')
    out=ROOT/(args.label+'.json');rawpath=ROOT/(args.label+'.psv')
    discovery_path=ROOT/(args.label+'.discovery.psv')
    if out.exists() or rawpath.exists() or discovery_path.exists():raise FileExistsError('Preserve earlier accounting')
    prior=json.loads((ROOT/'job_ledger_through_457_v3.json').read_text())
    gpu_ids={row['job_id'] for row in prior['jobs'] if row['gpu_node_job']} | {'4520485','4520486','4520525','4520544','4520546','4520549','4520576','4520579','4520580','4520583','4520589','4520590'}
    extra_registry=json.loads(args.gpu_registry.read_text())
    for entry in extra_registry['jobs']:
        receipt=Path(entry['submission_receipt'])
        field=entry.get('receipt_job_id_field','job_id')
        if field not in ('job_id','actual_sbatch_job_id','actual_job_id'):raise ValueError('Known actual receipt job identity field required')
        if hashlib.sha256(receipt.read_bytes()).hexdigest()!=entry['submission_receipt_sha256'] or json.loads(receipt.read_text())[field]!=entry['job_id']:raise ValueError('GPU registry must bind actual submission receipts')
        gpu_ids.add(entry['job_id'])
    columns=['JobIDRaw','JobName','User','State','ExitCode','ElapsedRaw','AllocCPUS','ReqMem','NodeList','ReqTRES','AllocTRES']
    discovery=['sacct','-S','2026-10-25T00:00:00','-u','zixiao','-X','-n','-P','-o',','.join(columns)]
    discovered=subprocess.run(discovery,capture_output=True,text=True,check=True,timeout=45)
    exact={row['job_id'] for row in prior['jobs']}
    for line in discovered.stdout.splitlines():
        fields=line.split('|')
        if len(fields)>=3 and fields[1].startswith('model_v3'):
            if not fields[0].isdigit() or fields[2]!='zixiao':raise ValueError('Unexpected discovered owner/parent')
            exact.add(fields[0])
    active_argv=['squeue','-u','zixiao','-h','-o','%i|%j|%u']
    active_raw=subprocess.check_output(active_argv,text=True,timeout=45)
    active_discovered=set()
    for line in active_raw.splitlines():
        fields=line.split('|')
        if len(fields)==3 and fields[1].startswith('model_v3'):
            if not fields[0].isdigit() or fields[2]!='zixiao':raise ValueError('Actual active owned model parents required')
            exact.add(fields[0]);active_discovered.add(fields[0])
    exact.update(gpu_ids)
    query=['sacct','-j',','.join(sorted(exact,key=int)),'-X','-n','-P','-o',','.join(columns)]
    p=subprocess.run(query,capture_output=True,text=True,check=True,timeout=45)
    rows=[]
    for line in p.stdout.splitlines():
        fields=line.split('|')
        if len(fields)==len(columns)+1 and fields[-1]=='':fields.pop()
        if len(fields)!=len(columns):raise ValueError('Actual sacct schema differs')
        row=dict(zip(columns,fields))
        if not row['JobName'].startswith('model_v3') and row['JobIDRaw'] not in exact:continue
        if row['User']!='zixiao' or not row['JobIDRaw'].isdigit():raise ValueError('Owned actual parents only')
        number=row['JobIDRaw']
        gpu=number in gpu_ids
        elapsed=int(row['ElapsedRaw']);cpus=int(row['AllocCPUS'])
        row.update(job_id=number,elapsed_seconds=elapsed,allocated_cpus=cpus,gpu_node_job=gpu,
            allocated_cpu_seconds=elapsed*cpus,terminal=row['State'].split()[0] in
            {'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL'})
        rows.append(row)
    actual={row['job_id'] for row in rows}
    missing=({row['job_id'] for row in prior['jobs']}|active_discovered|gpu_ids)-actual
    if len(actual)!=len(rows) or missing:raise ValueError('Missing or duplicate registered parents: '+repr(sorted(missing)))
    with rawpath.open('x') as stream:stream.write(p.stdout)
    with discovery_path.open('x') as stream:stream.write(discovered.stdout)
    result=dict(schema='model_v3_actual_parent_accounting_v12',captured_utc=datetime.now(timezone.utc).isoformat(),
        query=query,raw_receipt_sha256=hashlib.sha256(rawpath.read_bytes()).hexdigest(),jobs=rows,
        active_queue_discovery_argv=active_argv,active_queue_discovery_raw=active_raw,
        discovery_query=discovery,discovery_sha256=hashlib.sha256(discovery_path.read_bytes()).hexdigest(),
        registered_job_count=len(rows),exact_registered_job_ids=sorted(actual,key=int),
        discovery_scope='This account, today, actual parent JobName starts model_v3; previous exact registry must be included',
        active_job_ids=[row['job_id'] for row in rows if not row['terminal']],all_terminal=all(row['terminal'] for row in rows),
        allocated_cpu_seconds=sum(row['allocated_cpu_seconds'] for row in rows),
        allocated_gpu_node_job_seconds=sum(row['elapsed_seconds'] for row in rows if row['gpu_node_job']),
        gpu_time_is_utilization=False,active_costs_are_point_in_time=True,
        gpu_classification='Exact scientific GPU-job identity, preserving prior registry; CPU jobs on historical GPU nodes are not GPU computation',
        exact_GPU_job_ids=sorted(gpu_ids,key=int),additional_GPU_job_registry=extra_registry,additional_GPU_registry_sha256=hashlib.sha256(args.gpu_registry.read_bytes()).hexdigest())
    with out.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:result[k] for k in ('registered_job_count','active_job_ids','allocated_cpu_seconds','allocated_gpu_node_job_seconds')}))

if __name__=='__main__':main()
