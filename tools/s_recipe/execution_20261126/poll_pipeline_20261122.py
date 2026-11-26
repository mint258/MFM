"""One scheduled login-side metadata poll and own reservation renewal."""
import csv
import datetime
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path('/share/home/zixiao/descriptor_analysis')
CONTROL=ROOT/'runs/s_recipe_20261120'
sys.path.insert(0,str(ROOT/'MFM_s_recipe/tools/s_recipe'))
from storage_20261122 import claim_current
from retire_closed_training_reservations_20261122 import retire

state_at_start=json.loads((CONTROL/'current_state.json').read_text())
ledger=json.loads((CONTROL/'execution.json').read_text())
identifiers={4538264,4538584,4538597}
for record in state_at_start.get('extension_jobs',{}).values():
    if record.get('job_id'):
        identifiers.add(int(record['job_id']))
for record in state_at_start.get('B0_budget_trend_jobs',{}).values():
    identifiers.update(int(record[key]) for key in ('gpu_job','cpu_job') if record.get(key))
for bucket in (ledger['runs'],ledger['statistics']):
    identifiers.update(int(record['job_id']) for record in bucket.values() if record.get('job_id'))
    identifiers.update(int(record['standby_job_id']) for record in bucket.values() if record.get('standby_job_id'))
ids=','.join(map(str,sorted(identifiers)))
raw=subprocess.check_output(['/usr/bin/timeout','15s','/usr/bin/sacct','-X','-n','-P',
    '-j',ids,'--format=JobIDRaw,State,ExitCode,NodeList,Elapsed'],text=True)
jobs=[]
for line in raw.splitlines():
    if line.strip():
        job,state,code,node,elapsed=line.strip().split('|')[:5]
        jobs.append(dict(job_id=int(job),state=state,exit_code=code,node=node,elapsed=elapsed))
retired=retire(ledger,jobs)
future=claim_current()
cursors={}
for name in ledger['runs']:
    path=CONTROL/'training'/name/'losses.csv'
    if not path.is_file():
        continue
    with path.open('rb') as stream:
        stream.seek(max(0,stream.seek(0,2)-8192))
        rows=list(csv.reader(stream.read().decode().splitlines()))
    row=next((row for row in reversed(rows) if len(row)==9 and row[0].isdigit()),None)
    if row is None:
        continue
    cursors[name]=dict(samples=int(row[0]),updates=int(row[1]),training_seconds=float(row[-1]))
now=time.time()
stamp=datetime.datetime.fromtimestamp(now,datetime.timezone(datetime.timedelta(hours=8)))
record=dict(observed_time=now,observed_at_CST=stamp.isoformat(),jobs=jobs,cursors=cursors,
            own_reservation_renewed=True,own_remaining_bytes=future,retired_training_futures=retired)
destination=CONTROL/('pulse_'+stamp.strftime('%Y%m%d_%H%M')+'.json')
destination.write_text(json.dumps(record,indent=2)+'\n')
sfile=CONTROL/'current_state.json'
s=json.loads(sfile.read_text())
s.update(last_pipeline_poll_CST=stamp.isoformat(),
         pipeline_next_poll_CST=(stamp+datetime.timedelta(seconds=1800)).isoformat(),
         latest_pipeline_pulse=str(destination))
for key,field in (('S_B0_s0_3M','baseline_last_observed_samples'),('S_N1_s0_3M','N1_last_observed_samples'),('S_N2_s0_3M','N2_last_observed_samples')):
    if key in cursors:
        s[field]=cursors[key]['samples']
pending=sfile.with_name(sfile.name+'.next.pulse')
pending.write_text(json.dumps(s,indent=2)+'\n')
pending.replace(sfile)
previous_path=state_at_start.get('latest_pipeline_pulse')
previous=json.loads(Path(previous_path).read_text()) if previous_path and Path(previous_path).is_file() else {}
previous_jobs={row['job_id']:row['state'] for row in previous.get('jobs',[])}
print(json.dumps(dict(observed_at_CST=record['observed_at_CST'],
    cursors={name:value for name,value in cursors.items() if name.endswith('_9M') or value['samples']<3000000},
    active_or_failed_jobs=[row for row in jobs if row['state']!='COMPLETED' and not row['state'].startswith('CANCELLED')],
    changed_job_states=[row for row in jobs if previous_jobs.get(row['job_id'])!=row['state']],
    own_reservation_renewed=True,retired_training_futures=retired)),flush=True)
