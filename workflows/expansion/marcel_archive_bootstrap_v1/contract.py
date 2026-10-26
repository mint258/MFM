"""One opaque archive authorized by actual EOF transport metadata, no invented SHA."""
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q
HERE=Q.REPO/'workflows/expansion/marcel_archive_bootstrap_v1'
FILES=('__init__.py','contract.py','archive.py','run.py','test_v1.py','materialize.py','README.md')
KEY='marcel_official_archive_bootstrap_main_v1';MODULE='workflows.expansion.marcel_archive_bootstrap_v1.run'
STAGE='MARCEL_OFFICIAL_OPAQUE_ARCHIVE_FIRST_SHA_ZIP_CRC_INVENTORY'
IDS={'marcel_kraken_zip':'1QrV651Re7s6UF7Lg4KC9PM5QQUMPU7wd','marcel_drugs_zip':'1PHgbrxdDyyjnxSUA71zXWG8WNwocDLPH'}


def meta(r):
    Q.need(set(r)=={'path','bytes','sha256'} and Path(r['path']).suffix in ('.json','.md','.py') and Q.pin(r['path'])==r,'EXPLICIT_ACTUAL_SMALL_METADATA_ONLY')
    return Q.load(r['path'])


def transport(reference,relocation_reference=None):
    raw=meta(reference)
    if raw['schema']=='ROOT_OFFICIAL_MARCEL_OPAQUE_DOWNLOAD_TRANSPORT_V1':
        v=raw;sid=v['source_id'];Q.need(relocation_reference is None and sid in IDS
            and v['official_file_id']==IDS[sid] and v['original_official_locator']=='https://drive.google.com/file/d/'+IDS[sid]+'/view?usp=sharing'
            and v['http_status']==200 and v['actual_response_EOF'] is True and v['ordinary_TLS_and_redirects'] is True
            and v['authentication_or_proxy_bypass'] is False and v.get('declared_content_length') in (None,v['actual_transferred_bytes']),
            'ONLY_COMPLETE_ORIGINAL_DIRECT_MAIN_TRANSPORT')
    else:
        sid='marcel_drugs_zip';Q.need(raw['schema']=='OFFICIAL_OPAQUE_BINARY_TRANSPORT_V2'
            and raw['source']=='https://drive.google.com/uc?export=download&id='+IDS[sid] and raw['http_status']==200
            and raw['eof_observed'] is True and raw['status']=='TRANSPORT_COMPLETE_REQUIRES_SERVER_CPU_VERIFICATION'
            and raw['public_confirmation_form_followed_in_memory'] is True and raw['body_sha256_computed'] is False
            and raw['archive_crc_checked'] is raw['scientific_parsing_performed'] is False and relocation_reference is not None,
            'ONLY_ACTUAL_COMPLETE_DRUGS_PUBLIC_SPOOL_TRANSPORT')
        r=meta(relocation_reference);Q.need(r['schema']=='OFFICIAL_OPAQUE_TRANSPORT_RELOCATION_V1'
            and r['status']=='COPY_COMPLETE_REQUIRES_SERVER_CPU_VERIFICATION' and r['source_local_path']==raw['local_path']
            and r['bytes']==r['normal_official_download_bytes']==raw['bytes'] and r['source_and_target_length_equal'] is True
            and r['body_sha256_computed'] is r['archive_crc_checked'] is r['scientific_parsing_performed'] is False,
            'ACTUAL_CLOSED_MAIN_COPY_LENGTH_LOCATOR_NOT_SERVER_SHA_OR_CRC')
        v={'source_id':sid,'official_file_id':IDS[sid],'actual_transferred_bytes':raw['bytes'],'target_path':r['target_path'],
            'field_derivation':'OfficialID from exact original HTTPS source URL; bytes from actual EOF transport and Main copy size metadata.'}
    Q.need(type(v['actual_transferred_bytes']) is int and 0<v['actual_transferred_bytes']<=8<<30
        and Q.ROOT in Path(v['target_path']).parents,'FINITE_ACTUAL_ONE_MAIN_OPAQUE_FILE')
    return v,{'schema':'OFFICIAL_OPAQUE_ARCHIVE_FIRST_SHA_DEFERRED_LOCATOR_V1','source_id':sid,
        'authority_reference':reference,'relocation_authority_reference':relocation_reference,'path':v['target_path'],
        'bytes':v['actual_transferred_bytes'],'expected_sha256':None,'hash_basis':'FIRST_ACTUAL_CPU_HASH_AFTER_COMPLETE_EOF_TRANSPORT_METADATA'}


def parameters(v,expanded_cap):
    Q.need(type(expanded_cap) is int and 1<<20<=expanded_cap<=64<<30,'EXPLICIT_ROOT_EXPANDED_BYTE_CAP')
    return {'source_id':v['source_id'],'official_file_id':v['official_file_id'],'compressed_bytes':v['actual_transferred_bytes'],
        'expected_archive_SHA256':None,'first_CPU_SHA_bootstrap':True,'maximum_entries':4096,'maximum_central_directory_bytes':16<<20,
        'maximum_expanded_bytes':expanded_cap,'maximum_member_name_UTF8_bytes':1024,'new_pure_fixture_methods':3,
        'all3_fixtures_before_original_archive_body':True,'all_regular_members_EOF_CRC_and_SHA':True,'ZIP64_supported_bounded':True,
        'member_type_by_filename_only':True,'pickle_loaded_or_executed':False,'native_SDF_or_CSV_or_identity_fields_decoded':False,
        'molecules_conformers_stereo_or_full_population_accepted':False,'new_network_or_UFF_QM_calls':0,
        'maximum_active_archive_readers':1,'sixteen_busy_workers_claimed':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}
