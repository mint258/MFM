"""Bounded clock/process metadata only for the two failed pre-GPU entries."""
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time
sys.path.insert(0,'/share/home/zixiao/descriptor_analysis/MFM_s_recipe/tools/s_recipe')
from storage_20261122 import CONTROL as C, REPO as R, write
read=lambda p:json.loads(Path(p).read_text())
handles=('S_final_s0_9M_readout_budget_2000000_attempt0','S_FT_S_G1_3M_qm9_U0_atom_s2_attempt0')
tasks=[read(C/(handles[0]+'_task.json')),read(C/(handles[1]+'_fullft_native_task.json'))]
code=('import sys,json,time;sys.path.insert(0,'+repr(str(R/'tools/s_recipe'))+
    ');import lifecycle_20261122 as l;saved='+repr([t['producer'] for t in tasks])+
    ';print(json.dumps(dict(now=time.time(),same=[l.same_process(l.Identity(**s),l.identity(s["pid"])) for s in saved])))')
before=time.time()
child=subprocess.Popen(['/usr/bin/timeout','15s','ssh','-n','-o','BatchMode=yes',
    '-o','ConnectTimeout=3','compute-0-20',shlex.join([
    '/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python','-u','-B','-c',code])],text=True,stdout=subprocess.PIPE)
remote=json.loads(child.stdout.readline())
after=time.time()
if child.wait(timeout=16)!=0:raise ValueError('Clock metadata subprocess did not close successfully')
value=dict(status='METADATA_OBSERVED',handles=list(handles),producer_identities=[t['producer'] for t in tasks],
    login_before=before,login_after=after,node_observation=remote,
    node_minus_login_seconds_bounds=[remote['now']-after,remote['now']-before],
    scope='Current clock/process metadata; original native wait exit status is unavailable, not fabricated')
write(C/'native_startup_clock_20261127.json',value)
print(json.dumps(value),flush=True)
