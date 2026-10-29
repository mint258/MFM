"""Root-only typed quota-budget projection; no registry mutation or ledger invention."""
from __future__ import annotations
from copy import deepcopy
import math
import re
from pathlib import Path
import time
from long_common import *

ONE_JOB='model_v3_Root_one_job_output_reservation_v1'
DURABLE='model_v3_Root_durable_reservation_v1'
HISTORICAL_PHASE='model_v3_Root_geometry_head_moment_passive_output_reservation_v1'
OCCUPANCY_KEYS={'intent','submitted','script','slot_root'}


def integer(value,label):
    require(type(value) is int and value>=0,'Nonnegative integer required: '+label)
    return value


def project_path(value,label):
    require(type(value) is str and Path(value).is_absolute() and '..' not in Path(value).parts
        and Path(value).is_relative_to(PROJECT),'Actual project phase/root label required: '+label)
    return value


def reservation_projection(ledger,own_id,own_ref,principal_reader):
    """Pure projection. Live publish always supplies original owned read_ref.

    Unit tests may supply a closed synthetic metadata table, never live quota
    or scientific authority. No input dict is mutated; no root is created.
    """
    require(ledger['schema']=='native_S_Root_registered_reservations_v1'
        and ledger['authority']=='ROOT_ACTUAL' and ledger['uid']==1278
        and ledger['other_agents_or_data_line_unregistered_reservations_known'] is False,
        'Original Root registry authority/scope differs')
    records=ledger['reservations']
    require(type(records) is dict and own_id in records and records,'Own registered Native entry required')
    result={};phase_ids=[];durable_ids=[]
    for key,row in records.items():
        require(type(key) is str and key and type(row) is dict,'Typed reservation row required')
        amount=integer(row['remaining_bytes'],'remaining '+key)
        ref=row['principal']
        require(type(ref) is dict and set(ref)=={'path','bytes','sha256'}
            and type(ref['bytes']) is int and ref['bytes']>=0
            and type(ref['sha256']) is str and re.fullmatch('[0-9a-f]{64}',ref['sha256'])
            and row['principal_sha256']==ref['sha256'],'Reservation principal raw SHA differs')
        principal=principal_reader(ref)
        require(type(principal) is dict and principal['uid']==1278,'Registered principal UID differs')
        phase=project_path(row['phase'],'phase '+key)
        schema=principal['schema']
        projected=dict(principal_sha256=row['principal_sha256'],remaining_bytes=amount)
        if schema==DURABLE:
            require('durable_root' in row and 'durable_root' in principal,
                'A Native durable principal cannot fall back to phase')
            require(principal['authority']=='ROOT_ACTUAL' and principal['reservation_id']==key
                and principal['filesystem']=='/dev/sda1','Actual Native durable principal differs')
            durable=project_path(row['durable_root'],'durable '+key)
            require(durable==principal['durable_root'] and Path(durable).parent==Path(phase),
                'Native durable root/principal/phase differs')
            require(amount<=integer(principal['reserved_additional_bytes'],'Native allowance'),
                'Native remaining exceeds original registered allowance')
            projected['durable_root']=durable;durable_ids.append(key)
        elif schema==ONE_JOB:
            require('durable_root' not in row and 'durable_root' not in principal
                and principal['authority']=='ROOT_ACTUAL' and principal['reservation_id']==key
                and principal['filesystem']=='/dev/sda1' and principal['phase']==phase
                and principal['max_bytes']==principal['reserved_additional_bytes']==OUTER
                and amount<=OUTER,'One-job phase principal/root/allowance differs')
            if key!='native_S10000_seed0_fp32_dev9_v2':
                # The sixteen standard ONE_JOB principals retain their original gates.
                require('initial_existing_bytes' in principal and 'scientific_acceptance' in principal
                    and principal['initial_existing_bytes']==0 and principal['scientific_acceptance'] is False,
                    'Standard one-job initial/science declaration differs')
                semantics='PHASE_OUTPUT_BUDGET_NOT_NATIVE_LEDGER'
            else:
                # One real, already-closed historical panel did not declare these
                # two standard fields. This is not a fallback for an active hold.
                require('initial_existing_bytes' not in principal and 'scientific_acceptance' not in principal
                    and key=='native_S10000_seed0_fp32_dev9_v2'
                    and phase==str(N/'Native_S10000_seed0_fp32_dev9_v2/panel') and amount==0
                    and all(type(principal.get(name)) is int and principal[name]==OUTER
                        for name in ('max_bytes','reserved_additional_bytes','whole_output_bytes'))
                    and principal.get('physical_2GiB_file_allocation_claimed') is False
                    and principal.get('preparation_bytes_already_accounted_in_live_quota') is True
                    and principal.get('private_storage_independently_guarded') is True
                    and type(principal.get('actual_unix')) in (int,float)
                    and math.isfinite(principal['actual_unix']) and principal['actual_unix']>0,
                    'Unknown, nonzero or altered historical one-job panel principal')
                semantics='CLOSED_HISTORICAL_PANEL_BUDGET_NOT_NATIVE_LEDGER'
            projected.update(phase=phase,root_semantics=semantics)
            phase_ids.append(key)
        elif schema==HISTORICAL_PHASE:
            # This one already-closed historical schema never declared a Native
            # ledger, authority/id fields, or a positive additional hold.
            require(key=='geometry_head_moment_passive_v1' and amount==0
                and 'durable_root' not in row and 'durable_root' not in principal
                and principal['phase']==phase and principal['whole_output_budget_bytes']==OUTER
                and principal['private_budget_bytes']==PRIVATE,
                'Unknown or nonzero historical phase-only principal')
            projected.update(phase=phase,root_semantics='CLOSED_HISTORICAL_PHASE_BUDGET_NOT_NATIVE_LEDGER')
            phase_ids.append(key)
        else:raise ValueError('Unknown reservation principal schema: '+str(schema))
        if key==own_id:
            require(schema==DURABLE and ref==own_ref,'Own Native principal cannot use a phase fallback')
        result[key]=projected
    before=sum(row['remaining_bytes'] for row in records.values())
    after=sum(row['remaining_bytes'] for row in result.values())
    require(set(result)==set(records) and before==after,'Reservation population or total hold changed')
    return result,dict(schema='native_S_quota_budget_projection_v7',original_reservation_count=len(records),
        projected_reservation_count=len(result),remaining_total_before_bytes=before,
        remaining_total_after_bytes=after,phase_budget_ids=sorted(phase_ids),
        true_durable_ids=sorted(durable_ids),zero_rows_retained=True,
        foreign_phase_roots_are_not_ledgers=True,original_registry_not_modified=True)


def ensure_descriptor(phase):
    root_identity();phase=Path(phase);control=phase/'control'
    expected=dict(schema='model_v3_Root_quota_feed_descriptor_v1',uid=os.getuid(),filesystem='/dev/sda1',
        authority='ROOT_ACTUAL',producer_source=binding(__file__),feed_path=str(control/'quota_feed_v8.json'))
    path=control/'quota_descriptor_v8.json'
    if path.exists():require(read(path)==expected,'Existing v7 descriptor differs')
    else:write(path,expected)
    return binding(path)


def publish(phase,registry,descriptor_ref):
    root_identity();import root_phase
    phase=Path(phase);control=phase/'control'
    require(descriptor_ref==binding(control/'quota_descriptor_v8.json'),'Exact new descriptor required')
    descriptor=read_ref(descriptor_ref)
    require(descriptor['schema']=='model_v3_Root_quota_feed_descriptor_v1'
        and descriptor['producer_source']==binding(__file__)
        and descriptor['feed_path']==str(control/'quota_feed_v8.json')
        and descriptor['uid']==os.getuid() and descriptor['filesystem']=='/dev/sda1'
        and descriptor['authority']=='ROOT_ACTUAL','Actual new quota producer binding differs')
    with root_phase.registry_lock(registry):
        ledger=root_phase.registry_value(registry);original=deepcopy(ledger)
        principal_ref=binding(control/'principal.json');principal=read_ref(principal_ref)
        require(ledger['reservations'][principal['reservation_id']]['principal']==principal_ref,
            'Original own Native principal changed')
        reservations,projection=reservation_projection(ledger,principal['reservation_id'],principal_ref,read_ref)
        original_registry_ref=binding(registry)
        quota=root_phase.actual_quota()
        require(quota['free_bytes']-sum(x['remaining_bytes'] for x in reservations.values())>=64<<30,
            'Fresh account usage plus all registered holds exhausted conservative headroom')
        require(ledger==original,'Projection mutated actual Root registry records')
        feed=dict(schema='model_v3_Root_live_quota_v1',uid=os.getuid(),host='sonmi',filesystem='/dev/sda1',
            authority='ROOT_ACTUAL',returncode=quota['raw']['returncode'],stdout=quota['raw']['stdout'],
            captured_unix=quota['captured_unix'],inodes=quota['inodes'],producer_source_sha256=binding(__file__)['sha256'],
            phase_ledger_id=principal['reservation_id'],headroom_bytes=64<<30,reservations=reservations,
            actual_command_observation=quota['raw'],actual_inode_command_observation=quota['inode_command'],
            Root_registry_snapshot_sha256=digest(ledger),Root_registry_raw_reference=original_registry_ref,
            reservation_projection=projection,reservation_projection_sha256=digest(reservations))
        require(binding(registry)==original_registry_ref,'Registry changed during locked quota publication')
        replace_feed(control/'quota_feed_v8.json',feed)
    return binding(control/'quota_feed_v8.json')


def lease_decision(existing,*,reservation_id,slot,now,occupied,orphan_authorized):
    """No Slurm/no writes: reject any ambiguous slot; reuse only valid old019."""
    require(type(slot) is int and 1<=slot<=108 and type(occupied) is dict
        and set(occupied)==OCCUPANCY_KEYS and all(type(v) is bool for v in occupied.values()),
        'Exact prelaunch slot occupancy evidence required')
    require(not any(occupied.values()),'Existing intent/submission/script/slot makes retry ambiguous')
    if existing is None:return 'FRESH_V8_PATH'
    require(slot==19 and orphan_authorized is True,'Only explicitly reconciled orphan019 may be reused')
    require(existing['reservation_id']==reservation_id and existing['authority']=='ROOT_ACTUAL'
        and all(type(existing[key]) in (int,float) and math.isfinite(existing[key])
                for key in ('created_unix','expires_unix'))
        and existing['created_unix']<=now and existing['expires_unix']>existing['created_unix'],
        'Original lease identity/time differs')
    return 'REUSE_EXACT_ORIGINAL' if existing['expires_unix']-now>=SLURM_SECONDS else 'FRESH_V8_PATH'


def prepare_lease(phase,slot,adoption):
    root_identity();phase=Path(phase)
    old=phase/'control/leases'/f'slot_{slot:03d}.json'
    record=binding(old) if old.exists() else None
    existing=read_ref(record) if record else None
    occupancy=dict(intent=(phase/'control/attempts'/f'slot_{slot:03d}.intent.json').exists(),
        submitted=(phase/'control/attempts'/f'slot_{slot:03d}.submitted.json').exists(),
        script=(OLD/(phase.name+f'_slot_{slot:03d}.sbatch')).exists(),
        slot_root=slot_layout(phase,slot)['root'].exists())
    if slot==19:
        require(not (phase/'control/leases/slot_019.operational_v5.json').exists(),
            'Unexpected failed-v5 fresh lease requires Root reconciliation')
        require(not (phase/'control/leases/slot_019.operational_v6.json').exists(),
            'Unexpected failed-v6 fresh lease requires Root reconciliation')
    orphan=adoption['orphan_prelaunch']
    authorized=(slot==19 and orphan['slot']==19 and record==orphan['lease']
        and orphan['source_failure_before_sbatch'] is True)
    if record:
        require(authorized and not Path('/proc/'+str(orphan['coordinator_pid'])).exists(),
            'Original coordinator is present or orphan lease differs; Root must reconcile')
    decision=lease_decision(existing,reservation_id=phase.name,slot=slot,now=time.time(),
        occupied=occupancy,orphan_authorized=authorized)
    if decision=='REUSE_EXACT_ORIGINAL':return record
    path=phase/'control/leases'/f'slot_{slot:03d}.operational_v8.json'
    require(not path.exists(),'Existing v7 lease requires Root reconciliation; never overwrite or autoretry')
    now=time.time()
    return write(path,dict(reservation_id=phase.name,authority='ROOT_ACTUAL',created_unix=now,expires_unix=now+9000))
