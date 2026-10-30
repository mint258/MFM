"""Root-only small metadata draft/finalize; no scientific JSON/Parquet/body reads."""
import argparse,copy,csv,io,os,socket
from pathlib import Path
from . import contract as C
P=C.P
REVIEWS=('resume_origin_review_reference','pilot_input_review_reference','projection_origin_review_reference','base_cache_plan_reference','hof_closed_prefix_reuse_review_reference','pilot_priority_review_reference',
    'source_metadata_frame_review_reference','WP5_input_derivation_authority_reference','user_D1_decision_reference',
    'user_D1_design_policy_reference','five_layer_mapping_reference','quota_provider_review_reference',
    'quota_provider_identity_reference','root_carveout_review_reference')
DATA_KEYS=('canonical_index','field_map_reference','logical_group_plan_reference','source_inventory_reference','formal_record_index_reference','footer_manifest_reference')

def references(value):
    if type(value)is dict:
        if {'path','bytes','sha256'}<=set(value):yield C.reference(value,source=value.get('bytes')==0)
        else:
            for v in value.values():yield from references(v)
    elif type(value)is list:
        for v in value:yield from references(v)

def source_paths():
    result=[C.HERE/name for name in C.FILES]
    labels=('common_train_normalization_day_v1','normalization_compact_runtime_v3','normalization_compact_runtime_v2',
        'normalization_typed_cache_v1','normalization_v1','streaming_v1','source_status_cpu_auto_memory_v1',
        'full_projection_v1','bounded_projection_v1','footer_inventory_v1','payload_audit_v1','final_release_v1')
    for parent,names in ((C.REPO/'workflows/data_v1_final/labels',labels),
        (C.REPO/'workflows/data_v1_final/export',('d5_inputs_compound_day_v1','d5_inputs_builder_v1','d5_materialize_cpu_v1','wire_v1','pipeline_v1'))):
        for name in names:result.extend(p for p in (parent/name).iterdir() if p.is_file() and p.suffix in ('.py','.md'))
    result.extend(P.source_paths());result.append(C.REPO/'tools/check_repository.py')
    from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import metadata as OLD
    result.extend(OLD.source_paths())
    from workflows.data_v1_final.export.bounded_old_complete_d5_day_v1 import metadata as NATIVE
    result.extend(NATIVE.source_paths())
    result.extend(C.REPO/'workflows/data_v1_final/execution/cpu_analysis_general_nodes_v1'/name for name in ('__init__.py','contract.py','quota_provider.py'))
    result.extend(p for p in (C.REPO/'workflows/data_v1_final/labels').iterdir() if p.is_file() and p.suffix=='.py')
    from workflows.data_v1_final.export.d5_inputs_builder_v1 import contract as D5
    result.extend(D5.source_paths())
    from workflows.data_v1_final.labels.existing_sprime_native_pilot_day_v1 import metadata as NATIVE_ORIGIN
    result.extend(NATIVE_ORIGIN.source_paths())
    return list(dict.fromkeys(result))

def login():
    C.need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi' and not os.environ.get('SLURM_JOB_ID'),'MAIN_ROOT_METADATA_ONLY_LOGIN_CONTEXT')

def draft(request_path,out):
    login();request_ref=P.pin(request_path);v=C.meta(request_ref)
    C.need(v['schema']=='ROOT_REQUESTED_EXISTING_SPRIME_NATIVE_PILOT_RESUME_V2'
        and v['status']=='REQUESTED_FOR_REVIEW' and v['requested_by']=='root','ROOT_ACTUAL_REQUEST_NOT_PROXY_SIGNED')
    cfg_ref=v['original_coverage_config_reference'];cfg=C.meta(cfg_ref)
    p={key:copy.deepcopy(v[key]) for key in (*REVIEWS,'node','output_directory','whole_output_cap_bytes','formal_record_index_reference','element_basis','field_scope')}
    for key in DATA_KEYS:
        if key not in p:p[key]=copy.deepcopy(cfg[key])
    C.need(all(p[k]==cfg[k] for k in DATA_KEYS if k in cfg),'UNCHANGED_ORIGINAL_NUMERIC_AUTHORITY_REFERENCES')
    p.update(schema='EXISTING_SPRIME_NATIVE_PILOT_RESUME_PLAN_V2',status='ROOT_REVIEW_REQUIRED',reviewer=None,
        cpus=16,requested_cpus=16,workers=16,wall_seconds=86400,softwall_drain_seconds=900,TSQR_chunk=256,
        quality_new_mask_fraction=.01,independent_numeric_replay_required=True,full_Common_D4_D5_D3_D6_release=False,
        original_coverage_config_reference=cfg_ref,cache_transitive_output_origins=[],accepted_prior_output_roots=[],
        statistics_cap_bytes=v['whole_output_cap_bytes'],typed_part_cap_bytes=128<<20,row_serialized_cap_bytes=64<<20,
        worker_rss_stop_bytes=cfg.get('worker_rss_stop_bytes',12<<30),worker_histogram_row_cap=cfg.get('worker_histogram_row_cap',1000000),
        worker_serialized_buffer_cap_bytes=cfg.get('worker_serialized_buffer_cap_bytes',8<<20))
    resumed,old_native,old_native_proof=C.resume_authority(p)
    reuse,qa,origin=C.native_origin(p);base=C.meta(p['base_cache_plan_reference']);projection=C.projection_origins(p)
    from workflows.data_v1_final.conformers.pm7_precache_day_v1.pilot_prepare import policy
    _,scalar_sources,scalar_data=policy(p['pilot_priority_review_reference'],base)
    sources=[request_ref,cfg_ref,*v['source_references'],*(p[k] for k in REVIEWS),*(P.pin(path) for path in source_paths())]
    data=[*v['data_references'],*cfg['data_references'],*scalar_data,base['formal_source'],base['future_shards_reference'],reuse['failed_receipt_reference'],reuse['closed_state_reference'],*(p[k] for k in DATA_KEYS)]
    p['base_registry_reference']=cfg['science']['sources']['registry'];data.append(p['base_registry_reference'])
    # Only closed scalar receipt/DB/list authority, no PM7 cache proof or packets.
    sources.extend(resumed['parent_registration'][k]for k in ('request_reference','submission_reference','proof_reference','plan_reference','accounting_reference','raw_reference'))
    sources.extend(scalar_sources);sources.extend(reuse['actual_CPU_QA_parent_references'])
    sources.extend(reuse['failed_parent_registration'][k] for k in ('request_reference','proof_reference','submission_reference','accounting_reference'))
    sources.append(C.meta(reuse['failed_parent_registration']['accounting_reference'])['raw_sacct_reference'])
    provider=C.meta(p['quota_provider_review_reference'])
    for key in ('provider_source_references','evidence_references'):
        sources.extend(provider.get(key,[]))
    for key in ('marker_reference','probe_reference','count_correction_authority_reference'):
        if provider.get(key) is not None:sources.append(provider[key])
    carve=C.meta(p['root_carveout_review_reference']);sources.extend(carve.get('accounting_basis_references',[]))
    frame=C.meta(p['source_metadata_frame_review_reference']);sources.append(frame['actual_same_storage_mapping_probe_reference'])
    wp5=C.meta(p['WP5_input_derivation_authority_reference'])
    for item in wp5['package_protocol_references']:sources.extend([item['package_reference'],item['protocol_reference']])
    design=C.user_policy(p['user_D1_design_policy_reference'],p['user_D1_decision_reference'])
    mapping=C.meta(p['five_layer_mapping_reference'])
    C.need(mapping['schema']=='USER_FROZEN_D1_V3_FIVE_LAYER_MAPPING_SELECTIONS_V1' and mapping['contract_version']=='v3.0'
        and mapping['selection_authority_reference']==p['user_D1_decision_reference']
        and str(C.REPO/design['five_layer_selections_relative_path'])==p['five_layer_mapping_reference']['path'],'EXACT_PUBLISHED_D1_DESIGN_AND_FIVE_LAYER_SELECTIONS_NOT_FINAL_RELEASE')
    # A later published joint ACK appends to the interface document. The older
    # design's documentation pin is historical lineage, not an executed input.
    historical=[r for r in design['selected_baseline_source_references'] if r['path']==str(C.REPO/'docs/interfaces/training_format_v3.md')]
    p['historical_D1_design_document_references']=historical
    sources.extend(r for r in design['selected_baseline_source_references'] if r not in historical)
    for origin in projection['projection_origins']:
        sources.extend(origin[k] for k in ('accounting_reference','proof_reference','raw_reference'))
        data.append(origin['manifest_reference'])
        sources.extend(origin.get('historical_parent_evidence_references',[]))
        p['cache_transitive_output_origins'].append({'manifest_reference':origin['manifest_reference'],
            'output_root':origin.get('metadata_output_root',origin['parts_output_root']),
            'additional_output_roots':origin.get('parts_output_roots',[origin['parts_output_root']])})
    review=C.meta(p['pilot_input_review_reference']);parents=review['actual_parent_evidence_references']
    C.need(parents,'REAL_NONEMPTY_ACTUAL_PRIOR_PARENTS_REQUIRED_BY_ORIGINAL_CENTRAL_GUARD');sources.extend(parents)
    p['actual_parent_evidence_references']=C.unique([*parents,*[resumed['parent_registration'][k]for k in ('accounting_reference','raw_reference','request_reference','proof_reference')]])
    # Explicit source-name allowlist repairs old containers which listed known
    # source JSON as DATA; every scientific artifact remains DATA regardless size.
    known_sources={str(path) for path in source_paths()};sources=C.unique(sources)
    data=C.unique(r for r in data if r['path'] not in known_sources)
    data_paths={r['path'] for r in data};sources=[r for r in sources if r['path']not in data_paths]
    for r in sources:C.need(P.pin(r['path'])==r,'CURRENT_EXPLICIT_SOURCE_OR_SMALL_METADATA_ONLY')
    p['source_references']=sources;p['data_references']=data;p['scope_parameters']=C.scope(p)
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    return P.write(out/'plan_candidate.json',p)

def stage(plan_path,out,scope_review=None):
    login();plan_ref=P.pin(plan_path);p=C.plan(C.meta(plan_ref));C.native_origin(p);C.projection_origins(p);C.resume_authority(p)
    C.user_policy(p['user_D1_design_policy_reference'],p['user_D1_decision_reference'])
    authority=P.pin(C.REPO/'configs/data_v1/user_cpu_auto_memory_20261026_v1.json')
    argv=[C.PY,'-B','-m',C.MODULE,'--plan',str(plan_path),'--startup-proof','__ROOT_STARTUP_PROOF__']
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'ROOT_REVIEW_REQUIRED','reviewer':None,
        'resource_authority_reference':authority,'kind':'analysis','scope_key':C.KEY,'scope_parameters':C.scope(p),'pilot':False,
        'wall_seconds':86400,'estimated_peak_output_bytes':p['whole_output_cap_bytes'],'stage_output_cap_bytes':p['whole_output_cap_bytes'],
        'execution_argv':argv,'source_status_stage':None,'scope_mode':'BOUNDED_METADATA_PREPARATION',
        'parent_evidence_references':p['actual_parent_evidence_references'],'root_review_reason':None}
    out=Path(out);out.mkdir(parents=True,exist_ok=True);template=P.write(out/'scope_candidate.json',review)
    spec={k:review[k] for k in ('kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv','source_status_stage')}
    spec.update(schema='UNSIGNED_EXISTING_SPRIME_PILOT_DAY_STAGE_INPUTS_V1',cpus=16,memory_policy='SLURM_DEFAULT_UNSPECIFIED',
        source_references=C.unique([*p['source_references'],plan_ref]),data_references=p['data_references'],
        scope={'mode':'BOUNDED_METADATA_PREPARATION','review':None,'parent_profile':None},unsigned_scope_candidate_reference=template)
    if scope_review is not None:
        r=P.pin(scope_review);accepted=C.meta(r)
        for key,value in review.items():
            if key not in ('status','reviewer','root_review_reason'):C.need(accepted[key]==value,'EXACT_ORIGINAL_CENTRAL_SCOPE_FIELD:'+key)
        C.need(accepted['status']=='APPROVED_FOR_EXACT_STAGE' and accepted['reviewer']=='root' and accepted['root_review_reason'],'INDEPENDENT_ROOT_EXACT_SCOPE_REVIEW')
        spec.update(schema='ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1');spec['scope']['review']=r
        spec['source_references']=C.unique([*spec['source_references'],r]);spec.pop('unsigned_scope_candidate_reference')
    return P.write(out/('stage_spec.json' if scope_review else 'stage_inputs_candidate.json'),spec)

def close(registration_path,out):
    """Small actual terminal chain only; no numeric/geometry/cache body read."""
    login();registration_ref=P.pin(registration_path);v=C.meta(registration_ref)
    req=C.meta(v['request_reference']);sub=C.meta(v['submission_reference']);proof=C.meta(v['proof_reference'])
    accounting=C.meta(v['accounting_reference']);receipt=C.meta(v['receipt_reference']);job=str(sub['job_id'])
    C.need(req==sub['request']==proof['request'] and sub['request_reference']==proof['request_reference']==v['request_reference']
        and sub['uid']==proof['uid']==1278 and str(proof['job_id'])==str(receipt['job_id'])==job
        and sub['sbatch_returncode']==0 and req['scope_key']==C.KEY and req['cpus']==16 and req['node'] in ('compute-0-2','compute-0-8','compute-0-9','compute-0-10','compute-0-11','compute-0-12','compute-0-13','compute-0-14','compute-0-15','compute-0-16','compute-0-17','compute-0-18','compute-0-19')
        and req['wall_seconds']==86400,'TRUE_ORIGINAL_GENERIC16_PILOT_REQUEST_SUBMISSION_PROOF_RECEIPT')
    argv=req['execution_argv'];C.need(argv==[C.PY,'-B','-m',C.MODULE,'--plan',receipt['plan_reference']['path'],
        '--startup-proof',v['proof_reference']['path']] and receipt['plan_reference'] in req['source_references'],'EXACT_ACTUAL_PRIMARY_FULLARGV_PLAN_PROOF')
    C.need(accounting['query_returncode']==0 and accounting['uid']==1278 and accounting['raw_sacct_reference']==v['raw_reference'],'REAL_TERMINAL_RAW_ACCOUNT_REFERENCE')
    raw,actual=P.small(v['raw_reference']['path']);C.need(actual==v['raw_reference'],'ACTUAL_PARENT_RAW_BYTE_PIN')
    parents=[r for r in accounting['parents'] if str(r['job_id'])==job];rows=[r for r in csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),delimiter='|') if r['JobIDRaw']==job]
    C.need(len(parents)==len(rows)==1,'EXACT_REQUESTED_ACTUAL_PARENT_IN_RAW_AND_CLOSURE');a=parents[0];r=rows[0]
    C.need(a['state']=='COMPLETED' and a['exit_code']=='0:0' and a['alloc_cpus']==16 and a['node']==req['node']
        and r['State'].split()[0]=='COMPLETED' and r['ExitCode']=='0:0' and r['UID']=='1278' and int(r['AllocCPUS'])==16
        and r['NodeList']==req['node'] and int(r['ElapsedRaw'])==a['elapsed_raw_seconds'],'TRUE_C0_ACTUAL_CPU_NODE_AND_ELAPSED_NOT_STATUS_GUESS')
    C.need(receipt['schema']=='EXISTING_SPRIME_NATIVE_PILOT_RESUME_RECEIPT_V2' and receipt['held']is False and receipt['errors']==[]
        and receipt['full_Common_D2_D3_D4_D5_D6_release']is False,'NO_HELD_OR_GLOBAL_RELEASE_PROMOTION')
    complete=receipt['status']=='PROVISIONAL55K_NATIVE_RANDOM_CONTINUATION_AND_TRAIN_D4_COMPLETE_PENDING_ACTUAL_C0_ROOT_SEAL'
    C.need(complete or receipt['status']=='DAY_DURABLE_PARTIAL_PENDING_EXPLICIT_ROOT_CONTINUATION','NO_UNCLASSIFIED_C0_STATUS_ACCEPTANCE')
    C.need(not complete or receipt['independent_numeric_replay_equal']is True and receipt['r674_report_reference']is not None,'COMPLETE_PILOT_REQUIRES_REAL_TWO_REPLAYS_AND_REPORT')
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    return P.write(out/'root_limited_acceptance_candidate.json',{'schema':'ROOT_ACCEPTED_EXISTING_SPRIME_NATIVE_PILOT_RESUME_COMPONENTS_V2',
        'status':'ROOT_REVIEW_REQUIRED','reviewer':None,'root_review_reason':None,
        'proposed_status':'ACTUAL_C0_BOUNDED_COMPONENTS_ACCEPTED_NOT_FINAL_COMMON' if complete else 'ACTUAL_C0_DURABLE_CHECKPOINTS_ONLY_NOT_COMPLETE_PILOT',
        'actual_parent':{'manifest':v['receipt_reference'],'proof':v['proof_reference'],'accounting':v['accounting_reference'],'raw':v['raw_reference']},
        'registration_reference':registration_ref,'request_reference':v['request_reference'],'submission_reference':v['submission_reference'],
        'component_references':{key:receipt[key] for key in ('population_reference','geometry_reference','coverage_reference','eligibility_reference','typed_reader_config_reference','numeric_repetitions','r674_report_reference','schema_only_header_reference')},
        'pilot_counts':C.PILOT_COUNTS,'complete_55k_components':complete,'full_Common_D2_D3_D4_D5_D6_release':False,
        'future_D3_Family_requires_separate_explicit_bounded_consumer_input_review':True})

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    d=s.add_parser('draft');d.add_argument('--request',required=True);d.add_argument('--output',required=True)
    d=s.add_parser('stage');d.add_argument('--plan',required=True);d.add_argument('--output',required=True);d.add_argument('--scope-review')
    d=s.add_parser('close');d.add_argument('--registration',required=True);d.add_argument('--output',required=True)
    a=p.parse_args();print(draft(a.request,a.output) if a.action=='draft' else (close(a.registration,a.output) if a.action=='close' else stage(a.plan,a.output,a.scope_review)))
if __name__=='__main__':main()
