"""Readonly diagnostics of closed pilot differences and bounded source samples; no QM."""
from __future__ import annotations
import argparse,collections,concurrent.futures,hashlib,json,math,multiprocessing,os,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
F=ROOT/'acceptance/final_20261016_v1'
OLD=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/wp4_native_full_v4')
REG=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011/reports/label_registry_v2.json')
REPORT=F/'pilot_v4/pilot_comparison.json'
REPORT_SHA='ff9e6dd833cc294159423aecd9581d70c14ee81c034ec4ae9b6cba459ac6747a'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def publish(p,d):
 with p.open('x') as f:json.dump(d,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def init():
 import pyarrow as pa
 pa.set_cpu_count(1);pa.set_io_thread_count(1)
def number(s):
 try:
  v=float(s)
  return v if math.isfinite(v) else None
 except (ValueError,TypeError):return None
def phase(arg):
 import pyarrow.parquet as pq
 path,groups=arg;pf=pq.ParquetFile(path);counts=collections.Counter();pairs=collections.Counter();samples={};numeric={};records=set();aux_records=set()
 for group in groups:
  for row in pf.read_row_group(group,use_threads=False).to_pylist():
   key=(row['calc_type'],row['registry_id'],row['source_path'],row['comparison'])
   counts[key]+=1;records.add(row['record_id']);
   if row['calc_type']=='pm7_B' and row['comparison']=='DIFF' and row['registry_id'] not in (None,22,62) and int(hashlib.sha256(('20261010|AUX|'+row['record_id']).encode()).hexdigest()[:16],16)%10000<100:aux_records.add(row['record_id'])
   x=row['expected_summary'];y=row['actual_summary'];pairs[(key,x,y)]+=1
   ranked=samples.setdefault(key,[]);ranked.append(row);ranked.sort(key=lambda z:(z['record_id'],z['expected_sha256']));del ranked[4:]
   a,b=number(x),number(y)
   if a is not None and b is not None:numeric.setdefault(key,[]).append((abs(a-b),a,b))
 return dict(counts),dict(pairs),samples,numeric,records,aux_records,os.getpid()
def compact(v):
 if isinstance(v,list):return {'type':'list','length':len(v),'first':[compact(x) for x in v[:6]]}
 if isinstance(v,dict):return {'type':'dict','keys':list(v),'values':{k:compact(x) for k,x in list(v.items())[:40]}}
 if isinstance(v,float) and not math.isfinite(v):return {'nonfinite':str(v)}
 if v is None or isinstance(v,(str,bool,int,float)):return v
 return {'type':type(v).__name__,'value':repr(v)}
def flatten(v,path='$'):
 if isinstance(v,dict):
  for k,x in v.items():yield from flatten(x,path+'.'+str(k))
 elif isinstance(v,list):
  for i,x in enumerate(v):yield from flatten(x,path+'['+str(i)+']')
 else:yield path,v
def cells_summary(a,b):
 from wp5_acceptance_recompute import bits_equal
 aa=dict(flatten(a));bb=dict(flatten(b));changed=[];n=0;absolute=[]
 for p in sorted(set(aa)|set(bb)):
  x=aa.get(p,{'ABSENT':True});y=bb.get(p,{'ABSENT':True})
  if not bits_equal(x,y):
   n+=1
   if len(changed)<30:changed.append({'path':p,'expected':compact(x),'actual':compact(y)})
   if type(x) in (int,float) and type(y) in (int,float) and math.isfinite(x) and math.isfinite(y):absolute.append(abs(x-y))
 return {'expected':compact(a),'actual':compact(b),'changed_leaves':n,'expected_leaves':len(aa),'actual_leaves':len(bb),'first_changed_leaves':changed,'max_absolute_numeric_leaf_delta':max(absolute) if absolute else None,'numeric_leaf_deltas':len(absolute)}
def raw_evidence(receipt,details):
 import re,subprocess,tarfile
 reference=receipt['archive'];path=Path(reference['path'])
 if path.stat().st_size!=reference['bytes'] or sha(path)!=reference['sha256']:raise ValueError('OLD_NATIVE_ARCHIVE_SHA_CHANGED')
 targets={}
 for d in details:
  if not d.get('aux_archived'):raise ValueError('DETERMINISTIC_AUX_SELECTION_NOT_ACTUALLY_RETAINED:'+d['record_id'])
  arch=d['archive']
  if arch['path']!=reference['path'] or arch['sha256']!=reference['sha256']:raise ValueError('OLD_CALL_CONTAINER_BINDING_DIFFERS')
  for item in d['archived_files']:
   if item['name'] in ('input.out','input.aux'):targets[arch['member_prefix']+'/'+item['name']]=(d,item)
 result=[];observed=set();proc=subprocess.Popen(['zstd','-d','-c',str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:
  with tarfile.open(fileobj=proc.stdout,mode='r|') as archive:
   for member in archive:
    if member.name not in targets:continue
    if not member.isfile() or member.name in observed:raise ValueError('OLD_NATIVE_MEMBER_SHAPE_OR_DUPLICATE')
    d,item=targets[member.name];body=archive.extractfile(member).read()
    if len(body)!=item['bytes'] or hashlib.sha256(body).hexdigest()!=item['sha256']:raise ValueError('OLD_NATIVE_MEMBER_BYTES_SHA_DIFFERS')
    observed.add(member.name);text=body.decode(errors='replace');lines=text.splitlines();out={'record_id':d['record_id'],'member':member.name,'bytes':len(body),'sha256':item['sha256'],'filename':item['name'],'keywords_from_immutable_detail':d.get('keywords'),'native_coordinates_sha256':d.get('native_coordinates_sha256'),'native_atom_order_sha256':d.get('native_atom_order_sha256')}
    if item['name']=='input.out':
     patterns={'HOF':r'FINAL HEAT OF FORMATION\s*=\s*([-+0-9.DEded]+)','gradient_norm':r'GRADIENT NORM\s*=\s*([-+0-9.DEded]+)','total_energy':r'TOTAL ENERGY\s*=\s*([-+0-9.DEded]+)','electronic_energy':r'ELECTRONIC ENERGY\s*=\s*([-+0-9.DEded]+)'}
     out['all_scalar_occurrences']={k:[{'offset':m.start(),'token':m.group(1),'context':text[max(0,m.start()-160):m.end()+160]} for m in re.finditer(p,text,re.I)] for k,p in patterns.items()}
     needles=re.compile(r'POLAR|SCFCRT|SCF CRITER|ELECTRIC FIELD|FIELD STRENGTH|SELF.CONSISTEN|SCF TEST|ROOT NO\.|INITIAL HEAT|FINAL HEAT|GRADIENT NORM|JOB ENDED',re.I)
     out['header_first80_lines']=lines[:80];out['selected_physics_lines']=[{'line':i+1,'text':line[:600]} for i,line in enumerate(lines) if needles.search(line)][:160];out['tail_last45_lines']=lines[-45:]
    else:
     header=re.compile(r'^[ \t]*([A-Z][A-Z0-9_:./ -]*?)(?:\[(\d+)\])?[ \t]*=[ \t]*(.*)$',re.M)
     wanted={'BOND_ORDERS','EIGENVALUES','MOLECULAR_ORBITAL_OCCUPANCIES','DIP_VEC:DEBYE','AO_CHARGES','GRADIENTS:KCAL/MOL/ANGSTROM','MULLIKEN_ATOM_CHARGES','HEAT_OF_FORMATION:KCAL/MOL'};hits=list(header.finditer(text));occ=[]
     for i,m in enumerate(hits):
      if m.group(1).strip() not in wanted:continue
      tokens=(m.group(3)+' '+text[m.end():hits[i+1].start() if i+1<len(hits) else len(text)]).split()
      occ.append({'field':m.group(1).strip(),'declared_count':int(m.group(2)) if m.group(2) else None,'token_count':len(tokens),'first12':tokens[:12],'last12':tokens[-12:],'all_tokens_sha256':hashlib.sha256(' '.join(tokens).encode()).hexdigest(),'offset':m.start()})
     out['requested_aux_field_occurrences']=occ;out['requested_aux_field_repeat_counts']=dict(collections.Counter(x['field'] for x in occ));out['aux_header_first30_lines']=lines[:30]
    result.append(out)
 finally:
  while proc.stdout.read(1<<20):pass
  proc.stdout.close();error=proc.stderr.read();code=proc.wait()
 if code:raise ValueError('OLD_NATIVE_ARCHIVE_DECODE_FAILED:'+error.decode(errors='replace')[-300:])
 if set(targets)!=observed:raise ValueError('EXACT_REQUIRED_NATIVE_MEMBERS_MISSING')
 return {'archive_reference':reference,'container_sha_verified':True,'all_requested_members_sha_verified':True,'members':result,'input_bodies_saved':False,'raw_bodies_copied':False}
def sample_molecule(arg):
 import pyarrow.dataset as ds,pyarrow.parquet as pq,wp5_parquet as wire
 mol,locators,entries,changed_ids=arg;receipts=list(OLD.glob('bucket_*/molecules/'+hashlib.sha256(mol.encode()).hexdigest()[:24]+'/receipt.json'))
 if len(receipts)!=1:raise ValueError('EXACT_OLD_MOLECULE_RECEIPT_REQUIRED:'+mol)
 receipt_path=receipts[0];receipt=json.loads(receipt_path.read_text());ref=receipt['parquet']
 if sha(ref['path'])!=ref['sha256'] or Path(ref['path']).stat().st_size!=ref['bytes']:raise ValueError('OLD_PARQUET_SHA_CHANGED')
 ids={x['record_id'] for x in locators};originals={}
 for batch in pq.ParquetFile(ref['path']).iter_batches(columns=['details_json'],batch_size=32):
  for item in batch.to_pylist():
   d=json.loads(item['details_json'])
   if d['record_id'] in ids and d['task']=='pm7_B':originals[d['record_id']]=d
 actual={}
 paths={}
 for loc in locators:paths.setdefault(loc['family_parquet_path'],[]).append(loc['record_id'])
 for path,selected in paths.items():
  for row in ds.dataset(path,format='parquet').to_table(filter=ds.field('record_id').isin(selected),use_threads=False).to_pylist():
   loc=next((x for x in locators if x['record_id']==row['record_id'] and row['calc_type']=='pm7_B'),None)
   if loc and all(row[k]==loc[k] for k in ('attempt_id','job_id','task_id','lane')):actual[row['record_id']]=row
 output=[]
 for rid in sorted(ids):
  detail=originals[rid];old=wire.task_row(rid,mol,'pm7_B',detail,entries.values(),detail['natoms']);new=actual[rid]
  aa={x['registry_id']:wire.decode(x) for x in old['values']};bb={x['registry_id']:wire.decode(x) for x in new['values']}
  output.append({'record_id':rid,'original_detail_top_keys':sorted(detail),'original_nonvalues_context':{k:compact(v) for k,v in detail.items() if k!='values'},'actual_locator':next(x for x in locators if x['record_id']==rid),'actual_nonvalues':{k:compact(v) for k,v in new.items() if k!='values'},'changed_field_samples':[{'registry_id':i,'entry':entries[i],'comparison':cells_summary(aa[i],bb[i])} for i in sorted(changed_ids) if i in aa and i in bb]})
 return {'molecule_id':mol,'receipt':str(receipt_path),'receipt_sha256':sha(receipt_path),'receipt_metadata':receipt,'verified_pilot_parquet':ref,'native_raw_evidence':raw_evidence(receipt,[originals[x] for x in sorted(ids)]),'samples':output,'worker_pid':os.getpid()}
def main():
 from wp5_acceptance_catalog import require_slurm
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--workers',type=int,default=24);args=ap.parse_args();require_slurm(args.workers)
 if args.workers!=24:raise ValueError('EXACT24_WORKERS_REQUIRED')
 if sha(REPORT)!=REPORT_SHA:raise ValueError('CLOSED_PILOT_REPORT_SHA_CHANGED')
 report=json.loads(REPORT.read_text());entries={x['registry_id']:x for x in json.loads(REG.read_text())['entries']}
 if sha(REG)!=report['bindings']['registry_sha256']:raise ValueError('REGISTRY_BINDING_CHANGED')
 args.out.mkdir(parents=True,exist_ok=False);path=Path(report['differences']);before={'bytes':path.stat().st_size,'sha256':sha(path)}
 import pyarrow.parquet as pq,pyarrow.dataset as ds
 pf=pq.ParquetFile(path);groups=pf.num_row_groups;counts=collections.Counter();pairs=collections.Counter();samples={};numeric={};records=set();aux_records=set();pids=set();start=time.monotonic();ctx=multiprocessing.get_context('spawn')
 with concurrent.futures.ProcessPoolExecutor(max_workers=24,mp_context=ctx,initializer=init) as pool:
  for cc,pp,ss,nn,rr,ar,pid in pool.map(phase,[(str(path),list(range(i,groups,24))) for i in range(24)],chunksize=1):
   counts.update(cc);pairs.update(pp);records.update(rr);aux_records.update(ar);pids.add(pid)
   for k,v in ss.items():samples.setdefault(k,[]).extend(v);samples[k].sort(key=lambda z:(z['record_id'],z['expected_sha256']));del samples[k][4:]
   for k,v in nn.items():numeric.setdefault(k,[]).extend(v)
 if sum(counts.values())!=report['difference_rows']:raise ValueError('DIFFERENCE_ROW_TOTAL_MISMATCH')
 fields=[]
 for k,count in sorted(counts.items(),key=lambda x:(-x[1],str(x[0]))):
  v=numeric.get(k,[]);d=sorted(x[0] for x in v);pp=[(key[1],key[2],n) for key,n in pairs.items() if key[0]==k];pp.sort(key=lambda x:(-x[2],str(x)))
  fields.append({'calc_type':k[0],'registry_id':k[1],'source_path':k[2],'comparison':k[3],'entry':entries.get(k[1]),'rows':count,'scalar_summary_numeric_rows':len(d),'absolute_numeric_delta_quantiles':{str(q):d[min(len(d)-1,int(q*(len(d)-1)))] for q in (0,.5,.9,.99,1)} if d else {},'diagnostic_delta_bin_counts_NOT_ACCEPTANCE_TOLERANCES':{str(t):sum(x<=t for x in d) for t in (0,1e-12,1e-9,1e-6,.0005,.005,.05,1,10)},'top_summary_pairs':[{'expected':x,'actual':y,'rows':n} for x,y,n in pp[:12]],'representative_difference_rows':samples[k]})
 selected=sorted(aux_records)[:3]
 if not selected:raise ValueError('NO_FIXED_OLD_AUX_SAMPLE_WITH_ACTUAL_DIFFERENCE')
 loc=ds.dataset(F/'pilot_v4/pilot_reference_locators.parquet',format='parquet').to_table(filter=ds.field('record_id').isin(selected)&(ds.field('calc_type')=='pm7_B'),use_threads=False).to_pylist();by_mol={}
 for x in loc:by_mol.setdefault(x['molecule_id'],[]).append(x)
 changed_ids={x['registry_id'] for x in fields if x['registry_id'] is not None and x['comparison']=='DIFF'}
 with concurrent.futures.ProcessPoolExecutor(max_workers=24,mp_context=ctx,initializer=init) as pool:source=list(pool.map(sample_molecule,[(m,rows,entries,changed_ids) for m,rows in by_mol.items()],chunksize=1))
 if sha(path)!=before['sha256'] or path.stat().st_size!=before['bytes']:raise ValueError('DIFFERENCE_FILE_CHANGED_DURING_READ')
 publish(args.out/'diagnostic.json',{'status':'READONLY_DIAGNOSTIC_COMPLETE_NOT_AN_ACCEPTANCE_DECISION','source_report':str(REPORT),'source_report_sha256':REPORT_SHA,'closed_difference_file':{'path':str(path),**before},'rows':sum(counts.values()),'different_records':len(records),'fields':fields,'bounded_source_sample_records':selected,'source_samples':source,'sample_selection':'First3 actual differing B records satisfying frozen old seed20261010|AUX hash<100/10000; actual archived_files must prove AUX retained','effective_statistics_worker_pids':sorted(pids),'seconds':time.monotonic()-start,'source_sha256':sha(__file__),'new_QM':0,'SCI_or_receipt_mutated':False,'actual_host':os.uname().nodename,'slurm_job_id':os.environ['SLURM_JOB_ID'],'tolerance_or_difference_reclassified':False})
 print(json.dumps({'status':'READONLY_DIAGNOSTIC_COMPLETE','report':str(args.out/'diagnostic.json'),'difference_rows':sum(counts.values()),'samples':len(selected),'workers':len(pids)}))
if __name__=='__main__':main()
