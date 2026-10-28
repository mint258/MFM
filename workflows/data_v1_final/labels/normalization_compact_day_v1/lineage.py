"""Actual old C0 or exact current-parent checkpoints, never fabricated child C0."""
from pathlib import Path
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import metadata as OLD
from . import contract as C,io as I
CONTEXT=None;REGISTERED={}

def bind(proof,plan_ref,root,cfg):
    global CONTEXT
    C.need(CONTEXT is None,'ONE_DAY_LINEAGE_CONTEXT');CONTEXT={'proof':proof,'plan_ref':plan_ref,'root':Path(root),'cfg':cfg}

def register(ref,*,prior_root=None):
    C.need(CONTEXT is not None,'ACTUAL_DAY_CONTEXT_REQUIRED');root=CONTEXT['root'] if prior_root is None else Path(prior_root)
    C.need(Path(ref['path']).parent.parent==root and Path(ref['path']).name=='manifest.json','ONLY_ACTUAL_BOUND_DAY_PROJECTION_SUBDIR')
    m=I.load(I.require(ref));C.need(m['schema']==C.OLD.BATCH and m['status'] in ('DAY_INTERNAL_COMMITTED_WINDOWS_NOT_CHILD_C0','ROOT_ADOPTED_FAILED_DAY_CLOSED_WINDOWS_CURRENT_PARENT_VERIFIED')
        and m['mode']=='full' and not(m['errors'] or m['quality_hold_fields'] or m['unpublished_tickets']),'ONLY_CLEAN_DAY_COMMITTED_WINDOWS')
    cfg=I.load(I.require(m['config']))
    for key in ('canonical_index','footer_manifest_reference','logical_group_plan_reference','field_map_reference','codec_schema','row_size_rule'):
        C.need(cfg[key]==CONTEXT['cfg'][key],'EXACT_DAY_SOURCE_OR_CODEC_CHANGED:'+key)
    if prior_root is None:C.need(str(m['job_id'])==str(CONTEXT['proof']['job_id']),'ACTUAL_CURRENT_PARENT_ID')
    if m['status']=='ROOT_ADOPTED_FAILED_DAY_CLOSED_WINDOWS_CURRENT_PARENT_VERIFIED':
        C.need(m['failed_prefix_recovery_reference']==CONTEXT['cfg'].get('failed_prefix_recovery_reference') and m['old_parent_state']=='FAILED'
          and m['old_parent_core_seconds']==603392 and m['old_C0_claimed'] is False,
          'ONLY_EXPLICIT_ACTUAL_FAILED_PREFIX_VERIFIER_NOT_OLD_C0')
        plan=C.meta(CONTEXT['plan_ref'])
        if plan.get('prior_hash_stage_reference'):
            reuse=I.load(I.require(m['prior_hash_stage_reuse_reference']))
            C.need(m['prior_hash_stage_reference']==plan['prior_hash_stage_reference']
              and m['whole_SHA_basis']=='ACTUAL_PRIOR_C0_COMPLETE_HASH_CURRENT_FD_STABLE'
              and m['current_CPU_complete_whole_SHA_and_typed_readback'] is False
              and m['current_CPU_unchanged_frames_and_complete_typed_readback'] is True
              and reuse['schema']=='ACTUAL_PRIOR_HASH_STAGE_CURRENT_FD_REUSE_V1'
              and reuse['prior_hash_stage_reference']==plan['prior_hash_stage_reference']
              and reuse['current_parent_job_id']==str(m['job_id']) and reuse['current_old_file_FD_frames_verified'] is True
              and reuse['old_scientific_bodies_rehashed'] is False,'EXACT_ACTUAL_C0_HASH_CHAIN_AND_NEW_TYPED_READBACK_NOT_NEW_BODY_HASH_CLAIM')
        else:C.need(m['current_CPU_complete_whole_SHA_and_typed_readback'] is True,'CURRENT_PARENT_FIRST_HASH_AND_TYPED_READBACK')
    record={'origin_type':'REAL_DAY_PARENT_COMMITTED_CHECKPOINT_NOT_CHILD_JOB','manifest':ref}
    C.need(ref['path'] not in REGISTERED or REGISTERED[ref['path']]==record,'NO_CONFLICTING_INTERNAL_CHECKPOINT')
    REGISTERED[ref['path']]=record;return record

def actual(parent):
    if 'origin_type' not in parent:return OLD.actual(parent)
    C.need(CONTEXT is not None and parent.get('origin_type')=='REAL_DAY_PARENT_COMMITTED_CHECKPOINT_NOT_CHILD_JOB'
        and REGISTERED.get(parent['manifest']['path'])==parent,'ONLY_REGISTERED_ACTUAL_DAY_OUTPUT_AUTHORITY')
    return I.load(I.require(parent['manifest'])),[parent['manifest']]

def parts_root(manifest,parent):
    if manifest['status']=='ROOT_ADOPTED_FAILED_DAY_CLOSED_WINDOWS_CURRENT_PARENT_VERIFIED':
        C.need(parent.get('origin_type')=='REAL_DAY_PARENT_COMMITTED_CHECKPOINT_NOT_CHILD_JOB'
          and REGISTERED.get(parent['manifest']['path'])==parent,'ONLY_CURRENT_VERIFIED_ADOPTION_HAS_EXTERNAL_OLD_PARTS')
        from . import recovery
        a,inventory,old=recovery.authority(manifest['failed_prefix_recovery_reference'])
        C.need(manifest['adopted_original_projection_root']==inventory['exact_closed_projection_directory'],
          'EXACT_FAILED_PRODUCER_PARTS_ROOT_NOT_ARBITRARY_EXTERNAL_DATA')
        return Path(manifest['adopted_original_projection_root'])
    return Path(parent['manifest']['path']).parent
