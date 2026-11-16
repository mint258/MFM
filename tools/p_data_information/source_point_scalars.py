"""Recover graph-scalar authority with the existing physical locator index.
All locators and resumable values are restricted to the frozen physical records.
"""
import collections,hashlib,importlib.util,json,pathlib,pickle,sqlite3,time
import numpy as np
import pyarrow.parquet as pq
from stage0_cohort import R,O,load,save,guard
from stage3_information import statistics
B=R/'MFM_p_data_information';SNAP=R/'runs/data_v1_20261025/control/window2_20261105/D6_node20_shared_candidate_20261108_v1/source_snapshot86'
spec=importlib.util.spec_from_file_location('original_scalar_components',SNAP/'workflows/data_v1_final/labels/common.py');original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
def db(path):
 c=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True);c.execute('PRAGMA cache_size=-262144');return c
def chunks(a):
 for i in range(0,len(a),128):yield a[i:i+128]
def cache_save(path,value):
 guard();temporary=path.with_suffix('.partial')
 with temporary.open('wb') as stream:pickle.dump(value,stream,protocol=5)
 temporary.replace(path)
def main():
 started=time.time();guard();panels=load(O/'panel.json');ids=load(O/'pilot_physical_ids.json');pairs=load(O/'pairs.json');defs=load(B/'configs/p_data_information/fields.json')['fields'];enabled={f['field_key'] for f in defs if f['level']=='molecule'};coverage=load('/lfshome/zixiao/data_v1_20261025/full_projection_coverage_20261105_r2/manifest.json');fieldmap=load(coverage['field_map_reference']['path'])
 if isinstance(fieldmap,dict):fieldmap=fieldmap['fields']
 fs=[f for f in fieldmap if f['field_key'] in enabled and f['level']=='molecule'];assert {f['field_key'] for f in fs}==enabled;bytask=collections.defaultdict(list)
 for f in fs:bytask[f['field_key'].split('.')[1]].append(f)
 indexpath='/lfshome/zixiao/data_v1_20261025/D6_full_physical_index_20261105_v3/manifest.json';wanted={};source_values={role:{} for role in panels}
 for role,rows in panels.items():
  for row in rows:
   mid=row['molecule_id'];source_values[role][mid]={}
   for ci,rid in ids[role][mid].items():
    k=(mid,rid);assert k not in wanted;wanted[k]=(role,int(ci));source_values[role][mid][rid]={}
 checkpoint=O/'source_scalar_selected_locators.pkl'
 if checkpoint.exists():
  with checkpoint.open('rb') as stream:point=pickle.load(stream)
  assert point['index']==indexpath and point['wanted']==wanted and point['fields']==enabled;files=point['files'];locator=point['locator'];print('REUSED_SELECTED_LOCATORS',len(locator),flush=True)
 else:
  m=load(indexpath);files={v['id']:v for v in load(m['files_reference']['path'])};ordinals={};locator=collections.defaultdict(lambda:collections.defaultdict(list));c=db(m['canonical_reference']['path'])
  for part in chunks(sorted(wanted,key=lambda k:k[1])):
   marks=','.join('?'*len(part))
   for ordinal,rid,mid in c.execute('SELECT record_ordinal,record_id,molecule_id FROM records WHERE record_id IN ('+marks+')',[k[1] for k in part]):
    if (mid,rid) in wanted:ordinals[ordinal]=(mid,rid)
  c.close();assert len(ordinals)==len(wanted);print('CANONICAL_POINT_RECORDS',len(ordinals),flush=True);storages=[m['QC_locations'],*[x['storage'] for x in m['partitions']]]
  for si,ref in enumerate(storages):
   guard();c=db(ref['path'])
   for part in chunks(sorted(ordinals)):
    marks=','.join('?'*len(part))
    for ordinal,f,rg,r,task in c.execute('SELECT ordinal,file,rg,r,task FROM locations WHERE domain=0 AND ordinal IN ('+marks+')',part):
     if files[f]['family'] not in ['D20','D3','base_geometry']:locator[f][rg].append((r,ordinals[ordinal]))
   c.close();print('LOCATOR_PART',si,len(storages),'FILES',len(locator),flush=True)
  locator={f:dict(groups) for f,groups in locator.items()};files={f:files[f] for f in locator};cache_save(checkpoint,dict(index=indexpath,wanted=wanted,fields=enabled,files=files,locator=locator))
 save(O/'source_scalar_locator_summary.json',dict(index=indexpath,selected_records=len(wanted),files=len(locator),physical_row_groups=sum(map(len,locator.values())),fields=sorted(enabled),selected_locator_cache=str(checkpoint),original_component_reader=str(SNAP/'workflows/data_v1_final/labels/common.py')))
 candidates=load(B/'results/p_data_information/resolution.json')['calibration_2B']['candidates'];candidate_ids={(p['molecule_id'],rid) for p in candidates for rid in [p['native_record_id_a'],p['native_record_id_b']]};patterns={};versions=collections.Counter();candidate_meta=[];observed=set();duplicate_rows=0;read_groups=0;matched=collections.Counter();filecache=O/'source_scalar_selected_files';filecache.mkdir(exist_ok=True)
 for fi,(fid,groups) in enumerate(locator.items()):
  guard();file_checkpoint=filecache/(str(fid)+'.pkl')
  if file_checkpoint.exists():
   with file_checkpoint.open('rb') as stream:state=pickle.load(stream)
   assert state['reference']==files[fid]['reference'];cached=True
  else:
   cached=False;ref=files[fid]['reference'];path=pathlib.Path(ref['path']);assert path.stat().st_size==ref['bytes'];q=pq.ParquetFile(path,pre_buffer=False);state=dict(reference=ref,records=[],metadata=[],versions=collections.Counter(),patterns={},row_groups=len(groups));wanted_columns=['record_id','molecule_id','calc_type','total_atoms','status','source_status','failure_code','software_version_id','scf_iterations','converged','input_file_sha256','input_bundle_sha256','raw_audit_selected','reproduction_package_sha256','precision_by_field_json','registry_source_evidence_json','raw_output_locator_json','numeric_issues','values'];columns=[n for n in wanted_columns if n in q.schema_arrow.names]
   for rg,entries in sorted(groups.items()):
    selected={r:k for r,k in entries};assert len(selected)==len(entries);table=q.read_row_group(rg,columns=columns,use_threads=False)
    for r,(mid,rid) in sorted(selected.items()):
     raw=table.slice(r,1).to_pylist()[0];assert raw['record_id']==rid and raw['molecule_id']==mid;task=raw['calc_type']
     if task not in bytask:continue
     vals={}
     for f,v,indices,reason in original.task_components(raw,'REGISTRY_CELL',bytask[task]):vals[f['field_key']]=v[0] if len(v)==1 and original.numeric(v[0]) and reason is None else None
     state['records'].append((mid,rid,task,vals));state['versions'][str(raw.get('software_version_id'))]+=1;precision=raw.get('precision_by_field_json');h=hashlib.sha256(str(precision).encode()).hexdigest();state['patterns'].setdefault(h,dict(value=precision,rows=0))['rows']+=1
     if (mid,rid) in candidate_ids:state['metadata'].append(dict(role=wanted[(mid,rid)][0],native_record_id=rid,source_reference=ref,row_group=rg,row_within_group=r,**{k:v for k,v in raw.items() if k!='values'}))
    del table
   q.close();cache_save(file_checkpoint,state)
  for mid,rid,task,vals in state['records']:
   key=(mid,rid,task)
   if key in observed:raise ValueError('Ambiguous authority task row')
   observed.add(key);role,ci=wanted[(mid,rid)];source_values[role][mid][rid].update(vals);matched[task]+=1
  versions.update(state['versions']);candidate_meta.extend(state['metadata']);read_groups+=state['row_groups']
  for h,v in state['patterns'].items():patterns.setdefault(h,dict(value=v['value'],rows=0))['rows']+=v['rows']
  if fi%10==0 or cached:print('SOURCE_POINT_FILE',fi+1,len(locator),'GROUPS',read_groups,'CACHE' if cached else 'READ',flush=True)
 cache_save(O/'source_graph_scalars.pkl',source_values);save(O/'source_calibration_candidates_metadata.json',candidate_meta);save(O/'source_scalar_precision_patterns.json',dict(versions=dict(versions),patterns=patterns,matched_tasks=dict(matched),duplicate_rows=duplicate_rows,point_row_groups_read=read_groups))
 result={};record_compare={};graphs={}
 for role,rows in panels.items():
  graph={};within=collections.defaultdict(list);within_units=[];counters={n:collections.Counter() for n in enabled};byid={r['molecule_id']:r for r in rows};pairmid=collections.defaultdict(list)
  for p in pairs[role]['conformer']:pairmid[p['molecule_id']].append(p)
  for ri,row in enumerate(rows):
   mid=row['molecule_id'];mi=row['pilot_index']
   with (O/'samples'/role/(str(mi)+'.pkl')).open('rb') as stream:samples=pickle.load(stream)
   chosen={ci:source_values[role][mid][ids[role][mid][str(ci)]] for ci in row['allowed_conformers']};g={}
   for n in enabled:
    values=[]
    for ci in row['allowed_conformers']:
     t=samples[ci]['targets'].get(n);v=chosen[ci].get(n);ok=v is not None and t is not None and t.valid.all() and np.isfinite(t.raw).all();counters[n]['candidate_records']+=1
     if ok:
      counters[n]['comparable_records']+=1;counters[n]['single_F32_cast_matches_pilot']+=int(float(np.float32(v))==float(t.raw.flat[0]));counters[n]['source_F64_differs_pilot']+=int(v!=float(t.raw.flat[0]))
     values.append(v if ok else None)
    finite=[v for v in values if v is not None];g[n]=dict(first=values[0],median=float(np.median(finite)) if finite else None,valid_conformers=len(finite),minimum=min(finite) if finite else None,maximum=max(finite) if finite else None)
   graph[mid]=g
   for p in pairmid[mid]:
    within_units.append(mid)
    for n in enabled:
     a,b=chosen[p['a']].get(n),chosen[p['b']].get(n);ta,tb=samples[p['a']]['targets'].get(n),samples[p['b']]['targets'].get(n);ok=a is not None and b is not None and ta is not None and tb is not None and ta.valid.all() and tb.valid.all() and np.isfinite(ta.raw).all() and np.isfinite(tb.raw).all();d=abs(a-b) if ok else np.nan;within[n].append(d)
     if ok:
      old=float(ta.raw.flat[0])-float(tb.raw.flat[0]);c=counters[n];c['common_pairs']+=1;c['source_nonzero_pairs']+=int(d>0);c['source_nonzero_to_pilot_zero']+=int(d>0 and old==0);c['source_zero_to_pilot_nonzero']+=int(d==0 and old!=0)
      if d>0:c['source_to_pilot_storage_sign_flip']+=int((a-b)*old<0)
   if ri%500==0:guard();print(role,'AUTHORITY_SUMMARY',ri,len(rows),flush=True)
  levels={}
  for flag in ['core','enriched']:
   ix=[i for i,mid in enumerate(within_units) if byid[mid][flag]];levels['conformer_'+flag]={n:dict(statistics([within[n][i] for i in ix],[within_units[i] for i in ix]),candidate_pairs=len(ix),comparable_pairs=int(sum(np.isfinite(within[n][i]) for i in ix))) for n in enabled}
  for level in ['composition','isomer']:
   mode='median' if level=='isomer' else 'first';groups=[];amplitudes={n:[] for n in enabled}
   for i,p in enumerate(pairs[role][level]):
    groups.append(p['formula_charge'] if level=='isomer' else str(i))
    for n in enabled:
     a,b=graph[p['a']][n][mode],graph[p['b']][n][mode];amplitudes[n].append(abs(a-b) if a is not None and b is not None else np.nan)
   levels[level]={n:dict(statistics(v,groups),candidate_pairs=len(v),comparable_pairs=int(np.isfinite(v).sum())) for n,v in amplitudes.items()}
  result[role]=levels;record_compare[role]={n:dict(c) for n,c in counters.items()};graphs[role]=graph
 save(O/'source_graph_summaries.json',graphs);save(B/'results/p_data_information/source_scalar_authority.json',dict(roles=result,record_and_pair_retention=record_compare,source_index=indexpath,source_layer='WP5 original registry-cell F64; not a calculation-accuracy bound',fields=sorted(enabled),matched_tasks=dict(matched),elapsed_seconds=time.time()-started,local_and_vector_scope='This source comparison establishes graph scalars only; atom/frame/pair source mapping is not inferred from scalar identity',candidate_metadata=str(O/'source_calibration_candidates_metadata.json'),precision_patterns=str(O/'source_scalar_precision_patterns.json')))
 print('SOURCE_SCALAR_AUTHORITY_DONE',flush=True)
if __name__=='__main__':main()