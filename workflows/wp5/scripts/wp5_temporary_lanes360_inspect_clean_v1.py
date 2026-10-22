"""Exact360 historical temporary lane inspection; optional Root-enabled empty cleanup.
No QM, SCI/raw decoding, permanent archive/receipt/queue writes, or Slurm calls.
"""
from pathlib import Path
import argparse,collections,concurrent.futures,hashlib,importlib.util,json,os,re,socket,sqlite3,stat,subprocess,sys,time,traceback
from urllib.parse import quote
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
F=ROOT/'acceptance/final_20261016_v1'
SCOPE=F/'temporary_lanes360_scope_prepared_v1.json'
SCOPE_SHA='70f59b1c42940282c85b4c89cb08060b4ac69e821c9d351d0263c62af52676d0'
KEYS=('device','inode','uid','gid','mode','nlink','bytes','mtime_ns','kind')
def require(value,message):
    if not value:raise ValueError(message)
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()
def ref(p):return {'path':str(p),'bytes':Path(p).stat().st_size,'sha256':digest(p)}
def checked(r,load_json=False):
    actual=ref(r['path']);require(re.fullmatch('[0-9a-f]{64}',r['sha256']) is not None and actual['sha256']==r['sha256'] and ('bytes' not in r or actual['bytes']==r['bytes']),'BOUND_METADATA_CHANGED:'+r['path'])
    return json.loads(Path(r['path']).read_text()) if load_json else None
def info(p):
    s=Path(p).lstat();return {'path':str(p),'device':s.st_dev,'inode':s.st_ino,'uid':s.st_uid,'gid':s.st_gid,'mode':s.st_mode,'nlink':s.st_nlink,'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'kind':'directory' if stat.S_ISDIR(s.st_mode) else 'file' if stat.S_ISREG(s.st_mode) else 'UNSUPPORTED'}
def same(p,old,keys=KEYS):
    now=info(p);require(now['path']==old['path'] and all(now[k]==old[k] for k in keys),'IDENTITY_CHANGED:'+str(p));return now
def dump_new(p,value):
    with p.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def canon(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sql_normal(value):return ''.join(value.upper().split()).replace('IFNOTEXISTS','').rstrip(';')
def dir_shape(case,old=None):
    p=Path(case['temporary_directory']);r=info(p);require(r['kind']=='directory' and r['uid']==1278,'EXACT_TEMPORARY_DIR_OWNER_TYPE_REQUIRED')
    require(p.parent==Path(case['run_metadata']['path']).parent and p.name=='temporary_lanes','EXACT_TEMPORARY_PARENT_REQUIRED')
    for parent in (p.parent,p.parent.parent):
        x=info(parent);require(x['kind']=='directory' and x['uid']==1278,'ORIGINAL_RUN_PARENT_LINK_OR_OWNER_DIFFERS')
    with os.scandir(p) as it:actual={e.path for e in it}
    require(actual=={e['path'] for e in case['files']},'UNKNOWN_SIDECAR_OR_FILE_IN_TEMPORARY_LANES')
    if old is not None:same(p,old)
    return r

def inspect_one(item):
    file,context,ddl,tables,payload=item;p=Path(file['path']);result={'path':str(p),'original_parent_job_id':context['job_id'],'worker_pid':os.getpid(),'status':'PRESERVE_DO_NOT_DELETE','eligible_empty_payload':False,'issues':[]}
    try:
        before=info(p);result['file_identity']=before;require(before['kind']=='file' and before['uid']==1278 and before['nlink']==1 and before['bytes']==file['bytes']==36864,'EXACT_FILE_TYPE_OWNER_SIZE_OR_LINK_DIFFERS')
        for suffix in ('-journal','-wal','-shm'):require(not os.path.lexists(str(p)+suffix),'SQLITE_SIDECAR_PRESENT')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
        try:require(os.read(fd,16)==bytes.fromhex('53514c69746520666f726d6174203300'),'SQLITE_HEADER_DIFFERS')
        finally:os.close(fd)
        before_sha=digest(p);result['file_sha256']=before_sha;db=sqlite3.connect('file:'+quote(str(p),safe='/')+'?mode=ro&immutable=1',uri=True,timeout=30)
        try:
            db.execute('PRAGMA query_only=ON');master=[dict(zip(('type','name','tbl_name','sql'),r)) for r in db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name')];result['sqlite_master']=master
            names={r['name'] for r in master if r['type']=='table' and not r['name'].startswith('sqlite_')};result['user_tables']=sorted(names)
            counts={};columns={}
            for name in sorted(names):
                quoted='"'+name.replace('"','""')+'"';counts[name]=db.execute('SELECT count(*) FROM '+quoted).fetchone()[0];columns[name]=[list(x) for x in db.execute('PRAGMA table_info('+quoted+')')]
            result.update(table_row_counts=counts,table_columns=columns,all_user_tables_zero=all(n==0 for n in counts.values()))
            require(names==set(tables),'UNKNOWN_OR_MISSING_USER_TABLE')
            expected={}
            for statement in ddl.split(';'):
                if statement.strip():
                    name=re.search(r'CREATE TABLE IF NOT EXISTS\s+(\w+)',statement,re.I).group(1);expected[name]=sql_normal(statement)
            require(all(sql_normal(row['sql'])==expected[row['name']] for row in master if row['type']=='table'),'USER_SCHEMA_DIFFERS_FROM_FROZEN_ARCHIVE5')
            require(all(row['type']=='table' or (row['type']=='index' and row['sql'] is None and row['name'].startswith('sqlite_autoindex_')) for row in master),'UNKNOWN_TRIGGER_VIEW_OR_USER_INDEX')
            metadata_rows=[list(r) for r in db.execute('SELECT key,value FROM metadata ORDER BY key')];dict_rows=[list(r) for r in db.execute('SELECT dict_id,calc_type,sha256,path FROM dictionaries ORDER BY dict_id')];result.update(initialization_metadata_rows=metadata_rows,initialization_dictionary_rows=dict_rows,metadata_rows_canonical_sha256=hashlib.sha256(canon(metadata_rows)).hexdigest(),dictionary_rows_canonical_sha256=hashlib.sha256(canon(dict_rows)).hexdigest(),header_row_encoding='Canonical UTF8 JSON; all original field values retained')
            schema_only=all(counts[name]==0 for name in names)
            if not schema_only:
                meta=dict(metadata_rows);expected_meta=context['expected_metadata'];require(set(meta)==set(expected_meta)|{'zstd_version'},'UNKNOWN_OR_MISSING_METADATA_KEY')
                require(all(meta[k]==v for k,v in expected_meta.items()),'ORIGINAL_RUN_INITIALIZATION_METADATA_DIFFERS')
                require(isinstance(meta['zstd_version'],str) and re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}(?:[-+._A-Za-z0-9]*)?',meta['zstd_version']) is not None and len(meta['zstd_version'])<=64,'UNKNOWN_ZSTD_VERSION_HEADER')
                require(dict_rows==context['expected_dictionary_rows'],'PERMANENT_DICTIONARY_MANIFEST_INITIALIZATION_DIFFERS')
            result['payload_table_row_counts']={name:counts[name] for name in payload};require(all(counts[name]==0 for name in payload),'NONZERO_SCIENTIFIC_OR_RAW_PAYLOAD_RETAIN_ALL')
        finally:db.close()
        same(p,before);after_sha=digest(p);require(before_sha==after_sha,'SQLITE_CHANGED_DURING_READ_ONLY_INSPECTION');result.update(file_sha256=after_sha,status='EMPTY_SCHEMA_ONLY' if schema_only else 'EMPTY_OF_SCIENTIFIC_AND_RAW_PAYLOAD',eligible_empty_payload=True,SQLite_open_flags='mode=ro&immutable=1; query_only=ON',scientific_or_raw_frames_decoded=False)
    except BaseException as error:result['issues'].append(repr(error));result['traceback']=traceback.format_exc()
    return result

def open_dir(path):
    p=Path(path);require(p.is_absolute() and '..' not in p.parts,'EXACT_ABSOLUTE_PATH_REQUIRED');fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for part in p.parts[1:]:
            nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=nxt
        return fd
    except BaseException:os.close(fd);raise

def main(a):
    require(os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-17','EXACT_NODE17_UID1278_REQUIRED');require(os.environ.get('SLURM_JOB_ID','').isdigit() and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=24,'24CPU_SLURM_REQUIRED');require(a.out.is_absolute() and a.out.parent==F and not a.out.exists(),'FRESH_OWN_FINAL_OUTPUT_REQUIRED');require(digest(SCOPE)==SCOPE_SHA,'EXACT360_SCOPE_CHANGED');scope=json.loads(SCOPE.read_text());require(scope['file_count']==360 and scope['parent_count']==15 and len(scope['cases'])==15,'EXACT_360_15_REQUIRED')
    for key in ('archive5','archive4','reused_fd_guard','storage3','node_authority'):checked(scope[key])
    for r in scope['original_runner_sources']:checked(r)
    failed=checked(scope['failed_shared_storage_report'],True);require(failed['status']=='NOT_PASS' and failed['issues']==[{'issue':'UNRETIRED_RUNTIME_TEMPORARIES','files':360}] and failed['standalone_calculation_files']==[],'EXACT593_FAILED_EVIDENCE_REQUIRED')
    mapping=checked(scope['formal542_jobmap'],True);jobs={str(r['job_id']):r for r in mapping['jobs']};account=checked(scope['original541_accounting'],True);require(account['sacct_returncode']==0 and account['job_count']==541,'ACTUAL541_TERMINAL_ACCOUNTING_REQUIRED');arows={v.split('|')[0]:dict(zip(account['fields'],v.strip().split('|'))) for v in account['sacct_stdout'].splitlines() if v.strip()}
    spec=importlib.util.spec_from_file_location('wp5_exact9_guard_reuse',scope['reused_fd_guard']['path']);guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    node_reports=[]
    for r in scope['six_node_report_references']:
        document=checked(r,True);node_reports.append(document)
    spec2=importlib.util.spec_from_file_location('wp5_storage3_guard_reuse',scope['storage3']['path']);storage=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(storage);storage.validate_node_report_docs(node_reports,jobs,scope['formal542_jobmap']['sha256'],scope['node_authority']['sha256'],scope['storage3']['sha256'])
    all_files=[];contexts={};dirs={}
    for case in scope['cases']:
        run=checked(case['run_metadata'],True);o=run['options'];job=case['job_id'];require(str(o['job_id'])==job and str(o['task_id'])==case['task_id'] and o['session']==case['session'] and run['node']==case['original_node'],'ORIGINAL_RUN_IDENTITY_DIFFERS');require(jobs[job]['node']==run['node'] and str(jobs[job]['task_id'])==case['task_id'],'FORMAL542_SCOPE_DIFFERS');require(arows[job]==case['actual_original_terminal_accounting'] and arows[job]['User']=='zixiao' and arows[job]['State'] in ('COMPLETED','FAILED'),'ACTUAL_ORIGINAL_TERMINAL_PARENT_DIFFERS')
        binds={r['path']:r['sha256'] for r in o['source_bindings']};require(binds.get(case['original_runner_source']['path'])==case['original_runner_source']['sha256'] and binds.get(scope['archive5']['path'])==scope['archive5']['sha256'],'ORIGINAL_RUN_SOURCE_BINDING_DIFFERS');header={}
        for r in case['initializer_manifest_references']:
            checked(r);require(o[r['role']]==r['path'] and binds.get(r['path'])==r['sha256'],'ORIGINAL_INITIALIZATION_MANIFEST_BINDING_DIFFERS');header[r['role']]=r
        dictionary=json.loads(Path(header['dictionaries']['path']).read_text());expected_dict=sorted([[r['dict_id'],r['calc_type'],r['sha256'],r['path']] for r in dictionary['dictionaries']]);require(len(expected_dict)==12 and len({r[0] for r in expected_dict})==12,'EXACT12_INITIALIZED_DICTIONARIES_REQUIRED')
        expected={'format':'WP5_OUTPUT_ONLY_DICT_ZSTD_V2','policy':o['policy'],'audit_seed':'20261010','input_bodies_saved':'false','dictionary_manifest_sha256':header['dictionaries']['sha256'],'recipe_manifest_sha256':header['protocol']['sha256'],'reproduction_package_sha256':header['reproduction_package']['sha256'],'audit_membership_sha256':header['audit_membership']['sha256'],'compression_level':'3','raw_commit_boundary':'one retained call; scientific stage+receipt one completed molecule'}
        require(case['temporary_directory']==str(Path(o['run_root'])/'temporary_lanes'),'EXACT_ORIGINAL_RUN_TEMPORARY_PATH_REQUIRED');require(len(case['files'])==24 and {Path(r['path']).name for r in case['files']}=={'lane_'+str(i).zfill(2)+'.sqlite' for i in range(24)},'EXACT24_LANE_NAMES_REQUIRED');dirs[case['temporary_directory']]=dir_shape(case);contexts[job]={'job_id':job,'expected_metadata':expected,'expected_dictionary_rows':expected_dict};all_files.extend((r,contexts[job],scope['expected_archive_schema_sql'],scope['expected_user_tables'],scope['payload_tables']) for r in case['files'])
    require(len(all_files)==360 and len({r[0]['path'] for r in all_files})==360 and {r[0]['path'] for r in all_files}=={r['path'] for r in failed['temporary_files']},'EXACT593_360_FILE_SET_DIFFERS');a.out.mkdir()
    with concurrent.futures.ProcessPoolExecutor(max_workers=24) as pool:results=list(pool.map(inspect_one,all_files,chunksize=1))
    good=[r for r in results if r['eligible_empty_payload']];inspection={'schema':'WP5_EXACT360_TEMPORARY_LANE_SQLITE_INSPECTION_ACTUAL_V1','status':'ALL360_EMPTY_OF_SCIENTIFIC_AND_RAW_PAYLOAD' if len(good)==360 else 'PRESERVE_ALL360_UNRESOLVED_OR_NONEMPTY','created_epoch':time.time(),'source':ref(__file__),'scope':ref(SCOPE),'actual_job_id':os.environ['SLURM_JOB_ID'],'node':socket.gethostname(),'requested_workers':24,'actual_inspection_worker_pids':sorted({r['worker_pid'] for r in results}),'all360_files':results,'eligible_empty_payload_files':len(good),'ineligible_files':360-len(good),'original_parent_accounting':[c['actual_original_terminal_accounting'] for c in scope['cases']],'original_run_metadata':[c['run_metadata'] for c in scope['cases']],'initial_temporary_directory_identity':dirs,'all_actual_table_counts_preserved_without_zero_relabelling':True,'classification_counts':dict(collections.Counter(r['status'] for r in results)),'zstd_version':'Historical normal version string retained; no current-library probe/equality gate','scientific_or_raw_frames_decoded':False,'files_deleted':0,'queue_or_SCI_modified':False,'new_QM_calls':0};dump_new(a.out/'inspection.json',inspection)
    if len(good)!=360:print(json.dumps({'status':inspection['status'],'ineligible':360-len(good),'inspection':str(a.out/'inspection.json'),'files_deleted':0}));raise SystemExit(2)
    if not a.execute_cleanup:print(json.dumps({'status':inspection['status'],'execution':'INSPECT_ONLY','files_deleted':0,'inspection':str(a.out/'inspection.json')}));return
    state={'schema':'WP5_EXACT360_TEMPORARY_EMPTY_LANE_CLEANUP_ACTUAL_V1','status':'PREFLIGHT_BEFORE_MUTATION','inspection':ref(a.out/'inspection.json'),'scope':ref(SCOPE),'source':ref(__file__),'actual_job_id':os.environ['SLURM_JOB_ID'],'node':socket.gethostname(),'deleted_files':[],'removed_empty_directories':[],'SCI_or_raw_frames_decoded':False,'raw_archive_or_permanent_SCI_modified':False,'queue_or_old_receipts_or_reports_modified':False,'new_QM_calls':0}
    try:
        for case in scope['cases']:dir_shape(case,dirs[case['temporary_directory']]);checked(case['run_metadata'])
        for row in good:same(row['path'],row['file_identity']);require(digest(row['path'])==row['file_sha256'],'EXACT_FILE_SHA_CHANGED_BEFORE_CLEANUP')
        fd_cases=[{'root':c['temporary_directory'],'entries':[dirs[c['temporary_directory']]]+[r['file_identity'] for r in good if Path(r['path']).parent==Path(c['temporary_directory'])]} for c in scope['cases']];fds=guard.fd_review(fd_cases);state['fd_guard']=fds;require(fds['no_unknown_scientific_active_reference'],'ACTIVE_OR_UNKNOWN_FD_REFERENCE_RETAIN_ALL');dump_new(a.out/'cleanup_intent.json',state)
        bypath={r['path']:r for r in good}
        for case in scope['cases']:
            folder=case['temporary_directory'];dir_shape(case,dirs[folder]);fd=open_dir(folder)
            try:
                s=os.fstat(fd);old=dirs[folder];require((s.st_dev,s.st_ino,s.st_uid,s.st_mode)==tuple(old[k] for k in ('device','inode','uid','mode')),'OPEN_TEMPORARY_DIRECTORY_DIFFERS')
                for item in case['files']:
                    row=bypath[item['path']];same(row['path'],row['file_identity']);require(digest(row['path'])==row['file_sha256'],'FINAL_EXACT_FILE_SHA_CHANGED');os.unlink(Path(row['path']).name,dir_fd=fd);state['deleted_files'].append({'path':row['path'],'bytes':row['file_identity']['bytes'],'sha256':row['file_sha256'],'classification':row['status']})
            finally:os.close(fd)
            p=Path(folder);same(p,dirs[folder],('device','inode','uid','gid','mode','kind'));fd=open_dir(p.parent)
            try:os.rmdir(p.name,dir_fd=fd);state['removed_empty_directories'].append(str(p))
            finally:os.close(fd)
        require(len(state['deleted_files'])==360 and len(state['removed_empty_directories'])==15 and all(not os.path.lexists(c['temporary_directory']) for c in scope['cases']),'EXACT360_15_CLEANUP_NOT_CLOSED');state['temporary_lane_bytes_released']=sum(r['bytes'] for r in state['deleted_files']);command=[sys.executable,'-B',scope['storage3']['path'],'--scope','shared','--jobmap',scope['formal542_jobmap']['path'],'--runtime',str(ROOT/'runtime'),'--node-authority',scope['node_authority']['path'],'--node-storage-reports']+[r['path'] for r in scope['six_node_report_references']]+['--workers','24','--out',str(a.out/'shared_storage_reaudit')]
        proc=subprocess.run(command,cwd=str(ROOT.parent.parent),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=45*3600);(a.out/'shared_storage_reaudit.stdout').write_text(proc.stdout);(a.out/'shared_storage_reaudit.stderr').write_text(proc.stderr);state['shared_reaudit']={'command':command,'returncode':proc.returncode,'source':scope['storage3']}
        report=a.out/'shared_storage_reaudit/storage_report.json'
        if report.exists():state['shared_reaudit'].update(report=ref(report),status=json.loads(report.read_text())['status'])
        require(proc.returncode==0 and state['shared_reaudit'].get('status')=='PASS','FROZEN_SHARED_STORAGE_REAUDIT_NOT_PASS');state['status']='EXACT360_EMPTY_LANES_CLEANED_AND_SHARED_STORAGE_PASS'
    except BaseException as error:
        state.update(status='ROOT_REVIEW_REQUIRED_AFTER_EXACT360_CLEANUP_ATTEMPT',error=repr(error),traceback=traceback.format_exc());dump_new(a.out/'cleanup_report.json',state);raise
    dump_new(a.out/'cleanup_report.json',state);print(json.dumps({'status':state['status'],'deleted_files':360,'removed_empty_directories':15,'report':str(a.out/'cleanup_report.json')}))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute-cleanup',action='store_true');p.add_argument('--out',type=Path,required=True);main(p.parse_args())
