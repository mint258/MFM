"""Describe only the published A1 fields and their existing affine amplitudes."""
import numpy as np
from stage0_cohort import R,O,load,save
B=R/'MFM_p_data_information';OUT=B/'results/p_data_information'
def main():
 specs=load(B/'configs/p_recipe/label_parameters/PM7_A1.json')['normalizations'];source=load(OUT/'source_scalar_authority.json');norm=load(O/'normalizations_TRAIN.json');fields={f['field_key']:f for f in load(B/'configs/p_data_information/fields.json')['fields']};rows=[]
 for n,spec in sorted(specs.items()):
  m=source['roles']['TRAIN']['conformer_core'][n]['median'];d4scale=float(np.asarray(norm[n]['scale']).flat[0]);a1scale=float(np.asarray(spec['scale']).flat[0]);cross0=source['D4_offline_graph_scalars']['TRAIN']['composition'][n]['median'];cross1=source['A1_offline_graph_scalars']['TRAIN']['composition'][n]['median'];row=dict(field=n,unit=fields[n]['unit'],source_path=fields[n]['source_path'],D4_cross_composition=cross0,D4_within=m/d4scale if m is not None else None,A1_cross_composition=cross1,A1_within=m/a1scale if m is not None else None,within_amplitude_factor=d4scale/a1scale,element_reference_adds_conditional_numeric_information=False);rows.append(row)
 save(OUT/'A1_scope_and_amplitudes.json',dict(actual_changed_fields=sorted(specs),count=len(specs),rows=rows,energy_fields_changed=[n for n in specs if any(k in fields[n]['source_path'] for k in ['energy','heat_of_formation','repulsion'])],normalizations_refitted=False,interpretation='Existing offline transforms only; same-composition element references cancel. A1 changes relative amplitude, not the already stored input numbers or source numerical information.'))
 print(rows,flush=True)
if __name__=='__main__':main()