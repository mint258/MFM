"""Strict full-experiment extraction using the already tested directional rules.

This module cannot launch work. It requires four complete training summaries and
all twelve closed probe endpoints. Missing task targets remain unavailable.
"""
from __future__ import annotations
import math
from s_convergence_rules_v3 import S_RULES,task_comparison,probe_comparison,joint_judgment

N=11104772
MOLECULES=1206608
DATASETS=('qm7','qm9','cyp_isoform','az_exactsom','expansionrx')
CONDITIONS=tuple(kind+'_seed'+str(seed) for kind in ['B1','B3'] for seed in [0,1])
ENDPOINTS=tuple(['B1_seed'+str(s)+'_e1' for s in [0,1]]+
                ['B3_seed'+str(s)+'_e'+e for s in [0,1] for e in ['0p25','0p5','1','2','3']])
CELLS={(d,f) for d in DATASETS for f in (range(1) if d=='expansionrx' else range(10))}

def finite(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('Nonfinite or missing measured metric')
    return float(value)

def final_training(summary,condition):
    if condition not in CONDITIONS:raise ValueError('Unknown formal condition')
    epochs=1 if condition.startswith('B1_') else 3
    if (summary.get('condition')!=condition or summary.get('status')!='TRAINING_EXPOSURES_COMPLETE_AWAITING_H0_PROBES'
       or summary.get('epoch_accepted') is not True or summary.get('development_only') is not False
       or summary.get('scientific_stop') is not False or summary.get('consumed_records')!=epochs*N):
        raise ValueError('Incomplete, development or mismatched formal training')
    closed=summary['completed_epochs']
    if (len(closed)!=epochs or [x['epoch'] for x in closed]!=list(range(1,epochs+1))
       or any(x['records']!=N or x['molecules']!=MOLECULES for x in closed)):
        raise ValueError('Formal epoch population is incomplete')
    endpoints={}
    for epoch in range(1,epochs+1):
        rows=[x for x in summary['validation_history'] if x['consumed_records']==epoch*N]
        if len(rows)!=1:raise ValueError('Missing or ambiguous exact full-epoch evaluation')
        values=rows[0]['values']
        for role,records in [('full',127082),('routine',11322)]:
            x=values[role]
            if x['records']!=records or x['missing']!=0 or x['duplicates']!=0:
                raise ValueError('Validation record coverage differs')
        for key in S_RULES:finite(values['full'][key])
        endpoints[epoch]=values
    return {'condition':condition,'epochs':epochs,'consumed_records':epochs*N,
            'epoch_values':endpoints,'final_full':endpoints[epochs]['full']}

def aggregate_map(receipt,endpoint):
    if (receipt.get('endpoint')!=endpoint or receipt.get('status')!='ALL_FORTY_ONE_FROZEN_LINEAR_PROBE_CELLS_CLOSED'
       or receipt.get('primary_tasks')!=32 or receipt.get('all_reported_tasks')!=35
       or receipt.get('expansion_official_test_rows_used_for_training') is not False):
        raise ValueError('Probe receipt is incomplete or protocol differs')
    cells=receipt['cells']
    if len(cells)!=41 or {(c['dataset'],c['fold']) for c in cells}!=CELLS:
        raise ValueError('Missing, duplicate or altered original probe cells')
    if any(c.get('encoder_trained') is not False or c.get('test_targets_used_for_model_or_endpoint_selection') is not False for c in cells):
        raise ValueError('Probe fit violates frozen H0 or test target isolation')
    result={}
    for row in receipt['aggregate']:
        key=row['dataset']+'.'+row['task']
        if row['dataset'] not in DATASETS or key in result:raise ValueError('Invalid or duplicate probe task')
        if row['metric_name'] not in ['MAE','molecule_hit_at_1']:raise ValueError('Unknown metric direction')
        expected='molecule_hit_at_1' if row['dataset'] in ['cyp_isoform','az_exactsom','expansionrx'] else 'MAE'
        if row['metric_name']!=expected:raise ValueError('Changed probe metric')
        count=1 if row['dataset']=='expansionrx' else 10
        if len(row['fold_metrics'])!=count:raise ValueError('Changed scaffold aggregation')
        values=row['fold_metrics'];value=row['primary_metric']
        if any(v is None for v in values):
            if value is not None:raise ValueError('Missing fold hidden by a partial mean')
        else:
            observed=finite(value);expected=math.fsum(finite(v) for v in values)/count
            if abs(observed-expected)>1e-12*max(1.,abs(expected)):raise ValueError('Probe aggregate differs from fixed original fold mean')
        result[key]=row
    if len(result)!=35 or sum(bool(v['included_in_primary_judgment']) for v in result.values())!=32:
        raise ValueError('Expected exactly 35 tasks and 32 primary tasks')
    return result

def compare_full(training,probes):
    if set(training)!=set(CONDITIONS) or set(probes)!=set(ENDPOINTS):
        raise ValueError('Requires all four conditions and twelve probe endpoints')
    runs={k:final_training(v,k) for k,v in training.items()}
    tables={k:aggregate_map(v,k) for k,v in probes.items()}
    reference=tables['B1_seed0_e1']
    for table in tables.values():
        if set(table)!=set(reference):raise ValueError('Probe task family differs across endpoints')
        for key,row in table.items():
            if any(row[field]!=reference[key][field] for field in ['metric_name','included_in_primary_judgment']):
                raise ValueError('Probe direction or primary family changed across endpoints')
    s=[task_comparison(key,[runs['B1_seed'+str(seed)]['final_full'][key] for seed in [0,1]],
                           [runs['B3_seed'+str(seed)]['final_full'][key] for seed in [0,1]]) for key in S_RULES]
    p=[probe_comparison(key,[tables['B1_seed'+str(seed)+'_e1'][key]['primary_metric'] for seed in [0,1]],
                           [tables['B3_seed'+str(seed)+'_e3'][key]['primary_metric'] for seed in [0,1]],
                           higher_is_better=row['metric_name']=='molecule_hit_at_1',
                           primary=row['included_in_primary_judgment'],category=row['dataset']) for key,row in reference.items()]
    curves=[{'endpoint':point,'task_id':key,**row} for point,table in tables.items() for key,row in table.items()]
    judgment=joint_judgment(s,p)
    categories={dataset:sum(row['unconverged'] is True and row['primary'] and row['category']==dataset for row in p) for dataset in DATASETS}
    return {'status':'FOUR_COMPLETE_RUNS_AND_TWELVE_PROBES_EVALUATED','judgment':judgment,'S_comparisons':s,
            'probe_comparisons':p,'unconverged_primary_probe_categories':categories,'probe_endpoint_task_rows':curves,
            'closed_probe_cells':sum(len(v['cells']) for v in probes.values()),'closed_report_task_rows':len(curves),
            'total_base_training_exposures':sum(v['consumed_records'] for v in runs.values()),
            'required_epoch_count_extrapolated':False,'later_than_three_epochs_convergence_claimed':False}

def old_new_comparisons(new_probes,old_probes):
    expected={'B1_seed0_e1','B1_seed1_e1','B3_seed0_e3'}
    if not expected<=set(old_probes):raise ValueError('Original endpoint comparisons missing')
    new={p:aggregate_map(new_probes[p],p) for p in expected|{'B3_seed1_e3'}}
    old={p:aggregate_map(old_probes[p],p) for p in expected}
    rows=[]
    for kind in ['B1','B3']:
        old_ids=['B1_seed0_e1','B1_seed1_e1'] if kind=='B1' else ['B3_seed0_e3']
        new_ids=[kind+'_seed'+str(s)+('_e1' if kind=='B1' else '_e3') for s in [0,1]]
        keys=set(new[new_ids[0]])
        if any(set(old[p])!=keys for p in old_ids):raise ValueError('Old/new task family differs')
        for key in sorted(keys):
            exemplar=new[new_ids[0]][key]
            for p in old_ids:
                if any(old[p][key][f]!=exemplar[f] for f in ['metric_name','included_in_primary_judgment']):
                    raise ValueError('Old/new comparison changes metric or primary family')
            a=[old[p][key]['primary_metric'] for p in old_ids];b=[new[p][key]['primary_metric'] for p in new_ids]
            am=math.fsum(finite(v) for v in a)/len(a) if all(v is not None for v in a) else None
            bm=math.fsum(finite(v) for v in b)/len(b) if all(v is not None for v in b) else None
            higher=exemplar['metric_name']=='molecule_hit_at_1'
            delta=(bm-am if higher else am-bm) if am is not None and bm is not None else None
            rows.append({'kind':kind,'task_id':key,'metric_name':exemplar['metric_name'],'old_values':a,'new_values':b,
                         'old_seed_count':len(a),'new_seed_count':len(b),'old_mean':am,'new_mean':bm,
                         'new_improvement_original_units':delta,'old_seed_spread':abs(a[0]-a[1]) if len(a)==2 and am is not None else None,
                         'old_B3_has_only_seed0':kind=='B3','primary':exemplar['included_in_primary_judgment'],
                         'statistical_significance_claimed':False})
    return rows
