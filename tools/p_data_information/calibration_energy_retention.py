"""Read the already completed 2B outputs for two enabled PM7 energy targets.
No extra QM calls; the four molecules/pairs remain unchanged.
"""
import pickle,pathlib,sys
import numpy as np
from stage0_cohort import R,O,load,save
B=R/'MFM_p_data_information';sys.path.insert(0,str(R/'runs/phase1_wp5_20261011/scripts'));import wp5_parser_v2 as parser

def main():
 with (O/'source_graph_scalars.pkl').open('rb') as stream:source=pickle.load(stream)['TRAIN']
 calls=load(O/'calibration_2B_actual_calls.json')['cases'];lineage=load(O/'calibration_2B_lineage.json')['cases'];meta={(p['molecule_id'],p['native_record_id']):p for p in lineage if p['task']=='pm7_B'};tight={}
 for p in calls:
  key=(p['molecule_id'],p['native_record_id']);values=parser.parse_mopac(pathlib.Path(p['directory']),meta[key]['symbols']);tight[key]=dict(HOF=values.get('heat_of_formation_kcal_mol'),total_energy=values.get('total_energy_eV'))
 selected=load(B/'results/p_data_information/resolution.json')['calibration_2B']['candidates'];rows=[];ret=load(B/'results/p_data_information/retention.json')
 for p in selected:
  mid=p['molecule_id'];a,b=p['native_record_id_a'],p['native_record_id_b'];row=dict(molecule_id=mid,heavy_rmsd=p['heavy_rmsd'],fields={})
  for n,k,unit in [('P.pm7_B.r60.value','HOF','kcal/mol'),('P.pm7_B.r83.value','total_energy','eV')]:
   x,y=source[mid][a].get(n),source[mid][b].get(n);u,v=tight[(mid,a)].get(k),tight[(mid,b)].get(k)
   if any(t is None for t in [x,y,u,v]):row['fields'][n]=dict(status='UNRESOLVED_OUTPUT');continue
   z=float(np.float32(x))-float(np.float32(y));row['fields'][n]=dict(unit=unit,original_F64_absolute_difference=abs(x-y),tight_SCF_absolute_difference=abs(u-v),absolute_change_in_signed_difference=abs((x-y)-(u-v)),single_F32_cast_absolute_difference=abs(z),original_difference_erased_at_F32=bool(x!=y and z==0),largest_endpoint_setting_shift=max(abs(x-u),abs(y-v)),current_pilot_to_D6_distance_error_max=ret['roles']['TRAIN']['fields'][n]['pilot_to_D6_absolute_distance_error_max'],global_error_bound=None)
  rows.append(row)
 save(B/'results/p_data_information/calibration_energy_retention.json',dict(cases=rows,actual_additional_QM_calls=0,existing_new_QM_calls=8,scope='Same frozen 2B pairs; setting stability and numerical storage evidence only, not a full method-accuracy validation',interpretation='Equal stored raw energy and equal composition cannot acquire a nonzero difference through a deterministic D4/A1 affine; other enabled targets may retain the same contrast'))
 print(rows,flush=True)
if __name__=='__main__':main()