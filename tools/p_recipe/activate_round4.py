"""Release registered round4 configurations after the actual C3 completion."""
import argparse,json
from pathlib import Path
from decide_round4 import completed

REPO=Path(__file__).resolve().parents[2]
CONTROL=Path('/share/home/zixiao/descriptor_analysis/runs/p_recipe_20261113')
read=lambda path:json.loads(Path(path).read_text())


def activate(path,c3_path,acceptance_path=None):
 plan=read(path);ledger=read(CONTROL/'study_execution.json')
 c3=completed(c3_path,ledger)
 if c3['arm']!='C3' or c3['round']!=3 or c3['study_revision']!=plan['study_revision']:
  raise ValueError('Use the canonical C3 of this study revision')
 completed(plan['baseline_configuration'],ledger)
 acceptance=read(acceptance_path) if acceptance_path else None
 available={read(p)['arm']:p for p in plan['registered_configurations']}
 enabled=[]
 for arm in plan['training_priority']:
  if arm=='F1':
   if arm in plan.get('unresolved_arms',{}):continue
   if not acceptance or acceptance.get('status')!='ACCEPTED':continue
   f1=read(available[arm])
   if acceptance.get('run')!=f1['run'] or acceptance.get('configuration')!=str(available[arm]):
    raise ValueError('F1 acceptance belongs to a different configuration')
   if not acceptance.get('real_loader') or not acceptance.get('all_fields_passed'):
    raise ValueError('Real-loader per-head acceptance has not passed')
  enabled.append(available[arm]);plan['readiness_by_arm'][arm]='READY'
 plan.update(configurations=enabled,status='READY_AFTER_C3',
             C3_completion=dict(run=c3['run'],configuration=str(c3_path)),
             F1_acceptance=str(acceptance_path) if acceptance_path else None)
 Path(path).write_text(json.dumps(plan,indent=2)+'\n')
 return dict(status=plan['status'],ready_arms=[read(p)['arm'] for p in enabled],
             jobs_submitted=0,F1_pending='F1' not in [read(p)['arm'] for p in enabled])


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--plan',required=True)
 parser.add_argument('--C3-configuration',dest='c3',required=True)
 parser.add_argument('--F1-acceptance',dest='acceptance')
 args=parser.parse_args()
 print(json.dumps(activate(args.plan,args.c3,args.acceptance)),flush=True)
