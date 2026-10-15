"""Preserve exactly one partial native-output incident, never a completed SCI receipt.
No inputs, production queue, SCI payload, labels, or LMDB are read or modified.
"""
from __future__ import annotations
import argparse,hashlib,json,os,sqlite3,stat,tempfile,time,zlib
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
RUN=ROOT/'runtime/task_cleanup_14/job_4515292_38e2d502'
SCRATCH=Path('/tmp/wp5runtime_1278_4515292_38e2d502/wp5_4515292_38e2d502/lane_16/wp4native_1278_4515292_872wlefa')
RID='principal_00600001_00900000.lmdb:950624'
SESSION='38e2d50265f7495da715fa3c93ba9dd4'
CLASS='ARCHIVE_IO_FAILURE_PRESERVED_NATIVE_OUTPUT'

def digest(data):return hashlib.sha256(data).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def reference(path):
    path=Path(path);data=path.read_bytes()
    return {'path':str(path),'bytes':len(data),'sha256':digest(data)}
def checked_bytes(path,limit):
    path=Path(path)
    for item in [path,*path.parents]:
        if item==Path('/tmp'):break
        info=item.lstat()
        if info.st_uid!=1278 or stat.S_ISLNK(info.st_mode):raise ValueError('SOURCE_OWNER_OR_LINK_DIFFERS:'+str(item))
    before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size>limit:raise ValueError('SOURCE_TYPE_OR_SIZE_DIFFERS:'+str(path))
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        opened=os.fstat(fd)
        if (opened.st_dev,opened.st_ino)!=(before.st_dev,before.st_ino):raise ValueError('SOURCE_OPEN_IDENTITY_DIFFERS')
        with os.fdopen(fd,'rb',closefd=False) as stream:data=stream.read(limit+1)
        after=os.fstat(fd)
    finally:os.close(fd)
    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or len(data)!=before.st_size:raise ValueError('SOURCE_CHANGED_DURING_READ')
    return data,{'path':str(path),'bytes':len(data),'sha256':digest(data),'uid':before.st_uid,'inode':before.st_ino,'mtime_ns':before.st_mtime_ns}

def write_evidence(path,metadata,members):
    path=Path(path);fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    q=sqlite3.connect(path)
    try:
        q.execute('PRAGMA journal_mode=DELETE');q.execute('PRAGMA synchronous=FULL')
        q.execute('CREATE TABLE evidence(evidence_id TEXT PRIMARY KEY,classification TEXT NOT NULL,metadata_json TEXT NOT NULL) WITHOUT ROWID')
        q.execute('CREATE TABLE files(name TEXT PRIMARY KEY,bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,compression TEXT NOT NULL,body BLOB NOT NULL) WITHOUT ROWID')
        q.execute('INSERT INTO evidence VALUES(?,?,?)',(metadata['execution_id'],CLASS,canonical(metadata)))
        for name,data in members.items():q.execute('INSERT INTO files VALUES(?,?,?,?,?)',(name,len(data),digest(data),'zlib9',zlib.compress(data,9)))
        q.commit()
        readback=[]
        for name,length,expected,codec,frame in q.execute('SELECT name,bytes,sha256,compression,body FROM files ORDER BY name').fetchall():
            data=zlib.decompress(frame)
            if codec!='zlib9' or data!=members[name] or len(data)!=length or digest(data)!=expected:raise ValueError('EVIDENCE_SHA_READBACK_DIFFERS')
            readback.append({'name':name,'bytes':length,'sha256':expected,'SHA_readback_verified':True})
        if q.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('EVIDENCE_INTEGRITY_CHECK_FAILED')
        saved=json.loads(q.execute('SELECT metadata_json FROM evidence').fetchone()[0])
        if saved!=metadata:raise ValueError('EVIDENCE_METADATA_READBACK_DIFFERS')
    finally:q.close()
    fd=os.open(path,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return readback

def check():
    # Private evidence format only; no production path, source queue, or native output.
    with tempfile.TemporaryDirectory(prefix='wp5_partial_evidence_private_') as tmp:
        path=Path(tmp)/'evidence.sqlite';meta={'execution_id':'private:partial','scope_status':None,'converged':None}
        members={'RAW_ARCHIVE_FAILURE_PRESERVE.json':b'{"partial":true}','process.out':b'private partial output'}
        rows=write_evidence(path,meta,members)
        assert {row['name'] for row in rows}==set(members)
    print(json.dumps({'status':'PARTIAL_EVIDENCE_COMPRESSION_SHA_READBACK_PRIVATE_PASS','input_bodies_saved':False,'SCI_completion_created':False,'production_path_read':False}))

def main(args):
    if os.getuid()!=1278 or os.uname().nodename!='compute-0-14':raise ValueError('ACTUAL_UID1278_NODE14_REQUIRED')
    observed_path=ROOT/'reports/observation_latest.json';observed_bytes=observed_path.read_bytes();observation=json.loads(observed_bytes)
    if observation.get('uid')!=1278 or observation.get('hostname')!='sonmi' or observation.get('sacct',{}).get('returncode')!=0 or time.time()-observation['time']>180:raise ValueError('FRESH_ACTUAL_ACCOUNTING_REQUIRED')
    state=observation.get('registered_job_states',{}).get('4515292')
    if state not in {'COMPLETED','FAILED','CANCELLED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY','PREEMPTED'}:raise ValueError('SOURCE_JOB_NOT_PROVEN_TERMINAL')
    run_path=RUN/'run.json';run=json.loads(run_path.read_text());options=run['options']
    if str(options['job_id'])!='4515292' or options['session']!=SESSION:raise ValueError('SOURCE_RUN_ID_DIFFERS')
    marker,marker_ref=checked_bytes(SCRATCH/'RAW_ARCHIVE_FAILURE_PRESERVE.json',65536)
    output,output_ref=checked_bytes(SCRATCH/'process.out',4153)
    if len(output)!=4153:raise ValueError('EXPECTED_ORIGINAL_PROCESS_OUT_4153_BYTES')
    details=json.loads(marker)
    if details.get('record_id')!=RID or details.get('task')!='xtb_singlepoint' or not details.get('execution_id','').startswith(SESSION+':16:1:'):raise ValueError('EXACT_INCIDENT_MARKER_DIFFERS')
    bound={}
    for key in ('production_contract','reproduction_package','audit_membership'):
        item=reference(options[key]);expected=options.get(key+'_sha256')
        if item['sha256']!=expected:raise ValueError('ORIGINAL_PROVENANCE_SHA_DIFFERS:'+key)
        bound[key]=item
    dictionary_manifest=reference(options['dictionaries'])
    original_dict_ref=next(item for item in options['source_bindings'] if item['path']==options['dictionaries'])
    if dictionary_manifest['sha256']!=original_dict_ref['sha256']:raise ValueError('ORIGINAL_DICTIONARY_MANIFEST_DIFFERS')
    dictionaries=json.loads(Path(options['dictionaries']).read_text())['dictionaries']
    task_dictionary=next(item for item in dictionaries if item['calc_type']=='xtb_singlepoint')
    actual_dictionary=reference(task_dictionary['path'])
    if actual_dictionary['sha256']!=task_dictionary['sha256']:raise ValueError('ORIGINAL_TASK_DICTIONARY_DIFFERS')
    target=Path(args.out)
    if target.suffix!='.sqlite' or not target.resolve().is_relative_to((ROOT/'evidence/phase15_archive_io_failure').resolve()):raise ValueError('OWNED_NEW_EVIDENCE_OUTPUT_SCOPE_REQUIRED')
    target.parent.mkdir(parents=True,exist_ok=True)
    metadata={'schema':'WP5_PARTIAL_NATIVE_OUTPUT_EVIDENCE_V1','classification':CLASS,'record_id':RID,'calc_type':'xtb_singlepoint',
      'execution_id':details['execution_id'],'original_job_id':'4515292','original_session':SESSION,'source_node':'compute-0-14',
      'original_run':reference(run_path),'original_provenance':bound,'dictionary_manifest':dictionary_manifest,'task_dictionary':actual_dictionary,
      'source_members':[marker_ref,output_ref],'accounting_snapshot':{'path':str(observed_path),'bytes':len(observed_bytes),'sha256':digest(observed_bytes),'observed_epoch':observation['time']},'source_job_state':state,
      'scope_status':None,'scientific_status':'UNKNOWN_NOT_RECONSTRUCTED_FROM_PARTIAL_MARKER','scf_iterations':None,'converged':None,
      'SCI_completion_created':False,'input_bodies_saved':False,'inputs_read':False,'source_scratch_deleted':False,
      'QM_started':False,'original_LMDB_opened':False,'production_queue_modified':False,'created_epoch':time.time()}
    members={'RAW_ARCHIVE_FAILURE_PRESERVE.json':marker,'process.out':output}
    verified=write_evidence(target,metadata,members)
    report={'schema':'WP5_PARTIAL_NATIVE_OUTPUT_EVIDENCE_RECEIPT_V1','status':'PARTIAL_NATIVE_OUTPUT_EVIDENCE_SHA_READBACK_VERIFIED',
      'container':reference(target),'source':reference(Path(__file__)),'metadata':metadata,'members':verified,
      'source_scratch_retained':True,'SCI_completion_created':False,'queue_modified':False,'QM_started':False}
    receipt=target.with_suffix('.receipt.json')
    with receipt.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'status':report['status'],'receipt':str(receipt),'container':report['container'],'members':verified,'source_scratch_retained':True}))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--out',type=Path);args=parser.parse_args()
    if args.check:check()
    elif args.out is None:parser.error('--out required')
    else:main(args)
