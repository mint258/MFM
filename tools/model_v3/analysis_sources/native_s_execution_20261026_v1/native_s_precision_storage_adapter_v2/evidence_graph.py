"""Bound raw operational evidence. Boolean projections never supply authority."""
from __future__ import annotations
from pathlib import Path
import re
import os


def require(value,message):
    if not value: raise ValueError(message)


def bound_binary(storage,ref,*,maximum):
    require(type(ref) is dict and set(ref)=={'path','bytes','sha256'} and type(ref['bytes']) is int
        and 0<ref['bytes']<=maximum,'Bounded binary reference required')
    require(Path(ref['path']).stat().st_size==ref['bytes'] and storage.binding(ref['path'])==ref,
        'Raw artifact bytes/SHA changed')
    return ref


def argument(argv,*names):
    values=[]
    for index,item in enumerate(argv):
        for name in names:
            if item==name and index+1<len(argv): values.append(argv[index+1])
            elif item.startswith(name+'='): values.append(item[len(name)+1:])
    require(len(values)==1,'Unique raw command option required: '+str(names))
    return values[0]


def terminal(storage,ref):
    projection=storage.read_bound(ref)
    require(projection['schema']=='native_S_actual_terminal_projection_v2','Known raw terminal projection schema required')
    raw=storage.read_bound(projection['raw_sacct'])
    argv=raw['argv']; job=str(projection['job_id'])
    require(raw['returncode']==0 and Path(argv[0]).name=='sacct'
        and job in argument(argv,'--jobs','-j').split(','),'Actual successful sacct query for this job required')
    fields=argument(argv,'--format','-o').split(',')
    fields=[field.split('%')[0] for field in fields]
    require(any(name in fields for name in ('JobID','JobIDRaw')) and 'State' in fields and 'ExitCode' in fields,
        'Raw sacct format lacks terminal fields')
    rows=[]
    for line in raw['stdout'].splitlines():
        values=line.strip().split('|')
        if len(values)<len(fields): continue
        row=dict(zip(fields,values))
        if row.get('JobIDRaw',row.get('JobID'))==job: rows.append(row)
    require(len(rows)==1,'Exactly one raw parent job terminal row required')
    state=rows[0]['State']; code=rows[0]['ExitCode']
    require(state=='COMPLETED' and code=='0:0' and projection['status']=='COMPLETED'
        and projection['exit_code']==0,'Raw sacct is not actual COMPLETED0:0')
    return projection


def producer(storage,proof,configuration,role):
    expected=configuration['evidence_sources'][role]
    require(proof['producer_source']==expected and storage.binding(expected['path'])==expected,
        'Evidence producer source/version differs: '+role)
    execution=proof['execution']; raw=storage.read_bound(execution['raw_command'])
    require(raw['returncode']==0 and str(expected['path']) in raw['argv'],
        'Actual evidence command/source did not complete successfully')
    inputs=storage.read_bound(execution['inputs'])
    require(str(execution['inputs']['path']) in raw['argv'] and inputs['schema']=='native_S_evidence_inputs_v2'
        and inputs['role']==role,'Actual evidence command input manifest differs')
    actual=terminal(storage,execution['actual_terminal'])
    require(str(actual['job_id'])==str(execution['job_id']),'Evidence producer actual job differs')
    require(str(raw['job_id'])==str(execution['job_id']) and raw['uid']==os.getuid(),
        'Raw verifier execution observation belongs to another UID/job')
    return inputs


def sdk(storage,ref,*,configuration,raw_profile,profile_ref):
    proof=storage.read_bound(ref)
    require(proof['schema']=='native_S_full_SDK_projection_v2' and proof['status']=='VERIFIED',
        'Native full config/summary SDK projection required; unknown verifier schemas cannot be renamed')
    inputs=producer(storage,proof,configuration,'sdk_verifier')
    require(proof['profile_result']==profile_ref and proof['expectations']==raw_profile['SDK_expectations'],
        'SDK projection is for another profile/config/summary/mirror')
    expectations=proof['expectations']
    require(inputs['artifacts']==expectations,'SDK verifier input bindings differ from actual SDK/config/summary/mirror')
    bound_binary(storage,proof['sdk'],maximum=128<<20)
    bound_binary(storage,expectations['mirror'],maximum=128<<20)
    require(proof['sdk']==expectations['sdk'],'Raw native SDK source differs')
    for name in ('configuration','summary'): storage.read_bound(expectations[name])
    history=storage.read_bound(proof['raw_history_verification'])
    call=storage.read_bound(proof['raw_history_call_binding'])
    require(call['schema']=='native_S_bounded_reader_invocation_v2'
        and call['sdk']==proof['sdk'] and call['mirror']==expectations['mirror']
        and call['result']==proof['raw_history_verification'] and call['expected_run_id']==raw_profile['tracker_id']
        and call['expected_exit']==0 and call['reader_source']==proof['history_reader_source'],
        'Native history result lacks exact SDK/mirror/reader call binding')
    require(history['schema']=='model_v3_native_mirror_verification_v7'
        and history['status']=='VERIFIED_COMMITTED_HISTORY' and history['clean_eof'] is True
        and history['native_closed'] is True and history['uncommitted_native_requests']==0
        and history['decode_error'] is None and history['sdk_run_ids']==[raw_profile['tracker_id']]
        and history['sdk_exit_codes']==[0], 'Original full native history/EOF/exit evidence required')
    require(history['history_rows']==call['expected_history_rows'],'Native full expected mirror population differs')
    require(proof['history_reader_source']==configuration['evidence_sources']['sdk_history_reader']
        and storage.binding(proof['history_reader_source']['path'])==proof['history_reader_source'],
        'Actual bounded native reader source pin differs')
    tap=storage.read_bound(proof['raw_config_summary_verification'])
    require(tap['schema']=='native_S_config_summary_verification_v2'
        and tap['status']=='VERIFIED_ALL_SCIENTIFIC_CONFIG_AND_SUMMARY'
        and tap['sdk']==proof['sdk'] and tap['expectations']==expectations
        and tap['run_id']==raw_profile['tracker_id'] and tap['missing']==[] and tap['extra_scientific']==[]
        and tap['different']==[],'Raw full-config/summary tap evidence missing/different')
    return proof


def closed_outputs(storage,ref,*,configuration,profile_ref):
    proof=storage.read_bound(ref)
    require(proof['schema']=='native_S_closed_output_census_v2' and proof['profile_result']==profile_ref,
        'Post-child output census bound to the saved profile required')
    inputs=producer(storage,proof,configuration,'closed_census')
    require(inputs['artifacts']['profile_result']==profile_ref,'Census invocation input profile differs')
    raw=storage.read_bound(proof['raw_census'])
    require(proof['after_actual_child_terminal'] is True and proof['child_total_bytes']>=proof['checkpoint_payload_bytes']
        and proof['non_checkpoint_output_bytes']==proof['child_total_bytes']-proof['checkpoint_payload_bytes'],
        'Non-checkpoint bytes must derive from actual closed child census, not pre-result SDK estimate')
    require(raw['schema']=='native_S_actual_closed_census_v2' and raw['profile_result']==profile_ref
        and all(raw[key]==proof[key] for key in ('child_total_bytes','checkpoint_payload_bytes',
            'non_checkpoint_output_bytes','coverage_observation','after_actual_child_terminal')),
        'Closed census projection differs from raw collector result')
    return proof


def future_state(storage,ref,*,configuration,raw_profile,profile_ref):
    proof=storage.read_bound(ref)
    require(proof['schema']=='native_S_future_state_projection_v2'
        and proof['status']=='ROOT_VERIFIED_NATIVE_FUTURE_STATE_BOUND','Known future-state proof schema required')
    inputs=producer(storage,proof,configuration,'future_state')
    require(inputs['artifacts']['profile_result']==profile_ref and inputs['artifacts']['checkpoint']==raw_profile['checkpoint_ref'],
        'Future-state invocation inputs differ')
    require(proof['profile_result']==profile_ref and proof['checkpoint']==raw_profile['checkpoint_ref'],
        'Future-state certificate actual safe checkpoint differs')
    bound_binary(storage,proof['checkpoint'],maximum=512<<20)
    shape=storage.read_bound(proof['raw_shape_report'])
    require(shape['schema']=='native_S_actual_safe_checkpoint_shape_v2'
        and shape['checkpoint']==proof['checkpoint'] and shape['safe_weights_only_load'] is True
        and shape['native_sources']==raw_profile['native_sources'] and shape['model']==configuration['science']['model'],
        'Actual safeCP shapes/source report missing')
    bounds=storage.read_bound(proof['raw_future_bound_calculation'])
    require(bounds['schema']=='native_S_frozen_state_growth_bound_v2'
        and bounds['raw_shape_report']==proof['raw_shape_report'] and bounds['plan']==configuration['science']['plan']
        and bounds['provider_future_state_bound_bytes']==proof['provider_future_state_bound_bytes']
        and bounds['optimizer_future_state_bound_bytes']==proof['optimizer_future_state_bound_bytes']
        and bounds['unknown_assumptions']==[], 'Source/shape/plan-derived future bound calculation required; unknown is not zero')
    return proof


def precision(storage,ref,*,configuration,raw_profile,profile_ref):
    proof=storage.read_bound(ref)
    require(proof['schema']=='native_S_precision_projection_v2'
        and proof['status']=='ROOT_VERIFIED_NATIVE_OPERATOR_INTERFACES','Known operator-interface precision proof required')
    inputs=producer(storage,proof,configuration,'precision_verifier')
    require(inputs['artifacts']['profile_result']==profile_ref,'Precision verification invocation input differs')
    receipt=raw_profile['direct_precision_observation']
    require(proof['profile_result']==profile_ref and proof['raw_operator_observation']==receipt
        and receipt['schema']=='native_S_selective_precision_operator_interfaces_v2'
        and receipt['status']=='OBSERVED_OPERATOR_INTERFACES' and receipt['actual_device']=='cuda'
        and set(receipt['layers'])==set(map(str,range(6))) and all(receipt['coverage'].values())
        and receipt['loss_fields_and_total_fp32'] is True,'Complete six-layer actual operator-interface evidence required')
    for row in receipt['layers'].values():
        require(row['QK'] and row['AV'] and row['softmax'] and row['QK']['inputs'] and row['AV']['outputs'],
            'Every layer needs distinct QK/softmax/AV input/output shape/dtype/device records')
    require(proof['claims_kernel_accumulator_precision'] is False,'Operator interfaces do not prove kernel accumulator precision')
    return proof
