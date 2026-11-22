"""Opt-in lifecycle for future S jobs; no training or model changes on import.

The entry must install Guard before starting work. Signals request a checkpoint
at a committed optimizer boundary. No SIGKILL, scancel, or node recovery occurs.
"""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import ctypes
import math
import multiprocessing
from multiprocessing import resource_tracker
import os
from pathlib import Path
import signal
import threading
import time
import uuid


class StopAtBoundary(BaseException):
    """Interrupt an await of the next input, never an optimizer update."""


class UncleanExit(RuntimeError):
    pass


@dataclass(frozen=True)
class Identity:
    pid: int
    uid: int
    start_ticks: int
    ppid: int
    state: str


def identity(pid):
    path = Path('/proc')/str(pid)
    try:
        fields = (path/'stat').read_text().rsplit(')', 1)[1].split()
        return Identity(int(pid), path.stat().st_uid, int(fields[19]),
                        int(fields[1]), fields[0])
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None


def same_process(saved, current):
    return (current is not None and saved.pid == current.pid and
            saved.uid == current.uid and saved.start_ticks == current.start_ticks)


def enable_subreaper():
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # Linux PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), 'Cannot manage adopted S children')


def children_of(parent):
    records = {}
    for path in Path('/proc').iterdir():
        if path.name.isdecimal():
            value = identity(int(path.name))
            if value is not None:
                records[value.pid] = value
    selected = {}
    parents = {int(parent)}
    while True:
        extra = {pid: value for pid, value in records.items()
                 if value.ppid in parents and pid not in selected}
        if not extra:
            return selected
        if any(value.uid != os.getuid() for value in extra.values()):
            raise UncleanExit('Unexpected UID in the owned process tree')
        selected.update(extra)
        parents.update(extra)


def reap_adopted():
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return


def terminate_once(saved):
    """TERM only this still-matching, non-D owned child; caller verifies exit."""
    current = identity(saved.pid)
    if not same_process(saved, current):
        return 'already_exited'
    if current.uid != os.getuid() or current.pid == os.getpid():
        raise UncleanExit('Refuse to signal an unowned/self process')
    if current.state == 'D':
        return 'uninterruptible_requires_administrator'
    if current.state == 'Z':
        reap_adopted()
        return 'zombie_reap_requested'
    os.kill(current.pid, signal.SIGTERM)
    return 'term_requested'


def close_children(grace_seconds=180, *, poll_seconds=.1, signalled=None):
    """One TERM per identity, then observe/reap; never infer exit from a batch."""
    if multiprocessing.active_children():
        raise UncleanExit('Join managed multiprocessing workers before final cleanup')
    # The stdlib tracker intentionally ignores TERM. Close its owned pipe and
    # wait/reap through its own lifecycle, after all managed pools have joined.
    tracker = resource_tracker._resource_tracker
    tracker_record = identity(tracker._pid) if tracker._pid else None
    if tracker._pid is not None:
        tracker._stop()
    if tracker_record and same_process(tracker_record, identity(tracker_record.pid)):
        raise UncleanExit('The multiprocessing resource tracker has not exited')
    end = time.monotonic()+grace_seconds
    signalled = set() if signalled is None else signalled
    while True:
        reap_adopted()
        children = children_of(os.getpid())
        if not children:
            return
        for saved in children.values():
            key = (saved.pid, saved.start_ticks)
            if key not in signalled:
                result = terminate_once(saved)
                if result != 'uninterruptible_requires_administrator':
                    signalled.add(key)
        if time.monotonic() >= end:
            detail = [vars(value) for value in children.values()]
            error = UncleanExit('Owned children have not exited: '+repr(detail))
            error.signalled = signalled
            error.identities = children
            raise error
        time.sleep(poll_seconds)


class ManagedPool(ProcessPoolExecutor):
    """Cancel work not yet dispatched and join/reap actual pool workers."""
    def __exit__(self, exc_type, exc_value, traceback):
        records = [identity(p.pid) for p in (self._processes or {}).values()]
        records = [value for value in records if value is not None]
        self.shutdown(wait=True, cancel_futures=True)
        live = [saved for saved in records if same_process(saved, identity(saved.pid))]
        if live:
            raise UncleanExit('Pool shutdown did not reap workers: '+repr(live))
        return False


_ACTIVE = None


def active():
    if _ACTIVE is None:
        raise RuntimeError('The future S lifecycle entry has not installed its guard')
    return _ACTIVE


def pause_checkpoint(configuration, clock, payload_builder, publish, finish):
    """Publish only committed state; reuse a final checkpoint at that boundary."""
    request = active().handoff(configuration)
    path = Path(configuration['output'])/('samples_'+str(clock.samples_consumed)+'.pt')
    if path.exists() and not path.is_file():
        raise ValueError('The checkpoint destination is not a regular file')
    if not path.is_file():
        publish(payload_builder(), path)
    return finish(configuration, request, path, clock.state_dict())


class Guard:
    def __init__(self, end_epoch, closing_seconds=900, *, now=time.time):
        if (not math.isfinite(float(end_epoch)) or closing_seconds < 180 or
                float(end_epoch)-now() <= closing_seconds):
            raise ValueError('A real finite deadline and usable >=180s closing window are required')
        self.end_epoch = float(end_epoch)
        self.closing_seconds = float(closing_seconds)
        self.now = now
        self.phase = 'preparing'
        self.reason = None
        self.request_id = str(uuid.uuid4())
        self._done = threading.Event()
        self._handlers = {}
        self._watcher = None

    @classmethod
    def from_slurm(cls, closing_seconds=900, environment=None, scheduler_record=None):
        env = os.environ if environment is None else environment
        if not str(env.get('SLURM_JOB_ID', '')).isdecimal():
            raise ValueError('A real Slurm job identity is required')
        raw = env.get('SLURM_JOB_END_TIME', '')
        if str(raw).isdecimal():
            guard = cls(int(raw), closing_seconds)
            guard.deadline_basis = 'slurm_environment'
            return guard
        value = scheduler_record
        if not isinstance(value, dict):
            raise ValueError('A login-controller record of the real Slurm time limit is required')
        if (value.get('schema') != 'S_REAL_SLURM_LIMIT_V1' or
                value.get('source') != 'scontrol_show_job_utc' or
                value.get('job_id') != int(env['SLURM_JOB_ID']) or
                value.get('uid') != os.getuid() or
                value.get('node') != env.get('SLURMD_NODENAME') or
                value.get('deadline_basis') not in ('actual_start', 'submit_lower_bound')):
            raise ValueError('The deadline record does not bind this allocation')
        age = time.time()-float(value['observed_time'])
        # A held job's immutable SubmitTime lower bound remains conservative
        # through queueing. Do not reject it merely because startup took >60s.
        # Nodes can differ by a fraction of a second; reserve five extra seconds.
        if age < -5 or (value['deadline_basis'] == 'actual_start' and age > 60):
            raise ValueError('The actual scheduler deadline observation is stale')
        limit = value['time_limit_seconds']
        anchor = value['anchor_epoch']
        if (type(limit) is not int or limit <= closing_seconds or
                not math.isfinite(float(anchor))):
            raise ValueError('A finite actual Slurm time limit is required')
        safety = 5 if value['deadline_basis'] == 'submit_lower_bound' else 0
        guard = cls(float(anchor)+limit-safety, closing_seconds)
        guard.deadline_basis = value['deadline_basis']
        return guard

    def request(self, reason):
        if self.reason is None:
            self.reason = str(reason)

    def _handle(self, number, frame):
        self.request('signal_'+str(number))
        if self.phase == 'waiting_batch':
            raise StopAtBoundary()

    def stopping(self):
        if self.now() >= self.end_epoch-self.closing_seconds:
            self.request('closing_window')
        return self.reason is not None

    def await_next(self):
        self.phase = 'waiting_batch'
        if self.stopping():
            raise StopAtBoundary()

    def handoff(self, configuration):
        return dict(action='SAVE_AND_EXIT', run=configuration['run'],
                    job_id=int(os.environ['SLURM_JOB_ID']),
                    request_id=self.request_id, reason=self.reason,
                    origin='S_lifecycle_20261122')

    def _watch(self):
        while not self._done.wait(.5):
            if self.stopping():
                os.kill(os.getpid(), signal.SIGUSR1)
                return

    def __enter__(self):
        global _ACTIVE
        if _ACTIVE is not None:
            raise RuntimeError('Nested S lifecycle guards are not allowed')
        _ACTIVE = self
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGUSR1):
            self._handlers[number] = signal.signal(number, self._handle)
        self._watcher = threading.Thread(target=self._watch, daemon=False)
        self._watcher.start()
        return self

    def __exit__(self, *exc):
        global _ACTIVE
        self.phase = 'closing'
        self._done.set()
        if self._watcher is not None:
            self._watcher.join()
        for number, handler in self._handlers.items():
            signal.signal(number, handler)
        _ACTIVE = None
        return False
