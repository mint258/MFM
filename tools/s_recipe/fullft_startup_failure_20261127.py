"""Prove an unchanged saved state after a closed native startup RAM refusal."""
import copy
import hashlib
import json
from pathlib import Path
import stat

POLICY='S_FULLFT_STARTUP_FAILURE_SETTLEMENT_20261127_V1'
STATUS='FAILED_STARTUP_SAFE_CONTINUATION'
WAIT_POLICY='S_FULLFT_WAIT_ONLY_STARTUP_SETTLEMENT_20261128_V1'
C=Path('/share/home/zixiao/descriptor_analysis/runs/s_recipe_20261120')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def file_metadata(path):
    path=Path(path)
    value=path.lstat()
    return dict(path=str(path),uid=value.st_uid,size=value.st_size,ino=value.st_ino,
        dev=value.st_dev,mtime_ns=value.st_mtime_ns,ctime_ns=value.st_ctime_ns,
        regular=stat.S_ISREG(value.st_mode))


def snapshots(configuration):
    return {name:file_metadata(Path(configuration['output'])/name)
        for name in ('complete_state.pt','history.jsonl')}


def validate_failure(handle,row,closure,configuration,task,files,control=C):
    control=Path(control)
    expected_output=control/'finetune_20261124'/row['run']
    if (row.get('mode')!='finetune_native' or row.get('job_id') is not None
            or row.get('node') not in ('compute-0-20','compute-0-22')
            or task.get('native_handle')!=handle or closure.get('native_handle')!=handle
            or task.get('standby_job_id')!=row.get('standby_job_id')
            or closure.get('standby_job_id')!=row.get('standby_job_id')
            or task.get('configuration')!=row.get('configuration')
            or Path(row['configuration'])!=control/(handle+'_configuration.json')
            or configuration.get('run')!=row.get('run') or closure.get('run')!=row.get('run')
            or Path(configuration['output'])!=expected_output
            or configuration.get('node')!=row.get('node') or closure.get('node')!=row.get('node')
            or configuration.get('gpu_uuid')!=row.get('gpu_uuid')
            or closure.get('gpu_uuid')!=row.get('gpu_uuid')):
        raise ValueError('Exact own failed native task and output binding required')
    expected=task.get('producer',{})
    actual=closure.get('producer',{})
    if (expected.get('uid')!=1278 or any(expected.get(k)!=actual.get(k)
            for k in ('pid','uid','start_ticks')) or not expected.get('pid')
            or not expected.get('start_ticks')):
        raise ValueError('Exact UID/PID/start_ticks required')
    if (closure.get('status')!='FAILED' or closure.get('exit_code') is not None
            or not str(closure.get('error','')).startswith('AdmissionRefused: REFUSED insufficient node_ram:')
            or not closure.get('owned_descendants_exited') or not closure.get('observer_joined')
            or not closure.get('started_at') or not closure.get('ended_at')
            or closure['ended_at']<closure['started_at']
            or not 0<closure.get('peak_RSS_bytes',0)<=128*1024**2):
        raise ValueError('Closed pre-encoder RAM refusal with unobserved exit required')
    if set(files)!= {'complete_state.pt','history.jsonl'}:
        raise ValueError('Existing saved state and training history required')
    for name,value in files.items():
        if (value.get('path')!=str(expected_output/name) or value.get('uid')!=1278
                or value.get('regular') is not True or value.get('size',0)<=0
                or value.get('mtime_ns',0)<=0
                or value['mtime_ns']/1e9>=closure['started_at']):
            raise ValueError('Saved scientific state changed or is not the exact own regular file')
    return dict(policy=POLICY,handle=handle,run=row['run'],producer={k:actual[k]
        for k in ('pid','uid','start_ticks')},standby_job_id=row['standby_job_id'],
        configuration_digest=digest(configuration),closure_digest=digest(closure),
        files=copy.deepcopy(files),actual_native_exit_code=None,exit_code_observed=False)


def require_pending(info,actual,handle,job,held=False):
    if (str(info.get('JobId'))!=str(job) or info.get('UserId')!='zixiao(1278)'
            or info.get('JobName')!=handle or info.get('JobState')!='PENDING'
            or actual!='PENDING|0:0|0' or (held and info.get('Reason')!='JobHeldUser')):
        raise ValueError('Only the exact own zero-work pending standby may be cancelled')


def standby_terminal_action(closure):
    if (not closure.get('ended_at') or not closure.get('owned_descendants_exited')
            or not closure.get('observer_joined')):
        raise ValueError('Native owned exit is not closed')
    if closure.get('exit_code') is None:
        return 'STOP_UNKNOWN_EXIT'
    if closure.get('status')=='COMPLETE' and closure.get('exit_code')==0:
        return 'NO_REPLAY'
    if closure.get('status')=='CONTINUATION_REQUIRED' and closure.get('exit_code')==75:
        return 'RESUME'
    raise ValueError('Native producer did not close at a safe continuation boundary')


def validate_wait_exit(handle,row,wait,actual):
    codes={'WAITING_CONTINUATION_REQUIRED':75,'NATIVE_UNKNOWN_EXIT_NO_FIT_REPLAY':1}
    code=codes.get(wait.get('status'))
    parts=actual.split('|')
    identity=wait.get('producer',{})
    if (code is None or len(parts)!=3 or parts[0]!='FAILED' or parts[1]!=str(code)+':0'
            or not parts[2].isdigit() or wait.get('run')!=row.get('run')
            or wait.get('job_id')!=row.get('standby_job_id') or wait.get('node')!=row.get('node')
            or identity.get('uid')!=1278 or not identity.get('pid') or not identity.get('start_ticks')
            or not wait.get('owned_descendants_exited') or not wait.get('started_at')
            or not wait.get('ended_at') or wait['ended_at']<wait['started_at']):
        raise ValueError('Exact closed wait-only standby and actual terminal status required')
    return dict(standby_wait_policy=WAIT_POLICY,standby_actual=actual,
        standby_wait_record=copy.deepcopy(wait),standby_wait_digest=digest(wait))


def retire_entries(entries,expected,allow_absent=False):
    ids={row['id'] for row in expected}
    present=[row for row in entries if row['id'] in ids]
    if not present and allow_absent:return copy.deepcopy(entries)
    if len(present)!=len(expected) or len({r['id'] for r in present})!=len(expected):
        raise ValueError('Inspect changed or partial resource registrations')
    if {r['id']:r for r in present}!={r['id']:r for r in expected}:
        raise ValueError('Exact own resource registration required')
    return [copy.deepcopy(row) for row in entries if row['id'] not in ids]


def verify_receipt(previous,closure,old,task,files,receipt,control=C):
    handle=Path(previous['configuration']).name.removesuffix('_configuration.json')
    expected=validate_failure(handle,previous,closure,old,task,files,control)
    settled=str(receipt.get('standby_actual','')).startswith('CANCELLED by 1278|0:0|0')
    if not settled:
        wait=receipt.get('standby_wait_record',{})
        proof=validate_wait_exit(handle,previous,wait,receipt.get('standby_actual',''))
        settled=(receipt.get('standby_wait_producer_verified_gone') is True
            and all(receipt.get(k)==v for k,v in proof.items()))
    if (previous.get('status')!=STATUS or not previous.get('resource_closed')
            or receipt.get('status')!='FAILED_STARTUP_OWN_RESOURCES_CLOSED'
            or receipt.get('native_producer_verified_gone') is not True
            or not settled
            or any(receipt.get(k)!=v for k,v in expected.items())):
        raise ValueError('Actual failed-startup settlement is missing or changed')
    return True


def require_retired_startup(previous,closure,old,control=C):
    control=Path(control)
    handle=Path(previous['configuration']).name.removesuffix('_configuration.json')
    path=Path(previous.get('startup_failure_receipt',''))
    if path!=control/(handle+'_startup_failure_settlement.json'):
        raise ValueError('Exact failed-startup settlement receipt required')
    read=lambda p:json.loads(Path(p).read_text())
    receipt=read(path)
    verify_receipt(previous,closure,old,read(previous['native_task']),snapshots(old),receipt,control)
    if set(previous['resource_ids']) & {v['id'] for v in read(control/'storage_additional_entries.json')['entries']}:
        raise ValueError('Old startup resources were not retired')
    return receipt
