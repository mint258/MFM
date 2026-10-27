"""Small primary-source authority; initial scientific archive has no invented SHA."""
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
ROOT=Q.ROOT;HERE=ROOT/'code/secondary_qm7b_official2013_acquisition_v1'
FILES=('__init__.py','contracts.py','guard.py','archive.py','run.py','test_v1.py','README.md')
OLD=ROOT/'code/secondary_external_sources_acquisition_v1';OLD_FILES=('__init__.py','contracts.py','runtime.py','run.py')
KEY='qm7b_official2013_zip_acquisition_alpha_v1';MODULE='secondary_qm7b_official2013_acquisition_v1.run'
PLAN='SECONDARY_QM7B_OFFICIAL2013_ARCHIVE_PLAN_V1';PROOF='SECONDARY_QM7B_OFFICIAL2013_ARCHIVE_STARTUP_V1'
STAGE='AUTHOR_2013_QM7B_OPAQUE_ZIP_SHA_CRC_INVENTORY';SCOPE='OFFICIAL_ARCHIVE_ACQUISITION_NOT_GRAPH_OR_ROW_MAPPING'
URL='https://www.mrupp.info/Data/2013dsgdb7njp.zip';EXPECTED=2671083;DOWNLOAD=16<<20;EXPANDED=256<<20;MEMBERS=20000;CAP=2<<30;WALL=600
PRIMARY_PIN=(7303,'ef7ac8f9faad0d5e7c3b1c7ed009ab7f377e46a42234d8f87a177c7aac2f6e5f');HEAD_PIN=(3752,'5b7e0a4857702019249ad27805e61d2e2870c1523e038ba23e128c5c09dc56a8')
PARAMETERS={'exact_single_URL':URL,'expected_original_HEAD_bytes':EXPECTED,'maximum_GET_attempts':1,'HTTP_redirects_retries_mirrors_or_ranges':False,
    'HTTP403_429':'STOP_RESPONSE_PREFIX_RETAINED_NO_RETRY','maximum_download_body_bytes':DOWNLOAD,'maximum_total_uncompressed_bytes':EXPANDED,
    'maximum_ZIP_members':MEMBERS,'complete_whole_SHA_stable_FD_and_all_member_EOF_CRC_SHA':True,'original_compressed_and_uncompressed_bytes_preserved':True,
    'member_files_extracted_or_executed':False,'opaque_uncompressed_storage':'SINGLE_STABLE_CONCATENATED_BLOB_WITH_ORDINAL_SEGMENTS',
    'coordinates_SMILES_bonds_or_MAT_row_mapping_parsed_or_inferred':False,'numbered_members_or7211_are_MAT_row_evidence':False,
    'new_graph_parse_key_UFF_QM_calls':0,'new_pure_methods':3,'all3_before_network_DATA_and_Budget':True,'old_fixture_methods_reexecuted':False,
    'initial_archive_SHA_pin_in_plan':False,'input_DATA_files':0,'allocated_cpus':16,'network_reader_processes':1,'output_cap_bytes':CAP,'wall_seconds':WALL,
    'HEAD_or_response_length_mismatch':'ACTUAL_BOUNDED_RESPONSE_RETAINED_HOLD_NOT_ARCHIVE_ACCEPTANCE','resource_stop':'NATURAL_PREFIX_HOLD_NO_SIGNAL',
    'original_unknowns_changed':False,'automatic_graph_pool_identity_decontamination_release':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
    'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')


def unique(refs):
    result={}
    for ref in refs:Q.normalized(ref);Q.need(ref['path'] not in result or result[ref['path']]==ref,'CONFLICTING_SMALL_SOURCE_PIN');result[ref['path']]=ref
    return [result[p] for p in sorted(result)]


def exact_url(value):Q.need(isinstance(value,str) and value==URL,'ONLY_EXACT_AUTHOR_2013_URL_NO_ALTERNATES');return value


def inputs(plan):
    refs=[plan['primary_research_reference'],plan['official_HEAD_reference']]
    for ref,pin in zip(refs,(PRIMARY_PIN,HEAD_PIN)):
        Q.normalized(ref);p=Q.literal(ref['path']);Q.need(ROOT/'metadata' in p.parents and (ref['bytes'],ref['sha256'])==pin,'EXACT_BYTE_COPIED_PRIMARY_SMALL_SOURCE_NOT_DATA');Q.verify(ref)
    head=Q.load_ref(refs[1]);Q.need(head['schema']=='QM7B_OFFICIAL_CANDIDATE_HTTP_METADATA_ONLY_V1' and head['status']=='OFFICIAL_LOCATORS_FOUND_GRAPH_AND_MAT_ROW_MAPPING_UNKNOWN'
        and head['archive_contents_or_graph_or_SMILES_or_mapping_proven'] is False and head['files_saved_from_scientific_archive_response_body']==0,'ACTUAL_METADATA_ONLY_RESEARCH_NOT_GRAPH_OR_PAYLOAD_ACCEPTANCE')
    rows=[v for v in head['actual_HEAD_observations'] if v['requested_url']==URL]
    Q.need(len(rows)==1 and rows[0]['actual_response_url']==URL and rows[0]['method']=='HEAD' and rows[0]['status_code']==200
        and rows[0]['content_length']==EXPECTED and rows[0]['content_type']=='application/zip' and rows[0]['payload_body_opened'] is False
        and rows[0]['payload_SHA256_MD5_CRC_or_archive_members_observed'] is False,'EXACT_ACTUAL_AUTHOR_URL_HEAD200_LENGTH_NOT_CONTENT_SHA')
    matches=[v for v in head['source_pages'] if v.get('url')=='https://www.mrupp.info/publications.html' and v.get('actual_relative_href')=='Data/2013dsgdb7njp.zip']
    Q.need(len(matches)==1 and matches[0]['resolved_archive_url']==URL and matches[0]['publication_DOI']=='10.1088/1367-2630/15/9/095003','ACTUAL_ORIGINAL_AUTHOR_2013_PUBLICATION_LINK')
    Q.need(plan.get('data_references',[])==[],'NO_PRETENDED_PREEXISTING_ARCHIVE_SHA_OR_DATA')
    if 'source_references' in plan:
        Q.need(all(r in plan['source_references'] and r in plan['parent_evidence_references'] for r in refs),'BOTH_ACTUAL_RESEARCH_PINS_REVIEWED')
    return {'source_URL':URL,'actual_HEAD':rows[0],'parents':refs,'original_graph_SMILES_MAT_row_mapping':'UNKNOWN'}
