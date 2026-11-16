"""Joint distances and stratified missingness on the already frozen pairs."""
import collections,json,pathlib,pickle
import numpy as np
from stage0_cohort import R,O,load,save
from stage1_geometry import key
B=R/'MFM_p_data_information'
from stage3_information import statistics
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors
def main():
 fields=load(B/'configs/p_data_information/fields.json')['fields'];names=[f['field_key'] for f in fields];families=sorted({f['family'] for f in fields});panels=load(O/'panel.json');pairs=load(O/'pairs.json');out={};missing={};contrasts={}
 for f in fields:
  if f['level']!='molecule':continue
  anchors=[a for a in fields if a['field_key'].startswith('P.pm7_B.') and a['level']=='molecule' and a['method']==f['method'] and a['source_path']==f['source_path'] and a['unit']==f['unit']]
  if len(anchors)==1 and anchors[0]['field_key']!=f['field_key']:contrasts[f['field_key']]=anchors[0]['field_key']
 for role,rows in panels.items():
  z=dict(np.load(O/('distances_'+role+'.npz')));norms=load(O/('normalizations_'+role+'.json'));units=load(O/('unit_ids_'+role+'.json'));byid={r['molecule_id']:r for r in rows};roleout={}
  for level in ['composition','isomer','conformer']:
   families=sorted({f['family'] for i,f in enumerate(fields) if (level=='conformer' or f['level']=='molecule') and np.asarray(norms[names[i]]['scale']).size==1})
   distances=z[level];family_values=np.full((len(distances),len(families)),np.nan);definitions={}
   for j,family in enumerate(families):
    indices=[i for i,f in enumerate(fields) if f['family']==family and (level=='conformer' or f['level']=='molecule') and np.asarray(norms[names[i]]['scale']).size==1];definitions[family]=[names[i] for i in indices]
    if not indices:continue
    a=distances[:,indices]/np.array([float(np.asarray(norms[names[i]]['scale']).reshape(-1)[0]) for i in indices]);valid=np.isfinite(a).all(1);family_values[valid,j]=np.max(a[valid],axis=1)
   # Conditional correlations use equal-weight means over fixed independent units.
   groupindices=collections.defaultdict(list)
   for i,g in enumerate(units[level]):groupindices[g].append(i)
   grouped=[]
   for ix in groupindices.values():
    a=family_values[ix];n=np.isfinite(a).sum(0);grouped.append(np.divide(np.nansum(a,axis=0),n,out=np.full(len(families),np.nan),where=n>0))
   grouped=np.asarray(grouped).reshape((-1,len(families)));corr=[]
   for i,f in enumerate(families):
    for j,g in enumerate(families):
     ok=np.isfinite(grouped[:,i])&np.isfinite(grouped[:,j]);a,b=grouped[ok,i],grouped[ok,j]
     value=float(np.corrcoef(a,b)[0,1]) if len(a)>=3 and np.std(a)>0 and np.std(b)>0 else None
     corr.append(dict(family_a=f,family_b=g,independent_units=int(ok.sum()),conditional_distance_correlation=value))
   complete=np.isfinite(family_values).all(1);zero=np.isfinite(distances).any(1)&np.where(np.isfinite(distances),distances==0,True).all(1)
   cases=sorted(np.flatnonzero(zero).tolist(),key=lambda i:key(role,'collision',[level,pairs[role][level][i]]))[:2]
   roleout[level]=dict(candidate_pairs=len(distances),families=families,field_sets=definitions,common_all_family_pairs=int(complete.sum()),conditional_correlations=corr,calibrated_joint_detection_rate=None,unique_family_detection_rate=None,D_f=None,Holm=dict(alpha=.05,unknown_p_placeholder=1,reason='No field has applicable deterministic calculation-difference bound or matched empirical null; unknown is not zero'),uncalibrated_exact_FP32_collision_count=int(zero.sum()),collision_case_ids=[dict(pair=pairs[role][level][i],compared_fields=int(np.isfinite(distances[i]).sum()),reason='Coverage/precision unresolved; exact stored equality is not proof of physical invariance') for i in cases],collision_reason='Exact stored equality only; not proof of physical indistinguishability')
  counts=z['record_valid_counts'];strata={};molecule_pair_counts=np.zeros((len(rows),len(fields)),dtype=int);candidate_pair_counts=np.zeros(len(rows),dtype=int);rowindex={r['molecule_id']:i for i,r in enumerate(rows)}
  for i,pair in enumerate(pairs[role]['conformer']):
   ri=rowindex[pair['molecule_id']];candidate_pair_counts[ri]+=1;molecule_pair_counts[ri]+=np.isfinite(z['conformer'][i])
  # Inspect existing cached masks; no source reread and no numeric value comparison.
  common_mask_counts=np.zeros_like(molecule_pair_counts);pair_groups=collections.defaultdict(list)
  for pair in pairs[role]['conformer']:pair_groups[pair['molecule_id']].append(pair)
  state_within=[]
  for ri,row in enumerate(rows):
   with (O/'samples'/role/(str(row['pilot_index'])+'.pkl')).open('rb') as stream:samples=pickle.load(stream)
   for pair in pair_groups[row['molecule_id']]:
    state_row={}
    for state,anchor in contrasts.items():
     ta=samples[pair['a']]['targets'];tb=samples[pair['b']]['targets']
     if any(n not in ts or ts[n].raw.size!=1 or not np.isfinite(ts[n].raw).all() for ts in [ta,tb] for n in [state,anchor]):continue
     state_row[state]=float((ta[state].raw.astype(float)-ta[anchor].raw.astype(float)-tb[state].raw.astype(float)+tb[anchor].raw.astype(float)).flat[0])
    state_within.append(state_row)
    for j,name in enumerate(names):
     a,b=samples[pair['a']]['targets'].get(name),samples[pair['b']]['targets'].get(name)
     if a is None or b is None:continue
     if a.pair_index is not None:
      ia={tuple(p):i for i,p in enumerate(a.pair_index.tolist())};ib={tuple(p):i for i,p in enumerate(b.pair_index.tolist())}
      valid=any(np.any(a.valid[ia[p]]&b.valid[ib[p]]) for p in ia.keys()&ib.keys())
     else:valid=a.valid.shape==b.valid.shape and np.any(a.valid&b.valid)
     common_mask_counts[ri,j]+=int(valid)
  for flag in ['core','enriched']:
   for dim in ['source','heavy_atoms','rotatable_bonds','coverage']:
    grouped=collections.defaultdict(list)
    rotor={r['molecule_id']:int(rdMolDescriptors.CalcNumRotatableBonds(Chem.MolFromSmiles(r['graph']),rdMolDescriptors.NumRotatableBondsOptions.Strict)) for r in rows}
    for i,r in enumerate(rows):
     if not r[flag]:continue
     if dim=='source':v=r['source_family']
     elif dim=='heavy_atoms':v='<=20' if r['heavy_atoms']<=20 else ('21-35' if r['heavy_atoms']<=35 else '>35')
     elif dim=='coverage':v='single_representative' if r['representative_count_05A']<=1 else 'multiple_representatives'
     else:
      n=rotor.get(r['molecule_id']);v='unknown' if n is None else ('0' if n==0 else '1-3' if n<=3 else '>=4')
     grouped[str(v)].append(i)
    for v,ix in grouped.items():
     a=counts[ix].sum(0);strata[flag+'|'+dim+'|'+v]=dict(molecules=len(ix),fields={n:dict(valid_records=int(a[j,0]),candidate_records=int(a[j,1]),candidate_conformer_pairs=int(candidate_pair_counts[ix].sum()),common_mask_valid_pairs=int(common_mask_counts[ix,j].sum()),comparable_conformer_pairs=int(molecule_pair_counts[ix,j].sum()),molecules_with_comparable_pairs=int(np.count_nonzero(molecule_pair_counts[ix,j])),comparable_pairs_per_molecule_histogram={str(k):int(v) for k,v in collections.Counter(molecule_pair_counts[ix,j].tolist()).items()}) for j,n in enumerate(names)})
    graph=load(O/('graph_summaries_'+role+'.json'));state_summary={}
  for level in ['composition','isomer','conformer']:
   matrix=[];unit_ids=[]
   if level=='conformer':matrix=state_within;unit_ids=[p['molecule_id'] for p in pairs[role][level]]
   else:
    mode='median' if level=='isomer' else 'first'
    for ix,pair in enumerate(pairs[role][level]):
     state_row={}
     for state,anchor in contrasts.items():
      try:v=[graph[pair[end]][n][mode] for end in ['a','b'] for n in [state,anchor]]
      except KeyError:continue
      if all(x is not None for x in v):state_row[state]=v[0]-v[1]-v[2]+v[3]
     matrix.append(state_row);unit_ids.append(pair['formula_charge'] if level=='isomer' else str(ix))
   state_summary[level]={state:dict(neutral_anchor=anchor,structural_state_contrast=statistics([abs(m.get(state,np.nan)) for m in matrix],unit_ids)) for state,anchor in contrasts.items()}
  roleout['state_contrasts']=state_summary;roleout['shared_neutral_anchor_warning']='State contrasts sharing an anchor are algebraically coupled; absolute five-state correlation is not used as evidence of conditional equivalence.'
  missing[role]=dict(strata=strata,task_states={f['field_key']:dict(task_charge=f['actual_task_charge'],environment=f['environment'],geometry=f['geometry_route']) for f in fields});out[role]=roleout
 save(B/'results/p_data_information/family_complementarity.json',dict(roles=out,calibration='UNRESOLVED',algebraic_relations=[dict(field=f['field_key'],derived_from=f['derived_from'],dedup_of=f['dedup_of']) for f in fields if f.get('derived_from') or f.get('dedup_of')],interpretation='Distance correlation is descriptive; no detection or no-information claim'))
 base=load(B/'results/p_data_information/missingness.json');base['stratified']=missing;save(B/'results/p_data_information/missingness.json',base)
 print('JOINT_AND_MISSINGNESS_DONE',flush=True)
if __name__=='__main__':main()
