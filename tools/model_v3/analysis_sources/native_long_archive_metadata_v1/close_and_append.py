"""Root metadata closure and reviewed append-only entry for explicit Native long archive batches."""
from __future__ import annotations
import argparse,fcntl,hashlib,importlib.util,json,os,socket,stat,subprocess,sys,time
from pathlib import Path,PureWindowsPath
sys.dont_write_bytecode=True
P=Path('/share/home/zixiao/descriptor_analysis');N=P/'runs/model_v3_20261026';O=P/'runs/model_v3_20261025'
ARCH=P/'runs/phase1_full_corpus/wandb_archive';DEST=ARCH/'model_v3_20261025';ENTRY=P/'W&B_训练记录.html'
HERE=Path(__file__).absolute().parent;ARCHIVER=N/'native_closed_long_archive_v1'
ARCHIVE_PIN='2ad22f85ba5b6ada63c686dc652ef017721f1aef306cf13c5cf7480e68c73cac'

def require(ok,message):
    if not ok:raise ValueError(message)
def physical(path):
    path=Path(path);a=path.lstat()
    require(path.is_absolute() and path==path.resolve(strict=True) and stat.S_ISREG(a.st_mode)
        and a.st_uid==1278 and a.st_nlink==1,'Owned physical ordinary file required: '+str(path))
    return a
def ref(path):
    path=Path(path);a=physical(path);require(a.st_size<=16<<20,'Bounded source/aggregate/page/image required')
    data=path.read_bytes();b=physical(path)
    require((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'Metadata changed during binding')
    return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def read(path):
    original=ref(path)
    def pairs(items):
        result={}
        for key,value in items:require(key not in result,'Duplicate metadata key');result[key]=value
        return result
    result=json.loads(Path(path).read_bytes(),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite metadata')))
    require(ref(path)==original,'Metadata changed during read');return result
def bound(raw):
    require(set(raw)=={'path','bytes','sha256'} and ref(raw['path'])==raw,'Bound raw metadata differs')
    return read(raw['path'])
def stat_only(raw):
    a=physical(raw['path']);require(a.st_size==raw['bytes'],'Current payload size differs from worker-bound reference')
    return dict(path=raw['path'],bytes=a.st_size,uid=a.st_uid,device=a.st_dev,inode=a.st_ino,mtime_ns=a.st_mtime_ns,
        expected_SHA_from_closed_worker=raw.get('sha256'),payload_opened=False,Root_independent_content_SHA_verified=False)
def write(path,value):
    data=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    require(len(data)<=1<<20,'Finite Root metadata cap exceeded')
    with Path(path).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    return ref(path)
def sources(pin):
    own=ref(HERE/'source_pins.json');require(own['sha256']==pin,'Closer source inventory differs')
    for row in bound(own)['files']:
        require(ref(HERE/row['file'])==dict(path=str(HERE/row['file']),bytes=row['bytes'],sha256=row['sha256']),'Closer source changed')
    deps=read(HERE/'dependencies.json')
    for raw in deps.values():require(ref(raw['path'])==raw,'Frozen original archive dependency differs')
    require(deps['archive_sources']['sha256']==ARCHIVE_PIN,'Only exact supported generic archive family admitted')
    spec=importlib.util.spec_from_file_location('closed_long_archive_metadata_producer',ARCHIVER/'archive_closed_long.py')
    producer=importlib.util.module_from_spec(spec);sys.modules[spec.name]=producer;spec.loader.exec_module(producer)
    archive_source,old,common=producer.sources(ARCHIVE_PIN)
    return own,producer,archive_source,common
def actual_parent(job,node):
    argv=['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,User,State,ExitCode,AllocCPUS,NodeList,ElapsedRaw']
    actual=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45,check=False)
    rows=[line.split('|') for line in actual.stdout.splitlines() if line.strip()]
    require(actual.returncode==0 and len(rows)==1 and rows[0][:6]==[job,'zixiao','COMPLETED','0:0','16',node]
        and int(rows[0][6])>=0,'Actual archive parent C0/UID/16CPU/node missing')
    return dict(argv=argv,returncode=actual.returncode,stdout=actual.stdout,stderr=actual.stderr)
def collect(inputs,producer,archive_source,common):
    request=bound(inputs['request']);submission=bound(inputs['submission']);frame=bound(inputs['prepared_receipt'])
    result=bound(inputs['result']);supervisor=bound(inputs['supervisor']);index=bound(inputs['index'])
    job=str(submission['job_id']);node=submission['node'];root=Path(frame['archive_root'])
    require(job.isdigit() and submission['schema']=='model_v3_single_CPU_submission_v1'
        and submission['sbatch_returncode']==0 and submission['cpus']==16 and submission['requested_memory_MiB']==16384,
        'Exact immediate16CPU16GiB archive submission required')
    require(request['schema']=='native_S_explicit_closed_synced_archive_request_v1' and root==DEST/request['archive_name']
        and root.name.startswith('native_long_') and frame['schema']=='native_S_Root_closed_long_archive_quota_v1'
        and frame['request']==inputs['request'] and frame['source_pins']==archive_source,
        'Actual request/prepared producer/output binding differs')
    bindings=submission['bindings']
    require(bindings['MODEL_V3_CLOSED_LONG_ARCHIVE_RECEIPT']==inputs['prepared_receipt']['path']
        and bindings['MODEL_V3_CLOSED_LONG_ARCHIVE_RECEIPT_SHA']==inputs['prepared_receipt']['sha256']
        and bindings['MODEL_V3_CLOSED_LONG_ARCHIVE_PIN']==ARCHIVE_PIN
        and bindings['MODEL_V3_CLOSED_LONG_ARCHIVE_OUTPUT']==str(root),'Actual submission bindings differ')
    script=O/'run_native_closed_long_archive_v1.sbatch'
    require(submission['argv'][-1]==str(script) and ref(script)['sha256']==submission['script_sha256'],'Actual archive wrapper differs')
    expected=['/share/home/zixiao/.conda/envs/chemprop/bin/python','-u','-B',str(ARCHIVER/'archive_closed_long.py'),
        '--source-pins-sha256',ARCHIVE_PIN,'run','--expected-node',node,'--root-receipt',inputs['prepared_receipt']['path'],
        '--root-receipt-sha256',inputs['prepared_receipt']['sha256']]
    require(supervisor['job_id']==job and supervisor['status']=='COMPLETED' and supervisor['exit_code']==0
        and supervisor['first_failure'] is None and supervisor['remaining']==[] and supervisor['retirement'] is None
        and supervisor['command']==expected and supervisor['launch_identity']['uid']==1278
        and supervisor['launch_identity']['slurm_job_id']==job
        and supervisor['private_storage']['first_sampling_failure'] is None and supervisor['last_total_bytes']<2<<30,
        'Actual same-job original CPU supervisor/private cleanup differs')
    for path,sha in supervisor['sources_sha256'].items():require(ref(path)['sha256']==sha,'Supervision source changed')
    require(result['schema']=='native_S_explicit_closed_long_archive_result_v1'
        and result['status']=='ARCHIVED_EXPLICIT_CLOSED_SYNCED_LONG_PENDING_ACTUAL_CPU_C0'
        and result['actual_job_id']==job and result['source_pins']==archive_source and result['Root_receipt']==inputs['prepared_receipt']
        and result['metadata_tests']==dict(tests=4,failures=0,errors=0,skipped=0)
        and result['SDK_decoder_executed'] is False and result['online_sync_performed'] is False
        and result['scientific_acceptance'] is False and result['old_indexes_rewritten'] is False
        and result['archive_cap_bytes']==256<<20,'Exact generic archive result differs')
    require(index['schema']=='native_S_explicit_closed_long_append_archive_index_v1' and index['entries']==result['entries']
        and index['source_pins']==archive_source and index['old_indexes_rewritten'] is False
        and index['scientific_acceptance'] is False and index['online_sync_performed_by_this_archive'] is False
        and index['preserved_indexes']==result['preserved_indexes']==frame['preserved_indexes'],
        'Exact new append-only index differs')
    proof_rows=common.proof_rows(request['entries']) # Frozen metadata-only validator; no SDK open/normalize/decoder.
    canonical=frame['entries'];records=index['entries']
    require(1<=len(records)<=3 and len(canonical)==len(proof_rows)==len(records)
        and len({r['run_id'] for r in records})==len(records)
        and [r['run_id'] for r in records]==[r['run_id'] for r in canonical]==[r['run_id'] for r in proof_rows],
        'Exact dynamic1..3 membership differs')
    prior_ids=set()
    for raw in frame['preserved_indexes']:prior_ids.update(row['run_id'] for row in bound(raw)['entries'])
    require(not prior_ids.intersection(r['run_id'] for r in records),'New archive duplicates original index membership')
    test_log=Path(inputs['metadata_tests']['path']).read_text()
    require(ref(inputs['metadata_tests']['path'])==inputs['metadata_tests'] and 'Ran 4 tests' in test_log
        and test_log.rstrip().endswith('OK'),'Actual original four export regressions not closed')
    sync=bound(request['sync_Root_closure'])
    require(sync['schema']=='native_S_explicit_sync_Root_closure_v1' and sync['status']=='ROOT_CLOSED_C0_METADATA_VERIFIED'
        and sync['active_runs_included'] is False and sync['old_indexes_or_source_SDK_modified'] is False,'Root sync closure differs')
    payload=[];manifests=[]
    for row,entry,proved in zip(records,canonical,proof_rows,strict=True):
        parent=ARCH/row['path'];require(parent.is_relative_to(root) and row['manifest']['path']==str(parent/'manifest.json'),
            'New archive member path escapes actual root')
        manifest=bound(row['manifest']);proof=bound(entry['certificate'])
        require(manifest['schema']=='native_S_closed_synced_long_local_archive_v1'
            and all(manifest[key]==value for key,value in entry.items()) and manifest['source_pins']==archive_source
            and manifest['SDK_decoder_executed'] is False and manifest['online_sync_performed_by_this_archive'] is False
            and manifest['scientific_acceptance'] is False and row['job_id']==entry['job_id']
            and row['history_rows']==entry['rows']==proved['history_rows']
            and proved['native_exit_code']==0 and proved['original_model_status']=='COMPLETED'
            and entry['sdk']==proof['sdk'] and entry['mirror']==proof['mirror']
            and manifest['normalized_history_bytes']==proof['history']['normalized_history_bytes']
            and manifest['normalized_history_sha256']==proof['history']['normalized_history_sha256'],
            'Member manifest/canonical/proof/source scope differs')
        matching=[r for r in sync['records'] if r['run_id']==row['run_id']]
        require(len(matching)==1 and matching[0]['action']=='SYNCED_EXACT_COPY_AND_API_VERIFIED'
            and matching[0]['original_SDK_raw_ref_from_sync_job']==entry['sdk']
            and matching[0]['actual_remote_metadata']['history_rows']==entry['rows']
            and matching[0]['actual_remote_metadata']['state']=='finished','Selected synced SDK/history identity differs')
        for label in ('certificate','audit_batch','audit_supervisor','actual_audit_C0','model_terminal','configuration','sync_Root_closure'):
            copied=ref(parent/(label+'.original.json'))
            require((copied['bytes'],copied['sha256'])==(entry[label]['bytes'],entry[label]['sha256']),'Copied metadata certificate differs')
        payload.extend((stat_only(entry['sdk']),stat_only(entry['mirror']),
            stat_only(dict(path=str(parent/'source_history.jsonl'),bytes=entry['mirror']['bytes'],sha256=entry['mirror']['sha256'])),
            stat_only(dict(path=str(parent/'history.normalized.jsonl'),bytes=manifest['normalized_history_bytes'],
                           sha256=manifest['normalized_history_sha256']))))
        for item in manifest['source_files']:
            relative=Path(item['relative_path']);require(not relative.is_absolute() and '..' not in relative.parts,'Copied SDK path escapes')
            copied=parent/'wandb'/Path(entry['sdk']['path']).parent.name/relative
            payload.extend((stat_only(dict(path=item['read_path'],bytes=item['bytes'],sha256=item['sha256'])),
                            stat_only(dict(path=str(copied),bytes=item['bytes'],sha256=item['sha256']))))
        for name in ('metrics.csv','last_metrics.json','index.html'):require(physical(parent/name).st_size>0,'Readable export missing/empty')
        manifests.append(row['manifest'])
    count,total=0,0
    for parent,dirs,files in os.walk(root,followlinks=False):
        for name in dirs:
            st=(Path(parent)/name).lstat();require(stat.S_ISDIR(st.st_mode) and st.st_uid==1278,'Archive directory not physical/owned')
        for name in files:
            count+=1;total+=physical(Path(parent)/name).st_size
            require(count<=2048 and total<=256<<20,'Actual archive file count/256MiB cap exceeded')
    proposal=bound(inputs['append_proposal'])
    require(proposal['schema']=='native_S_Root_closed_long_archive_entry_proposal_v1' and proposal['entry_path']==str(ENTRY)
        and proposal['unique_marker']=='data-model-v3-'+request['archive_name'] and proposal['preserve_all_prior_bytes'] is True
        and proposal['apply_only_after_actual_archive_parent_C0_and_Root_visual_review'] is True
        and proposal['old_indexes_may_be_rewritten'] is False,'Exact original append proposal differs')
    actual=actual_parent(job,node)
    return dict(actual_accounting=actual,job_id=job,archive_root=str(root),entries=len(records),
        scientific_history_rows=sum(r['history_rows'] for r in records),records=records,manifest_refs=manifests,
        current_archive_file_bytes=total,current_archive_files=count,current_payload_stat_observations=payload,
        Root_independent_SDK_or_journal_content_rehash=False,SDK_or_journal_payload_opened=False,
        content_hash_evidence='Original same-source C0 worker copy/hash/normalization before-after evidence; Root current payload stat only',
        preserved_indexes=frame['preserved_indexes'],old_indexes_rewritten=False,scientific_acceptance=False)
def close(args,pin,producer,archive_source,common):
    request_ref=ref(args.request);submission_ref=ref(args.submission)
    require(request_ref['sha256']==args.request_sha256 and submission_ref['sha256']==args.submission_sha256,'Explicit actual input SHA differs')
    submission=bound(submission_ref);bindings=submission['bindings']
    prepared=ref(bindings['MODEL_V3_CLOSED_LONG_ARCHIVE_RECEIPT'])
    require(prepared['sha256']==bindings['MODEL_V3_CLOSED_LONG_ARCHIVE_RECEIPT_SHA'],'Actual prepared receipt SHA differs')
    root=Path(bindings['MODEL_V3_CLOSED_LONG_ARCHIVE_OUTPUT'])
    inputs=dict(request=request_ref,submission=submission_ref,prepared_receipt=prepared,result=ref(root/'RESULT.json'),
        supervisor=ref(Path(str(root)+'.supervisor.json')),index=ref(root/'index.json'),
        append_proposal=ref(root/'UNIFIED_ENTRY_APPEND_PROPOSAL.json'),metadata_tests=ref(root/'metadata_tests.log'))
    collected=collect(inputs,producer,archive_source,common)
    output=Path(args.output);require(output.parent==N and not output.exists(),'Fresh immediate N Root evidence directory required')
    before=ref(ENTRY);require(before['bytes']<=1<<20,'Bounded unified entry required')
    output.mkdir(mode=0o700)
    value=dict(schema='native_S_closed_long_archive_Root_metadata_closure_v1',
        status='ACTUAL_ARCHIVE_C0_METADATA_CLOSED_VISUAL_REVIEW_PENDING',inputs=inputs,source_pins=pin,
        unified_entry_before=before,unified_entry_modified=False,visual_review_not_yet_claimed=True,
        expected_visual_review_schema='native_S_closed_long_archive_Root_visual_review_v1',
        producer_source=ref(__file__),created_unix=time.time(),**collected)
    raw=write(output/'CLOSURE.json',value);print(json.dumps(dict(status=value['status'],closure=raw)))
def visual(raw,closure):
    review=bound(raw);records=closure['records']
    require(review['schema']=='native_S_closed_long_archive_Root_visual_review_v1'
        and review['status']=='ALL_EXPLICIT_DEFAULT_CURVE_PAGES_RENDERED_AND_INSPECTED'
        and str(review['archive_job_id'])==closure['job_id'] and review['archive_result']==closure['inputs']['result']
        and review['request']==closure['inputs']['request'] and review['no_scientific_adoption'] is True
        and type(review['review_scope']) is str and bool(review['review_scope'])
        and len(review['entries'])==len(records)
        and {r['run_id'] for r in review['entries']}=={r['run_id'] for r in records},'Actual exact-list Root visual review required')
    def path(value):
        if value.startswith('/'):return Path(value)
        windows=PureWindowsPath(value)
        require(windows.drive.upper() in ('X:','Y:'),'Only verified same-project Windows aliases admitted')
        return P/windows.relative_to(windows.anchor).as_posix()
    by_id={r['run_id']:r for r in records}
    for item in review['entries']:
        page,image=path(item['page_path']),path(item['screenshot_path'])
        require(page==ARCH/by_id[item['run_id']]['path']/'index.html' and image.is_relative_to(N)
            and image.suffix.lower()=='.png' and item['rendered_and_visually_inspected'] is True
            and ref(page)==dict(path=str(page),bytes=item['page_bytes'],sha256=item['page_sha256'])
            and ref(image)==dict(path=str(image),bytes=item['screenshot_bytes'],sha256=item['screenshot_sha256']),
            'Reviewed actual page/screenshot raw bytes changed')
    return review
def append(args,pin,producer,archive_source,common):
    raw=ref(args.closure);require(raw['sha256']==args.closure_sha256,'Root closure SHA differs');closure=bound(raw)
    require(closure['schema']=='native_S_closed_long_archive_Root_metadata_closure_v1'
        and closure['status']=='ACTUAL_ARCHIVE_C0_METADATA_CLOSED_VISUAL_REVIEW_PENDING'
        and closure['source_pins']==pin and closure['producer_source']==ref(__file__),'Actual same-source Root closure required')
    collected=collect(closure['inputs'],producer,archive_source,common)
    require(collected['records']==closure['records'],'Closed explicit archive membership changed')
    review_ref=ref(args.visual_review);require(review_ref['sha256']==args.visual_review_sha256,'Root visual review SHA differs')
    review=visual(review_ref,closure);proposal=bound(closure['inputs']['append_proposal'])
    output=Path(raw['path']).parent;require(output.parent==N,'Original immediate N evidence directory required')
    backup=output/'UNIFIED_ENTRY_BEFORE.html';application=output/'APPEND_ACTUAL.json'
    require(not backup.exists() and not application.exists() and ref(ENTRY)==closure['unified_entry_before'],
        'Fresh append/backup and unchanged original entry required; no blind retry')
    marker=proposal['unique_marker'].encode();addition=proposal['html'].encode()
    require(len(addition)<=4096 and addition.count(marker)==1,'Exactly one bounded original proposal marker required')
    fd=os.open(ENTRY,os.O_RDWR|os.O_APPEND|os.O_NOFOLLOW)
    with os.fdopen(fd,'r+b') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB);before=stream.read();identity=os.fstat(stream.fileno())
        require(ref(ENTRY)==closure['unified_entry_before'] and marker not in before,'Entry changed/marker already exists')
        with backup.open('xb') as f:f.write(before);f.flush();os.fsync(f.fileno())
        require(backup.read_bytes()==before,'Entire original entry backup differs')
        for original in closure['preserved_indexes']:bound(original)
        require(os.write(stream.fileno(),addition)==len(addition),'Incomplete append; preserve actual evidence, no retry')
        os.fsync(stream.fileno());stream.seek(0);after=stream.read();observed=os.fstat(stream.fileno())
        require(after==before+addition and after.startswith(before) and after.count(marker)==1
            and (identity.st_dev,identity.st_ino)==(observed.st_dev,observed.st_ino),'Exact prefix/inode/single-marker invariant failed')
        for original in closure['preserved_indexes']:bound(original)
    result=dict(schema='native_S_closed_long_archive_Root_entry_append_actual_v1',
        status='EXACT_PRIOR_PREFIX_BACKED_UP_AND_SINGLE_PROPOSAL_APPENDED',job_id=closure['job_id'],
        closure=raw,source_pins=pin,visual_review=review_ref,visual_review_scope=review['review_scope'],
        entry_before=closure['unified_entry_before'],entry_backup=ref(backup),entry_after=ref(ENTRY),
        appended_proposal=closure['inputs']['append_proposal'],append_bytes=len(addition),
        old_indexes_rewritten=False,old_entry_prefix_preserved=True,online_state_changed=False,
        scientific_acceptance=False,producer_source=ref(__file__),created_unix=time.time())
    receipt=write(application,result);print(json.dumps(dict(status=result['status'],application=receipt)))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-pins-sha256',required=True)
    sub=p.add_subparsers(dest='mode',required=True);s=sub.add_parser('close')
    for name in ('request','request-sha256','submission','submission-sha256','output'):s.add_argument('--'+name,required=True)
    s=sub.add_parser('append')
    for name in ('closure','closure-sha256','visual-review','visual-review-sha256'):s.add_argument('--'+name,required=True)
    args=p.parse_args();require(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi','Root login metadata operation only')
    pin,producer,archive_source,common=sources(args.source_pins_sha256)
    if args.mode=='close':close(args,pin,producer,archive_source,common)
    else:append(args,pin,producer,archive_source,common)
if __name__=='__main__':main()

