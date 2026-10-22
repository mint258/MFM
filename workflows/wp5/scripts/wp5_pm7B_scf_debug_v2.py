"""Six isolated B-only diagnostic calls: three original AUX records, two no-POLAR recipes."""
from __future__ import annotations
import argparse,collections,concurrent.futures,copy,hashlib,json,multiprocessing,os,stat,struct,tempfile,time,uuid
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011');F=ROOT/'acceptance/final_20261016_v1'
BINDINGS=json.loads(r'''{"source_plan":{"path":"/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/plan.json","sha256":"b08b508c9630539df6d3bfa4a2a1b51621c3a9ef20e9e9dc72f7f6b1c1f483ab","bytes":54200},"contract":{"path":"/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/configs/production_contract_v7.json","sha256":"f2966094cc57ef82ca79292a9640a9bbbcf99f46d12626d28dccbe0a507fe33f","bytes":53594},"reconstruct_source":{"path":"/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts/wp5_reproduction50_v3.py","sha256":"ce19d8595c27f73ed7348fd35d0fb2f987279f30caadf03d18a204ef30cf8eb1","bytes":31554},"engine":{"path":"/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts/wp5_engine_v3.py","sha256":"53c09b68938ead8449f0da2ec7a03337df3125826080ece58fabe107cdd9f26b","bytes":31025},"diagnostic":{"path":"/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/acceptance/final_20261016_v1/pilot_difference_diagnostic_v2/diagnostic.json","sha256":"ec9613ab1dd454815d2a99e7ec6613d4d1d70d76954ab47415dac564c98c90d9","bytes":834777}}''')
RECORDS=('principal_00000001_00300000.lmdb:118739','principal_00000001_00300000.lmdb:1197774','principal_00000001_00300000.lmdb:1222267')
VARIANTS=('CURRENT_NO_POLAR_DEFAULT','CANDIDATE_NO_POLAR_SCFCRT_1E6')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def checked(ref):
 p=Path(ref['path'])
 if sha(p)!=ref['sha256'] or ('bytes' in ref and p.stat().st_size!=ref['bytes']):raise ValueError('FROZEN_DEBUG_BINDING_CHANGED:'+str(p))
 return p
def save(p,d):
 with p.open('x') as f:json.dump(d,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def init():
 import pyarrow as pa
 pa.set_cpu_count(1);pa.set_io_thread_count(1)
def canonical(v):
 import wp5_parquet_v2 as w
 if v is w.MISSING:return {'__ABSENT__':True}
 if isinstance(v,float):return {'__float64_bits__':struct.pack('>d',v).hex(),'value':v}
 if isinstance(v,list):return [canonical(x) for x in v]
 if isinstance(v,dict):return {k:canonical(x) for k,x in v.items()}
 return v
def one_call(a):
 import wp5_engine_v3 as E,wp5_archive_v5 as A
 from wp5_scf_metadata_v2 import extract_scf
 row,variant,context,options=a;contract=options['contract'];protocol=copy.deepcopy(options['protocol']);task=copy.deepcopy(next(t for t in protocol['tasks'] if t['name']=='pm7_B'))
 if any(x in task['keywords'] for x in ('POLAR','SCFCRT','RELSCF','PRECISE')):raise ValueError('UNEXPECTED_BASE_B_PRECISION_CONTROL')
 if variant==VARIANTS[1]:task['keywords']+=' SCFCRT=1e-6'
 elif variant!=VARIANTS[0]:raise ValueError('UNKNOWN_DEBUG_VARIANT')
 candidate_protocol=copy.deepcopy(protocol);candidate_protocol['tasks'][0]=task
 # Engine validates the actual current immutable package/environment. Candidate
 # keyword bytes are a separate diagnostic variant, never a production package claim.
 E.initialize_worker(BINDINGS['source_plan']['path'],protocol=protocol,node_scratch_root=options['scratch'],audit_membership=contract['audit_manifest']['path'],reproduction_package=contract['reproduction_package']['path'],deadline=time.time()+1800)
 writer=None;durable=False;result=None;failure=None;cleanup=None
 try:
  native=E.NATIVE.read_native(row)
  for k in ('native_coordinates_sha256','native_atom_order_sha256'):
   if native[k]!=context['old_context'][k]:raise ValueError('EXACT_OLD_NATIVE_IDENTITY_DIFFERENT:'+k)
  if row['record_payload_sha256']!=context['old_context']['source_payload_sha256']:raise ValueError('SOURCE_PAYLOAD_DIFFERS')
  files=E.render_inputs(task,native,row,protocol);input_sha=[{'name':k,'sha256':hashlib.sha256(v).hexdigest()} for k,v in sorted(files.items())]
  if variant==VARIANTS[0] and input_sha!=context['formal_B']['input_file_sha256']:raise ValueError('DEFAULT_REPLAY_INPUT_BYTES_NOT_FORMAL')
  E.CAPTURED=None;E.CAPTURE_ERROR=None;E.CALL_SCRATCH=None
  result=E.NATIVE.invoke(task,native,row,E.WORK)
  if E.CAPTURE_ERROR is not None or result.get('preserved_scratch'):E.PRESERVE_ARCHIVE_FAILURE=True;raise RuntimeError('DEBUG_CAPTURE_OR_NATIVE_CLEANUP_FAILURE')
  source_status=result['status'];result['source_status']=source_status;result['status']=E.canonical_status(source_status);result['scope_status']=result['status']
  result['atomic_array_validation']=E.validate_atomic_arrays(result,native['z'])
  if result['atomic_array_validation'] and result['status']=='SUCCESS':result.update(status='PROPERTY_FAILED',scope_status='PROPERTY_FAILED',failure_code='REQUESTED_SCOPE_ATOMIC_ARRAY_QC_FAILED')
  captured=E.CAPTURED or [];scf=extract_scf('pm7_B',captured,result.get('values'),result['status'],source_status)
  # Same renderer and bundle format as the current engine; do not write input bodies.
  before=E.CONFIG['tasks'][0];E.CONFIG['tasks'][0]=task
  try:per_file,bundle=E.rendered_input_hashes(task,native,row)
  finally:E.CONFIG['tasks'][0]=before
  result['provenance']={'software_version_id':E.PACKAGE['software_versions']['mopac']['software_version_id'],'elapsed_seconds':result.get('elapsed_seconds'),'scf_iterations':scf['scf_iterations'],'converged':scf['converged'],'input_file_sha256':per_file,'input_bundle_sha256':bundle}
  selected=E.AUDIT_IDS.get(row['record_id']);result['raw_audit_selected']=selected is not None
  if result['raw_audit_selected']!=context['formal_B']['raw_audit_selected']:raise ValueError('ORIGINAL_AUDIT_MEMBERSHIP_DIFFERS')
  result['precision_by_field']=E.PARSER.context().get('rounding_decimal_places',{});result['reproduction_package_sha256']=E.PACKAGE_SHA
  run_context={'execution_id':str(os.environ['SLURM_JOB_ID'])+':'+variant+':'+hashlib.sha256(row['record_id'].encode()).hexdigest()[:16],'job_id':int(os.environ['SLURM_JOB_ID']),'diagnostic_only':True,'variant':variant,'candidate_keywords':task['keywords'],'baseline_package_sha256':E.PACKAGE_SHA,'candidate_is_not_frozen_production_package':variant==VARIANTS[1]}
  raw=E.raw_record(task,row,result,captured,run_context);raw['candidate_keywords']=task['keywords'];raw['diagnostic_only']=True
  keep,reason=A.retention(raw)
  if not keep:
   # No shared container, directory or call-sized file for ordinary success.
   ref={'record_id':row['record_id'],'calc_type':'pm7_B','execution_id':run_context['execution_id'],'output_retained':False,'retention_reason':reason,'ordinary_success_shared_insert':False}
  else:
   import fcntl
   path=Path(options['out'])/'retained_raw.sqlite'
   lock_path=Path(options['scratch'])/'retained_raw.lock'
   lock_fd=os.open(lock_path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
   with os.fdopen(lock_fd,'r+b') as lock_stream:
    info=os.fstat(lock_stream.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1 or info.st_size!=0:raise ValueError('PRIVATE_RETENTION_LOCK_SHAPE_OWNER')
    fcntl.flock(lock_stream.fileno(),fcntl.LOCK_EX)
    try:
     writer=A.ArchiveWriter(path,options['dictionaries'],resume=path.exists(),reproduction_package=contract['reproduction_package']['path'],audit_membership=contract['audit_manifest']['path']);writer.begin_molecule(row['molecule_id']);ref=writer.put_record(raw);writer.commit_molecule();writer.close();writer=None
     reader=A.ArchiveReader(path,options['dictionaries'])
     try:readback=reader.get(row['record_id'],'pm7_B',run_context['execution_id'])
     finally:reader.close()
     if [dict(name=f['name'],sha256=f['sha256']) for f in readback['output_files']]!=[dict(name=f['name'],sha256=f['sha256']) for f in captured]:raise ValueError('RETAINED_DEBUG_RAW_READBACK_DIFFERS')
    finally:
     if writer is not None:writer.close();writer=None
   # Closing the private lock descriptor releases flock after durable readback.
  if bool(ref['output_retained'])!=keep or (keep and not ref.get('raw_call_durable')):raise ValueError('DEBUG_RAW_NOT_DURABLE')
  durable=True
  if E.CALL_SCRATCH is not None:E.ORIGINAL_CLEANUP(E.CALL_SCRATCH)
  E.CAPTURED=None;E.CALL_SCRATCH=None
  # Reuse the other already-computed formal tasks solely for B's derived labels.
  other=copy.deepcopy(context['other_formal_details']);E.derived_quantities([result]+other)
  result.pop('archive',None);result.pop('archived_files',None)
  return {'record_id':row['record_id'],'variant':variant,'detail':result,'input_file_sha256':per_file,'input_bundle_sha256':bundle,'raw_ref':ref,'native_coordinates_sha256':native['native_coordinates_sha256'],'native_atom_order_sha256':native['native_atom_order_sha256'],'atomic_array_validation':result['atomic_array_validation'],'worker_pid':os.getpid(),'QM_calls':1,'candidate_keywords':task['keywords'],'formal_other_tasks_reused_without_QM':[d['task'] for d in other]}
 except Exception:
  E.PRESERVE_ARCHIVE_FAILURE=True
  raise
 finally:
  if writer is not None:writer.close()
  E.close_worker()
def main():
 from wp5_acceptance_catalog import require_slurm
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--dictionaries',type=Path,required=True);ap.add_argument('--execute',action='store_true');a=ap.parse_args()
 if not a.execute:raise ValueError('PREPARED_DEBUG_REQUIRES_ROOT_EXECUTE')
 require_slurm(24)
 if os.uname().nodename.split('.')[0] not in {'compute-0-'+str(x) for x in (12,13,14,17,18,19)}:raise ValueError('AUTHORIZED_NODE_REQUIRED')
 for ref in BINDINGS.values():checked(ref)
 contract=json.loads(Path(BINDINGS['contract']['path']).read_text());protocol=json.loads(checked(contract['protocol']).read_text());checked(contract['reproduction_package']);checked(contract['audit_manifest']);checked(contract['registry'])
 diagnostic=json.loads(Path(BINDINGS['diagnostic']['path']).read_text())
 if tuple(sorted(diagnostic['bounded_source_sample_records']))!=RECORDS:raise ValueError('EXACT3_OLD_NATIVE_AUX_RECORDS_REQUIRED')
 a.out.mkdir(parents=True,exist_ok=False)
 import pyarrow as pa,pyarrow.parquet as pq,pyarrow.dataset as ds,wp5_parquet_v2 as wire
 from wp5_reproduction50_v3 import reconstruct,bits as bits_equal,value_sha
 from wp5_acceptance_recompute import normalized_scientific
 entries={x['registry_id']:x for x in wire.registry(contract['registry']['path'])}
 panel=ROOT.parent/'phase1_dataset_rebuild_20261010/wp4_native_panel/pilot_panel.parquet'
 rows=ds.dataset(panel,format='parquet').to_table(filter=ds.field('record_id').isin(RECORDS),use_threads=False).to_pylist()
 if len(rows)!=3 or {r['record_id'] for r in rows}!=set(RECORDS):raise ValueError('EXACT3_NATIVE_SOURCE_ROWS')
 loc=ds.dataset(F/'pilot_v4/pilot_reference_locators.parquet',format='parquet').to_table(filter=ds.field('record_id').isin(RECORDS),use_threads=False).to_pylist();locations={(x['record_id'],x['calc_type']):x for x in loc};formal={}
 for path in sorted({x['family_parquet_path'] for x in loc}):
  for r in ds.dataset(path,format='parquet').to_table(filter=ds.field('record_id').isin(RECORDS),use_threads=False).to_pylist():
   l=locations.get((r['record_id'],r['calc_type']))
   if l and all(r[k]==l[k] for k in ('attempt_id','job_id','task_id','lane')):formal[(r['record_id'],r['calc_type'])]=r
 if len(formal)!=36:raise ValueError('FORMAL3_BY12_NOT_CLOSED')
 old={};contexts={}
 for m in diagnostic['source_samples']:
  ref=m['verified_pilot_parquet'];checked(ref)
  for item in pq.read_table(ref['path'],columns=['details_json']).to_pylist():
   d=json.loads(item['details_json'])
   if d['record_id'] in RECORDS and d['task']=='pm7_B':old[d['record_id']]=d
  for s in m['samples']:contexts[s['record_id']]={'old_context':s['original_nonvalues_context'],'formal_B':formal[(s['record_id'],'pm7_B')],'other_formal_details':[reconstruct(v,entries) for (rid,task),v in formal.items() if rid==s['record_id'] and task!='pm7_B']}
 if set(old)!=set(RECORDS):raise ValueError('EXACT_OLD3_B_DETAILS_REQUIRED')
 scratch=Path(tempfile.mkdtemp(prefix='wp5Bscfdebug_'+str(os.getuid())+'_'+os.environ['SLURM_JOB_ID']+'_',dir='/tmp'))
 save(a.out/'execution_plan.json',{'status':'ISOLATED_6_CALL_DEBUG_NOT_PRODUCTION','records':RECORDS,'variants':VARIANTS,'max_QM_calls':6,'candidate_keyword_change_only':'Append SCFCRT=1e-6 to current B; never POLAR','bindings':BINDINGS,'dictionary_manifest':{'path':str(a.dictionaries),'sha256':sha(a.dictionaries)},'scratch':str(scratch),'original_audit_membership_fixed':True,'input_bodies_saved':False,'shared_SCI_or_queue_mutated':False,'host':os.uname().nodename,'job_id':os.environ['SLURM_JOB_ID']})
 options={'contract':contract,'protocol':protocol,'scratch':str(scratch),'out':str(a.out),'dictionaries':str(a.dictionaries)};ctx=multiprocessing.get_context('spawn');results=[]
 try:
  with concurrent.futures.ProcessPoolExecutor(max_workers=6,mp_context=ctx,initializer=init) as pool:results=list(pool.map(one_call,[(r,v,contexts[r['record_id']],options) for r in rows for v in VARIANTS],chunksize=1))
  if len(results)!=6:raise ValueError('SIX_ACTUAL_DEBUG_OUTCOMES_REQUIRED')
  lookup={(x['record_id'],x['variant']):x for x in results};fields=[];totals=collections.Counter()
  for rid in RECORDS:
   pop={'OLD_POLAR_PILOT':wire.task_row(rid,old[rid]['molecule_id'],'pm7_B',old[rid],entries.values(),old[rid]['natoms']),'CURRENT_FORMAL':formal[(rid,'pm7_B')]}
   for v in VARIANTS:pop[v]=wire.task_row(rid,old[rid]['molecule_id'],'pm7_B',lookup[(rid,v)]['detail'],entries.values(),old[rid]['natoms'])
   cells={p:{x['registry_id']:wire.decode(x) for x in row['values']} for p,row in pop.items()}
   for i,e in entries.items():
    if e['task']!='pm7_B':continue
    values={p:items.get(i,wire.MISSING) for p,items in cells.items()};scientific={p:normalized_scientific(v,e) for p,v in values.items()};comparisons={}
    for left,right in [('CURRENT_FORMAL',VARIANTS[0]),('OLD_POLAR_PILOT',VARIANTS[1]),('OLD_POLAR_PILOT',VARIANTS[0]),(VARIANTS[0],VARIANTS[1])]:
     status='MATCH_BITS' if bits_equal(scientific[left],scientific[right]) else 'DIFF';comparisons[left+'__'+right]=status
     if e['classification']!='provenance':totals[(left+'__'+right,status)]+=1
    fields.append({'record_id':rid,'registry_id':i,'source_path':e['source_path'],'classification':e['classification'],'comparisons_json':json.dumps(comparisons,sort_keys=True),'values_json':json.dumps({p:canonical(v) for p,v in values.items()},sort_keys=True,allow_nan=False),'value_sha256_json':json.dumps({p:value_sha(v) for p,v in scientific.items()},sort_keys=True)})
  pq.write_table(pa.Table.from_pylist(fields),a.out/'all_B_registry_field_comparison.parquet',compression='zstd')
  save(a.out/'debug_report.json',{'status':'SIX_CALL_DIAGNOSTIC_COMPLETE_NOT_AN_ACCEPTANCE_DECISION','records':RECORDS,'actual_QM_calls':sum(x['QM_calls'] for x in results),'results':results,'comparison_counts':[{'pair':k[0],'comparison':k[1],'count':n} for k,n in totals.items()],'comparison_precision':'Recursive strict Float64 bits and types, no new tolerance; all registry fields listed, QC and provenance retained with classification','field_comparison':str(a.out/'all_B_registry_field_comparison.parquet'),'candidate_protocol_not_adopted':True,'production_SCI_or_queue_mutated':False,'source_sha256':sha(__file__),'original_input_body_or_ordinary_success_raw_saved':False})
 finally:
  # ProcessPool has joined every worker before this finally block. Only the
  # known empty, owned, regular local flock file may be unlinked here.
  lock_path=scratch/'retained_raw.lock';lock_deleted=False;lock_review=None
  if lock_path.exists() or lock_path.is_symlink():
   info=lock_path.lstat()
   if stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and info.st_nlink==1 and info.st_size==0:
    lock_path.unlink();lock_deleted=True
   else:lock_review='UNKNOWN_LOCAL_LOCK_SHAPE_OR_OWNER_LEFT_FOR_REVIEW'
  # Unknown or failed archival scratch stays for review; no recursive deletion.
  if scratch.exists():
   try:scratch.rmdir()
   except OSError:pass
  save(a.out/'local_scratch_closure.json',{'exact_dispatcher_root':str(scratch),'root_absent':not scratch.exists(),'known_local_retention_lock_deleted':lock_deleted,'lock_review':lock_review,'shared_science_files_changed':False})
 print(json.dumps({'status':'SIX_CALL_DEBUG_CLOSED','report':str(a.out/'debug_report.json'),'QM_calls':6}))
if __name__=='__main__':main()
