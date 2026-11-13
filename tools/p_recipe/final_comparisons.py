"""Final registered comparisons from completed readouts; never retrain a probe."""
import argparse,json
from pathlib import Path
import numpy as np
import torch
from decide_round import compare,write_deltas
from phychem_mfm.phase1.p_recipe import paired_decision
from phychem_mfm.phase1.v3_dev_evaluation import compare_panel
from phychem_mfm.phase1.v3_dev_evaluation_v2 import _unpack
R=Path('/share/home/zixiao/descriptor_analysis');REPO=Path(__file__).resolve().parents[2]
REFERENCE=Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/reference_C1_0/predictions.json')


def read(path):return json.loads(Path(path).read_text())

def summaries(c):return read(Path(c['output'])/'readout/scores.json')


def report_task_values(c,readout):
 """Retain frozen seven-task means; bootstrap excluded report-only tasks separately."""
 result=summaries(c)[readout];tasks=dict(result['tasks']);values=dict(result['paired_bootstrap']['task_values'])
 manifest=read(Path(c['output'])/'readout/predictions.json');reference=read(REFERENCE)
 missing=[key for key in manifest['files'] if key.endswith('/'+readout) and key.rsplit('/',1)[0] not in tasks]
 if missing:
  actual={key.rsplit('/',1)[0]:_unpack(torch.load(manifest['files'][key],map_location='cpu',weights_only=True)['prediction']) for key in missing}
  random={key.rsplit('/',1)[0]:_unpack(torch.load(reference['files'][key],map_location='cpu',weights_only=True)['prediction']) for key in missing}
  extra=compare_panel(actual,random,architecture_sha256='C1-0-reference',reference_architecture_sha256='C1-0-reference',retain_paired_samples=True,retain_task_samples=True)
  tasks.update(extra['tasks']);values.update(extra['paired_bootstrap']['task_values'])
 return tasks,values


def task_rows(a,b):
 rows=[]
 for readout in ('R3','R1'):
  ta,ba=report_task_values(a,readout);tb,bb=report_task_values(b,readout)
  for task in sorted(ta):
   av,bv=ta[task]['normalized_improvement'],tb[task]['normalized_improvement']
   pairs=[(x,y) for x,y in zip(ba[task],bb[task]) if x is not None and y is not None]
   if av is not None and bv is not None and pairs:
    x,y=np.asarray(pairs,dtype=np.float64).T;decision=paired_decision(av,bv,x,y)
   else:decision=dict(delta=None,ci_lower=None,ci_upper=None,verdict='undefined')
   rows.append(dict(purpose='P_vs_Pprime',round=0,readout=readout,task=task,A=a['run'],B=b['run'],**decision))
 return rows



def budget_sign_comparison(plan,configs):
 components=plan.get('M2_components')
 if components is None:return dict(status='M2 was not formed before the registered screening stop')
 candidates=[]
 for path in (REPO/'configs/p_recipe').glob('round*/*.json'):
  item=read(path)
  if item.get('stage')==2 and item.get('components')==components and (Path(item['output'])/'readout/scores.json').is_file():candidates.append(item)
 full=next((configs[arm] for arm in ('T2','T3','T1') if configs[arm]['components']==components),None)
 if not candidates or full is None:return dict(status='M2 lacks a separately measured matched configuration at one budget; no extra run',components=components)
 small=max(candidates,key=lambda item:item['round']);baseline=read(REPO/'configs/p_recipe/round1/B0.json')
 d1=summaries(small)['R3']['mean_normalized_improvement']-summaries(baseline)['R3']['mean_normalized_improvement']
 d2=summaries(full)['R3']['mean_normalized_improvement']-summaries(configs['T1'])['R3']['mean_normalized_improvement']
 return dict(status='MEASURED',definition='R3 score(M2)-score(B0)',M2_1p5M_run=small['run'],M2_4p5M_run=full['run'],after_registered_rollback=plan.get('M2_after_rollback',False),delta_1p5M=d1,delta_4p5M=d2,same_sign=bool(np.sign(d1)==np.sign(d2)))

def close(plan):
 configs={read(path)['arm']:read(path) for path in plan['configurations']}
 rows=[]
 for a,b,purpose in [('T2','T1','confirmation'),('T3','T1','confirmation'),('T2','T3','final_recipe'),
  (plan['Pprime_comparator'],'T4','P_vs_Pprime'),('T2','T6','molecule_scaling'),('T6','T5','molecule_scaling')]:
  rows.extend(compare(configs[a],configs[b],purpose,0))
 rows.extend(task_rows(configs[plan['Pprime_comparator']],configs['T4']));write_deltas(rows)
 decision=next(row for row in rows if row['purpose']=='final_recipe' and row['readout']=='R3')
 if decision['verdict']=='win':chosen='T2'
 elif decision['verdict']=='loss':chosen='T3'
 else:chosen=min(('T2','T3'),key=lambda arm:len(configs[arm]['components']))
 target=REPO/'configs/p_recipe/final_recipe.json';c=dict(configs[chosen]);c.pop('resume',None)
 c.update(run='P_final_recipe_reproduction',output=str(Path(c['output']).parent/'P_final_recipe_reproduction'))
 parameter_paths={Path(item['label_parameters']) for item in configs.values() if item.get('label_parameters')}
 for path in (REPO/'configs/p_recipe').glob('round*/*.json'):
  item=read(path)
  if item.get('label_parameters') and (Path(item['output'])/'readout/scores.json').is_file():parameter_paths.add(Path(item['label_parameters']))
 exported=REPO/'configs/p_recipe/label_parameters';exported.mkdir(parents=True,exist_ok=True)
 for path in sorted(parameter_paths):(exported/path.name).write_text(path.read_text())
 if c.get('label_parameters'):c['label_parameters']='configs/p_recipe/label_parameters/'+Path(c['label_parameters']).name
 target.write_text(json.dumps(c,indent=2)+'\n')
 cohort=read(configs['T2']['corpus']);full_count=cohort['train_molecules']
 verdict=dict(final_run=configs[chosen]['run'],final_arm=chosen,final_components=configs[chosen]['components'],
  runnable_configuration=str(target),T2_T3=decision,Pprime_comparator=plan['Pprime_comparator'],
  Pprime_and_scaling_recipe='T2/M3',repeat_on_T3='Pending user decision; no rerun' if chosen=='T3' else 'Not needed',
  neither_candidate_beats_T1=not any(row['purpose']=='confirmation' and row['readout']=='R3' and row['verdict']=='win' for row in rows),
  comparisons=rows,B0_M2_budget_sign=budget_sign_comparison(plan,configs),training_samples=4500000,batch_size=c['batch_size'],
  batch_size_by_arm={arm:item['batch_size'] for arm,item in configs.items()},full_TRAIN_molecules=full_count,
  molecule_repeats={'250000':18.,'500000':9.,str(full_count):4500000/full_count},
  molecule_repeat_note='Fixed sample budget increases repetition when molecule count decreases; descriptive only, no expansion decision.')
 return verdict

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 result=close(read(a.plan));Path(a.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
