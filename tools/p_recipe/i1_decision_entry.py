"""Registered I1 decision using unchanged original paired-seed mathematics."""
import argparse,json,os,time,fcntl
from pathlib import Path

def recommendation(primary):
 decision=primary['decision'];verdict=decision['verdict']
 if primary['seed1_required']:return 'WAITING_CONDITIONAL_SEED1',None
 if verdict=='win':
  if primary['seed_count']!=2:raise ValueError('I1 WIN must be confirmed with two seeds')
  return 'COMPLETE','DROP'
 if verdict=='loss':return 'COMPLETE','RETAIN'
 if decision['ci_lower']<=0<=decision['ci_upper']:return 'COMPLETE','DROP'
 if decision['ci_upper']<0:return 'COMPLETE','RETAIN'
 # 22B does not enumerate a TIE whose entire CI is positive. Keep the raw
 # registered result, and obtain clarification only if this actual case occurs.
 return 'WAITING_USER_RULE_INTERPRETATION',None

def validate_native_sources(candidate,baseline,seed):
 if (candidate['arm']!='I1' or baseline['arm']!='F2' or any(c['samples']!=3000000 or c['seed']!=seed or c.get('budget_curve') or c.get('source_training_budget',3000000)!=3000000 for c in [candidate,baseline])):
  raise ValueError('I1 must use own-budget3M and the original own-budget round4 F2')
 expected=dict(baseline['p_recipe'],anti_collapse=False)
 if candidate['p_recipe']!=expected:raise ValueError('The only registered recipe change is disabling B4')
 if candidate['normalizations']!=baseline['normalizations'] or 'window2_TRAIN_normalization_parameters_20261107_v1' not in candidate['normalizations']:
  raise ValueError('The fixed11-07 normalization must remain identical')

def retained_clip_report(configuration):
 path=Path(configuration['output'])/'clip_calibration.json'
 value=json.loads(path.read_text())
 if not value.get('fitted') or (value.get('calibration_samples'),value.get('window_start_samples'),value.get('quantile'),value.get('initial_clip'))!=(150000,60000,.99,281.7):
  raise ValueError('A completed original fixed-window clip report is required')
 return dict(path=str(path),report=value,recomputed=False)

def run(c):
 from finetune_entry import CooperativeStop,set_actual_deadline
 from finetune_statistics_entry import require_cpu_admission,atomic_json,fingerprint
 if c.get('ready') is not True:raise ValueError('Actual3M frozen evaluation must finish first')
 with CooperativeStop() as stop:
  set_actual_deadline(c,stop);require_cpu_admission(c)
  import shared_guard
  from phychem_mfm.phase1.p_recipe_seed_policy import combined_seed_decision
  registry=json.loads((shared_guard.REGISTRY/'p-recipe.json').read_text());future=sum(x['bytes'] for x in registry['entries'] if x['kind']=='shared_fs' and x.get('path')=='/share')
  shared_guard.check_with_timeout('p-recipe','shared_fs',future,path='/share')
  output=Path(c['output']);output.mkdir(parents=True,exist_ok=True)
  with (output/'owner.lock').open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   if (output/'primary_complete.json').exists():raise ValueError('Closed intervention decision must be reused')
   scores={};metadata={};identities={};clips={}
   def load_seed(seed,entry):
    native=[json.loads(Path(entry[k]).read_text()) for k in ['candidate_native_configuration','baseline_native_configuration']]
    validate_native_sources(*native,seed)
    clips[seed]={name:retained_clip_report(configuration) for name,configuration in zip(['candidate','baseline'],native)}
    pair=[];identity={}
    for name,configuration,key in zip(['candidate','baseline'],native,['candidate_evaluation_configuration','baseline_evaluation_configuration']):
     evaluation=json.loads(Path(entry[key]).read_text());root=Path(evaluation['output'])
     if (evaluation['samples']!=3000000 or evaluation.get('source_run',evaluation['run'])!=configuration['run'] or evaluation.get('source_training_budget',3000000)!=3000000):raise ValueError('Evaluation source ancestry differs')
     summary=json.loads((root/'summary.json').read_text());value=json.loads((root/'readout/scores.json').read_text())
     if summary.get('status')!='COMPLETE' or summary['samples']!=3000000 or not all(value[r].get('complete') and value[r]['bootstrap_defined']==1000 and value[r]['bootstrap_samples']==1000 for r in ['R1','R3']):raise ValueError('Registered frozen evaluation incomplete')
     pair.append(value);identity[name]=dict(configuration=fingerprint(entry[key]),scores=fingerprint(root/'readout/scores.json'))
    if any(pair[0][r]['paired_bootstrap']['groups']!=pair[1][r]['paired_bootstrap']['groups'] or pair[0][r]['paired_bootstrap']['seed']!=pair[1][r]['paired_bootstrap']['seed'] for r in ['R1','R3']):raise ValueError('Original molecular draws must align')
    scores[seed]=pair;metadata[seed]=native;identities[seed]=identity
   load_seed(0,c['seed0'])
   def pairs(readout):
    return {seed:(a[readout]['mean_normalized_improvement'],b[readout]['mean_normalized_improvement'],a[readout]['paired_bootstrap']['values'],b[readout]['paired_bootstrap']['values']) for seed,(a,b) in scores.items()}
   prior=output/'seed0_original_comparison.json'
   if prior.exists():
    initial=json.loads(prior.read_text())
    if initial['identity']!=identities[0]:raise ValueError('Closed seed0 inputs changed')
    seed0=initial['results']
   else:
    if stop.requested:return 75
    seed0={r:combined_seed_decision(pairs(r)) for r in ['R3','R1']}
    atomic_json(prior,dict(identity=identities[0],results=seed0))
   required=seed0['R3']['seed0_win_requires_confirmation']
   results=seed0
   if c.get('seed1') is not None:
    if not required:raise ValueError('No unrequested seed1 comparison')
    load_seed(1,c['seed1'])
    results={r:combined_seed_decision(pairs(r)) for r in ['R3','R1']}
   for readout,value in results.items():
    value['may_trigger_seed1']=readout=='R3'
    if readout=='R1':value['seed1_required']=False
   status,action=recommendation(results['R3'])
   a,b=metadata[0]
   record=dict(status=status,arm='I1',candidate=dict(arm='I1',run=a['run'],samples=3000000,source_training_budget=3000000),baseline=dict(arm='F2',run=b['run'],samples=3000000,source_training_budget=3000000),pretraining_seed_count=len(scores),conditional_seed1_required=required,conditional_seed1_complete=required and len(scores)==2,verdict=results['R3']['decision']['verdict'],rule_recommendation=action,original_readout_comparisons=results,source_identity=identities,frozen_recipe_changed=False,user_adoption_pending=True,new_model_fits=0,new_bootstrap_draws=0,normalization_changed=False,source='Original p_recipe_seed_policy.combined_seed_decision',job=os.environ['SLURM_JOB_ID'])
   record['gradient_clip_reports']=clips
   atomic_json(output/'primary.json',record)
   if status=='COMPLETE':atomic_json(output/'primary_complete.json',dict(status='COMPLETE',job=os.environ['SLURM_JOB_ID'],source_identity=identities))
   print(json.dumps(dict(status=status,verdict=record['verdict'],conditional_seed1_required=required,rule_recommendation=action)),flush=True);return 0

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--configuration',type=Path,required=True);a=p.parse_args();c=json.loads(a.configuration.read_text())
 if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('CPU-only decision required')
 raise SystemExit(run(c))
