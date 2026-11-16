"""Stored native-base coordinate retention, independent of vector-frame rendering.
Exact byte/numeric equality only; no additional Kabsch/threshold comparisons.
"""
import collections,pickle
import numpy as np
from stage0_cohort import R,O,load,save,guard
B=R/'MFM_p_data_information'
def main():
 with (O/'source_selected_unique_permutations.pkl').open('rb') as stream:m=pickle.load(stream)
 with (O/'source_selected_native_geometries.pkl').open('rb') as stream:geometries=pickle.load(stream)
 panels=load(O/'panel.json');pairs=load(O/'pairs.json');ids=load(O/'pilot_physical_ids.json');result={}
 for role,rows in panels.items():
  totals=collections.Counter();bymid=collections.defaultdict(list);byflag={f:[] for f in ['core','enriched']}
  for p in pairs[role]['conformer']:bymid[p['molecule_id']].append(p)
  for row in rows:
   guard();mid=row['molecule_id'];mi=row['pilot_index']
   with (O/'samples'/role/(str(mi)+'.pkl')).open('rb') as stream:pilot=pickle.load(stream)
   native={};unit=collections.Counter()
   for ci in row['allowed_conformers']:
    rid=ids[role][mid][str(ci)];p=m['maps'][(mid,rid)];g=geometries[(mid,rid)];unit['candidate_records']+=1
    if p is None:continue
    Z=np.empty_like(g['Z']);Z[list(p)]=g['Z'];pos=np.empty_like(g['pos']);pos[list(p)]=g['pos']
    if not np.array_equal(Z,pilot[ci]['Z']):continue
    unit['mapped_native_records']+=1;exact=np.array_equal(pos.astype(np.float32),pilot[ci]['pos']);unit['native_single_F32_cast_reproduces_pilot_records']+=int(exact)
    if exact:native[ci]=pos
   for pair in bymid[mid]:
    a,b=pair['a'],pair['b'];unit['candidate_pairs']+=1
    if a not in native or b not in native:continue
    unit['common_source_pilot_pairs']+=1;different=not np.array_equal(native[a],native[b]);unit['native_stored_coordinate_different_pairs']+=int(different);unit['native_difference_collapsed_at_F32_pairs']+=int(different and np.array_equal(pilot[a]['pos'],pilot[b]['pos']))
   totals.update(unit)
   if unit['native_stored_coordinate_different_pairs']:
    rate=unit['native_difference_collapsed_at_F32_pairs']/unit['native_stored_coordinate_different_pairs']
    for flag in byflag:
     if row[flag]:byflag[flag].append(rate)
  result[role]=dict(counts=dict(totals),rates={f:dict(independent_molecules=len(v),equal_molecule_mean=float(np.mean(v)) if v else None,median=float(np.median(v)) if v else None) for f,v in byflag.items()})
 save(B/'results/p_data_information/native_coordinate_retention.json',dict(roles=result,source_layer='Original registered native base_geometry F64 container, unambiguous source-to-M mapping',scope='Stored coordinates only; binary inequality is not physical inequivalence. Does not claim that two actual QM input files differ.',vector_frame_integration='UNRESOLVED_AFTER_TWO_FAILED_RUNS, reported separately',additional_Kabsch_comparisons=0));print('NATIVE_COORDINATE_RETENTION_DONE')
if __name__=='__main__':main()