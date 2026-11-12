"""Score actual complete C3 once,then queue its required selected-view SDP heads."""
import datetime,fcntl,json,os,subprocess,sys
from pathlib import Path
plan_path=Path(sys.argv[1]);C=plan_path.parent
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
control=R.parent/'runs/model_v31_20261105'
p=json.loads(plan_path.read_text())
if not all((Path(row['evaluation_output'])/'producer_complete.json').exists() for row in p['runs']):
 raise SystemExit(0)
with (C/'comparison.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 result=R/'results/model_v3_c3_views.json';page=R/'docs/model_v3/M3_C3_RESULTS.md'
 if not (result.exists() and page.exists()):
  subprocess.run([sys.executable,'-B',str(R/'tools/model_v3/v3_score_followon.py'),
   '--manifest',str(C/'decision_manifest.json'),'--results',str(result),'--page',str(page)],cwd=R,check=True)
 # Queue failures are execution failures,not a failed native panel evaluation.
 # Actual handles/journals are retained for the regular coordinator; no blind retry.
 queued=subprocess.run(['ssh','-n','compute-0-20',
  '/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B '+
  str(control/'MODEL_V3_queue_HEADS_SDP_after_C3_20261113.py')+
  ' --completion-job '+str(int(os.environ['SLURM_JOB_ID']))],capture_output=True,text=True)
 record=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
  returncode=queued.returncode,stdout=queued.stdout,stderr=queued.stderr,
  evaluation_result_retained=True,automatic_queue_only=True)
 with (C/'heads_sdp_queue_attempts.jsonl').open('a') as stream:
  stream.write(json.dumps(record)+'\n')
 if queued.returncode:
  print('C3 panel selection retained; SDP queue needs coordinator recovery',flush=True)
 else:print(queued.stdout,flush=True)
