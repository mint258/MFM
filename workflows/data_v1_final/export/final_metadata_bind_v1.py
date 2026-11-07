"""Bind closed D3 and immutable D5 indexes using small metadata only."""
import csv,fcntl,hashlib,io,json,os,pathlib,subprocess,tempfile

R=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
FORMAL=R/'repository/configs/data_v1/v1-pilot-provisional'
D3=FORMAL/'D3_export.json'
D5=FORMAL/'D5_diagnostic_payload.json'
LOCK=R/'control/root_data_v1_sequential_submit.lock'
VERSION='v1-pilot-provisional'
COUNTS={'TRAIN':50000,'VAL':5000}

def need(value,message):
    if not value:raise ValueError(message)

def reference(path,data):
    return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

def read_json(path,expected=None):
    path=pathlib.Path(path)
    need(path.is_absolute() and '..' not in path.parts and path.suffix=='.json' and not path.is_symlink(),'LITERAL_JSON_METADATA_ONLY')
    before=path.stat();need(before.st_uid==1278,'OWN_FORMAL_METADATA_REQUIRED')
    data=path.read_bytes();after=path.stat()
    need((before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),'UNCHANGED_SMALL_METADATA_READ')
    if expected is not None:need(reference(path,data)==expected,'FORMAL_METADATA_REFERENCE_BYTES_SHA_MATCH')
    return json.loads(data),data

def formal_json(ref):
    need(isinstance(ref,dict) and set(ref)=={'path','bytes','sha256'},'THREE_FIELD_FORMAL_REFERENCE_REQUIRED')
    return read_json(ref['path'],ref)[0]

def canonical(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()

def atomic_write(path,data,replace=False):
    fd,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.pending',dir=path.parent)
    temporary=pathlib.Path(name)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        if replace:os.replace(temporary,path)
        else:os.link(temporary,path);temporary.unlink()
        directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        if temporary.exists():temporary.unlink()

def accounting(job):
    argv=['sacct','-X','-j',job,'--parsable2','--format=JobIDRaw,State,ExitCode,UID,AllocCPUS,NodeList']
    result=subprocess.run(argv,capture_output=True,text=True)
    need(result.returncode==0,'ACTUAL_NATIVE_SACCT_REQUIRED')
    rows=[row for row in csv.DictReader(io.StringIO(result.stdout),delimiter='|') if row['JobIDRaw']==job]
    need(len(rows)==1,'EXACT_ONE_ACTUAL_D3_PARENT')
    fields=('JobIDRaw','State','ExitCode','UID','AllocCPUS','NodeList')
    row={field:rows[0][field] for field in fields}
    need(row==dict(JobIDRaw=job,State='COMPLETED',ExitCode='0:0',UID='1278',AllocCPUS='16',NodeList='compute-0-8'),
         'D3_ACTUAL_COMPLETED_ZERO_UID1278_16CPU_NODE8_REQUIRED')
    return row

def bind():
    need(os.getuid()==1278,'MAIN_ACCOUNT_UID1278_REQUIRED')
    with LOCK.open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        d3,d3_bytes=read_json(D3);d5,d5_bytes=read_json(D5)
        need(d3['version']==d5['version']==VERSION,'SAME_PROVISIONAL_RELEASE_REQUIRED')
        job=str(d3['actual_parent_job_id']);need(job.isdecimal(),'ACTUAL_D3_JOB_ID_REQUIRED')
        native=accounting(job)
        need(d3['actual_root_C0_wrapper'] is True and d3['status']=='DELIVERED_PENDING_MODEL_LOADER_AND_HEAD_OVERFIT','ORIGINAL_FORMAL_D3_PUBLICATION_REQUIRED')
        need(all(str(d3['actual_parent_accounting'][key])==value for key,value in native.items()),'FORMAL_INDEX_AND_ACTUAL_NATIVE_PARENT_AGREE')
        receipt_ref=d3['actual_export_receipt_reference'];receipt=formal_json(receipt_ref)
        manifest_ref=d3['manifest_reference'];manifest=formal_json(manifest_ref)
        need(receipt['schema']=='BOUNDED_PILOT_FAMILY_D3_RECEIPT_V1' and str(receipt['job_id'])==job
             and receipt['uid']==1278 and receipt['actual_cpus']==16 and receipt['node']=='compute-0-8','SAME_CLOSED_D3_RECEIPT_PARENT')
        need(receipt['manifest_reference']==receipt['verification_reference']==d3['verification_reference']==manifest_ref,'SINGLE_ORIGINAL_D3_MANIFEST_BINDING')
        need(receipt['pilot_counts']==d3['pilot_counts']==manifest['pilot_counts']==COUNTS and manifest['version']==VERSION,'ORIGINAL_FULL55K_COUNTS_REQUIRED')
        need(receipt['export_and_single1000_complete'] is True and receipt['source_roundtrip_records']==d3['source_roundtrip_records']==manifest['source_roundtrip_records']==1000,'ORIGINAL_SINGLE1000_QA_COMPLETED')
        need(manifest['schema']=='D3_SINGLE_EXPORT_MANIFEST_V1' and manifest['single_final_count_and_source_sample_pass'] is True
             and all(manifest[key] is False for key in ('independent_replay','independent_16reader_pass','full_F64_second_scan','domain_numerical_self_comparison')),
             'ORIGINAL_ONCE_COUNT_AND_NO_INDEPENDENT_REPLAY_MARKERS')
        distribution=receipt['distribution']
        need(d3['distribution']==distribution and distribution['status']=='COPIED_WITH_RSYNC_CHECKSUM'
             and distribution['checksum_method']=='rsync --checksum' and distribution['transfer']['returncode']==0,'ORIGINAL_CHECKSUM_DISTRIBUTION_COMPLETE')
        need(d3['pilot_acceptance_reference']==receipt['pilot_acceptance_reference']==d5['pilot_acceptance_reference'],'SAME_FROZEN_PILOT_TRAIN_ACCEPTANCE_REQUIRED')
        need(all(value[key] is False for value in (d3,d5) for key in ('Model_ACK','Model_payload_ACK')),'MODEL_ACCEPTANCE_REMAINS_PENDING')
        need(d5['role']=='TRAIN_UNSEEN_CONFORMATION' and d5['training_excluded'] is True and d5['actual_seen_D5_intersection_MIDs']==893
             and d5['selected_geometries']==12502 and d5['frozen_D3_selected_TRAIN_MIDs']==50000,'UNCHANGED_ORIGINAL_D5_DIAGNOSTIC_SCOPE')
        d5_qa=formal_json(d5['verification_reference'])
        need(d5_qa['available_label_records']==43757 and len(d5['store_references'])==len(d5_qa['store_counts'])==53,'ORIGINAL_D5_METADATA_COUNTS_RETAINED')
        original=reference(D5,d5_bytes);bound_path=FORMAL/('D5_diagnostic_payload_D3_job'+job+'_bound.json')
        current=d3['D5_diagnostic_payload_reference']
        need(current==original or current.get('path')==str(bound_path),'NO_OTHER_D5_COMPONENT_VERSION_MAY_BE_OVERWRITTEN')
        bound=dict(d5,actual_D3_seen_TRAIN_MIDs=50000,actual_D3_seen_status='ACTUAL_D3_PAYLOAD_CLOSED_SAME_FROZEN_TRAIN_ROSTER',
            actual_D3_parent_job_id=job,actual_D3_manifest_reference=manifest_ref,actual_D3_receipt_reference=receipt_ref,
            actual_D3_parent_accounting=native,original_D5_component_reference=original,
            available_label_records=d5_qa['available_label_records'],closed_store_count=len(d5['store_references']))
        # No D3_export.json reference is embedded in bound D5: there is no cycle.
        if bound_path.exists():
            existing,bound_bytes=read_json(bound_path)
            need(existing==bound,'EXISTING_BOUND_D5_MUST_BE_IDENTICAL_SAME_ACTUAL_PARENT')
        else:
            need(current==original,'DANGLING_OR_DIFFERENT_BOUND_VERSION_NOT_REPLACED')
            bound_bytes=canonical(bound);atomic_write(bound_path,bound_bytes)
        bound_ref=reference(bound_path,bound_bytes)
        need(current in (original,bound_ref),'EXACT_EXISTING_D5_REFERENCE_REQUIRED')
        updated=dict(d3,D5_diagnostic_payload_reference=bound_ref)
        need(D3.read_bytes()==d3_bytes and D5.read_bytes()==d5_bytes,'FORMAL_INDEXES_UNCHANGED_BEFORE_ATOMIC_BIND')
        changed=current!=bound_ref
        if changed:atomic_write(D3,canonical(updated),replace=True)
        return dict(status='D3_D5_SMALL_METADATA_BOUND',actual_D3_job_id=job,changed=changed,
            D5_diagnostic_payload_reference=bound_ref,actual_D3_seen_TRAIN_MIDs=50000,Model_ACK=False)

if __name__=='__main__':print(json.dumps(bind(),sort_keys=True))
