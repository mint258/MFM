"""Stdlib Main Root helper: candidate -> separate approval -> actual C0 freeze."""
import argparse,json,os
from pathlib import Path
from . import contract as C,io as I
from workflows.data_v1_final.labels.bounded_projection_v1 import materialize as M
from workflows.data_v1_final.labels.normalization_compact_runtime_v2 import metadata as P

def actual(parent):
    for key in ('manifest','proof','accounting','raw'):C.reference(parent[key],source=True);I.require(parent[key])
    row,refs=M.actual_parent(*(parent[k]['path'] for k in ('manifest','proof','accounting','raw')))
    account=I.load(I.require(parent['accounting']));C.need(account['endpoint']=='202.38.247.57:22' and row['state']=='COMPLETED' and row['exit_code']=='0:0','ACTUAL_MAIN_C0_PARENT_NEVER_TIMEOUT')
    return I.load(I.require(parent['manifest'])),refs

def candidate(a):
    req=I.load(a.request);C.need(req['schema']=='ROOT_FULL_LOGICAL_OWNER_PLAN_BUILD_REQUEST_V2','EXACT_NEW_ROOT_REQUEST')
    root=Path(a.output).absolute();C.need(C.RUN/'control' in root.parents and not root.exists(),'FRESH_MAIN_METADATA_DIRECTORY')
    base_ref=req['baseline512_config_reference'];baseline=I.load(I.require(base_ref));C.need(baseline['schema']=='LOSSLESS_LABEL_PROJECTION_CONFIG_V1','REAL_ORIGINAL512_CONFIG')
    original_ref=baseline['owner_plan'];original=I.load(I.require(original_ref));C.need(original['schema']=='CANONICAL_STREAM_GROUP_PLAN_V1' and original['records']==4251 and original['molecules']==512 and len(original['groups'])==16,'REAL_ORIGINAL_4251_TOTAL_NOT4251_TRAIN')
    bmanifest,brefs=actual(req['baseline_parent']);C.need(bmanifest['schema']=='LOSSLESS_LABEL_PROJECTION_PILOT_V1' and bmanifest['config']==base_ref,'ACTUAL_BASELINE512_PARENT_BINDING')
    footer,frefs=actual(req['footer_parent']);book,_,_,footer_small,_=M.footer_inputs(footer)
    from workflows.data_v1_final.labels.full_projection_v1.control import source_contract
    source_contract(book['files'])
    prep_ref=req['canonical_preparation_reference'];prep=I.load(I.require(prep_ref));C.need(prep['schema']=='SOURCE_STATUS_FULL_PLAN_V1'
      and prep['record_count']==11231854 and prep['molecule_count']==1220466 and prep['canonical_index']==baseline['canonical_index'],'ORIGINAL_ALL_SOURCE_CANONICAL_PREPARATION')
    C.need(prep['authority_locators']['population']==req['formal_record_index_reference'] and prep['sources']['roles']==original['sources']['roles'],'EXACT_FORMAL_AND_ROLE_SOURCE_CHAIN')
    C.need(req['source_mapping_evidence_references'],'EXPLICIT_ROOT_SOURCE_MAPPING_EVIDENCE_REQUIRED')
    for r in req['source_mapping_evidence_references']:I.require(r)
    cfg={'schema':C.SCHEMA,'scope_key':C.KEY,'scope_parameters':C.PARAMETERS,'workers':16,'wall_seconds':req['wall_seconds'],'output_cap_bytes':C.CAP,
      'other_output_cap_bytes':req['other_output_cap_bytes'],'baseline512_config_reference':base_ref,'baseline_parent':req['baseline_parent'],
      'footer_parent':req['footer_parent'],'canonical_preparation_reference':prep_ref,'canonical_index':baseline['canonical_index'],
      'formal_record_index_reference':req['formal_record_index_reference'],'catalog_reference':prep['authority_locators']['catalog'],
      'verification_reference':prep['sources']['verification'],'roles_reference':prep['sources']['roles'],
      'technical_review_reference':req['technical_review_reference'],'resource_authority_reference':req['resource_authority_reference'],
      'source_mapping_evidence_references':req['source_mapping_evidence_references']}
    data=M.unique([cfg['canonical_index'],cfg['formal_record_index_reference'],cfg['catalog_reference']]);denied={r['path'] for r in data}
    refs=[base_ref,original_ref,prep_ref,footer['source_inventory_reference'],cfg['verification_reference'],cfg['roles_reference'],cfg['technical_review_reference'],cfg['resource_authority_reference'],
      *req['source_mapping_evidence_references'],*footer_small,*brefs,*frefs,M.pin(a.request)]
    for r in refs:I.require(r)
    own=[M.pin(C.HERE/name) for name in C.FILES]
    # Only Source assets are inherited here. JSON/numeric/owner files are never
    # promoted to login-hashed Source merely because an old config called them small.
    frozen=[M.pin(C.REPO/'workflows/data_v1_final/labels/full_logical_owner_plan_v1'/name) for name in C.FILES]
    code=M.unique([*own,*frozen,*[r for r in P.sources(baseline) if r['path'] not in denied and
      (Path(r['path']).suffix=='.py' or (C.REPO in Path(r['path']).parents and Path(r['path']).name=='README.md'))]])
    for name in ('prepare_pilot_plan.py','common.py'):code=M.unique([*code,M.pin(C.REPO/'workflows/data_v1_final/labels'/name)])
    cfg.update(source_references=code,small_references=M.unique(refs),data_references=data);C.config(cfg);C.review(cfg,I.load(I.require(cfg['technical_review_reference'])))
    root.mkdir(parents=True,mode=0o700);cr=I.save(root/'config.json',cfg)
    output=Path(req['output_directory']).absolute();C.need(C.RUN/'artifacts/labels/source_status_v1' in output.parents and not output.exists(),'FRESH_OUTPUT_ONLY_NO_OLD_BOOK')
    binding={'schema':'FULL_LOGICAL_OWNER_PLAN_RESOURCE_BINDING_V2','scientific_config_reference':cr,'scope_key':C.KEY,'scope_parameters':C.PARAMETERS,
      'resource_authority_reference':cfg['resource_authority_reference'],'memavailable_soft_floor_bytes':4<<30,'resource_evidence_local_cap_bytes':64<<20,
      'resource_evidence_output':str(output)+'_resource_observation'}
    br=I.save(root/'resource_binding.json',binding);argv=[M.PY,'-B','-m',C.MODULE,'--config',cr['path'],'--startup-proof','__ROOT_STARTUP_PROOF__','--output',str(output)]
    scope={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'ROOT_REVIEW_REQUIRED','reviewer':None,'reason':None,
      'resource_authority_reference':cfg['resource_authority_reference'],'kind':'analysis','pilot':False,'scope_key':C.KEY,'scope_parameters':C.PARAMETERS,
      'scope_mode':'BOUNDED_METADATA_PREPARATION','wall_seconds':cfg['wall_seconds'],'estimated_peak_output_bytes':C.CAP,'stage_output_cap_bytes':C.CAP,
      'source_status_stage':None,'execution_argv':argv,'bounded_batch_limits_reviewed':True,'profile_reviewed':True,'approved_profile_reference':req['baseline_parent']['manifest'],
      'parent_evidence_references':M.unique([*brefs,*frefs,prep_ref,*req['source_mapping_evidence_references']]),'new_full_plan_not_old_null':True,
      'all_other_future_caps_reviewed':True,'other_output_cap_bytes':cfg['other_output_cap_bytes'],'labels_or_numeric_calibration_read':False,'final_Common_D4_authorized':False}
    sr=I.save(root/'scope_candidate.json',scope);I.save(root/'candidate.json',{'config_reference':cr,'binding_reference':br,'scope_candidate':sr,'DATA_opened_or_hashed_on_login':False})

def finalize(a):
    root=Path(a.directory);candidate=I.load(root/'scope_candidate.json');approved=I.load(a.scope_review)
    C.need(approved['status']=='APPROVED_FOR_EXACT_STAGE' and approved['reviewer']=='root' and approved['reason'].strip(),'SEPARATE_ROOT_EXACT_SCOPE_SIGNATURE')
    for key,value in candidate.items():
        if key not in ('status','reviewer','reason'):C.need(approved[key]==value,'EXACT_SCOPE_FIELD:'+key)
    meta=I.load(root/'candidate.json');cfg=I.load(I.require(meta['config_reference']));review=I.pin(a.scope_review)
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1','kind':'analysis','pilot':False,'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
      'wall_seconds':cfg['wall_seconds'],'estimated_peak_output_bytes':C.CAP,'stage_output_cap_bytes':C.CAP,'source_status_stage':None,
      'execution_argv':approved['execution_argv'],'source_references':M.unique([*cfg['source_references'],*cfg['small_references'],meta['config_reference'],meta['binding_reference'],review]),
      'data_references':cfg['data_references'],'scope_key':C.KEY,'scope_parameters':C.PARAMETERS,
      'scope':{'mode':approved['scope_mode'],'review':review,'parent_profile':approved['approved_profile_reference']},'producer_resource_binding_reference':meta['binding_reference']}
    I.save(root/'stage_spec.json',spec)

def freeze(a):
    req=I.load(a.request);C.need(req['schema']=='ROOT_FULL_LOGICAL_OWNER_PLAN_ACTUAL_FREEZE_REQUEST_V2','EXACT_POST_ACTUAL_REQUEST')
    parent=req['actual_parent'];manifest,refs=actual(parent);cfg=I.load(I.require(manifest['config']));proof=I.load(I.require(parent['proof']))
    expected=[M.PY,'-B','-m',C.MODULE,'--config',manifest['config']['path'],'--startup-proof',parent['proof']['path'],'--output',str(Path(parent['manifest']['path']).parent)]
    C.need(proof['request']['execution_argv']==expected and proof['request']['scope_key']==C.KEY and proof['request']['scope_parameters']==C.PARAMETERS,'EXACT_ACTUAL_NEW_PRODUCER_PRIMARY_AND_ALL_OPTIONS')
    C.need(str(manifest['job_id'])==str(proof['job_id']) and manifest['schema']=='FULL_LOGICAL_OWNER_PLAN_BUILD_RECEIPT_V2' and manifest['status']=='CPU_GENERATED_NOT_ROOT_FROZEN_NOT_NUMERIC_COVERAGE'
      and manifest['records']==11231854 and manifest['molecules']==1220466 and len(manifest['actual_worker_pids'])==16,'ACTUAL_FULL_IDENTITY_CLOSURE_REQUIRED')
    planref=manifest['group_plan_reference'];plan=I.load(I.require(planref));C.need(plan['records']==11231854 and plan['molecules']==1220466 and len(plan['groups'])==manifest['source_groups']
      and plan['old_books_or_HOLD_modified'] is False and plan['new_plan_frozen_by_this_process'] is False,'UNCHANGED_NEW_PLAN_NOT_OLD_ACCEPTANCE')
    reviewref=req['root_actual_freeze_review_reference'];review=I.load(I.require(reviewref))
    C.need(review['schema']=='ROOT_FULL_LOGICAL_OWNER_PLAN_ACTUAL_FREEZE_REVIEW_V2' and review['status']=='ROOT_APPROVED_ACTUAL_C0_NEW_FULL_LOGICAL_PLAN'
      and review['reviewer']=='root' and review['reason'].strip() and review['actual_parent']==parent and review['group_plan_reference']==planref
      and review['old_full_null_not_retroactively_changed'] is True and review['full_numeric_dispatch_authorized'] is False,'SEPARATE_POST_C0_ROOT_FREEZE_NOT_PRODUCTION_RELEASE')
    output=Path(a.output).absolute();C.need(C.RUN/'control' in output.parents and not output.exists(),'FRESH_SMALL_AUTHORITY_FILE')
    I.save(output,{'schema':'ROOT_FROZEN_FULL_LOGICAL_OWNER_PLAN_AUTHORITY_V2','status':'ACTUAL_C0_ROOT_FROZEN_SOURCE_ORDER_NOT_FINAL_COMMON_D4',
      'logical_group_plan_reference':planref,'root_actual_freeze_review_reference':reviewref,'actual_parent':parent,'actual_parent_evidence_references':refs,
      'records':11231854,'molecules':1220466,'roles':manifest['roles'],'source_groups':manifest['source_groups'],'source_file_order_preserved':True,
      'TSQR_chunk':256,'ordered_left_fold':True,'old1904_remains_TIMEOUT':True,'old_books_or_HOLD_modified':False,
      'numeric_full_requires_original_compact14_actual512_exact_profile':True,'final_Common_D4':False,'full_numeric_dispatch_authorized':False})

def main():
    C.need(hasattr(os,'getuid') and os.getuid()==1278,'MAIN_LOGIN_METADATA_ONLY_NO_WINDOWS_PROJECT_PYTHON')
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    for name in ('candidate','freeze'):
        q=sub.add_parser(name);q.add_argument('--request',required=True);q.add_argument('--output',required=True)
    q=sub.add_parser('finalize');q.add_argument('--directory',required=True);q.add_argument('--scope-review',required=True)
    a=p.parse_args();{'candidate':candidate,'finalize':finalize,'freeze':freeze}[a.action](a)
if __name__=='__main__':main()
