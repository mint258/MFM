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
CLOSEOUT='docs/p_recipe/USER_DIRECTIVE_20261118B.md'


def read(path):return json.loads(Path(path).read_text())

def summaries(c):return read(Path(c['output'])/'readout/scores.json')


def study_root(plan):
 path=Path(plan.get('base_configuration',REPO/'configs/p_recipe/base.json'))
 return (path if path.is_absolute() else REPO/path).parent


def completed_configurations(plan):
 """Final producers consume successful full-budget runs, including readouts."""
 configs={read(path)['arm']:read(path) for path in plan['configurations']}
 closeout=plan.get('selection_authority')==CLOSEOUT
 required={'T1','T2','T5','T6'} if closeout else {'T1','T2','T3','T5','T6'}
 if closeout and (not plan.get('recipe_frozen') or plan.get('T7_required')):
  raise ValueError('18B requires a frozen recipe and excludes T7')
 if 'T4' not in configs:
  if plan.get('T4_included') is not False or plan.get('T4_user_decision')!='OMIT' or not plan.get('T4_user_confirmation'):
   raise ValueError('Missing T4 requires the recorded explicit user omission')
 else:
  if plan.get('T4_included') is False:raise ValueError('T4 contradicts the recorded omission')
  required.add('T4')
 if plan.get('T7_required'):required.add('T7')
 if set(configs)!=required:raise ValueError('Confirmation arms differ from the registered plan')
 ledger=read(R/'runs/p_recipe_20261113/study_execution.json')
 for c in configs.values():
  if c.get('study_revision','original_20261113')!=plan.get('study_revision','original_20261113'):
   raise ValueError('Confirmation configurations belong to another study revision')
  expected=plan.get('samples_per_run',9000000)
  if c['samples']!=expected:raise ValueError('Confirmation sample budgets differ')
  record=ledger['runs'][c['run']];summary=read(Path(c['output'])/'summary.json')
  if record.get('state')!='COMPLETED' or record.get('exit_code') not in (0,'0:0'):
   raise ValueError('Refresh actual successful terminal accounting: '+c['run'])
  if summary.get('status')!='COMPLETE' or summary['samples']!=expected:
   raise ValueError('Full-budget training/readouts are incomplete: '+c['run'])
  scores=summaries(c)
  if not all(scores[r].get('complete') and scores[r]['bootstrap_samples']==1000 and scores[r]['bootstrap_defined']==1000 for r in ('R1','R3')):
   raise ValueError('Registered readouts are incomplete: '+c['run'])
 return configs


def comparison_layout(plan,configs):
 """Scaling remains descriptive under18B and never requests another seed."""
 deciding=[('T2','T1','confirmation')]
 scaling=[('T2','T6','molecule_scaling'),('T6','T5','molecule_scaling')]
 if plan.get('selection_authority')!=CLOSEOUT:
  deciding.extend([('T3','T1','confirmation'),('T2','T3','final_recipe')])
 if 'T4' in configs:deciding.append((plan['Pprime_comparator'],'T4','P_vs_Pprime'))
 return deciding,scaling


def final_recipe_choice(plan,configs,rows):
 if plan.get('selection_authority')==CLOSEOUT:return 'T2',None
 decision=next(row for row in rows if row['purpose']=='final_recipe' and row['readout']=='R3')
 if decision['verdict']=='win':return 'T2',decision
 if decision['verdict']=='loss':return 'T3',decision
 return min(('T2','T3'),key=lambda arm:len(configs[arm]['components'])),decision


def confirmation_seed_results(plan,configs,session):
 """Preflight every deciding pair before producing any final artifact."""
 deciding,descriptive=comparison_layout(plan,configs);results=[]
 for a,b,purpose in deciding:
  results.append(session.assess(configs[a],configs[b],purpose,0))
 for a,b,purpose in descriptive:
  results.append(session.assess(configs[a],configs[b],purpose,0,descriptive=True))
 state=session.save()
 if not all(result['ready'] for result in results):return state,None
 return state,[row for result in results for row in result['rows']]


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
 for path in study_root(plan).glob('round*/*.json'):
  item=read(path)
  if item.get('stage')==2 and item.get('study_revision','original_20261113')==plan.get('study_revision','original_20261113') and item.get('components')==components and (Path(item['output'])/'readout/scores.json').is_file():candidates.append(item)
 full=next((configs[arm] for arm in ('T2','T3','T1') if arm in configs and configs[arm]['components']==components),None)
 if not candidates or full is None:return dict(status='M2 lacks a separately measured matched configuration at one budget; no extra run',components=components)
 small=max(candidates,key=lambda item:item['round']);baseline=read(study_root(plan)/'round1/B0.json')
 d1=summaries(small)['R3']['mean_normalized_improvement']-summaries(baseline)['R3']['mean_normalized_improvement']
 d2=summaries(full)['R3']['mean_normalized_improvement']-summaries(configs['T1'])['R3']['mean_normalized_improvement']
 return dict(status='MEASURED',definition='R3 score(M2)-score(B0)',M2_screening_run=small['run'],screening_samples=small['samples'],M2_confirmation_run=full['run'],confirmation_samples=full['samples'],after_registered_rollback=plan.get('M2_after_rollback',False),delta_screening=d1,delta_confirmation=d2,same_sign=bool(np.sign(d1)==np.sign(d2)))

def close(plan,*,seed_session=None):
 if plan.get('selection_valid') is False:raise ValueError('The user invalidated this confirmation evidence')
 closeout=plan.get('selection_authority')==CLOSEOUT
 configs=completed_configurations(plan)
 seed_state=None;rows=[]
 if closeout:
  from seed_comparisons import SeedComparisons
  session=seed_session or SeedComparisons(Path(plan.get('control_directory',R/'runs/p_recipe_20261113/fixed_20261115'))/'conditional_seed_decisions/confirmation')
  seed_state,rows=confirmation_seed_results(plan,configs,session)
  if rows is None:
   return dict(status='WAITING_REGISTERED_INPUTS',conditional_seed_decisions_complete=False,
       seed_comparisons=seed_state,no_final_artifacts_created=True,no_jobs_submitted=True)
  plan['conditional_seed_decisions_complete']=True
  plan['seed_comparisons']=seed_state
 else:
  comparisons,descriptive=comparison_layout(plan,configs)
  for a,b,purpose in comparisons+descriptive:rows.extend(compare(configs[a],configs[b],purpose,0))
 if 'T4' in configs:
  reported=task_rows(configs[plan['Pprime_comparator']],configs['T4'])
  if closeout:
   for row in reported:row['verdict']='descriptive'
  rows.extend(reported)
 write_deltas(rows,REPO/plan.get('results_directory','results/p_recipe')/'deltas.csv')
 chosen,decision=final_recipe_choice(plan,configs,rows)
 target=study_root(plan)/'final_recipe.json';c=dict(configs[chosen])
 for key in ('resume','resume_samples','resume_from_output','attempt','handoff_request','handoff_ack','required_gpu_uuid'):
  c.pop(key,None)
 reproduction_name=c.get('run_prefix','')+'P_final_recipe_reproduction'
 c.update(run=reproduction_name,output=str(Path(c['output']).parent/reproduction_name))
 parameter_paths={Path(item['label_parameters']) for item in configs.values() if item.get('label_parameters')}
 for path in study_root(plan).glob('round*/*.json'):
  item=read(path)
  if item.get('label_parameters') and (Path(item['output'])/'readout/scores.json').is_file():parameter_paths.add(Path(item['label_parameters']))
 exported=REPO/'configs/p_recipe/label_parameters';exported.mkdir(parents=True,exist_ok=True)
 for path in sorted(parameter_paths):(exported/path.name).write_text(path.read_text())
 if c.get('label_parameters'):c['label_parameters']='configs/p_recipe/label_parameters/'+Path(c['label_parameters']).name
 target.write_text(json.dumps(c,indent=2)+'\n')
 cohort=read(configs['T2']['corpus']);full_count=cohort['train_molecules']
 verdict=dict(final_run=configs[chosen]['run'],final_arm=chosen,final_components=configs[chosen]['components'],
  study_revision=plan.get('study_revision','original_20261113'),
  runnable_configuration=str(target),T2_T3=decision,Pprime_comparator=plan['Pprime_comparator'],
  selection_authority=plan.get('selection_authority'),recipe_frozen=plan.get('recipe_frozen',False),
  conditional_seed_decisions_complete=plan.get('conditional_seed_decisions_complete',False),
  seed_comparisons=seed_state,per_task_comparison_basis='seed0 descriptive' if closeout else 'legacy',
  external_adoptions=plan.get('external_adoptions',[]),
  Pprime_and_scaling_recipe='T2/final merged recipe',
  repeat_on_T3='Not applicable:18B cancels T3; no post-closeout training' if closeout else 'Pending user decision; no rerun' if chosen=='T3' else 'Not needed',
  T4_included='T4' in configs,T4_user_decision=plan.get('T4_user_decision','KEEP'),
  T4_user_confirmation=plan.get('T4_user_confirmation'),
  neither_candidate_beats_T1=not any(row['purpose']=='confirmation' and row['readout']=='R3' and row['verdict']=='win' for row in rows),
  comparisons=rows,B0_M2_budget_sign=budget_sign_comparison(plan,configs),training_samples=configs['T2']['samples'],batch_size=c['batch_size'],
  batch_size_by_arm={arm:item['batch_size'] for arm,item in configs.items()},full_TRAIN_molecules=full_count,
  molecule_repeats={'250000':configs['T2']['samples']/250000,'500000':configs['T2']['samples']/500000,str(full_count):configs['T2']['samples']/full_count},
  molecule_repeat_note='Fixed sample budget increases repetition when molecule count decreases; descriptive only, no expansion decision.')
 return verdict

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 plan=read(a.plan);result=close(plan);destination=Path(a.output)
 from execution_ledger import write
 if result.get('conditional_seed_decisions_complete') is False:destination=destination.with_name(destination.stem+'.pending.json')
 elif plan.get('selection_authority')==CLOSEOUT:write(a.plan,plan)
 destination.parent.mkdir(parents=True,exist_ok=True)
 write(destination,result);print(json.dumps(result,indent=2),flush=True)
