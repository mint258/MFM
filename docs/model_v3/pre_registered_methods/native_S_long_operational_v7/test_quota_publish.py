"""Closed synthetic metadata mechanisms only; no quota/Slurm/model calls."""
from copy import deepcopy
from pathlib import Path
import pytest
import long_common as c
from quota_publish import reservation_projection,lease_decision,ONE_JOB,DURABLE,HISTORICAL_PHASE


def registry23():
    # Exactly the current population shape and observed hold amounts, but all
    # refs are explicit synthetic fixtures and are never read as live authority.
    own='native_S_B20k_v3';rows={};principals={}
    native=[(own,133741589242,128<<30),('native_S_profile_fp32_v6',3<<30,3<<30),
        ('native_S_profile_fp32_v7',3<<30,3<<30),('native_S_profile_fp32_v8',0,3<<30),
        ('native_S_profile_bf16_v8',0,3<<30)]
    phase_ids=['ffn_fp32_e2e_v1','ffn_fp32_e2e_v2','geometry_head_moment_passive_v1',
        'native_S10000_seed0_fp32_dev9_v2','performance_A5_R2_v1','performance_auto_R2_v1',
        *['performance_head_off_R1_ABBA_v2_member_%d'%i for i in range(1,5)],
        'performance_head_off_R2_v1',*['performance_manual_R1_ABBA_v1_member_%d'%i for i in range(1,5)],
        'performance_manual_R2_4090_v1','performance_manual_R2_v1','performance_native_max_R1_v2']
    for index,(key,amount,cap) in enumerate(native+[(key,2<<30 if key=='performance_manual_R2_4090_v1' else 0,2<<30) for key in phase_ids]):
        phase=str(c.N/'Native_S10000_seed0_fp32_dev9_v2/panel') if key=='native_S10000_seed0_fp32_dev9_v2' else str(c.N/key)
        sha=('%064x'%(index+1));ref=dict(path=phase+'/control/principal.json',bytes=1,sha256=sha)
        row=dict(phase=phase,principal=ref,principal_sha256=sha,remaining_bytes=amount)
        if index<5:
            row['durable_root']=phase+'/ledger'
            principal=dict(schema=DURABLE,uid=1278,authority='ROOT_ACTUAL',filesystem='/dev/sda1',
                reservation_id=key,durable_root=row['durable_root'],reserved_additional_bytes=cap)
        elif key=='geometry_head_moment_passive_v1':
            principal=dict(schema=HISTORICAL_PHASE,uid=1278,phase=phase,
                whole_output_budget_bytes=2<<30,private_budget_bytes=2<<30)
        elif key=='native_S10000_seed0_fp32_dev9_v2':
            # Actual historical field shape; fixture refs remain synthetic.
            principal=dict(schema=ONE_JOB,uid=1278,authority='ROOT_ACTUAL',filesystem='/dev/sda1',
                reservation_id=key,phase=phase,max_bytes=2<<30,reserved_additional_bytes=2<<30,
                whole_output_bytes=2<<30,physical_2GiB_file_allocation_claimed=False,
                preparation_bytes_already_accounted_in_live_quota=True,
                private_storage_independently_guarded=True,actual_unix=1793220000.)
        else:
            principal=dict(schema=ONE_JOB,uid=1278,authority='ROOT_ACTUAL',filesystem='/dev/sda1',
                reservation_id=key,phase=phase,max_bytes=2<<30,reserved_additional_bytes=2<<30,
                initial_existing_bytes=0,scientific_acceptance=False)
        rows[key]=row;principals[sha]=principal
    ledger=dict(schema='native_S_Root_registered_reservations_v1',uid=1278,authority='ROOT_ACTUAL',
        other_agents_or_data_line_unregistered_reservations_known=False,reservations=rows)
    return ledger,own,rows[own]['principal'],principals


def test_all23_projection_preserves_every_hold_and17_zero_phase_histories_without_ledger_invention():
    ledger,own,ref,principals=registry23();before=deepcopy(ledger)
    rows,receipt=reservation_projection(ledger,own,ref,lambda value:principals[value['sha256']])
    assert ledger==before and len(rows)==23 and set(rows)==set(ledger['reservations'])
    assert sum(row['remaining_bytes'] for row in rows.values())==142331523834
    assert receipt['remaining_total_before_bytes']==receipt['remaining_total_after_bytes']==142331523834
    assert rows['performance_manual_R2_4090_v1']['remaining_bytes']==2147483648
    assert len(receipt['phase_budget_ids'])==18 and len(receipt['true_durable_ids'])==5
    assert sum(rows[key]['remaining_bytes']==0 for key in receipt['phase_budget_ids'])==17
    assert all('durable_root' not in rows[key] and rows[key]['phase']==ledger['reservations'][key]['phase']
               for key in receipt['phase_budget_ids'])
    assert rows[own]['durable_root']==ledger['reservations'][own]['durable_root']
    assert all(rows[key]['principal_sha256']==ledger['reservations'][key]['principal_sha256'] for key in rows)


@pytest.mark.parametrize('bad',['unknown_schema','phase_mismatch','principal_sha','own_missing_root','invented_foreign_root'])
def test_unknown_principal_or_root_mismatch_never_filters_or_defaults_a_hold(bad):
    ledger,own,ref,principals=registry23();key='performance_manual_R2_4090_v1';row=ledger['reservations'][key]
    if bad=='unknown_schema':principals[row['principal']['sha256']]['schema']='UNKNOWN'
    elif bad=='phase_mismatch':principals[row['principal']['sha256']]['phase']=str(c.N/'another')
    elif bad=='principal_sha':row['principal_sha256']='f'*64
    elif bad=='own_missing_root':del ledger['reservations'][own]['durable_root']
    else:row['durable_root']=row['phase']+'/ledger'
    with pytest.raises(ValueError):reservation_projection(ledger,own,ref,lambda value:principals[value['sha256']])


@pytest.mark.parametrize('amount',[-1,True,(2<<30)+1])
def test_invalid_or_excess_positive_budget_is_not_accepted_as_zero(amount):
    ledger,own,ref,principals=registry23()
    ledger['reservations']['performance_manual_R2_4090_v1']['remaining_bytes']=amount
    with pytest.raises(ValueError):reservation_projection(ledger,own,ref,lambda value:principals[value['sha256']])


def test_orphan019_lease_uses_exact_valid_old_or_fresh_distinct_path_without_mutation():
    old=dict(reservation_id='native_S_B20k_v3',authority='ROOT_ACTUAL',created_unix=0.,expires_unix=9000.)
    before=deepcopy(old);clear=dict(intent=False,submitted=False,script=False,slot_root=False)
    assert lease_decision(old,reservation_id='native_S_B20k_v3',slot=19,now=100.,occupied=clear,
        orphan_authorized=True)=='REUSE_EXACT_ORIGINAL'
    assert lease_decision(old,reservation_id='native_S_B20k_v3',slot=19,now=2000.,occupied=clear,
        orphan_authorized=True)=='FRESH_V7_PATH'
    assert old==before
    with pytest.raises(ValueError):lease_decision(old,reservation_id='native_S_B20k_v3',slot=19,now=100.,
        occupied=clear,orphan_authorized=False)
    assert lease_decision(None,reservation_id='native_S_B20k_v3',slot=20,now=100.,occupied=clear,
        orphan_authorized=False)=='FRESH_V7_PATH'


@pytest.mark.parametrize('occupied_key',['intent','submitted','script','slot_root'])
def test_any_existing_prelaunch_or_submission_evidence_blocks_orphan_replay(occupied_key):
    occupied=dict(intent=False,submitted=False,script=False,slot_root=False);occupied[occupied_key]=True
    with pytest.raises(ValueError,match='ambiguous'):
        lease_decision(None,reservation_id='native_S_B20k_v3',slot=19,now=100.,occupied=occupied,orphan_authorized=True)


def test_actual_frozen_stable_request_identity_excludes_only_operational_refs():
    # Normal immutable runtime import; no encoder, input provider or tensor work.
    from phychem_mfm.phase1 import v3_long_run_storage as storage
    assert Path(storage.__file__).absolute()==c.RUNTIME/'current/phychem_mfm/phase1/v3_long_run_storage.py'
    old=dict(native_member=dict(seed=0,precision='fp32'),configuration=dict(path='/same/config'),
        long_run=dict(reservation_principal=dict(path='/same/principal'),profile=dict(path='/same/profile'),
            lease=dict(path='/old/lease'),quota_feed_descriptor=dict(path='/old/descriptor'),
            Root_segment_admission=dict(path='/old/admission')))
    new=deepcopy(old)
    for key in ('lease','quota_feed_descriptor','Root_segment_admission'):new['long_run'][key]=dict(path='/new/'+key)
    assert storage.stable_request_identity(old)==storage.stable_request_identity(new)
    new['native_member']['seed']=1
    assert storage.stable_request_identity(old)!=storage.stable_request_identity(new)


def test_actual_closed_panel_missing_standard_fields_is_explicit_and_registry_is_not_resealed():
    ledger,own,ref,principals=registry23();before=deepcopy(ledger);original_digest=c.digest(ledger)
    key='native_S10000_seed0_fp32_dev9_v2';row=ledger['reservations'][key]
    principal=principals[row['principal']['sha256']]
    assert 'initial_existing_bytes' not in principal and 'scientific_acceptance' not in principal
    rows,receipt=reservation_projection(ledger,own,ref,lambda value:principals[value['sha256']])
    assert ledger==before and c.digest(ledger)==original_digest and c.digest(rows)!=original_digest
    assert rows[key]==dict(phase=str(c.N/'Native_S10000_seed0_fp32_dev9_v2/panel'),
        principal_sha256=row['principal_sha256'],remaining_bytes=0,
        root_semantics='CLOSED_HISTORICAL_PANEL_BUDGET_NOT_NATIVE_LEDGER')
    assert rows['performance_manual_R2_4090_v1']['remaining_bytes']==2<<30
    assert receipt['original_registry_not_modified'] is True


@pytest.mark.parametrize('bad',['positive_hold','wrong_key','wrong_phase','wrong_cap','wrong_flags','wrong_time_or_partial_fields'])
def test_closed_panel_alias_never_accepts_positive_unknown_or_resealed_variant(bad):
    ledger,own,ref,principals=registry23();key='native_S10000_seed0_fp32_dev9_v2'
    row=ledger['reservations'][key];principal=principals[row['principal']['sha256']]
    if bad=='positive_hold':row['remaining_bytes']=1
    elif bad=='wrong_key':
        ledger['reservations']['unknown_panel']=ledger['reservations'].pop(key)
        principal['reservation_id']='unknown_panel'
    elif bad=='wrong_phase':
        row['phase']=principal['phase']=str(c.N/'another_panel/panel')
    elif bad=='wrong_cap':
        for field,value in (('max_bytes',True),('reserved_additional_bytes',(2<<30)-1),('whole_output_bytes',None)):
            values=deepcopy(principals);values[row['principal']['sha256']][field]=value
            with pytest.raises(ValueError):reservation_projection(ledger,own,ref,lambda r:values[r['sha256']])
        return
    elif bad=='wrong_flags':
        for field in ('physical_2GiB_file_allocation_claimed',
                'preparation_bytes_already_accounted_in_live_quota','private_storage_independently_guarded'):
            for value in (None,0,1):
                values=deepcopy(principals);values[row['principal']['sha256']][field]=value
                with pytest.raises(ValueError):reservation_projection(ledger,own,ref,lambda r:values[r['sha256']])
            values=deepcopy(principals);del values[row['principal']['sha256']][field]
            with pytest.raises(ValueError):reservation_projection(ledger,own,ref,lambda r:values[r['sha256']])
        return
    else:
        for value in (None,True,0.,-1.,float('nan'),float('inf'),'1793220000'):
            values=deepcopy(principals);values[row['principal']['sha256']]['actual_unix']=value
            with pytest.raises(ValueError):reservation_projection(ledger,own,ref,lambda r:values[r['sha256']])
        for field,value in (('initial_existing_bytes',0),('scientific_acceptance',False)):
            values=deepcopy(principals);values[row['principal']['sha256']][field]=value
            with pytest.raises(ValueError):reservation_projection(ledger,own,ref,lambda r:values[r['sha256']])
        values=deepcopy(principals)
        values[row['principal']['sha256']].update(initial_existing_bytes=0,scientific_acceptance=False)
        with pytest.raises(ValueError):reservation_projection(ledger,own,ref,lambda r:values[r['sha256']])
        # A standard principal cannot inherit the panel exception by deleting fields.
        key2='performance_manual_R2_4090_v1';row2=ledger['reservations'][key2]
        values=deepcopy(principals)
        for field in ('initial_existing_bytes','scientific_acceptance'):
            del values[row2['principal']['sha256']][field]
        with pytest.raises(ValueError):reservation_projection(ledger,own,ref,lambda r:values[r['sha256']])
        return
    with pytest.raises(ValueError):reservation_projection(ledger,own,ref,lambda value:principals[value['sha256']])
