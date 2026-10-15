"""Diagnose mount-local device IDs independently of original record identity."""
import concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,socket,time
from pathlib import Path
from prepare import ROOT,save,sha

def check(task):
    import lmdb
    sid,shard,records=task;path=Path(shard['path']);stat=path.stat()
    current=[stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns];expected=shard['identity']
    assert current[1:]==expected[1:],{'source':str(path),'expected':expected,'actual':current}
    checked=[]
    with lmdb.open(str(path),subdir=False,readonly=True,create=False,lock=False,readahead=False,meminit=False) as env:
        with env.begin() as tx:
            assert hashlib.sha256(tx.get(b'__len__')).hexdigest()==shard['length_header_sha256']
            assert tx.stat()['entries']==shard['entries']
            for row in records:
                prefix,key=row['record_id'].rsplit(':',1);assert prefix==path.name
                raw=tx.get(f'{int(key):09d}'.encode())
                assert raw is not None and hashlib.sha256(raw).hexdigest()==row['payload_sha256'],'ACTUAL_RECORD_MANIFEST_MISMATCH'
                checked.append(row['record_id'])
        assert env.info()['last_txnid']==shard['last_txnid']
    after=path.stat();assert [after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns]==current
    return {'shard_id':sid,'path':str(path),'expected_from_compute2':expected,'actual_on_node':current,
            'mount_device_id_equal':current[0]==expected[0],'inode_bytes_mtime_equal':True,
            'length_header_entries_transaction_equal':True,'actual_payload_SHA_verified_record_ids':checked}

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    start=time.time();snapshot_path=ROOT/'training_inputs_v1/shard_snapshot_v1.json';snapshot=json.loads(snapshot_path.read_text())
    checks_path=ROOT/'training_inputs_v1/native_read_checks.json';records=json.loads(checks_path.read_text())['records']
    tasks=[(sid,shard,[r for r in records if r['record_id'].rsplit(':',1)[0]==Path(shard['path']).name]) for sid,shard in snapshot['shards'].items()]
    assert sum(len(t[2]) for t in tasks)==len(records)
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn')) as pool:results=list(pool.map(check,tasks))
    save(ROOT/'reports/cross_node_native_identity_v1.json',{'status':'PORTABLE_NATIVE_IDENTITY_AND_PAYLOADS_PASS','job_id':os.environ['SLURM_JOB_ID'],
        'hostname':socket.gethostname(),'shard_snapshot_sha256':sha(snapshot_path),'native_read_checks_sha256':sha(checks_path),
        'effective_processes':16,'actual_payload_SHA_verified_records':len(records),'results':results,
        'original_lmdb_written':False,'new_lmdb_created':False,'optimizer_updates':0,
        'interpretation':'st_dev is mount-local metadata. Compare portable inode/bytes/mtime plus LMDB header/transaction and raw record SHA across nodes; retain local st_dev for diagnostics.',
        'elapsed_seconds':time.time()-start})
    print(json.dumps({'status':'PORTABLE_NATIVE_IDENTITY_AND_PAYLOADS_PASS','records':len(records),'mount_device_differences':sum(not r['mount_device_id_equal'] for r in results)}),flush=True)

if __name__=='__main__':main()
