"""Close only the prescribed HEADS/pooling comparisons after actual complete evaluations."""
import argparse,fcntl,json,os,subprocess,sys
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
H=C/'HEADS_V3_20261113'
B=Path('/lfshome/zixiao/model_v31_20261105/HEADS_V3_20261113')
def read(path):return json.loads(Path(path).read_text())
def finish(group,plan_path,manifest_path,result,page,evaluation):
 if not plan_path.exists() or not manifest_path.exists():return
 plan=read(plan_path)
 if not any(Path(row['evaluation_output'])==evaluation for row in plan['runs']):return
 manifest=read(manifest_path)
 # Existing scientific consumers enforce all candidates,conditions,tasks and paired draws.
 for conditions in manifest['panels'].values():
  for source in conditions.values():
   path=Path(source);marker=path.parent/'producer_complete.json'
   if not path.is_file() or not marker.is_file():return
   if read(marker).get('status')!='PREDICTIONS_COMPLETE':return
 revision=R/'configs/dev_panel_v3.json'
 if revision.exists():
  policy=read(revision)
  scope=policy['authority']['retrospective_scope']
  if scope=='REEVALUATE_C1_T0_T1' and policy['authority'].get('reselection_status')!='COMPLETE_MATCHES_CURRENT_RUNNING_ARCHITECTURE':
   print(group+' selection waits for actual new C1/T1 reselection and architecture compatibility',flush=True)
   return
  if ((scope not in ('FORWARD_ONLY_KEEP_C1_T0_T1','REEVALUATE_C1_T0_T1')
       and not policy['authority'].get('forward_evaluation_requested'))
      or any(read(source).get('panel')!='v3'
       for conditions in manifest['panels'].values() for source in conditions.values())):
   print(group+' comparison deferred until the requested new panel and scope are ready',flush=True)
   return
 with (H/(group+'_comparison.lock')).open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  if result.exists():
   if page.exists():return
   # Recover documentation from the existing scientific result,never rescore it.
   saved=read(result)
   lines=['# '+saved['group'],'','Status: '+saved['status'],'',
    'Fixed taskbook-v3 paired molecule-group bootstrap: 1000 draws, seed20261025; equal tasks then equal conditions.',
    '', 'Source manifest: \x60'+str(saved['input_manifest'])+'\x60','',
    '\x60\x60\x60json',json.dumps(saved,indent=2,ensure_ascii=False),'\x60\x60\x60','']
   page.parent.mkdir(parents=True,exist_ok=True);page.write_text('\n'.join(lines));return
  if page.exists():raise FileExistsError('Retain existing group report without a matching original result')
  subprocess.run([sys.executable,'-B',str(R/'tools/model_v3/v3_score_followon.py'),
   '--manifest',str(manifest_path),'--results',str(result),'--page',str(page)],cwd=R,check=True)
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--evaluation-output',type=Path,required=True)
 args=parser.parse_args();evaluation=args.evaluation_output
 if not evaluation.is_relative_to(B):return
 if os.getuid()!=1278:raise ValueError('Use the actual model owner')
 cases=[('pooling',H/'pooling_plan.json',H/'pooling_decision_manifest.json',
   R/'results/model_v3_pooling.json',R/'docs/model_v3/M3_POOLING_RESULTS.md'),
  ('heads',H/'plan.json',H/'decision_manifest.json',
   R/'results/model_v3_heads.json',R/'docs/model_v3/M3_HEADS_RESULTS.md')]
 for values in cases:
  try:finish(*values,evaluation)
  except Exception as error:
   # A postprocessing fault never reclassifies or reruns a completed native panel.
   record=dict(group=values[0],evaluation_output=str(evaluation),error=type(error).__name__,
    detail=str(error),original_panel_retained=True,requires_coordinator_recovery=True)
   with (H/'group_comparison_failures.jsonl').open('a') as stream:
    stream.write(json.dumps(record)+'\n')
   print(json.dumps(record),flush=True)
if __name__=='__main__':main()
