"""Actual Alpha-allocation streaming SHA verification, strictly after six tests."""
from __future__ import annotations
import concurrent.futures,hashlib,os,socket,stat,threading,time
from pathlib import Path
from .support import load,require,need,save,ref
from .resource_runtime import drain_submit,stop_requested

def hash_one(row):
    p=Path(row['target_reference']['path']);expected=row['target_reference'];before=p.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid==1264 and before.st_size==expected['bytes'],'ACTUAL_ALPHA_BODY_OWNER_SIZE_TYPE')
    started=time.monotonic();digest=hashlib.sha256();count=0
    with p.open('rb') as stream:
        first=os.fstat(stream.fileno());need((first.st_dev,first.st_ino)==(before.st_dev,before.st_ino),'OPENED_SAME_BODY_INODE')
        for block in iter(lambda:stream.read(1<<20),b''):digest.update(block);count+=len(block)
        after=os.fstat(stream.fileno())
    fingerprint=lambda s:[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
    need(fingerprint(first)==fingerprint(after)==fingerprint(p.lstat()),'BODY_IDENTITY_CHANGED_DURING_SHA')
    actual=digest.hexdigest();need(count==expected['bytes'] and actual==expected['sha256'],'EXPECTED_MAIN_BODY_SHA_DIFFERS:'+str(p))
    return {'kind':row['kind'],'origin_reference':row['origin_reference'],'expected_target_reference':expected,
      'actual_target_reference':{'path':str(p),'bytes':count,'sha256':actual},'fstat_before_after':fingerprint(first),
      'pid':os.getpid(),'native_thread_id':threading.get_native_id(),'elapsed_seconds':time.monotonic()-started,'status':'ACTUAL_SHA_PASS'}

def verify_bodies(plan,proof,root,fixture_gate):
    gate=load(require(fixture_gate));need(gate['status']=='PASS' and gate['counts']['run']==6,'SIX_REAL_FIXTURES_REQUIRED_BEFORE_BODY_HASH')
    mapping=load(require(plan['relocation_map_reference']));rows=[r for r in mapping['entries'] if r['kind']!='original_frozen_small_source_or_metadata']
    need(len(rows)==227 and sum(r['target_reference']['bytes'] for r in rows)==2714663309,'EXACT_227_BODY_SET')
    receipts=[];peer=threading.Event();started=time.monotonic()
    output=Path(plan['transfer_verification_expected_output_path']);need(output==Path(root)/'transfer_verification.json','NEW_ACTUAL_HASH_RECEIPT_PATH')
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            drain_submit(rows,executor,hash_one,receipts,stop_requested,peer)
        need(len(receipts)==227,'ALL227_ACTUAL_BODY_HASHES_REQUIRED')
        report={'schema':'ALPHA_LABEL_PAYLOAD512_ACTUAL_BODY_HASH_VERIFICATION_V1','status':'ACTUAL_ALL227_SHA_PASS',
          'endpoint':'218.192.171.238:22','uid':os.getuid(),'node':socket.gethostname().split('.')[0],
          'job_id':str(proof['job_id']),'boot_id':proof['boot_id'],'scope_key':plan['scope_key'],'stage':plan['stage'],
          'source_expected_inventory':plan['origin_inventory_reference'],'relocation_map':plan['relocation_map_reference'],
          'pre_scan_fixture_gate':fixture_gate,'body_count':227,'body_bytes':2714663309,'maximum_hash_workers':16,
          'actual_hash_threads':sorted({r['native_thread_id'] for r in receipts}),'elapsed_seconds':time.monotonic()-started,
          'original_values_parsed_during_hash':False,'records':sorted(receipts,key=lambda r:r['actual_target_reference']['path'])}
        return save(output,report)
    except BaseException as exc:
        save(Path(root)/'transfer_verification_failed.json',{'schema':'ALPHA_LABEL_PAYLOAD512_ACTUAL_BODY_HASH_VERIFICATION_V1',
          'status':'FAILED_NO_PAYLOAD_SCAN_STARTED','error':str(exc),'closed_hash_records':receipts,
          'endpoint':'218.192.171.238:22','uid':os.getuid(),'job_id':str(proof['job_id']),'pre_scan_fixture_gate':fixture_gate})
        raise