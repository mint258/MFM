"""Exact metadata-only continuation of the proven never-dispatched batch96."""
import copy
from pathlib import PurePosixPath
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as F

BID='batch-00096';FAILED_RUN='4521922';OLD_CLOSE='4521923';PREPARE='4521921'
DERIVATION='ROOT_EXPLICIT_UNSTARTED96_METADATA_DERIVATIVE_V1'


def zero_consumption(closed,prepared,original_plan_reference):
    F.need(closed['schema']=='SPRIME_FORMAL_CPU_CLOSED_BATCH_V3'
      and closed['status']=='ACTUAL_TERMINAL_BATCH_CLASSIFIED'
      and closed['batch_id']==BID and closed['actual_parent_job_id']==FAILED_RUN
      and closed['actual_parent']['state']=='FAILED' and closed['actual_parent']['exit_code']=='1:0'
      and closed['valid_packets']==closed['consumed_outcomes']==closed['execution_unresolved']==0
      and closed['unstarted_count']==500 and closed['errors']==closed['consumed_elsewhere']==[],
      'ONLY_ACTUAL96_ZERO_CONSUMED_ALL500_UNSTARTED_NO_UNKNOWN')
    F.need(closed['plan']==original_plan_reference and closed['prepared']['path'].endswith('/batch-00096/prepared_mapping_v1/prepared.json')
      and prepared['schema']==F.SCHEMAS['prepared'] and prepared['status']=='ORIGINAL_BATCH_INPUTS_READY_NOT_GENERATED'
      and prepared['batch']['batch_id']==BID and prepared['molecules']==prepared['batch']['molecules']==500
      and prepared['plan']==original_plan_reference and prepared['runtime']['job_id']==PREPARE
      and prepared['kernel_sha256']==F.KERNEL_SHA,'ORIGINAL500_PREPARED_C0_LINEAGE_AND_KERNEL')
    F.triple(prepared['tasks'])


def replacement_slot(original,review):
    F.need(len(review['jobs'])==1 and review['maximum_concurrent_jobs']==1,'ONE_EXPLICIT_REPLACEMENT96_SLOT_ONLY')
    slot=review['jobs'][0]
    F.need(original['batch_id']==slot['batch_id']==BID,'NO_OTHER_BATCH_REPLACEMENT')
    F.need(set(slot)==set(original) and all(slot[k]==original[k] for k in original if k not in {'job_name','output_root'}),
      'ONLY_NEW_NAME_AND_OUTPUT_SLOT_DELTA_RESOURCES_UNCHANGED')
    F.need(slot['job_name']!=original['job_name'] and slot['job_name'].startswith('dv1_q_')
      and slot['output_root']!=original['output_root'],'FRESH_EXPLICIT_NAME_AND_OUTPUT_REQUIRED')
    p=PurePosixPath(slot['output_root'])
    F.need(p.is_absolute() and str(F.BASE/'wave2'/BID) in {str(q) for q in p.parents}
      and '..' not in p.parts,'EXACT96_NEW_OUTPUT_UNDER_ORIGINAL_BATCH_NAMESPACE')
    F.need(slot['cpus']==16 and slot['node']=='compute-0-13' and slot['wall_seconds']==28800
      and slot['whole_output_cap_bytes']==F.CAP and slot['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED',
      'UNCHANGED_CPU13_NO_MEMORY8H8GIB_SLOT')
    return copy.deepcopy(slot)


def derive_plan(original,original_reference,wave_review_reference,wave_review,decision_reference):
    slots=[r for r in original['jobs'] if r['batch_id']==BID]
    F.need(len(slots)==1 and original['schema']==F.SCHEMAS['plan']
      and original['status']=='BOUNDED_WAVE_FROZEN_IMPORTS_CLOSED'
      and len(original['jobs'])==179 and original['imports320_durably_verified'] is True
      and original['runtime']['job_id']=='4521486','ACTUAL_ORIGINAL179_FROZEN_PLAN_REQUIRED')
    slot=replacement_slot(slots[0],wave_review)
    result=copy.deepcopy(original)
    F.need('recovery_metadata_derivation' not in result,'NO_DERIVATIVE_OF_DERIVATIVE_AUTOMATIC_RETRY')
    result.update(jobs=[slot],root_review=wave_review_reference,maximum_concurrent_jobs=1,
      requested_allocation_core_seconds_ceiling=16*28800,
      recovery_metadata_derivation={'schema':DERIVATION,'origin_plan_reference':original_reference,
        'root_decision_reference':decision_reference,'metadata_only':True,'new_CPU_freeze_claimed':False,
        'inherited_runtime_is_original_4521486':True,'new_task_keys_or_seeds':False,'original179_plan_changed':False})
    reverse=copy.deepcopy(result);reverse.pop('recovery_metadata_derivation')
    for key in ('jobs','root_review','maximum_concurrent_jobs','requested_allocation_core_seconds_ceiling'):
        if key in original:reverse[key]=copy.deepcopy(original[key])
        else:reverse.pop(key,None)
    F.need(F.canonical(reverse)==F.canonical(original),'INVERSE_PLAN_DELTA_MUST_RECOVER_ALL_ORIGINAL_METADATA')
    return result


def derive_prepared(original,original_reference,new_plan_reference,decision_reference):
    F.need(original['runtime']['job_id']==PREPARE and original['batch']['batch_id']==BID
      and original['molecules']==500,'ORIGINAL_ACTUAL_PREPARE_LINEAGE_ONLY')
    result=copy.deepcopy(original);F.need('recovery_metadata_derivation' not in result,'NO_PREPARED_DERIVATIVE_RETRY')
    result.update(plan=new_plan_reference,recovery_metadata_derivation={'schema':DERIVATION,
      'origin_prepared_reference':original_reference,'root_decision_reference':decision_reference,
      'metadata_only':True,'tasks_bytes_not_read_or_rewritten':True,'new_CPU_prepare_claimed':False,
      'inherited_runtime_is_original_4521921':True})
    reverse=copy.deepcopy(result);reverse.pop('recovery_metadata_derivation');reverse['plan']=copy.deepcopy(original['plan'])
    F.need(F.canonical(reverse)==F.canonical(original) and result['tasks']==original['tasks'],
      'INVERSE_PREPARED_DELTA_AND_ALL_ORIGINAL_TASK_LOCATORS_UNCHANGED')
    return result
