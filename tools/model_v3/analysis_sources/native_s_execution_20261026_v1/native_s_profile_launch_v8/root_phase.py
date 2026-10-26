"""Explicit Root-invoked finite reservation/feed producer; never runs at import."""
from __future__ import annotations
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import time
from common import *

@contextmanager
def registry_lock(path):
    path=Path(path);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with path.with_suffix(path.suffix+'.lock').open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        yield

def initialize(path):
    root_identity()
    with registry_lock(path):
        return write(path,dict(schema='native_S_Root_registered_reservations_v1',uid=os.getuid(),
            authority='ROOT_ACTUAL',scope='this_profile_lineage_and_explicitly_Root_registered_reservations_only',
            other_agents_or_data_line_unregistered_reservations_known=False,
            actual_account_usage_includes_all_account_files=True,created_unix=time.time(),reservations={}))

def registry_value(path):
    value=read(path)
    require(value['schema']=='native_S_Root_registered_reservations_v1' and value['uid']==os.getuid()
        and value['authority']=='ROOT_ACTUAL' and value['other_agents_or_data_line_unregistered_reservations_known'] is False,
        'Explicit Root registered-reservation scope required')
    for row in value['reservations'].values():
        require(type(row['remaining_bytes']) is int and row['remaining_bytes']>=0,'Invalid outstanding reservation')
        if row.get('principal') is not None:read_ref(row['principal'])
    return value

def actual_quota(filesystem='/dev/sda1'):
    root_identity()
    raw=actual(['quota','-v','-u','zixiao'])
    inode_raw=actual(['df','-P','-i',str(PROJECT)])
    inode_rows=[line.split() for line in inode_raw['stdout'].splitlines()[1:] if line.split()]
    require(len(inode_rows)==1 and inode_rows[0][0]==filesystem,
        'Actual project filesystem differs from native quota filesystem')
    lines=[line.split() for line in raw['stdout'].splitlines() if line.split() and line.split()[0]==filesystem]
    require(len(lines)==1 and len(lines[0])>=4,'Unique known native quota filesystem row required')
    row=lines[0];require(all(re.fullmatch(r'\d+\*?',x) for x in row[1:4]),'Unknown quota numeric KiB fields')
    used,soft,hard=[int(x.rstrip('*'))*1024 for x in row[1:4]]
    limits=[x for x in (soft,hard) if x>0];require(limits and used<min(limits),'Unknown/exhausted account quota')
    fact=os.statvfs(PROJECT);available=fact.f_favail
    tail=[x.rstrip('*') for x in row[4:] if re.fullmatch(r'\d+\*?',x)]
    require(len(tail)>=3,'Actual quota row lacks interpretable inode usage/soft/hard fields')
    inode_used,inode_soft,inode_hard=map(int,tail[-3:]);inode_limits=[x for x in (inode_soft,inode_hard) if x>0]
    if inode_limits:available=min(available,max(0,min(inode_limits)-inode_used))
    now=time.time()
    return dict(raw=raw,inode_command=inode_raw,filesystem=filesystem,free_bytes=min(limits)-used,used_bytes=used,limit_bytes=min(limits),
        inodes=dict(filesystem=filesystem,uid=os.getuid(),captured_unix=now,available=available,
            physical_available=fact.f_favail,native_quota_used=inode_used,native_quota_limits=inode_limits),captured_unix=now)

def reserve(phase,configuration_ref,registry):
    """New3GiB lineage allowance; every actual job still whole2GiB/private2GiB."""
    root_identity();phase=Path(phase);control=phase/'control';control.mkdir(mode=0o700,parents=True,exist_ok=True)
    config=read_ref(configuration_ref);limits=config['long_run_policy'];reservation_id=phase.name
    zeros={key:0 for key in limits['counts']}
    with registry_lock(registry):
        ledger=registry_value(registry);require(reservation_id not in ledger['reservations'],'Reservation ID already consumed')
        quota=actual_quota()
        outstanding=sum(row['remaining_bytes'] for row in ledger['reservations'].values())
        require(quota['free_bytes']-outstanding-(64<<30)>=limits['durable_bytes']
            and quota['inodes']['available']>=limits['inode_limit'],'Account quota cannot cover registered holds + new allowance +64GiB headroom')
        record=write(control/'Root_reservation_record.json',dict(reservation_id=reservation_id,uid=os.getuid(),
            durable_root=str(phase/'ledger'),reserved_additional_bytes=limits['durable_bytes'],initial_counts=zeros,
            authority='ROOT_ACTUAL',phase_ledger_id=reservation_id,registered_ledger=str(Path(registry).absolute()),
            actual_initial_quota=quota,coordinator_pid=os.getpid(),coordinator_hostname=socket.gethostname(),
            durable_scope='lineage_total_only_not_per_job_output_cap',whole_job_output_cap_bytes=OUTER))
        principal=write(control/'principal.json',dict(schema='model_v3_Root_durable_reservation_v1',
            reservation_id=reservation_id,uid=os.getuid(),status='ROOT_COORDINATOR_RESERVED_FINITE',authority='ROOT_ACTUAL',
            policy_sha256=digest(limits),max_bytes=limits['durable_bytes'],counts=limits['counts'],
            science_identity_sha256=digest(config),initial_existing_bytes=0,reserved_additional_bytes=limits['durable_bytes'],
            initial_counts=zeros,Root_reservation_record=record,durable_root=str(phase/'ledger'),filesystem='/dev/sda1'))
        ledger['reservations'][reservation_id]=dict(durable_root=str(phase/'ledger'),principal=principal,
            principal_sha256=principal['sha256'],remaining_bytes=limits['durable_bytes'],phase=str(phase))
        replace_feed(registry,ledger)
    write(control/'initial_roots.json',dict(schema='model_v3_long_run_initial_roots_v1',roots=[
        dict(path=str(control),kind='management',type='directory',must_exist=True)]))
    write(control/'lease.json',dict(reservation_id=reservation_id,authority='ROOT_ACTUAL',
        created_unix=time.time(),expires_unix=time.time()+9000))
    write(control/'quota_descriptor.json',dict(schema='model_v3_Root_quota_feed_descriptor_v1',uid=os.getuid(),
        filesystem='/dev/sda1',authority='ROOT_ACTUAL',producer_source=binding(__file__),feed_path=str(control/'quota_feed.json')))
    publish(phase,registry)
    return principal

def publish(phase,registry):
    root_identity();phase=Path(phase);control=phase/'control'
    with registry_lock(registry):
        ledger=registry_value(registry);principal_ref=binding(control/'principal.json');principal=read_ref(principal_ref)
        own=ledger['reservations'][principal['reservation_id']]
        require(own['principal']==principal_ref,'Registered principal changed')
        quota=actual_quota()
        require(quota['free_bytes']-sum(x['remaining_bytes'] for x in ledger['reservations'].values())>=64<<30,
            'Fresh account usage plus registered holds exhausted conservative headroom')
        reservations={key:dict(durable_root=x['durable_root'],principal_sha256=x['principal_sha256'],remaining_bytes=x['remaining_bytes'])
            for key,x in ledger['reservations'].items()}
        feed=dict(schema='model_v3_Root_live_quota_v1',uid=os.getuid(),host='sonmi',filesystem='/dev/sda1',
            authority='ROOT_ACTUAL',returncode=quota['raw']['returncode'],stdout=quota['raw']['stdout'],
            captured_unix=quota['captured_unix'],inodes=quota['inodes'],producer_source_sha256=binding(__file__)['sha256'],
            phase_ledger_id=principal['reservation_id'],headroom_bytes=64<<30,reservations=reservations,
            actual_command_observation=quota['raw'],Root_registry_snapshot_sha256=digest(ledger))
        feed['actual_inode_command_observation']=quota['inode_command']
        replace_feed(control/'quota_feed.json',feed)
    return binding(control/'quota_feed.json')
