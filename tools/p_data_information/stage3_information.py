"""Frozen-pair raw/normalized information and coverage, using shared pilot sources."""
import collections,json,pathlib,sys,time,pickle,dataclasses
import numpy as np
from stage0_cohort import R,D,O,P,load,save,guard
B=R/'MFM_p_data_information'
sys.path.insert(0,str(B/'current'))
from phychem_mfm.phase1.v31_loader import MFM4Dataset
from stage1_geometry import key
ROUTES='/lfshome/zixiao/data_v1_20261025/window2_TRAIN_normalization_parameters_20261107_v1/routes.json'
def rotation(a,b,heavy):
 a=a[heavy].astype(float);b=b[heavy].astype(float);a-=a.mean(0);b-=b.mean(0);u,s,v=np.linalg.svd(a.T@b);u[:,-1]*=np.linalg.det(u@v);return u@v

def distance(a,b,sa,sb,field):
 if a.representation=='vector' and a.raw.shape[-1]!=3:
  prefix=field['field_key'].rsplit('.',1)[0];components=[prefix+'.'+axis for axis in ('x','y','z')]
  if sa is None or sb is None or any(n not in sa['targets'] or n not in sb['targets'] for n in components):return None,0,int(a.raw.size)
  ar=np.concatenate([sa['targets'][n].raw for n in components],axis=-1);br=np.concatenate([sb['targets'][n].raw for n in components],axis=-1)
  a=dataclasses.replace(a,raw=ar,level='molecule');b=dataclasses.replace(b,raw=br,level='molecule')
 x=a.raw.astype(float);y=b.raw.astype(float)
 if a.pair_index is not None:
  ia={tuple(p):i for i,p in enumerate(a.pair_index.tolist())};ib={tuple(p):i for i,p in enumerate(b.pair_index.tolist())};common=sorted(ia.keys()&ib.keys())
  if not common:return None,0,0
  x=x[[ia[p] for p in common]];y=y[[ib[p] for p in common]]
 if x.shape!=y.shape:return None,0,0
 if a.level.startswith('molecule') and x.size not in (1,3):return None,0,int(x.size)
 if 'tensor' in a.representation:return None,0,int(x.size)
 valid=np.isfinite(x)&np.isfinite(y)
 if a.representation=='vector' or (x.ndim==2 and x.shape[-1]==3):
  # Published frame rules; charged-origin-sensitive molecular vectors remain unknown.
  if a.level.startswith('molecule') and field.get('actual_task_charge') not in (0,None):return None,0,int(x.size)
  ga,gb=sa['pos'],sb['pos']
  if 'perturb' in str(field.get('geometry_route','')).lower():ga,gb=sa.get('pos_perturbed'),sb.get('pos_perturbed')
  if ga is None or gb is None:return None,0,int(x.size)
  if sa['Z'].shape!=sb['Z'].shape or not np.array_equal(sa['Z'],sb['Z']):return None,0,int(x.size)
  valid=np.isfinite(x).all(-1)&np.isfinite(y).all(-1)
  if not valid.any():return None,0,int(x.size)
  diff=(x@rotation(ga,gb,sa['Z']>1)-y)[valid]
  d=np.linalg.norm(diff) if a.level.startswith('molecule') else np.sqrt(np.mean(np.sum(diff*diff,axis=-1)))
  return float(d),int(valid.sum()),int(len(valid))
 if not valid.any():return None,0,int(x.size)
 diff=(x-y)[valid];d=abs(float(diff[0])) if x.size==1 else float(np.sqrt(np.mean(diff**2)))
 return d,int(valid.sum()),int(valid.size)

def statistics(values,units):
 grouped=collections.defaultdict(list)
 for x,g in zip(values,units):
  if np.isfinite(x):grouped[g].append(float(x))
 a=np.array([np.mean(v) for v in grouped.values()]);n=len(a)
 if not n:return dict(independent_units=0,median=None,p10=None,p90=None,ci95=None,reason='No comparable pairs')
 rng=np.random.default_rng(20261025);boot=[]
 for start in range(0,1000,100):boot.extend(np.median(a[rng.integers(n,size=(100,n))],axis=1).tolist())
 return dict(independent_units=n,median=float(np.median(a)),p10=float(np.quantile(a,.1)),p90=float(np.quantile(a,.9)),ci95=list(map(float,np.quantile(boot,[.025,.975]))))

def main():
 started=time.time();panels=load(O/'panel.json');pairs=load(O/'pairs.json');fields=load(B/'configs/p_data_information/fields.json')['fields'];names=[f['field_key'] for f in fields];byname={f['field_key']:f for f in fields};view=load(D/'configs/data_v1/training_view_v1.json');view['fields']=[f for f in view['fields'] if f.get('group')=='P'];routes=load(ROUTES);summary={};coverage={}
 for role,rows in panels.items():
  bymid={r['molecule_id']:r for r in rows};ds=MFM4Dataset(P,split=role,training_view=view,normalizations=routes,k=10,molecule_indices=[r['pilot_index'] for r in rows]);graph={};records=[];within=[];within_units=[];record_counts=np.zeros((len(rows),len(fields),2),dtype=np.int64);scales={n:float(np.asarray(ds.view.normalizations[n]['scale']).reshape(-1)[0]) if np.asarray(ds.view.normalizations[n]['scale']).size==1 and n.rsplit('.',1)[-1] not in ('x','y','z') else None for n in names}
  cache_dir=O/'samples'/role;cache_dir.mkdir(parents=True,exist_ok=True)
  save(O/('normalizations_'+role+'.json'),ds.view.normalizations)
  pairbymid=collections.defaultdict(list)
  for pair in pairs[role]['conformer']:pairbymid[pair['molecule_id']].append(pair)
  for ni,row in enumerate(rows):
   guard();mid=row['molecule_id'];mi=row['pilot_index'];cache_path=cache_dir/(str(mi)+'.pkl')
   if cache_path.exists():
    with cache_path.open('rb') as stream:samples=pickle.load(stream)
   else:samples={ci:ds.read(mi,ci) for ci in row['allowed_conformers']}
   g={}
   assert list(samples)==row['allowed_conformers']
   if not cache_path.exists():
    with cache_path.open('wb') as output:pickle.dump(samples,output,protocol=5)
   for j,name in enumerate(names):
    ts=[s['targets'].get(name) for s in samples.values()];record_counts[ni,j]=[sum(t is not None and t.valid.any() for t in ts),len(ts)]
    if ts and all(t is not None and t.level=='molecule' and t.raw.size==1 for t in ts):
     vals=[float(t.raw.reshape(-1)[0]) for t in ts];valid=[v for v in vals if np.isfinite(v)]
     g[name]=dict(first=vals[0] if np.isfinite(vals[0]) else None,median=float(np.median(valid)) if valid else None,minimum=min(valid) if valid else None,maximum=max(valid) if valid else None,valid_conformers=len(valid))
   graph[mid]=g
   for pair in pairbymid[mid]:
    sa,sb=samples[pair['a']],samples[pair['b']];v=np.full((len(fields),3),np.nan)
    for j,name in enumerate(names):
     ta,tb=sa['targets'].get(name),sb['targets'].get(name)
     if ta is None or tb is None:continue
     d,n,total=distance(ta,tb,sa,sb,byname[name]);v[j]=[d if d is not None else np.nan,n,total]
    within.append(v);within_units.append(mid)
   ds._molecules.clear()
   if ni%250==0:print(role,'LABELS',ni,len(rows),flush=True)
  ds.close();within=np.array(within).reshape((-1,len(fields),3));arrays=dict(conformer=within[:,:,0]);units=dict(conformer=within_units)
  for level in ['composition','isomer']:
   vals=[];groups=[]
   for k,pair in enumerate(pairs[role][level]):
    a,b=graph[pair['a']],graph[pair['b']];v=np.full(len(fields),np.nan)
    for j,name in enumerate(names):
     if name not in a or name not in b:continue
     x,y=a[name],b[name];mode='median' if level=='isomer' else 'first'
     if x[mode] is not None and y[mode] is not None:v[j]=abs(x[mode]-y[mode])
    vals.append(v);groups.append(pair['formula_charge'] if level=='isomer' else str(k))
   arrays[level]=np.array(vals).reshape((-1,len(fields)));units[level]=groups
  guard();np.savez_compressed(O/('distances_'+role+'.npz'),**arrays,conformer_valid_sites=within[:,:,1],conformer_candidate_sites=within[:,:,2],record_valid_counts=record_counts)
  save(O/('graph_summaries_'+role+'.json'),graph);level_summary={}
  for level,a in arrays.items():
   strata=['core','enriched'] if level=='conformer' else [level]
   for stratum in strata:
    indices=np.array([i for i,g in enumerate(units[level]) if level!='conformer' or bymid[g][stratum]],dtype=int)
    field_summary={}
    for j,name in enumerate(names):
     v=a[indices,j];groups=[units[level][i] for i in indices];s=statistics(v,groups)
     s.update(candidate_pairs=len(indices),comparable_pairs=int(np.isfinite(v).sum()),nonzero_stored_differences=int(np.count_nonzero(v[np.isfinite(v)])),scale=scales[name],median_D4_amplitude=s['median']/scales[name] if s['median'] is not None and scales[name] is not None else None,reliability='UNRESOLVED_CALCULATION_PRECISION',comparison_layer='pilot_MFM4_raw_FP32')
     field_summary[name]=s
    level_summary[level+'_'+stratum]=field_summary
  summary[role]=level_summary;coverage[role]=dict(molecules=len(rows),records=int(record_counts[:,0,1].sum()),fields={name:dict(valid_records=int(record_counts[:,j,0].sum()),candidate_records=int(record_counts[:,j,1].sum())) for j,name in enumerate(names)},pair_candidates={k:len(a) for k,a in arrays.items()})
  save(O/('unit_ids_'+role+'.json'),units)
 save(B/'results/p_data_information/conditional_information.json',dict(roles=summary,bootstrap=dict(repetitions=1000,seed=20261025,unit='molecule/formula-group/disjoint-composition-pair',statistic='median of group mean pair distances'),source_precision='UNRESOLVED; no raw-source reliability claim',elapsed_seconds=time.time()-started))
 save(B/'results/p_data_information/missingness.json',dict(roles=coverage,source='frozen panel; no missing values filled'))
 print('CONDITIONAL_INFORMATION_DONE',flush=True)
if __name__=='__main__':main()
