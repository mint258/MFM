"""Small batched scheduler/progress snapshot; never reopens scientific inputs."""
import argparse, datetime, json, subprocess
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')

def query(argv):
    p=subprocess.run(argv,capture_output=True,text=True,stdin=subprocess.DEVNULL,timeout=45)
    return {'exitcode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--startup',action='store_true')
    args=parser.parse_args()
    dispatch=json.loads((ROOT/'reports/wp1_geometry_dispatch.json').read_text())
    jobs=[str(item['job_id']) for item in dispatch['submitted']]
    jobs.append('4512824')
    native_jobs=[]
    native_dispatch=ROOT/'reports/wp4_native_dispatch.json'
    if native_dispatch.exists():
        native_jobs=[str(item['job_id']) for item in json.loads(native_dispatch.read_text())['submitted']]
        jobs.extend(native_jobs)
    progress_meta=json.loads((ROOT/'progress.json').read_text())
    for stage in ('WP4_polar_cost_probe','WP4_final_report'):
        if progress_meta.get(stage,{}).get('job_id'):
            jobs.append(str(progress_meta[stage]['job_id']))
    jobs=list(dict.fromkeys(jobs))
    snapshot={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'probe_reason':'one-time startup check' if args.startup else 'hourly batch monitor',
        'squeue':query(['squeue','-j',','.join(jobs),'-h','-o','%i|%j|%T|%M|%C|%N|%R']),
        'sacct':query(['sacct','-j',','.join(jobs),'--format=JobID,State,ExitCode,AllocCPUS,ElapsedRaw,TotalCPU,MaxRSS','-P']),
        'progress':[]}
    for path in sorted((ROOT/'wp1_geometry_full').glob('*/progress.json')):
        try:snapshot['progress'].append({'path':str(path),**json.loads(path.read_text())})
        except (FileNotFoundError,json.JSONDecodeError):pass
    for path in sorted((ROOT/'wp1_geometry_full').glob('*/summary.json')):
        snapshot['progress'].append({'path':str(path),**json.loads(path.read_text())})
    for path in sorted((ROOT/'wp4_native_full_v4').glob('*/progress.json')):
        snapshot['progress'].append({'path':str(path),**json.loads(path.read_text())})
    (ROOT/'reports/latest_batch_monitor.json').write_text(json.dumps(snapshot,indent=2)+'\n')
    native=[item for item in snapshot['progress'] if '/wp4_native_full_v4/' in item['path']]
    wp4_ids=set(native_jobs+[str(progress_meta.get(stage,{}).get('job_id'))
        for stage in ('WP4_polar_cost_probe','WP4_final_report')])
    wp4_states=[line for line in snapshot['sacct']['stdout'].splitlines()
        if line.split('|',1)[0] in wp4_ids]
    print(json.dumps({'UTC':snapshot['UTC'],'squeue':snapshot['squeue'],
        'wp4_job_states':wp4_states,'sacct_error':snapshot['sacct']['stderr'],
        'native_buckets':len(native),
        'native_closed_or_partial_molecules':sum(item.get('closed_or_partial_molecules',0) for item in native),
        'native_active_workers':sum(item.get('active_workers',0) for item in native),
        'native_worker_failures':[{'path':item['path'],'failures':item['worker_failures']} for item in native if item.get('worker_failures')],
        'snapshot_path':str(ROOT/'reports/latest_batch_monitor.json')}))

if __name__=='__main__':main()
