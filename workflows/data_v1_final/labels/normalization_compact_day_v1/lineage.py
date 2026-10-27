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
    m=I.load(I.require(ref));C.need(m['schema']==C.OLD.BATCH and m['status']=='DAY_INTERNAL_COMMITTED_WINDOWS_NOT_CHILD_C0'
        and m['mode']=='full' and not(m['errors'] or m['quality_hold_fields'] or m['unpublished_tickets']),'ONLY_CLEAN_DAY_COMMITTED_WINDOWS')
    cfg=I.load(I.require(m['config']))
    for key in ('canonical_index','footer_manifest_reference','logical_group_plan_reference','field_map_reference','codec_schema','row_size_rule'):
        C.need(cfg[key]==CONTEXT['cfg'][key],'EXACT_DAY_SOURCE_OR_CODEC_CHANGED:'+key)
    if prior_root is None:C.need(str(m['job_id'])==str(CONTEXT['proof']['job_id']),'ACTUAL_CURRENT_PARENT_ID')
    record={'origin_type':'REAL_DAY_PARENT_COMMITTED_CHECKPOINT_NOT_CHILD_JOB','manifest':ref}
    C.need(ref['path'] not in REGISTERED or REGISTERED[ref['path']]==record,'NO_CONFLICTING_INTERNAL_CHECKPOINT')
    REGISTERED[ref['path']]=record;return record

def actual(parent):
    if 'origin_type' not in parent:return OLD.actual(parent)
    C.need(CONTEXT is not None and parent.get('origin_type')=='REAL_DAY_PARENT_COMMITTED_CHECKPOINT_NOT_CHILD_JOB'
        and REGISTERED.get(parent['manifest']['path'])==parent,'ONLY_REGISTERED_ACTUAL_DAY_OUTPUT_AUTHORITY')
    return I.load(I.require(parent['manifest'])),[parent['manifest']]
