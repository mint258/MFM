"""Root-reviewed exact5292 output-only forensic preservation, then local cleanup.
Runs only in a new node14 24CPU Slurm allocation. No QM or formal SCI changes.
"""
from pathlib import Path
import argparse,collections,concurrent.futures,hashlib,json,os,socket,sqlite3,stat,time,traceback,zlib
import wp5_node14_fault_scratch_inspect_v1 as B
import wp5_node14_fault_scratch_plan_v3 as P
ROOT=B.ROOT;F=ROOT/'acceptance/final_20261016_v1';PLAN=F/'node14_5292_scratch_classification_v3.json'
PLAN_SOURCE_SHA='6d07fe2ed128363d47e4b16210166a0ce8b98b9ecf5d772addf47096037eb8e9'
EVIDENCE=ROOT/'evidence/phase15_archive_io_failure/victim4515292_additional50_outputs_v1.sqlite'
RECEIPT=EVIDENCE.with_suffix('.receipt.json')
UID=1278

def sha(path):return P.sha(path)
def ref(path):return P.ref(path)
def publish(path,value):
    if os.path.lexists(path):raise FileExistsError('WRITE_ONCE:'+str(path))
    with Path(path).open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def verified_bytes(item):
    path=Path(item['path']);P.info_same(path,item)
    if not path.is_relative_to(B.SCRATCH) or path.resolve()!=path:raise ValueError('EXACT_OWN_SCRATCH_FILE_PATH_DIFFERS')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd)
        with os.fdopen(fd,'rb',closefd=False) as stream:body=stream.read()
        after=os.fstat(fd)
    finally:os.close(fd)
    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or len(body)!=item['bytes'] or hashlib.sha256(body).hexdigest()!=item['sha256']:raise ValueError('SOURCE_FILE_SHA_OR_IDENTITY_CHANGED:'+str(path))
    return body

def tree_recheck(plan,hash_files):
    expected={row['path']:row for row in plan['all75_files']+plan['all48_directories']};actual={}
    def walk(path):
        m=B.metadata(path)
        if m['uid']!=UID or m['kind'] not in ('file','directory') or m['kind']=='file' and m['nlink']!=1:raise ValueError('SCRATCH_OWNER_LINK_OR_TYPE_DIFFERS')
        actual[str(path)]=m
        if m['kind']=='directory':
            with os.scandir(path) as entries:children=[Path(e.path) for e in entries]
            for child in children:walk(child)
    walk(B.SCRATCH)
    if set(actual)!=set(expected) or len(actual)!=123:raise ValueError('EXACT75_FILE_48_DIRECTORY_SET_CHANGED')
    for path,item in expected.items():
        keys=('kind','uid','device','inode','mode') if item['kind']=='directory' else ('kind','uid','device','inode','mode','nlink','bytes','mtime_ns')
        if any(actual[path][k]!=item[k] for k in keys):raise ValueError('EXACT_SCRATCH_METADATA_IDENTITY_CHANGED:'+path)
    if hash_files:
        def one(item):
            P.info_same(Path(item['path']),item)
            if sha(item['path'])!=item['sha256']:raise ValueError('EXACT_SOURCE_SHA_CHANGED:'+item['path'])
        with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:list(pool.map(one,plan['all75_files']))
    return actual

def compress(item):
    body=verified_bytes(item);frame=zlib.compress(body,9)
    if zlib.decompress(frame)!=body:raise ValueError('COMPRESSION_ROUNDTRIP_FAILED')
    case=item['case'];relative=str(Path(item['path']).relative_to(B.SCRATCH))
    return relative,item,frame,case

def preserve(plan,items,catalog_reference,old_backup):
    pending=EVIDENCE.with_name(EVIDENCE.name+'.pending')
    q=sqlite3.connect(pending)
    try:
        q.execute('PRAGMA journal_mode=DELETE');q.execute('PRAGMA synchronous=FULL')
        q.executescript('CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL) WITHOUT ROWID; CREATE TABLE cases(execution_id TEXT PRIMARY KEY,metadata_json TEXT NOT NULL) WITHOUT ROWID; CREATE TABLE files(relative_path TEXT PRIMARY KEY,execution_id TEXT NOT NULL,name TEXT NOT NULL,bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,compression TEXT NOT NULL,body BLOB NOT NULL) WITHOUT ROWID;')
        metadata={'schema':'WP5_ARCHIVE_IO_FAILURE_FORENSIC_OUTPUT_ONLY_V1','original_job_id':'4515292','original_session':P.SESSION,'source_node':'compute-0-14','classification':'ARCHIVE_IO_FAILURE_PARTIAL_NATIVE_OUTPUT','scientific_status':'UNKNOWN_PARTIAL_NOT_PROMOTED_TO_SCI','input_bodies_saved':False,'SCI_completion_created':False,'formal_population_catalog':catalog_reference,'classification_plan':ref(PLAN),'original_two_member_backup':old_backup,'producer_source':ref(__file__),'producer_job_id':os.environ['SLURM_JOB_ID']}
        for key,value in metadata.items():q.execute('INSERT INTO metadata VALUES(?,?)',(key,json.dumps(value,ensure_ascii=False,allow_nan=False)))
        cases={item['case']['execution_id']:item['case'] for item in items}
        for execution,case in cases.items():q.execute('INSERT INTO cases VALUES(?,?)',(execution,json.dumps(case,sort_keys=True,allow_nan=False)))
        manifest=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
            for relative,item,frame,case in pool.map(compress,items):
                name=Path(item['path']).name
                if name in P.INPUTS or name not in P.OUTPUTS:raise ValueError('INPUT_OR_UNREGISTERED_FILE_FORBIDDEN_IN_FORENSIC_CONTAINER')
                q.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?)',(relative,case['execution_id'],name,item['bytes'],item['sha256'],'zlib9',frame))
                manifest.append({'source_path':item['path'],'relative_path':relative,'name':name,'execution_id':case['execution_id'],'record_id':case['record_id'],'calc_type':case['calc_type'],'bytes':item['bytes'],'sha256':item['sha256'],'scientific_status':'UNKNOWN_PARTIAL_ARCHIVE_IO_FAILURE'})
        q.commit()
        if q.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('FORENSIC_SQLITE_INTEGRITY_FAILED')
        expected={str(Path(i['path']).relative_to(B.SCRATCH)):i for i in items};seen=set()
        for relative,execution,name,n,digest,codec,frame in q.execute('SELECT relative_path,execution_id,name,bytes,sha256,compression,body FROM files'):
            item=expected[relative];body=zlib.decompress(frame)
            if codec!='zlib9' or name in P.INPUTS or len(body)!=n or hashlib.sha256(body).hexdigest()!=digest or body!=verified_bytes(item) or execution!=item['case']['execution_id']:raise ValueError('FORENSIC_FULL_MEMBER_READBACK_DIFFERS')
            seen.add(relative)
        if set(expected)!=seen or len(seen)!=50:raise ValueError('EXACT50_NEW_FORENSIC_MEMBER_SCOPE_DIFFERS')
    finally:q.close()
    fd=os.open(pending,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    pending.rename(EVIDENCE)
    receipt={'schema':'WP5_ADDITIONAL50_PARTIAL_OUTPUT_EVIDENCE_RECEIPT_V1','status':'ALL50_OUTPUT_ONLY_FORENSIC_MEMBERS_SHA_READBACK_VERIFIED','container':ref(EVIDENCE),'metadata':metadata,'members':manifest,'members_verified':50,'input_bodies_saved':False,'SCI_completion_created':False,'production_queue_modified':False,'QM_calls':0,'original_two_member_evidence_unchanged':old_backup,'source':ref(__file__)}
    publish(RECEIPT,receipt);return receipt

def main(args):
    if os.getuid()!=UID or socket.gethostname().split('.')[0]!='compute-0-14' or not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<24:raise ValueError('ACTUAL_NODE14_UID1278_24CPU_SLURM_REQUIRED')
    if not args.execute:raise ValueError('ROOT_REVIEWED_EXPLICIT_EXECUTE_REQUIRED')
    if Path(args.plan)!=PLAN or sha(Path(P.__file__))!=PLAN_SOURCE_SHA:raise ValueError('FROZEN_EXACT_PLAN_AND_SOURCE_REQUIRED')
    destinations=(args.out,EVIDENCE,RECEIPT,EVIDENCE.with_name(EVIDENCE.name+'.pending'))
    if any(os.path.lexists(p) for p in destinations):raise FileExistsError('DESTINATION_EXISTS_DO_NOT_REPLAY_PRESERVATION_OR_CLEANUP')
    if not args.out.resolve().is_relative_to(F):raise ValueError('OWN_FINAL_OUTPUT_DIRECTORY_REQUIRED')
    plan=json.loads(PLAN.read_text())
    if plan.get('status')!='ALL75_CLASSIFIED_PENDING_REQUIRED_OUTPUT_PRESERVATION' or plan.get('unknown_files') or len(plan['all75_files'])!=75 or len(plan['all48_directories'])!=48 or plan['source']!=ref(P.__file__):raise ValueError('ALL75_CLASSIFIED_EXACT_ROOT_PROOF_REQUIRED')
    counts=collections.Counter(r['category'] for r in plan['all75_files'])
    if counts!={'REBUILDABLE_ORIGINAL_INPUT_INDEX_CACHE':1,'INPUT_NOT_RETAINED_BY_EXPLICIT_USER_POLICY':22,'ARCHIVE_IO_FAILURE_OR_AUDIT_PARTIAL_OUTPUT_MUST_PRESERVE':52}:raise ValueError('EXACT_CACHE_INPUT_OUTPUT_CLASSIFICATION_DIFFERS')
    catalog_path=F/'catalog_closed_v2/catalog.json';catalog=json.loads(catalog_path.read_text())
    if catalog['status']!='CLOSED' or catalog['issues'] or catalog['canonical_record_tasks']!=134782248 or catalog['canonical_records']!=11231854 or catalog['canonical_molecules']!=1220466:raise ValueError('FORMAL_POPULATION_ALL12_CATALOG_NOT_CLOSED')
    catalog_reference=ref(catalog_path);account=B.terminal(args.accounting);backup,_=B.backup();tree_recheck(plan,True)
    outputs=[r for r in plan['all75_files'] if r['category']=='ARCHIVE_IO_FAILURE_OR_AUDIT_PARTIAL_OUTPUT_MUST_PRESERVE']
    original_paths={str(B.NATIVE/name) for name in B.EXPECTED};old=[r for r in outputs if r['path'] in original_paths];new=[r for r in outputs if r['path'] not in original_paths]
    if len(old)!=2 or len(new)!=50 or any((r['bytes'],r['sha256'])!=B.EXPECTED[Path(r['path']).name] for r in old):raise ValueError('EXACT2_PLUS50_OUTPUT_BACKUP_SCOPE_DIFFERS')
    args.out.mkdir(parents=True,exist_ok=False);report={'schema':'WP5_EXACT_NODE14_PRESERVE_THEN_CLEAN_V1','created_epoch':time.time(),'actor_job_id':os.environ['SLURM_JOB_ID'],'host':socket.gethostname(),'uid':os.getuid(),'source':ref(__file__),'classification_plan':ref(PLAN),'actual_old_parent':account,'formal_closed_catalog':catalog_reference,'old_backup_before':backup,'files_deleted':[],'directories_removed':[],'scientific_files_or_original_receipts_written':False,'QM_calls':0,'historical_scratch_clean_rewritten':False,'input_bodies_saved':False}
    publish(args.out/'execution_intent.json',report)
    try:
        first_fd=P.fd_review(plan['all75_files']+plan['all48_directories']);report['pre_preservation_FD_review']=first_fd
        if not first_fd['no_unknown_scientific_active_reference']:raise ValueError('UNKNOWN_SCIENTIFIC_OPEN_REFERENCE_BEFORE_PRESERVE')
        evidence=preserve(plan,new,catalog_reference,backup);report['additional_evidence_receipt']=ref(RECEIPT);report['additional_evidence_container']=evidence['container']
        # Deletion can start only after permanent SHA/full decompressed readback.
        tree_recheck(plan,True);B.terminal(args.accounting);after_fd=P.fd_review(plan['all75_files']+plan['all48_directories']);report['pre_delete_FD_review']=after_fd
        if not after_fd['no_unknown_scientific_active_reference']:raise ValueError('UNKNOWN_SCIENTIFIC_OPEN_REFERENCE_BEFORE_UNLINK')
        if B.backup()[0]!=backup:raise ValueError('ORIGINAL_TWO_MEMBER_BACKUP_CHANGED')
        for item in plan['all75_files']:
            path=Path(item['path']);P.info_same(path,item)
            if not path.is_relative_to(B.SCRATCH) or path.resolve()!=path:raise ValueError('UNLINK_PATH_SCOPE_OR_LINK_CHANGED')
            path.unlink();report['files_deleted'].append({'path':str(path),'bytes':item['bytes'],'sha256':item['sha256'],'category':item['category']})
        for item in sorted(plan['all48_directories'],key=lambda r:len(Path(r['path']).parts),reverse=True):
            path=Path(item['path']);now=B.metadata(path)
            if any(now[k]!=item[k] for k in ('kind','uid','device','inode','mode')) or now['kind']!='directory' or not path.is_relative_to(B.SCRATCH):raise ValueError('EMPTY_DIRECTORY_IDENTITY_OR_SCOPE_DIFFERS')
            path.rmdir();report['directories_removed'].append(str(path))
        if os.path.lexists(B.SCRATCH):raise ValueError('EXACT_SCRATCH_ROOT_REMAINS')
        if B.backup()[0]!=backup or ref(EVIDENCE)!=evidence['container'] or sha(catalog_path)!=catalog_reference['sha256']:raise ValueError('PRESERVED_PERMANENT_EVIDENCE_OR_CATALOG_CHANGED')
        report.update(status='EXACT75_FILES_PRESERVED_BY_POLICY_AND_REMOVED_ROOT_ABSENT',exact_root_absent=True,released_local_file_bytes=sum(r['bytes'] for r in report['files_deleted']))
    except BaseException:
        report.update(status='RECORDED_ERROR_NO_SCOPE_EXPANSION',error=traceback.format_exc(limit=12),exact_root_absent=not os.path.lexists(B.SCRATCH));raise
    finally:publish(args.out/'cleanup_report.json',report)
    supplemental={'schema':'WP5_NODE14_FORENSIC_CLEANUP_SUPPLEMENTAL_V1','status':report['status'],'source':ref(__file__),'classification_plan':ref(PLAN),'old_evidence_container':backup['container'],'old_evidence_receipt':backup['receipt'],'new_evidence_container':ref(EVIDENCE),'new_evidence_receipt':ref(RECEIPT),'cleanup_report':ref(args.out/'cleanup_report.json'),'all52_output_members_covered':True,'inputs22_archived':False,'cache_permanent_backup_required':False,'SCI_modified':False,'QM_calls':0}
    publish(args.out/'final_supplemental_refs.json',supplemental)
    print(json.dumps({'status':report['status'],'deleted_files':len(report['files_deleted']),'removed_empty_directories':len(report['directories_removed']),'released_local_bytes':report['released_local_file_bytes'],'exact_root_absent':True,'new_output_members':50,'total_output_members_covered':52,'inputs_archived':0,'supplemental':str(args.out/'final_supplemental_refs.json')}))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--accounting',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--execute',action='store_true');main(p.parse_args())
