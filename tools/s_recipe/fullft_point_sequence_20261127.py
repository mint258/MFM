"""Finite foreground orchestration for one already registered full-FT point.

Only lightweight controller/accounting metadata runs on the login host. The
existing controllers retain all GPU admission, scientific and exit contracts.
No daemon, retry policy, scientific decision or legacy dispatcher is enabled.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import time

from controller_sequence_20261127 import advance,invoke
from storage_20261122 import CONTROL as C, write

def read(path):
    for retry in range(4):
        try:return json.loads(Path(path).read_text())
        except json.JSONDecodeError:
            if retry==3:raise
            time.sleep(.1)


def point_only_advance(role,handle,node,uuid,*,point,allowed_runs,control=invoke,load=read):
    """Finish only this registered point, leaving the next point for priority."""
    row=load(C/'execution.json')['statistics'][handle]
    if (role!='fullft' or row.get('point')!=point or row.get('run') not in allowed_runs
            or row.get('node')!=node or row.get('gpu_uuid')!=uuid):
        raise ValueError('Exact owned same-point controller required')
    settled=control('close_fullft_resources_20261126.py',handle)
    if settled.get('status')!='OWN_RESOURCES_CLOSED' or settled.get('exit_code')!=0:
        return dict(status='WAITING_ACTUAL_POINT_SETTLEMENT',result=settled)
    ledger=load(C/'execution.json')['statistics']
    selected=None
    for run in allowed_runs:
        attempts=[r for r in ledger.values() if r.get('run')==run
            and r.get('mode') in ('finetune','finetune_native')]
        if not attempts:selected=run;break
        latest=max(attempts,key=lambda r:r.get('released_at',0))
        if latest.get('resource_closed') and latest.get('status')=='COMPLETE':continue
        return dict(status='WAITING_EXACT_SAME_POINT_FIT_OR_ROOT_REPAIR',run=run)
    if selected is None:
        following=dict(status='NO_FOLLOWING_POINT_SUBMITTED',completed_point=point)
    else:
        control('observe_S_gpu_slots_20261122.py')
        following=control('launch_fullft_20261124.py',node,uuid,'--run',selected)
    return dict(status='EXPLICIT_CONTROLLER_SEQUENCE_RETURNED',completed_handle=handle,
        next_controller_result=following)


def completed(row, closure, accounting):
    """A running allocation's provisional 0:0 must never release new work."""
    if row.get('job_id'):
        actual=accounting(row['job_id'])
        if actual!='COMPLETED|0:0':
            if actual.split('|')[0] in ('FAILED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY','CANCELLED'):
                raise ValueError('Inspect the failed actual allocation; no automatic repair/retry')
            return False
    return (closure.get('status')=='COMPLETE' and closure.get('exit_code')==0
        and closure.get('owned_descendants_exited') is True
        and closure.get('observer_joined') is True and bool(closure.get('ended_at')))


def sequence(point, handle, node, uuid, allowed_runs, *, load=read, control=advance,
             accounting=None, now=time.monotonic, sleep=time.sleep, emit=lambda value:None,
             wait_seconds=7200):
    if len(allowed_runs)!=12 or len(set(allowed_runs))!=12 or not 60<=wait_seconds<=8*3600:
        raise ValueError('Exactly one registered twelve-fit point and finite wait required')
    started=now()
    seen=set()
    for _ in range(12):
        while True:
            row=load(C/'execution.json')['statistics'][handle]
            if (row.get('point')!=point or row.get('run') not in allowed_runs
                    or row.get('node')!=node or row.get('gpu_uuid')!=uuid
                    or row.get('mode') not in ('finetune','finetune_native')
                    or row['run'] in seen):
                raise ValueError('Sequence identity changed; inspect before any mutation')
            if now()-started>=wait_seconds:
                return dict(status='FINITE_WAIT_ENDED_WITHOUT_CANCELLING_WORK',point=point,
                    active_handle=handle,closed_fits=len(seen))
            path=Path(row['lifecycle_record'])
            try: closure=load(path)
            except FileNotFoundError: closure={}
            if completed(row,closure,accounting):break
            sleep(10)
        result=control('fullft',handle,node,uuid)
        if result.get('status')!='EXPLICIT_CONTROLLER_SEQUENCE_RETURNED':
            return dict(status='CONTROLLER_REQUIRES_INSPECTION',point=point,handle=handle,result=result)
        seen.add(row['run'])
        following=result['next_controller_result']
        emit(dict(status='CLOSED_FIT_AND_RETURNED_NEXT_CONTROLLER',point=point,
            completed_run=row['run'],next_point=following.get('point'),next_run=following.get('run')))
        if following.get('point')!=point:
            return dict(status='POINT_SEQUENCE_ENDED',point=point,closed_fits=len(seen),
                next_controller_result=following,
                point_statistics='Not run by this foreground sequence; root must validate and launch once')
        handle=Path(following['configuration']).name.removesuffix('_configuration.json')
    raise ValueError('Twelve-fit bound reached with another same-point task; inspect registered plan')


def main():
    parser=argparse.ArgumentParser()
    for name in ('point','handle','node','gpu_uuid','receipt'):parser.add_argument(name)
    parser.add_argument('--wait-seconds',type=int,default=7200)
    parser.add_argument('--point-only',action='store_true')
    args=parser.parse_args()
    if (os.getuid()!=1278 or not all(re.fullmatch(r'S_[A-Za-z0-9_]+',value)
            for value in (args.point,args.handle,args.receipt))):
        raise ValueError('Explicit own registered identities required')
    proof=read(C/'fullft_point_sequence_check_20261127.json')
    parent=read(proof['native_record'])
    command=read(Path(proof['native_record']).with_name('command_exit.json'))
    if (proof.get('status')!='COMPLETE' or proof.get('new_tests')!=3
            or parent.get('status')!='COMPLETE' or parent.get('exit_code')!=0
            or command.get('exit_code')!=0 or not parent.get('owned_descendants_exited')
            or not parent.get('observer_joined')):
        raise ValueError('New foreground boundary checks must actually close first')
    if not re.fullmatch(r'GPU-[a-fA-F0-9-]+',args.gpu_uuid):
        raise ValueError('Exact target UUID required')
    lock=(C/('foreground_fullft_sequence_'+args.gpu_uuid+'.lock')).open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    cells=[r['run'] for r in read(C/'finetune_plan_20261124.json')['cells'] if r['point']==args.point]
    if args.point_only:
        check=read(C/'point_only_sequence_check_20261127.json')
        parent=read(check['native_record'])
        command=read(Path(check['native_record']).with_name('command_exit.json'))
        if (check.get('new_tests')!=2 or parent.get('status')!='COMPLETE' or parent.get('exit_code')!=0
                or command.get('exit_code')!=0 or not parent.get('owned_descendants_exited')
                or not parent.get('observer_joined')):
            raise ValueError('New same-point priority boundaries must actually close first')
    receipt=C/(args.receipt+'.json')
    if receipt.exists():raise ValueError('Inspect existing finite sequence; no duplicate control process')
    from lifecycle_20261122 import identity
    started=time.time()
    base=dict(point=args.point,initial_handle=args.handle,node=args.node,gpu_uuid=args.gpu_uuid,
        producer=vars(identity(os.getpid())),started_at=started,
        orchestration_only=True,background_daemon=False,legacy_dispatch_enabled=False,
        point_only=args.point_only)
    def emit(value):
        write(receipt,dict(base,**value,observed_time=time.time()))
        print(json.dumps(value),flush=True)
    def accounting(job):
        return subprocess.check_output(['/usr/bin/timeout','15s','/usr/bin/sacct','-X','-n','-P',
            '-j',str(job),'--format=State,ExitCode'],text=True).strip()
    emit(dict(status='FINITE_FOREGROUND_SEQUENCE_RUNNING'))
    try:
        controller=(lambda role,handle,node,uuid:point_only_advance(role,handle,node,uuid,
            point=args.point,allowed_runs=cells)) if args.point_only else advance
        result=sequence(args.point,args.handle,args.node,args.gpu_uuid,cells,
            accounting=accounting,control=controller,emit=emit,wait_seconds=args.wait_seconds)
    except BaseException as error:
        emit(dict(status='CONTROLLER_ERROR_NO_AUTOMATIC_RETRY',error=repr(error),ended_at=time.time()))
        raise
    emit(dict(**result,ended_at=time.time()))


if __name__=='__main__':main()
