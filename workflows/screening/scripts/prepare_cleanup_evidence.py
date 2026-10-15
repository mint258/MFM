"""Root-only light scheduler evidence before the authorized cleanup allocation."""
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
JOBS = ['4513516','4513519','4513520','4513521','4513633','4513634']


def query(argv):
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


output = query(['sacct','-X','-j',','.join(JOBS + ['4513636']),'-n','-P',
                '-o','JobID,User,UID,State,ExitCode,NodeList'])
rows = {}
for line in output.splitlines():
    parts = line.split('|')
    if len(parts) >= 6:
        rows[parts[0]] = dict(zip(['job_id','user','uid','state','exit_code','node'],parts[:6]))
for job in JOBS + ['4513636']:
    row = rows[job]
    if int(row['uid']) != os.getuid() or row['state'] != 'COMPLETED' or row['exit_code'] != '0:0':
        raise ValueError('Expected this round own completed resource job: ' + job)
queue = query(['squeue','-h','-j',','.join(JOBS + ['4513636']),'-o','%i|%T'])
if queue.strip():
    raise ValueError('C3 or Cclose still live')
evidence = {'created_epoch': time.time(), 'completed_own_jobs': {
    job: {**rows[job], 'uid':int(rows[job]['uid'])} for job in JOBS},
    'Cclose_state':rows['4513636']['state'],'scheduler_raw':output,'C3_or_Cclose_live_queue':queue}
(ROOT / 'reports/cleanup_terminal_evidence.json').write_text(json.dumps(evidence,indent=2) + '\n')
print(json.dumps({'status':'OWN_SIX_C3_AND_CCLOSE_TERMINAL_CONFIRMED','jobs':JOBS}))
