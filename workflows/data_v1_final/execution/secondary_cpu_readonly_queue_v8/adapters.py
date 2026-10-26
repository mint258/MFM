"""Only the exact Alpha labels512 existing-value reducer; body locators stay unread."""
import csv,io
from collections import Counter
from pathlib import Path
from secondary_cpu_queue_v1.common import ROOT,ENDPOINT,UID,POLICY,NODES,need,ref,load,load_ref,verify,normalized,literal,read_small

KEY='labels_payload512_reduce_readonly_alpha_v1'
PROTOCOLS={KEY:{'plan':'SECONDARY_LABEL_PAYLOAD512_REDUCE_READONLY_PLAN_V1',
    'proof':'SECONDARY_LABEL_PAYLOAD512_REDUCE_READONLY_STARTUP_V1','stage':'LABEL_PAYLOAD512_EXISTING_VALUES_REDUCTION',
    'module':'payload_reduce_alpha_v1.run'}}
HERE=ROOT/'code/secondary_cpu_readonly_queue_v8'
FROZEN=ROOT/'code/labels_payload512_frozen_v1'
OUT=ROOT/'artifacts/labels_payload512_readonly_v1/reduction_v1'
KINDS={'group_details':16,'candidate_mask':16,'coverage':16,'selection_owner_index':16,'expected_role':1}
KIND_BYTES={'group_details':26652140,'candidate_mask':232897,'coverage':71642,'selection_owner_index':249172,'expected_role':11231854}
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot',
    'wall_seconds','output_cap_bytes','execution_argv','data_references','data_total_bytes','parent_evidence_references',
    'resource_evidence_output','resource_evidence_output_cap_bytes','storage_reservation_reference')
PARAMETERS={'parent_alpha_job_id':'1884788','original_main_job_id':'4521327','input_molecules':512,'input_records':4251,
 'source_TRAIN_records':4211,'source_VAL_records':20,'source_FULL_records':20,'input_shard_manifests':1,'source_owner_groups':16,
 'group_details_files':16,'candidate_mask_files':16,'coverage_files':16,'selection_owner_index_files':16,'expected_role_files':1,
 'reduction_body_files':65,'global_role_records':11231854,'task_types':14,'expected_task_slots':59514,'coverage_output_bytes':157245956,
 'enabled_components':146,'registered_components':264,'synthetic_test_methods':6,'all6_tests_before_any_body_reads':True,
 'body_hash_after_tests_in_this_allocation':True,'body_hash_workers':16,'new_QM_calls':0,'new_UFF_calls':0,
 'source_values_read_only':True,'original_JSON_paths_rewritten':False,'Main_runtime_proof_reused':False,
 'scan_runtime_proof_reused_as_startup':False,'median_MAD_refit':False,'matched_pilot_TRAIN_reference_only':True,
 'full_or_export_or_final_D4_release':False,'minimum_mem_available_bytes':4294967296,
 'target_python':'3.11.14','target_numpy':'2.2.6','target_rdkit':'2025.09.5','target_pyarrow':'17.0.0','Main_pyarrow_major':25}
PARENT_PINS={"scan_manifest_reference":{"bytes":6891,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/manifest.json","sha256":"c549347314b423c964c1a42ac1250184c0e4b6710b580acf53ffce33954a94c5"},"scan_plan_reference":{"bytes":85219,"path":"/gfshome/alpha/codex_data_v1_20261026/control/readonly_specs/labels_payload512_readonly_v2/plan.json","sha256":"58f275886af0278eb875c7342e9e21ed6a51dfde28d58aa5dcde9127000ccdb9"},"scan_startup_proof_reference":{"bytes":29941,"path":"/gfshome/alpha/codex_data_v1_20261026/control/secondary_startup/dv1_labels_payload512_readonly_v2_20261026_v1.json","sha256":"a87086e0d1104cf143a2ae10361abf2f31c84bd9f4d86e0371e8b22589f0e20e"},"scan_transfer_verification_reference":{"bytes":357743,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/transfer_verification.json","sha256":"3b2dce34dc5917b00ae2dddc771756aaa37bb0fbdcd2d143d551872841b03068"},"scan_fixture_gate_reference":{"bytes":2131,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/pre_scan_fixture_gate.json","sha256":"789cad91c445591a0ff4f3adbb434bcdada526e6c7ab1b60690c658ec5d63dea"},"parent_accounting_reference":{"bytes":1672,"path":"/gfshome/alpha/codex_data_v1_20261026/control/secondary_cpu_queue/labels_payload512_readonly_v2/accounting_1793027034226493409.json","sha256":"32d82ce4566f9be834e0930424b36c73a7c8210f8e27561dc39903b6457d7828"},"parent_accounting_raw_reference":{"bytes":273,"path":"/gfshome/alpha/codex_data_v1_20261026/control/secondary_cpu_queue/labels_payload512_readonly_v2/sacct_1793027034226493409.txt","sha256":"736a42695fc8f1da323f0b83ca813e1c5e063f026bc8bdd47620bd9e72af9ac5"}}
SCAN_REVIEW_PIN={"bytes":82985,"path":"/gfshome/alpha/codex_data_v1_20261026/control/readonly_specs/labels_payload512_readonly_v2/root_review.json","sha256":"560b7abfa949dda271bba5274d5a7ce6a9fa52fea379ab665ebe00db4a61d0a5"}
REPORT_PINS=[{"bytes":104042,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/group_0000/report.json","sha256":"821f6289fd36af269fc0a516aa7d8c67acd7811d4f6cadb9bdb5252125f67966"},{"bytes":126705,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/group_0001/report.json","sha256":"761220933fef7f2937970984dc3487a05256c928621712a590d414515403ba12"},{"bytes":102676,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/group_0002/report.json","sha256":"44e5c44661f7955ed416f3887db58c6686346e7dc16d9503be67d7c5929516ce"},{"bytes":104096,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/group_0003/report.json","sha256":"a13ecf29a40988b1730254be82cdcec0c2ac0d75227d205e3b17a14cd81c4edb"},{"bytes":104168,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/group_0004/report.json","sha256":"313ff38198bab17d2186c6b3d8e9d4992acd58437562534b87eb3435526e55b1"},{"bytes":103977,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/group_0005/report.json","sha256":"a93b6c1bd4d57898f096d16f7f3a319a52b9b439fc59cf60aff733b9c87a5d98"},{"bytes":102798,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/group_0006/report.json","sha256":"5b91e33bb427de8e6695bb1d770fe73455e985aa7c50070180459daa140e7ea6"},{"bytes":103937,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/group_0007/report.json","sha256":"1cf7b0b8431af9a50afbeacccf5582f908989d6675c4f006aa143d5545e98e01"},{"bytes":104101,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/group_0008/report.json","sha256":"2f618dcd41aa2879dec66c12c9cb5e40e46756c9904db17b75cc661acfbad00c"},{"bytes":136066,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/group_0009/report.json","sha256":"f9ac04542353ff30b8c0f18c7695f174b2bc1476e8a3634f58c87ecf43c7a649"},{"bytes":104037,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/group_0010/report.json","sha256":"90af5fe0495bb3d54eb988a0cfe77eb2d6cebc7d9dc571e45c12d69fa1123f19"},{"bytes":104034,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/group_0011/report.json","sha256":"38c3e1bb4d9d4b887dd944d7575fde1d2dc4c909292d88e08a520914191ea58d"},{"bytes":126401,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/group_0012/report.json","sha256":"94ca5f9af759ec69b643ce5fc7a698c58ccfc2f186ca6bd08f4767818d3594c0"},{"bytes":104162,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/group_0013/report.json","sha256":"77950d8e0ac9fe065bcb846103714814a93276d88c26f1f4545d12f1b365cf0c"},{"bytes":104056,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/group_0014/report.json","sha256":"4b5a26a454f73c8bf785f8daaeb0f1d017f179e0f8c990f50413aa14735a50ab"},{"bytes":104101,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/labels_payload512_readonly_v1/v2/group_0015/report.json","sha256":"faeabc18c7ffbcb942b03a85829ec06ed59aa25d225b1f92c88fc980b0ac2da2"}]
ORIGIN_INVENTORY_PIN={"bytes":515109,"path":"/gfshome/alpha/codex_data_v1_20261026/code/payload_audit_alpha_v1/transfer_inventory_v1.json","sha256":"b20b5a8a707dc2614d1e77dda7ac7c7371f89e6cb673218900c35171bb20282d"}
RELOCATION_MAP_PIN={"bytes":248377,"path":"/gfshome/alpha/codex_data_v1_20261026/metadata/labels_payload512_v1/relocation_map.json","sha256":"26abbe5d775a067b8d2807cace2d5c89939afa83c2f5506f89e40d6025cce090"}
CONFIG_PIN={"bytes":3861,"path":"/gfshome/alpha/codex_data_v1_20261026/inputs/labels_payload512_v1/main/runs/data_v1_20261025/control/payload_audit_v1_pilot_metadata/config.json","sha256":"48357da799b8772a4b18c1288aa5e582daf6c5c1126f7bbb4927cf4c852f5528"}

def triple(value):
    need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'} and type(value['bytes']) is int and value['bytes']>=0
        and isinstance(value['sha256'],str) and len(value['sha256'])==64 and set(value['sha256'])<=set('0123456789abcdef'),
        'EXACT_REDUCER_BODY_LOCATOR_TRIPLE_WITHOUT_BODY_READ_REQUIRED')
    literal(value['path']);return value


def strip_triple(value):return {key:value[key] for key in ('path','bytes','sha256')}


def parent_and_input_authority(plan):
    for key,value in PARENT_PINS.items():
        need(plan[key]==value and value in plan['parent_evidence_references'],'ONLY_EXACT_ACTUAL_ALPHA1884788_PARENT_PIN:'+key)
    need(SCAN_REVIEW_PIN in plan['parent_evidence_references'],'ACTUAL_ALPHA_SCAN_ROOT_REVIEW_PARENT_PIN_REQUIRED')
    need(all(value in plan['source_references'] for value in plan['parent_evidence_references']),
        'EVERY_REDUCER_PARENT_MUST_BE_APPROVED_SMALL_SOURCE')
    account=load_ref(PARENT_PINS['parent_accounting_reference']);parent=account['actual_parent']
    need(account.get('schema')=='SECONDARY_CPU_ACTUAL_ACCOUNTING_EVIDENCE_V1' and account.get('query_returncode')==0
        and account.get('endpoint')==ENDPOINT and account.get('uid')==UID
        and parent.get('JobIDRaw')=='1884788' and parent.get('State')=='COMPLETED' and parent.get('ExitCode')=='0:0'
        and parent.get('UID')=='1264' and parent.get('AllocCPUS')=='16' and parent.get('ElapsedRaw')=='57'
        and parent.get('NodeList')=='compute-0-6' and parent.get('Partition')=='cpu'
        and account.get('raw_sacct_reference')==PARENT_PINS['parent_accounting_raw_reference']
        and account.get('allocated_core_seconds_observed')==912,'ACTUAL_ALPHA1884788_C0_57S_CPU16_COST_REQUIRED')
    raw=list(csv.DictReader(io.StringIO(read_small(verify(PARENT_PINS['parent_accounting_raw_reference'])).decode()),delimiter='|'))
    matches=[row for row in raw if row.get('JobIDRaw')=='1884788']
    need(len(matches)==1 and all(matches[0].get(key)==parent.get(key) for key in
        ('State','ExitCode','UID','ElapsedRaw','AllocCPUS','NodeList','Partition')),'ACTUAL_ALPHA_PARENT_RAW_SACCT_MUST_MATCH_ALL_FIELDS')
    scan=load_ref(PARENT_PINS['scan_plan_reference']);proof=load_ref(PARENT_PINS['scan_startup_proof_reference'])
    scan_review=load_ref(SCAN_REVIEW_PIN);manifest=load_ref(PARENT_PINS['scan_manifest_reference'])
    need(scan.get('schema')=='SECONDARY_LABEL_PAYLOAD512_READONLY_PLAN_V1'
        and scan.get('producer_key')==scan.get('scope_key')=='labels_payload512_readonly_alpha_v1'
        and scan.get('stage')=='LABEL_PAYLOAD512_EXISTING_VALUES_PILOT' and scan.get('kind')=='analysis' and scan.get('pilot') is True
        and scan.get('endpoint')==ENDPOINT and scan.get('uid')==UID and scan.get('node')=='compute-0-6'
        and scan.get('run_root')==str(ROOT) and scan.get('cpus')==16 and scan.get('root_review_reference')==SCAN_REVIEW_PIN
        and scan.get('output_directory')==str(ROOT/'artifacts/labels_payload512_readonly_v1/v2'),
        'HISTORICAL_MATCHED_PILOT_SCAN_PLAN_ALPHA_IDENTITY_REQUIRED')
    need(proof.get('schema')=='SECONDARY_LABEL_PAYLOAD512_READONLY_STARTUP_V1' and str(proof.get('job_id'))=='1884788'
        and proof.get('endpoint')==ENDPOINT and proof.get('uid')==UID and proof.get('node')=='compute-0-6'
        and proof.get('plan_reference')==PARENT_PINS['scan_plan_reference'] and proof.get('root_review_reference')==SCAN_REVIEW_PIN
        and proof.get('request',{}).get('kind')=='analysis' and proof['request'].get('pilot') is True
        and proof['request'].get('cpus')==16,'HISTORICAL_SCAN_PROOF_IS_PARENT_EVIDENCE_NOT_NEW_STARTUP')
    need(scan_review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and scan_review.get('status')=='APPROVED_FOR_EXACT_STAGE' and scan_review.get('reviewer')=='root'
        and scan_review.get('approved_source_references')==scan['source_references'],'EXACT_HISTORICAL_SCAN_ROOT_SOURCE_REVIEW_REQUIRED')
    for key in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot',
        'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references'):
        need(scan_review[key]==scan[key],'HISTORICAL_SCAN_REVIEW_FIELD_DIFFERS:'+key)
    for key in ('origin_inventory_reference','relocation_map_reference','config_reference','fixture_auxiliary_config_reference',
        'fixture_auxiliary_original_reference','fixture_auxiliary_transform_reference'):
        need(plan[key]==scan[key] and plan[key] in plan['source_references'],'UNCHANGED_ACTUAL_SCAN_AUTHORITY:'+key)
    need(plan['origin_inventory_reference']==ORIGIN_INVENTORY_PIN and plan['relocation_map_reference']==RELOCATION_MAP_PIN
        and plan['config_reference']==CONFIG_PIN,'EXACT_FROZEN_LABELS_ORIGIN_MAP_AND3861B_CONFIG_PINS_REQUIRED')
    origin=load_ref(ORIGIN_INVENTORY_PIN);mapping=load_ref(RELOCATION_MAP_PIN);config=load_ref(CONFIG_PIN)
    need(origin.get('schema')=='SECONDARY_LABEL_PAYLOAD512_TRANSFER_INVENTORY_V1' and len(origin['data'])==227
        and len(origin['small'])==54 and mapping.get('schema')=='LABEL_PAYLOAD512_READONLY_RELOCATION_MAP_V1'
        and len(mapping['entries'])==281,'EXACT_ORIGINAL227_PLUS54_RELOCATION_MEMBERS_REQUIRED')
    expected={row['origin_reference']['path']:row for row in [*origin['data'],*origin['small']]}
    moved={row['origin_reference']['path']:row for row in mapping['entries']};targets=set()
    need(len(expected)==len(moved)==281 and set(expected)==set(moved),'EXACT_UNIQUE_ORIGINAL281_ORIGIN_SET_REQUIRED')
    for old,row in moved.items():
        frozen=expected[old];target=triple(row['target_reference'])
        need(row['origin_reference']==frozen['origin_reference'] and row['kind']==frozen['kind']
            and target==strip_triple(frozen['target_locator']) and target['path'] not in targets,'ORIGINAL281_ORIGIN_METADATA_OR_TARGET_CHANGED')
        targets.add(target['path'])
    for row in origin['small']:
        need(triple(moved[row['origin_reference']['path']]['target_reference']) in plan['source_references'],
            'ALL_ORIGINAL54_FROZEN_SMALL_SOURCES_MUST_BE_APPROVED')
    def relocated(value):
        row=moved.get(value['path']);need(row is not None and strip_triple(value)==strip_triple(row['origin_reference']),
            'EXACT_REDUCER_ORIGINAL_ROLE_OR_OWNER_INDEX_PIN_REQUIRED')
        return triple(row['target_reference'])
    need(plan['owner_plan_reference'] in plan['source_references'] and plan['owner_plan_reference']==relocated(config['sources']['plan']),
        'EXACT_ORIGINAL_OWNER_PLAN_ALPHA_BYTE_COPY_REQUIRED')
    owner=load_ref(plan['owner_plan_reference'])
    need((owner['mode'],owner['molecules'],owner['records'],owner['global_records'],owner['shards'])==('pilot',512,4251,11231854,1)
        and config['new_mask_fraction_stop']==0.01 and config['robust_z_review']==20,'UNCHANGED_MATCHED_PILOT_REFERENCE_AND_QUALITY_RULES')
    need(manifest.get('schema')=='LABEL_PAYLOAD_SHARD_MANIFEST_V1' and manifest.get('status')=='PAYLOAD_SHARD_SCANNED_REDUCTION_REQUIRED'
        and manifest.get('execution_endpoint')==ENDPOINT and manifest.get('execution_uid')==UID
        and str(manifest.get('execution_job_id'))=='1884788' and manifest.get('shard_id')==0
        and manifest.get('pre_scan_fixture_tests_passed')==6 and manifest.get('config')==CONFIG_PIN
        and manifest.get('plan')==config['sources']['plan'] and len(manifest['groups'])==16
        and len({row['pid'] for row in manifest['groups']})==16,'ACTUAL_CLOSED_ALPHA16_WORKER_SCAN_MANIFEST_REQUIRED')
    need(manifest['actual_transfer_verification']==PARENT_PINS['scan_transfer_verification_reference']
        and manifest['pre_scan_fixture_gate']==PARENT_PINS['scan_fixture_gate_reference'],'ACTUAL_SCAN227_HASH_AND6_FIXTURE_RECEIPTS_REQUIRED')
    prior_hash=load_ref(PARENT_PINS['scan_transfer_verification_reference']);prior_gate=load_ref(PARENT_PINS['scan_fixture_gate_reference'])
    need(prior_hash.get('status')=='ACTUAL_ALL227_SHA_PASS' and str(prior_hash.get('job_id'))=='1884788'
        and prior_hash.get('uid')==UID and prior_hash.get('body_count')==227
        and prior_hash.get('pre_scan_fixture_gate')==PARENT_PINS['scan_fixture_gate_reference']
        and prior_gate.get('status')=='PASS' and prior_gate['counts']['run']==6,'ACTUAL_SAME_PARENT227_SHA_AFTER_SIX_FIXTURES_REQUIRED')
    ordered=sorted(manifest['groups'],key=lambda row:row['group_index'])
    need([strip_triple(row['report']) for row in ordered]==REPORT_PINS,'ONLY_ACTUAL_ALPHA16_REPORT_PINS_FROM58_COPY_AUTHORITY')
    groups={row['group_index']:row for row in owner['groups']};entries=[];molecules=records=0
    need(len(groups)==16 and set(groups)=={row['group_index'] for row in ordered},'EXACT_ORIGINAL16_OWNER_GROUPS_REQUIRED')
    for receipt,pin in zip(ordered,REPORT_PINS):
        need(pin in plan['source_references'],'EVERY_ACTUAL_ALPHA_GROUP_REPORT_MUST_BE_APPROVED_SMALL_SOURCE')
        report=load_ref(pin);gid=receipt['group_index'];group=groups[gid]
        need(report['group_index']==gid and report['pid']==receipt['pid'] and report.get('schema')=='LABEL_PAYLOAD_GROUP_REPORT_V1'
            and report.get('status')=='OWNER_PAYLOAD_SCANNED' and report['source_job_id']==group['source_job_id']
            and report['records']==group['expected_records'] and report['molecules']==group['expected_molecules']
            and len(report['task_counts'])==14 and all(value==group['expected_records'] for value in report['task_counts'].values())
            and report['source_opens']==report['source_closes'] and report['max_simultaneous_source_handles']==1,
            'ACTUAL_CLOSED_OWNER_COMPLETE_GROUP_REPORT_REQUIRED')
        molecules+=report['molecules'];records+=report['records']
        for kind,key in (('group_details','details'),('candidate_mask','candidate_masks'),('coverage','coverage')):
            value=triple(strip_triple(report[key]));entries.append({'kind':kind,'group_index':gid,'origin_reference':value,'reference':value})
        original=strip_triple(group['owner_index'])
        entries.append({'kind':'selection_owner_index','group_index':gid,'origin_reference':original,'reference':relocated(original)})
    original=strip_triple(owner['expected_roles'])
    entries.append({'kind':'expected_role','group_index':None,'origin_reference':original,'reference':relocated(original)})
    need((molecules,records)==(512,4251) and len(entries)==65 and dict(Counter(row['kind'] for row in entries))==KINDS
        and {kind:sum(row['reference']['bytes'] for row in entries if row['kind']==kind) for kind in KINDS}==KIND_BYTES,
        'EXACT_ACTUAL65_REDUCTION_BODY_LOCATORS_AND38437705_BYTES_REQUIRED')
    inventory=load_ref(plan['input_inventory_reference'])
    need(inventory.get('schema')=='ALPHA_LABEL_PAYLOAD512_REDUCTION_INPUT_INVENTORY_V1'
        and inventory.get('status')=='EXPECTED_INPUTS_PENDING_THIS_ALLOCATION_SHA' and inventory.get('parent_alpha_job_id')=='1884788'
        and inventory.get('scan_manifest_reference')==PARENT_PINS['scan_manifest_reference'] and inventory.get('scientific_config_reference')==CONFIG_PIN
        and inventory.get('owner_plan_reference')==plan['owner_plan_reference'] and inventory.get('relocation_map_reference')==RELOCATION_MAP_PIN
        and inventory.get('group_report_references')==REPORT_PINS and inventory.get('entries')==entries and inventory.get('kind_counts')==KINDS
        and inventory.get('body_files')==65 and inventory.get('body_bytes')==38437705
        and inventory.get('body_read_or_hash_performed_by_builder') is False and inventory.get('future_allocation_body_verification_reference') is None,
        'EXACT_METADATA_ONLY65_INPUT_INVENTORY_REBUILT_FROM_REAL_PARENTS_REQUIRED')
    need(plan['data_references']==[row['reference'] for row in entries] and plan['data_total_bytes']==38437705,
        'EXACT65_ORDERED_BODY_TRIPLES_REQUIRED_NOT_PREVERIFIED')
    need(plan.get('transfer_verification_reference') is None
        and plan.get('transfer_verification_expected_output_path')==str(OUT/'input_verification.json'),
        'NO_FUTURE65_BODY_HASH_RECEIPT_PIN_ALLOWED')
    need(plan['source_equivalence_reference'] in plan['source_references'],'ACTUAL_REDUCER_SOURCE_EQUIVALENCE_MUST_BE_APPROVED')
    equivalence=load_ref(plan['source_equivalence_reference'])
    need(equivalence.get('schema')=='ALPHA_LABEL_PAYLOAD512_REDUCER_SOURCE_EQUIVALENCE_V1' and equivalence.get('status')=='PASS'
        and equivalence.get('science_reduction_body_inverse_source_bytes_equal') is True
        and equivalence.get('science_reduction_body_inverse_AST_equal') is True,'ACTUAL_ORIGINAL_REDUCTION_CORE_EQUIVALENCE_REQUIRED')
    for key,path in (('alpha_reducer_reference',ROOT/'code/payload_reduce_alpha_v1/run.py'),
        ('original_reducer_reference',FROZEN/'workflows/data_v1_final/labels/payload_audit_v1/reduce.py'),
        ('coverage_helper_module_reference',FROZEN/'workflows/data_v1_final/labels/source_status_v1/reduce.py'),
        ('unchanged_numeric_shape_mask_kernel_reference',FROZEN/'workflows/data_v1_final/labels/payload_audit_v1/payload.py'),
        ('unchanged_six_fixture_source_reference',FROZEN/'workflows/data_v1_final/labels/payload_audit_v1/test_payload.py')):
        value=ref(path);need(value in plan['source_references'] and all(equivalence[key][part]==value[part] for part in ('bytes','sha256')),
            'EXACT_OLD_SCIENCE_AND_NEW_REDUCER_SOURCE_BYTES_BINDING_REQUIRED')
    return {'parent_alpha_job_id':'1884788','parent_actual_allocated_core_seconds':912,'fixed_body_files':65,'fixed_body_bytes':38437705,
        'frozen_relocation_members':281,'frozen_small_sources':54,'body_SHA_verified_by_login_controller':False,
        'matched_pilot_TRAIN_reference_only':True,'median_MAD_refit':False,'full_or_export_or_final_D4_release':False}


def readonly(input_path,deployment_path,node,seconds,**unused):
    need(deployment_path is None,'EXACT_LABEL_REDUCER_PLAN_HAS_NO_DEPLOYMENT_WRAPPER')
    plan=load(input_path);refs={};protocol=PROTOCOLS[KEY]
    need(plan.get('producer_key')==plan.get('scope_key')==KEY and plan.get('schema')==protocol['plan']
        and plan.get('stage')==protocol['stage'] and plan.get('scope_parameters')==PARAMETERS
        and plan.get('kind')=='analysis' and plan.get('pilot') is False and plan.get('endpoint')==ENDPOINT and plan.get('uid')==UID
        and plan.get('run_root')==str(ROOT) and plan.get('node')==node and plan.get('cpus')==16 and plan.get('memory_policy')==POLICY
        and type(plan.get('wall_seconds')) is int and plan['wall_seconds']==seconds==3600 and plan.get('output_cap_bytes')==2<<30
        and plan.get('output_directory')==str(OUT),'ONLY_EXACT_ALPHA_LABEL512_REDUCER_RESOURCE_AND_SCOPE_ALLOWED')
    need(plan.get('resource_evidence_output')==str(OUT)+'_resource_observation' and plan.get('resource_evidence_output_cap_bytes')==64<<20
        and plan['storage_reservation_reference'] in plan['source_references'],'EXACT_SEPARATE_OBSERVER64MIB_RESERVATION_PIN_REQUIRED')
    review=load_ref(plan['root_review_reference'])
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review.get('status')=='APPROVED_FOR_EXACT_STAGE'
        and review.get('reviewer')=='root','EXACT_LABEL_REDUCER_ROOT_REVIEW_REQUIRED')
    for key in REVIEW_FIELDS:need(plan[key]==review[key],'EXACT_LABEL_REDUCER_ROOT_SCOPE_DIFFERS:'+key)
    need(plan['source_references']==review['approved_source_references'],'EXACT_REVIEWED_REDUCER_SOURCE_SET_REQUIRED')
    bodies=plan['data_references'];need(isinstance(bodies,list) and len(bodies)==65,'EXACT65_REDUCER_BODY_LOCATOR_LIST_REQUIRED')
    body_paths={triple(value)['path'] for value in bodies}
    need(len(body_paths)==65 and not any(value['path'] in body_paths for value in [*plan['source_references'],*plan['parent_evidence_references']]),
        'NO_REDUCER_BODY_CAN_BE_HASHED_AS_PRE_FIXTURE_SMALL_METADATA')
    for value in [*plan['source_references'],*plan['parent_evidence_references'],ref(input_path),plan['root_review_reference']]:
        value=normalized(value);verify(value)
        need(value['path'] not in refs or refs[value['path']]==value,'CONFLICTING_LABEL_REDUCER_SMALL_SOURCE_PIN')
        refs[value['path']]=value
    for path in (HERE/'controller.py',HERE/'adapters.py',Path(__file__).absolute(),
        ROOT/'code/secondary_cpu_queue_v1/common.py',ROOT/'code/secondary_cpu_queue_v1/__init__.py'):
        need(ref(path) in plan['source_references'],'ACTUAL_V8_CONTROLLER_AND_BASE_IMPORTED_SOURCES_REQUIRED')
    primary=ROOT/'code/payload_reduce_alpha_v1/run.py'
    for directory in (primary.parent,ROOT/'code/payload_audit_alpha_v1'):
        for path in directory.iterdir():
            if path.is_file() and path.suffix in {'.py','.json','.md'}:
                need(ref(path) in plan['source_references'],'EVERY_NEW_REDUCER_AND_REUSED_ALPHA_SOURCE_MUST_BE_APPROVED:'+path.name)
    need(plan['resource_authority_reference'] in plan['source_references'],'ACTUAL_ALPHA_RESOURCE_AUTHORITY_MUST_BE_APPROVED')
    for key in ('input_inventory_reference','owner_plan_reference','origin_inventory_reference','relocation_map_reference','config_reference',
        'fixture_auxiliary_config_reference','fixture_auxiliary_original_reference','fixture_auxiliary_transform_reference'):
        need(plan[key] in plan['source_references'],'EXPLICIT_APPROVED_REDUCER_METADATA_AUTHORITY:'+key)
    proof=literal(plan['startup_proof_path']);out=literal(plan['output_directory'])
    argv=[plan['python'],'-B','-m',protocol['module'],'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    need(plan.get('execution_argv')==argv and Path(argv[0]).is_absolute(),'EXACT_ALPHA_REDUCER_PRIMARY_AND_ALL_EIGHT_ARGV_REQUIRED')
    archive=parent_and_input_authority(plan)
    return {'producer':'readonly','input_reference':ref(input_path),'producer_argv':argv,
        'producer_plan_reference':ref(input_path),'producer_review_reference':plan['root_review_reference'],
        'producer_authority_reference':plan['resource_authority_reference'],'source_references':list(refs.values()),
        'data_reference_locators_only':bodies,'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':plan['output_cap_bytes'],
        'producer_working_directory':str(ROOT/'code'),'proof_schema':protocol['proof'],'request_kind':'analysis','pilot':False,
        'scope_key':KEY,'scope_parameters':PARAMETERS,'stage':protocol['stage'],'scope_mode':'BOUNDED_READONLY_ANALYSIS','performance_profile':False,
        'resource_reservation_reference':plan['storage_reservation_reference'],'resource_evidence_output':plan['resource_evidence_output'],
        'resource_evidence_output_cap_bytes':plan['resource_evidence_output_cap_bytes'],'fixed_archive_authority':archive}

def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    adapter=request['adapter']
    need(adapter['producer']=='readonly' and adapter['scope_key'] in PROTOCOLS and request['kind']==adapter['request_kind']=='analysis'
        and request['pilot'] is adapter['pilot'] and request['scope_key']==adapter['scope_key']
        and request['scope_parameters']==adapter['scope_parameters'] and request['stage']==adapter['stage']
        and request['scope_mode']==adapter['scope_mode'] and request['performance_profile'] is adapter['performance_profile'],
        'ONLY_EXACT_ALPHA_LABEL512_REDUCER_REQUEST_PROTOCOL_ALLOWED')
    return {'schema':adapter['proof_schema'],'endpoint':ENDPOINT,'uid':UID,'node':request['node'],
        'boot_id':probe['boot_id'],'job_id':str(jid),'observed_unix_seconds':probe['observed_unix_seconds'],
        'memory_policy':POLICY,'memory_limits_requested':False,'exclusive_requested':False,
        'script_reference':request['script_reference'],'controller_evidence':controller_evidence,
        'source_target_verification':request['verified_target_references'],
        'actual_gate_process':probe['gate_process'],'actual_memory_environment':probe['actual_memory_environment'],
        'scheduler_memory_is_recorded_not_an_admission_threshold':True,
        'other_jobs_modified':False,'forced_signals_sent':False,'job_metadata':raw,
        'request':{'kind':'analysis','pilot':adapter['pilot'],'cpus':16,'memory_policy':POLICY,
                   'wall_seconds':request['wall_seconds'],'execution_argv':adapter['producer_argv']},
        'plan_reference':adapter['producer_plan_reference'],'root_review_reference':adapter['producer_review_reference'],
        'account_free_bytes':storage['effective_free_bytes'],'effective_free_basis':storage['effective_free_basis'],
        'storage_observation_reference':storage_reference,'storage_observation':storage,
        'scope_key':adapter['scope_key'],'stage':adapter['stage'],'scope_mode':adapter['scope_mode'],
        'performance_profile':adapter['performance_profile'],'bounded_readonly_scope_only':True,
        'bounded_source_acquisition_scope_only':False,'scientific_population_or_full_SQL_status_coverage_accepted':False}


