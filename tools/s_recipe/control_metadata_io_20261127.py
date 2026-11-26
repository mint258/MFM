"""Future control-file atomic writes and parent-safe short metadata locking."""
import ctypes
import fcntl
import json
import os
from pathlib import Path
import tempfile
from storage_20261122 import CONTROL as C,write as original_write

ATOMIC_TARGETS={C/'current_state.json',C/'storage_additional_entries.json'}
PARENTS=dict(terminal='launch_terminal_statistics_native_20261126.py',
    budget_statistics='launch_budget_statistics_native_20261126.py',
    fullft_statistics='launch_fullft_statistics_native_20261126.py')


def write(path,value):
    path=Path(path)
    if path not in ATOMIC_TARGETS:return original_write(path,value)
    with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,prefix='.'+path.name+'.',
            suffix='.pending',delete=False) as stream:
        stream.write(json.dumps(value,indent=2)+'\n');temporary=Path(stream.name)
    os.replace(temporary,path)


class Flock(ctypes.Structure):
    _fields_=[('type',ctypes.c_short),('whence',ctypes.c_short),
        ('start',ctypes.c_longlong),('length',ctypes.c_longlong),('pid',ctypes.c_int)]


def lock_owner(fd):
    request=Flock(fcntl.F_WRLCK,os.SEEK_SET,0,0,0)
    value=Flock.from_buffer_copy(fcntl.fcntl(fd,fcntl.F_GETLK,bytes(request)))
    return value.pid if value.type!=fcntl.F_UNLCK else None


def trusted_parent(stage,pid):
    if stage not in PARENTS:return False
    expected=str(C/PARENTS[stage])
    ancestor=os.getppid()
    for _ in range(6):
        try:
            directory=Path('/proc')/str(ancestor)
            status=directory.joinpath('status').read_text().splitlines()
            uid=int(next(line for line in status if line.startswith('Uid:')).split()[1])
            args=directory.joinpath('cmdline').read_bytes().decode().split('\0')
            parent=int(next(line for line in status if line.startswith('PPid:')).split()[1])
        except (OSError,ValueError,StopIteration):return False
        if uid!=os.getuid():return False
        if ancestor==pid:return expected in args
        if parent<=1:return False
        ancestor=parent
    return False


def acquire_control_lock(stage,path=C/'execution.lock',*,trusted=trusted_parent):
    """A statistic child reuses its actual owning ancestor's POSIX lock.

    Other callers acquire both lock domains before modifying the forecast.
    Busy lock means no forecast mutation or launch, never a scientific retry.
    """
    lock=Path(path).open('a')
    owner=lock_owner(lock.fileno())
    if owner and trusted(stage,owner):
        lock.close();return None,'INHERITED_VERIFIED_PARENT_CONTROL_LOCK'
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BaseException:
        lock.close();raise
    return lock,'OWN_FLOCK_AND_POSIX_CONTROL_LOCK'
