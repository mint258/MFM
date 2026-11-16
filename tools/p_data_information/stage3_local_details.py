"""Local maxima and element-specific RMS differences from existing frozen caches."""
import collections,pickle
import numpy as np
from stage0_cohort import R,O,load,save,guard
from stage3_information import rotation,statistics
B=R/'MFM_p_data_information'
def main():
 fields=load(B/'configs/p_data_information/fields.json')['fields'];fmap={f['field_key']:f for f in fields};panels=load(O/'panel.json');pairs=load(O/'pairs.json');result={}
 for role,rows in panels.items():
  acc=collections.defaultdict(lambda:collections.defaultdict(lambda:collections.defaultdict(list)));bymid=collections.defaultdict(list)
  for p in pairs[role]['conformer']:bymid[p['molecule_id']].append(p)
  for ri,row in enumerate(rows):
   with (O/'samples'/role/(str(row['pilot_index'])+'.pkl')).open('rb') as stream:samples=pickle.load(stream)
   for p in bymid[row['molecule_id']]:
    sa,sb=samples[p['a']],samples[p['b']]
    for name,a in sa['targets'].items():
     b=sb['targets'].get(name)
     if b is None or a.level not in ('atom','atom_vector','pair'):continue
     x,y=a.raw.astype(float),b.raw.astype(float);labels=None
     if a.pair_index is not None:
      ia={tuple(v):i for i,v in enumerate(a.pair_index.tolist())};ib={tuple(v):i for i,v in enumerate(b.pair_index.tolist())};common=sorted(ia.keys()&ib.keys())
      if not common:continue
      x=x[[ia[v] for v in common]];y=y[[ib[v] for v in common]];labels=np.full(len(x),-1)
     else:labels=sa['Z']
     if x.shape!=y.shape:continue
     if a.representation=='vector':
      ga,gb=sa['pos'],sb['pos']
      if 'perturb' in str(fmap[name].get('geometry_route','')).lower():ga,gb=sa.get('pos_perturbed'),sb.get('pos_perturbed')
      if ga is None or gb is None or x.shape[-1]!=3:continue
      ok=np.isfinite(x).all(-1)&np.isfinite(y).all(-1);diff=np.linalg.norm(x@rotation(ga,gb,sa['Z']>1)-y,axis=-1)
     else:ok=(np.isfinite(x)&np.isfinite(y)).all(-1);diff=np.sqrt(np.mean((x-y)**2,axis=-1))
     for element in np.unique(labels):
      valid=ok&(labels==element)
      if not valid.any():continue
      value=diff[valid];group=str(int(element)) if element>=0 else 'directed_pairs';acc[name][group]['rms'].append((float(np.sqrt(np.mean(value**2))),row['molecule_id']));acc[name][group]['maximum'].append((float(np.max(value)),row['molecule_id']))
   if ri%500==0:guard();print(role,'LOCAL_DETAILS',ri,len(rows),flush=True)
  out={}
  flags={r['molecule_id']:{k:r[k] for k in ['core','enriched']} for r in rows}
  for name,groups in acc.items():
   out[name]={}
   for element,metrics in groups.items():
    out[name][element]={flag:{metric:dict(statistics([v for v,mid in pairs if flags[mid][flag]],[mid for v,mid in pairs if flags[mid][flag]]),observed_max=max([v for v,mid in pairs if flags[mid][flag]],default=None)) for metric,pairs in metrics.items()} for flag in ['core','enriched']}
  result[role]=out
 save(B/'results/p_data_information/local_differences.json',dict(roles=result,atom_element='atomic number',pair_endpoint_policy='existing directed endpoints only',maximum_statistic='per-pair maximum local Euclidean/absolute difference, then equal-weight group summary',reliability='Stored-label differences, not a calculation-noise guarantee'))
 print('LOCAL_DETAILS_DONE',flush=True)
if __name__=='__main__':main()
