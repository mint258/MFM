"""Read-only SHA256 pinning of a bounded list of pre-existing data inputs."""
from __future__ import annotations
import argparse, concurrent.futures, datetime, hashlib, json, os
from pathlib import Path
import socket, stat, threading, time


def reference(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8<<20), b''): h.update(block)
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':h.hexdigest()}


def pin_file(item):
    path=Path(item['path']); before=path.stat()
    assert path.is_absolute() and not path.is_symlink() and stat.S_ISREG(before.st_mode)
    assert before.st_size==item['bytes']
    began=time.monotonic(); result=reference(path); after=path.stat()
    assert (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
    if item.get('sha256') is not None: assert result['sha256']==item['sha256'], 'Known immutable source SHA differs'
    def identity(s):return {'device':s.st_dev,'inode':s.st_ino,'size':s.st_size,'mtime_ns':s.st_mtime_ns,'uid':s.st_uid}
    return {'name':item['name'],'reference':result,'before':identity(before),'after':identity(after),'stable_file_identity':{'dev':after.st_dev,'ino':after.st_ino,'mtime_ns':after.st_mtime_ns},'seconds':time.monotonic()-began,'worker_thread_id':threading.get_native_id()}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True,type=Path);p.add_argument('--root-intent',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-20' and os.environ.get('SLURM_JOB_ID')
    assert int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    c=json.loads(a.config.read_text());intent=json.loads(a.root_intent.read_text());q=intent['request']
    assert c['schema']=='DATA_V1_SOURCE_PIN_PREPARATION_V1' and 1<=len(c['inputs'])<=16
    assert reference(a.config) in q['source_references'] and reference(Path(__file__).absolute()) in q['source_references']
    age=time.time()-datetime.datetime.fromisoformat(intent['observed_at']).timestamp();assert 0<=age<=3600
    assert q['kind']=='analysis' and q['node']=='compute-0-20' and q['root_review']['status']=='APPROVED'
    assert intent['account_free_bytes']-q['estimated_peak_output_bytes']>=200000000000
    allowed=Path(c['external_output_root']); assert allowed.is_absolute() and a.output.is_absolute() and a.output==a.output.resolve() and a.output.is_relative_to(allowed)
    a.output.parent.mkdir(parents=True,exist_ok=True); assert not a.output.exists()
    began=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool: results=list(pool.map(pin_file,c['inputs']))
    report={'schema':'DATA_V1_SOURCE_PIN_RECEIPT_V1','status':'ALL_BOUND_INPUTS_SHA_VERIFIED','job_id':os.environ['SLURM_JOB_ID'],'node':socket.gethostname(),'config':reference(a.config),'root_intent':reference(a.root_intent),'outputs':results,'input_bytes_read':sum(x['reference']['bytes'] for x in results),'elapsed_seconds':time.monotonic()-began,'allocated_cpus':int(os.environ['SLURM_CPUS_PER_TASK']),'actual_hash_threads':len({x['worker_thread_id'] for x in results}),'input_files_modified':False,'scope':'SHA and stable file identity only; no scientific parsing or selection acceptance'}
    payload=json.dumps(report,indent=2).encode()+b'\n';assert len(payload)<=32*1024**2
    with a.output.open('xb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
    print(json.dumps({'status':report['status'],'receipt':reference(a.output),'input_files':len(results)}))


if __name__=='__main__':main()
