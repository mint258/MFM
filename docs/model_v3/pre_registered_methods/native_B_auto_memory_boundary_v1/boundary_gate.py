"""One finite Root dispatch boundary; never submits, signals or edits old source."""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import time

B=Path('/share/home/zixiao/descriptor_analysis')
N=B/'runs/model_v3_20261026'
PHASE=N/'native_S_B20k_v3'
CONTROL=N/'native_B_remaining_20261029'
SOURCE=CONTROL/'continue_original_B.py'
MAX_JSON=2<<20


def need(ok, message):
    if not ok:
        raise ValueError(message)


def raw(path):
    path=Path(path)
    before=path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid==1278
         and before.st_size<=MAX_JSON, 'Owned small ordinary metadata file required')
    data=path.read_bytes()
    after=path.lstat()
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
         (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns), 'Metadata changed during read')
    return data


def ref(path):
    data=raw(path)
    return dict(path=str(Path(path).absolute()), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def read(path):
    return json.loads(raw(path))


def bound(value):
    need(type(value) is dict and set(value)=={'path','bytes','sha256'}, 'Exact three-field rawref required')
    need(ref(value['path'])==value, 'Bound metadata changed')
    return value


def create(path, value):
    data=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    need(len(data)<=MAX_JSON, 'Small boundary metadata limit exceeded')
    with Path(path).open('xb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    return ref(path)


def status(output, state, **fields):
    data=(json.dumps(dict(schema='native_B_Root_dispatch_boundary_status_v1',
        status=state,observed_unix=time.time(),**fields),sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    need(len(data)<=MAX_JSON, 'Small boundary status required')
    temporary=output/'status.pending'
    with temporary.open('wb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,output/'status.json')


def lock_fd(path):
    before=path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid==1278, 'Existing owned ordinary mutex required')
    fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW)
    actual=os.fstat(fd)
    need((actual.st_dev,actual.st_ino,actual.st_uid)==(before.st_dev,before.st_ino,before.st_uid),
         'Mutex inode changed')
    return fd


def own_identity():
    tail=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    return dict(pid=os.getpid(),uid=os.getuid(),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        start_ticks=int(tail[19]),pgid=os.getpgrp(),sid=os.getsid(0),
        argv_sha256=hashlib.sha256(Path('/proc/self/cmdline').read_bytes()).hexdigest(),source=ref(__file__))


def controller_alive(identity):
    root=Path('/proc')/str(identity['pid'])
    if not root.exists():
        return False
    try:
        need(root.stat().st_uid==identity['uid'], 'Original PID reused or ownership changed; Root reconciliation required')
        tail=(root/'stat').read_text().rsplit(')',1)[1].split()
        need(int(tail[19])==identity['start_ticks'], 'Original PID start identity changed')
        if tail[0]=='Z':
            return True  # Wait for actual disappearance; never signal or treat a zombie as PIDgone.
        need(hashlib.sha256((root/'cmdline').read_bytes()).hexdigest()==identity['argv_sha256']
             and os.getpgid(identity['pid'])==identity['pgid'] and os.getsid(identity['pid'])==identity['sid'],
             'Original PID identity changed; no signal or automatic recovery')
        return True
    except (FileNotFoundError,ProcessLookupError):
        if not root.exists():
            return False
        raise


def phase_snapshot():
    attempts={}
    for path in sorted((PHASE/'control/attempts').glob('slot_*.json')):
        need(re.fullmatch(r'slot_[0-9]{3}\.(intent|submitted)\.json',path.name), 'Unknown attempt metadata shape')
        attempts[path.name]=ref(path)
    leases={}
    for path in sorted((PHASE/'control/leases').glob('*.json')):
        need(re.fullmatch(r'slot_[0-9]{3}(?:\.operational_v[0-9]+)?\.json',path.name), 'Unknown lease filename')
        leases[path.name]=ref(path)
    need(len(attempts)<=216 and len(leases)<=216, 'Original finite phase bounds exceeded')
    return dict(attempts=attempts,leases=leases)


def closed_boundary(snapshot, minimum_slot):
    attempts=snapshot['attempts']
    intents={name[:8] for name in attempts if name.endswith('.intent.json')}
    submitted={name[:8] for name in attempts if name.endswith('.submitted.json')}
    need(intents==submitted and submitted, 'Unresolved intent or no submitted segment')
    rows=[]
    for slot_key in sorted(submitted):
        slot=int(slot_key[5:])
        frame_ref=attempts[slot_key+'.submitted.json'];frame=read(frame_ref['path'])
        need(frame['status']=='SUBMITTED' and frame['slot']==slot and frame['phase']==str(PHASE), 'Submitted frame identity differs')
        closure_path=PHASE/'slots'/slot_key/'management/ROOT_LONG_SEGMENT_CLOSURE.json'
        closure_ref=ref(closure_path);closure=read(closure_path)
        need(closure['submission']==frame_ref, 'Closure binds another submitted frame')
        rows.append(dict(slot=slot,job_id=frame['actual_sbatch_job_id'],submission=frame_ref,closure=closure_ref,
                         closure_status=closure['status']))
    last=rows[-1]
    need(last['slot']>=minimum_slot, 'Boundary precedes explicitly requested running segment')
    closure=read(last['closure']['path'])
    need(closure['status']=='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING' and closure['failure'] is None,
         'Latest segment is failed/unknown; no automatic resource switch')
    terminal=read(bound(closure['actual_terminal'])['path'])
    need(terminal['job_id']==last['job_id'] and terminal['status']=='COMPLETED'
         and terminal['exit_code']==0 and terminal['exit_code_raw']=='0:0', 'Actual C0 terminal projection required')
    supervisor=read(bound(closure['supervisor'])['path'])
    need(str(supervisor['job_id'])==last['job_id'] and supervisor['status']=='COMPLETED'
         and supervisor['exit_code']==0 and supervisor['first_failure'] is None
         and supervisor['remaining_recorded_processes_before_retirement']==[]
         and supervisor['private_storage_cleanup_errors']==[], 'Actual process/private closure required')
    for name in snapshot['leases']:
        need(int(name[5:8])<=last['slot'], 'A future lease already exists; Root reconciliation required')
    return dict(closed_attempts=rows,last=last,latest_slot_was_exact_requested=(last['slot']==minimum_slot),
                no_unresolved_intent=True,no_future_lease=True,scientific_acceptance=False,SDK_audit_claimed=False)


def hold(args):
    need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi' and not os.environ.get('SLURM_JOB_ID'),
         'Original Root login identity required')
    need(1<=args.minimum_slot<=108 and 1<=args.wait_seconds<=9000 and 1<=args.hold_seconds<=3600,
         'Finite boundary bounds required')
    need(ref(__file__)['sha256']==args.source_sha256, 'Explicit reviewed helper SHA required')
    expected=read(CONTROL/'identity.json')
    need(ref(CONTROL/'identity.json')['sha256']==args.controller_identity_sha256
         and expected['pid']==3244560 and expected['uid']==1278
         and expected['source_sha256']==ref(SOURCE)['sha256'], 'Exact existing controller source/identity required')
    need(expected['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'Original boot changed')
    output=args.output.absolute()
    need(output.parent==N and output.name.startswith('native_B_auto_memory_boundary_')
         and not output.exists() and not output.is_symlink(), 'Fresh explicit N-level boundary output required')
    output.mkdir(mode=0o700)
    identity_ref=create(output/'identity.json',own_identity())
    dispatch=None;controller=None;acquired=False
    try:
        status(output,'WAITING_ORIGINAL_EXISTING_DISPATCH_MUTEX',identity=identity_ref,
               original_controller=ref(CONTROL/'identity.json'),fair_order_or_exact_slot_guaranteed=False)
        dispatch=lock_fd(PHASE/'control/.dispatch.lock')
        deadline=time.monotonic()+args.wait_seconds
        while True:
            try:
                fcntl.flock(dispatch,fcntl.LOCK_EX|fcntl.LOCK_NB);acquired=True;break
            except BlockingIOError:
                need(time.monotonic()<deadline, 'Finite existing-mutex wait expired; no submission performed')
                time.sleep(.25)
        before=phase_snapshot()
        boundary=closed_boundary(before,args.minimum_slot)
        status(output,'HOLDING_BOUNDARY_WAITING_ORIGINAL_CONTROLLER_NATURAL_EXIT',identity=identity_ref,boundary=boundary)
        exit_deadline=time.monotonic()+90
        while controller_alive(expected):
            need(time.monotonic()<exit_deadline, 'Old controller did not naturally exit in90s; stop and reconcile')
            time.sleep(.25)
        controller=lock_fd(CONTROL/'controller.lock')
        fcntl.flock(controller,fcntl.LOCK_EX|fcntl.LOCK_NB)
        final_status=read(CONTROL/'status.json')
        need(final_status['identity']==expected and final_status['status'] in (
             'STOPPED_REQUIRES_ROOT_RECONCILIATION_NO_RETRY',
             'FOUR_TRAINING_MEMBERS_COMPLETE_PENDING_SDK_AND_B_CURVE_GATES'), 'Original controller final status unknown')
        need(phase_snapshot()==before, 'Lease/intent/submission changed while boundary mutex held')
        ready=create(output/'BOUNDARY_HELD.json',dict(schema='native_B_Root_dispatch_boundary_held_v1',
            status='ORIGINAL_C0_SEGMENT_CLOSED_CONTROLLER_GONE_NO_NEW_ATTEMPT_MUTEX_HELD',
            authority='ROOT_ACTUAL',identity=identity_ref,original_controller=ref(CONTROL/'identity.json'),
            original_controller_source=ref(SOURCE),original_controller_final_status=ref(CONTROL/'status.json'),
            boundary=boundary,phase_snapshot=before,hold_seconds=args.hold_seconds,
            no_signal_or_submission_performed=True,scientific_acceptance=False))
        status(output,'BOUNDARY_HELD_PENDING_ROOT_EXPLICIT_RELEASE',identity=identity_ref,boundary_receipt=ready)
        release_deadline=time.monotonic()+args.hold_seconds
        while not (output/'RELEASE.json').exists():
            need(time.monotonic()<release_deadline, 'Finite boundary hold expired; original controller remains stopped')
            need(phase_snapshot()==before, 'Phase attempts changed while held; Root reconciliation required')
            time.sleep(1)
        release=read(output/'RELEASE.json')
        need(release['schema']=='native_B_Root_dispatch_boundary_release_v1'
             and release['authority']=='ROOT_ACTUAL' and release['boundary_receipt']==ready,
             'Root release must bind this exact held boundary')
        for key in ('new_operations_source_pins','new_operations_adoption','method_publication'):
            bound(release[key])
        need(phase_snapshot()==before and not Path('/proc/3244560').exists(), 'Boundary changed before explicit release')
        create(output/'RELEASE_ACTUAL.json',dict(status='ROOT_EXPLICIT_RELEASE_NO_SUBMISSION',
            boundary_receipt=ready,release_request=ref(output/'RELEASE.json'),
            metadata_refs_only_not_validation_of_new_operations=True,no_submission_performed=True))
        status(output,'ROOT_EXPLICITLY_RELEASED_READY_FOR_SEPARATE_ROOT_SUBMIT',identity=identity_ref)
    except BaseException as error:
        status(output,'BOUNDARY_FAILED_REQUIRES_ROOT_RECONCILIATION_NO_RETRY',identity=identity_ref,
               error=dict(type=type(error).__name__,message=str(error)),dispatch_mutex_was_acquired=acquired,
               no_signal_or_submission_performed=True)
        raise
    finally:
        if controller is not None:os.close(controller)
        if dispatch is not None:os.close(dispatch)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-sha256',required=True)
    parser.add_argument('--controller-identity-sha256',required=True)
    parser.add_argument('--minimum-slot',type=int,default=26)
    parser.add_argument('--wait-seconds',type=int,default=9000)
    parser.add_argument('--hold-seconds',type=int,default=3600)
    hold(parser.parse_args())


if __name__=='__main__':main()
