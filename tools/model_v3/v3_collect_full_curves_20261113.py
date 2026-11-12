"""Collect only completed full-D6 endpoint readouts for the original B-star decision."""
import argparse,json,os,socket,subprocess,sys
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
ENDPOINTS={1000000,2000000,4000000,8000000,16000000,32000000,64000000}
def read(path):return json.loads(Path(path).read_text())
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--plan',type=Path,action='append',required=True)
 parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--results',type=Path,required=True)
 parser.add_argument('--page',type=Path,required=True)
 args=parser.parse_args()
 if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-20':
  raise ValueError('Full-curve summary consumption belongs on the existing development node')
 os.chdir(R)
 curves={'S':{},'P':{}};sources=[]
 for path in args.plan:
  plan=read(path)
  for row in plan['runs']:
   if row['stage']!='FULL_TRAIN' or row['condition'] not in ('S','P'):
    raise ValueError('Use only the actual full-D6 segment plans')
   endpoint=row['run_until_samples'];condition=row['condition']
   if endpoint not in ENDPOINTS:raise ValueError('Keep only the registered doubling endpoints')
   evaluation=Path(row['evaluation_output'])
   marker=evaluation/'producer_complete.json'
   if not marker.exists():continue
   completed=read(marker)
   if (completed.get('status')!='PREDICTIONS_COMPLETE'
       or completed.get('statistics_complete') is not True):
    raise ValueError('Use the actual native completed primary evaluation')
   panel=str(evaluation/'R3_summary.json')
   existing=curves[condition].get(str(endpoint))
   if existing is not None and existing!=panel:
    raise ValueError('Retain both conflicting endpoint sources and resolve their actual identity')
   curves[condition][str(endpoint)]=panel
   sources.append(dict(plan=str(path),condition=condition,samples=endpoint,
    training_job=row.get('job'),evaluation_job=row.get('evaluation_job'),panel=panel))
 if not sources:
  print(json.dumps(dict(status='WAITING_FOR_FIRST_ACTUAL_FULL_READOUT',curves=curves,
   results_created=False)));return
 if args.results.exists() or args.page.exists():
  raise FileExistsError('Retain the actual original decision; do not recompute an unchanged prefix')
 sys.path.insert(0,str(R/'tools/model_v3'))
 from v3_prepare_m4_batch_20261113 import fresh_control_output
 output=fresh_control_output(args.output)
 # Empty unfinished-condition prefixes permit independent S/P execution.
 manifest=dict(kind='convergence',group='Full D6 S P B star',curves=curves,
  schedule_budget=64000000,expected_molecules=1194551,
  actual_completed_sources=sources,source_roles=['train','train_inner_validation'],
  downstream_TEST_read=False)
 manifest_path=output/'curve_manifest.json'
 manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
 env=os.environ.copy()
 env['PYTHONPATH']=str(R/'current')+os.pathsep+env.get('PYTHONPATH','')
 subprocess.run([sys.executable,'-B',str(R/'tools/model_v3/v3_score_followon.py'),
  '--manifest',str(manifest_path),'--results',str(args.results),'--page',str(args.page)],
  cwd=R,env=env,check=True)
 print(json.dumps(dict(status='ACTUAL_FULL_CURVE_DECISION_WRITTEN',
  latest={condition:max(map(int,points),default=0) for condition,points in curves.items()},
  manifest=str(manifest_path),results=str(args.results),page=str(args.page),
  no_probe_refitted=True,model_and_recipe_frozen=False)))
if __name__=='__main__':main()
