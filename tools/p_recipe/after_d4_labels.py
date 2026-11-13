"""Fit A1/A2 after training parameters close while MAD may continue."""
import json,shlex,subprocess
from pathlib import Path
from after_d4 import wait_for_routes,set_normalizations
R=Path('/share/home/zixiao/descriptor_analysis');C=R/'runs/p_recipe_20261113'

def main():
 routes=wait_for_routes()
 for stage in ('fit_A1','fit_A2'):
  path=C/('P0_'+stage+'.json');c=json.loads(path.read_text());py=c['command'][4]
  configuration=Path(c['command'][c['command'].index('--configuration')+1])
  if not configuration.is_absolute():configuration=R/'MFM_p_recipe'/configuration
  set_normalizations(configuration,routes)
  command=[py,'-B','-u',str(R/'MFM_p_recipe/tools/p_recipe/native_run.py'),'--configuration',str(path)]
  code='import subprocess;f=open('+repr(str(C/('P0_'+stage+'.log')))+',"ab",buffering=0);p=subprocess.Popen('+repr(command)+',stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);print(p.pid)'
  try:
   pid=subprocess.check_output(['ssh','-n',c['node'],shlex.join([py,'-c',code])],text=True).strip()
   print(json.dumps(dict(stage=stage,state='NATIVE_WRAPPER_STARTED',node=c['node'],wrapper_pid=pid)),flush=True)
  except subprocess.CalledProcessError as error:
   print(json.dumps(dict(stage=stage,state='LAUNCH_FAILED',exit_code=error.returncode)),flush=True)
 print(json.dumps(dict(state='LABEL_FIT_LAUNCHES_ISSUED',note='Real exits remain in each native process state; no training is started here.')),flush=True)
if __name__=='__main__':main()
