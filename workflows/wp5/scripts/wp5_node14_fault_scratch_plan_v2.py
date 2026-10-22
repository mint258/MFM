"""Classify all exact5292 scratch files; read-only, no deletion/backup/QM."""
from pathlib import Path
import argparse,collections,concurrent.futures,hashlib,json,os,re,socket,sqlite3,stat,time
import wp5_node14_fault_scratch_inspect_v1 as B
ROOT=B.ROOT;F=ROOT/'acceptance/final_20261016_v1';BASE=F/'node14_5292_scratch_inspection_v1.json'
BASE_SHA='a466d9c9e9acf2c44550f76f7abcf13b2c7b85e22981767d5bc5645e1d7aff86b'
RUN=ROOT/'runtime/task_cleanup_14/job_4515292_38e2d502';SESSION='38e2d50265f7495da715fa3c93ba9dd4'
INPUTS={'input.xyz','input.mop','native.inp'}
OUTPUTS={'RAW_ARCHIVE_FAILURE_PRESERVE.json','process.out','input.aux','input.out','input.arc','input.end'}
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8<<20),b''):h.update(block)
    return h.hexdigest()
def ref(path):return {'path':str(path),'bytes':Path(path).stat().st_size,'sha256':sha(path)}
def checked(ref_value):
    if ref(ref_value['path'])!={k:ref_value[k] for k in ('path','bytes','sha256')}:raise ValueError('BOUND_REFERENCE_CHANGED')
def info_same(path,item):
    now=B.metadata(path)
    if any(now[k]!=item[k] for k in ('kind','uid','device','inode','bytes','mtime_ns','mode','nlink')):raise ValueError('EXACT_SCRATCH_ENTRY_CHANGED:'+str(path))
def fd_review(entries):
    own=os.getpid();ancestors=set();pid=own
    while pid>0 and pid not in ancestors:
        ancestors.add(pid)
        try:s=(Path('/proc')/str(pid)/'status').read_text();pid=int(re.search(r'^PPid:\s*(\d+)',s,re.M).group(1))
        except (FileNotFoundError,AttributeError):break
    inodes={(r['device'],r['inode']) for r in entries};matched=[];unknown=[];excluded=[];examined=[]
    services={}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            if p.stat().st_uid!=1278:continue
            text=(p/'status').read_text();comm=(p/'comm').read_text().strip();cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace');parent=int(re.search(r'^PPid:\s*(\d+)',text,re.M).group(1));services[int(p.name)]={'pid':int(p.name),'ppid':parent,'comm':comm,'cmdline':cmd}
        except FileNotFoundError:continue
    for pid,row in services.items():
        p=Path('/proc')/str(pid);reason=None
        if pid in ancestors:reason='THIS_READ_ONLY_INSPECTOR_AND_ITS_ACTUAL_SSH_ANCESTORS'
        elif row['comm']=='systemd' and row['cmdline'].strip()=='/usr/lib/systemd/systemd --user':reason='IDENTIFIED_OS_USER_SESSION_MANAGER_NOT_A_SCIENCE_WORKER'
        elif row['comm']=='(sd-pam)' and services.get(row['ppid'],{}).get('comm')=='systemd':reason='IDENTIFIED_OS_PAM_SESSION_HELPER_NOT_A_SCIENCE_WORKER'
        if reason:excluded.append({**row,'reason':reason});continue
        examined.append(row)
        try:
            for special in ('cwd','root'):
                target=os.readlink(p/special)
                if target==str(B.SCRATCH) or target.startswith(str(B.SCRATCH)+'/'):matched.append({**row,'kind':special,'target':target})
            with os.scandir(p/'fd') as handles:paths=[e.path for e in handles]
            for handle in paths:
                try:
                    target=os.readlink(handle);st=os.stat(handle)
                    if target.removesuffix(' (deleted)')==str(B.SCRATCH) or target.removesuffix(' (deleted)').startswith(str(B.SCRATCH)+'/') or (st.st_dev,st.st_ino) in inodes:matched.append({**row,'kind':'fd','fd':Path(handle).name,'target':target})
                except FileNotFoundError:continue
        except FileNotFoundError:continue
        except PermissionError as error:unknown.append({**row,'error':str(error)})
    return {'self_and_SSH_ancestor_pids':sorted(ancestors),'excluded_identified_control_processes':excluded,'other_same_UID_processes_examined':examined,'matching_references':matched,'unknown_process_or_permission_errors':unknown,'no_unknown_scientific_active_reference':not matched and not unknown,'exclusion_policy':'Only actual inspector/SSH ancestry and explicitly identified OS user-manager/PAM controls are excluded. Unknown business/scientific processes are inspected; permission failures block readiness.'}
def main(args):
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-14':raise ValueError('EXACT_NODE14_UID1278_ONLY')
    if sha(BASE)!=BASE_SHA:raise ValueError('EXACT_BASE_INSPECTION_CHANGED')
    baseline=json.loads(BASE.read_text());entries=baseline['entries'];files=[r for r in entries if r['kind']=='file']
    if len(files)!=75 or len(entries)!=123 or baseline['scope_or_type_issues']:raise ValueError('EXACT75_SCOPE_REQUIRED')
    for r in entries:info_same(Path(r['path']),r)
    if sha(RUN/'run.json')!='0e2c91a4d9d83b390e7f15f27837e06e08a73d557aba0a860f3772ddaec0adeb':raise ValueError('ORIGINAL_RUN_METADATA_CHANGED')
    run=json.loads((RUN/'run.json').read_text());options=run['options']
    if options['session']!=SESSION or str(options['job_id'])!='4515292' or options['local_index']!=str(B.SCRATCH/'record_index.sqlite'):raise ValueError('EXACT_ORIGINAL_RUN_CACHE_IDENTITY_DIFFERS')
    backup_proof,old_member_bytes=B.backup();account=B.terminal(args.accounting)
    source_bindings={r['path']:r['sha256'] for r in options['source_bindings']};rebuild=[]
    for key in ('plan','assignments','source_plan','protocol'):
        path=Path(options[key]);actual=ref(path)
        if source_bindings.get(str(path))!=actual['sha256']:raise ValueError('ORIGINAL_REBUILD_INPUT_SOURCE_CHANGED:'+key)
        rebuild.append({'role':key,**actual})
    index_meta=json.loads((RUN/'input_index.json').read_text());cache=B.SCRATCH/'record_index.sqlite';q=sqlite3.connect('file:'+str(cache)+'?mode=ro',uri=True)
    try:
        tables=[r[0] for r in q.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        columns=[r[1] for r in q.execute('PRAGMA table_info(rows)')];count=q.execute('SELECT count(*) FROM rows').fetchone()[0]
        if tables!=['rows'] or columns!=['molecule_id','payload'] or count!=index_meta['molecules'] or cache.stat().st_size!=index_meta['bytes']:raise ValueError('REBUILDABLE_INPUT_INDEX_SHAPE_DIFFERS')
    finally:q.close()
    folders=sorted({Path(r['path']).parent for r in files if Path(r['path']).name=='RAW_ARCHIVE_FAILURE_PRESERVE.json'});cases={}
    for folder in folders:
        marker=json.loads((folder/'RAW_ARCHIVE_FAILURE_PRESERVE.json').read_text());lane=int(folder.parent.name.removeprefix('lane_'));execution=marker['execution_id']
        if not execution.startswith(SESSION+':'+str(lane)+':') or not re.fullmatch(r'[^:]+:\d+:[01]:[a-f0-9]{32}',execution):raise ValueError('PARTIAL_MARKER_ORIGINAL_EXECUTION_DIFFERS')
        cases[str(folder)]={'record_id':marker['record_id'],'calc_type':marker['task'],'execution_id':execution,'lane':lane,'marker':ref(folder/'RAW_ARCHIVE_FAILURE_PRESERVE.json'),'scientific_status':'UNKNOWN_PARTIAL_NATIVE_OUTPUT_ARCHIVE_IO_FAILURE','SCI_completion_created':False}
    import pyarrow.dataset as ds
    audit=json.loads(Path(options['audit_membership']).read_text())
    if sha(options['audit_membership'])!=options['audit_membership_sha256']:raise ValueError('ORIGINAL_FIXED_AUDIT_CHANGED')
    selected=audit['selected_records'];checked(selected)
    selected_ids={r['record_id'] for r in ds.dataset(selected['path'],format='parquet').to_table(filter=ds.field('record_id').isin([c['record_id'] for c in cases.values()]),columns=['record_id'],use_threads=False).to_pylist()}
    from wp5_archive_v5 import ArchiveReader
    archive_path=RUN/'raw_archive.sqlite';reader=ArchiveReader(archive_path,options['dictionaries']) if archive_path.exists() else None;raw_values={};raw_errors={}
    try:
        for key,case in cases.items():
            case['fixed_audit_selected']=case['record_id'] in selected_ids
            if reader:
                try:
                    raw=reader.get(case['record_id'],case['calc_type'],case['execution_id']);raw_values[key]=raw
                    case['existing_exact_execution_raw']={'container':str(archive_path),'raw_sha256':raw['raw_sha256'],'scope_status':raw['scope_status'],'input_bodies_saved':raw['input_bodies_saved'],'output_members':raw['original_output_manifest']}
                except KeyError:case['existing_exact_execution_raw']=None
                except Exception as error:raw_errors[key]=repr(error);case['existing_exact_execution_raw']=None
    finally:
        if reader:reader.close()
    def hash_item(item):
        p=Path(item['path']);digest=sha(p);info_same(p,item);return (item['path'],digest)
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:hashes=dict(pool.map(hash_item,files))
    classified=[];new_evidence=[];unknown=[];archive_used=False
    for item in files:
        p=Path(item['path']);record={**item,'sha256':hashes[item['path']]}
        if p==cache:record.update(category='REBUILDABLE_ORIGINAL_INPUT_INDEX_CACHE',deletion_requires_backup=False,proof={'original_run':ref(RUN/'run.json'),'input_index':ref(RUN/'input_index.json'),'sqlite_tables':tables,'sqlite_columns':columns,'input_molecule_rows':count,'frozen_rebuild_inputs':rebuild})
        elif p.name in INPUTS and str(p.parent) in cases:record.update(category='INPUT_NOT_RETAINED_BY_EXPLICIT_USER_POLICY',deletion_requires_backup=False,case=cases[str(p.parent)],input_body_not_saved=True)
        elif p.name in OUTPUTS and str(p.parent) in cases:
            record.update(category='ARCHIVE_IO_FAILURE_OR_AUDIT_PARTIAL_OUTPUT_MUST_PRESERVE',deletion_requires_backup=True,case=cases[str(p.parent)])
            if p.parent==B.NATIVE and p.name in old_member_bytes and len(old_member_bytes[p.name])==item['bytes'] and hashlib.sha256(old_member_bytes[p.name]).hexdigest()==record['sha256']:record['existing_backup']={'kind':'PERMANENT_INCIDENT_EVIDENCE','container':backup_proof['container'],'member':p.name}
            else:
                raw=raw_values.get(str(p.parent));matches=[m for m in (raw or {}).get('output_files',[]) if m['name']==p.name and len(m['data'])==item['bytes'] and hashlib.sha256(m['data']).hexdigest()==record['sha256']]
                if len(matches)==1:record['existing_backup']={'kind':'EXACT_SAME_EXECUTION_RAW_MEMBER','container':str(archive_path),'execution_id':cases[str(p.parent)]['execution_id'],'member':p.name,'member_sha256':record['sha256']};archive_used=True
                else:record['existing_backup']=None;new_evidence.append(record)
        else:record['category']='UNKNOWN_PRESERVE_DO_NOT_DELETE';unknown.append(record)
        classified.append(record)
    fds=fd_review(entries);counts=collections.Counter(r['category'] for r in classified);report={'schema':'WP5_EXACT_NODE14_ALL75_SCRATCH_CLASSIFICATION_V2','status':'ALL75_CLASSIFIED_PENDING_REQUIRED_OUTPUT_PRESERVATION' if not unknown and fds['no_unknown_scientific_active_reference'] else 'ROOT_REVIEW_REQUIRED','created_epoch':time.time(),'host':socket.gethostname(),'uid':os.getuid(),'source':ref(__file__),'base_inspection':ref(BASE),'exact_root':str(B.SCRATCH),'actual_parent_accounting':account,'all75_files':classified,'all48_directories':[e for e in entries if e['kind']=='directory'],'category_counts':dict(counts),'partial_native_contexts':list(cases.values()),'fixed_audit':ref(options['audit_membership']),'ordinary_success_non_audit_outputs_proven_droppable':0,'unknown_files':unknown,'existing_incident_backup':backup_proof,'existing_original_raw_archive':ref(archive_path) if archive_used else {'path':str(archive_path),'used_as_backup':False},'exact_execution_raw_lookup_errors':raw_errors,'new_required_evidence_files':new_evidence,'new_required_evidence_bytes':sum(r['bytes'] for r in new_evidence),'input_bodies_to_backup':0,'rebuildable_cache_backup_required':False,'fd_review':fds,'execution_plan':'First preserve only new_required_evidence_files to a fresh incident output-only container with per-member SHA readback, no SCI receipt. Recheck all exact75 inode/owner/type/SHA and original terminal/FD guards, then unlink the explicit75 files under their policy/proof categories and rmdir only the exact48 empty directories deepest-first. No recursive deletion, no other root, no permanent SCI/receipt writes.','files_deleted':0,'containers_created':0,'new_QM_calls':0,'production_queue_modified':False,'historical_scratch_clean_rewritten':False}
    if args.out.exists() or not args.out.resolve().is_relative_to(F):raise ValueError('OWN_WRITE_ONCE_FINAL_REPORT_REQUIRED')
    with args.out.open('x') as f:json.dump(report,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
    print(json.dumps({'report':str(args.out),'status':report['status'],'categories':dict(counts),'partial_contexts':len(cases),'fixed_audit_contexts':sum(c['fixed_audit_selected'] for c in cases.values()),'new_required_evidence_files':len(new_evidence),'new_required_evidence_bytes':report['new_required_evidence_bytes'],'unknown_files':len(unknown),'FD_review':fds,'files_deleted':0,'containers_created':0}))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--accounting',type=Path,required=True);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
