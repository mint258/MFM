"""Mechanical V2 projections after ONE real supplemental CPU parent C0.

Reads only saved metadata/raw references. Does not scan SDKs, load checkpoints,
repeat model work, reserve quota or manufacture an independent terminal.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from pathlib import Path
from long_common import *


def execution(component,terminal,job,*,inputs=None):
    value=read_ref(component['raw_command'])
    require(value['returncode']==0 and str(value['job_id'])==job and value['uid']==os.getuid(),
        'Actual readiness stage command/job/UID differs')
    source=component['producer_source'];require(binding(source['path'])==source and source['path'] in value['argv'],
        'Actual readiness stage/source differs')
    selected=inputs or component['inputs'];manifest=read_ref(selected)
    require(selected['path'] in value['argv'] and manifest['schema']=='native_S_evidence_inputs_v2',
        'Actual stage argv did not consume this evidence manifest')
    return dict(raw_command=component['raw_command'],inputs=selected,actual_terminal=terminal,job_id=job)


def assemble(phase,index_path,terminal_path):
    root_identity();verify();phase=Path(phase);draft=read(phase/'control/DRAFT.json')
    contract,adapter=import_runtime(draft['runtime_contract']['path'])
    index_ref=binding(index_path);index=read_ref(index_ref)
    require(index['schema']=='native_S_supplemental_component_index_v1'
        and index['status']=='RAW_COMPONENTS_AVAILABLE_PENDING_ACTUAL_CPU_OUTER_C0',
        'Actual complete supplemental component index required')
    require(len(index['sdk']['profiles'])==2 and len(index['future_state'])==2
        and len(index['metadata_observations'])==4,'Exact finite readiness component cardinalities required')
    terminal_ref=binding(terminal_path);terminal=read_ref(terminal_ref);job=str(index['actual_CPU_job_id'])
    require(str(terminal['job_id'])==job and terminal['status']=='COMPLETED' and terminal['exit_code']==0,
        'The ONE actual supplemental parent must be C0 before projections')
    require_C0(read_ref(terminal['raw_sacct']),job)
    result_path=Path(index_path).parent/'READINESS_RESULT.json';readiness=read(result_path)
    require(readiness['status']=='READINESS_CHILD_COMPLETE_PENDING_ACTUAL_CPU_C0' and readiness['returncode']==0
        and readiness['failure'] is None and str(readiness['job_id'])==job,'Readiness child did not actually complete')
    out=phase/'control/readiness_assembly';require(not out.exists(),'Fresh metadata assembly output required');out.mkdir()
    pressure=index['accounting'];measured=read_ref(pressure['raw_measurement'])
    require(measured['managed_roots']==512 and measured['metadata_records']==32768
        and measured['metadata_bytes']==512<<20 and measured['measurement_passes']>=8,
        'Actual complete finite accounting pressure differs')
    accounting_execution=execution(pressure,terminal_ref,job)
    accounting=write(out/'accounting_projection.json',dict(schema='native_S_accounting_pressure_projection_v2',
        producer_source=pressure['producer_source'],execution=accounting_execution,
        raw_measurement=pressure['raw_measurement'],scope='same_supplemental_CPU_C0_metadata_only'))
    accounting_terminal=write(out/'accounting_terminal.json',{**terminal,
        'produced_artifact':pressure['raw_measurement'],'same_actual_CPU_parent_not_new_job':True})
    rows={}
    for sdk in index['sdk']['profiles']:
        precision=sdk['precision'];require(precision in ('fp32','bf16') and precision not in rows,'Exactly two profile roles required')
        profile_ref=sdk['profile_result'];profile=read_ref(profile_ref)
        gpu_terminal=sdk['actual_profile_terminal'];gpu=read_ref(gpu_terminal)
        require(gpu['profile_result']==profile_ref and gpu['status']=='COMPLETED' and gpu['exit_code']==0,
            'Underlying observed GPU profile was not actual C0')
        require_C0(read_ref(gpu['raw_sacct']),gpu['job_id'])
        sdk_execution=execution(index['sdk'],terminal_ref,job,inputs=sdk['input_manifest'])
        sdk_fields={key:sdk[key] for key in ('profile_result','expectations','sdk','history_reader_source',
            'raw_history_verification','raw_history_call_binding','raw_config_summary_verification')}
        sdk_proof=write(out/(precision+'_SDK_projection.json'),dict(schema='native_S_full_SDK_projection_v2',
            status='VERIFIED',producer_source=index['sdk']['producer_source'],execution=sdk_execution,**sdk_fields))
        future=next(item for item in index['future_state'] if read_ref(item['inputs'])['artifacts']['profile_result']==profile_ref)
        calculation=read_ref(future['future_bound_calculation'])
        require(calculation['unknown_assumptions']==[] and calculation['fits_finite_checkpoint_cap'] is True,
            'Unknown/oversize future state cannot be admitted')
        future_proof=write(out/(precision+'_future_projection.json'),dict(schema='native_S_future_state_projection_v2',
            status='ROOT_VERIFIED_NATIVE_FUTURE_STATE_BOUND',producer_source=future['producer_source'],
            execution=execution(future,terminal_ref,job),profile_result=profile_ref,checkpoint=profile['checkpoint_ref'],
            raw_shape_report=future['shape_report'],raw_future_bound_calculation=future['future_bound_calculation'],
            provider_future_state_bound_bytes=calculation['provider_future_state_bound_bytes'],
            optimizer_future_state_bound_bytes=calculation['optimizer_future_state_bound_bytes']))
        selected=[item for item in index['metadata_observations'] if item['profile_result']==profile_ref]
        require(len(selected)==2,'Exactly two distinct saved-metadata roles per profile required')
        metadata={item['role']:item for item in selected}
        require(set(metadata)=={'precision_verifier','closed_census'},'Actual precision/closed observations both required')
        dtype=metadata['precision_verifier'];receipt=read_ref(dtype['observation'])
        dtype_proof=write(out/(precision+'_precision_projection.json'),dict(schema='native_S_precision_projection_v2',
            status='ROOT_VERIFIED_NATIVE_OPERATOR_INTERFACES',producer_source=dtype['producer_source'],
            execution=execution(dtype,terminal_ref,job),profile_result=profile_ref,
            raw_operator_observation=receipt,claims_kernel_accumulator_precision=False))
        census=metadata['closed_census'];counts=read_ref(census['observation'])
        closed=write(out/(precision+'_closed_census_projection.json'),dict(schema='native_S_closed_output_census_v2',
            profile_result=profile_ref,producer_source=census['producer_source'],execution=execution(census,terminal_ref,job),
            raw_census=census['observation'],**{key:counts[key] for key in ('child_total_bytes','checkpoint_payload_bytes',
                'non_checkpoint_output_bytes','coverage_observation','after_actual_child_terminal')}))
        rows[precision]={key:profile['measurements'][key] for key in ('checkpoint_bytes','save_seconds',
            'validation_seconds','cleanup_seconds','base_records_per_second')}
        rows[precision].update(non_checkpoint_output_bytes=counts['non_checkpoint_output_bytes'],
            provider_future_state_bound_bytes=calculation['provider_future_state_bound_bytes'],
            optimizer_future_state_bound_bytes=calculation['optimizer_future_state_bound_bytes'],
            accounting_seconds_per_guard=measured['measured_seconds']+profile['measurements']['current_accounting_seconds'],
            accounting_worst_case_roots=measured['managed_roots'],actual_terminal=gpu_terminal,profile_result=profile_ref,
            native_SDK_verification=sdk_proof,closed_output_census=closed,future_state_certificate=future_proof,
            selective_precision_certificate=dtype_proof,accounting_certificate=accounting,accounting_terminal=accounting_terminal)
    require(set(rows)=={'fp32','bf16'},'Both complete profiles required')
    first=read_ref(rows['fp32']['profile_result'])
    base=read(N/'native_S_profile_fp32_v8/control/configuration.json')
    member=dict(sources=first['native_sources'],runtime=first['runtime'],code_sha=CODE,prereg_sha=PUBLIC)
    projection=write(out/'native_S_profile.json',dict(schema='model_v3_Root_existing_native_S_profile_v2',
        authority='ROOT_ACTUAL',scope=adapter.SCOPE,D5_authority=False,
        profile_identity_sha256=adapter.identity(base,dict(native_member=member)),
        source=adapter.SOURCE,full_TRAIN_disjointness=first['full_TRAIN_disjointness'],measurements=rows,
        actual_shared_CPU_terminal=terminal_ref,raw_component_index=index_ref,
        assembly_source=binding(__file__),new_GPU_execution_performed=False,scientific_acceptance=False))
    return projection


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('phase','components','terminal'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(assemble(a.phase,a.components,a.terminal))
