"""Actual1884892 small parent chain and one strict large ZIP locator."""
import hashlib,re
from secondary_cpu_queue_v1 import common as Q
from secondary_qm7b_official2013_acquisition_v1 import contracts as AQ
from secondary_moleculenet_csv6_identity_v1.guard import account

ROOT=Q.ROOT;HERE=ROOT/'code/secondary_qm7b2013_format_v1'
FILES=('__init__.py','contracts.py','guard.py','formats.py','run.py','test_v1.py','README.md')
KEY='qm7b_official2013_passive_format_alpha_v1';MODULE='secondary_qm7b2013_format_v1.run'
PLAN='SECONDARY_QM7B2013_PASSIVE_FORMAT_PLAN_V1';PROOF='SECONDARY_QM7B2013_PASSIVE_FORMAT_STARTUP_V1'
STAGE='ACTUAL1884892_QM7B2013_ZIP_PASSIVE_FORMAT_METADATA'
SCOPE='PASSIVE_MEMBER_FORMAT_NO_GRAPH_KEY_OR_MAT_ROW_MAPPING'
CAP=2<<30;WALL=600;ZIP_BYTES=2671083;EXPANDED=7143546;MEMBERS=4
LINE_BYTES=1<<20;LINES=200000;TOKENS=4096;XYZ_ATOMS=100000
MAT_FIELDS=128;MAT_NAME_BYTES=256;MAT_DIMS=32
RECEIPT_PATH=ROOT/'artifacts/qm7b_official2013_acquisition_v1/v1/receipt.json'
ZIP_PATH=ROOT/'artifacts/qm7b_official2013_acquisition_v1/v1/author_2013_actual_response.DATA.bin'
ZIP_SHA='49b104aeb208a88c1a6a743cba3e9f17f14d1a74d77992a1c03959b02988eb8e'
GUARD_PARENT=ROOT/'code/secondary_pdbbind_index27_extract_v1/guard.py'
GUARD_EDITS=(
    ('Fresh Alpha gate; actual866/856/792/784 are historical parents, not this runtime.',
     'Fresh Alpha format gate;1884892 is a historical acquisition, not this runtime.'),
    ('only_original27_identity_and_opaque_index_evidence','only_closed_qm7b2013_zip_format_evidence'),
    ('PDBBIND27','QM7B2013_FORMAT'),
)
PARAMETERS={'actual_original_acquisition_job':'1884892','one_original_ZIP_DATA_file':1,'original_ZIP_bytes':ZIP_BYTES,
    'expected_physical_members':MEMBERS,'expected_total_uncompressed_bytes':EXPANDED,
    'DATA_locator_has_small_metadata_ceiling':False,'whole_SHA_stable_FD_then_every_member_EOF_CRC_SHA':True,
    'original_AQ_inventory_function_object_reused':True,'new_compressed_or_uncompressed_alias_created':False,
    'MAT_inspection':'scipy.io.whosmat_ONLY_names_shapes_MATLAB_class_no_values',
    'XYZ_inspection':'bounded_count_symbol_and_numeric_lexeme_grammar_NO_coordinate_float',
    'other_text':'bounded_UTF8_line_and_column_counts_only_headers_and_IDs_opaque',
    'all_original_lines_headers_IDs_possible_SMILES_only_opaque_DATA_refs':True,
    'maximum_line_bytes':LINE_BYTES,'maximum_lines_per_member':LINES,'maximum_tokens_per_line':TOKENS,
    'maximum_XYZ_atom_rows_per_record':XYZ_ATOMS,'member_names_ordinals_or7211_are_MAT_row_evidence':False,
    'maximum_MAT_fields_per_member':MAT_FIELDS,'maximum_MAT_field_name_bytes':MAT_NAME_BYTES,'maximum_MAT_dimensions':MAT_DIMS,
    'MAT_values_objects_pickle_graph_Mol_DetermineBonds_or_SMILES_generation':False,
    'network_graph_key_UFF_QM_calls':0,'new_pure_methods':3,'all3_before_original_DATA_and_Budget':True,
    'old_fixture_methods_reexecuted':False,'summary_contains_IDs_coordinates_or_target_values':False,
    'allocated_cpus':16,'reader_processes':1,'whole_output_cap_bytes':CAP,'wall_seconds':WALL,
    'unknown_format':'UNKNOWN_HOLD_NO_ALTERNATIVE_PARSER','resource_stop':'PARTIAL_HOLD_NATURAL_NO_SIGNAL',
    'original_unknowns_or_assets_modified':False,'automatic_identity_graph_mapping_pool_release':False,
    'cost_overrun_action':'REPORT_AND_CONTINUE'}
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
    'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')


def data_locator(ref):
    Q.need(isinstance(ref,dict) and set(ref)=={'path','bytes','sha256'} and isinstance(ref['path'],str)
        and type(ref['bytes']) is int and ref['bytes']>0 and isinstance(ref['sha256'],str)
        and re.fullmatch('[0-9a-f]{64}',ref['sha256']),'EXACT_POSITIVE_LARGE_PRODUCER_DATA_TRIPLE')
    Q.need(ROOT/'artifacts' in Q.literal(ref['path']).parents,'ONLY_LITERAL_ALPHA_ARTIFACT_DATA')
    return ref


def unique(refs):
    out={}
    for r in refs:
        Q.normalized(r);Q.need(r['path'] not in out or out[r['path']]==r,'CONFLICTING_SMALL_SOURCE_PIN');out[r['path']]=r
    return [out[k] for k in sorted(out)]


def guard_derivation():
    old=GUARD_PARENT.read_bytes();expected=old.decode('utf-8')
    for before,after in GUARD_EDITS:
        Q.need(before in expected,'EXACT_LITERAL_GUARD_DERIVATION_SOURCE');expected=expected.replace(before,after)
    current=(HERE/'guard.py').read_bytes()
    Q.need(current==expected.encode('utf-8'),'GUARD_DIFFERS_OUTSIDE_EXPLICIT_LITERAL_SCOPE_EDITS')
    return {'original_guard_reference':Q.ref(GUARD_PARENT),'current_guard_reference':Q.ref(HERE/'guard.py'),
            'literal_edit_groups':len(GUARD_EDITS),'body_guard_bytes_unchanged_except_declared_scope_literals':True,
            'original_sha256':hashlib.sha256(old).hexdigest()}


def validate_closed(r,a,p,s,review,request,submission):
    parent=a['actual_parent']
    Q.need(r['schema']=='SECONDARY_QM7B_OFFICIAL2013_ARCHIVE_RECEIPT_V1'
        and r['status']=='OFFICIAL_ARCHIVE_SHA_ALL_MEMBER_EOF_CRC_INVENTORY_COMPLETE_GRAPH_AND_ROW_MAPPING_UNKNOWN'
        and r['job_id']=='1884892' and r['uid']==1264 and r['endpoint']==Q.ENDPOINT and r['node']==parent['NodeList'],
        'ACTUAL_CLOSED1884892_RECEIPT_NOT_HEAD_OR_NEW_FORMAT_ACCEPTANCE')
    Q.need(parent['JobIDRaw']=='1884892' and parent['State']=='COMPLETED' and parent['ExitCode']=='0:0'
        and parent['UID']=='1264' and parent['AllocCPUS']=='16' and parent['Partition']=='cpu'
        and a['query_returncode']==0 and a['uid']==1264 and a['endpoint']==Q.ENDPOINT,'ACTUAL1884892_CPU16_C0')
    observation=r['all_member_observation']
    Q.need(all(type(observation[k]) is int for k in ('physical_members','total_uncompressed_bytes',
        'directory_flags','duplicate_literal_filenames_preserved'))
        and observation['physical_members']==MEMBERS and observation['total_uncompressed_bytes']==EXPANDED
        and observation['directory_flags']==0 and observation['duplicate_literal_filenames_preserved']==0
        and observation['every_member_EOF_CRC_SHA_verified'] is True
        and observation['original_compressed_and_uncompressed_bytes_preserved'] is True,'EXACT_ORIGINAL_C0_CONTAINER_MASSES')
    Q.need(r['graph_SMILES_MAT_mapping_accepted'] is False and r['global_pool_decontamination_release'] is False
        and r['new_graph_parse_key_UFF_QM_calls']==0 and r['scope_parameters']==AQ.PARAMETERS,'OLD_SCOPE_AND_UNKNOWN_AXES_PRESERVED')
    Q.need(r['fixtures']['tests_run']==3 and all(r['fixtures'][k]==0 for k in
        ('failures','errors','skips','expected_failures','unexpected_successes')),'ACTUAL_OLD_PURE3_HISTORICAL_ONLY')
    Q.need(p['schema']==AQ.PLAN and p['scope_key']==AQ.KEY and p['scope_parameters']==AQ.PARAMETERS
        and s['schema']==AQ.PROOF and str(s['job_id'])=='1884892' and s['endpoint']==Q.ENDPOINT and s['uid']==1264
        and s['node']==r['node'] and s['plan_reference']==r['plan_reference']
        and s['root_review_reference']==p['root_review_reference'],'EXACT_OLD_PLAN_AND_ACTUAL_CPU_PROOF')
    Q.need(review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root'
        and all(p[k]==review[k] for k in AQ.REVIEW_FIELDS)
        and p['source_references']==review['approved_source_references'],'ACTUAL_OLD_ROOT_SCOPE_REVIEW')
    Q.need(request['adapter']['producer_plan_reference']==r['plan_reference']
        and request['adapter']['startup_proof_path']==r['startup_proof_reference']['path']
        and request['scope_key']==AQ.KEY and s['controller_evidence']['queue_request_reference']==a['queue_request_reference']
        and submission['job_id']=='1884892' and submission['sbatch_returncode']==0
        and submission['queue_request_reference']==a['queue_request_reference'],'OLD_REQUEST_SUBMISSION_PLAN_PROOF_SAME_ACTUAL_JOB')
    archive=data_locator(r['original_archive_reference']);raw=data_locator(r['all_uncompressed_original_bytes_reference'])
    Q.need(archive=={'path':str(ZIP_PATH),'bytes':ZIP_BYTES,'sha256':ZIP_SHA}
        and raw['bytes']==EXPANDED,'EXACT_CLOSED_PRODUCER_ZIP_NOT_SMALL_SOURCE')
    return archive,raw


def discover(value):
    refs=[]
    def meta(ref):
        Q.normalized(ref);path=Q.literal(ref['path'])
        Q.need(ROOT/'control' in path.parents or path==RECEIPT_PATH,'ONLY_EXACT_CLOSED_RECEIPT_OR_CONTROL_METADATA')
        refs.append(ref);return Q.load_ref(ref)
    rr=value['acquisition_receipt_reference'];Q.need(rr['path']==str(RECEIPT_PATH),'ONLY_ACTUAL1884892_RECEIPT')
    r=meta(rr);ar=value['acquisition_accounting_reference'];a=meta(ar)
    raw_account=a['raw_sacct_reference'];Q.normalized(raw_account);Q.need(ROOT/'control' in Q.literal(raw_account['path']).parents,'ACCOUNT_RAW_IS_SMALL_CONTROL')
    refs.append(raw_account);account(ar,'1884892',refs)
    p=meta(r['plan_reference']);s=meta(r['startup_proof_reference']);review=meta(p['root_review_reference'])
    request=meta(a['queue_request_reference']);submission=meta(s['controller_evidence']['submission_reference'])
    archive,raw=validate_closed(r,a,p,s,review,request,submission)
    return {'receipt':r,'acquisition_plan':p,'data':[archive],'original_raw_reference':raw,
        'parents':unique(refs),'expected_container':r['all_member_observation']}


def inputs(plan):
    d=discover(plan);Q.need(plan['data_references']==d['data'] and plan['scope_parameters']==PARAMETERS,
        'EXACT_ONE_PRODUCER_ZIP_AND_FORMAT_ONLY_SCOPE')
    Q.need(all(r in plan['parent_evidence_references'] and r in plan['source_references'] for r in d['parents']),
        'ALL_ACTUAL_C0_SMALL_PARENTS_APPROVED')
    Q.need(Q.ref(GUARD_PARENT) in plan['source_references'],'EXACT_FROZEN_GUARD_SOURCE_USED_BY_PURE_DERIVATION')
    return d
