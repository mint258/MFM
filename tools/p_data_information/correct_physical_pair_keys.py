"""Correct the prespecified pair key using physical IDs, without new label reads."""
import collections,itertools,json,pathlib,pickle,shutil,time
import numpy as np
import pyarrow as pa
import pyarrow.dataset as pad
from stage0_cohort import R,O,P,load,save,guard
from stage1_geometry import key,rmsd,local_setup,local_difference
B=R/'MFM_p_data_information'
from physical_pair_identity import physical_pair,select_pairs

def main():
 guard();panels=load(O/'panel.json');oldpairs=load(O/'pairs.json');coverage=load(O/'coverage.json');archive=O/'exploratory_local_index_pair_key';archive.mkdir(exist_ok=False)
 # Preserve the completed exploratory outputs, never delete or relabel their history.
 for p in O.iterdir():
  if p.is_file() and (p.name in ['pairs.json','panel.json','coverage.json'] or p.name.startswith(('distances_','graph_summaries_','unit_ids_','normalizations_'))):shutil.copy2(p,archive/p.name)
 for source,name in [(B/'results/p_data_information','results'),(B/'docs/p_data_information','reports')]:shutil.copytree(source,archive/name)
 physical={};newpairs={};summary={};pa.set_cpu_count(2)
 for role,panel in panels.items():
  mids=[r['molecule_id'] for r in panel];allowed={(r['pilot_index'],ci) for r in panel for ci in r['allowed_conformers']};ids={};byaddr={}
  expression=(pad.field('record_kind')=='P')&pad.field('molecule_id').isin(mids)
  options=pad.ParquetFragmentScanOptions(pre_buffer=False)
  scan=pad.dataset(P/('v31_pilot_'+role)/'id_map.parquet',format='parquet').scanner(columns=['molecule_id','molecule_index','conformer_index','native_record_id','legacy_geometry_ids'],filter=expression,batch_size=128,use_threads=False,batch_readahead=0,fragment_readahead=0,fragment_scan_options=options)
  for batch in scan.to_batches():
   for row in batch.to_pylist():
    address=(int(row['molecule_index']),int(row['conformer_index']))
    if address not in allowed:continue
    rid=row['native_record_id']
    if not rid:
     bases=sorted(g for g in row['legacy_geometry_ids'] if g.startswith('pm7:'))
     if not bases:raise ValueError('No stable physical record ID for '+str(address))
     rid='geometry:'+bases[0]
    if address in byaddr:raise ValueError('Ambiguous pilot physical address')
    byaddr[address]=rid
  assert set(byaddr)==allowed
  out=[];roleids={};unresolved=[]
  for index,row in enumerate(panel):
   guard();mid=row['molecule_id'];mi=row['pilot_index'];mapping={ci:byaddr[(mi,ci)] for ci in row['allowed_conformers']};roleids[mid]={str(k):v for k,v in mapping.items()}
   assert len(set(mapping.values()))==len(mapping),'Duplicate native IDs need an explicit geometry identity, never a local-index tie break'
   chosen=select_pairs(role,mid,mapping)
   with (O/'samples'/role/(str(mi)+'.pkl')).open('rb') as stream:samples=pickle.load(stream)
   m={1:np.asarray(row['elements']),2:np.asarray(row['bonds']),3:np.asarray(row['bond_order'])};contacts,torsions=local_setup(m,role,mid);heavy=m[1]>1
   for a,b,identity in chosen:
    sa,sb=samples[a],samples[b];ga,gb=sa['pos'],sb['pos'];pert_a,pert_b=sa.get('pos_perturbed'),sb.get('pos_perturbed')
    pair=dict(molecule_id=mid,a=a,b=b,native_record_id_a=mapping[a],native_record_id_b=mapping[b],physical_pair_id=identity,heavy_rmsd=rmsd(ga,gb,heavy),all_atom_rmsd=rmsd(ga,gb,np.ones(len(heavy),dtype=bool)),exact_stored_geometry=bool(np.array_equal(ga,gb)),perturbed_heavy_rmsd=rmsd(pert_a,pert_b,heavy) if pert_a is not None and pert_b is not None else None,**local_difference(ga.astype(float),gb.astype(float),contacts,torsions));out.append(pair)
   if index%500==0:print(role,'PHYSICAL_PAIR_KEYS',index,len(panel),flush=True)
  newpairs[role]=dict(oldpairs[role],conformer=out);physical[role]=roleids;summary[role]=dict(molecules=len(panel),records=len(allowed),conformer_pairs=len(out),native_ids_unique_within_each_molecule=True)
  coverage['roles'][role]['conformer_pairs']=len(out)
 coverage.update(pair_key='Prespecified canonical native_record_id pair; local indices used only as frozen cache addresses',pair_key_correction='Earlier local-index-key outputs are exploratory only; archived without deletion',exploratory_archive=str(archive))
 save(O/'pilot_physical_ids.json',physical);save(O/'pairs.json',newpairs);save(O/'coverage.json',coverage);save(O/'pair_key_correction.json',dict(status='CORRECTED_TO_PRESPECIFIED_NATIVE_ID_RULE',roles=summary,archive=str(archive),new_molecules=0,new_raw_P_reads=0,new_QM_calls=0,label_values_used_for_pair_choice=False,exploratory_pairs=sum(len(r['conformer']) for r in oldpairs.values()),authoritative_pairs=sum(len(r['conformer']) for r in newpairs.values())))
 print('PHYSICAL_PAIR_KEYS_CORRECTED',json.dumps(summary),flush=True)
if __name__=='__main__':main()
