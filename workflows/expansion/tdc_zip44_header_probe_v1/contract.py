"""One Main CPU protocol and producer-metadata-only input validation."""
import copy,re
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q

HERE=Q.REPO/'workflows/expansion/tdc_zip44_header_probe_v1'
FILES=('__init__.py','contract.py','projection.py','run.py','test_v1.py','materialize.py','README.md')
OLD=Q.REPO/'workflows/expansion/secondary_missing11_identity_format_probe_v1'
KEY='tdc_zip44_header_only_main_v1';MODULE='workflows.expansion.tdc_zip44_header_probe_v1.run'
STAGE='TDC_ORIGINAL_ZIP44_HEADER_AND_STRUCTURE_METADATA_ONLY'
PARAMETERS={'official_dataverse_file_id':'4426004','source_payload_bytes':1472501,'ZIP_entries':68,'CSV_members':44,
 'CSV_endpoint_directories':22,'CSV_decoded_bytes':5428641,'all_regular_decoded_bytes':5434789,'maximum_CSV_member_bytes':632718,
 'original_feed_finish_append_finish_field_method_objects':True,'new_header_and_summary_seams_only':True,
 'new_pure_fixture_methods':3,'all3_fixtures_before_any_original_ZIP_body_read':True,'selected_data_columns':0,
 'identity_or_assay_data_fields_text_decoded':False,'identity_or_assay_data_fields_persisted':False,
 'literal_headers_persisted':True,'ID_or_SMILES_column_semantics_assigned':False,'original_train_val_test_names_preserved':True,
 'physical_CSV_records_are_effective_molecules':False,'maximum_active_member_readers':1,'sixteen_busy_CPU_claimed':False,
 'new_network_or_keys_or_X_UFF_QM_calls':0,'parent1884799_failed3_not_rebranded_C0':True,
 'new_input_current_full_SHA_fstat_CRC_EOF_required':True,'full_decontamination_pool_training_release':False,
 'cost_overrun_action':'REPORT_AND_CONTINUE'}


def meta(r):
    Q.need(isinstance(r,dict) and set(r)=={'path','bytes','sha256'} and r['bytes']<=2<<20
        and Path(r['path']).suffix in {'.json','.py','.md','.txt'} and Q.pin(r['path'])==r,'ACTUAL_SMALL_SOURCE_OR_METADATA_PIN')
    return Q.load(r['path'])


def inputs(observation,relocation):
    obs=meta(observation);o=obs['observation'];origin=obs['body_reference'];r=meta(relocation)
    Q.need(obs['source_id']=='tdc_admet_group_zip' and obs['original_official_URL']=='https://dataverse.harvard.edu/api/access/datafile/4426004'
        and origin['bytes']==1472501 and re.fullmatch('[0-9a-f]{64}',origin['sha256']) and o['status_code']==200
        and o['actual_eof_observed'] is True and o['archive_complete'] is True and o['response_entity_complete'] is True
        and o['archive_whole_sha256']==o['whole_response_entity_sha256']==origin['sha256']
        and o['ZIP_inventory']['status']=='COMPLETE_ZIP_ALL_ENTRIES_EOF_CRC_PASS','ACTUAL_INDIVIDUALLY_CLOSED_TDC_PAYLOAD_NOT_PARENT_C0')
    entries=o['ZIP_inventory']['entries'];csv=[v for v in entries if v['name'].endswith('.csv')]
    Q.need(len(entries)==68 and len(csv)==44 and sum(v['uncompressed_bytes'] for v in csv)==5428641
        and sum(v['uncompressed_bytes'] for v in entries)==5434789,'EXACT_ACTUAL68_MEMBER_INVENTORY')
    target=r['target_reference'];Q.need(r['schema']=='TDC_ZIP44_RAW_RELOCATION_V1'
        and r['status']=='COPY_LOCATOR_REQUIRES_CPU_VERIFICATION' and r['origin_reference']==origin
        and r['producer_observation_reference']==observation and set(target)=={'path','bytes','sha256'}
        and all(target[k]==origin[k] for k in ('bytes','sha256')) and Q.ROOT in Path(target['path']).parents,'ONLY_BYTES_IDENTICAL_ONE_MAIN_COPY_LOCATOR')
    return obs,copy.deepcopy(target),copy.deepcopy(entries)
