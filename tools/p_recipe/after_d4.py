"""Start bounded P0 when repaired training parameters close; MAD may continue."""
import json,os,shlex,subprocess,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis');C=R/'runs/p_recipe_20261113'
READY=Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/D4_REPAIRED/routes.json')
TRAINING_READY=READY.with_name('training_routes.json')

def wait_for_routes():
 print(json.dumps(dict(state='WAITING_FOR_CLOSED_TRAINING_PARAMETERS',pid=os.getpid(),
     paths=[str(TRAINING_READY),str(READY)])),flush=True)
 while True:
  for path in (TRAINING_READY,READY):
   try:
    routes=json.loads(path.read_text())
    if routes.get('numeric_statistics_refitted') and (routes.get('training_normalizations_complete') or routes.get('D4_complete')):
     return path
   except (FileNotFoundError,json.JSONDecodeError):pass
  time.sleep(30)

def set_normalizations(path,routes):
 configuration=json.loads(path.read_text());configuration['normalizations']=str(routes)
 path.write_text(json.dumps(configuration,indent=2)+'\n')

def main():
 routes=wait_for_routes()
 set_normalizations(R/'MFM_p_recipe/configs/p_recipe/base.json',routes)
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
