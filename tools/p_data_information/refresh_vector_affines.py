"""Refresh only affine vector summaries/family distances after source packing review."""
import collections
import numpy as np
from stage0_cohort import R,O,load,save
B=R/'MFM_p_data_information'
def main():
 c=load(B/'results/p_data_information/conditional_information.json');j=load(B/'results/p_data_information/family_complementarity.json');fields=load(B/'configs/p_data_information/fields.json')['fields'];names=[f['field_key'] for f in fields];verified={}
 for role in ['TRAIN','VAL']:
  norms=load(O/('normalizations_'+role+'.json'));scales={}
  for name in names:
   v=np.asarray(norms[name]['scale']);s=float(v.flat[0]) if v.size==1 else None
   if name.rsplit('.',1)[-1] in ('x','y','z'):
    members=[name.rsplit('.',1)[0]+'.'+axis for axis in ('x','y','z')]
    if any(m not in norms for m in members) or s is None or any(np.asarray(norms[m]['scale']).size!=1 or float(np.asarray(norms[m]['scale']).flat[0])!=s or np.any(np.asarray(norms[m]['center'])!=0) for m in members):s=None
   scales[name]=s
  verified[role]={n:s for n,s in scales.items() if n.rsplit('.',1)[-1] in ('x','y','z')}
  for level,fs in c['roles'][role].items():
   for n,s in fs.items():
    if n.rsplit('.',1)[-1] in ('x','y','z'):
     s['scale']=scales[n];s['median_D4_amplitude']=s['median']/scales[n] if s['median'] is not None and scales[n] is not None else None;s['raw_median_over_D4_scale']=s['median_D4_amplitude'];s['vector_scale_evidence']='Actual grouped target packing requires zero center and one common triplet scale; verified from existing parameters'
  z=np.load(O/('distances_'+role+'.npz'));units=load(O/('unit_ids_'+role+'.json'))
  for level in ['composition','isomer','conformer']:
   fams=sorted({f['family'] for f in fields if level=='conformer' or f['level']=='molecule'});a=z[level];T=np.full((len(a),len(fams)),np.nan);definitions={};unscaled={}
   for fi,fam in enumerate(fams):
    ix=[i for i,f in enumerate(fields) if f['family']==fam and (level=='conformer' or f['level']=='molecule') and scales[names[i]] is not None];unscaled[fam]=[f['field_key'] for f in fields if f['family']==fam and (level=='conformer' or f['level']=='molecule') and scales[f['field_key']] is None];definitions[fam]=[names[i] for i in ix]
    if ix:
     values=a[:,ix]/np.array([scales[names[i]] for i in ix]);ok=np.isfinite(values).all(1);T[ok,fi]=np.max(values[ok],axis=1)
   groups=collections.defaultdict(list)
   for i,u in enumerate(units[level]):groups[u].append(i)
   means=[]
   for ix in groups.values():
    v=T[ix];n=np.isfinite(v).sum(0);means.append(np.divide(np.nansum(v,axis=0),n,out=np.full(len(fams),np.nan),where=n>0))
   means=np.array(means).reshape((-1,len(fams)));corr=[]
   for i,f in enumerate(fams):
    for k,g in enumerate(fams):
     ok=np.isfinite(means[:,i])&np.isfinite(means[:,k]);x,y=means[ok,i],means[ok,k];v=float(np.corrcoef(x,y)[0,1]) if len(x)>=3 and np.std(x)>0 and np.std(y)>0 else None;corr.append(dict(family_a=f,family_b=g,independent_units=int(ok.sum()),conditional_distance_correlation=v))
   j['roles'][role][level].update(families=fams,field_sets=definitions,unscaled_fields=unscaled,common_all_family_pairs=int(np.isfinite(T).all(1).sum()),conditional_correlations=corr)
 c['verified_common_vector_scales']=verified;j['vector_packing_review']='Actual P preparation reassembles vector components and enforces a shared zero-centered scale; known positive scales reused. Charged-origin-uncertain vectors remain incomparable.'
 save(B/'results/p_data_information/conditional_information.json',c);save(B/'results/p_data_information/family_complementarity.json',j)
 print('VECTOR_AFFINE_SUMMARIES_REFRESHED',flush=True)
if __name__=='__main__':main()
