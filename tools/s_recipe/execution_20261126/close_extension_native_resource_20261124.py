"""Close only complete registered E1/subset native producers and their own futures."""
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
ROOT=Path('/share/home/zixiao/descriptor_analysis')
C=ROOT/'runs/s_recipe_20261120'
sys.path.insert(0,str(ROOT/'MFM_s_recipe/tools/s_recipe'))
from runtime import write
from control_metadata_io_20261127 import write
from storage_20261122 import claim_current

def read(path):
    return json.loads(Path(path).read_text())
def call(*args):
    return subprocess.check_output(['/usr/bin/timeout','15s',*args],text=True).strip()
def waiting(reason):
    print(json.dumps(dict(status=reason)),flush=True)
    raise SystemExit(0)

if os.getuid()!=1278 or len(sys.argv)!=2 or sys.argv[1] not in ('S_E1_k1_s0_3M','S_E1_k2_s0_3M','S_E1_k5_s0_3M','S_subset_T5_s0_9M','S_subset_T6_s0_9M'):
    raise ValueError('Only the five registered E1/subset resource owners')
name=sys.argv[1]
with (C/'execution.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ledger=read(C/'execution.json')
    run=ledger['runs'][name]
    if run.get('full_budget_producer_exit_observed'):
        print(json.dumps(dict(status='ALREADY_CLOSED',evidence=run.get('producer_exit_evidence'))),flush=True)
        raise SystemExit(0)
    path=Path(run['lifecycle_record'])
    closed=read(path)
    if closed.get('job_id') is not None:
        waiting('USE_ACTUAL_SLURM_CLOSURE_ROUTE')
    c=read(run['configuration'])
    from extension_native_training_20261124 import bound
    bound(c)
    if (c['run']!=name or c['samples'] not in (3000000,9000000) or c['seed']!=0 or
            closed.get('run')!=name or closed.get('node')!=c['node'] or closed.get('gpu_uuid')!=c['gpu_uuid']):
        raise ValueError('Source configuration and actual native identity do not match')
    if (closed.get('status')!='TRAINING_COMPLETE_READOUT_PENDING' or
            closed.get('result',{}).get('samples')!=c['samples'] or closed.get('result',{}).get('updates')!=c['samples']//32 or
            not closed.get('owned_descendants_exited') or not closed.get('observer_joined') or not closed.get('ended_at')):
        waiting('WAITING_FULL_REGISTERED_BUDGET_AND_OWNED_EXIT')
    owner=closed['producer']
    if owner['uid']!=1278 or c['node'] not in ('compute-0-20','compute-0-22'):
        raise ValueError('Wrong actual native resource owner')
    code="""import json,sys
from pathlib import Path
p=Path('/proc')/sys.argv[1]
try:
    s=(p/'stat').read_text().rsplit(')',1)[1].split()
    value=dict(pid=int(sys.argv[1]),uid=p.stat().st_uid,start_ticks=int(s[19]))
except (FileNotFoundError,ProcessLookupError):
    value=None
print(json.dumps(value))
"""
    observed=json.loads(call('/usr/bin/ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=3',c['node'],
        shlex.join(['/usr/bin/python3','-B','-c',code,str(owner['pid'])])))
    if observed is not None and all(observed[key]==owner[key] for key in ('pid','uid','start_ticks')):
        waiting('WAITING_ACTUAL_NATIVE_PID_EXIT')
    job=closed['standby_job_id']
    jobname=name+'_extension'
    if int(run['job_id'])!=job:
        raise ValueError('The closure does not bind the actual recorded standby')
    from standby_settlement_20261126 import settle
    settlement_path=C/(name+'_standby_settlement_20261126.json')
    settlement=settle(job,jobname,call,lambda value:write(settlement_path,value),
        read(settlement_path) if settlement_path.exists() else None)
    if not settlement['settled']:
        print(json.dumps(dict(status='WAITING_ACTUAL_STANDBY_SETTLEMENT',**settlement)),flush=True)
        raise SystemExit(0)
    budget=read(C/'storage_additional_entries.json')
    identifiers={name+'_node_disk',name+'_node_ram'}
    removed=[row['id'] for row in budget['entries'] if row['id'] in identifiers]
    budget['entries']=[row for row in budget['entries'] if row['id'] not in identifiers]
    write(C/'storage_additional_entries.json',budget)
    claim_current()
    evidence=dict(run=name,source_lifecycle=str(path),producer=owner,observed_at=time.time(),
        actual_proc_identity=observed,full_budget_samples=c['samples'],owned_descendants_exited=True,
        standby_job_id=job,standby_actual_terminal=settlement['actual'],
        pending_only_cancel_requested=settlement.get('cancel_requested',False),
        retired_writer_futures=removed)
    target=C/(name+'_producer_exit_evidence.json')
    write(target,evidence)
    run.update(full_budget_producer_exit_observed=True,producer_exit_evidence=str(target),
        retired_writer_futures=removed,standby_cancel_requested=settlement.get('cancel_requested',False))
    write(C/'execution.json',ledger)
    print(json.dumps(evidence),flush=True)
