"""Actual866/856/792/acquisition chain; four producer DATA locators, no login body IO."""
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_moleculenet_csv6_identity_v1.guard import account
from secondary_moleculenet_native4_full_v1.contracts import data_locator
ROOT=Q.ROOT;HERE=ROOT/'code/secondary_pdbbind_index27_extract_v1'
FILES=('__init__.py','contracts.py','guard.py','projection.py','run.py','test_v1.py','README.md')
KEY='pdbbind_general_unresolved27_original_index_alpha_v1';MODULE='secondary_pdbbind_index27_extract_v1.run'
PLAN='SECONDARY_PDBBIND_UNRESOLVED27_INDEX_PLAN_V1';PROOF='SECONDARY_PDBBIND_UNRESOLVED27_INDEX_STARTUP_V1'
STAGE='PDBBIND_GENERAL27_ORIGINAL_INDEX_ROWS_AND_FROZEN_SOURCE_MAPPING';SCOPE='OPAQUE_INDEX_EVIDENCE_NO_GRAPH_OR_KEY_COMPUTATION'
CAP=2<<30;WALL=600;INDEX='v2019-other-PL/index/INDEX_general_PL_data.2019';N=27;INDEX_N=17679
COUNTS={'qm8_sdf':21786,'pdbbind_core':193,'pdbbind_general':17679,'pdbbind_refined':4852}
MISSING={'qm8_sdf':0,'pdbbind_core':0,'pdbbind_general':27,'pdbbind_refined':0}
DATA_BYTES=1927276053;NATIVE=ROOT/'code/secondary_moleculenet_native4_identity_v1'
PARAMETERS={'full_inventory_job':'1884866','native_context_job':'1884856','format_job':'1884792','original_source_id':'pdbbind_general',
    'relation_rows':44510,'relation_counts':COUNTS,'no_native_context_counts':MISSING,'selected_unresolved_index_rows':27,
    'original_index_noncomment_rows':17679,'original_index_member':INDEX,'selection':'EXACT_RECORDED_NO_NATIVE_CONTEXT_IN_ALL_COMPONENTS',
    'all_source_fields_ID_zeroes_case_and_original_ordinals_preserved':True,'four_DATA_files':4,'four_DATA_bytes':DATA_BYTES,
    'DATA_locator_has_small_metadata_ceiling':False,'all4_current_whole_SHA_stable_FD_before_decoding':True,
    'whole_TAR_inventory_every_regular_member_SHA_and_gzip_EOF_CRC':True,'raw_original_line_bytes_only_DATA_no_affinity_decode':True,
    'index_grammar':'ORIGINAL_NON_COMMENT_LINE_FIRST4_BYTES_AND_ZERO_BASED_ORDINAL_NO_STRIP',
    'original_source_projection_and_line_length_SHA_exact_binding':True,'version_source_labels_prove_missing_structure_cause':False,
    'source_version_and_download_mapping_evidence_only_DATA':True,'summary_contains_IDs_SMILES_raw_lines_or_target_values':False,
    'new_pure_methods':3,'all3_before_any_original_DATA_and_Budget':True,'new_SDF_MOL2_graph_parses_keys_UFF_QM_network_calls':0,
    'workerlog_or_EOF_graph_failure_causal_diagnosis':False,'general12119_key_UNKNOWN_is_the27_index_gap':False,
    'original_UNKNOWN_or_source_assets_modified':False,'allocated_cpus':16,'reader_processes':1,'whole_output_cap_bytes':CAP,'wall_seconds':WALL,
    'time_or_resource_shortfall':'PARTIAL_HOLD_NOT_COMPLETE','automatic_structure_identity_pool_decontamination_release':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
    'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')


def unique(refs):
    out={}
    for r in refs:Q.normalized(r);Q.need(r['path'] not in out or out[r['path']]==r,'CONFLICTING_SMALL_REFERENCE');out[r['path']]=r
    return [out[k] for k in sorted(out)]


def small(ref):
    Q.normalized(ref);p=Q.literal(ref['path'])
    Q.need(p.suffix=='.json' or ROOT/'control' in p.parents,'SMALL_JSON_OR_CONTROL_RAW_ONLY')
    Q.need(any(ROOT/x in p.parents for x in ('control','metadata','code')) or p.name in ('receipt.json','pdbbind_general.json'),
        'NO_SCIENTIFIC_BODY_AS_SMALL_METADATA');return ref


def discover(value):
    refs=[]
    def meta(ref):small(ref);refs.append(ref);return Q.load_ref(ref)
    def acct(ref,job):
        a=meta(ref);raw=a['raw_sacct_reference'];Q.normalized(raw);Q.need(ROOT/'control' in Q.literal(raw['path']).parents,'ACCOUNT_RAW_METADATA_ONLY');refs.append(raw)
        return account(ref,job,refs)
    rr=value['full_inventory_receipt_reference'];Q.need(rr['path']==str(ROOT/'artifacts/moleculenet_native4_full_inventory_v1/v2/receipt.json'),'EXACT_ACTUAL866_RECEIPT_PATH')
    r=meta(rr);acct(value['full_inventory_accounting_reference'],'1884866')
    Q.need(r['schema']=='SECONDARY_NATIVE4_FULL_PHYSICAL_INVENTORY_RECEIPT_V1' and r['status']=='ALL39633_SDF_ATTEMPT_RESULTS_AND_ORIGINAL_CONTEXT_RECORDED_UNKNOWNS_RETAINED'
        and r['job_id']=='1884866' and r['uid']==1264 and r['endpoint']==Q.ENDPOINT and r['node']=='compute-0-6'
        and r['automatic_fallback_policy_graph_pool_decontamination_training_release'] is False,'ACTUAL866_NOT_IDENTITY_ACCEPTANCE')
    Q.need(r['all_original_index_relations']['all_ID_rows_by_source']==COUNTS and r['all_original_index_relations']['ID_rows_without_matching_existing_native_context']==MISSING,
        'EXACT44510_AND_GENERAL_ONLY27_CURRENT_CONTEXT_GAPS')
    Q.need(r['fixtures']['tests_run']==3 and not any(r['fixtures'][k] for k in ('failures','errors','skips','expected_failures','unexpected_successes')),
        'ACTUAL866_NEW3_PURE_PASS_IS_HISTORICAL_NOT_CURRENT_FIXTURES')
    for k in ('plan_reference','startup_proof_reference'):meta(r[k])
    fullplan=Q.load_ref(r['plan_reference']);fullproof=Q.load_ref(r['startup_proof_reference'])
    Q.need(str(fullproof['job_id'])=='1884866' and fullproof['uid']==1264 and fullproof['endpoint']==Q.ENDPOINT
        and fullproof['plan_reference']==r['plan_reference'] and fullplan['scope_parameters']==r['scope_parameters'],'REAL866_PLAN_AND_PROOF')
    p=meta(r['native_profile_receipt_reference']);acct(r['native_profile_accounting_reference'],'1884856')
    Q.need(p['job_id']=='1884856' and p['uid']==1264 and p['endpoint']==Q.ENDPOINT,'REAL856_SOURCE_CONTEXT')
    op=meta(p['plan_reference']);meta(p['startup_proof_reference'])
    authority_ref=op['format_authority_reference'];Q.need(authority_ref==Q.ref(NATIVE/'authority792.json'),'UNCHANGED_ORIGINAL_AUTHORITY792_SOURCE')
    authority=meta(authority_ref);fmt=meta(authority['format_receipt_reference']);fp=meta(authority['format_plan_reference']);meta(authority['format_proof_reference'])
    acct(op['format_accounting_reference'],'1884792')
    Q.need(fmt['job_id']=='1884792' and fmt['uid']==1264 and fmt['endpoint']==Q.ENDPOINT and fmt['status']=='FORMAT_METADATA_PROFILE_COMPLETE_IDENTITY_ACCEPTANCE_PENDING',
        'ACTUAL792_OFFICIAL_FORMAT_PARENT_NOT_IDENTITY_ACCEPTANCE')
    general=[v for v in authority['sources'] if v['source_id']=='pdbbind_general'];Q.need(len(general)==1,'ONE_ORIGINAL_GENERAL_SOURCE');general=general[0]
    report=meta(general['format_report_reference']);Q.need(report['source_id']=='pdbbind_general' and report['payload_reference']==general['payload_reference']
        and report['inventory']['inventory_reference']==general['inventory_reference'],'EXACT792_GENERAL_PAYLOAD_AND_INVENTORY')
    acquisition=meta(fp['acquisition_receipt_reference']);acct(fp['acquisition_accounting_reference'],'1884784')
    Q.need(acquisition['schema']=='SECONDARY_EXTERNAL_SOURCE_ACQUISITION_RECEIPT_V1' and acquisition['status']=='OFFICIAL_ELEVEN_SOURCE_CONTAINER_ACQUISITION_COMPLETE'
        and acquisition['job_id']=='1884784' and acquisition['uid']==1264 and acquisition['endpoint']==Q.ENDPOINT,'ORIGINAL_OFFICIAL_ACQUISITION_CLOSED')
    ap=meta(acquisition['plan']);meta(acquisition['startup_proof']);catalog=meta(fp['locator_catalog_reference'])
    Q.need(ap['locator_catalog_reference']==fp['locator_catalog_reference'] and acquisition['locator_catalog_sha256']==fp['locator_catalog_reference']['sha256']
        and catalog['official_loader_commit']==authority['official_loader_commit'],'UNCHANGED_FROZEN_OFFICIAL_SOURCE_CATALOG_AND_LOADER')
    entries=[v for v in catalog['entries'] if v['source_id']=='pdbbind_general'];sources=[v for v in acquisition['sources'] if v['source_id']=='pdbbind_general']
    Q.need(len(entries)==len(sources)==1,'ONE_BOUND_GENERAL_VERSION_SOURCE');entry=entries[0];source=sources[0]
    Q.need(source['payload_reference']==general['payload_reference'] and source['container']['inventory_reference']==general['inventory_reference']
        and source['url']==entry['url'] and source['status']=='COMPLETE_CONTAINER_OBSERVED','ACTUAL_OFFICIAL_DOWNLOAD_MAPPING_NOT_NEW_URL')
    head=meta(ap['head_receipt_reference']);obs=[v for v in ap['head_observation_references'] if v['source_id']=='pdbbind_general'];Q.need(len(obs)==1,'ORIGINAL_GENERAL_HEAD_OBSERVATION')
    observed_head=meta(obs[0]['reference'])
    Q.need(head['job_id']=='4521094' and source['container']['gzip_EOF_CRC_verified'] is True,'ORIGINAL_HEAD_AND_FULL_GZIP_PRODUCER')
    data=[r['all_original_index_relations']['reference'],p['source_rows_reference'],general['payload_reference'],general['inventory_reference']]
    for ref in data:data_locator(ref)
    Q.need(len({v['path'] for v in data})==4 and sum(v['bytes'] for v in data)==DATA_BYTES,'FOUR_ACTUAL_PRODUCER_LOCATORS_AND_COMBINED_BYTES')
    v=source['container'];expected={'members':v['tar_members'],'regular_bytes':v['regular_member_total_bytes'],'decoded_bytes':v['decoded_stream_bytes'],'decoded_sha256':v['decoded_stream_sha256']}
    Q.need(expected['members']==64016 and expected['regular_bytes']==7221482449 and expected['decoded_bytes']==7267440640,'EXACT_ORIGINAL_GENERAL_CONTAINER_CENSUS')
    projected=[v for v in p['projection'] if v['source_id']=='pdbbind_general'];Q.need(len(projected)==1,'ONE_CLOSED856_GENERAL_PROJECTION');projected=projected[0]
    Q.need(projected['complete_gzip_EOF_CRC'] is True and projected['decoded_tar_sha256']==expected['decoded_sha256'] and projected['decoded_tar_bytes']==expected['decoded_bytes']
        and projected['members']==expected['members'],'ACQUISITION_AND856_FULL_SOURCE_DECODE_AGREE')
    mapping={'schema':'PDBBIND_GENERAL_FROZEN_DOWNLOAD_AND_VERSION_EVIDENCE_DATA_V1','source_id':'pdbbind_general','original_index_member':INDEX,
        'official_loader_commit':authority['official_loader_commit'],'catalog_entry':entry,'original_acquisition_source':source,'original_HEAD_observation':observed_head,
        'actual_source_catalog_reference':fp['locator_catalog_reference'],'source_authority_reference':authority_ref,'format_report_reference':general['format_report_reference'],
        'source_version_labels_are_not_missing_structure_cause_or_complete_release_proof':True,'missing_structure_reason':'UNKNOWN','original_graph_UNKNOWNs_unchanged':True}
    return {'full':r,'profile':p,'full_plan':fullplan,'profile_plan':op,'format_plan':fp,'acquisition_plan':ap,
        'data':data,'parents':unique(refs),'expected_container':expected,'version_mapping_DATA':mapping}


def inputs(plan):
    d=discover(plan);Q.need(plan['data_references']==d['data'] and plan['scope_parameters']==PARAMETERS,'EXACT_FOUR_DATA_AND_FIXED_SCOPE')
    Q.need(all(r in plan['parent_evidence_references'] and r in plan['source_references'] for r in d['parents']),'ALL_ACTUAL_SMALL_PARENT_AND_VERSION_PINS')
    return d
