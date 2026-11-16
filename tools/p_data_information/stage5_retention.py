"""Trace frozen physical records pilot -> current D6 -> actual loader; no new members."""
import collections,dataclasses,json,pathlib,pickle,sys,time
from types import SimpleNamespace
import numpy as np
import pyarrow as pa
import pyarrow.dataset as pad
from stage0_cohort import R,D,O,P,load,save,guard
B=R/'MFM_p_data_information'
# The production loader file is read without changing its running processes.
sys.path.insert(0,str(R/'MFM_p_recipe/current'))
from phychem_mfm.phase1.v31_loader import MFM4Dataset,normalize_values
from phychem_mfm.phase1.v31_training import head_layout,V31PDModel
from phychem_mfm.phase1.p_recipe_input import prepare_samples,unpack_targets
from stage3_information import distance,ROUTES
pa.set_cpu_count(4);pa.set_io_thread_count(1)
def rows(path,expr,columns):
 options=pad.ParquetFragmentScanOptions(pre_buffer=False,buffer_size=1048576)
 return pad.dataset(path,format='parquet').scanner(columns=columns,filter=expr,batch_size=64,use_threads=False,batch_readahead=0,fragment_readahead=0,fragment_scan_options=options).to_batches()
def compact_identity(r,allowed_gids=None):
 maps={};intern={}
 for x in r.get('atom_permutations') or []:
  gid=x['gid']
  if not isinstance(gid,str) or not gid or (allowed_gids is not None and gid not in allowed_gids):continue
  value=tuple(x['source_to_M']);value=intern.setdefault(value,value)
  if gid in maps and maps[gid]!=value:maps[gid]=None
  else:maps[gid]=value
 return dict(mi=int(r['molecule_index']),ci=int(r['conformer_index']),mid=r['molecule_id'],rid=r['native_record_id'],maps=maps)
def atom_mapping(p,c,n):
 answers=set()
 for gid in p['maps'].keys()&c['maps'].keys():
  a,b=p['maps'][gid],c['maps'][gid]
  if a is None or b is None or len(a)!=n or len(b)!=n:continue
  if sorted(a)!=list(range(n)) or sorted(b)!=list(range(n)):continue
  permutation=np.empty(n,dtype=int);permutation[list(a)]=b;answers.add(tuple(permutation))
 return np.asarray(next(iter(answers)),dtype=int) if len(answers)==1 else None

def remap(sample,p):
 inv=np.argsort(p);out=dict(sample,Z=sample['Z'][p],pos=sample['pos'][p],pos_perturbed=sample['pos_perturbed'][p] if sample.get('pos_perturbed') is not None else None);targets={}
 for name,t in sample['targets'].items():
  if t.level in ('atom','atom_vector'):targets[name]=dataclasses.replace(t,raw=t.raw[p],values=t.values[p],valid=t.valid[p])
  elif t.pair_index is not None:targets[name]=dataclasses.replace(t,pair_index=inv[t.pair_index])
  else:targets[name]=t
 out['targets']=targets;return out

def packing_metadata(view):
 heads,fields,routes,selections,_=head_layout(view);names=tuple(f.name for f in fields)
 registry=SimpleNamespace(enabled=lambda groups,selected:tuple(f for f in fields if f.group in groups and (selected is None or f.name in selected)))
 return SimpleNamespace(registry=registry,head_by_name={f.name:f for f in heads},selections=selections,definitions={f['name']:f for f in view.fields},view=view,routes=routes,fields=names,_require_vector_normalization=V31PDModel._require_vector_normalization)

def inspect_packing(sample,metadata,counters,geometry):
 packed=prepare_samples([sample],metadata,retain_samples=False).prepared
 geometry['actual_clean_batches_compared']+=1;geometry['actual_clean_batch_coordinate_changes']+=int(not np.array_equal(packed['clean_batch'].pos.numpy(),sample['pos']))
 if 'perturbed_batch' in packed:geometry['actual_perturbed_batches_compared']+=1;geometry['actual_perturbed_batch_coordinate_changes']+=int(not np.array_equal(packed['perturbed_batch'].pos.numpy(),sample['pos_perturbed']))
 targets,affines,names=unpack_targets(packed['loss_targets'])
 for head,members in names.items():
  actual=targets[head];expected=np.concatenate([sample['targets'][n].values for n in members],axis=-1);expected_valid=np.concatenate([sample['targets'][n].valid for n in members],axis=-1).all(-1);offset=0
  for n in members:
   width=sample['targets'][n].values.shape[-1];c=counters[n];c['prepared_records_compared']+=1;c['prepared_numeric_change_records']+=int(not np.array_equal(actual.values.numpy()[:,offset:offset+width],expected[:,offset:offset+width],equal_nan=True));c['prepared_mask_mismatch_records']+=int(not np.array_equal(actual.valid.numpy(),expected_valid));c['prepared_joint_valid_rows']+=int(actual.valid.sum());c['source_component_valid_rows']+=int(sample['targets'][n].valid.all(-1).sum());offset+=width
 for head,ends in packed['pairs'].items():
  n=names[head][0];t=sample['targets'][n];expected=t.pair_index[t.valid.any(-1)].T
  counters[n]['prepared_pair_routes_compared']+=1;counters[n]['prepared_pair_endpoint_changes']+=int(not np.array_equal(ends.numpy(),expected))

def main():
 started=time.time();guard();snapshot=O/('consumer_source_'+str(time.time_ns()));snapshot.mkdir(exist_ok=True)
 for module in ['v31_loader','v31_training','p_recipe_input','v31_grouped_loss']:
  source=pathlib.Path(sys.modules['phychem_mfm.phase1.'+module].__file__);(snapshot/(module+'.py')).write_bytes(source.read_bytes())
 panels=load(O/'panel.json');pairs=load(O/'pairs.json');fields=load(B/'configs/p_data_information/fields.json')['fields'];names=[f['field_key'] for f in fields];fmap={f['field_key']:f for f in fields};view=load(D/'configs/data_v1/training_view_v1.json');view['fields']=[f for f in view['fields'] if f['group']=='P'];routes=load(ROUTES);A1=load(B/'configs/p_recipe/label_parameters/PM7_A1.json').get('normalizations',{});root=R/'runs/data_v1_20261025/artifacts/export/D6_full_v31_20261105_v1/compact';manifest=load(root/'manifest.json');result={}
 cols=['record_kind','molecule_id','native_record_id','molecule_index','conformer_index','atom_permutations']
 for role,panel in panels.items():
  mids=[r['molecule_id'] for r in panel];allowed={(r['pilot_index'],c) for r in panel for c in r['allowed_conformers']};old={};new={};duplicates=set();oldduplicates=set();old_by_address={}
  expr=(pad.field('record_kind')=='P')&pad.field('molecule_id').isin(mids)
  for batch in rows(P/('v31_pilot_'+role)/'id_map.parquet',expr,cols):
   for r in batch.to_pylist():
    if (r['molecule_index'],r['conformer_index']) in allowed:
     p=compact_identity(r);k=(r['molecule_id'],r['native_record_id'])
     if k in old:oldduplicates.add(k)
     old[k]=p;old_by_address[(p['mi'],p['ci'])]=p
  print(role,'PILOT_IDENTITIES',len(old),flush=True)
  split='TRAIN' if role=='TRAIN' else 'FULL';directory=pathlib.Path(manifest['split_roots'][split]);expr=(pad.field('record_kind')=='P')&pad.field('native_record_id').isin(sorted({k[1] for k in old}))&pad.field('molecule_id').isin(mids)
  for batch in rows(directory/'id_map.parquet',expr,cols):
   for r in batch.to_pylist():
    k=(r['molecule_id'],r['native_record_id'])
    if k in new:duplicates.add(k)
    else:new[k]=compact_identity(r,old[k]['maps'] if k in old else set())
  print(role,'CURRENT_IDENTITIES',len(new),flush=True)
  indices=sorted({v['mi'] for k,v in new.items() if k not in duplicates});ds=MFM4Dataset(root,split=split,training_view=view,normalizations=routes,k=10,molecule_indices=indices)
  selector_mismatches=[]
  for field in ds.view.fields:
   if field.get('r73_component'):continue
   for selector in field.get('selectors',[]):
    column=ds.schema['columns'][selector[2]][selector[1]]
    if column['field_key']!=field['field_key']:selector_mismatches.append(dict(field=field['field_key'],actual_column_field=column['field_key'],selector=selector))
  bad_selectors={m['field'] for m in selector_mismatches};metadata=packing_metadata(ds.view)
  stratified_counters={n:{flag:collections.Counter() for flag in ['core','enriched']} for n in names};unitstats={n:collections.defaultdict(list) for n in names};counters={n:collections.Counter() for n in names};errors={n:[] for n in names};amplitudes={n:[] for n in names};identity=collections.Counter();geometry=collections.Counter();curgraph={};pairbymid=collections.defaultdict(list)
  for pair in pairs[role]['conformer']:pairbymid[pair['molecule_id']].append(pair)
  olddist=np.load(O/('distances_'+role+'.npz'))['conformer'];pairpos=0
  for ni,row in enumerate(panel):
   guard();mi=row['pilot_index'];mid=row['molecule_id'];before={n:dict(counters[n]) for n in names};error_start={n:len(errors[n]) for n in names};amp_start={n:len(amplitudes[n]) for n in names}
   with (O/'samples'/role/(str(mi)+'.pkl')).open('rb') as stream:pilot=pickle.load(stream)
   current={};g={}
   for ci,ps in pilot.items():
    p=old_by_address.get((mi,ci));k=(mid,p['rid']) if p else None;c=new.get(k)
    if c is None or k in duplicates or k in oldduplicates:identity['unresolved_or_ambiguous_records']+=1;continue
    if c['ci'] not in ds.choices(c['mi']):identity['current_D5_or_order_excluded']+=1;continue
    cs=ds.read(c['mi'],c['ci']);identity['matched_records']+=1
    for n,t in cs['targets'].items():
     if n in counters:counters[n]['current_record_targets']+=1;counters[n]['loss_disabled_record_targets']+=int(not t.loss_enabled);counters[n]['unmasked_nonfinite_raw_leaves']+=int(np.count_nonzero(t.valid&~np.isfinite(t.raw)));counters[n]['unmasked_nonfinite_normalized_leaves']+=int(np.count_nonzero(t.valid&~np.isfinite(t.values)))
    inspect_packing(cs,metadata,counters,geometry)
    mapping=atom_mapping(p,c,len(ps['Z']))
    if not np.array_equal(np.sort(cs['Z']),np.sort(ps['Z'])):identity['element_counts_mismatch']+=1;continue
    if mapping is None or not np.array_equal(cs['Z'][mapping],ps['Z']):
     identity['atom_mapping_unresolved']+=1;cs=dict(cs,targets={n:t for n,t in cs['targets'].items() if t.level=='molecule' and t.raw.size==1},_atom_mapping_verified=False);current[ci]=cs
     continue
    cs=remap(cs,mapping);cs['_atom_mapping_verified']=True;current[ci]=cs;identity['mapped_records']+=1
    geometry['compared_records']+=1;geometry['different_stored_geometry']+=int(not np.array_equal(ps['pos'],cs['pos']));geometry['perturbed_comparable']+=int(ps.get('pos_perturbed') is not None and cs.get('pos_perturbed') is not None)
    for n in names:
     a,b=ps['targets'].get(n),cs['targets'].get(n)
     if a is None or b is None:continue
     if a.raw.shape==b.raw.shape and a.pair_index is None:
      counters[n]['mask_leaf_comparisons']+=a.valid.size;counters[n]['mask_changed_leaves']+=int(np.count_nonzero(a.valid!=b.valid))
     elif a.pair_index is not None and b.pair_index is not None:
      ia={tuple(p):i for i,p in enumerate(a.pair_index.tolist())};ib={tuple(p):i for i,p in enumerate(b.pair_index.tolist())};common=ia.keys()&ib.keys()
      counters[n]['pair_endpoint_rows_compared']+=len(common);counters[n]['pair_endpoint_symmetric_difference']+=len(ia.keys()^ib.keys())
      for endpoint in common:
       va,vb=a.valid[ia[endpoint]],b.valid[ib[endpoint]]
       if va.shape==vb.shape:counters[n]['mask_leaf_comparisons']+=va.size;counters[n]['mask_changed_leaves']+=int(np.count_nonzero(va!=vb))
   # Cache scalar leaves for the fixed-record cross-level tracer; no local-index sort.
   need=set(row['allowed_conformers']) if row['enriched'] else set(row['allowed_conformers'][:1]);cache_path=O/'current_graph_records'/role/(str(mi)+'.pkl')
   if not cache_path.exists():
    cache_path.parent.mkdir(parents=True,exist_ok=True);rec={};cc=collections.Counter()
    for ci in need:
     p=old_by_address[(mi,ci)];s=current.get(ci);record=dict(native_record_id=p['rid'],exposed=s is not None,fields={});cc['requested_records']+=1
     if s is None:cc['unavailable_or_unexposed']+=1
     else:
      cc['point_read_records']+=1
      for n,t in s['targets'].items():
       if n in bad_selectors or fmap.get(n,{}).get('level')!='molecule' or t.raw.size!=1:continue
       valid=bool(t.valid.all() and np.isfinite(t.raw).all());record['fields'][n]=dict(raw=float(t.raw.flat[0]) if valid else None,normalized=float(t.values.flat[0]) if valid and np.isfinite(t.values).all() else None)
     rec[ci]=record
    with cache_path.open('wb') as stream:pickle.dump(dict(molecule_id=mid,native_ids={ci:old_by_address[(mi,ci)]['rid'] for ci in need},counts=dict(cc),records=rec),stream,protocol=5)
   for pair in pairbymid[mid]:
    sa,sb=current.get(pair['a']),current.get(pair['b'])
    if sa is not None and sb is not None and sa.get('_atom_mapping_verified') and sb.get('_atom_mapping_verified'):
     pa0,pb0=pilot[pair['a']],pilot[pair['b']]
     if not np.array_equal(pa0['pos'],pb0['pos']):geometry['pilot_distinct_stored_geometry_pairs']+=1;geometry['current_collapsed_geometry_pairs']+=int(np.array_equal(sa['pos'],sb['pos']))
     if all(x.get('pos_perturbed') is not None for x in [pa0,pb0,sa,sb]) and not np.array_equal(pa0['pos_perturbed'],pb0['pos_perturbed']):geometry['pilot_distinct_perturbed_pairs']+=1;geometry['current_collapsed_perturbed_pairs']+=int(np.array_equal(sa['pos_perturbed'],sb['pos_perturbed']))
    for j,n in enumerate(names):
     counters[n]['candidate_pairs']+=1
     if sa is None or sb is None or n not in sa['targets'] or n not in sb['targets']:continue
     if n in bad_selectors:continue
     a,b=sa['targets'][n],sb['targets'][n];d,_,_=distance(a,b,sa,sb,fmap[n]);old_d=olddist[pairpos,j]
     if d is None or not np.isfinite(old_d):continue
     counters[n]['comparable_pairs']+=1;errors[n].append(abs(d-old_d))
     if old_d>0:counters[n]['pilot_nonzero_pairs']+=1;counters[n]['current_erased_pairs']+=int(d==0)
     else:counters[n]['pilot_zero_pairs']+=1;counters[n]['new_nonzero_when_pilot_zero']+=int(d>0)
     # Quantization of component differences is distinct from physical alignment.
     if a.pair_index is not None and b.pair_index is not None:
      ia={tuple(p):i for i,p in enumerate(a.pair_index.tolist())};ib={tuple(p):i for i,p in enumerate(b.pair_index.tolist())};common=sorted(ia.keys()&ib.keys());ai=[ia[p] for p in common];bi=[ib[p] for p in common]
     elif a.raw.shape==b.raw.shape:ai=slice(None);bi=slice(None)
     else:continue
     if True:
      ok=a.valid[ai]&b.valid[bi];rawdiff=(a.raw[ai].astype(float)-b.raw[bi].astype(float))[ok];normdiff=(a.values[ai].astype(float)-b.values[bi].astype(float))[ok]
      if rawdiff.size and np.any(rawdiff!=0):
       counters[n]['nonzero_component_pairs']+=1;counters[n]['D4_component_erased_pairs']+=int(np.all(normdiff==0))
       d4amp=float(np.sqrt(np.mean(normdiff**2)));a1amp=None
       if n in A1:
        av=normalize_values(a.raw,A1[n],Z=sa['Z']);bv=normalize_values(b.raw,A1[n],Z=sb['Z']);a1amp=float(np.sqrt(np.mean((av[ai].astype(float)-bv[bi].astype(float))[ok]**2)));counters[n]['A1_component_erased_pairs']+=int(a1amp==0)
       if a1amp is not None and d4amp>0:amplitudes[n].append(a1amp/d4amp)
    pairpos+=1
   for n in names:
    for numerator,denominator,stat in [('current_erased_pairs','pilot_nonzero_pairs','pilot_to_D6_erasure_rate'),('D4_component_erased_pairs','nonzero_component_pairs','D4_component_erasure_rate'),('A1_component_erased_pairs','nonzero_component_pairs','A1_component_erasure_rate')]:
     d=counters[n][denominator]-before[n].get(denominator,0)
     if d>0 and (stat!='A1_component_erasure_rate' or n in A1):unitstats[n][stat].append((counters[n][numerator]-before[n].get(numerator,0))/d)
    if len(errors[n])>error_start[n]:unitstats[n]['absolute_distance_error'].append(float(np.mean(errors[n][error_start[n]:])))
    if len(amplitudes[n])>amp_start[n]:unitstats[n]['A1_D4_amplitude_ratio'].append(float(np.mean(amplitudes[n][amp_start[n]:])))
    for flag in ['core','enriched']:
     if row[flag]:
      for key,value in counters[n].items():stratified_counters[n][flag][key]+=value-before[n].get(key,0)
      for numerator,denominator,stat in [('current_erased_pairs','pilot_nonzero_pairs','pilot_to_D6_erasure_rate'),('D4_component_erased_pairs','nonzero_component_pairs','D4_component_erasure_rate'),('A1_component_erased_pairs','nonzero_component_pairs','A1_component_erasure_rate')]:
       d=counters[n][denominator]-before[n].get(denominator,0)
       if d>0 and (stat!='A1_component_erasure_rate' or n in A1):unitstats[n][stat+'_'+flag].append((counters[n][numerator]-before[n].get(numerator,0))/d)
      if len(amplitudes[n])>amp_start[n]:unitstats[n]['A1_D4_amplitude_ratio_'+flag].append(float(np.mean(amplitudes[n][amp_start[n]:])))
   ds._molecules.clear()
   if ni%250==0:print(role,'RETENTION',ni,len(panel),flush=True)
  ds.close();fieldresult={}
  for n in names:
   c=dict(counters[n]);c['stratified_counts']={flag:dict(v) for flag,v in stratified_counters[n].items()};c['molecule_equal_weight_summaries']={k:dict(independent_molecules=len(v),mean=float(np.mean(v)),median=float(np.median(v))) for k,v in unitstats[n].items()};c.update(pilot_to_D6_absolute_distance_error_median=float(np.median(errors[n])) if errors[n] else None,pilot_to_D6_absolute_distance_error_max=max(errors[n]) if errors[n] else None,A1_to_D4_component_amplitude_ratio_median=float(np.median(amplitudes[n])) if amplitudes[n] else None,reliable_physical_sign_flip_rate=None,reliable_physical_sign_flip_denominator=0,source_to_pilot_difference_erasure=None,reason='Earliest traced layer is pilot FP32; source accuracy and source->pilot losses unresolved; sign not claimed reliable');fieldresult[n]=c
  cross=dict(status='SEE_FIXED_PHYSICAL_RECORD_TRACE',result='results/p_data_information/graph_pipeline_retention.json')
  result[role]=dict(identity=dict(identity),geometry=dict(geometry),fields=fieldresult,graph_scalar_levels=cross,ambiguous_physical_ids=len(duplicates),pilot_ambiguous_physical_ids=len(oldduplicates),selector_mismatches=selector_mismatches)
 save(B/'results/p_data_information/retention.json',dict(roles=result,elapsed_seconds=time.time()-started,source_to_pilot='UNRESOLVED_NO_REGISTERED_POINT_ROW_LOCATOR',production_modified=False,normalizations_refitted=False,loader_source=str(R/'MFM_p_recipe/current/phychem_mfm/phase1/v31_loader.py'),consumer_source_snapshot=str(snapshot),consumer_scope='Actual dataset, geometry/target packing on CPU; no model construction, forward pass, probe or optimization',A1_parameters=str(B/'configs/p_recipe/label_parameters/PM7_A1.json')))
 print('RETENTION_DONE',flush=True)
if __name__=='__main__':main()
