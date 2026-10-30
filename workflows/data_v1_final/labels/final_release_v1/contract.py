"""Small metadata only. A current-family candidate is never a separate C0."""
import json,re
from pathlib import Path
from workflows.data_v1_final.labels.common_train_normalization_day_v1 import contract as D4
from workflows.data_v1_final.labels.normalization_typed_cache_v1.contract import need,reference
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q,contract as A
ROOT=Q.ROOT;REPO=Q.REPO;HERE=REPO/'workflows/data_v1_final/labels/final_release_v1'
SCHEMA='ROOT_FINAL_LABEL_RELEASE_DIRECTIVE_V1';CANDIDATE='FINAL_LABEL_RELEASE_CANDIDATE_V1';RELEASE='ROOT_FINAL_LABEL_RELEASE_V1'
FILES=('__init__.py','contract.py','originals.py','produce.py','rho.py','mask_binding.py','metadata.py','test_boundaries.py','README.md')
REQUIRED=('d4_closure_reference','root_actual_d4_acceptance_reference','joint_policy_reference','base_registry_reference',
          'mapping_reference','d5_components_acceptance_reference')

def meta(ref):return json.loads(A.pin_bytes(ref,Q.read_small))

def unique(refs):
    out={}
    for r in refs:
        r=reference(r,source=r.get('bytes')==0);need(r['path'] not in out or out[r['path']]==r,'NO_CONFLICTING_RELEASE_REFERENCE');out[r['path']]=r
    return list(out.values())

def actual_accounted_parent(parent):
    p=meta(parent['proof']);a=meta(parent['accounting']);jid=str(p['job_id']);req=p['request']
    need(a['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and a['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
      and a['endpoint']=='202.38.247.57:22' and a['uid']==1278 and a['query_returncode']==0 and a['raw_sacct_reference']==parent['raw'],
      'ACTUAL_MAIN_SEPARATE_STATISTICS_ACCOUNTING')
    rows=[r for r in a['parents'] if str(r['job_id'])==jid]
    need(len(rows)==1 and rows[0]['state']=='COMPLETED' and rows[0]['exit_code']=='0:0' and rows[0]['alloc_cpus']==req['cpus']>=16,
      'REAL_SEPARATE_STATISTICS_C0_NOT_DIAGNOSTIC_ALIAS')
    raw=A.pin_bytes(parent['raw'],Q.read_small).decode('utf-8-sig').splitlines();head=raw[0].split('|')
    records=[dict(zip(head,line.split('|'))) for line in raw[1:] if line.split('|')[0]==jid]
    need(len(records)==1 and records[0]['UID']=='1278' and records[0]['State']=='COMPLETED' and records[0]['ExitCode']=='0:0'
      and records[0]['AllocCPUS']==str(req['cpus']),'RAW_SEPARATE_STATISTICS_C0_IDENTITY')
    return p,meta(parent['manifest'])

def descendants(value):
    if isinstance(value,dict):
        if {'path','bytes','sha256'}<=set(value):yield reference(value,source=value.get('bytes')==0)
        else:
            for v in value.values():yield from descendants(v)
    elif isinstance(value,list):
        for v in value:yield from descendants(v)

def sources():
    paths=[*(HERE/n for n in FILES),REPO/'workflows/data_v1_final/labels/build_registry.py',
      REPO/'workflows/data_v1_final/labels/common.py',REPO/'workflows/data_v1_final/labels/streaming_v1/reduce.py',
      REPO/'workflows/data_v1_final/export/pipeline_v1/masks.py',REPO/'workflows/data_v1_final/export/pipeline_v1/mask_binding.py',
      REPO/'workflows/data_v1_final/export/wire_v1/mapping.py']
    paths.extend(D4.HERE/n for n in D4.FILES)
    return unique(Q.pin(p) for p in paths)

def missing_result(d,missing):
    return {'status':'NONEXECUTABLE','missing':missing,'source_references':[],'data_references':[],
      'directive':d,'current_parent_C0_required_for_candidate':False,'future_references_created':False}

def validate_directive(directive,*,allow_nonexecutable=True):
    d=directive;need(type(d)is dict and d.get('schema')==SCHEMA,'EXACT_FINAL_RELEASE_DIRECTIVE')
    missing=[k for k in REQUIRED if not isinstance(d.get(k),dict)]
    if d.get('status')!='ROOT_REVIEWED_ACTUAL_D4_AND_JOINT_POLICY_INPUTS' or d.get('reviewer')!='root':missing.append('actual_Root_directive_review')
    if missing:
        if allow_nonexecutable:return missing_result(d,missing)
        raise ValueError('NONEXECUTABLE:'+','.join(missing))
    need(d['release_scope'] in ('BOUNDED_D3_50K_TRAIN_5K_ROUTINE_VAL','FULL_V1') and type(d['release_id'])is str
      and re.fullmatch('[a-zA-Z0-9_]{1,80}',d['release_id']),'EXACT_BOUNDED_OR_FULL_SCOPE_NO_ALIAS')
    closure=meta(d['d4_closure_reference']);need(closure['schema']=='COMMON_TRAIN_NORMALIZATION_ACTUAL_DAY_CLOSURE_V1'
      and closure['status']=='ACTUAL_C0_TECHNICAL_CLOSURE_PENDING_ROOT_REVIEW','REAL_D4_TECHNICAL_C0_PARENT')
    D4.actual(closure['actual_parent']);m=meta(closure['actual_parent']['manifest'])
    need(m['schema']=='COMMON_TRAIN_NORMALIZATION_DAY_RECEIPT_V1' and m['status']=='COMMON_TRAIN_NUMERIC_COMPONENT_STATISTICS_AND_GUIDE1_5_COMPLETE_PENDING_ROOT_AND_JOINT_POLICY'
      and m['held'] is False and m['errors']==[] and m['quality_hold_fields']==[] and m['independent_full_numeric_replay_equal'] is True,
      'COMPLETE_ACTUAL_COMMON_TRAIN_D4_AND_ALL_POPULATION_MASK_GATE')
    accepted=meta(d['root_actual_d4_acceptance_reference'])
    need(accepted['schema']=='ROOT_ACTUAL_COMMON_TRAIN_NUMERIC_ACCEPTANCE_V1' and accepted['status']=='APPROVED_EXACT_FULL_TRAIN_NUMERIC_AND_MASK_INPUTS'
      and accepted['reviewer']=='root' and accepted['actual_closure_reference']==d['d4_closure_reference']
      and accepted['no_one_percent_quality_waiver'] is True,'INDEPENDENT_ACTUAL_D4_ACCEPTANCE_NO_MASK_WAIVER')
    joint=meta(d['joint_policy_reference'])
    if not (joint.get('schema')=='ROOT_MODEL_JOINT_FINAL_LABEL_POLICY_V1' and joint.get('status')=='JOINTLY_FROZEN'
      and joint.get('actual_final_Model_ack_not_conditional') is True):
        if allow_nonexecutable:return missing_result(d,['actual_final_Root_Model_policy_and_ack'])
        raise ValueError('NONEXECUTABLE:actual_final_Root_Model_policy_and_ack')
    for r in (joint['root_review_reference'],joint['model_ack_reference'],joint['contract_reference']):A.pin_bytes(r,Q.read_small)
    need(joint['root_signoff'] is True and joint['model_signoff'] is True and joint['partial_mask_policy_explicit'] is True
      and joint['r73_pair_dependent_double_basis_onsite_ordinal_explicit'] is True and joint['r674_native_symmetric6_no_trace_projection'] is True
      and joint['actual_child_coordinate_frames_explicit'] is True,'ACTUAL_JOINT_NATIVE_DOMAINS_AND_MASK_POLICY')
    need(joint['registry_source_reference']==d['base_registry_reference'] and joint['mapping_source_reference']==d['mapping_reference'],
      'JOINT_POLICY_BINDS_ACTUAL_REGISTRY_AND_MAPPING_SOURCE')
    unsupported=[]
    for name,recipe in joint['normalization_by_target'].items():
        if recipe.get('scale')!='SERIES_STD_DDOF0' or recipe.get('centering') not in ('SUBTRACT_SERIES_MEAN','FIXED_ZERO'):
            unsupported.append('actual_implemented_normalization_builder:'+name)
    for name,definition in joint['scientific_field_definitions'].items():
        for k in ('unit','sign','basis','frame'):
            if definition.get(k+'_status') not in ('VERIFIED','NOT_APPLICABLE_WITH_ACTUAL_DEFINITION'):unsupported.append('actual_'+k+'_resolution:'+name)
        if definition.get('numeric_transform')!='IDENTITY_NATIVE_STORED_VALUES':unsupported.append('actual_numeric_transform_builder:'+name)
    if unsupported:
        if allow_nonexecutable:return missing_result(d,unsupported)
        raise ValueError('NONEXECUTABLE:'+','.join(unsupported))
    dc=meta(d['d5_components_acceptance_reference']);need(dc['schema']=='ROOT_ACCEPTED_D5_COMPOUND_COMPONENTS_V1'
      and dc['status']=='ACTUAL_C0_COMPONENTS_ACCEPTED_NOT_JOINT_D5','REAL_ROOT_ACCEPTED_D5_COMPONENTS')
    dp=meta(m['plan_reference']);need(dp['d5_components_acceptance_reference']==d['d5_components_acceptance_reference'],'EXACT_D4_D5_POPULATION_AND_ANTI_JOIN')
    need(d['claim_mode'] in ('PREVIOUS_ACTUAL_C0_ACCEPTED_CLAIMS','CURRENT_PARENT_DERIVED_EXACT_FIELD_CLAIMS'),'EXPLICIT_REAL_FIELD_CLAIM_AUTHORITY_MODE')
    if d['claim_mode']!='CURRENT_PARENT_DERIVED_EXACT_FIELD_CLAIMS':
        if allow_nonexecutable:return missing_result(d,['current_family_Source_field_claim_callback_required_for_this_publisher_version'])
        raise ValueError('NONEXECUTABLE:current_family_Source_field_claim_callback_required_for_this_publisher_version')
    claims=None;claim_sources=[]
    if d['claim_mode']=='PREVIOUS_ACTUAL_C0_ACCEPTED_CLAIMS':
        if not d.get('field_geometry_claim_authority_reference'):
            if allow_nonexecutable:return missing_result(d,['actual_field_geometry_claim_authority'])
            raise ValueError('NONEXECUTABLE:actual_field_geometry_claim_authority')
        claims=meta(d['field_geometry_claim_authority_reference']);claim_sources.append(d['field_geometry_claim_authority_reference'])
        need(claims['status']=='ROOT_ACCEPTED_ACTUAL_FIELD_INPUT_GEOMETRY_CLAIMS' and claims['reviewer']=='root'
          and claims['d5_components_acceptance_reference']==d['d5_components_acceptance_reference']
          and claims['all_Common_canonical_field_task_cells_covered'] is True and claims['per_cell_original_input_double_hash_verified'] is True
          and claims['unknown_or_duplicate_claims']==0,'REAL_FIELD_LEVEL_CHILD_GEOMETRY_CLAIMS_NOT_TASK_NAME_MAP')
    else:
        need(d['field_claim_builder_source_references'] and d['claim_builder_review_reference'],'EXACT_CURRENT_PARENT_BUILDER_SOURCE_AND_ROOT_REVIEW')
        claim_sources.extend(d['field_claim_builder_source_references']);claim_sources.append(d['claim_builder_review_reference'])
        review=meta(d['claim_builder_review_reference']);need(review['reviewer']=='root'
          and review['status']=='APPROVED_EXACT_CURRENT_PARENT_FIELD_CLAIM_BUILD' and review['no_future_claim_hash'] is True
          and review['source_references']==d['field_claim_builder_source_references'],'REAL_REVIEWED_SOURCE_BUILDER_NOT_FUTURE_C0')
    if d['release_scope']=='FULL_V1' and not d.get('independent_Pprime_actual_statistics'):
        if allow_nonexecutable:return missing_result(d,['independent_formal_Pprime_statistics_and_actual_C0'])
        raise ValueError('NONEXECUTABLE:independent_formal_Pprime_statistics_and_actual_C0')
    data=unique([*m['numeric_repetition_references'],m['all_population_audit_reference'],*d['exact_DATA_references'],*joint['evidence_DATA_references']])
    small=unique([*(d[k] for k in REQUIRED),*claim_sources,*descendants(closure['actual_parent']),joint['root_review_reference'],joint['model_ack_reference'],joint['contract_reference'],m['plan_reference'],*joint['evidence_source_references']])
    if d.get('independent_Pprime_actual_statistics'):
        pp=d['independent_Pprime_actual_statistics'];actual_accounted_parent(pp['actual_parent'])
        small=unique([*small,*descendants(pp['actual_parent']),pp['root_acceptance_reference']]);data=unique([*data,pp['numeric_statistics_reference']])
    need(not {r['path'] for r in data}&{r['path'] for r in small},'NUMERIC_JSON_AND_PARQUET_NOT_SMALL_SOURCE')
    for r in small:A.pin_bytes(r,Q.read_small)
    from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import metadata as OriginalMetadata
    original_closure=OriginalMetadata.sources(dp)
    return {'status':'READY_ACTUAL_PARENTS_BOUND','missing':[],'source_references':unique([*small,*sources(),*original_closure]),
      'data_references':data,'directive':d,'d4_manifest':m,'d4_plan':dp,'joint_policy':joint,'geometry_claim_authority':claims,
      'current_parent_C0_required_for_candidate':False}
