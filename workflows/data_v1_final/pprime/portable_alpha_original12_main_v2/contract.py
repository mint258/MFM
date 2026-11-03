"""Closed component and CPU-produced dispatch controls, never a PREP C0 claim."""
import pathlib,re
from workflows.data_v1_final.pprime.formal_packed_day_v1 import contract as F
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v3 import contract as Sharded,root_metadata as Small
Q=F.Q;M=F.M;O=F.O;P=F.P;need=F.need;meta=F.meta;unique=F.unique;small=Small.small
MAIN_ENDPOINT='202.38.247.57:22';ALPHA_ENDPOINT='218.192.171.238:22'
KEY='pprime_alpha_original12_portable_main_export_v1'
HERE=Q.REPO/'workflows/data_v1_final/pprime/portable_alpha_original12_main_v2'
MODULE='workflows.data_v1_final.pprime.portable_alpha_original12_main_v2.run'
BASE=Q.ROOT/'artifacts/pprime_alpha_original12_portable_main_v2'
FILES=('__init__.py','contract.py','io.py','packets.py','relay.py','run.py','metadata.py','README.md')
WALL=86400;NODES=tuple('compute-0-'+str(v) for v in (2,*range(8,20)))
REQUIRED=('component_plan_reference','external_assignment_reference','additional_runtime_source_inventory_reference',*F.RESOURCE)
SOFTWARE_WHITELIST={'path':str(Q.REPO/'configs/data_v1/pprime/original2000_explicit_readonly_software_whitelist_20261029.json'),
  'bytes':31385,'sha256':'c70761de0a08cf1030cea67cd3b37dbb9fab50c919ffeddc37c7ac457c5d957d'}

def registered_software_specs(context):
    specs=P.software_original_specs(context);config=small(SOFTWARE_WHITELIST)
    need(config['schema']=='PPRIME2000_EXISTING_PRODUCER_PINNED_READONLY_SOFTWARE_CONFIG_PATHS_V1',
      'EXACT_ORIGINAL14_PLUS22_TRANSPORT_WHITELIST')
    refs=[P.triple(v) for v in config['existing_frozen_references_by_category']['xtb_project_assets']]
    need(len(refs)==22 and len({v['path'] for v in refs})==22,'EXACT22_ORIGINAL_XTB_PROJECT_ASSETS')
    package=meta(context['execution_asset_verification_context']['manifest_reference'])
    declared=[P.triple(v) for v in context['execution_asset_references']]
    for ref in refs:
        need(ref in declared,'EXISTING_DECLARED_XTB_ASSET_NOT_NEW_SOFTWARE')
        matches=[a for a in package['assets'] if a.get('source_path')==ref['path']
                 and a['sha256']==ref['sha256'] and a['bytes']==ref['bytes']]
        need(matches and len({(a['source_uid'],a['mode'],a.get('resolved_source_path')) for a in matches})==1,
          'ORIGINAL_REPRODUCTION_XTB_SOURCE_UID_MODE_RESOLVED_CONSENSUS')
        a=matches[0];need(a['source_uid'] in (0,1278) and type(a['mode'])is int,'ORIGINAL_REGISTERED_SOFTWARE_OWNER_MODE')
        specs[ref['path']]={'reference':ref,'source_uid':a['source_uid'],'mode':a['mode'],
          'resolved_source_path':a.get('resolved_source_path'),'role':a.get('role'),
          'manifest_reference':context['execution_asset_verification_context']['manifest_reference']}
    need(len(specs)==36,'EXACT14_PLUS22_REGISTERED_SOFTWARE_FILES')
    return specs

def runtime_source_references():
    parent=HERE.parent
    names=('common.py','geometry.py','engine_adapter.py','raw_archive.py','export_families.py','prepare_pilot.py',
           'retention_v1/retention_policy_v1.py','raw_policy_proposal_v1/policy_v1.py')
    return [Q.pin(parent/name) for name in names]

def parameters(p):
    need(p['node'] in NODES and type(p['maximum_molecules'])is int and 1<=p['maximum_molecules']<=5000,
      'FINITE_MAIN_ANALYSIS16_ORIGINAL_COMPONENT_EXPORT')
    need(type(p['output_cap_bytes'])is int and 4<<20<p['output_cap_bytes']<=64<<30,'ROOT_EXPLICIT_FINITE_EXPORT_CAP')
    return {'component_only':True,'maximum_MIDs':p['maximum_molecules'],'maximum_records':2*p['maximum_molecules'],
      'original_first2_seed':20261025,'original12_tasks':list(O.TASKS),'native_invokes':0,'UFF_or_embedding_calls':0,
      'selection':'CLOSED_COMPONENT_MID_DESCENDING_UNCLAIMED_ORIGINAL_PREPARED_RANKS',
      'packets_are_not_claims':True,'global_once_claims_created':0,'whole_LMDB_files_copied':False,
      'one_science_source_to_portable_IO_mapping':True,'software_working_budget_bytes':64<<30,'RSS_limit_bytes':56<<30,
      'cpus':16,'node':p['node'],'wall_seconds':WALL,'output_cap_bytes':p['output_cap_bytes'],
      'scientific_PASS':False,'final_Common_or_training_admission':False}

def bootstrap(p):
    from workflows.data_v1_final.pprime.current_prepared_component_v1 import authority as Component
    cp=small(p['component_plan_reference']);h,component_sources,component_data=Component.metadata_bind(cp,allowed_owner='ALPHA')
    b=F.bootstrap(cp);href=cp['prepared_shard_header_reference']
    need(h['schema']=='PPRIME_CPU_CLOSED_ASSIGNED_PAIRS_HEADER_V2' and h['native_invokes']==0
      and h['production_once_written'] is False and h['native_physical_IDs_and_original_first2_input_hashes_verified'] is True
      and h['source_context_reference']==cp['source_context_reference']
      and h['original_protocol_reference']==cp['original_protocol_reference'],'ORIGINAL_PUBLISHED_COMPONENT_NOT_PARENT_C0')
    review=meta(cp['shared_preparation_root_acceptance_reference'])
    need(p['external_assignment_reference']==review['external_assignment_reference'],
      'SAME_SOURCE_VERIFIED_ROOT_EXCLUSIVE_ALPHA_COMPONENT_HANDOFF')
    audit=small(h['audit_membership_reference'])
    need(audit['schema']=='WP5_STRATIFIED_RECORD_AUDIT_V1' and audit['status']=='AUDIT_MEMBERSHIP_CLOSED'
      and P.triple(audit['selected_records'])==h['audit_selected_reference'],'ORIGINAL_AUDIT_LOCATORS')
    source_plan=meta(b['pilot']['source_plan']);sources=source_plan['sources']
    need(len(sources)==11 and {int(v['shard_id']) for v in sources}==set(range(11)),'ELEVEN_MAIN_ORIGIN_SOURCES')
    inventory=small(p['additional_runtime_source_inventory_reference'])
    need(inventory['schema']=='ROOT_EXPLICIT_ORIGINAL_PPRIME_RUNTIME_PYTHON_SOURCE_INVENTORY_V1'
      and inventory['reviewer']=='root' and inventory['source_file_count']==len(inventory['source_references'])
      and inventory['source_root']=='/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime/phychem_mfm',
      'EXPLICIT_ORIGINAL_RUNTIME_PYTHON_SOURCES_NO_MODEL_EDITS_OR_CREDENTIAL_COPY')
    extra=inventory['source_references']
    need(all(v['path'].endswith('.py') and pathlib.Path(inventory['source_root']) in pathlib.Path(v['path']).parents
      for v in extra),'ONLY_ROOT_REGISTERED_RUNTIME_PYTHON_SOURCE')
    if 'additional_runtime_source_references' in p:
        need(p['additional_runtime_source_references']==extra,'UNCHANGED_REGISTERED_RUNTIME_SOURCE_LIST')
    data=unique([*b['data'],*component_data,*extra])
    # Original eight runtime files already have frozen SOURCE authority. Keep
    # SOURCE and DATA disjoint; CPU original_copy still verifies their bytes.
    refs=unique([*b['refs'],*component_sources,p['component_plan_reference'],p['external_assignment_reference'],href,
      h['audit_membership_reference'],h['publication_manifest_reference'],h['shared_prepare_plan_reference'],h['shared_prepare_proof_reference']])
    # Component-specific authorities are metadata; no DATA locator is converted
    # into a login source pin. metadata_bind verifies its own complete chain.
    for k,v in cp.items():
        if k.endswith('_reference') and isinstance(v,dict) and set(v)=={'path','bytes','sha256'}:
            if v not in data and not any(t in pathlib.Path(v['path']).name for t in ('.DATA.','.parquet','.duckdb','.sqlite','.jsonl')):
                refs=unique([*refs,v])
    refs=unique([*refs,p['additional_runtime_source_inventory_reference'],SOFTWARE_WHITELIST])
    return dict(b,component_plan=cp,component_header=h,component_header_reference=href,component_authority=Component,
      audit=audit,sources=sources,data=data,refs=refs,additional_runtime_source_references=extra)

def sources(p):
    from workflows.data_v1_final.pprime.current_prepared_component_v1 import authority as Component
    cp=small(p['component_plan_reference'])
    return unique([*Sharded.sources(cp),*[Q.pin(HERE/n) for n in FILES],
      *[Q.pin(v) for v in pathlib.Path(Component.__file__).parent.glob('*.py')]])

def export_closed(reference):
    closed=small(reference)
    need(closed['schema']=='ROOT_ACTUAL_PPRIME_ALPHA_PORTABLE_EXPORT_CLOSURE_V1'
      and closed['status']=='ACTUAL_CPU_C0_PORTABLE_PACKET_SOURCE_ONLY' and closed['reviewer']=='root',
      'ROOT_ACTUAL_EXPORT_CPU_C0_REQUIRED')
    r,p,proof,actual=Small.closed_parent(closed['parent'],KEY,MODULE,'PPRIME_ALPHA_PORTABLE_MAIN_EXPORT_RECEIPT_V1')
    need(r['portable_manifest_reference']==closed['portable_manifest_reference'] and r['native_invokes']==0
      and r['global_once_claims_created']==0 and r['scientific_PASS'] is False,'REAL_ZERO_INVOKE_EXPORT_NOT_CLAIM_OR_SCIENCE_PASS')
    manifest=small(r['portable_manifest_reference'])
    need(manifest['schema']=='PPRIME_ALPHA_ORIGINAL12_PORTABLE_INPUTS_V1' and manifest['packets_are_not_claims'] is True
      and manifest['prepared_header_reference']==p['prepared_shard_header_reference']
      and manifest['external_assignment_reference']==p['external_assignment_reference'],
      'ACTUAL_CLOSED_EXPORT_BOUND_COMPONENT_AND_EXTERNAL_ASSIGNMENT')
    return manifest,p,r

def validate_authorization(a,manifest,key):
    need(a['schema']=='PPRIME_ALPHA_DISPATCH_AUTHORIZATION_V1' and a['physical_key']==key
      and re.fullmatch('[0-9a-f]{64}',key) and a['prepared_header_reference']==manifest['prepared_header_reference']
      and a['original_protocol_reference']==manifest['original_protocol_reference']
      and a['external_assignment_reference']==manifest['external_assignment_reference']
      and a['target_endpoint']==ALPHA_ENDPOINT and a['target_uid']==1264 and a['packet_is_not_claim'] is True
      and a['original_ledger_path']==str(Q.ROOT/'artifacts/pprime_retention_v1/pilot_once/physical_records_v1'/(key+'.json')),
      'CPU_CLOSED_SMALL_DISPATCH_AUTHORIZATION_ONLY_NO_LOGIN_RECOMPUTATION')

def relay_binding(binding):
    need(binding['schema']=='ROOT_APPROVED_PPRIME_ALPHA_DISPATCH_RELAY_V1' and binding['status']=='APPROVED_BOUNDED_METADATA_ONLY_RELAY'
      and binding['reviewer']=='root' and binding['uid']==1278 and binding['endpoint']==MAIN_ENDPOINT,
      'EXACT_ROOT_LOGIN_CONTROL_AUTHORITY')
    manifest,p,r=export_closed(binding['portable_export_closure_reference'])
    need(manifest['records']>0,'NO_EMPTY_ALPHA_NATIVE_OR_METADATA_RELAY_WORK')
    need(binding['portable_manifest_reference']==r['portable_manifest_reference']
      and binding['external_assignment_reference']==manifest['external_assignment_reference'],'SAME_ACTUAL_C0_EXPORT_ASSIGNMENT')
    for name in FILES:need(Q.pin(HERE/name) in binding['source_references'],'ROOT_FROZEN_RELAY_SOURCE:'+name)
    need(type(binding['relay_seconds'])is int and 0<binding['relay_seconds']<=86400
      and 1<=binding['poll_seconds']<=30 and 10<=binding['heartbeat_max_age_seconds']<=300
      and 0<binding['maximum_transport_calls']<=100000 and 4<<20<binding['maximum_control_bytes']<=1<<30,
      'FINITE_METADATA_RELAY_WITHOUT_SLURM_STANDBY')
    proof=small(binding['alpha_startup_proof_reference']);parent=binding['alpha_parent'];gate=proof['actual_gate_process']
    need(proof['schema']=='SECONDARY_PPRIME_ORIGINAL12_DAY_STARTUP_V1' and proof['endpoint']==ALPHA_ENDPOINT and proof['uid']==1264
      and proof['scope_key']=='pprime_formal_original12_alpha_v1' and proof['stage']=='PPRIME_ORIGINAL12_FORMAL_GENERATION'
      and proof['execution_admission_granted'] is True and proof['bounded_generation_scope_only'] is True
      and proof['request']['kind']=='qm' and proof['request']['pilot'] is False and proof['request']['cpus']==16
      and proof['request']['wall_seconds']==86400 and proof['request']['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
      and parent=={'endpoint':ALPHA_ENDPOINT,'uid':1264,'job_id':str(proof['job_id']),'node':proof['node'],
                  'boot_id':proof['boot_id'],'parent_pid':gate['pid'],'parent_ticks':str(gate['start_ticks'])},
      'REAL_ALPHA_UID_JOB_BOOT_GATE_PROCESS_NOT_MAIN_NATIVE_PARENT')
    need(proof['portable_inputs_origin_reference']==binding['portable_manifest_reference'],'ACTUAL_ALPHA_PROOF_ORIGIN_PACKET_BINDING')
    inventory=small(manifest['dispatch_authorization_inventory_reference']);allow={}
    need(inventory['schema']=='PPRIME_ALPHA_SMALL_DISPATCH_AUTHORIZATION_INVENTORY_V1'
      and inventory['records']==manifest['records'] and len(inventory['page_references'])<=80,'FINITE_CPU_AUTHORIZATION_PAGES')
    for ref in inventory['page_references']:
        page=small(ref);need(page['schema']=='PPRIME_ALPHA_SMALL_DISPATCH_AUTHORIZATION_PAGE_V1'
          and 0<len(page['entries'])<=128,'SMALL_CONTROL_PAGE_NOT_SCIENCE_BODY')
        for entry in page['entries']:
            key=entry['physical_key'];need(key not in allow,'UNIQUE_CPU_AUTHORIZED_PHYSICAL_KEYS');allow[key]=entry['authorization_reference']
    need(len(allow)==manifest['records'],'EXACT_CPU_EXPORTED_AUTHORIZATION_COUNT')
    return manifest,allow,parent
