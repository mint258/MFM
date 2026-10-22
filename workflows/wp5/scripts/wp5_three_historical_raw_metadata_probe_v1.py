"""Three fixed historical raw SQLite containers: read-only metadata, no SCI decoding."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, multiprocessing, os, socket, sqlite3, stat, time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
INPUTS=(
 ('4513997','47','runtime/task_47/job_4513997_b9632d3f'),
 ('4514044','35','runtime/task_35/job_4514044_e3d58779'),
 ('4514026','26','runtime/task_26/job_4514026_ba437ec5'),
)
EXPECTED_BYTES=45056
TERMINAL={'COMPLETED','FAILED','CANCELLED','NODE_FAIL','PREEMPTED','BOOT_FAIL','OUT_OF_MEMORY','TIMEOUT','DEADLINE','REVOKED'}
UNKNOWN={'','unknown','none','null','n/a','na','-','(null)'}
def digest(body):return hashlib.sha256(body).hexdigest()
def identity(info):
 return {'device':info.st_dev,'inode':info.st_ino,'uid':info.st_uid,'mode':info.st_mode,
         'nlink':info.st_nlink,'bytes':info.st_size,'mtime_ns':info.st_mtime_ns,'ctime_ns':info.st_ctime_ns}
def stable_bytes(path,expected_size=None):
 path=Path(path);before=path.lstat()
 if not stat.S_ISREG(before.st_mode):raise ValueError('REGULAR_FILE_NO_SYMLINK_REQUIRED:'+str(path))
 if expected_size is not None and before.st_size!=expected_size:raise ValueError('EXPECTED_45056_BYTE_CONTAINER_CHANGED:'+str(path)+':'+str(before.st_size))
 fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
 try:
  if identity(os.fstat(fd))!=identity(before):raise ValueError('FILE_IDENTITY_CHANGED_BEFORE_OPEN')
  with os.fdopen(fd,'rb',closefd=False) as stream:body=stream.read()
 finally:os.close(fd)
 after=path.lstat()
 if identity(before)!=identity(after) or len(body)!=before.st_size:raise ValueError('FILE_IDENTITY_OR_SIZE_CHANGED_DURING_READ')
 return body,{'path':str(path),'bytes':len(body),'sha256':digest(body),'lstat_before':identity(before),'lstat_after':identity(after)}
def read_json(path):
 body,reference=stable_bytes(path)
 return json.loads(body),reference
def ident(name):return '"'+name.replace('"','""')+'"'
def metadata_value(value):
 if isinstance(value,bytes):return {'sqlite_type':'BLOB','bytes':len(value),'sha256':digest(value),'body_not_saved':True}
 return value
def accounting_refs(path):
 raw,source=read_json(path)
 if raw.get('sacct_returncode')!=0:raise ValueError('ACTUAL_RAW_ACCOUNTING_RETURN_CODE_REQUIRED')
 columns=['JobID' if key=='JobIDRaw' else key for key in raw['fields']]
 required={'JobID','User','State','ExitCode','Start','End','ElapsedRaw','AllocCPUS'}
 if len(columns)!=len(set(columns)) or not required.issubset(columns):raise ValueError('ACTUAL_ACCOUNTING_REQUIRED_COLUMNS')
 targets={row[0] for row in INPUTS};actual={}
 for original in raw['sacct_stdout'].splitlines(keepends=True):
  if not original.strip():continue
  values=[value.strip() for value in original.rstrip('\r\n').split('|')]
  if values and values[-1]=='':values.pop()
  if len(values)!=len(columns):raise ValueError('ACTUAL_ACCOUNTING_ROW_WIDTH')
  row=dict(zip(columns,values));job=row['JobID']
  if job not in targets:continue
  if job in actual or row['User']!='zixiao':raise ValueError('ACTUAL_ORIGINAL_PARENT_DUPLICATE_OR_WRONG_USER')
  if row['State'].split()[0].rstrip('+') not in TERMINAL:raise ValueError('ACTUAL_ORIGINAL_PARENT_NOT_TERMINAL:'+job)
  if any(row[key].casefold() in UNKNOWN for key in required):raise ValueError('ACTUAL_ORIGINAL_PARENT_ACCOUNTING_UNKNOWN:'+job)
  if min(int(row['ElapsedRaw']),int(row['AllocCPUS']))<0:raise ValueError('ACTUAL_RESOURCE_FIELDS_INVALID')
  actual[job]={'actual_sacct':row,'original_sacct_line':original,'source_reference':source}
 if set(actual)!=targets:raise ValueError('ALL_THREE_ACTUAL_ORIGINAL_PARENT_ROWS_REQUIRED')
 return source,actual
def init(barrier):barrier.wait(timeout=120)
def observe(spec):
 job,task,relative=spec;folder=ROOT/relative;path=folder/'raw_archive.sqlite'
 result={'original_job_id':job,'original_task_id':task,'path':str(path),'worker_pid':os.getpid(),
         'SQLite_opened':False,'scientific_raw_frame_decoded':False,'raw_body_saved':False,
         'source_files_deleted_or_modified':False}
 try:
  first,before=stable_bytes(path,EXPECTED_BYTES);result['raw_before']=before
  if before['lstat_before']['uid']!=1278:raise ValueError('RAW_OWNER_UID1278_REQUIRED')
  run,run_ref=read_json(folder/'run.json');options=run.get('options',{})
  if str(options.get('job_id'))!=job or str(options.get('task_id'))!=task:raise ValueError('ORIGINAL_RUN_IDENTITY_DIFFERS')
  result['original_run']={'reference':run_ref,'node':run.get('node'),'guide_source_sha256':run.get('guide_source_sha256'),
   'production_contract_sha256':run.get('production_contract_sha256'),
   'execution_metadata':{key:options.get(key) for key in ('job_id','task_id','mode','session','policy','protocol','registry_sha','production_contract','production_contract_sha256','reproduction_package','reproduction_package_sha256')},
   'recorded_source_bindings':options.get('source_bindings',[]),
   'recorded_bindings_not_claimed_newly_validated_against_historical_binaries':True}
  db=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True,isolation_level=None,timeout=5)
  result['SQLite_opened']=True
  try:
   db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON')
   if db.execute('PRAGMA query_only').fetchone()[0]!=1:raise ValueError('QUERY_ONLY_NOT_ENABLED')
   objects=[dict(row) for row in db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE substr(name,1,7)!='sqlite_' ORDER BY type,name")]
   tables=[]
   for obj in objects:
    if obj['type']!='table':continue
    name=obj['name'];quoted=ident(name)
    columns=[dict(row) for row in db.execute('PRAGMA table_xinfo('+quoted+')')]
    count=db.execute('SELECT count(*) FROM '+quoted).fetchone()[0]
    table={'name':name,'schema_sql':obj['sql'],'columns':columns,'row_count':count}
    if name in {'metadata','dictionaries'}:
     # Preserve initialization rows only. Scientific tables are counted, never
     # selected, unpickled, unbundled, or decompressed.
     rows=db.execute('SELECT * FROM '+quoted+' ORDER BY '+','.join(ident(col['name']) for col in columns if col['hidden']==0)).fetchall()
     table['initialization_rows']=[{key:metadata_value(row[key]) for key in row.keys()} for row in rows]
    tables.append(table)
   result.update(sqlite_mode='ro',sqlite_immutable=True,query_only=True,user_objects=objects,user_tables=tables)
  finally:db.close()
  second,after=stable_bytes(path,EXPECTED_BYTES);result['raw_after']=after
  stable=before['lstat_before']==after['lstat_after'] and before['sha256']==after['sha256'] and first==second
  result['raw_lstat_and_SHA_stable']=stable
  if not stable:raise ValueError('RAW_CHANGED_ACROSS_READONLY_SQLITE_OBSERVATION')
  payload={table['name']:table['row_count'] for table in tables if table['name'] not in {'metadata','dictionaries'}}
  result['noninitialization_table_row_counts']=payload
  result['all_scientific_or_other_payload_table_rows_zero']=all(count==0 for count in payload.values())
  required={'records','molecules','parsed_molecules','completion_receipts','parquet_exports'}
  names={table['name'] for table in tables}
  recognized=required|{'metadata','dictionaries'}
  result['expected_archive_tables_present']=required.issubset(names)
  result['other_user_table_names']=sorted(names-recognized)
  if names==recognized and not any(obj['type']!='table' for obj in objects) and result['all_scientific_or_other_payload_table_rows_zero']:
   result['classification']='HISTORICAL_INITIALIZATION_CONTAINER_NO_SCI_PAYLOAD_ROWS'
   result['followup_required']=False
  else:
   result['classification']='HISTORICAL_NONEMPTY_OR_UNRECOGNIZED_CONTAINER_RETAINED_FOR_REVIEW'
   result['followup_required']=True
  result['canonical_formal_scientific_artifact_claimed']=False
 except Exception as error:
  result['classification']='READONLY_OBSERVATION_INCOMPLETE_RETAINED_FOR_REVIEW'
  result['followup_required']=True;result['error']={'type':type(error).__name__,'message':str(error)}
 return result
def save(path,document):
 with Path(path).open('x') as stream:
  json.dump(document,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--catalog',type=Path,required=True)
 ap.add_argument('--terminal-accounting',type=Path,required=True,help='Actual raw union accounting JSON: fields/sacct_returncode/sacct_stdout; not a predicted or normalized future terminal row.')
 ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
 host=socket.gethostname().split('.')[0];job=os.environ.get('SLURM_JOB_ID','')
 allocated=int(os.environ.get('SLURM_CPUS_PER_TASK','0'))
 if os.getuid()!=1278 or host!='compute-0-17' or not job.isdigit() or allocated!=24:raise ValueError('ACTUAL_NODE17_UID1278_SLURM24CPU_REQUIRED')
 if not args.out.is_absolute() or not args.out.is_relative_to(ROOT/'acceptance') or args.out.exists() or not args.out.parent.is_dir():raise ValueError('FRESH_ACCEPTANCE_JSON_IN_EXISTING_PARENT_REQUIRED')
 catalog,cat_ref=read_json(args.catalog)
 if catalog.get('status')!='CLOSED':raise ValueError('CLOSED_CATALOG3_REQUIRED')
 terminal_ref,actual=accounting_refs(args.terminal_accounting)
 source,source_ref=stable_bytes(__file__)
 fixed_paths={str(ROOT/relative/'raw_archive.sqlite') for _,_,relative in INPUTS}
 canonical_raw=[ref for ref in catalog['artifacts'] if Path(ref['path']).name=='raw_archive.sqlite']
 catalog_paths={str(Path(ref['path'])) for ref in catalog['artifacts']}
 context=multiprocessing.get_context('spawn');barrier=context.Barrier(3);start=time.time()
 with concurrent.futures.ProcessPoolExecutor(max_workers=3,mp_context=context,initializer=init,initargs=(barrier,)) as pool:observations=list(pool.map(observe,INPUTS,chunksize=1))
 for entry in observations:
  entry['actual_original_parent_terminal']=actual[entry['original_job_id']]
  entry['path_present_in_closed_canonical_catalog']=entry['path'] in catalog_paths
 pids={entry['worker_pid'] for entry in observations}
 errors=[entry for entry in observations if entry.get('error')]
 ambiguous=[entry for entry in observations if entry.get('followup_required') or entry['path_present_in_closed_canonical_catalog']]
 payload_zero=all(entry.get('all_scientific_or_other_payload_table_rows_zero') is True for entry in observations)
 initialization=not errors and not ambiguous
 report={'schema':'WP5_THREE_HISTORICAL_RAW_READONLY_PROBE_V1',
  'status':'HISTORICAL_INITIALIZATION_CONTAINERS_CONFIRMED' if initialization else 'HISTORICAL_RAW_PROBE_RETAINED_FOR_REVIEW',
  'scope':'Exactly three enumerated history-only raw containers; no runtime-wide scan and no SCI raw-frame decoding.',
  'started_epoch':start,'finished_epoch':time.time(),'host':host,'uid':os.getuid(),'slurm_job_id':job,
  'allocated_cpus':allocated,'workers_requested':3,'actual_worker_pids':sorted(pids),'actual_workers_observed':len(pids),
  'parallelism_statement':'Three fixed inputs use a pool capped at three processes within the delivery 24CPU allocation; actual distinct scanning PIDs are listed. No claim of 24 effective probe workers.',
  'catalog':cat_ref,'original_parent_terminal_accounting':terminal_ref,'probe_source':source_ref,
  'canonical_raw_artifact_reference_count':len(canonical_raw),
  'canonical_raw_artifact_declared_bytes':sum(ref['bytes'] for ref in canonical_raw),
  'fixed_input_count':3,'fixed_expected_bytes_each':EXPECTED_BYTES,'fixed_expected_total_bytes':EXPECTED_BYTES*3,
  'actual_fixed_input_bytes':sum(entry.get('raw_before',{}).get('bytes',0) for entry in observations),
  'fixed_paths_in_canonical_catalog':sorted(fixed_paths&catalog_paths),'observations':observations,
  'all_scientific_payload_rows_zero':payload_zero,'observations_with_errors':len(errors),'followup_required':bool(ambiguous or errors),
  'source_SQLite_opened_by_prepare_step':False,'SQLite_files_written':False,'inputs_or_raw_bodies_saved':False,
  'scientific_frames_decoded':False,'new_QM_calls':0,'SCI_or_queue_modified':False,'files_deleted':0,
  'classification_is_not_addition_to_canonical_formal_results':True}
 save(args.out,report)
 print(json.dumps({'status':report['status'],'report':str(args.out),'probe_workers_observed':len(pids),'followup_required':report['followup_required'],'errors':len(errors)}))
 if errors:raise SystemExit(2)
if __name__=='__main__':main()

