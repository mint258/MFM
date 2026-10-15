"""Root-only disjoint shard submission after the completed geometry smoke."""
import ast, hashlib, json, subprocess, sys, time
from pathlib import Path

ROOT = Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
REPORT = ROOT/'reports/wp1_geometry_dispatch.json'

def save(value):
    temporary = REPORT.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    temporary.replace(REPORT)

def main():
    if REPORT.exists():
        raise RuntimeError('Dispatch already recorded; inspect submitted shards before recovery')
    script = ROOT/'scripts/wp1_geometry.py'
    ast.parse(script.read_text())
    smoke = json.loads((ROOT/'wp1_geometry_smoke/job_4512807/summary.json').read_text())
    cache = json.loads((ROOT/'reports/geometry_cache_enrichment.json').read_text())
    if smoke['status'] != 'COMPLETE' or smoke['rows'] != 1000 or cache['job_id'] != '4512808':
        raise RuntimeError('Required completed inputs unavailable')
    jobs = [(sid, 'compute-0-17') for sid in range(6)]
    jobs += [(sid, 'compute-0-19') for sid in range(6,9)]
    jobs += [(9,'compute-0-18'), (10,'compute-0-14')]
    receipt = {'created_epoch':time.time(), 'stage':'WP1_FULL_GEOMETRY',
        'physical_input_rows':15879477, 'after_X_only':True,
        'source_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),
        'input':str(ROOT/'record_index.parquet'), 'source_lmdb_readonly':True,
        'lmdb_created_or_written':False, 'cpus_per_job':32,
        'memory_gib_per_job':32, 'monitor_seconds':3600,
        'planned_shards':[{'shard':sid,'node':node} for sid,node in jobs], 'submitted':[]}
    save(receipt)
    for sid,node in jobs:
        argv = [sys.executable, str(ROOT/'scripts/submit_job.py'),
            '--script',str(ROOT/'scripts/wp1_geometry_full.sbatch'),
            '--name',f'p1data_WP1_full_s{sid:02d}', '--node',node,
            '--cpus','32', '--memory-gb','32','--time','12:00:00',
            '--kind','wp1',str(sid)]
        result = subprocess.run(argv,capture_output=True,text=True,stdin=subprocess.DEVNULL)
        if result.returncode:
            receipt['submission_error'] = {'shard':sid,'argv':argv,
                'exitcode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
            save(receipt)
            raise RuntimeError(result.stderr or result.stdout)
        entry = json.loads(result.stdout)
        entry['shard'] = sid
        receipt['submitted'].append(entry)
        save(receipt)
        print(json.dumps(entry),flush=True)
    receipt['dispatch_complete_epoch'] = time.time()
    save(receipt)

if __name__ == '__main__':
    main()
