"""Register unique FT sources and bind reused P scratch metadata, no fits."""
import hashlib
import json
import os
import socket
from pathlib import Path
from storage_20261122 import CONTROL as C, REPO as R, ROOT, write

read = lambda p: json.loads(Path(p).read_text())
if socket.gethostname().split('.')[0] not in {'compute-0-'+str(i) for i in range(8,20)} or os.environ.get('CUDA_VISIBLE_DEVICES'):
    raise ValueError('Run this metadata compiler on an admitted CPU8..19 node')
P = ROOT/'MFM_p_recipe'
tasks = ('qm9.U0_atom','qm9.homo','exp.LogD','exp.LogS')
plan_path = C/'finetune_plan_20261124.json'
if plan_path.exists():
    raise ValueError('Extension plan producer already closed; no duplicate matrix')
panels = [read(repo/'configs/dev_panel_v3.json')['tasks'] for repo in (P,R)]
for task in tasks:
    if next(row for row in panels[0] if row['task_id']==task) != next(row for row in panels[1] if row['task_id']==task):
        raise ValueError('Original P/S development task protocols differ')
scratch = {}
summaries = []
for task in tasks:
    scratch[task] = []
    for seed in (0,1,2):
        key = task.replace('.','_')
        ref = P/'configs/p_recipe/fixed_20261115/analysis_20261122/F1'/('F1_scratch_random_0M_'+key+'_s'+str(seed)+'.json')
        c = read(ref)
        summary_path = Path(c['output'])/'summary.json'
        summary = read(summary_path)
        if (c['mode'] != 'scratch' or c['task'] != task or c['seed'] != seed
                or c['authority'] != 'docs/p_recipe/USER_DIRECTIVE_20261122B.md'
                or c['internal_split_seed'] != 20261112 or summary.get('status') != 'COMPLETE'
                or c['store'] != read(R/'configs/s_recipe/screening/S-R1.json')['evaluation_store']):
            raise ValueError('Existing same-protocol scratch control is unavailable')
        scratch[task].append(str(Path(c['output'])/'prediction.pt'))
        summaries.append(str(summary_path))
points = []
for arm in ('B0','G1','N1','N2','R1','R2'):
    points.append(dict(point='S_'+arm+'_3M',run='S_'+arm+'_s0_3M',samples=3000000,
        source_training_budget=3000000, configuration=str(R/'configs/s_recipe/screening'/('S-'+arm+'.json'))))
for arm in ('B0','final'):
    points.append(dict(point='S_'+arm+'_9M',run='S_'+arm+'_s0_9M',samples=9000000,
        source_training_budget=9000000, configuration=str(R/'configs/s_recipe/confirmation'/('S-'+arm+'.json'))))
for k in (1,2,5):
    points.append(dict(point='S_E1_k'+str(k)+'_3M',run='S_E1_k'+str(k)+'_s0_3M',samples=3000000,
        source_training_budget=3000000, configuration=str(R/'configs/s_recipe/extensions_20261124'/('k'+str(k)+'_training.json'))))
for count in (1000000,3000000,6000000):
    points.append(dict(point='S_final_9Mtrajectory_'+str(count//1000000)+'M',run='S_final_s0_9M',
        samples=count, source_training_budget=9000000,
        configuration=str(R/'configs/s_recipe/confirmation/S-final.json')))
for arm in ('T5','T6'):
    points.append(dict(point='S_subset_'+arm+'_9M',run='S_subset_'+arm+'_s0_9M',samples=9000000,
        source_training_budget=9000000,configuration=str(R/'configs/s_recipe/extensions_20261124'/(arm+'_training.json'))))
for row in points:
    row['checkpoint'] = str(C/'training'/row['run']/('samples_'+str(row['samples'])+'.pt'))
cells = [dict(point=p['point'],task=t,seed=s,
    run='S_FT_'+p['point']+'_'+t.replace('.','_')+'_s'+str(s),source=p)
    for p in points for t in tasks for s in (0,1,2)]
original3M={'S_'+arm+'_3M' for arm in ('B0','G1','N1','N2','R1','R2')}
# Stable within each group: first B0/G1 and other completed3M fits; an eligible
# E1 fit precedes the supplementary9M trajectory/molecule-count work.
cells.sort(key=lambda row:0 if row['point'] in original3M else
           1 if row['point'].startswith('S_E1_') else 2)
providers = {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in
    (P/'tools/p_recipe/finetune_entry.py', P/'tools/p_recipe/finetune.py',
     P/'tools/p_recipe/finetune_statistics_entry.py', P/'tools/p_recipe/finetune_statistics.py')}
reference=read(P/'configs/p_recipe/E1_20261124/k10_F_primary_seed0.json')['reference']
plan = dict(schema='S_FULLFT_MATRIX_20261124_V1', points=points,cells=cells,reference=reference,
    distinct_points=len(points), fits=len(cells), scratch=scratch, scratch_complete_summaries=summaries,
    providers_sha256=providers, k10_reuses='S_R1_3M', priority_first=['S_B0_3M','S_G1_3M'],
    retention='After COMPLETE and actual owned exit, CPU seals selected best encoder/head/normalization and predictions; only then retires unused completed optimizer continuation state. Active/partial state retained.',
    new_scratch_fits=0, original_outputs_changed=False)
write(R/'configs/s_recipe/full_finetune_matrix_20261124.json', plan)
registration_path=R/'configs/s_recipe/extensions_20261124.json'
registration=read(registration_path)
validation=read(C/'extension_logic_check_20261124.json')
closed=read(C/('cpu_stage_'+str(validation['job_id'])+'.json'))
if validation['status']!='COMPLETE' or closed['exit_code']!=0 or not closed['owned_descendants_exited']:
    raise ValueError('New logic check requires actual completed owned exit')
registration.update(status='REGISTERED_IMPLEMENTATION_READY',
    validation=dict(job_id=validation['job_id'],new_tests=validation['new_tests'],
        source_receipt=str(C/'extension_logic_check_20261124.json')),
    prepared_matrix=str(R/'configs/s_recipe/full_finetune_matrix_20261124.json'),
    prepared_populations=str(C/'extension_populations_20261124/COMPLETE.json'))
write(registration_path,registration)
write(plan_path,plan)
print(json.dumps(dict(distinct_points=len(points),fits=len(cells),new_scratch_fits=0,
    reused_scratch_summaries=len(summaries),plan=str(plan_path))),flush=True)
