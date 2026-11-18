"""Close a screening round using the registered paired comparison and merge."""
import argparse,csv,json
from pathlib import Path
from phychem_mfm.phase1.p_recipe_data import read_json
from phychem_mfm.phase1.p_recipe import paired_decision
from phychem_mfm.phase1.p_recipe_plan import accepted_winners
REPO=Path(__file__).resolve().parents[2]
CLOSEOUT='docs/p_recipe/USER_DIRECTIVE_20261118B.md'


def compare(a,b,purpose,round_number):
 sa=read_json(Path(a['output'])/'readout/scores.json');sb=read_json(Path(b['output'])/'readout/scores.json');rows=[]
 for readout in ('R3','R1'):
  aa,bb=sa[readout],sb[readout]
  result=paired_decision(aa['mean_normalized_improvement'],bb['mean_normalized_improvement'],aa['paired_bootstrap']['values'],bb['paired_bootstrap']['values'])
  rows.append(dict(purpose=purpose,round=round_number,readout=readout,task='MEAN',A=a['run'],B=b['run'],**result))
 return rows


def unresolved_entries(plan,configurations):
 """Read explicit arm-to-reason entries after the registered diagnosis timebox.

 This records a scientific disposition; it sends no signals to live trainers.
 Missing evidence without this declaration remains an error.
 """
 by_arm={c['arm']:(path,c) for path,c in configurations}
 unresolved={}
 for arm,reason in plan.get('unresolved_arms',{}).items():
  if arm not in by_arm:raise ValueError('Unknown unresolved arm: '+arm)
  if arm==plan['baseline']:raise ValueError('The round baseline cannot be unresolved')
  if not isinstance(reason,str) or not reason.strip():raise ValueError('An unresolved arm needs its recorded reason: '+arm)
  path,c=by_arm[arm]
  if (Path(c['output'])/'readout/scores.json').is_file():
   raise ValueError('Cannot omit an arm with completed readout evidence: '+arm)
  unresolved[arm]=dict(status='UNRESOLVED',reason=reason,configuration=str(path),run=c['run'])
 return unresolved


def screening_stop_reasons(plan,empty,hours):
 reasons=[]
 if plan['round']==3:reasons.append('Three registered rounds completed')
 if empty>=2:reasons.append('Two consecutive rounds without winning components')
 limit=plan.get('screening_gpu_hour_limit',200)
 if limit is not None and hours>=limit:reasons.append(f'Screening reached{limit:g}GPUh; current round completed')
 return reasons


def close(plan,previous,round_gpu_hours,*,seed_session=None):
 if plan.get('selection_valid') is False or previous and previous.get('selection_valid') is False:raise ValueError('The user invalidated this screening evidence')
 if previous and previous.get('study_revision','original_20261113')!=plan.get('study_revision','original_20261113'):raise ValueError('Cannot merge screening evidence from different study revisions')
 configurations=[(path,read_json(path)) for path in plan['configurations']]
 unresolved=unresolved_entries(plan,configurations)
 eligible=[(path,c) for path,c in configurations if c['arm'] not in unresolved]
 baseline=next(c for path,c in configurations if c['arm']==plan['baseline']);round_number=plan['round']
 conditional=(round_number==3 and plan.get('study_revision')=='fixed_20261115' and (REPO/CLOSEOUT).is_file())
 session=seed_session;seed_state=None;comparisons={}
 if conditional:
  if session is None:
   from seed_comparisons import SeedComparisons
   session=SeedComparisons(Path(plan['control_directory'])/'conditional_seed_decisions/round3')
  for path,c in eligible:
   if c['arm']!=plan['baseline']:
    comparisons[(c['run'],baseline['run'],'screening')]=session.assess(c,baseline,'screening',round_number)
  if previous:
   best=read_json(previous['best_single_configuration'])
   comparisons[(baseline['run'],best['run'],'merge_rollback')]=session.assess(baseline,best,'merge_rollback',round_number)
  seed_state=session.save()
  if not all(result['ready'] for result in comparisons.values()):
   return dict(status='WAITING_REGISTERED_INPUTS',round=round_number,selection_valid=False,
      conditional_seed_decisions_complete=False,seed_comparisons=seed_state,no_jobs_submitted=True)
 def compared_rows(a,b,purpose):
  return comparisons[(a['run'],b['run'],purpose)]['rows'] if conditional else compare(a,b,purpose,round_number)
 decisions={};rows=[];by_arm={c['arm']:c for path,c in configurations}
 evidence=dict(previous.get('component_evidence',{})) if previous else {}
 for path,c in eligible:
  if c['arm']==plan['baseline']:continue
  compared=compared_rows(c,baseline,'screening');rows.extend(compared);decisions[c['arm']]=compared[0]
  evidence[c['arm']]=dict(compared[0],configuration=path)
 selected=accepted_winners(decisions);base_components=set(plan['baseline_components']);rollback=False
 if previous:
  best=read_json(previous['best_single_configuration']);compared=compared_rows(baseline,best,'merge_rollback');rows.extend(compared)
  if compared[0]['verdict']=='loss':base_components=set(best['components']);rollback=True
 merged=base_components|selected
 single=[(path,c) for path,c in eligible if c['arm']!=plan['baseline']]
 best_path,best=max(single or eligible,key=lambda item:read_json(Path(item[1]['output'])/'readout/scores.json')['R3']['mean_normalized_improvement'])
 empty=(previous.get('consecutive_empty_rounds',0) if previous else 0)+1 if not selected else 0
 hours=(previous.get('screening_gpu_hours',0.) if previous else 0.)+round_gpu_hours
 reasons=[] if conditional else screening_stop_reasons(plan,empty,hours)
 state=dict(round=round_number,decisions=decisions,adopted_winners=sorted(selected),merged_components=sorted(merged),
  unresolved_arms=unresolved,skipped_arms=dict(plan.get('skipped',{})),
  study_revision=plan.get('study_revision','original_20261113'),selection_valid=True,
  merge_base_components=sorted(base_components),merge_rollback=rollback,component_evidence=evidence,
  best_single_configuration=best_path,best_single_run=best['run'],consecutive_empty_rounds=empty,
  round_gpu_hours=round_gpu_hours,screening_gpu_hours=hours,screening_finished=bool(reasons),stop_reasons=reasons,
  secondary_disagreement=[name for name,d in decisions.items() if d['verdict']=='win' and next(r for r in rows if r['purpose']=='screening' and r['A']==by_arm[name]['run'] and r['readout']=='R1')['verdict']=='loss'])
 if conditional:state.update(selection_authority=CLOSEOUT,conditional_seed_decisions_complete=True,
      seed_comparisons=seed_state,registered_round4_pending=True)
 write_deltas(rows,REPO/plan.get('results_directory','results/p_recipe')/'deltas.csv')
 return state


def write_deltas(rows,destination=None):
 destination=Path(destination) if destination is not None else REPO/'results/p_recipe/deltas.csv';destination.parent.mkdir(parents=True,exist_ok=True)
 previous_rows=[]
 if destination.is_file():
  with destination.open() as stream:previous_rows=list(csv.DictReader(stream))
 def key(row):return (row['purpose'],str(row['round']),row['readout'],row.get('task','MEAN'),row['A'],row['B'])
 keys={key(row) for row in rows};previous_rows=[row for row in previous_rows if key(row) not in keys]
 with destination.open('w',newline='') as stream:
  writer=csv.DictWriter(stream,fieldnames=['purpose','round','readout','task','A','B','delta','ci_lower','ci_upper','verdict'])
  writer.writeheader();writer.writerows(previous_rows+rows)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--previous-state');p.add_argument('--round-gpu-hours',type=float,required=True);p.add_argument('--output',required=True);a=p.parse_args()
 state=close(read_json(a.plan),read_json(a.previous_state) if a.previous_state else None,a.round_gpu_hours)
 destination=Path(a.output)
 if state.get('conditional_seed_decisions_complete') is False:destination=destination.with_name(destination.stem+'.pending.json')
 from execution_ledger import write
 write(destination,state);print(json.dumps(state,indent=2),flush=True)
