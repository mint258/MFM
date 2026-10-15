import json,statistics
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
data=json.loads((root/'reports/wp4_capability_numeric_review_v2.json').read_text())
rows={(r['molecule'],r['task']):r for r in data['rows']}
polar=[r['values']['static_polar_block']['max_antisymmetric_component_bohr3'] for r in data['rows'] if r['task']=='pm7_B_static_POLAR_LET']
mul=[r['values']['mulliken_reconstruction_charge_max_error_e'] for r in data['rows'] if r['task']=='pm7_B_large' and r['values'].get('mulliken_reconstruction_charge_max_error_e') is not None]
deltas=[abs(r['values']['heat_of_formation_kcal_mol']-rows[(r['molecule'],'pm7_B_large')]['values']['heat_of_formation_kcal_mol']) for r in data['rows'] if r['task']=='pm7_B_static_POLAR_LET']
report={'synthetic_cases':16,'numerical_rows':448,
 'static_polar_antisymmetry_bohr3':{'min':min(polar),'median':statistics.median(polar),'max':max(polar),'above_0_01':sum(x>.01 for x in polar)},
 'mulliken_reconstruction_charge_max_error_e':max(mul) if mul else None,
 'B_with_static_POLAR_vs_B_large_max_HOF_difference_kcal_mol':max(deltas),
 'notes':'Read-only summaries of completed numeric review; no new molecular calculation.'}
(root/'reports/wp4_capability_decision_numbers.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
