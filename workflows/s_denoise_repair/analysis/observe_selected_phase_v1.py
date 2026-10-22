"""Bounded selected-phase metadata observation; no science calculation or Slurm loop."""
import argparse,json,os,socket
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['d3_local_blocks_v1','d3_message1_v1','d3_message2_v1'],required=True);a=ap.parse_args()
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
c=R/'control'/a.phase
print('SMON_BEGIN',flush=True);print('PHASE',a.phase)
print('ROOT_STATE',json.loads((c/'status.json').read_text())['status'])
jobs_path=c/'jobs.json'
for key,job in (json.loads(jobs_path.read_text()) if jobs_path.exists() else {}).items():
    p=R/'diagnostics'/key/('job_'+job['job_id']);steps=val=0;rmse=None
    q=p/'progress.json'
    if q.exists():steps=json.loads(q.read_text())['updates']
    q=p/'curve.json'
    if q.exists():
        row=json.loads(q.read_text())[-1];val=row['optimizer_update'];rmse=row['local_rmse_A']
    print('FIT',key,job['job_id'],max(steps,val),val,int((p/'result.json').exists()))
    if rmse is not None:print('RMSE',key,format(rmse,'.8f'))
print('GSTOP',int((R/'GUIDE_STOP.json').exists()));print('SMON_END',flush=True)
