"""Small exact-recipe read cross-check; no model and no new LMDB."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import time
import refit_lookup as original
from runtime import ROOT,save,sha


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args()
    assert os.getuid()==1278 and os.environ.get('SLURM_JOB_ID')
    assert int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0] in ['compute-0-8','compute-0-9','compute-0-10','compute-0-11']
    out=ROOT/'diagnostics'/args.label/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
    original.initialize_worker('train')
    original._DATASET.cache_bytes=0
    positions=list(range(8))
    positions += [6291456+8192*i for i in range(8)]
    positions += [6291456+65536*i for i in range(1,17)]
    positions += [8388608+i for i in range(8)]+[11000000+i for i in range(8)]
    rows=[]
    try:
        for logical in positions:
            save(out/'progress.json',dict(status='READ_IN_PROGRESS',completed=len(rows),attempting_record=logical,timestamp=time.time()))
            started=time.monotonic();codes,expected,noisy=original.pairs(logical);seconds=time.monotonic()-started
            digest=hashlib.sha256()
            for value in [codes,expected,noisy]:digest.update(value.tobytes())
            rows.append(dict(logical_index=logical,local_pairs=len(expected),seconds=seconds,arrays_sha256=digest.hexdigest()))
        report=dict(status='EXACT_RECIPE_SMALL_READ_PROBE_COMPLETE',job_id=os.environ['SLURM_JOB_ID'],host=socket.gethostname(),rows=rows,
            total_record_read_seconds=sum(r['seconds'] for r in rows),cache_bytes=0,original_recipe_sha256=sha(original.__file__),
            probe_sha256=sha(__file__),no_model_or_optimizer_executed=True,original_LMDB_written=False,new_LMDB_created=False)
        save(out/'result.json',report);print(json.dumps(report),flush=True)
    finally:original._DATASET.close()


if __name__=='__main__':main()
