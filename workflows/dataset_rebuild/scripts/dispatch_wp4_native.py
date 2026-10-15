"""Root-only WP4 pilot dispatch, with complete molecules in disjoint hash buckets."""
import argparse, ast, hashlib, json, subprocess, sys, time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')

def query(argv):
    result=subprocess.run(argv,capture_output=True,text=True,stdin=subprocess.DEVNULL,timeout=60)
    if result.returncode:raise RuntimeError(result.stderr or result.stdout)
    return result.stdout

def save(path,value):
    temporary=path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n')
    temporary.replace(path)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--buckets',type=int,default=16)
    p.add_argument('--bounded-summary',required=True)
    p.add_argument('--runner',required=True)
    p.add_argument('--batch-script',required=True)
    args=p.parse_args()
    report=ROOT/'reports/wp4_native_dispatch.json'
    if report.exists():raise RuntimeError('Dispatch already recorded; inspect exact bucket submissions before recovery')
    quality=json.loads((ROOT/'wp1_results/screening_report.json').read_text())
    panel=json.loads((ROOT/'wp4_native_panel/pilot_panel_manifest.json').read_text())
    bounded=json.loads(Path(args.bounded_summary).read_text())
    if quality['status']!='COMPLETE' or panel['status']!='READY_FOR_NATIVE_WP4' or panel['target_records']!=10000:
        raise RuntimeError('Complete full-population WP1 and genuine 10000-record panel required')
    if bounded['status'] not in ('NATIVE_PANEL_ATTEMPT_COMPLETE','ARCHIVE_ONLY_REPAIR_COMPLETE') or bounded['failures'] or bounded['completed_molecules']<16:
        raise RuntimeError('Bounded native integration has unresolved infrastructure failures')
    runner=Path(args.runner)
    ast.parse(runner.read_text())
    nodes={}
    listing=query(['sinfo','--Node','-h','-p','cpu','-o','%N|%t|%C'])
    for line in listing.splitlines():
        node,state,cpu=line.split('|')
        if state.rstrip('*') not in ('idle','mix','allocated','alloc'):continue
        free=int(cpu.split('/')[1])
        if free>=16:nodes[node]={'initial_idle':free,'reserved':0,'initial_state':state}
    if sum(n['initial_idle'] for n in nodes.values())<16:
        raise RuntimeError('No available CPU allocation of at least 16 cores')
    receipt={'created_epoch':time.time(),'scope':'WP4_NATIVE_10000_PANEL_TEST_NO_LMDB_WRITES',
        'bucket_count':args.buckets,'panel_records':panel['actual_records'],'panel_molecules':panel['molecules'],
        'whole_molecule_hash_partition':True,'monitor_seconds':3600,'memory_gib_per_job':48,
        'runner':str(runner),'runner_sha256':hashlib.sha256(runner.read_bytes()).hexdigest(),
        'bounded_integration_summary':args.bounded_summary,'nodes_before':{key:dict(value) for key,value in nodes.items()},'submitted':[]}
    save(report,receipt)
    for bucket in range(args.buckets):
        candidates=sorted(nodes,key=lambda node:(-(nodes[node]['initial_idle']-nodes[node]['reserved']),node))
        last_errors=[]
        for node in candidates:
            idle=nodes[node]['initial_idle']-nodes[node]['reserved']
            if idle<16:continue
            cpus=min(32,idle)
            argv=[sys.executable,str(ROOT/'scripts/submit_job_v2.py'),
                '--script',args.batch_script,'--name',f'p1data_WP4_native_b{bucket:02d}',
                '--node',node,'--cpus',str(cpus),'--memory-gb','48','--time','24:00:00',
                '--kind','wp4',str(bucket),str(args.buckets)]
            result=subprocess.run(argv,capture_output=True,text=True,stdin=subprocess.DEVNULL)
            if result.returncode:
                last_errors.append({'node':node,'returncode':result.returncode,'stderr':result.stderr,'stdout':result.stdout})
                if not any(reason in result.stderr for reason in ('Insufficient current idle CPUs','Declared memory plus new request')):
                    receipt['submission_error']={'bucket':bucket,'attempt':last_errors[-1]}
                    save(report,receipt)
                    raise RuntimeError('Submission failed outside resource preflight; inspect existing own queue before retry')
                continue
            entry=json.loads(result.stdout);entry.update(bucket=bucket,bucket_count=args.buckets,cpus=cpus)
            receipt['submitted'].append(entry)
            nodes[node]['reserved']+=cpus
            save(report,receipt)
            print(json.dumps(entry),flush=True)
            break
        else:
            receipt['dispatch_incomplete']={'next_bucket':bucket,'resource_errors':last_errors}
            save(report,receipt)
            raise RuntimeError('Remaining buckets need free CPU/memory; resume only undispatched buckets')
    receipt['dispatch_complete_epoch']=time.time()
    receipt['allocated_cpus']=sum(j['cpus'] for j in receipt['submitted'])
    save(report,receipt)

if __name__=='__main__':main()
