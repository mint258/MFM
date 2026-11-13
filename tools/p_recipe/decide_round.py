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
  rows.append(dict(purpose=purpose,round=round_number,readout=readout,A=a['run'],B=b['run'],**result))
 return rows


def close(plan,previous,round_gpu_hours):
 configurations=[(path,read_json(path)) for path in plan['configurations']]
 baseline=next(c for path,c in configurations if c['arm']==plan['baseline']);round_number=plan['round']
 decisions={};rows=[];by_arm={c['arm']:c for path,c in configurations}
 evidence=dict(previous.get('component_evidence',{})) if previous else {}
 for path,c in configurations:
  if c['arm']==plan['baseline']:continue
  compared=compare(c,baseline,'screening',round_number);rows.extend(compared);decisions[c['arm']]=compared[0]
  evidence[c['arm']]=dict(compared[0],configuration=path)
 selected=accepted_winners(decisions);base_components=set(plan['baseline_components']);rollback=False
 if previous:
  best=read_json(previous['best_single_configuration']);compared=compare(baseline,best,'merge_rollback',round_number);rows.extend(compared)
  if compared[0]['verdict']=='loss':base_components=set(best['components']);rollback=True
 merged=base_components|selected
 single=[(path,c) for path,c in configurations if c['arm']!=plan['baseline']]
 best_path,best=max(single or configurations,key=lambda item:read_json(Path(item[1]['output'])/'readout/scores.json')['R3']['mean_normalized_improvement'])
 empty=(previous.get('consecutive_empty_rounds',0) if previous else 0)+1 if not selected else 0
 hours=(previous.get('screening_gpu_hours',0.) if previous else 0.)+round_gpu_hours
 reasons=[]
 if round_number==3:reasons.append('Three registered rounds completed')
 if empty>=2:reasons.append('Two consecutive rounds without winning components')
 if hours>=200:reasons.append('Screening reached200GPUh; current round completed')
 state=dict(round=round_number,decisions=decisions,adopted_winners=sorted(selected),merged_components=sorted(merged),
  merge_base_components=sorted(base_components),merge_rollback=rollback,component_evidence=evidence,
  best_single_configuration=best_path,best_single_run=best['run'],consecutive_empty_rounds=empty,
  round_gpu_hours=round_gpu_hours,screening_gpu_hours=hours,screening_finished=bool(reasons),stop_reasons=reasons,
  secondary_disagreement=[name for name,d in decisions.items() if d['verdict']=='win' and next(r for r in rows if r['purpose']=='screening' and r['A']==by_arm[name]['run'] and r['readout']=='R1')['verdict']=='loss'])
 destination=REPO/'results/p_recipe/deltas.csv';destination.parent.mkdir(parents=True,exist_ok=True)
 previous_rows=[]
 if destination.is_file():
  with destination.open() as stream:previous_rows=list(csv.DictReader(stream))
 keys={(r['purpose'],str(r['round']),r['readout'],r['A'],r['B']) for r in rows}
 previous_rows=[r for r in previous_rows if (r['purpose'],str(r['round']),r['readout'],r['A'],r['B']) not in keys]
 with destination.open('w',newline='') as stream:
  writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(previous_rows+rows)
 return state

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--previous-state');p.add_argument('--round-gpu-hours',type=float,required=True);p.add_argument('--output',required=True);a=p.parse_args()
 state=close(read_json(a.plan),read_json(a.previous_state) if a.previous_state else None,a.round_gpu_hours)
 Path(a.output).write_text(json.dumps(state,indent=2)+'\n');print(json.dumps(state,indent=2),flush=True)