import json
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
data=json.loads((root/'reports/wp4_capability_numeric_review_v2.json').read_text())
print(json.dumps({'rows':len(data['rows']),'outcomes':data['outcomes'],'worker_pids':data['worker_pids']},indent=2))
for name in ['pm7_B_static_POLAR_LET','pm7_B_large']:
 row=next(x for x in data['rows'] if x['task']==name)
 print(json.dumps({'task':name,'numeric_keys':list(row['values']),
   'static_polar_block':row['values'].get('static_polar_block'),
   'mulliken_reconstruction_keys':[k for k in row['values'] if 'mulliken' in k]}))
