"""Close registered round4 against M2; do not launch or cancel any run."""
import argparse,json
from pathlib import Path
from decide_round import compare,write_deltas
from seed_comparisons import SeedComparisons
from execution_ledger import write as atomic_write
from phychem_mfm.phase1.p_recipe_plan import accepted_winners,configuration

REPO=Path(__file__).resolve().parents[2]
C=Path('/share/home/zixiao/descriptor_analysis/runs/p_recipe_20261113')
read=lambda p:json.loads(Path(p).read_text())
CLOSEOUT='docs/p_recipe/USER_DIRECTIVE_20261118B.md'
def write(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);atomic_write(path,value)

def adopted_components(decisions):
 eligible={arm:dict(row,verdict='win') for arm,row in decisions.items()
           if row['verdict']=='win' or arm in ('X1','F2') and row['verdict']=='tie'}
 return accepted_winners(eligible)

def completed(path,ledger):
 c=read(path);summary=read(Path(c['output'])/'summary.json');record=ledger['runs'][c['run']]
 if record.get('state')!='COMPLETED' or record.get('exit_code') not in (0,'0:0'):
  raise ValueError('Refresh actual terminal accounting before deciding: '+c['run'])
 if summary.get('status')!='COMPLETE' or summary['samples']!=3000000 or summary['updates']!=93750:
  raise ValueError('Registered round4 requires complete3M training/readouts: '+c['run'])
 scores=read(Path(c['output'])/'readout/scores.json')
 if not all(scores[r].get('complete') and scores[r]['bootstrap_samples']==1000 and scores[r]['bootstrap_defined']==1000 for r in ('R1','R3')):
  raise ValueError('Complete registered readouts required: '+c['run'])
 return c

def pp_disposition(pp,control,result,noise):
 """T4's explicit seed0 rule is independent of a conditional PP seed1."""
 primary=result['seed0_rows'][0]
 a=result['seed0_evidence']['R3']['mean_score_A'];b=result['seed0_evidence']['R3']['mean_score_B']
 noise_delta=abs(noise['observed_seed_noise']['seed1_minus_seed0']['R3']) if noise.get('ready_for_reuse') else None
 effect=max(.01,.05*max(a,b));nonzero=primary['ci_lower']>0 or primary['ci_upper']<0
 if noise_delta is None:raise ValueError('T4 needs the already registered M2 seed-noise observation')
 clear=nonzero and abs(primary['delta'])>=effect and abs(primary['delta'])>noise_delta
 return dict(run=pp['run'],control_run=control['run'],comparison=result['rows'][0] if result['ready'] else None,
    T4_seed0_comparison=primary,T4_decision_basis='Explicit18B PP seed0 versus M2 seed0 rule',
    minimum_effect=effect,noise_R3_difference=noise_delta,noise_pending=False,CI_excludes_zero=nonzero,
    effect_threshold_passed=abs(primary['delta'])>=effect,exceeds_seed_noise=abs(primary['delta'])>noise_delta,
    difference_clear=clear,recommendation='OMIT_T4' if clear else 'KEEP_T4',omission_automatic=True,
    T4_user_decision='OMIT' if clear else 'KEEP',T4_user_confirmation=CLOSEOUT,
    PP_conditional_seed_decision_complete=result['ready'],estimated_saving_GPU_hours=38 if clear else 0)

def record_pp(plan,*,seed_session=None):
 """Record automatic T4 disposition as soon as PP seed0 has readouts."""
 ledger=read(C/'study_execution.json');by_arm={read(p)['arm']:p for p in plan['registered_configurations']}
 pp=completed(by_arm['PP'],ledger);control=completed(plan['baseline_configuration'],ledger)
 session=seed_session or SeedComparisons(Path(plan['control_directory'])/'conditional_seed_decisions/round4_PP')
 result=session.assess(pp,control,'P_vs_Pprime',4);seed_state=session.save()
 if not result.get('seed0_rows'):raise ValueError('PP and M2 seed0 must be complete before deciding T4')
 state=pp_disposition(pp,control,result,read(REPO/'configs/p_recipe/M2_SEED1_REFERENCE.json'))
 state['seed_comparisons']=seed_state
 return state

def close(plan,round3,m3_path,round_gpu_hours,merge_path=None,*,seed_session=None):
 if round3['round']!=3 or round3.get('selection_valid') is False:
  raise ValueError('A valid canonical round3 decision is required')
 if round3['study_revision']!=plan['study_revision']:raise ValueError('Study revisions differ')
 ledger=read(C/'study_execution.json')
 m2=completed(plan['baseline_configuration'],ledger);m3=completed(m3_path,ledger)
 if set(m3['components'])!=set(round3['merged_components']):raise ValueError('M3 configuration differs from round3 decision')
 by_arm={read(p)['arm']:p for p in plan['registered_configurations']}
 unresolved=dict(plan.get('unresolved_arms',{}))
 if set(unresolved)-{'F1'}:raise ValueError('Only F1 has the registered development-skip exception')
 if any(not isinstance(reason,str) or not reason.strip() for reason in unresolved.values()):raise ValueError('Unresolved F1 needs its recorded reason')
 if 'F1' in unresolved and (Path(read(by_arm['F1'])['output'])/'readout/scores.json').exists():
  raise ValueError('A completed F1 result cannot be omitted')
 decisions={};rows=[];evidence=dict(round3['component_evidence']);configs={}
 session=seed_session or SeedComparisons(Path(plan['control_directory'])/'conditional_seed_decisions/round4')
 comparisons={}
 for arm in ('X1','X2','F1','F2'):
  if arm in unresolved:continue
  candidate=completed(by_arm[arm],ledger);configs[arm]=candidate
  comparisons[arm]=session.assess(candidate,m2,'screening',4)
 pp=completed(by_arm['PP'],ledger)
 control=completed(by_arm['M2C'],ledger) if plan['M2C_required'] else m2
 comparisons['PP']=session.assess(pp,control,'P_vs_Pprime',4)
 seed_state=session.save()
 pp_result=pp_disposition(pp,control,comparisons['PP'],read(REPO/'configs/p_recipe/M2_SEED1_REFERENCE.json'))
 if not all(item['ready'] for item in comparisons.values()):
  return dict(status='WAITING_REGISTERED_INPUTS',round=4,selection_valid=False,
      conditional_seed_decisions_complete=False,seed_comparisons=seed_state,PP_comparison=pp_result,
      T4_user_decision=pp_result['T4_user_decision'],T4_user_confirmation=CLOSEOUT,no_jobs_submitted=True)
 for arm in configs:
  compared=comparisons[arm]['rows'];rows.extend(compared);decisions[arm]=compared[0]
  evidence[arm]=dict(compared[0],configuration=by_arm[arm])
 # Keep raw tie verdicts in the report. Only selection treats simpler
 # removals as adoptable, then applies the original larger-delta conflicts.
 candidates=adopted_components(decisions)
 rows.extend(comparisons['PP']['rows'])
 desired=set(m3['components'])|candidates
 required=bool(candidates and set(m3['components'])!=set(m2['components']))
 final=set(m3['components']);validated=not required;merge_decision=None
 root=Path(plan['fidelity_pairs']).parent
 def merged_config(arm):
  c=configuration(m2,desired,run='fixed_20261115_round4_'+arm,round_number=4,arm=arm,samples=3000000)
  c.update(label_parameters=m2['label_parameters'],protocol_exception='USER_DIRECTIVE_20261118_REGISTERED_ROUND4')
  return c
 merge_configuration=None
 if required:
  target=root/'M4_merge.json';expected=merged_config('M4_merge')
  if target.exists():
   if set(read(target)['components'])!=desired:raise ValueError('Preserve and inspect the existing merge configuration')
  else:write(target,expected)
  merge_configuration=str(target)
  write(root/'merge_plan.json',dict(configurations=[str(target)],study_revision=plan['study_revision'],
        results_directory=plan['results_directory'],control_directory=plan['control_directory'],purpose='registered_M3_plus_round4_winners_vs_M3'))
  if merge_path:
   candidate=completed(merge_path,ledger)
   if set(candidate['components'])!=desired:raise ValueError('Merge run does not contain the selected components')
   result=session.assess(candidate,m3,'round4_merge',4);seed_state=session.save()
   if not result['ready']:
    return dict(status='WAITING_REGISTERED_INPUTS',round=4,selection_valid=False,
       conditional_seed_decisions_complete=False,seed_comparisons=seed_state,merge_required=True,
       merge_configuration=str(merge_path),PP_comparison=pp_result,no_jobs_submitted=True)
   compared=result['rows'];rows.extend(compared);merge_decision=compared[0];validated=True
   if merge_decision['verdict']=='win':final=desired
 else:final=desired
 trained_path=None
 if final==set(m3['components']):trained_path=str(m3_path)
 elif required and validated and merge_decision['verdict']=='win':trained_path=str(merge_path)
 else:
  trained_path=next((by_arm[arm] for arm,c in configs.items() if set(c['components'])==final),None)
 recipe_path=root/'M4.json'
 if validated:
  recipe=configuration(m2,final,run='fixed_20261115_round4_M4_recipe',round_number=4,arm='M4',samples=3000000)
  recipe.update(label_parameters=m2['label_parameters'],recipe_preparation_only=True)
  write(recipe_path,recipe)
 state=dict(round=4,study_revision=plan['study_revision'],selection_valid=True,
   decisions=decisions,unresolved_arms=unresolved,screening_candidates=sorted(candidates),
   adopted_winners=sorted(final-set(m3['components'])) if validated else [],merged_components=sorted(final),
   proposed_components=sorted(desired),component_evidence=evidence,merge_base_components=sorted(m3['components']),
   M2_components=sorted(m2['components']),M3_configuration=str(m3_path),
   merge_required=required,merge_configuration=merge_configuration,merge_decision=merge_decision,
   merge_validation_complete=validated,final_recipe_configuration=str(recipe_path) if validated else None,
   final_trained_configuration=trained_path,merged_recipe_has_trained_checkpoint=trained_path is not None,
   PP_comparison=pp_result,T4_user_decision=pp_result['T4_user_decision'],T4_user_confirmation=CLOSEOUT,
   selection_authority=CLOSEOUT,conditional_seed_decisions_complete=True,seed_comparisons=seed_state,round_gpu_hours=round_gpu_hours,
   screening_gpu_hours=round3['screening_gpu_hours']+round_gpu_hours,
   bootstrap=dict(unit='molecule',draws=1000,seed=20261025,source='existing registered paired bootstrap arrays'),
   no_jobs_submitted=True)
 write_deltas(rows,REPO/'results/p_recipe/fixed_20261115/deltas.csv')
 return state

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--round3-state')
 p.add_argument('--m3-configuration');p.add_argument('--round-gpu-hours',type=float)
 p.add_argument('--pp-only',action='store_true')
 p.add_argument('--merge-configuration');p.add_argument('--output',required=True);args=p.parse_args()
 if args.pp_only:state=record_pp(read(args.plan))
 else:
  if args.round3_state is None or args.m3_configuration is None or args.round_gpu_hours is None:p.error('Closing round4 needs round3-state, m3-configuration and round-gpu-hours')
  state=close(read(args.plan),read(args.round3_state),args.m3_configuration,args.round_gpu_hours,args.merge_configuration)
 destination=Path(args.output)
 if state.get('conditional_seed_decisions_complete') is False:destination=destination.with_name(destination.stem+'.pending.json')
 write(destination,state);print(json.dumps(state,indent=2),flush=True)
