"""Actual792 native TAR authority, no fabricated population/ordinal/key closure."""
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
ROOT=Q.ROOT;HERE=ROOT/'code/secondary_moleculenet_native4_identity_v1'
FILES=('__init__.py','contracts.py','guard.py','native.py','run.py','test_v1.py','README.md','authority792.json')
MODULE='secondary_moleculenet_native4_identity_v1.run';KEY='moleculenet_native4_identity_profile_alpha_v1'
PLAN='SECONDARY_MOLECULENET_NATIVE4_IDENTITY_PROFILE_PLAN_V1';PROOF='SECONDARY_MOLECULENET_NATIVE4_IDENTITY_PROFILE_STARTUP_V1'
STAGE='MOLECULENET_NATIVE4_ALL_PHYSICAL_RELATIONSHIPS_AND_BOUNDED_SDF_KEY_PROFILE';SCOPE='NATIVE4_ALL_RECORDS_WITH_BOUNDED_SDF_KEYS'
IDS=('qm8_sdf','pdbbind_core','pdbbind_general','pdbbind_refined');CAP=2<<30;NATIVE_CAP=1<<20
PREFIX={'pdbbind_core':'v2013-core','pdbbind_general':'v2019-other-PL','pdbbind_refined':'refined-set'}
INDEX={'pdbbind_core':'v2013-core/pdbbind_v2013_core.csv','pdbbind_general':'v2019-other-PL/index/INDEX_general_PL_data.2019','pdbbind_refined':'refined-set/index/INDEX_refined_data.2019'}
PARAMETERS={'mode':'profile','source_ids':list(IDS),'format_parent_job_id':'1884792','all_four_TAR_physical_members_and_native_records':True,
    'current_full_payload_inventory_SHA_fstat_and_gzip_EOF_CRC':True,'maximum_SDF_key_rows_per_source':1000,'unknown_N_until_actual_full_source_projection':True,
    'sampler':'PY31114_SHA256_20261026_SOURCE_RANDOM_SAMPLE_SORTED_V1','seed':20261026,'sampler_python':'3.11.14','RDKit':'2025.09.5',
    'workers':16,'maximum_pending':32,'new_pure_methods':3,'all3_before_original_DATA':True,'old_B3_not_reexecuted_or_claimed_as792':True,
    'QM8_reader':{'sanitize':True,'removeHs':False,'strictParsing':False},'PDB_SDF_source_only_reader':{'sanitize':True,'removeHs':False,'strictParsing':True},
    'PDB_source_only_seam_equals_author_PDBFixer_loader':False,'PDBFixer_addH_Gasteiger_or_source_graph_repair':False,
    'MOL2_graph_parser_or_charge_stereo_inference':False,'composition':'DIRECT_FROZEN_NATIVE_COMPOSITION_FROM_COMPLETE_ORIGINAL_ATOM_TABLE',
    'all_titles_IDs_physical_ordinals_conformers_and_present_SMILES_variants_retained':True,'index_and_companion_mapping':'EXPLICIT_LITERAL_FIELDS_AND_OFFICIAL_ORDINAL_RELATION_NOT_TITLE_GUESS',
    'unselected_SDF_graph_state':'NOT_YET_EXAMINED','known_key_entity_automatic_composition_exclusion':False,
    'native_record_container_cap_bytes':NATIVE_CAP,'whole_output_cap_bytes':CAP,'wall_seconds':14400,'algorithm_RSS_reference_bytes':48<<30,
    'new_QM_UFF_network_calls':0,'redo_CSV6_QM7_QM9_or_QM7b':False,'full_or_pool_or_decontamination_release':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}


def authority(plan):
    ref=plan['format_authority_reference'];Q.need(ref==Q.ref(HERE/'authority792.json') and ref in plan['source_references'],'EXACT_NEW_NATIVE4_AUTHORITY_SOURCE')
    a=Q.load_ref(ref);Q.need(a['schema']=='ACTUAL792_FOUR_NATIVE_TAR_AUTHORITY_V1' and a['endpoint']==Q.ENDPOINT and a['uid']==1264
        and a['job_id']=='1884792' and [s['source_id'] for s in a['sources']]==list(IDS),'EXACT_ALPHA792_NATIVE_SCOPE')
    data=[v['payload_reference'] for v in a['sources']]+[v['inventory_reference'] for v in a['sources']]
    Q.need(plan['data_references']==data and len({v['path'] for v in data})==8,'EIGHT_DECLARED_BODY_LOCATORS_NOT_PRE_FIXTURE_METADATA')
    return a
