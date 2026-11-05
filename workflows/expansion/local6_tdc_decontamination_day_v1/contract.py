"""Closed metadata lineage and positive producer DATA references only."""
from pathlib import Path
import sys,re
from workflows.data_v1_final.execution.cpu_analysis_day_v1 import contract as Day
from workflows.data_v1_final.pprime.strict20_readback_v1 import contract as Pins
triple=Pins.triple;unique=Pins.unique
from workflows.expansion.marcel_kraken_decontamination_main_v1 import contract as K
Q=K.Q;ROOT=Q.ROOT;REPO=Q.REPO;PY=Q.PY;need=Q.need;meta=K.meta
HERE=REPO/'workflows/expansion/local6_tdc_decontamination_day_v1'
FILES=('__init__.py','contract.py','io.py','projection.py','local.py','tdc.py','supplement.py','run.py','materialize.py','test_v1.py','README.md')
KEY='local6_tdc_decontamination_day_v1';MODULE='workflows.expansion.local6_tdc_decontamination_day_v1.run'
BASE=ROOT/'artifacts/expansion/local6_tdc_decontamination_day_v1';WALL=72000;CAP=32<<30
LOCAL=ROOT/'artifacts/expansion/identity/sb5_identity_full_closed_units_coverage_v1_v1/receipt.json'
TDC=ROOT/'artifacts/expansion/tdc_zip44_identity_main_v1/receipt.json'
POLICY=ROOT/'control/root_actual_tdc2_conservative_composition_policy_v1.json'
PRIMARY={'v1_all_roles_and_embargo':11236754,'expansionrx':7608,'som_cyp':2003,'som_az':120,'qm7':7165,'qm9':133885}
PARTIAL={'moleculenet_bace':1513,'moleculenet_bbbp':2050,'moleculenet_clintox':1484,'moleculenet_esol':1128,'moleculenet_freesolv':642,'moleculenet_lipophilicity':4200}
PARAMETERS={'scope_key':KEY,'local_closed_parent':'4521192','old_failed_parent':'4521152','old_failed_parent_upgraded':False,
    'original_local_closed_units':404,'all_local_physical_SourceRows':11398552,'primary6_physical_SourceRows':11387535,
    'primary6_expected_records':PRIMARY,'TDC_original_rows':81809,'TDC_original_known_key_rows':81807,'TDC_original_UNKNOWN_rows':2,
    'primary7_export_records':11469344,'original_Molnet6_partial_rows':11017,'original_Molnet17_full_claimed':False,
    'original_physical_membership_only':True,'wholeMID_or_Common_role_filter':False,'cpus':16,'node':'compute-0-14',
    'workers':16,'maximum_pending':32,'wall_seconds':WALL,'whole_output_cap_bytes':CAP,'source_fixture_methods':3,
    'all3_before_DATA_and_resource_monitor':True,'new_graph_RDKit_key_UFF_QM_computations':0,
    'strict_identity_fields':['source_id','role','subdataset','inchikeys','non_h_composition'],
    'chunk_fsync_not_per_row':True,'TDC2_composition_conservative_only_no_graph_SUCCESS':True,
    'candidate_READY_requires_separate_actual_C0_Root_adoption':True,'global_pool_or_training_release':False}
PARAMETERS.update(existing_software_DATA_files=6,physical_C0_manifest_DATA_files=1,top_level_DATA_files=413,
    repository_checker_original_object_once=True,physical_C0_job='4524581',physical_C0_embedded_ref_scope='384native_20tensor_old72_defined_official_exact_paths',
    physical_units_sign_frame_scientific_PASS_or_precision_permission_signed=False)

def generic_review(value):
    need(value['schema']=='EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1'
        and value['status']=='APPROVED_FOR_EXACT_STAGE' and value['reviewer']=='root'
        and value['closed_local6_all44_and_exact2_conservative_identity_only_authorized'] is True
        and value['original_repository_checker_and_six_software_DATA_authorized'] is True
        and value['exact_407_closed_physical_C0_embedded_triples_discovered_on_CPU_only_authorized'] is True
        and value['global_pool_release_authorized'] is False,'REAL_ROOT_EXACT_GENERIC_SCOPE_REVIEW')
    return value

def account(ref,job,node):
    a=meta(ref);refs=[]
    raw=a.get('raw_sacct_reference',a.get('raw_accounting_reference',a.get('raw_reference')))
    if raw is None:
        raw=next((v for v in a.values() if isinstance(v,dict) and str(v.get('path','')).endswith(('.sacct.txt','.txt'))),None)
    need(raw is not None,'ACTUAL_TERMINAL_RAW_REFERENCE_REQUIRED');raw=triple(raw)
    need(raw['bytes']<=2<<20 and Q.pin(raw['path'])==raw,'CURRENT_SMALL_TERMINAL_RAW')
    lines=Path(raw['path']).read_text().splitlines();header=next((x.split('|') for x in lines if x.startswith('JobIDRaw|')),None)
    need(header is not None,'EXPLICIT_SACCT_FIELDS_REQUIRED');rows=[dict(zip(header,x.split('|'))) for x in lines if x.startswith(str(job)+'|')]
    need(len(rows)==1 and rows[0]['State']=='COMPLETED' and rows[0]['ExitCode']=='0:0' and rows[0]['AllocCPUS']=='16'
        and rows[0]['NodeList']==node and rows[0]['UID']=='1278','TRUE_C0_PRIMARY_NOT_EXTERN_OR_OTHER_PARENT')
    return raw

def derive(plan):
    need(triple(plan['local_receipt_reference'])['path']==str(LOCAL) and triple(plan['tdc_receipt_reference'])['path']==str(TDC)
        and triple(plan['tdc2_policy_reference'])['path']==str(POLICY),'SPECIFIC_THREE_CLOSED_AUTHORITIES')
    local=meta(plan['local_receipt_reference']);tdc=meta(plan['tdc_receipt_reference']);policy=meta(plan['tdc2_policy_reference'])
    need(local['schema']=='FULL_IDENTITY_READONLY_CLOSURE_RECEIPT_V1' and local['job_id']=='4521192' and len(local['closed_units'])==404
        and local['unit_summary']['counts']['records']==11398552 and local['role_semantics']=='ORIGINAL_PHYSICAL_RECORD_MEMBERSHIP_ONLY'
        and local['effective_training_roles_applied'] is False and local['apply_common_filter'] is False
        and local['original_failed_parent_upgraded_to_COMPLETED'] is False,'ACTUAL_LOCAL_CLOSED_SCOPE_NOT_NEW_ROLES')
    need(all(local['unit_summary']['datasets'][d]==n for d,n in {**PRIMARY,**PARTIAL}.items()),'EXACT_ALL_LOCAL_DATASET_COUNTS')
    lp=meta(local['plan']);manifest=meta(lp['unit_manifest']);need(len(manifest['units'])==404 and manifest['failed_parent']=='4521152','ACTUAL404_UNIT_LOCATORS')
    closed={v['unit_id']:triple(v['file']) for v in local['closed_units']};units=[];parents=[plan['local_receipt_reference'],local['plan'],local['startup_proof'],lp['unit_manifest'],lp['prior_failure'],lp['prior_accounting']]
    for row in manifest['units']:
        receipt=meta(row['receipt_reference']);name=receipt['unit_id'];need(name in closed and triple(receipt['file'])==closed[name]
            and triple(row['part_reference_claimed_by_original_unit'])==closed[name],'SAME_CLOSED_UNIT_AND_CURRENT_PRODUCER_FILE')
        need(re.fullmatch('[A-Za-z0-9_]{1,128}',name) is not None and closed[name]['path']==str(ROOT/'artifacts/expansion/identity/sb5_identity_full_source_roles_after_profile_v1_v1/parts'/(name+'.parquet')),
            'LITERAL_OLD_CLOSED_UNIT_SCOPE_NOT_NEW_PATH_ALIAS')
        need(receipt['counts']['records']>0 and sum(receipt['datasets'].values())==sum(receipt['roles'].values())==receipt['counts']['records'],'UNIT_COUNTS_CONSERVE')
        units.append({'unit_id':name,'file':closed[name],'receipt_reference':row['receipt_reference'],'counts':receipt['counts'],'datasets':receipt['datasets'],'roles':receipt['roles']})
        parents.append(row['receipt_reference'])
    need(len({x['unit_id'] for x in units})==404,'NO_DUPLICATE_UNIT')
    need(tdc['schema']=='TDC_ZIP44_IDENTITY_RECEIPT_V1' and tdc['job_id']=='4521757' and tdc['uid']==1278
        and tdc['result']['physical_rows_dispatched']==tdc['result']['physical_rows_with_durable_results']==81809
        and tdc['result']['identity_state_counts']=={'FULL_KEYS_DERIVED':81807,'ORIGINAL_SMILES_UNRESOLVED':2}
        and len(tdc['result']['member_result_counts'])==44,'ACTUAL_ALL44_TDC_NOT_TEST_ONLY')
    need(policy['schema']=='ROOT_TDC_EXACT2_CONSERVATIVE_COMPOSITION_POLICY_REVIEW_V1'
        and policy['status']=='APPROVED_FOR_CONSERVATIVE_EXCLUSION_ONLY_PENDING_FULL81809_IDENTITY_EXPORT'
        and policy['original_unknown_graph_charge_stereo_and_error_states_preserved'] is True
        and str(policy['actual_alpha_job_id'])=='1884865' and policy['actual_alpha_uid']==1264
        and policy['actual_main_uid']==1278,'SPECIFIC_ACTUAL_ALPHA_CONSERVATIVE_ADOPTION_NOT_GRAPH_SUCCESS')
    join=policy['required_runtime_join'];need(join['member']=='admet_group/solubility_aqsoldb/test.csv' and join['physical_ordinals']==[1159,1160]
        and join['same_original_source_events_AND_result_events_required'] is True,'EXACT_TWO_UNKNOWN_JOIN_NOT_CAUSE_INFERENCE')
    alpha=triple(policy['main_opaque_copy_DATA_locator_pending_CPU_whole_SHA']);origin=triple(policy['original_alpha_journal_DATA_reference'])
    need(alpha['bytes']==origin['bytes']==11166 and alpha['sha256']==origin['sha256'],'OPAQUE_MAIN_COPY_MATCHES_ACTUAL_ALPHA_PRODUCER_PIN')
    parents.extend([plan['tdc_receipt_reference'],tdc['plan_reference'],tdc['startup_proof_reference'],tdc['accepted_header_receipt_reference'],tdc['accepted_header_accounting_reference'],plan['tdc2_policy_reference']])
    aliases=[policy[k] for k in ('actual_receipt_metadata_alias_reference','actual_plan_metadata_alias_reference','actual_proof_metadata_alias_reference',
        'actual_accounting_metadata_alias_reference','actual_raw_accounting_metadata_alias_reference','actual_request_metadata_alias_reference','actual_submission_metadata_alias_reference')]
    for r in aliases:need(Q.pin(r['path'])==triple(r),'ACTUAL_ALPHA_ALIAS_BYTES_NOT_REWRITTEN_AS_MAIN')
    ap=meta(policy['actual_proof_metadata_alias_reference']);ar=meta(policy['actual_receipt_metadata_alias_reference'])
    need(str(ap['job_id'])=='1884865' and ap['uid']==1264 and str(ar['job_id'])=='1884865','REAL_FOREIGN_PARENT_IDENTITY_PRESERVED')
    parents.extend(aliases)
    parents.extend([plan['local_accounting_reference'],account(plan['local_accounting_reference'],'4521192',local['node']),
        plan['tdc_accounting_reference'],account(plan['tdc_accounting_reference'],'4521757',tdc['node'])])
    need(triple(plan['native_git_assets_manifest_reference'])['path']==str(ROOT/'control/alpha_source_checker_git2393_original6_assets_manifest_v2.json')
        and triple(plan['native_git_wrapper_reference'])['path']==str(ROOT/'artifacts/software/git_2_39_3_login_v1/bin/git'),
        'ONLY_ORIGINAL_SIX_ASSETS_AND_KNOWN_WRAPPER_NOT_ARBITRARY_EXECUTION')
    assets=meta(plan['native_git_assets_manifest_reference']);software=[triple(v['origin_reference']) for v in assets['files']]
    need(len(software)==6 and len({r['path'] for r in software})==6,'EXACT_ORIGINAL_NATIVE_GIT6_DATA_LOCATORS')
    need(Q.pin(plan['native_git_wrapper_reference']['path'])==triple(plan['native_git_wrapper_reference']),'ACTUAL_ORIGINAL_GIT_WRAPPER_SOURCE')
    physical=triple(plan['physical_manifest_reference']);need(physical['path']==str(ROOT/'artifacts/labels/source_status_v1/physical_closure_day_v1/day02_r2/manifest.json'),
        'SPECIFIC_ACTUAL_R2_MANIFEST_DATA_AUTHORITY_NO_LOGIN_CHILD_PARSE')
    parents.extend([plan['native_git_assets_manifest_reference'],plan['native_git_wrapper_reference'],plan['physical_accounting_reference'],
        account(plan['physical_accounting_reference'],'4524581','compute-0-18')])
    data=unique([*(v['file'] for v in units),triple(tdc['result']['journal_reference']),alpha,*software,physical])
    need(len(data)==413,'EXACT406_IDENTITY_6_SOFTWARE_AND1_CLOSED_PHYSICAL_MANIFEST_DATA')
    authority={'units':sorted(units,key=lambda x:x['unit_id']),'local_counts':local['unit_summary'],'local_source_authority':local['source_authority'],
        'local_original_raw_body_references':local['original_source_body_hashes'],'TDC_journal_reference':triple(tdc['result']['journal_reference']),
        'TDC_original_archive_reference':tdc['input_reference'],'TDC_member_counts':tdc['result']['member_result_counts'],
        'TDC2_DATA_reference':alpha,'TDC2_origin_DATA_reference':origin,'TDC2_accepted_observations':policy['new_compositions_accepted_for_conservative_non_H_exclusion_only'],
        'physical_manifest_reference':physical,'software_DATA_references':software}
    return authority,data,unique(parents,source=True)

def sources():
    paths=[*(HERE/n for n in FILES),*Day.sources(),*Pins.sources(),K.HERE/'runtime.py',K.HERE/'projection.py',K.HERE/'contract.py',*K.OLD,
        REPO/'workflows/expansion/common.py',REPO/'workflows/expansion/decontamination.py',
        REPO/'workflows/expansion/marcel_drugs_keys_main_v1/runtime.py',
        REPO/'workflows/data_v1_final/pprime/strict20_readback_v1/io.py',REPO/'workflows/data_v1_final/pprime/strict20_readback_v1/contract.py']
    for folder in ('cpu_auto_memory_queue_v2','queue_v1','labels/source_status_cpu_auto_memory_v1'):
        base=REPO/'workflows/data_v1_final'/folder if folder.startswith('labels/') else REPO/'workflows/data_v1_final/execution'/folder
        paths.extend(base.glob('*.py'))
    for name,module in list(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if name.startswith('workflows.') and path and Path(path).suffix=='.py' and REPO in Path(path).parents:paths.append(Path(path))
    for path in list(paths):
        for parent in path.parents:
            if parent==REPO:break
            init=parent/'__init__.py'
            if REPO in init.parents and init.exists():paths.append(init)
    return list(dict.fromkeys(paths))
