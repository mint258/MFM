"""Short ASCII lines for reliable Windows SSH PTY progress observation."""
from pathlib import Path
import json
import os
import socket
import time

assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
r=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
print('\nSMON_BEGIN',flush=True)
c=r/'control/d3_local_blocks_v1'
print('ROOT_STATE',json.loads((c/'status.json').read_text())['status'])
for key,job in json.loads((c/'jobs.json').read_text()).items():
    p=r/'diagnostics'/key/('job_'+job['job_id']);steps=val=0;rmse=0.
    q=p/'progress.json'
    if q.exists():steps=json.loads(q.read_text())['updates']
    q=p/'curve.json'
    if q.exists():
        item=json.loads(q.read_text())[-1];val=item['optimizer_update'];rmse=item['local_rmse_A']
    print('FIT',key,job['job_id'],max(steps,val),val,int((p/'result.json').exists()))
    print('RMSE',key,format(rmse,'.8f'))
p=r/'diagnostics/lookup_refit_v2/pilot_job4515550'
print('PILOT',len(list((r/'diagnostics/lookup_refit_v2/chunks').glob('chunk_*.json'))),int((p/'result.json').exists()),int((p/'failure.json').exists()))
p=r/'diagnostics/lookup_refit_v1/progress.json';item=json.loads(p.read_text())
print('OLD_LUT',item['visited_records'],round(time.time()-p.stat().st_mtime))
print('LUT_DONE',int((r/'reports/lookup_latest.json').exists()))
print('GSTOP',int((r/'GUIDE_STOP.json').exists()))
print('SMON_END',flush=True)
