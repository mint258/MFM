"""Prespecified near/distinct and first-conformer supplements, from caches only."""
import collections,pickle
import numpy as np
from stage0_cohort import R,O,load,save,guard
from stage3_information import statistics
B=R/'MFM_p_data_information'
def main():
 guard();panels=load(O/'panel.json');pairs=load(O/'pairs.json');fields=load(B/'configs/p_data_information/fields.json')['fields'];names=[f['field_key'] for f in fields];source_names=load(B/'results/p_data_information/source_scalar_authority.json')['fields'];source_graph=load(O/'source_graph_summaries.json');ids=load(O/'pilot_physical_ids.json')
 with (O/'source_graph_scalars.pkl').open('rb') as stream:source_values=pickle.load(stream)
 result={};first={};single={}
 for role,rows in panels.items():
  bymid={r['molecule_id']:r for r in rows};old=np.load(O/('distances_'+role+'.npz'))['conformer'];units=[p['molecule_id'] for p in pairs[role]['conformer']];raw=np.full((len(units),len(source_names)),np.nan)
  for i,p in enumerate(pairs[role]['conformer']):
   mid=p['molecule_id'];a=source_values[role][mid][ids[role][mid][str(p['a'])]];b=source_values[role][mid][ids[role][mid][str(p['b'])]]
   for j,n in enumerate(source_names):
    if a.get(n) is not None and b.get(n) is not None and np.isfinite(old[i,names.index(n)]):raw[i,j]=abs(a[n]-b[n])
  roleout={}
  for flag in ['core','enriched']:
   for geo in ['near_duplicate','distinct']:
    ix=[i for i,p in enumerate(pairs[role]['conformer']) if bymid[p['molecule_id']][flag] and (p['heavy_rmsd']<.5 if geo=='near_duplicate' else p['heavy_rmsd']>=.5)];groups=[units[i] for i in ix];fs={}
    for j,n in enumerate(names):
     v=old[ix,j];s=statistics(v,groups);s.update(candidate_pairs=len(ix),comparable_pairs=int(np.isfinite(v).sum()),nonzero_stored_pairs=int(np.count_nonzero(v[np.isfinite(v)])),layer='Pilot FP32; original graph scalar evidence separately supplied');fs[n]=s
    ss={}
    for j,n in enumerate(source_names):
     v=raw[ix,j];o=old[ix,names.index(n)];nonzero=np.isfinite(v)&np.isfinite(o)&(v>0);erased=nonzero&(o==0);rates=collections.defaultdict(lambda:[0,0])
     for k,mid in enumerate(groups):
      if nonzero[k]:rates[mid][0]+=int(erased[k]);rates[mid][1]+=1
     rv=[a/b for a,b in rates.values() if b];s=statistics(v,groups);s.update(candidate_pairs=len(ix),comparable_pairs=int(np.isfinite(v).sum()),original_nonzero_numeric_pairs=int(nonzero.sum()),original_to_pilot_zero_pairs=int(erased.sum()),equal_molecule_mean_erasure_rate=float(np.mean(rv)) if rv else None,erasure_independent_molecules=len(rv),erased_original_difference=statistics([v[k] for k in np.flatnonzero(erased)],[groups[k] for k in np.flatnonzero(erased)]),maximum_erased_original_difference=float(v[erased].max()) if erased.any() else None,layer='Original registry-cell F64, common existing masks; no global calculation error bound');ss[n]=s
    roleout[flag+'|'+geo]=dict(pilot_all_fields=fs,original_graph_scalars=ss)
  result[role]=roleout;first[role]={};single[role]={}
  for n in source_names:
   vals=[];groups=[]
   for p in pairs[role]['isomer']:
    a,b=source_graph[role][p['a']][n]['first'],source_graph[role][p['b']][n]['first'];vals.append(abs(a-b) if a is not None and b is not None else np.nan);groups.append(p['formula_charge'])
   first[role][n]=dict(statistics(vals,groups),candidate_pairs=len(vals),comparable_pairs=int(np.isfinite(vals).sum()))
   single[role][n]={}
   for flag in ['core','enriched']:
    counts=collections.Counter()
    for row in rows:
     if not row[flag]:continue
     g=source_graph[role][row['molecule_id']][n];k=g['valid_conformers'];counts['molecules']+=1;counts['no_valid_conformer']+=int(k==0);counts['single_valid_conformer_explicitly_not_a_zero_variation_claim']+=int(k==1);counts['multiple_valid_conformers']+=int(k>=2);counts['multiple_valid_equal_stored_range']+=int(k>=2 and g['minimum']==g['maximum'])
    single[role][n][flag]=dict(counts)
 save(B/'results/p_data_information/comparison_supplements.json',dict(roles=result,original_isomer_first_conformer=first,explicit_single_conformer_counts=single,geometry_split='Prespecified pilot proper-heavy RMSD <0.5A versus >=0.5A; not a universal property threshold',bootstrap=dict(repetitions=1000,seed=20261025,independent_unit='molecule or formula-group'),additional_source_P_reads=0));print('COMPARISON_SUPPLEMENTS_DONE',flush=True)
if __name__=='__main__':main()