"""Actual author v3 / format1897 authority; all data locators stay declarative."""
import hashlib
from pathlib import Path
from workflows.expansion.tdc_zip44_identity_main_v1 import contract as T
from workflows.expansion.marcel_drugs_keys_main_v1 import contract as D
Q=T.Q;HERE=Q.REPO/'workflows/expansion/qm7b_native_composition_main_v1'
FILES=('__init__.py','contract.py','projection.py','run.py','test_v1.py','materialize.py','README.md')
OLD=tuple(Q.REPO/n for n in T.OLD)+tuple(D.HERE/n for n in D.FILES)+D.OLD
KEY='qm7b_author_v3_native_composition_main_v1';MODULE='workflows.expansion.qm7b_native_composition_main_v1.run'
STAGE='QM7B_ALL7211_AUTHOR_NATIVE_COMPOSITION_ONLY';CAP=128<<20
RECORD='https://archive.materialscloud.org/records/rmp9p-1k216';DOI='10.24435/materialscloud:2019.0002/v3'
MD5='a0d313a486513690bb172da819a3f622';NAMESPACE='materialscloud:2019.0002/v3:qm7b_coords.xyz'
REASON='QM7B_AUTHOR_XYZ_NATIVE_NON_H_COMPOSITION_GRAPH_IDENTITY_UNPROVEN'
SYMBOL_Z={'H':1,'C':6,'N':7,'O':8,'S':16,'Cl':17}
PARAMETERS={'source_DOI':DOI,'source_record':RECORD,'source_frames':7211,'source_XYZ_bytes':7837328,
    'author_release_FPS_order_is_not_MAT_order':True,'source_ID_basis':'AUTHOR_RELEASE_FILE_FRAME_ORDINAL_LOCATOR_NOT_NATIVE_OR_MAT_ID',
    'native_author_ID_present':False,'maximum_atoms_per_frame':512,'source_comment_values_decoded':False,
    'coordinate_tokens_converted_to_floating_point':False,'coordinate_graph_or_bond_perception':False,
    'frozen_native_composition_and_identity_function_objects':True,'non_H_native_composition_fallback':True,
    'full_InChIKeys_or_WP5_keys_computed':False,'graph_stereo_charge_isotope_or_MAT_mapping_accepted':False,
    'all7211_source_and_result_rows_kept_without_composition_dedup':True,'source_first_fsync_before_composition':True,
    'new_pure_fixture_methods':3,'all3_before_XYZ_body':True,'sequential_source_streams':1,'allocated_cpus':16,
    'output_cap_bytes':CAP,'frozen_drugs_Budget_Writer_dispatch_argument':False,'explicit_original_stop_new_before_every_read':True,
    'runtime_statvfs_not_refreshed_account_quota':True,'new_network_UFF_QM_calls':0,'production_once_opened':False,
    'global_decontamination_pool_training_release':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}


def unique(rows):return D.unique(rows)


def inputs(plan):
    b=T.meta(plan['accepted_format_receipt_reference']);account,raw=D.account(plan['accepted_format_accounting_reference'],b)
    Q.need(b['schema']=='QM7B_AUTHOR_XYZ_FORMAT_OBSERVATION_V1' and b['status']=='ALL7211_NATIVE_XYZ_FRAMES_OBSERVED_GRAPH_AND_MAT_MAPPING_UNRESOLVED'
        and b['job_id']=='4521897' and b['uid']==1278 and b['observed_frames']==7211 and b['whole_SHA_and_EOF_verified'] is True
        and b['published_MD5_match'] is True and b['original_graph_or_stereo_or_MAT_identity_mapping_accepted'] is False
        and b['frames_with_identity_header_tokens']==0 and b['identity_header_key_counts']=={}
        and set(b['symbols'])==set(SYMBOL_Z) and sum(b['atom_count_histogram'].values())==7211,'ACTUAL_FULL1897_FORMAT_C0_NO_GRAPH_OR_NATIVE_ID_CLAIM')
    config=T.meta(b['config_reference']);proof=T.meta(b['startup_proof_reference'])
    Q.need(config['original_XYZ_reference']==b['original_reference']==plan['data_references'][0] and len(plan['data_references'])==1
        and config['published_XYZ_MD5']==MD5 and config['source_record']==RECORD and config['graph_or_MAT_mapping_release'] is False
        and proof['job_id']==b['job_id'] and proof['uid']==1278 and proof['request']['node']==b['node']
        and proof['request']['scope_key']=='qm7b_materialscloud_v3_xyz_format_v2' and b['config_reference'] in proof['request']['source_references'],
        'ACTUAL_FORMAT_PLAN_PROOF_AND_ORIGINAL_XYZ_BINDING')
    source=Path(plan['data_references'][0]['path']);Q.need(source.is_absolute() and Q.ROOT/'artifacts' in source.parents and '..' not in source.parts
        and plan['data_references'][0]['bytes']==7837328,'ONLY_LITERAL_ORIGINAL_AUTHOR_XYZ_DATA')
    transport=T.meta(plan['author_transport_reference'])
    Q.need(transport['schema']=='OFFICIAL_PUBLIC_DATA_TRANSPORT_INTEGRITY_V1' and transport['status']=='ALL3_HTTP200_AND_PUBLISHED_MD5_MATCH'
        and transport['source_record']==RECORD and transport['source_DOI']==DOI and transport['version']=='v3','ACTUAL_AUTHOR_V3_TRANSPORT_NOT_AN_ALTERNATE_GRAPH_SOURCE')
    files={Path(r['path']).name:r for r in transport['files']};xyz=files['qm7b_coords.xyz']
    Q.need({k:xyz[k] for k in ('path','bytes','sha256')}==plan['data_references'][0] and xyz['published_MD5']==MD5,'PUBLISHED_AUTHOR_MD5_AND_CURRENT_EXPECTED_SOURCE_TRIPLE')
    refs=[plan['accepted_format_receipt_reference'],plan['accepted_format_accounting_reference'],raw,b['config_reference'],b['startup_proof_reference'],plan['author_transport_reference']]
    for name in ('README.txt','files_description.md'):
        r={k:files[name][k] for k in ('path','bytes','sha256')};Q.need(r['bytes']<=2<<20 and Q.pin(r['path'])==r
            and hashlib.md5(Q.read_small(r['path'])).hexdigest()==files[name]['published_MD5'],'REAL_SMALL_AUTHOR_METADATA_HASH_AND_PUBLISHED_MD5');refs.append(r)
    policy=T.meta(plan['decontamination_policy_reference']);Q.need(policy['schema']=='expansion_decontamination_sources_v1'
        and policy['identity_policy']['exact']=='full_inchikey' and policy['identity_policy']['wp5']=='inchikey_first14+colon+last_protonation_character'
        and policy['identity_policy']['unresolved']=='conservative_non_h_element_composition_when_original_graph_identity_unavailable','UNCHANGED_EXISTING_CONSERVATIVE_COMPOSITION_POLICY')
    refs.append(plan['decontamination_policy_reference'])
    failed=config['previous_failed_parent_accounting_reference'];failure=T.meta(failed);fr=failure['raw_sacct_reference']
    Q.need(failure['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and failure['endpoint']=='202.38.247.57:22'
        and failure['uid']==1278 and failure['query_returncode']==0 and failure['parents'][0]['job_id']=='4521888'
        and failure['parents'][0]['state']=='FAILED' and Q.pin(fr['path'])==fr,'ORIGINAL_FAILED_FORMAT1888_AND_COST_RETAINED');refs.extend((failed,fr))
    for relative,(size,sha) in T.FROZEN.items():
        r=Q.pin(Q.REPO/relative);Q.need(r['bytes']==size and r['sha256']==sha,'UNCHANGED_FROZEN_IDENTITY_KERNEL_BYTES')
    return b,unique(refs)
