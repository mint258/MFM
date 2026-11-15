"""Close a screening round using the registered paired comparison and merge."""
import argparse,csv,json
from pathlib import Path
from phychem_mfm.phase1.p_recipe_data import read_json
from phychem_mfm.phase1.p_recipe import paired_decision
from phychem_mfm.phase1.p_recipe_plan import accepted_winners
REPO=Path(__file__).resolve().parents[2]


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


def close(plan,previous,round_gpu_hours):
 if plan.get('selection_valid') is False or previous and previous.get('selection_valid') is False:raise ValueError('The user invalidated this screening evidence')
 if previous and previous.get('study_revision','original_20261113')!=plan.get('study_revision','original_20261113'):raise ValueError('Cannot merge screening evidence from different study revisions')
 configurations=[(path,read_json(path)) for path in plan['configurations']]
 unresolved=unresolved_entries(plan,configurations)
 eligible=[(path,c) for path,c in configurations if c['arm'] not in unresolved]
 baseline=next(c for path,c in configurations if c['arm']==plan['baseline']);round_number=plan['round']
 decisions={};rows=[];by_arm={c['arm']:c for path,c in configurations}
 evidence=dict(previous.get('component_evidence',{})) if previous else {}
 for path,c in eligible:
  if c['arm']==plan['baseline']:continue
  compared=compare(c,baseline,'screening',round_number);rows.extend(compared);decisions[c['arm']]=compared[0]
  evidence[c['arm']]=dict(compared[0],configuration=path)
 selected=accepted_winners(decisions);base_components=set(plan['baseline_components']);rollback=False
 if previous:
  best=read_json(previous['best_single_configuration']);compared=compare(baseline,best,'merge_rollback',round_number);rows.extend(compared)
  if compared[0]['verdict']=='loss':base_components=set(best['components']);rollback=True
 merged=base_components|selected
 single=[(path,c) for path,c in eligible if c['arm']!=plan['baseline']]
 best_path,best=max(single or eligible,key=lambda item:read_json(Path(item[1]['output'])/'readout/scores.json')['R3']['mean_normalized_improvement'])
 empty=(previous.get('consecutive_empty_rounds',0) if previous else 0)+1 if not selected else 0
 hours=(previous.get('screening_gpu_hours',0.) if previous else 0.)+round_gpu_hours
 reasons=[]
 if round_number==3:reasons.append('Three registered rounds completed')
 if empty>=2:reasons.append('Two consecutive rounds without winning components')
 if hours>=200:reasons.append('Screening reached200GPUh; current round completed')
 state=dict(round=round_number,decisions=decisions,adopted_winners=sorted(selected),merged_components=sorted(merged),
  unresolved_arms=unresolved,skipped_arms=dict(plan.get('skipped',{})),
  study_revision=plan.get('study_revision','original_20261113'),selection_valid=True,
  merge_base_components=sorted(base_components),merge_rollback=rollback,component_evidence=evidence,
  best_single_configuration=best_path,best_single_run=best['run'],consecutive_empty_rounds=empty,
  round_gpu_hours=round_gpu_hours,screening_gpu_hours=hours,screening_finished=bool(reasons),stop_reasons=reasons,
  secondary_disagreement=[name for name,d in decisions.items() if d['verdict']=='win' and next(r for r in rows if r['purpose']=='screening' and r['A']==by_arm[name]['run'] and r['readout']=='R1')['verdict']=='loss'])
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
 Path(a.output).write_text(json.dumps(state,indent=2)+'\n');print(json.dumps(state,indent=2),flush=True)
