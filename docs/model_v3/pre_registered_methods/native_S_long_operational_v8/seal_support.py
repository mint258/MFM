"""Trusted same-host census; no lifecycle/counter mutation in this helper."""
from __future__ import annotations
import json
import shlex
from pathlib import Path
from long_common import *


def compute_census(phase,submission,frame):
    manifest,_=verify();submission_ref=binding(submission)
    command=[str(PYTHON),'-B',str(HERE/'same_host_census.py'),'--phase',str(phase),
        '--submission',submission_ref['path'],'--submission-sha256',submission_ref['sha256'],
        '--pins-sha256',manifest['sha256']]
    # Match the proven V8 resources.py explicit trust file. Never inherit
    # the login default StrictHostKeyChecking=false or modify known_hosts.
    prefix=['env','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1']
    argv=['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
        '-o','UserKnownHostsFile='+str(OLD/'compute21_known_hosts_v1'),
        '-o','ConnectTimeout=20',NODE,shlex.join(prefix+command)]
    row=actual(argv,check=False,timeout=120)
    management=slot_layout(phase,frame['slot'])['management']
    record=write(management/'same_host_census_execution_v4.json',row)
    require(row['returncode']==0,'Original-host census failed; raw command retained')
    result=json.loads(row['stdout'])
    require(result['schema']=='native_S_same_host_census_observation_v1'
        and result['host']==NODE and result['uid']==1278 and result['submission']==submission_ref
        and result['operational_manifest']==manifest
        and result['actual_census_source']==binding(HERE/'long_frames.py')
        and result['baseline']==binding(management/'ledger_baseline.json')
        and result['model_or_payload_read'] is False,'Exact original-host/source census result required')
    require(result['current']['shared_ledger_baseline']==read(management/'ledger_baseline.json')
        and result['current']['cap_bytes']==OUTER,'Original baseline/cap changed')
    require(result['current']['whole_job_bytes']+(1<<20)<=OUTER
        and result['current']['static_management_bytes']+(1<<20)<=16<<20,
        'Original output/static reserve must cover final metadata receipts')
    return result['current'],record
