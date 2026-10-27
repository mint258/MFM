"""Stdlib Root candidate/finalize helper. Scientific DATA are locators only."""
import argparse,copy,json,os
from pathlib import Path
from . import contract as C
from workflows.data_v1_final.labels.bounded_projection_v1 import materialize as M


def actual(parent):
    for name in ('manifest','proof','accounting','raw'):C.reference(parent[name])
    p,refs=M.actual_parent(*(parent[k]['path'] for k in ('manifest','proof','accounting','raw')))
    C.actual_c0(M.load(parent['accounting']['path']),p['job_id']);manifest=M.load(parent['manifest']['path'])
    proof=M.load(parent['proof']['path']);request=proof['request'];module={C.BATCH:'run',C.COVERAGE:'coverage','COMPACT_NUMERIC_TRAIN_STATISTICS_V1':'statistics'}.get(manifest['schema'])
    C.need(module is not None,'ONLY_ACTUAL_THIS_NAMESPACE_PARENT_SCHEMAS')
    argv=[M.PY,'-B','-m','workflows.data_v1_final.labels.normalization_compact_runtime_v1.'+module,'--config',manifest['config']['path'],
      '--startup-proof',parent['proof']['path'],'--output',str(Path(parent['manifest']['path']).parent)]
    C.need(request['execution_argv']==argv,'EXACT_ACTUAL_PARENT_PRIMARY_ALL_OPTIONS')
    return manifest,refs


def sources(baseline):
    paths=[C.HERE/'README.md']
    for name in ('normalization_compact_runtime_v1','normalization_typed_cache_v1','bounded_projection_v1','full_projection_v1','footer_inventory_v1',
      'lossless_projection_pilot_v1','payload_audit_v1','source_status_cpu_auto_memory_v1','source_status_v1','streaming_v1','normalization_cache_v1','normalization_cache_v2','normalization_v1','size_cpu_v2','size_semantics_v1'):
        paths.extend((C.REPO/'workflows/data_v1_final/labels'/name).glob('*.py'))
    paths.extend((C.REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2').glob('*.py'))
    for name in ('__init__.py','shared.py','queue_contract.py'):paths.append(C.REPO/'workflows/data_v1_final/execution/queue_v1'/name)
    # Frozen old plans remain historical. Actual numeric calibration/DATA are
    # reclassified here, never login-hashed merely because old code called them small.
    denied={r['path'] for r in baseline['data_references']}
    if baseline['science'].get('calibration'):denied.add(baseline['science']['calibration']['path'])
    return M.unique([*(M.pin(p) for p in paths),*(r for r in baseline['source_references'] if r['path'] not in denied)])


def candidate(a):
    req=M.load(a.request);C.need(req['schema']=='ROOT_COMPACT_NUMERIC_STAGE_REQUEST_V1' and req['stage'] in C.KEYS,'EXACT_ROOT_REQUEST')
    out=Path(a.output).absolute();C.need(C.RUN/'control' in out.parents and not out.exists(),'FRESH_UNSIGNED_STAGE_METADATA');out.mkdir(parents=True,mode=0o700)
    base_ref=req['baseline512_config_reference'];baseline=M.load(M.require(base_ref));C.need(baseline['schema']=='LOSSLESS_LABEL_PROJECTION_CONFIG_V1','REAL_FROZEN512_BASELINE_CONFIG')
    footer_ref=req['footer_manifest_reference'];footer=M.load(M.require(footer_ref));book,index,streams,footer_small,_=M.footer_inputs(footer)
    C.source_contract(book['files']);files=book['files'];byid={s['file_id']:s for s in files};byname={s['path']:s for s in files}
    logical=req['logical_group_plan_reference'];group_plan=M.load(M.require(logical));groups=group_plan['groups']
    C.need(groups and len({g['source_job_id'] for g in groups})==len(groups),'ORIGINAL_UNSPLIT_LOGICAL_OWNER_GROUPS')
    data=[];parents=[];small=[base_ref,footer_ref,logical,req['technical_review_reference'],req['resource_authority_reference'],M.pin(a.request),*footer_small,*baseline['small_references']]
    prior={};history=[]
    for parent in req.get('batch_history',[]):
        row,refs=actual(parent);parents.extend(refs)
        C.need(row['schema']==C.BATCH and row['mode']==req['mode'] and row['status']=='CLOSED_WINDOWS_ACTUAL_PARENT_ACCOUNTING_REQUIRED'
          and not row['errors'] and not row['unpublished_tickets'] and not row['quality_hold_fields'],'ACTUAL_C0_NO_UNKNOWN_QUALITY_HOLD_CONTINUATION')
        prior=C.advance_cursors(files,prior,row['closed_physical_intervals']);history.append(parent)
    cfg=copy.deepcopy(baseline);cfg.update(schema=C.SCHEMA,stage=req['stage'],scope_key=C.KEYS[req['stage']],mode=req['mode'],geometry_source='pm7',workers=16,
      source_inventory_reference=footer['source_inventory_reference'],logical_group_plan_reference=logical,footer_manifest_reference=footer_ref,
      technical_review_reference=req['technical_review_reference'],resource_authority_reference=req['resource_authority_reference'],batch_history=history,
      whole_output_cap_bytes=req['whole_output_cap_bytes'],wall_seconds=req['wall_seconds'],row_serialized_cap_bytes=64<<20,worker_rss_stop_bytes=3<<30,
      typed_part_cap_bytes=128<<20,max_physical_window_rows=4096,window_soft_target_bytes=32<<20,output_inode_cap=8192,
      quality_new_mask_fraction=.01,TSQR_chunk=256,QR_reduction='ORIGINAL_ORDERED_LEFT_FOLD',new_UFF_QM_calls=0,
      old_books_modified=False,final_Common_D4=False,calibration_state='MATCHED512_ONLY' if req['mode']=='pilot512' else 'PENDING_MATCHED_FULL_SOURCE_TRAIN',
      joint_model_policy_release_reference=None,pending_Pprime='REAL_INDEPENDENT_PPRIME_SOURCE_AND_NATIVE_POLICY_REQUIRED')
    profile_ref=req.get('approved_profile_reference')
    if req['mode']=='full':
        C.need(req.get('accepted_512_profile_parent'),'ACTUAL_NEW512_COMPACT_PROFILE_BEFORE_ANY_FULL_STAGE')
        accepted,prefs=actual(req['accepted_512_profile_parent']);parents.extend(prefs)
        C.need(accepted['schema']=='COMPACT_NUMERIC_TRAIN_STATISTICS_V1' and accepted['mode']=='pilot512' and accepted['legacy_exact_comparison'] is True,'REAL_NEW512_EXACT_LEGACY_MATCH')
        profile_ref=req['accepted_512_profile_parent']['manifest']
    if req['mode']=='pilot512':
        cfg['pilot_groups']=groups;data.extend(g['owner_index'] for g in groups)
    if req['stage']=='project':
        if req['mode']=='pilot512':
            C.need(not history and group_plan['records']==4251 and group_plan['molecules']==512 and len(groups)==16,'EXACT_ORIGINAL512_PILOT_NOT_REPEATED_HISTORY')
            selected={r['path'] for g in groups for r in [*g['base_files'],*g['label_files']]};selected_files=[byname[p] for p in selected]
            selectors=[{'file_id':s['file_id'],'physical_row_lo':0,'physical_row_hi':s['rows']} for s in sorted(selected_files,key=lambda r:r['file_id'])]
            cfg['pilot_groups']=groups;data.extend(g['owner_index'] for g in groups);cfg['max_actual_RGs_per_source']=1<<30
        else:
            pending=[s for s in sorted(files,key=lambda r:r['file_id']) if prior.get(str(s['file_id']),0)<s['rows']]
            C.need(pending,'ALL_SOURCES_ALREADY_CLOSED_USE_CPU_COVERAGE');selected_files=pending[:16]
            selectors=[{'file_id':s['file_id'],'physical_row_lo':prior.get(str(s['file_id']),0),'physical_row_hi':s['rows']} for s in selected_files]
            cfg['max_actual_RGs_per_source']=req.get('max_row_groups_per_source',1024);C.need(type(cfg['max_actual_RGs_per_source']) is int and 1<=cfg['max_actual_RGs_per_source']<=1024,'FINITE_FULL_ACTUAL_RG_TILE')
        selector=M.save(out/'selector.json',{'sources':selectors});cfg['selector_reference']=selector;small.append(selector)
        data.extend([cfg['canonical_index'],*(M.triple(s) for s in selected_files),*(index[s['file_id']]['inventory_reference'] for s in selected_files)])
    elif req['stage']=='coverage':
        C.need(history,'ACTUAL_C0_PROJECT_BATCH_CHAIN_REQUIRED')
        if req['mode']=='full':C.need(all(prior.get(str(s['file_id']),0)==s['rows'] for s in files),'EXACT_PHYSICAL_COVERAGE_BEFORE_FINAL_CPU_NUMERIC_COVERAGE')
        data.extend([cfg['canonical_index'],req['formal_record_index_reference']]);cfg['formal_record_index_reference']=req['formal_record_index_reference']
        # Exact actual-C0 transitive output authority, not a many-MiB DATA locator list.
        # CPU verifies every bound window/part; login never opens numeric part bodies.
        cfg['transitive_batch_output_authority']=[p['manifest'] for p in history]
        small.extend(p['manifest'] for p in history)
    else:
        coverage,prefs=actual(req['coverage_parent']);parents.extend(prefs)
        C.need(coverage['schema']==C.COVERAGE and coverage['mode']==req['mode'] and coverage['status']=='EXACT_NUMERIC_SOURCE_COVERAGE_NOT_FINAL_MASKS'
          and not coverage['quality_hold_fields'] and not coverage['errors'],'ACTUAL_COMPLETE_INDEPENDENT_COMPACT_COVERAGE')
        cfg['coverage_reference']=req['coverage_parent']['manifest'];cfg['statistics_purpose']=req.get('statistics_purpose','legacy512' if req['mode']=='pilot512' else 'element_reference')
        cfg['matched_legacy_profile_reference']=req.get('matched_legacy_profile_reference');cfg['matched_legacy_query_reference']=req.get('matched_legacy_query_reference')
        C.need(cfg['statistics_purpose'] in ('legacy512','diagnostic_median_MAD','element_reference','normalization_quantiles','normalization_moments'),'EXACT_STATISTICAL_ROUTE')
        if cfg['statistics_purpose']=='legacy512':C.need(req['mode']=='pilot512' and cfg['matched_legacy_profile_reference'] and cfg['matched_legacy_query_reference'],'EXACT_LEGACY512_PROFILE_AND_QUERY_ORACLE')
        data.extend([cfg['canonical_index'],coverage['parts_catalog'],coverage['base_index']]);small.append(cfg['coverage_reference'])
        for key in ('matched_legacy_profile_reference','matched_legacy_query_reference'):
            if cfg.get(key):data.append(cfg[key])
        cfg['query_stage_reference']=req.get('query_stage_reference');cfg['previous_statistics_parent']=req.get('previous_statistics_parent')
        if cfg['query_stage_reference']:
            C.need(cfg['previous_statistics_parent'],'QUERY_CONTINUATION_REQUIRES_ACTUAL_C0_PARENT');previous,prevrefs=actual(cfg['previous_statistics_parent']);parents.extend(prevrefs);small.extend(prevrefs)
            C.need(previous['next_query_stage']==cfg['query_stage_reference'] and previous['coverage_reference']==cfg['coverage_reference'] and previous['statistics_purpose']==cfg['statistics_purpose'] and previous['mode']==req['mode'],'EXACT_QUERY_AND_COVERAGE_CONTINUATION');data.append(cfg['query_stage_reference'])
        cfg['element_models_reference']=None;cfg['exact_tail_reference']=None
        if cfg['statistics_purpose'].startswith('normalization_'):
            element,eref=actual(req['element_reference_parent']);parents.extend(eref);small.extend(eref)
            C.need(element['coverage_reference']==cfg['coverage_reference'] and element['mode']==req['mode'] and element['statistics_purpose'] in ('element_reference','legacy512'),'REAL_MATCHED_SOURCE_TRAIN_ELEMENT_REFERENCE_PARENT')
            cfg['element_models_reference']=element['element_reference_models_reference'];data.append(cfg['element_models_reference'])
        if cfg['statistics_purpose']=='normalization_moments':
            tails,tref=actual(req['quantiles_parent']);parents.extend(tref);small.extend(tref)
            C.need(tails['coverage_reference']==cfg['coverage_reference'] and tails['mode']==req['mode'] and tails['statistics_purpose']=='normalization_quantiles'
              and tails['element_models_reference']==cfg['element_models_reference'] and tails['exact_tail_reference'] is not None,'ACTUAL_COMPLETE_EXACT_001_999_PARENT')
            cfg['exact_tail_reference']=tails['exact_tail_reference'];data.append(cfg['exact_tail_reference'])
        cfg['worker_histogram_row_cap']=1000000;cfg['worker_serialized_buffer_cap_bytes']=128<<20
    cfg['scope_parameters']={'stage':req['stage'],'mode':req['mode'],'expected_records':4251 if req['mode']=='pilot512' else 11231854,'expected_molecules':512 if req['mode']=='pilot512' else 1220466,'task_slots':14,'workers':16,'dataset':'PM7_P_D_NUMERIC_VIEW','new_UFF_QM_calls':0,'final_Common_D4':False,
      'old1904_stays_TIMEOUT':True,'quality_fraction':.01,'TSQR_chunk':256,'ordered_left_fold':True,'statistics_purpose':cfg.get('statistics_purpose'),'element_models_reference':cfg.get('element_models_reference'),'exact_tail_reference':cfg.get('exact_tail_reference'),'query_stage_reference':cfg.get('query_stage_reference'),'statistics_fit_role':'TRAIN_ONLY' if req['stage']=='statistics' else None,'cache_preserves_all_source_roles':True,'selector_reference':cfg.get('selector_reference'),'max_actual_RGs_per_source':cfg.get('max_actual_RGs_per_source'),'whole_output_cap_bytes':cfg['whole_output_cap_bytes']}
    registry=M.load(M.require(cfg['science']['sources']['registry']))['fields'];enabled=sorted((f for f in registry if f['status']=='enabled'),key=lambda f:f['field_key'])
    C.need(len(enabled)==146,'ORIGINAL146_FIELD_MAP');derived=[dict(f,field_id=i) for i,f in enumerate(enabled)]
    if req['stage']=='statistics':
        fmap=coverage['field_map_reference'];C.need(M.load(M.require(fmap))==derived,'EXACT_SAME_FROZEN_FIELD_MAP_BYTES_AND_LOCATOR_ACROSS_QUERY_STAGES')
    else:fmap=M.save(out/'field_map.json',derived)
    original_plan=M.load(M.require(baseline['owner_plan']));cfg['field_map_reference']=fmap;cfg['element_basis']=group_plan.get('element_basis',original_plan['element_basis']);small.append(fmap)
    denied={r['path'] for r in baseline['data_references']}
    calibration=baseline['science'].get('calibration')
    if calibration:
        denied.add(calibration['path'])
        if req['mode']=='pilot512' and req['stage']=='project':data.append(calibration)
    code=sources(baseline);small=M.unique([r for r in [*small,*parents] if r['path'] not in denied]);cfg['source_references']=code;cfg['small_references']=small;cfg['data_references']=M.unique(data)
    C.validate_config(cfg);C.technical_review(cfg,M.load(M.require(cfg['technical_review_reference'])));cfgref=M.save(out/'config.json',cfg)
    binding={'schema':'COMPACT_NUMERIC_RESOURCE_BINDING_V1','scientific_config_reference':cfgref,'scope_key':cfg['scope_key'],'scope_parameters':cfg['scope_parameters'],
      'resource_authority_reference':req['resource_authority_reference'],'memavailable_soft_floor_bytes':4<<30,'resource_evidence_local_cap_bytes':64<<20,
      'resource_evidence_output':req['output_directory']+'_resource_observation'};bp=M.save(out/'resource_binding.json',binding)
    entry={'project':'run','coverage':'coverage','statistics':'statistics'}[req['stage']]
    argv=[M.PY,'-B','-m','workflows.data_v1_final.labels.normalization_compact_runtime_v1.'+entry,'--config',cfgref['path'],'--startup-proof','__ROOT_STARTUP_PROOF__','--output',req['output_directory']]
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'ROOT_REVIEW_REQUIRED','reviewer':None,'reason':None,
      'resource_authority_reference':req['resource_authority_reference'],'kind':'analysis','pilot':req['mode']=='pilot512','scope_key':cfg['scope_key'],'scope_parameters':cfg['scope_parameters'],
      'scope_mode':'BOUNDED_PERFORMANCE_BATCH' if req['mode']=='pilot512' else 'FULL_SOURCE_AFTER_PROFILE','wall_seconds':cfg['wall_seconds'],
      'estimated_peak_output_bytes':cfg['whole_output_cap_bytes'],'stage_output_cap_bytes':cfg['whole_output_cap_bytes'],'source_status_stage':None,'execution_argv':argv,
      'bounded_batch_limits_reviewed':True,'profile_reviewed':True,'approved_profile_reference':profile_ref,
      'parent_evidence_references':M.unique(parents),'independent_numeric_view_not_old_book_acceptance':True,'final_Common_D4_authorized':False}
    M.save(out/'scope_candidate.json',review);M.save(out/'stage_candidate.json',{'config_reference':cfgref,'binding_reference':bp,'scope_candidate':M.pin(out/'scope_candidate.json')})


def finalize(a):
    out=Path(a.directory);candidate=M.load(out/'scope_candidate.json');approved=M.load(a.scope_review)
    C.need(approved['status']=='APPROVED_FOR_EXACT_STAGE' and approved['reviewer']=='root' and approved['reason'].strip(),'SEPARATE_EXACT_ROOT_SCOPE_SIGNATURE')
    for k,v in candidate.items():
        if k not in ('status','reviewer','reason'):C.need(approved[k]==v,'EXACT_REVIEW_FIELD:'+k)
    meta=M.load(out/'stage_candidate.json');cfg=M.load(M.require(meta['config_reference']));review=M.pin(a.scope_review)
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1','kind':'analysis','pilot':approved['pilot'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
      'wall_seconds':approved['wall_seconds'],'estimated_peak_output_bytes':approved['estimated_peak_output_bytes'],'stage_output_cap_bytes':approved['stage_output_cap_bytes'],
      'source_status_stage':None,'execution_argv':approved['execution_argv'],'source_references':M.unique([*cfg['source_references'],*cfg['small_references'],meta['config_reference'],meta['binding_reference'],review]),
      'data_references':cfg['data_references'],'scope_key':cfg['scope_key'],'scope_parameters':cfg['scope_parameters'],
      'scope':{'mode':approved['scope_mode'],'review':review,'parent_profile':approved['approved_profile_reference']},'producer_resource_binding_reference':meta['binding_reference']}
    M.save(out/'stage_spec.json',spec)


def main():
    C.need(hasattr(os,'getuid') and os.getuid()==1278,'MAIN_METADATA_ONLY_NO_LOCAL_INTERPRETER')
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    q=s.add_parser('candidate');q.add_argument('--request',required=True);q.add_argument('--output',required=True)
    q=s.add_parser('finalize');q.add_argument('--directory',required=True);q.add_argument('--scope-review',required=True)
    a=p.parse_args();{'candidate':candidate,'finalize':finalize}[a.action](a)

if __name__=='__main__':main()