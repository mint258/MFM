"""Private small semantics fixture and bounded read-only stat profile for inventory V4."""
from __future__ import annotations
import argparse, concurrent.futures, errno, importlib, json, os, shutil, signal, socket, stat, tempfile, threading, time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
V4_SHA='85cd785806b82f59afdb33436d4e083ef8240e2b49abf7f31224382ee3d3d5a7'
V3_SHA='dea339a9b6444791c575738cad7185a202ec0578002c3d8adff385a9ba9571b2'
def sha(path):
 import hashlib
 return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
 with Path(path).open('x') as stream:json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
def guard(args):
 nodes={'compute-0-'+str(i) for i in (12,13,14,17,18,19)}
 if os.getuid()!=1278 or socket.gethostname().split('.')[0] not in nodes or not os.environ.get('SLURM_JOB_ID','').isdigit() or os.environ.get('SLURM_CPUS_PER_TASK')!='24':raise ValueError('ACTUAL_AUTHORIZED_NODE_UID1278_SLURM24CPU_REQUIRED')
 if not args.out.is_absolute() or not args.out.is_relative_to(ROOT/'acceptance') or args.out.exists() or not args.out.parent.is_dir():raise ValueError('FRESH_ACCEPTANCE_JSON_REPORT_REQUIRED')
 if sha(ROOT/'scripts/wp5_file_inventory_v4.py')!=V4_SHA or sha(ROOT/'scripts/wp5_file_inventory_v3.py')!=V3_SHA:raise ValueError('V4_CANDIDATE_OR_V3_BASE_SHA_CHANGED')
def projection(V,result):
 return {key:result[key] for key in V.FIELDS}
def walk(V,home,exclude,parallel):
 total=V.empty();stack=[b'tree'];seen=[];traces=[]
 V._STOP=threading.Event()
 while stack:
  rel=stack.pop();row={'path':rel,'top':json.dumps('tree'),'depth':rel.count(b'/')}
  args=(str(home),str(exclude),row,time.monotonic()+60,60,0)
  result=V.threaded_scan_directory(args,threading.Event()) if parallel else V.scan_directory(args)
  if result['state']!='DONE':raise ValueError('SMALL_FIXTURE_SCAN_UNEXPECTED_PARTIAL')
  V.add(total,result['result']);stack.extend(result['children']);seen.append(rel)
  if parallel:traces.append(result.get('threaded_tail'))
 return total,sorted(seen),traces
class ErrorEntry:
 def __init__(self,entry):self.entry=entry;self.name=entry.name;self.path=entry.path
 def stat(self,follow_symlinks=False):
  if self.name in (b'controlled_vanished','controlled_vanished'):raise FileNotFoundError(errno.ENOENT,'PRIVATE_FIXTURE_CONTROLLED_VANISHED_ENTRY')
  return self.entry.stat(follow_symlinks=follow_symlinks)
class WrappedScandir:
 def __init__(self,base):self.base=base
 def __enter__(self):self.base.__enter__();return self
 def __exit__(self,*args):return self.base.__exit__(*args)
 def __iter__(self):return self
 def __next__(self):return ErrorEntry(next(self.base))
def private_state(V,base,home,rel):
 state=base/'state';state.mkdir()
 cfg=V.config(home,state);V.write_json(state/'manifest.json',{'status':'SIX_DISJOINT_DIRECTORY_SHARDS_READY','config':cfg})
 db=V.database(state/'shard_0.sqlite',cfg)
 try:
  V.meta_set(db,'seed_shard',0);V.meta_set(db,'seed_ready',True)
  db.execute("INSERT INTO tasks(path,top,depth,state) VALUES(?,?,?,'PENDING')",(rel,json.dumps('tree'),0))
  sentinel=json.dumps(V.empty(),sort_keys=True)
  db.execute("INSERT INTO tasks(path,top,depth,state,result,attempts) VALUES(?,?,?,'DONE',?,777)",(b'already_done',json.dumps('tree'),0,sentinel))
 finally:db.close()
 return state,cfg,sentinel
def fixture(V,args):
 base=Path(tempfile.mkdtemp(prefix='wp5_inventory_v4_fixture_'+str(os.getuid())+'_'+os.environ['SLURM_JOB_ID']+'_',dir='/tmp'))
 report=None;original_scandir=os.scandir;original_chunk=V._thread_stat_chunk
 original_batch=V.THREAD_BATCH_ENTRIES;original_bound=V.THREAD_MAX_INFLIGHT
 try:
  # Multiple small batches exercise ordered concurrent reduction, privately.
  V.THREAD_BATCH_ENTRIES=4;V.THREAD_MAX_INFLIGHT=8
  home=base/'home';tree=home/'tree';tree.mkdir(parents=True)
  for i in range(40):(tree/('entry_'+str(i))).write_bytes(('fixture_'+str(i)).encode())
  (tree/'child').mkdir();(tree/'child'/'nested').write_bytes(b'child')
  excluded=tree/'checkpoint';excluded.mkdir();(excluded/'not_enumerated').write_bytes(b'EXCLUDED')
  (tree/'controlled_vanished').write_bytes(b'controlled fault')
  (tree/'link_file').symlink_to(tree/'entry_0')
  (tree/'link_directory').symlink_to(tree/'child',target_is_directory=True)
  (tree/'broken_link').symlink_to(tree/'does_not_exist')
  # The only injected fault is metadata-only and identical for serial/threaded.
  os.scandir=lambda path:WrappedScandir(original_scandir(path))
  serial,serial_dirs,_=walk(V,home,excluded,False)
  threaded,threaded_dirs,traces=walk(V,home,excluded,True)
  os.scandir=original_scandir
  if projection(V,serial)!=projection(V,threaded) or serial_dirs!=threaded_dirs or serial['errors']!=threaded['errors']:raise ValueError('SERIAL_THREADED_FIXTURE_POPULATION_OR_ERROR_DIFFERENCE')
  if threaded['symlinks']!=3 or threaded['excluded_subtrees']!=1 or threaded['vanished_entries']!=1 or threaded['errors_total']!=1:raise ValueError('SYMLINK_EXCLUSION_OR_ERROR_SEMANTICS_CHANGED')
  if not any(trace['batches_submitted']>1 for trace in traces) or any(trace['max_inflight_batches_observed']>8 or trace['actual_stat_threads_observed']>23 for trace in traces):raise ValueError('PRIVATE_MULTIBATCH_OR_BOUNDED_THREAD_SEMANTICS')
  if b'tree/child' not in threaded_dirs or b'tree/link_directory' in threaded_dirs or b'tree/checkpoint' in threaded_dirs:raise ValueError('CHILD_DISCOVERY_OR_SYMLINK_FOLLOW_CHANGED')
  # Exclusive-lock single-tail selection + atomic DONE/child discovery.
  complete_base=base/'complete_case';complete_base.mkdir()
  state,cfg,sentinel=private_state(V,complete_base,home,b'tree')
  complete=V.scan_shard(state,0,workers=24,hours=1/60,budget=30,max_directories=1)
  db=V.database(state/'shard_0.sqlite',cfg)
  try:
   done=db.execute("SELECT state,result,attempts FROM tasks WHERE path=?",(b'tree',)).fetchone()
   children={bytes(r[0]) for r in db.execute("SELECT path FROM tasks WHERE state='PENDING'")}
   old=db.execute("SELECT result,attempts FROM tasks WHERE path=?",(b'already_done',)).fetchone()
   if done['state']!='DONE' or not done['result'] or b'tree/child' not in children:raise ValueError('ATOMIC_DONE_AND_CHILDREN_NOT_COMMITTED')
   if tuple(old)!=(sentinel,777):raise ValueError('ALREADY_DONE_WAS_RESCANNED_OR_MODIFIED')
  finally:db.close()
  # Explicit target may be one of several pending directories: claim only it.
  target_base=base/'target_case';target_base.mkdir()
  state,cfg,sentinel=private_state(V,target_base,home,b'tree')
  db=V.database(state/'shard_0.sqlite',cfg)
  try:db.execute("INSERT INTO tasks(path,top,depth,state) VALUES(?,?,?,'PENDING')",(b'tree/child',json.dumps('tree'),1))
  finally:db.close()
  targeted=V.scan_shard(state,0,workers=24,hours=1/60,budget=30,target_directory='tree')
  db=V.database(state/'shard_0.sqlite',cfg)
  try:
   target_row=db.execute("SELECT state,result FROM tasks WHERE path=?",(b'tree',)).fetchone()
   untouched=db.execute("SELECT state,result,attempts FROM tasks WHERE path=?",(b'tree/child',)).fetchone()
   prior=db.execute("SELECT result,attempts FROM tasks WHERE path=?",(b'already_done',)).fetchone()
   if target_row['state']!='DONE' or not target_row['result'] or tuple(untouched)!=('PENDING',None,0) or tuple(prior)!=(sentinel,777) or targeted['status']!='SHARD_CHECKPOINTED_PENDING_REMAINS':raise ValueError('EXPLICIT_TARGET_CLAIMED_OTHERS_OR_FALSE_COMPLETE')
   for invalid in ('tree','not_a_task'):
    try:V.scan_shard(state,0,workers=24,hours=1/60,budget=30,target_directory=invalid)
    except ValueError as error:
     if str(error)!='TARGET_MUST_BE_EXISTING_PENDING_OR_INCLUDED_LARGE_DIRECTORY':raise
    else:raise ValueError('DONE_OR_UNKNOWN_TARGET_WAS_NOT_REJECTED')
  finally:db.close()
  # A real one-second global deadline after a positive partial prefix. Reduce
  # only this private module instance's queue bound; production constants stay.
  deadline_base=base/'deadline_case';deadline_base.mkdir()
  state,cfg,sentinel=private_state(V,deadline_base,home,b'tree')
  V.THREAD_BATCH_ENTRIES=2;V.THREAD_MAX_INFLIGHT=1
  def delayed_chunk(arg):
   result=original_chunk(arg)
   time.sleep(max(0,arg[4]-time.monotonic())+.03)
   return result
  V._thread_stat_chunk=delayed_chunk
  partial=V.scan_shard(state,0,workers=24,hours=1/3600,budget=30,max_directories=1)
  db=V.database(state/'shard_0.sqlite',cfg)
  try:
   row=db.execute("SELECT state,result FROM tasks WHERE path=?",(b'tree',)).fetchone()
   rows=db.execute('SELECT count(*) FROM tasks').fetchone()[0]
   prior=db.execute("SELECT result,attempts FROM tasks WHERE path=?",(b'already_done',)).fetchone()
   diagnostics=partial['diagnostics']
   prefix=diagnostics[0]['diagnostic_entries_seen'] if diagnostics else 0
   if row['state']!='PENDING' or row['result'] is not None or rows!=2 or not 0<prefix<40 or tuple(prior)!=(sentinel,777):raise ValueError('DEADLINE_PARTIAL_PREFIX_OR_CHILDREN_WAS_COMMITTED')
  finally:db.close()
  report={'status':'PRIVATE_V4_SEMANTICS_FIXTURE_PASS','scope':'Small private /tmp tree only; no source home, active inventory DB, or SCI opened',
   'serial_population':projection(V,serial),'threaded_population':projection(V,threaded),
   'same_population_errors_and_children':True,'symlinks_not_followed':True,'checkpoint_subtree_excluded':True,
   'controlled_metadata_error_counted':True,'positive_deadline_prefix_entries':prefix,
   'deadline_prefix_result_and_children_not_committed':True,'already_DONE_unchanged':True,
   'single_tail_path':complete.get('v4_threaded_tail'),'actual_thread_traces':traces,
   'explicit_target_only_claimed_selected_pending':True,'explicit_target_other_pending_and_DONE_unchanged':True,
   'explicit_target_report_still_pending':targeted['status'],'DONE_and_unknown_targets_rejected':True,
   'fixture_root':str(base),'shared_per_record_files_created':0}
 finally:
  os.scandir=original_scandir;V._thread_stat_chunk=original_chunk
  V.THREAD_BATCH_ENTRIES=original_batch;V.THREAD_MAX_INFLIGHT=original_bound
  checked=base.resolve()
  if checked.parent!=Path('/tmp') or not checked.name.startswith('wp5_inventory_v4_fixture_'+str(os.getuid())+'_'):raise ValueError('PRIVATE_FIXTURE_CLEANUP_SCOPE')
  if base.lstat().st_uid!=os.getuid() or not stat.S_ISDIR(base.lstat().st_mode):raise ValueError('PRIVATE_FIXTURE_CLEANUP_OWNER_OR_TYPE')
  shutil.rmtree(base)
 if report is not None:
  report['fixture_root_absent']=not base.exists();return report
class ProfileEntry:
 def __init__(self,path,name):self.path=path;self.name=name
 def stat(self,follow_symlinks=False):return os.stat(self.path,follow_symlinks=follow_symlinks)
def profile_pass(V,entries,parallel,rel,exclude):
 started=time.monotonic();stop=threading.Event();deadline=started+120
 chunks=[entries[i:i+256] for i in range(0,len(entries),256)]
 jobs=[(chunk,rel,exclude,stop,deadline,started,120) for chunk in chunks]
 if parallel:
  with concurrent.futures.ThreadPoolExecutor(max_workers=23) as pool:parts=list(pool.map(V._thread_stat_chunk,jobs))
 else:parts=[V._thread_stat_chunk(job) for job in jobs]
 total=V.empty();ids=set();children=[]
 for part in parts:
  if part['reason']:raise ValueError('BOUNDED_PROFILE_METADATA_TIME_LIMIT')
  for key in V.FIELDS:total[key]+=part['result'][key]
  total['errors'].extend(part['result']['errors'][:max(0,20-len(total['errors']))])
  children.extend(part['children']);ids.add(part['stat_thread_native_id'])
 import hashlib
 child_digest=hashlib.sha256(json.dumps(sorted(path.hex() for path in children),separators=(',',':')).encode()).hexdigest()
 return {'seconds':time.monotonic()-started,'population':projection(V,total),'errors':total['errors'],
         'children_count':len(children),'child_paths_sha256':child_digest,'actual_stat_thread_native_ids':sorted(ids)}
def entry_identities(entries):
 import hashlib
 rows=[]
 for entry in entries:
  try:
   s=entry.stat(follow_symlinks=False)
   value={'device':s.st_dev,'inode':s.st_ino,'mode':s.st_mode,'uid':s.st_uid,'nlink':s.st_nlink,
          'bytes':s.st_size,'blocks':getattr(s,'st_blocks',0),'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns}
  except OSError as error:value={'errno':error.errno,'type':type(error).__name__}
  rows.append({'path_hex':entry.path.hex(),'identity':value})
 return hashlib.sha256(json.dumps(sorted(rows,key=lambda row:row['path_hex']),sort_keys=True,separators=(',',':')).encode()).hexdigest()
def profile(V,args):
 import hashlib
 path=args.path.absolute()
 if not path.is_relative_to(Path('/share/home/zixiao')) or not stat.S_ISDIR(path.lstat().st_mode):raise ValueError('EXPLICIT_READONLY_HOME_DIRECTORY_REQUIRED')
 if not 2<=args.entries<=8192:raise ValueError('PROFILE_ENTRIES_RANGE_2_TO8192')
 selected=[];started=time.monotonic()
 with os.scandir(os.fsencode(path)) as entries:
  for _ in range(args.entries):
   try:entry=next(entries)
   except StopIteration:break
   # Fresh path stat on every pass avoids DirEntry's own cached stat result.
   selected.append(ProfileEntry(entry.path,entry.name))
 enumeration=time.monotonic()-started
 if len(selected)<2:raise ValueError('PROFILE_NEEDS_AT_LEAST_TWO_SELECTED_ENTRIES')
 rel=os.fsencode(path.name);exclude=str(ROOT/'reports/home_stat_inventory_v2_20261016')
 # Both methods warm the identical bounded set before any timing used for gain.
 warmups=[{'mode':mode,**profile_pass(V,selected,mode=='threaded',rel,exclude)} for mode in ('serial','threaded')]
 before=entry_identities(selected);passes=[]
 for index,mode in enumerate(('serial','threaded','threaded','serial')):
  passes.append({'pass':index,'mode':mode,**profile_pass(V,selected,mode=='threaded',rel,exclude)})
 after=entry_identities(selected)
 signatures=[{key:item[key] for key in ('population','errors','children_count','child_paths_sha256')} for item in passes]
 same_population=all(item==signatures[0] for item in signatures)
 comparable=before==after and same_population
 serial=sum(item['seconds'] for item in passes if item['mode']=='serial')/2
 threaded=sum(item['seconds'] for item in passes if item['mode']=='threaded')/2
 speedup=serial/threaded if comparable and threaded else None
 return {'status':'TEST_PARTIAL_NOT_ACCOUNT_RESULT','path':str(path),'entry_cap':args.entries,'selected_entries':len(selected),
  'selected_path_set_sha256':hashlib.sha256(json.dumps(sorted(entry.path.hex() for entry in selected),separators=(',',':')).encode()).hexdigest(),
  'enumeration_seconds':enumeration,'warmups_not_used_for_gain':warmups,'measurement_order':['serial','threaded','threaded','serial'],
  'measured_passes':passes,'identities_before_sha256':before,'identities_after_sha256':after,
  'selected_entry_identities_stable':before==after,'identical_observed_population_all_measured_passes':same_population,
  'timing_comparable_only_for_stable_same_set':comparable,
  'mean_serial_stat_seconds':serial,'mean_threaded_stat_seconds':threaded,'observed_stat_only_speedup':speedup,
  'measured_threaded_faster':bool(speedup is not None and speedup>1),'keep_V3_if_no_measured_gain':True,
  'automatic_production_enablement':False,'directory_fully_inventoried':False,'state_or_DB_opened':False,
  'directory_internal_cursor_saved':False,'source_file_contents_opened':False,'source_paths_modified':False,
  'maximum_execution_threads':24,
  'limitations':['Same bounded entry set is warmed by both methods, then measured serial/threaded/threaded/serial.',
   'Gain is NULL if before/after entry identities or observed measured populations differ; live-tree/cache/RPC bias can still remain.',
   'Only a few thousand entries are sampled; no full-directory or end-to-end speedup is proven.',
   'Stat timings exclude complete-directory enumeration, child processing, DB commit, and final collection.']}
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=('fixture','profile'))
 ap.add_argument('--out',type=Path,required=True);ap.add_argument('--path',type=Path);ap.add_argument('--entries',type=int,default=4096);args=ap.parse_args()
 guard(args);V=importlib.import_module('wp5_file_inventory_v4')
 if args.mode=='profile' and args.path is None:ap.error('--path is required for bounded readonly profile')
 previous=signal.signal(signal.SIGTERM,lambda *a:(_ for _ in ()).throw(SystemExit('VALIDATION_TERMINATED')))
 try:report=fixture(V,args) if args.mode=='fixture' else profile(V,args)
 finally:signal.signal(signal.SIGTERM,previous)
 report.update(candidate_source={'path':str(ROOT/'scripts/wp5_file_inventory_v4.py'),'sha256':V4_SHA},
  unchanged_V3_base={'path':str(ROOT/'scripts/wp5_file_inventory_v3.py'),'sha256':V3_SHA},
  allocated_cpus=24,host=socket.gethostname(),uid=os.getuid(),slurm_job_id=os.environ['SLURM_JOB_ID'],
  validation_source_sha256=sha(__file__),QM_started=False,active_inventory_SQLite_opened=False)
 save(args.out,report);print(json.dumps({'status':report['status'],'report':str(args.out)}))
if __name__=='__main__':main()
