"""Read-only reasons for the 43 closed pilot B property-failure differences; no QM."""
from __future__ import annotations
import argparse, collections, concurrent.futures, hashlib, json, math, multiprocessing, os, re, subprocess, tarfile, time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
FINAL=ROOT/'acceptance/final_20261016_v1'
OLD=ROOT.parent/'phase1_dataset_rebuild_20261010/wp4_native_full_v4'
BINDINGS=json.loads(r'''{"diagnostic":{"path":"/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/acceptance/final_20261016_v1/pilot_difference_diagnostic_v2/diagnostic.json","bytes":834777,"sha256":"ec9613ab1dd454815d2a99e7ec6613d4d1d70d76954ab47415dac564c98c90d9"},"report":{"path":"/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/acceptance/final_20261016_v1/pilot_v4/pilot_comparison.json","bytes":322170,"sha256":"ff9e6dd833cc294159423aecd9581d70c14ee81c034ec4ae9b6cba459ac6747a"},"protocol":{"path":"/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/configs/protocol.json","bytes":18720,"sha256":"3e831aa57d4d90376c6107e309484e231038a3536ed0f28371d2f8554149a6bc"},"registry":{"path":"/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011/reports/label_registry_v2.json","bytes":438523,"sha256":"b1a74b7a1fc27b0173dc837cb00de568991309b7ed8157e7c354b65df122654e"},"formal_jobmap":{"path":"/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/acceptance/final_20261016_v1/control_jobmap_actual542_v1.json","bytes":80660,"sha256":"9487a547e770170f40cd22f97b373cc4a5a3e242b37c1a877dc9f3209340a1e8"},"wire_source":{"path":"/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts/wp5_parquet_v2.py","bytes":11543,"sha256":"2864d129336d597ac224d494547143fac35591b6cdcaff6b4520a094fef6c6cd"},"archive_source":{"path":"/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts/wp5_archive_v5.py","bytes":23925,"sha256":"3ef37935402fffc9a5111f0dd6b942b279f42581cdea9aeea1a358169d766477"},"archive_base_source":{"path":"/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts/wp5_archive_v4.py","bytes":32161,"sha256":"56039c79a353a0c2c1459add065f6aa46ca0514e2b8bee18fbf5ccd97c94939b"},"scf_source":{"path":"/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts/wp5_scf_metadata_v2.py","bytes":8410,"sha256":"565c55a2b63ce0de7a7c84302b69cccc0bffe5afb2516cb0df4013bbbf54d64a"}}''')
_OPTIONS={}
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for body in iter(lambda:stream.read(8<<20),b''):h.update(body)
 return h.hexdigest()
def checked(ref):
 p=Path(ref['path'])
 if p.stat().st_size!=ref['bytes'] or sha(p)!=ref['sha256']:raise ValueError('BOUND_SOURCE_CHANGED:'+str(p))
 return p
def publish(path,value):
 with Path(path).open('x') as stream:
  json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
def safe(value):
 import wp5_parquet_v2 as wire
 if value is wire.MISSING:return {'state':'ABSENT'}
 if isinstance(value,float) and not math.isfinite(value):return {'nonfinite':str(value)}
 if isinstance(value,list):return [safe(x) for x in value]
 if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
 return value
def shape(value):
 import wp5_parquet_v2 as wire
 if value is wire.MISSING:return {'state':'ABSENT'}
 if value is None:return {'state':'NULL'}
 if isinstance(value,list):return {'state':'EMPTY' if not value else 'VALUE','type':'list','length':len(value)}
 if isinstance(value,dict):return {'state':'EMPTY' if not value else 'VALUE','type':'dict','keys':sorted(value)}
 return {'state':'VALUE','value':safe(value)}
def selected_difference(row):
 if row['calc_type']!='pm7_B' or row['comparison']!='DIFF':return False
 return ((row['source_path'] in ('status','source_status') and row['actual_summary']=='PROPERTY_FAILED')
         or (row['source_path']=='failure_code' and row['actual_summary']=='NUMERIC_PROPERTY_MISSING'))
def init(options,barrier):
 global _OPTIONS
 _OPTIONS=options
 import pyarrow as pa
 pa.set_cpu_count(1);pa.set_io_thread_count(1)
 barrier.wait(timeout=180)
def output_evidence(files):
 from wp5_scf_metadata_v2 import extract_scf
 markers=re.compile(r'SCF|SELF.CONSIST|CONVERGEN|FAIL|ERROR|UNABLE|NOT AVAILABLE|NOT SUPPORTED|DOES NOT|MISSING|JOB ENDED|CALCULATION DONE|FINAL HEAT|GRADIENT NORM|TERMINAT',re.I)
 evidence=[];seen=0;manifest=[]
 for item in files:
  name=item['name'];body=item['data'];digest=hashlib.sha256(body).hexdigest()
  if digest!=item['sha256']:raise ValueError('RAW_OUTPUT_MEMBER_SHA_CHANGED:'+name)
  manifest.append({'name':name,'bytes':len(body),'sha256':digest})
  if Path(name).name not in ('input.out','process.out'):continue
  for n,line in enumerate(body.decode(errors='replace').splitlines(),1):
   if markers.search(line):
    seen+=1
    if len(evidence)<100:evidence.append({'name':name,'line_1_based':n,'text':line[:600],'file_sha256':digest})
 return {'output_file_manifest':manifest,'SCF_from_actual_output':extract_scf('pm7_B',files),
         'diagnostic_lines':evidence,'diagnostic_lines_total':seen,'diagnostic_lines_limit':100,
         'raw_bodies_saved':False,'input_bodies_saved':False}
def old_raw(detail,receipt):
 ref=receipt.get('archive')
 if not ref:return {'available':False,'reason':'OLD_RECEIPT_HAS_NO_ARCHIVE'}
 checked(ref);call=detail.get('archive') or {}
 if call.get('path')!=ref['path'] or call.get('sha256')!=ref['sha256']:raise ValueError('OLD_CALL_ARCHIVE_BINDING_DIFFERS')
 targets={}
 for item in detail.get('archived_files',[]):
  if item['name'] in ('input.out','process.out'):targets[call['member_prefix']+'/'+item['name']]=item
 if not targets:return {'available':False,'reason':'OLD_OUTPUT_MEMBERS_NOT_DECLARED','archive_reference':ref}
 files=[];observed=set();proc=subprocess.Popen(['zstd','-d','-c',ref['path']],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:
  with tarfile.open(fileobj=proc.stdout,mode='r|') as archive:
   for member in archive:
    if member.name not in targets:continue
    if not member.isfile() or member.name in observed:raise ValueError('OLD_RAW_MEMBER_DUPLICATE_OR_TYPE')
    item=targets[member.name];body=archive.extractfile(member).read()
    if len(body)!=item['bytes'] or hashlib.sha256(body).hexdigest()!=item['sha256']:raise ValueError('OLD_RAW_MEMBER_SHA_OR_BYTES')
    observed.add(member.name);files.append({'name':item['name'],'data':body,'sha256':item['sha256'],'role':'output'})
 finally:
  while proc.stdout.read(1<<20):pass
  proc.stdout.close();error=proc.stderr.read();code=proc.wait()
 if code:raise ValueError('OLD_ARCHIVE_DECODE_FAILED:'+error.decode(errors='replace')[-300:])
 if observed!=set(targets):raise ValueError('OLD_REQUIRED_OUTPUT_MEMBER_MISSING')
 return {'available':True,'archive_reference':ref,'call_member_prefix':call['member_prefix'],
         'container_sha_verified':True,'members_sha_verified':True,**output_evidence(files)}
def new_raw(row,locator):
 from wp5_archive_v5 import ArchiveReader
 ref=json.loads(row.get('raw_output_locator_json') or '{}')
 if not ref.get('output_retained'):return {'available':False,'reason':'FORMAL_RAW_NOT_MARKED_RETAINED','original_locator':ref}
 # The completed canonical locator names the consolidated container. A retained
 # call's historical lane path may legitimately have retired after consolidation.
 path=Path(locator['archive_path'])
 if not path.is_relative_to(ROOT) or path.suffix!='.sqlite':raise ValueError('FORMAL_RAW_CONTAINER_SCOPE')
 reader=ArchiveReader(path,_OPTIONS['dictionaries'])
 try:
  value=reader.get(row['record_id'],'pm7_B',ref.get('execution_id'))
 finally:reader.close()
 meta=value['metadata']
 if any(value.get(k) for k in ('input_files','input_bodies_saved')):raise ValueError('UNEXPECTED_ARCHIVED_INPUT')
 for key in ('attempt_id','job_id','task_id','lane'):
  if str(meta['context'][key])!=str(locator[key]):raise ValueError('RAW_CONTEXT_NOT_CANONICAL:'+key)
 if value['input_bundle_sha256']!=row['input_bundle_sha256']:raise ValueError('RAW_INPUT_HASH_NOT_CANONICAL')
 return {'available':True,'canonical_container_path':str(path),'original_locator':ref,
         'execution_id':value['execution_id'],'raw_sha256':value['raw_sha256'],'retention_reason':value['retention_reason'],
         'raw_sha_verified_by_existing_reader':True,'metadata_context_matches_canonical':True,
         **output_evidence(value['output_files'])}
def one_record(locator,selected_rows):
 import pyarrow.parquet as pq,pyarrow.dataset as ds,wp5_parquet_v2 as wire
 rid=locator['record_id'];mol=locator['molecule_id']
 paths=[OLD/('bucket_'+str(i))/'molecules'/hashlib.sha256(mol.encode()).hexdigest()[:24]/'receipt.json' for i in range(16)]
 paths=[p for p in paths if p.is_file()]
 if len(paths)!=1:raise ValueError('OLD_MOLECULE_RECEIPT_NOT_UNIQUE:'+mol)
 receipt_path=paths[0];receipt=json.loads(receipt_path.read_text());parquet=checked(receipt['parquet']);old=[]
 for batch in pq.ParquetFile(parquet).iter_batches(batch_size=32,columns=['details_json']):
  for item in batch.to_pylist():
   d=json.loads(item['details_json'])
   if d['record_id']==rid and d['task']=='pm7_B':old.append(d)
 if len(old)!=1:raise ValueError('OLD_B_DETAIL_NOT_UNIQUE:'+rid)
 old=old[0];columns=list(wire.SCHEMA.names)
 rows=ds.dataset(locator['family_parquet_path'],format='parquet').to_table(
  columns=columns,filter=(ds.field('record_id')==rid)&(ds.field('calc_type')=='pm7_B'),use_threads=False).to_pylist()
 rows=[r for r in rows if all(str(r[k])==str(locator[k]) for k in ('attempt_id','job_id','task_id','lane'))]
 if len(rows)!=1:raise ValueError('CURRENT_CANONICAL_B_ROW_NOT_UNIQUE:'+rid)
 row=rows[0];entries=_OPTIONS['entries'];decoded={c['registry_id']:wire.decode(c) for c in row['values']}
 by_path={e['source_path']:decoded.get(i,wire.MISSING) for i,e in entries.items() if e['task']=='pm7_B'}
 if row['status']!='PROPERTY_FAILED' or row['failure_code']!='NUMERIC_PROPERTY_MISSING':raise ValueError('SELECTED_OUTCOME_NOT_EXPECTED_PROPERTY_FAILURE')
 if old['status'] not in ('SUCCESS','PROPERTY_FAILED'):raise ValueError('UNEXPECTED_OLD_SOURCE_STATUS')
 wanted=('detail.missing_properties','detail.failure_reason','detail.failure_code','detail.status',
         'detail.diagnostic_lines','detail.qc_codes','detail.returncode','values.normal_end',
         'values.parse_errors','values.property_failure_lines')
 diagnostic={p:safe(by_path.get(p,wire.MISSING)) for p in wanted}
 missing=by_path.get('detail.missing_properties',wire.MISSING)
 names=missing if isinstance(missing,list) else []
 coverage=json.loads(row.get('registry_source_evidence_json') or '{}')
 relevant_ids={i for i,e in entries.items() if e['task']=='pm7_B' and
               any(e['source_path']=='values.'+str(name) or e['source_path'].startswith('values.'+str(name)+'.') for name in names)}
 required={name:shape(by_path.get('values.'+name,wire.MISSING)) for name in _OPTIONS['required_values']}
 original_keys=('status','source_status','failure_code','failure_reason','missing_properties','diagnostic_lines','qc_codes','returncode','keywords')
 result={'record_id':rid,'molecule_id':mol,'worker_pid':os.getpid(),'selected_difference_rows':selected_rows,
  'current_locator':locator,'old_receipt':{'path':str(receipt_path),'bytes':receipt_path.stat().st_size,'sha256':sha(receipt_path)},
  'old_parquet':receipt['parquet'],'old_context':{k:safe(old[k]) for k in original_keys if k in old},
  'current_status':{k:row.get(k) for k in ('status','source_status','failure_code','scf_iterations','converged','software_version_id','elapsed_seconds','numeric_issues')},
  'current_diagnostics':diagnostic,'current_required_property_presence':required,
  'current_missing_property_names':names,'missing_property_registry_ids':sorted(relevant_ids),
  'missing_property_registry_source_rows':[x for x in coverage.get('rows',[]) if x[0] in relevant_ids],
  'registry_source_evidence_status':coverage.get('status'),'registry_source_evidence_issues':coverage.get('issues'),
  'SCF_causality_not_inferred_from_PROPERTY_FAILED':True,'evidence_gaps':[]}
 for label,fn in (('old_raw_output',lambda:old_raw(old,receipt)),('current_raw_output',lambda:new_raw(row,locator))):
  try:
   result[label]=fn()
   if not result[label].get('available'):result['evidence_gaps'].append({'source':label,'reason':result[label]['reason']})
  except Exception as exc:
   result[label]={'available':False,'exception_type':type(exc).__name__,'reason':str(exc)}
   result['evidence_gaps'].append({'source':label,'reason':str(exc),'exception_type':type(exc).__name__})
 return result
def chunk(job):
 out=[]
 for locator,selected in job:
  try:out.append(one_record(locator,selected))
  except Exception as exc:out.append({'record_id':locator['record_id'],'molecule_id':locator['molecule_id'],'worker_pid':os.getpid(),'core_read_error':{'exception_type':type(exc).__name__,'reason':str(exc)}})
 return out
def main():
 from wp5_acceptance_catalog import require_slurm
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--dictionaries',type=Path,required=True);ap.add_argument('--workers',type=int,default=24);a=ap.parse_args()
 require_slurm(a.workers)
 if a.workers!=24:raise ValueError('EXACT_24_PARALLEL_READERS_REQUIRED')
 if os.uname().nodename.split('.')[0] not in {'compute-0-'+str(i) for i in (12,13,14,17,18,19)}:raise ValueError('AUTHORIZED_WP5_NODE_REQUIRED')
 if not a.out.resolve().is_relative_to(FINAL):raise ValueError('NEW_ACCEPTANCE_OUTPUT_ONLY')
 for ref in BINDINGS.values():checked(ref)
 import pyarrow as pa,pyarrow.parquet as pq,pyarrow.dataset as ds,wp5_parquet_v2 as wire
 pa.set_cpu_count(24);pa.set_io_thread_count(24)
 diagnostic=json.loads(Path(BINDINGS['diagnostic']['path']).read_text());report=json.loads(Path(BINDINGS['report']['path']).read_text())
 diff=diagnostic['closed_difference_file'];checked(diff)
 if str(report['differences'])!=diff['path']:raise ValueError('CLOSED_DIFFERENCE_REFERENCE_CHANGED')
 registry=json.loads(Path(BINDINGS['registry']['path']).read_text())
 if sha(BINDINGS['registry']['path'])!=report['bindings']['registry_sha256']:raise ValueError('REGISTRY_NOT_CLOSED_PILOT_REGISTRY')
 entries={e['registry_id']:e for e in registry['entries']}
 columns=['record_id','calc_type','comparison','source_path','expected_summary','actual_summary','registry_id']
 selected=[r for r in pq.read_table(diff['path'],columns=columns).to_pylist() if selected_difference(r)]
 by_id={}
 for row in selected:by_id.setdefault(row['record_id'],[]).append(row)
 counts=collections.Counter(r['source_path'] for r in selected)
 if len(by_id)!=43 or len(selected)!=127 or counts!={'status':42,'source_status':42,'failure_code':43}:raise ValueError('CLOSED43_ID_OR127_STATUS_SELECTION_CHANGED')
 locators=ds.dataset(FINAL/'pilot_v4/pilot_reference_locators.parquet',format='parquet').to_table(
  filter=ds.field('record_id').isin(sorted(by_id))&(ds.field('calc_type')=='pm7_B'),use_threads=True).to_pylist()
 if len(locators)!=43 or {l['record_id'] for l in locators}!=set(by_id):raise ValueError('EXACT43_CURRENT_CANONICAL_LOCATORS')
 formal=json.loads(Path(BINDINGS['formal_jobmap']['path']).read_text())
 formal_ids={str(x['job_id']) for x in formal['jobs']}
 if any(str(l['job_id']) not in formal_ids for l in locators):raise ValueError('SELECTED_LOCATOR_NOT_FORMAL_SCI_PARENT')
 task=next(t for t in json.loads(Path(BINDINGS['protocol']['path']).read_text())['tasks'] if t['name']=='pm7_B')
 options={'entries':entries,'required_values':task['required_values'],'dictionaries':str(a.dictionaries)}
 a.out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
 publish(a.out/'execution_plan.json',{'status':'READONLY43_B_FAILURE_REASON_REVIEW','bindings':BINDINGS,'selected_records':43,
   'selected_difference_rows':127,'selection_fields':dict(counts),'current_B_task':task,'workers':24,
   'raw_policy':'Only existing closed formal/oldpilot outputs, decoded in memory; no raw/input bodies saved',
   'dictionary_manifest':{'path':str(a.dictionaries),'bytes':a.dictionaries.stat().st_size,'sha256':sha(a.dictionaries)},
   'new_QM':0,'source_LMDB_opened':False,'production_or_SCI_mutated':False,'job_id':os.environ['SLURM_JOB_ID'],'host':os.uname().nodename})
 jobs=[[] for _ in range(24)]
 for i,l in enumerate(sorted(locators,key=lambda l:l['record_id'])):jobs[i%24].append((l,by_id[l['record_id']]))
 ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(24);records=[]
 with concurrent.futures.ProcessPoolExecutor(max_workers=24,mp_context=ctx,initializer=init,initargs=(options,barrier)) as pool:
  for batch in pool.map(chunk,jobs,chunksize=1):records.extend(batch)
 records.sort(key=lambda r:r['record_id']);pids={r['worker_pid'] for r in records}
 if len(records)!=43 or len(pids)!=24:raise ValueError('EXACT43_RESULTS_AND24_EFFECTIVE_READERS_REQUIRED')
 errors=[r for r in records if r.get('core_read_error')];missing=collections.Counter();old_states=collections.Counter();conv=collections.Counter();gaps=[]
 for r in records:
  if r.get('core_read_error'):continue
  missing.update(r['current_missing_property_names']);old_states.update([r['old_context'].get('status')]);conv.update([str(r['current_status']['converged'])])
  gaps.extend({'record_id':r['record_id'],**g} for g in r['evidence_gaps'])
 summary={'status':'B_FAILURE_READONLY_SUMMARY_INCOMPLETE' if errors else ('B_FAILURE_READONLY_SUMMARY_COMPLETE_WITH_EVIDENCE_GAPS' if gaps else 'B_FAILURE_READONLY_SUMMARY_COMPLETE_NOT_AN_ACCEPTANCE_DECISION'),
   'selected_records':43,'selected_difference_rows':127,'source_field_counts':dict(counts),'current_missing_property_name_counts':dict(missing),
   'old_source_status_counts':dict(old_states),'current_converged_counts':dict(conv),'core_read_errors':len(errors),'raw_evidence_gaps':gaps,
   'effective_worker_pids':sorted(pids),'elapsed_seconds':time.monotonic()-start,'bindings':BINDINGS,
   'source_sha256':sha(__file__),'host':os.uname().nodename,'uid':os.getuid(),'job_id':os.environ['SLURM_JOB_ID'],
   'new_QM':0,'SCI_or_protocol_mutated':False,'SCF_failure_not_inferred_from_property_failure':True,
   'acceptance_tolerance_or_outcome_reclassified':False,'records':records}
 publish(a.out/'B_property_failure_reasons.json',summary)
 flattened=[{'record_id':r['record_id'],'molecule_id':r['molecule_id'],'worker_pid':r['worker_pid'],
  'old_status':r.get('old_context',{}).get('status'),'current_status':r.get('current_status',{}).get('status'),
  'current_failure_code':r.get('current_status',{}).get('failure_code'),'scf_iterations':r.get('current_status',{}).get('scf_iterations'),
  'converged':r.get('current_status',{}).get('converged'),'missing_property_names_json':json.dumps(r.get('current_missing_property_names')),
  'record_evidence_json':json.dumps(r,sort_keys=True,allow_nan=False)} for r in records]
 pq.write_table(pa.Table.from_pylist(flattened),a.out/'B_property_failure_records.parquet',compression='zstd')
 print(json.dumps({'status':summary['status'],'report':str(a.out/'B_property_failure_reasons.json'),'records':43,'workers':len(pids),'core_read_errors':len(errors),'raw_evidence_gaps':len(gaps)}))
 if errors:raise SystemExit(2)
if __name__=='__main__':main()

