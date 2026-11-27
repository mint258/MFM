"""Opt-in fullFT runtime accounting of already committed own anonymous RAM.

Startup admission, the shared guard and every registered peak stay unchanged.
Only this fit's current process Pss_Anon can reduce its remaining future need;
no pretraining, peer, file-backed, shared-memory or child RSS is credited.
"""
import json
import os
from pathlib import Path
import socket
import time

POLICY = 'S_FULLFT_SELF_ANON_REMAINING_RAM_20261127_V1'


def validate_policy(configuration):
    if configuration.get('runtime_ram_accounting') not in (None, POLICY):
        raise ValueError('Unknown fullFT runtime RAM accounting policy')


def anonymous_pss(text):
    values={}
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0] in ('Pss_Anon:','LazyFree:'):
            if len(fields) != 3 or fields[2] != 'kB':
                return None
            try:
                value = int(fields[1])
            except ValueError:
                return None
            if value < 0:return None
            values[fields[0]]=value*1024
    if set(values)!= {'Pss_Anon:','LazyFree:'}:return None
    return max(0,values['Pss_Anon:']-values['LazyFree:'])


def self_sample(producer, peak):
    import lifecycle_20261122 as life
    expected = life.Identity(**producer)
    if os.getuid() != 1278 or expected.uid != 1278 or expected.pid != os.getpid():
        raise ValueError('Credit only this exact owned fullFT process')
    if not life.same_process(expected, life.identity(os.getpid())):
        raise ValueError('The fullFT producer identity changed')
    try:
        values = [anonymous_pss(Path('/proc/self/smaps_rollup').read_text()) for _ in range(2)]
    except OSError:
        values = [None]
    if not life.same_process(expected, life.identity(os.getpid())):
        raise ValueError('The fullFT producer identity changed during observation')
    supported = all(value is not None and value <= peak for value in values)
    return dict(credit_bytes=min(values) if supported else 0,
        reason='OWN_PSS_ANON_ONLY' if supported else 'UNSUPPORTED_OR_ABOVE_PEAK_NO_CREDIT',
        observed_time=time.time(), producer={key:producer[key] for key in ('pid','uid','start_ticks')},
        measurement='Pss_Anon minus all LazyFree; file, shmem and other processes excluded')


def remaining_ram_check(total_peak, fit_peak, sample, check):
    """The full registered fit peak includes RAM already charged to MemAvailable."""
    if not 0 < fit_peak <= total_peak:
        raise ValueError('The full registered phase peak must remain covered')
    first = sample()
    credit = first['credit_bytes']
    if not 0 <= credit <= fit_peak:
        raise ValueError('Resident credit exceeds this fit reservation')
    observations = [first]
    for _ in range(3):
        report = check(total_peak-credit)
        last = sample()
        if not 0 <= last['credit_bytes'] <= fit_peak:
            raise ValueError('Invalid resident observation')
        observations.append(last)
        smaller = min(credit, last['credit_bytes'])
        if smaller == credit:
            return report, dict(policy=POLICY, registered_S_peak_bytes=total_peak,
                this_fit_peak_bytes=fit_peak, committed_own_anon_bytes=credit,
                remaining_S_bytes=total_peak-credit, observations=observations,
                startup_and_peer_pretraining_reservations_unchanged=True)
        credit = smaller
    # Rapidly declining residency cannot justify a credit. Use the original
    # full requirement, retaining its refusal behavior and all reserves.
    return check(total_peak), dict(policy=POLICY, registered_S_peak_bytes=total_peak,
        this_fit_peak_bytes=fit_peak, committed_own_anon_bytes=0,
        remaining_S_bytes=total_peak, observations=observations,
        reason='UNSTABLE_RESIDENCY_ORIGINAL_FULL_REQUIREMENT',
        startup_and_peer_pretraining_reservations_unchanged=True)


def admit_runtime(configuration, producer):
    validate_policy(configuration)
    import storage_line_20261122 as line
    if configuration.get('runtime_ram_accounting') is None:
        return line.admit(configuration)
    storage = line.storage
    guard = storage.shared_guard
    future = storage.claim_current()
    node = socket.gethostname().split('.')[0]
    if node != configuration['node']:
        raise ValueError('Observe RAM on the actual fullFT node')
    own = json.loads((guard.REGISTRY/'s-recipe.json').read_text())
    paths = guard._same_device('node_disk', '/')
    root, ram = line.requirements(own['entries'], node, paths)
    peak = configuration['peak_ram_bytes']
    if root < 16*1024**2 or ram < peak:
        raise guard.AdmissionRefused('No sufficient full registered local/RAM future')
    bound=[row for row in own['entries'] if row.get('id')==configuration.get('runtime_ram_reservation_id')
        and row.get('kind')=='node_ram' and row.get('node')==node and row.get('bytes')==peak]
    if len(bound)!=1:
        raise guard.AdmissionRefused('No exact current-fit full RAM reservation; do not borrow another phase')
    quota = json.loads((storage.ROOT/'runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json').read_text())
    if (quota['uid'] != os.getuid() or quota['filesystem'] != '/share'
            or not 0 <= time.time()-quota['observed_time'] <= 5):
        raise guard.AdmissionRefused('No fresh matching UID quota observation')
    # Preserve the exact original physical disk/inode/UID/peer checks.
    reports = dict(root=guard.check_with_timeout('s-recipe','node_disk',root,path='/',new_inodes=1000),
        shared=guard.check_with_timeout('s-recipe','shared_fs',future,path='/share',new_inodes=20000,
            quota_available=quota['available_bytes']))
    reports['ram'], reports['runtime_RAM_accounting'] = remaining_ram_check(ram, peak,
        lambda:self_sample(producer, peak),
        lambda need:guard.check_with_timeout('s-recipe','node_ram',need))
    return reports
