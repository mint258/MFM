"""Fixed physical-record graph-scalar retention, with resumable point caches.
This corrects the initial scalar summary's local-index sort and common-set issue.
"""
import argparse,collections,json,pathlib,pickle
import numpy as np
import pyarrow.dataset as pad
from stage0_cohort import R,D,O,load,save,guard
from stage5_retention import rows,MFM4Dataset,ROUTES
from stage3_information import statistics
B=R/'MFM_p_data_information';CACHE=O/'current_graph_records'
def write_cache(path,value):
 guard();path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix('.partial')
 with temporary.open('wb') as stream:pickle.dump(value,stream,protocol=5)
 temporary.replace(path)
def get_cache(path):
 with path.open('rb') as stream:return pickle.load(stream)
def fixed_layers(records,order,mode):
 """Use the prescribed first record, or the identical common record subset."""
 chosen=order[:1] if mode=='first' else order
 a=[records[c] for c in chosen if c in records and all(records[c].get(k) is not None for k in ['source','pilot','current'])]
 if mode=='first' and len(a)!=1:return None
 if not a:return None
 out={k:float(np.median([r[k] for r in a])) for k in ['source','pilot','current']};out['normalized']=float(np.median([r['normalized'] for r in a])) if all(r.get('normalized') is not None for r in a) else None;out['common_records']=len(a);return out

def collect():
 panels=load(O/'panel.json');ids=load(O/'pilot_physical_ids.json');pairs=load(O/'pairs.json');fields=load(B/'configs/p_data_information/fields.json')['fields'];names={f['field_key'] for f in fields if f['level']=='molecule'};view=load(D/'configs/data_v1/training_view_v1.json');view['fields']=[f for f in view['fields'] if f['field_key'] in names];root=R/'runs/data_v1_20261025/artifacts/export/D6_full_v31_20261105_v1/compact';manifest=load(root/'manifest.json');result={}
 for role,panel in panels.items():
  bymid={r['molecule_id']:r for r in panel};need=collections.defaultdict(set)
  for p in pairs[role]['composition']:
   for mid in [p['a'],p['b']]:need[mid].update(bymid[mid]['allowed_conformers'][:1])
  for p in pairs[role]['isomer']:
   for mid in [p['a'],p['b']]:need[mid].update(bymid[mid]['allowed_conformers'])
  wanted={(mid,ids[role][mid][str(ci)]) for mid,cs in need.items() for ci in cs};split='TRAIN' if role=='TRAIN' else 'FULL';directory=pathlib.Path(manifest['split_roots'][split]);identity_cache=O/('current_graph_identities_'+role+'.pkl')
  if identity_cache.exists():
   cached=get_cache(identity_cache);assert cached['wanted']==wanted;mapping=cached['mapping'];ambiguous=cached['ambiguous']
  else:
   mapping={};ambiguous=set();expr=(pad.field('record_kind')=='P')&pad.field('native_record_id').isin(sorted({rid for mid,rid in wanted}))&pad.field('molecule_id').isin(sorted(need))
   for batch in rows(directory/'id_map.parquet',expr,['molecule_id','native_record_id','molecule_index','conformer_index']):
    for r in batch.to_pylist():
     k=(r['molecule_id'],r['native_record_id'])
     if k not in wanted:continue
     if k in mapping:ambiguous.add(k)
     else:mapping[k]=(int(r['molecule_index']),int(r['conformer_index']))
   write_cache(identity_cache,dict(wanted=wanted,mapping=mapping,ambiguous=ambiguous))
  print(role,'FIXED_GRAPH_IDENTITIES',len(mapping),'REQUESTED',len(wanted),flush=True);ds=MFM4Dataset(root,split=split,training_view=view,normalizations=load(ROUTES),k=10,molecule_indices=sorted({mi for k,(mi,ci) in mapping.items() if k not in ambiguous}));bad=set()
  for field in ds.view.fields:
   for selector in field.get('selectors',[]):
    if ds.schema['columns'][selector[2]][selector[1]]['field_key']!=field['field_key']:bad.add(field['field_key'])
  counters=collections.Counter();fresh=0
  for ni,row in enumerate(panel):
   mid=row['molecule_id']
   if mid not in need:continue
   guard();path=CACHE/role/(str(row['pilot_index'])+'.pkl')
   if path.exists():
    cached=get_cache(path);assert cached['native_ids']=={ci:ids[role][mid][str(ci)] for ci in need[mid]};counters.update(cached['counts'])
   else:
    records={};c=collections.Counter()
    for ci in sorted(need[mid]):
     rid=ids[role][mid][str(ci)];key=(mid,rid);c['requested_records']+=1;record=dict(native_record_id=rid,exposed=False,fields={})
     if key in ambiguous or key not in mapping:c['missing_or_ambiguous_identity']+=1
     else:
      mi2,ci2=mapping[key]
      if ci2 not in ds.choices(mi2):c['current_k10_or_D5_unexposed']+=1
      else:
       sample=ds.read(mi2,ci2);c['point_read_records']+=1;fresh+=1;record['exposed']=True
       for n,t in sample['targets'].items():
        if n in bad or t.raw.size!=1:continue
        valid=bool(t.valid.all() and np.isfinite(t.raw).all());record['fields'][n]=dict(raw=float(t.raw.flat[0]) if valid else None,normalized=float(t.values.flat[0]) if valid and np.isfinite(t.values).all() else None)
     records[ci]=record
    write_cache(path,dict(molecule_id=mid,native_ids={ci:ids[role][mid][str(ci)] for ci in need[mid]},counts=dict(c),records=records));counters.update(c)
   ds._molecules.clear()
   if ni%250==0:print(role,'FIXED_GRAPH_CACHE',ni,len(panel),flush=True)
  ds.close();result[role]=dict(counts=dict(counters),fresh_point_reads_this_invocation=fresh,selector_mismatch_fields=sorted(bad),identity_cache=str(identity_cache))
 save(O/'current_graph_collection.json',dict(roles=result,scope='Only graph scalars of previously frozen physical records; corrective reread after scalar summary order bug',source_numeric_records_added=0,QM_calls=0))
 print('FIXED_GRAPH_RECORD_CACHE_READY',flush=True)

def summarize():
 panels=load(O/'panel.json');pairs=load(O/'pairs.json');ids=load(O/'pilot_physical_ids.json');authority=get_cache(O/'source_graph_scalars.pkl');fields=load(B/'configs/p_data_information/fields.json')['fields'];names=sorted({f['field_key'] for f in fields if f['level']=='molecule'});result={}
 for role,panel in panels.items():
  data={};byid={r['molecule_id']:r for r in panel};norms=load(O/('normalizations_'+role+'.json'));offsets={}
  for row in panel:
   mid=row['molecule_id'];path=CACHE/role/(str(row['pilot_index'])+'.pkl')
   if not path.exists():continue
   current=get_cache(path)['records'];pilot=get_cache(O/'samples'/role/(str(row['pilot_index'])+'.pkl'));perfield={n:{} for n in names};cnt=collections.Counter(row['elements'])
   for n in names:
    ref=norms[n].get('element_reference');offsets[(mid,n)]=float(ref.get('intercept',0))+sum(cnt.get(int(z),0)*coef for z,coef in zip(ref['basis'],ref['coefficients'])) if ref else 0.
   for ci,c in current.items():
    rid=c['native_record_id']
    for n in names:
     p=pilot[ci]['targets'].get(n);v=c['fields'].get(n,{})
     perfield[n][ci]=dict(source=authority[role][mid][rid].get(n),pilot=float(p.raw.flat[0]) if p is not None and p.valid.all() and np.isfinite(p.raw).all() else None,current=v.get('raw'),normalized=v.get('normalized'))
   data[mid]=perfield
  levels={}
  for level in ['composition','isomer']:
   mode='first' if level=='composition' else 'median';counters={n:collections.Counter() for n in names};metrics={n:collections.defaultdict(list) for n in names};units={n:[] for n in names};rate_units={n:collections.defaultdict(lambda:collections.defaultdict(lambda:[0,0])) for n in names}
   for pi,pair in enumerate(pairs[role][level]):
    ma,mb=pair['a'],pair['b'];unit=pair['formula_charge'] if level=='isomer' else str(pi)
    for n in names:
     c=counters[n];c['candidate_pairs']+=1
     if ma not in data or mb not in data:continue
     a=fixed_layers(data[ma][n],byid[ma]['allowed_conformers'],mode);b=fixed_layers(data[mb][n],byid[mb]['allowed_conformers'],mode)
     if a is None or b is None:continue
     c['same_physical_subset_comparable_pairs']+=1;c['common_endpoint_records']+=a['common_records']+b['common_records'];d={k:a[k]-b[k] for k in ['source','pilot','current']};scale=float(np.asarray(norms[n]['scale']).flat[0]);math_delta=(d['current']-(offsets[(ma,n)]-offsets[(mb,n)]))/scale;actual_delta=a['normalized']-b['normalized'] if a['normalized'] is not None and b['normalized'] is not None else None
     for k,v in d.items():metrics[n][k+'_amplitude'].append(abs(v))
     metrics[n]['pilot_current_signed_difference_error'].append(abs(d['current']-d['pilot']));metrics[n]['mathematical_D4_amplitude'].append(abs(math_delta));metrics[n]['actual_D4_amplitude'].append(abs(actual_delta) if actual_delta is not None else np.nan);units[n].append(unit)
     for name,old,new in [('source_to_pilot',d['source'],d['pilot']),('source_to_current',d['source'],d['current']),('pilot_to_current',d['pilot'],d['current']),('D4_quantization',math_delta,actual_delta)]:
      if new is None:continue
      if old!=0:
       c[name+'_nonzero_pairs']+=1;c[name+'_erased_pairs']+=int(new==0);rate_units[n][name][unit][0]+=int(new==0);rate_units[n][name][unit][1]+=1
   out={}
   for n in names:
    rates={}
    for key,groups in rate_units[n].items():
     vals=[a/b for a,b in groups.values() if b];rates[key]=dict(independent_units=len(vals),equal_unit_mean=float(np.mean(vals)) if vals else None,median=float(np.median(vals)) if vals else None)
    out[n]=dict(counts=dict(counters[n]),metrics={key:statistics(v,units[n]) for key,v in metrics[n].items()},group_weighted_erasure_rates=rates,physical_reliability='Global source computation bound unresolved; storage-direction evidence only')
   levels[level]=out
  result[role]=levels
 output=dict(roles=result,collection=load(O/'current_graph_collection.json'),comparison='Prescribed first frozen native record; isomer median on identical source/pilot/current valid conformers',original_scalar_local_sort_summary='Superseded as exploratory; never used for final erasure claims',normalization='Source/pilot/current raw differences and actual D4 differences separate; known element-reference subtraction is not quantization')
 save(B/'results/p_data_information/graph_pipeline_retention.json',output);print('FIXED_GRAPH_PIPELINE_RETENTION_DONE',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--collect-only',action='store_true');p.add_argument('--summarize-only',action='store_true');a=p.parse_args()
 if not a.summarize_only:collect()
 if not a.collect_only:summarize()