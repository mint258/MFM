"""Start the remaining bounded P0 diagnostics after the repaired D4 is published."""
import json,os,shlex,subprocess,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis');C=R/'runs/p_recipe_20261113'
READY=Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/D4_REPAIRED/routes.json')

def main():
 print(json.dumps(dict(state='WAITING_FOR_REPAIRED_D4',pid=os.getpid(),path=str(READY))),flush=True)
 while True:
  try:
   routes=json.loads(READY.read_text())
   if routes.get('D4_complete') and routes.get('numeric_statistics_refitted'):break
  except (FileNotFoundError,json.JSONDecodeError):pass
  time.sleep(30)
 for stage in ('D1','D2','D3'):
  path=C/('P0_'+stage+'.json');c=json.loads(path.read_text());py=c['command'][4]
  command=[py,'-B','-u',str(R/'MFM_p_recipe/tools/p_recipe/native_run.py'),'--configuration',str(path)]
  code='import subprocess;f=open('+repr(str(C/('P0_'+stage+'.log')))+',"ab",buffering=0);p=subprocess.Popen('+repr(command)+',stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);print(p.pid)'
  try:
   pid=subprocess.check_output(['ssh','-n',c['node'],shlex.join([py,'-c',code])],text=True).strip()
   print(json.dumps(dict(stage=stage,state='NATIVE_WRAPPER_STARTED',node=c['node'],wrapper_pid=pid)),flush=True)
  except subprocess.CalledProcessError as error:
   print(json.dumps(dict(stage=stage,state='LAUNCH_FAILED',exit_code=error.returncode)),flush=True)
 print(json.dumps(dict(state='P0_LAUNCHES_ISSUED',note='Real exits remain in each native process state; no training is started here.')),flush=True)
if __name__=='__main__':main()